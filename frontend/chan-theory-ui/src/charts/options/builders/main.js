// src/charts/options/builders/main.js
// ==============================
// V10.1 - Tooltip 显式注入 indicators（TR/MATR/ATR_stop 纯展示）
// 本次仅做：makeMainTooltipFormatter 增加 indicators 注入，消除 tooltip 隐式依赖风险。
// 其它逻辑保持不变。
// ==============================

import { getChartTheme } from "@/charts/theme";
import { hexToRgba } from "@/utils/colorUtils";
import { formatNumberScaled } from "@/utils/numberUtils";
import {
  STYLE_PALETTE,
  DEFAULT_KLINE_STYLE,
  ORIGINAL_KLINE_BAR_SHRINK_PERCENT,
  DEFAULT_ATR_STOP_SETTINGS,
  MAIN_YAXIS_PADDING_RATIO,
} from "@/constants";
import { applyLayout } from "../positioning/layout";
import { makeMainTooltipFormatter } from "../tooltips/index";
import { candleH, candleL, resolveAnchorIdx } from "@/composables/chan/common";

function asArray(x) {
  return Array.isArray(x) ? x : [];
}
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

function clamp(n, min, max) {
  const x = Number(n);
  if (!Number.isFinite(x)) return min;
  return Math.max(min, Math.min(max, x));
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
    anchorPolicy,
    mergedGDByOrigIdx,
    atrStopSettings,
    atrBasePrice,
  },
  ui
) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);

  const series = [];

  const ks = klineStyle || DEFAULT_KLINE_STYLE || {};
  const MK = ks.mergedK || DEFAULT_KLINE_STYLE.mergedK || {};

  const barPercent = Number.isFinite(+ks.barPercent)
    ? Math.max(10, Math.min(100, Math.round(+ks.barPercent)))
    : Math.max(10, Math.min(100, Math.round(+DEFAULT_KLINE_STYLE.barPercent || 88)));

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
      series.push({
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
        barWidth: `${originalBarPercent}%`,
        z: originalZ,
      });
    }

    if (showMerged && Array.isArray(reducedBars) && reducedBars.length) {
      const outlineW = Math.max(0.1, Number(MK.outlineWidth));
      const upC = MK.upColor || DEFAULT_KLINE_STYLE.mergedK.upColor;
      const dnC = MK.downColor || DEFAULT_KLINE_STYLE.mergedK.downColor;

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

    // ===== ATR_stop 最终止损线（仅绘制最终线；TR/MATR 不出图）=====
    {
      const s =
        atrStopSettings && typeof atrStopSettings === "object"
          ? atrStopSettings
          : DEFAULT_ATR_STOP_SETTINGS;

      // 删除总开关字段：以各条线 enabled 为准（用户设置页勾选）
      // fixed 多
      if (s.fixed?.long?.enabled === true && Array.isArray(inds.ATR_FIXED_LONG)) {
        series.push({
          id: "ATR_FIXED_LONG",
          type: "line",
          name: "倍数止损-多",
          data: inds.ATR_FIXED_LONG,
          showSymbol: false,
          smooth: false,
          lineStyle: {
            width: Number(s.fixed.long.lineWidth ?? DEFAULT_ATR_STOP_SETTINGS.fixed.long.lineWidth),
            type: String(s.fixed.long.lineStyle ?? DEFAULT_ATR_STOP_SETTINGS.fixed.long.lineStyle),
            color: String(s.fixed.long.color ?? DEFAULT_ATR_STOP_SETTINGS.fixed.long.color),
          },
          itemStyle: { color: String(s.fixed.long.color ?? DEFAULT_ATR_STOP_SETTINGS.fixed.long.color) },
          color: String(s.fixed.long.color ?? DEFAULT_ATR_STOP_SETTINGS.fixed.long.color),
          emphasis: { disabled: true },
          z: 3,
        });
      }

      // fixed 空
      if (s.fixed?.short?.enabled === true && Array.isArray(inds.ATR_FIXED_SHORT)) {
        series.push({
          id: "ATR_FIXED_SHORT",
          type: "line",
          name: "倍数止损-空",
          data: inds.ATR_FIXED_SHORT,
          showSymbol: false,
          smooth: false,
          lineStyle: {
            width: Number(s.fixed.short.lineWidth ?? DEFAULT_ATR_STOP_SETTINGS.fixed.short.lineWidth),
            type: String(s.fixed.short.lineStyle ?? DEFAULT_ATR_STOP_SETTINGS.fixed.short.lineStyle),
            color: String(s.fixed.short.color ?? DEFAULT_ATR_STOP_SETTINGS.fixed.short.color),
          },
          itemStyle: { color: String(s.fixed.short.color ?? DEFAULT_ATR_STOP_SETTINGS.fixed.short.color) },
          color: String(s.fixed.short.color ?? DEFAULT_ATR_STOP_SETTINGS.fixed.short.color),
          emphasis: { disabled: true },
          z: 3,
        });
      }

      // chandelier 多
      if (s.chandelier?.long?.enabled === true && Array.isArray(inds.ATR_CHAN_LONG)) {
        series.push({
          id: "ATR_CHAN_LONG",
          type: "line",
          name: "波动止损-多",
          data: inds.ATR_CHAN_LONG,
          showSymbol: false,
          smooth: false,
          lineStyle: {
            width: Number(s.chandelier.long.lineWidth ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.long.lineWidth),
            type: String(s.chandelier.long.lineStyle ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.long.lineStyle),
            color: String(s.chandelier.long.color ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.long.color),
          },
          itemStyle: { color: String(s.chandelier.long.color ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.long.color) },
          color: String(s.chandelier.long.color ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.long.color),
          emphasis: { disabled: true },
          z: 3,
        });
      }

      // chandelier 空
      if (s.chandelier?.short?.enabled === true && Array.isArray(inds.ATR_CHAN_SHORT)) {
        series.push({
          id: "ATR_CHAN_SHORT",
          type: "line",
          name: "波动止损-空",
          data: inds.ATR_CHAN_SHORT,
          showSymbol: false,
          smooth: false,
          lineStyle: {
            width: Number(s.chandelier.short.lineWidth ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.short.lineWidth),
            type: String(s.chandelier.short.lineStyle ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.short.lineStyle),
            color: String(s.chandelier.short.color ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.short.color),
          },
          itemStyle: { color: String(s.chandelier.short.color ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.short.color) },
          color: String(s.chandelier.short.color ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.short.color),
          emphasis: { disabled: true },
          z: 3,
        });
      }
    }
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

  const padRatio = clamp(MAIN_YAXIS_PADDING_RATIO, 0, 0.3);

  const mainYAxis = {
    scale: true,
    min: (val) => {
      try {
        const mn = Number(val?.min);
        const mx = Number(val?.max);
        if (!Number.isFinite(mn) || !Number.isFinite(mx)) return mn;
        const span = mx - mn;
        const pad = span > 0 ? span * padRatio : Math.max(Math.abs(mx) || 1, 1) * padRatio;
        return mn - pad;
      } catch {
        return val?.min;
      }
    },
    max: (val) => {
      try {
        const mn = Number(val?.min);
        const mx = Number(val?.max);
        if (!Number.isFinite(mn) || !Number.isFinite(mx)) return mx;
        const span = mx - mn;
        const pad = span > 0 ? span * padRatio : Math.max(Math.abs(mx) || 1, 1) * padRatio;
        return mx + pad;
      } catch {
        return val?.max;
      }
    },

    // ===== NEW: 限制主图Y轴标签有效小数位（示范修复）=====
    axisLabel: {
      formatter: (v) =>
        formatNumberScaled(v, {
          digits: 2,              // 你后续想改 3 位，就改这里
          allowEmpty: true,
          minIntDigitsToScale: 9, // 避免价格被缩放成“万/亿”
        }),
    },

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
        indicators: inds, // NEW: 显式注入（唯一来源）
        maConfigs,
        adjust,
        klineStyle: ks,
        reducedBars,
        mapOrigToReduced,
        mergedGDByOrigIdx,
        atrStopSettings,
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
