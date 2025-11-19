// src/charts/options/builders/main.js
// ==============================
// V7.0 - 添加诊断日志版
//
// 新增：
//   - 第150行后：输出主图的 yAxis[1] 和 series 使用情况
// ==============================

import { getChartTheme } from "@/charts/theme";
import { hexToRgba } from "@/utils/colorUtils";
import { formatNumberScaled } from "@/utils/numberUtils";
import { STYLE_PALETTE, DEFAULT_KLINE_STYLE } from "@/constants";
import { applyLayout } from "../positioning/layout";
import { makeMainTooltipFormatter } from "../tooltips/index";

function asArray(x) {
  return Array.isArray(x) ? x : [];
}
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

export function buildMainChartOption(
  {
    candles,
    indicators,
    chartType,
    maConfigs,
    freq,
    klineStyle,
    adjust,
    reducedBars,
    mapOrigToReduced,
  },
  ui
) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);

  const series = [];

  const ks = klineStyle || DEFAULT_KLINE_STYLE || {};
  const MK = ks.mergedK || DEFAULT_KLINE_STYLE.mergedK || {};
  const showOriginal = (ks.originalEnabled ?? true) === true;
  const showMerged = (ks.mergedEnabled ?? true) === true;
  const mergedFirst = String(MK.displayOrder || "first") === "first";
  const originalZ = showOriginal && showMerged ? (mergedFirst ? 2 : 3) : 3;
  const mergedZ = showOriginal && showMerged ? (mergedFirst ? 3 : 2) : 3;

  if (chartType === "kline") {
    if (showOriginal) {
      const upColor = ks.upColor || DEFAULT_KLINE_STYLE.upColor;
      const downColor = ks.downColor || DEFAULT_KLINE_STYLE.downColor;
      const upPct =
        Math.max(0, Math.min(100, Number(ks.originalFadeUpPercent ?? 100))) /
        100;
      const downPct =
        Math.max(0, Math.min(100, Number(ks.originalFadeDownPercent ?? 0))) /
        100;
      const upFill = upPct === 0 ? "transparent" : hexToRgba(upColor, upPct);
      const downFill =
        downPct === 0 ? "transparent" : hexToRgba(downColor, downPct);

      const ohlc = list.map((d) => [d.o, d.c, d.l, d.h]);
      const klineSeries = {
        type: "candlestick",
        name: "原始K线",
        data: ohlc,
        itemStyle: {
          color: upFill,
          color0: downFill,
          borderColor: upColor,
          borderColor0: downColor,
          borderWidth:
            ks.originalBorderWidth ?? DEFAULT_KLINE_STYLE.originalBorderWidth,
        },
        z: originalZ,
      };
      if (ks.barPercent && ks.barPercent < 100)
        klineSeries.barWidth = `${ks.barPercent}%`;
      series.push(klineSeries);
    }

    if (showMerged && Array.isArray(reducedBars) && reducedBars.length) {
      const outlineW = Math.max(0.1, Number(MK.outlineWidth));
      const fallbackUp = DEFAULT_KLINE_STYLE.mergedK.upColor;
      const fallbackDn = DEFAULT_KLINE_STYLE.mergedK.downColor;
      const upC = MK.upColor || fallbackUp;
      const dnC = MK.downColor || fallbackDn;

      const fillAlpha = Math.max(
        0,
        Math.min(1, Number((MK.fillFadePercent ?? 0) / 100))
      );

      const upFill =
        fillAlpha === 0 ? "transparent" : hexToRgba(upC, fillAlpha);
      const dnFill =
        fillAlpha === 0 ? "transparent" : hexToRgba(dnC, fillAlpha);

      const n = list.length;
      const baseLow = new Array(n).fill(null);
      const hlSpan = new Array(n).fill(null);
      const upIndexSet = new Set();

      for (const rb of reducedBars) {
        const idx = Math.max(
          0,
          Math.min(n - 1, Number(rb?.anchor_idx_orig ?? rb?.end_idx_orig ?? 0))
        );
        const hi = Number(rb?.g_pri),
          lo = Number(rb?.d_pri);
        if (!Number.isFinite(hi) || !Number.isFinite(lo) || hi < lo) continue;
        baseLow[idx] = lo;
        hlSpan[idx] = hi - lo;
        if (Number(rb?.dir_int || 0) > 0) upIndexSet.add(idx);
      }

      series.push({
        id: "MERGED_K_BASE",
        name: "合并K线",
        type: "bar",
        stack: "merged_k",
        data: baseLow,
        itemStyle: { color: "transparent" },
        ...(ks.barPercent && ks.barPercent < 100
          ? { barWidth: `${ks.barPercent}%` }
          : {}),
        barGap: "-100%",
        silent: true,
        z: mergedZ,
      });

      series.push({
        id: "MERGED_K_SPAN",
        name: "合并K线",
        type: "bar",
        stack: "merged_k",
        data: hlSpan.map((v, i) =>
          v == null
            ? null
            : {
                value: v,
                itemStyle: {
                  borderColor: upIndexSet.has(i) ? MK.upColor : MK.downColor,
                },
              }
        ),
        ...(ks.barPercent && ks.barPercent < 100
          ? { barWidth: `${ks.barPercent}%` }
          : {}),
        barGap: "-100%",
        itemStyle: {
          color: (p) => (upIndexSet.has(p.dataIndex) ? upFill : dnFill),
          borderColor: (p) =>
            upIndexSet.has(p.dataIndex) ? MK.upColor : MK.downColor,
          borderWidth: outlineW,
          opacity: 1,
        },
        z: mergedZ,
      });
    }

    Object.entries(maConfigs || {}).forEach(([key, conf]) => {
      if (!conf || !conf.enabled || !Number.isFinite(+conf.period)) return;
      const data = inds[key];
      if (!data) return;
      series.push({
        id: key,
        type: "line",
        name: `MA${conf.period}`,
        data,
        showSymbol: false,
        smooth: false,
        lineStyle: {
          width: conf.width ?? 1,
          type: conf.style ?? "solid",
          color: conf.color,
        },
        itemStyle: { color: conf.color },
        color: conf.color,
        emphasis: { disabled: true },
        z: 3,
      });
    });
  } else {
    const closeLineColor =
      (STYLE_PALETTE.lines[5] && STYLE_PALETTE.lines[5].color) ||
      STYLE_PALETTE.lines[0].color;
    series.push({
      type: "line",
      name: "Close",
      data: list.map((d) => d.c),
      showSymbol: false,
      smooth: true,
      lineStyle: { color: closeLineColor, width: 1.0 },
      itemStyle: { color: closeLineColor },
      color: closeLineColor,
    });
  }

  const mainYAxis = {
    scale: true,
    axisPointer: {
      show: true,
      triggerOn: 'mousemove|click',
      label: {
        show: true,
        formatter: function (params) {
          const val =
            typeof params.value === "object" && params.value !== null
              ? params.value.value
              : params.value;
          return formatNumberScaled(val, { digits: 2, allowEmpty: true });
        },
      },
      lineStyle: {
        color: theme.axisLineColor,
        width: 1,
        type: "dashed",
      },
    },
  };

  const overlayMarkerYAxis = {
    type: "value",
    min: 0,
    max: 1,
    show: false,
    scale: false,
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { show: false },
    axisPointer: {
      show: false,
    },
  };

  // ===== 新增：诊断日志 =====
  console.log('[DIAG][main.js] 主图 yAxis 配置', {
    yAxis数量: 2,
    yAxis0_axisPointer: mainYAxis.axisPointer ? '有配置' : 'undefined',
    yAxis1_完整配置: overlayMarkerYAxis,
    yAxis1_axisPointer: JSON.stringify(overlayMarkerYAxis.axisPointer),
  });

  let option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    axisPointer: {
      link: [{ xAxisIndex: "all" }],
    },
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "cross",
        crossStyle: {
          color: theme.axisLineColor || "#999",
          width: 1,
          type: "dashed",
        },
      },
      appendToBody: false,
      confine: true,
      formatter: makeMainTooltipFormatter({
        theme,
        chartType,
        freq,
        candles: list,
        maConfigs,
        adjust,
        klineStyle: ks,
        reducedBars,
        mapOrigToReduced,
      }),
      className: "ct-fixed-tooltip",
      borderWidth: 0,
      backgroundColor: "rgba(20,20,20,0.85)",
      textStyle: { color: theme.textColor, fontSize: 12, align: "left" },
    },
    xAxis: { type: "category", data: [] },
    yAxis: [mainYAxis, overlayMarkerYAxis],
    series,
  };

  if (ui?.tooltipPositioner) {
    option.tooltip.position = ui.tooltipPositioner;
  }

  // ===== 新增：在 applyLayout 前输出 =====
  console.log('[DIAG][main.js] applyLayout 前', {
    yAxis数量: option.yAxis?.length,
    yAxis1_axisPointer: JSON.stringify(option.yAxis?.[1]?.axisPointer),
  });

  option = applyLayout(
    option,
    { ...ui, isMain: true, leftPx: 72 },
    { candles: list, freq }
  );

  // ===== 新增：在 applyLayout 后输出 =====
  console.log('[DIAG][main.js] applyLayout 后', {
    yAxis数量: option.yAxis?.length,
    yAxis1_axisPointer: JSON.stringify(option.yAxis?.[1]?.axisPointer),
    yAxis1_完整: option.yAxis?.[1],
  });

  // ===== 新增：输出 series 使用情况 =====
  console.log('[DIAG][main.js] series 使用情况', {
    总series数量: option.series?.length,
    使用yAxisIndex1的series: option.series?.filter(s => s.yAxisIndex === 1).map(s => ({
      id: s.id,
      name: s.name,
      type: s.type,
      dataLength: s.data?.length
    })),
  });

  return option;
}