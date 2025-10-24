// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options\builders\main.js
// ==============================
// 说明：主图 option 构造器（K 线 / 合并K / MA）
// - tooltip 内容统一来自 tooltips 模块；position 由外部 ui.tooltipPositioner 注入
// - yAxis：主轴 + 覆盖轴（隐藏）
// - 仅联动 X 轴（竖线），不联动 Y 轴（水平线）
// - FIX: 保持主图与副图的 axisPointer 规则完全一致，实现“悬浮窗十字，其余竖线”效果。
// ==============================

import { getChartTheme } from "@/charts/theme";
import { hexToRgba } from "@/utils/colorUtils";
import { formatNumberScaled } from "@/utils/numberUtils";
import {
  STYLE_PALETTE,
  DEFAULT_KLINE_STYLE,
} from "@/constants";
import { applyUi } from "../ui/applyUi";
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
    maConfigs, // <--- 注意：这个参数由 useViewRenderHub 从 settings 传入
    freq,
    klineStyle, // <--- 注意：这个参数由 useViewRenderHub 从 settings 传入
    adjust,
    reducedBars,
    mapOrigToReduced,
  },
  ui
) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const dates = list.map((d) => d.t);
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
          borderWidth: 1.2,
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

      const upFill = fillAlpha === 0 ? "transparent" : hexToRgba(upC, fillAlpha);
      const dnFill = fillAlpha === 0 ? "transparent" : hexToRgba(dnC, fillAlpha);

      const n = dates.length;
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
      show: true, // 保持为 true, 由 link 机制统一控制
      label: {
        show: !!ui?.isHovered,
        formatter: function (params) {
          const val =
            typeof params.value === "object" && params.value !== null
              ? params.value.value
              : params.value;
          return formatNumberScaled(val, { digits: 2, allowEmpty: true });
        },
      },
      // FIX: 通过颜色控制可见性, 悬浮时可见, 否则透明
      lineStyle: {
        color: ui?.isHovered ? theme.axisLineColor : "transparent",
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
    // FIX: 显式禁用第二Y轴的指针
    axisPointer: {
      show: false,
    },
  };

  let option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    axisPointer: {
      link: [{ xAxisIndex: "all" }],
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
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
    xAxis: { type: "category", data: dates },
    yAxis: [mainYAxis, overlayMarkerYAxis],
    series,
  };

  if (ui?.tooltipPositioner) {
    option.tooltip.position = ui.tooltipPositioner;
  }

  option = applyUi(
    option,
    {
      ...ui,
      isMain: true,
      leftPx: 72,
    },
    { dates, freq }
  );

  return option;
}
