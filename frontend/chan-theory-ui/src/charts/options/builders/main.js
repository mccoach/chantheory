// src/charts/options/builders/main.js
// ==============================
// V8.0 - 主图柱宽单一参数版（barPercent 统一控制原始K与合并K）
// 改动：
//   1) 新增：统一读取 klineStyle.barPercent（10~100, integer）
//   2) 原始K(candlestick) 与 合并K(bar stack) 统一显式设置 barWidth
//   3) 删除旧逻辑：仅当 barPercent < 100 才设置 barWidth（避免隐式默认宽度产生第二套规则）
// ==============================

import { getChartTheme } from "@/charts/theme";
import { hexToRgba } from "@/utils/colorUtils";
import { formatNumberScaled } from "@/utils/numberUtils";
import { STYLE_PALETTE, DEFAULT_KLINE_STYLE, ORIGINAL_KLINE_BAR_SHRINK_PERCENT } from "@/constants";
import { applyLayout } from "../positioning/layout";
import { makeMainTooltipFormatter } from "../tooltips/index";

// NEW: Idx-Only 合并K渲染需要从 candles 回溯价格，并动态推导 anchor
import { candleH, candleL, resolveAnchorIdx } from "@/composables/chan/common";

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
    // NEW: 由上层传入（来自 chanSettings.anchorPolicy），用于动态推导合并K落点
    anchorPolicy,
  },
  ui
) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);

  const series = [];

  const ks = klineStyle || DEFAULT_KLINE_STYLE || {};
  const MK = ks.mergedK || DEFAULT_KLINE_STYLE.mergedK || {};

  // ===== NEW: 主图柱宽（单一参数）=====
  const barPercent = Number.isFinite(+ks.barPercent)
    ? Math.max(10, Math.min(100, Math.round(+ks.barPercent)))
    : Math.max(10, Math.min(100, Math.round(+DEFAULT_KLINE_STYLE.barPercent || 88)));

  // ===== NEW: 原始K额外收缩（合并K不受影响）=====
  const shrink = Number.isFinite(+ORIGINAL_KLINE_BAR_SHRINK_PERCENT)
    ? Math.max(0, Math.round(+ORIGINAL_KLINE_BAR_SHRINK_PERCENT))
    : 0;
  const originalBarPercent = barPercent - shrink;

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
        // CHANGED: 原始K柱宽在现有 barPercent 基础上额外减 shrink%
        barWidth: `${originalBarPercent}%`,
        z: originalZ,
      };

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

      // NEW: Idx-Only 方式计算合并K的 hi/lo（通过 g_idx_orig/d_idx_orig 回溯 candles）
      // NEW: 合并K落点 idx 通过 resolveAnchorIdx 动态推导（不再依赖 rb.anchor_idx_orig）
      const ap =
        anchorPolicy === "left" || anchorPolicy === "right" || anchorPolicy === "extreme"
          ? anchorPolicy
          : "right";

      for (const rb of reducedBars) {
        const idx = resolveAnchorIdx(rb, ap);
        if (!Number.isInteger(idx) || idx < 0 || idx >= n) continue;

        const hi = candleH(list, rb?.g_idx_orig);
        const lo = candleL(list, rb?.d_idx_orig);
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
        // 保持不变：合并K仍使用原 barPercent（现有机制）
        barWidth: `${barPercent}%`,
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
                  borderColor: upIndexSet.has(i) ? upC : dnC,
                },
              }
        ),
        // 保持不变：合并K仍使用原 barPercent（现有机制）
        barWidth: `${barPercent}%`,
        barGap: "-100%",
        itemStyle: {
          color: (p) => (upIndexSet.has(p.dataIndex) ? upFill : dnFill),
          borderColor: (p) => (upIndexSet.has(p.dataIndex) ? upC : dnC),
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

  option = applyLayout(
    option,
    { ...ui, isMain: true, leftPx: 72 },
    { candles: list, freq }
  );

  return option;
}
