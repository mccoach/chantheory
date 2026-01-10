// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\viewRenderHub\mainOverlay\atrBreachOverlay.js
// ==============================
// ATR_stop 刺穿标记 overlay（单一路径）
// - 改造：从 markPoint 改为 scatter（与分型/涨跌/量窗 marker 保持同类实现）
// - 宽度：从 widthState(key=main:atrBreach) 动态读取，随缩放实时变化（WidthController 写入）
// - 高度：固定为 10px（与现有 marker 体系一致），由 ATR_BREACH_DEFAULTS.markerHeightPx 提供
// - 颜色：不单独设置，严格跟随对应 ATR_stop 线颜色（atrStopSettings.*.color）
// - 点集上限归入 ATR_BREACH_DEFAULTS.pointLimit.maxPoints（超限保右端完整）
// ==============================

import { ATR_BREACH_DEFAULTS } from "@/constants";
import { getWidthPx } from "@/charts/width/widthState";

const WIDTH_KEY = "main:atrBreach";

function capPointsKeepRight(arr, maxN) {
  const a = Array.isArray(arr) ? arr : [];
  const cap = Math.max(1, Math.floor(Number(maxN || 1)));
  if (a.length <= cap) return a;
  return a.slice(a.length - cap);
}

function asArr(x) {
  return Array.isArray(x) ? x : null;
}

function num(x) {
  const v = Number(x);
  return Number.isFinite(v) ? v : null;
}

function asEnabled(settings) {
  const s = settings && typeof settings === "object" ? settings : {};
  return (s.enabled ?? ATR_BREACH_DEFAULTS.enabled) === true;
}

function resolveStyle(atrBreachSettings) {
  const s = atrBreachSettings && typeof atrBreachSettings === "object" ? atrBreachSettings : {};

  const shape = String(s.shape ?? ATR_BREACH_DEFAULTS.shape);
  const fill = String(s.fill ?? ATR_BREACH_DEFAULTS.fill);
  const isHollow = fill === "hollow";

  const markerH = Number(ATR_BREACH_DEFAULTS.markerHeightPx);
  const fallbackW = 8; // widthState 尚未落地时的兜底
  const markerW = () => getWidthPx(WIDTH_KEY, fallbackW);

  const hollowBorderWidth = Number(ATR_BREACH_DEFAULTS.hollowBorderWidth);

  return {
    shape,
    isHollow,
    markerH,
    markerW,
    hollowBorderWidth,
  };
}

function buildScatterSeries({ id, name, shape, isHollow, markerW, markerH, hollowBorderWidth, color, points }) {
  const c = String(color || "").trim() || "#ffffff";

  return {
    id,
    name,
    type: "scatter",
    yAxisIndex: 0,
    data: points,
    symbol: shape,
    symbolSize: () => [markerW(), markerH],
    itemStyle: isHollow
      ? {
        color: "transparent",
        borderColor: c,
        borderWidth: hollowBorderWidth,
        opacity: 0.95,
      }
      : {
        color: c,
        opacity: 0.95,
      },
    silent: true,
    z: 10,
    tooltip: { show: false },
    emphasis: { disabled: true },
  };
}

export function buildAtrStopBreachSeries({ candles, indicators, atrStopSettings, atrBreachSettings }) {
  const list = Array.isArray(candles) ? candles : [];
  const inds = indicators && typeof indicators === "object" ? indicators : {};
  const stops = atrStopSettings && typeof atrStopSettings === "object" ? atrStopSettings : null;

  const n = list.length;
  if (!n || !stops) return [];

  if (!asEnabled(atrBreachSettings)) return [];

  const maxPts = Number(ATR_BREACH_DEFAULTS?.pointLimit?.maxPoints ?? 20000);

  const { shape, isHollow, markerH, markerW, hollowBorderWidth } = resolveStyle(atrBreachSettings);

  function pointsLongBreach(stopArr) {
    const pts = [];
    for (let i = 0; i < n; i++) {
      const stop = num(stopArr[i]);
      if (stop == null) continue;
      const low = num(list[i]?.l);
      if (low == null) continue;
      if (low <= stop) pts.push([i, stop]);
    }
    return capPointsKeepRight(pts, maxPts);
  }

  function pointsShortBreach(stopArr) {
    const pts = [];
    for (let i = 0; i < n; i++) {
      const stop = num(stopArr[i]);
      if (stop == null) continue;
      const high = num(list[i]?.h);
      if (high == null) continue;
      if (high >= stop) pts.push([i, stop]);
    }
    return capPointsKeepRight(pts, maxPts);
  }

  const out = [];

  // 固定倍数止损：多（low <= stop）
  if (stops.fixed?.long?.enabled === true) {
    const stopArr = asArr(inds.ATR_FIXED_LONG);
    if (stopArr && stopArr.length === n) {
      const pts = pointsLongBreach(stopArr);
      if (pts.length) {
        out.push(
          {
            ...buildScatterSeries({
              id: "ATR_BREACH_FIXED_LONG",
              name: "ATR_BREACH_FIXED_LONG",
              shape,
              isHollow,
              markerW,
              markerH,
              hollowBorderWidth,
              color: stops.fixed?.long?.color,
              points: pts,
            }),
            symbolRotate: 180, // 多头止损标记符号翻转 180 度
          }
        );
      }
    }
  }

  // 固定倍数止损：空（high >= stop）
  if (stops.fixed?.short?.enabled === true) {
    const stopArr = asArr(inds.ATR_FIXED_SHORT);
    if (stopArr && stopArr.length === n) {
      const pts = pointsShortBreach(stopArr);
      if (pts.length) {
        out.push(
          buildScatterSeries({
            id: "ATR_BREACH_FIXED_SHORT",
            name: "ATR_BREACH_FIXED_SHORT",
            shape,
            isHollow,
            markerW,
            markerH,
            hollowBorderWidth,
            color: stops.fixed?.short?.color,
            points: pts,
          }),
        );
      }
    }
  }

  // 波动通道止损：多（low <= stop）
  if (stops.chandelier?.long?.enabled === true) {
    const stopArr = asArr(inds.ATR_CHAN_LONG);
    if (stopArr && stopArr.length === n) {
      const pts = pointsLongBreach(stopArr);
      if (pts.length) {
        out.push(
          {
            ...buildScatterSeries({
              id: "ATR_BREACH_CHAN_LONG",
              name: "ATR_BREACH_CHAN_LONG",
              shape,
              isHollow,
              markerW,
              markerH,
              hollowBorderWidth,
              color: stops.chandelier?.long?.color,
              points: pts,
            }),
            symbolRotate: 180, // 多头止损标记符号翻转 180 度
          }
        );
      }
    }
  }

  // 波动通道止损：空（high >= stop）
  if (stops.chandelier?.short?.enabled === true) {
    const stopArr = asArr(inds.ATR_CHAN_SHORT);
    if (stopArr && stopArr.length === n) {
      const pts = pointsShortBreach(stopArr);
      if (pts.length) {
        out.push(
          buildScatterSeries({
            id: "ATR_BREACH_CHAN_SHORT",
            name: "ATR_BREACH_CHAN_SHORT",
            shape,
            isHollow,
            markerW,
            markerH,
            hollowBorderWidth,
            color: stops.chandelier?.short?.color,
            points: pts,
          }),
        );
      }
    }
  }

  return out;
}
