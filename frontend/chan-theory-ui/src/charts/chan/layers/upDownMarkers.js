// src/charts/chan/layers/upDownMarkers.js
// ==============================
// 缠论图层：涨跌标记 (Up/Down Markers)
//
// 本轮改动：
//   - 涨跌标记宽度迁移到通用 WidthController + widthState：
//       * 两个 scatter series（CHAN_UP / CHAN_DOWN）共用 widthState key: "main:updown"
//       * symbolSize 读取 widthState，避免 notMerge 覆盖造成的竞态
//   - 不再消费 env.symbolWidthPx（不再依赖 renderHub stepPx 推导）
// ==============================

import { CHAN_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { deriveSymbolSize } from "./geometry";
import { resolveAnchorIdx } from "@/composables/chan/common";
import { getWidthPx } from "@/charts/width/widthState";

const WIDTH_KEY = "main:updown";

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

  const upPoints = [];
  const downPoints = [];

  const policy = CHAN_DEFAULTS.anchorPolicy;

  for (let i = 0; i < (reducedBars || []).length; i++) {
    const rb = reducedBars[i];
    const d = Number(rb?.dir_int || 0);
    if (!Number.isFinite(d) || d === 0) continue;

    const x = resolveAnchorIdx(rb, policy);
    if (!Number.isInteger(x) || x < 0) continue;

    const point = [x, 0];

    if (d > 0) upPoints.push(point);
    else downPoints.push(point);
  }

  function downSample(arr, maxN) {
    const n = arr.length;
    if (n <= maxN) return arr;
    const step = Math.ceil(n / maxN);
    const out = [];
    for (let i = 0; i < n; i += step) out.push(arr[i]);
    return out;
  }

  const maxMarkers = CHAN_DEFAULTS.maxVisibleMarkers;
  const upArr = downSample(upPoints, maxMarkers);
  const dnArr = downSample(downPoints, maxMarkers);

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
