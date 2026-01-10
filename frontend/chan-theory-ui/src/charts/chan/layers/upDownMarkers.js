// src/charts/chan/layers/upDownMarkers.js
// ==============================
// 缠论图层：涨跌标记 (Up/Down Markers)
// - 点集上限归入 CHAN_DEFAULTS.pointLimit.maxPoints（按业务归置）
// - 超限策略：保右端（最新）完整，截断左侧（更早期）
// ==============================

import { CHAN_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { deriveSymbolSize } from "./geometry";
import { resolveAnchorIdx } from "@/composables/chan/common";
import { getWidthPx } from "@/charts/width/widthState";

const WIDTH_KEY = "main:updown";

function capPointsKeepRight(arr, maxN) {
  const a = Array.isArray(arr) ? arr : [];
  const cap = Math.max(1, Math.floor(Number(maxN || 1)));
  if (a.length <= cap) return a;
  return a.slice(a.length - cap);
}

export function buildUpDownMarkers(reducedBars, env = {}) {
  const settings = useUserSettings();

  const chan = Object.assign(
    {},
    CHAN_DEFAULTS,
    (settings.chanTheory && settings.chanTheory.chanSettings) || {}
  );

  // 高度与偏移仍按原常量；宽度由 widthState 提供（fallback 使用 deriveSymbolSize）
  const { widthPx: fallbackW, heightPx: markerH, offsetBottomPx } = deriveSymbolSize({
    hostWidth: env.hostWidth,
    visCount: env.visCount,
    minPx: CHAN_DEFAULTS.markerMinPx,
    maxPx: CHAN_DEFAULTS.markerMaxPx,
    overrideWidth: null,
    heightPx: CHAN_DEFAULTS.markerHeightPx,
    yOffsetPx: CHAN_DEFAULTS.markerYOffsetPx,
  });

  const markerW = () => getWidthPx(WIDTH_KEY, fallbackW);

  const upPointsRaw = [];
  const downPointsRaw = [];

  const policy = CHAN_DEFAULTS.anchorPolicy;

  for (let i = 0; i < (reducedBars || []).length; i++) {
    const rb = reducedBars[i];
    const d = Number(rb?.dir_int || 0);
    if (!Number.isFinite(d) || d === 0) continue;

    const x = resolveAnchorIdx(rb, policy);
    if (!Number.isInteger(x) || x < 0) continue;

    const point = [x, 0];

    if (d > 0) upPointsRaw.push(point);
    else downPointsRaw.push(point);
  }

  const maxPts = Number(CHAN_DEFAULTS?.pointLimit?.maxPoints ?? 20000);

  const upArr = capPointsKeepRight(upPointsRaw, maxPts);
  const dnArr = capPointsKeepRight(downPointsRaw, maxPts);

  const upShape = chan.upShape;
  const downShape = chan.downShape;
  const upFill = chan.upColor;
  const downFill = chan.downColor;
  const opacity = CHAN_DEFAULTS.opacity;

  const commonScatter = {
    type: "scatter",
    yAxisIndex: 1,
    symbolSize: () => [markerW(), markerH],
    symbolOffset: [0, offsetBottomPx],
    clip: false,
    tooltip: { show: false },
    z: 2,
    emphasis: { scale: false },
  };

  const upSeries = {
    ...commonScatter,
    id: "CHAN_UP",
    name: "CHAN_UP",
    data: upArr,
    symbol: upShape,
    symbolRotate: 0,
    itemStyle: { color: upFill, opacity },
  };

  const downSeries = {
    ...commonScatter,
    id: "CHAN_DOWN",
    name: "CHAN_DOWN",
    data: dnArr,
    symbol: downShape,
    symbolRotate: 180,
    itemStyle: { color: downFill, opacity },
  };

  return {
    series: [upSeries, downSeries],
  };
}
