// src/charts/chan/layers.js
// 最小改动：支持从 chanSettings 中读取 upShape/upColor/downShape/downColor 覆盖预设
import { CHAN_MARKER_PRESETS, CHAN_DEFAULTS } from "@/constants";

export function buildUpDownMarkers(reducedBars, env = {}) {
  const theme = env.theme || {};
  const chan = Object.assign({}, CHAN_DEFAULTS, env.chanSettings || {});
  const hostWidth = Math.max(1, Number(env.hostWidth || 0));
  const visCount = Math.max(1, Number(env.visCount || 1));
  const preset =
    CHAN_MARKER_PRESETS[chan.visualPreset] ||
    CHAN_MARKER_PRESETS["tri-default"];

  const approxBarWidthPx =
    hostWidth > 1 ? Math.max(1, Math.floor((hostWidth * 0.88) / visCount)) : 8;
  const markerW = Math.max(
    chan.markerMinPx,
    Math.min(chan.markerMaxPx, approxBarWidthPx)
  );
  const markerH = 10;
  const offsetDownPx = Math.round(markerH * 1.2);

  const upPoints = [];
  const downPoints = [];
  for (let i = 0; i < reducedBars.length; i++) {
    const rb = reducedBars[i];
    const d = Number(rb.dir || 0);
    if (!Number.isFinite(d) || d === 0) continue;
    const x = Number(rb.anchor_idx ?? rb.idx_end);
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
  const upArr = downSample(upPoints, chan.maxVisibleMarkers);
  const dnArr = downSample(downPoints, chan.maxVisibleMarkers);

  // 预设颜色
  const presetUpFill = preset.up.fill;
  const presetDnFill = preset.down.fill;

  // 覆盖优先：若 chanSettings 中设置了 shape/color，则按设置覆盖；否则用预设
  const upShape = chan.upShape || preset.up.shape;
  const upFill = chan.upColor || presetUpFill;
  const downShape = chan.downShape || preset.down.shape;
  const downFill = chan.downColor || presetDnFill;

  const commonScatter = {
    type: "scatter",
    yAxisIndex: 1,
    symbolSize: () => [markerW, markerH],
    symbolOffset: [0, offsetDownPx],
    clip: false,
    tooltip: { show: false },
    z: 2,
  };

  const upSeries = {
    ...commonScatter,
    id: "CHAN_UP",
    name: "CHAN_UP",
    data: upArr,
    symbol: upShape,
    symbolRotate: preset.up.rotate || 0,
    itemStyle: { color: upFill, opacity: chan.opacity },
  };

  const downSeries = {
    ...commonScatter,
    id: "CHAN_DOWN",
    name: "CHAN_DOWN",
    data: dnArr,
    symbol: downShape,
    symbolRotate: preset.down.rotate || 180,
    itemStyle: { color: downFill, opacity: chan.opacity },
  };

  const extra = { xAxisLabelMargin: Math.max(14, markerH + 12) };
  return { series: [upSeries, downSeries], extra };
}
