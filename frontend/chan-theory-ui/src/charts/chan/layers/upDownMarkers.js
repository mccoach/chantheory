// src/charts/chan/layers/upDownMarkers.js
// ==============================
// 缠论图层：涨跌标记 (Up/Down Markers)
// 职责：将合并K线的方向信息转换为散点图系列
// 
// 修复要点：
//   - 已暴露参数：从 chan 配置读取（upShape/upColor等）
//   - 未暴露参数：直接用常量（markerHeightPx/markerYOffsetPx等）
// ==============================

import { CHAN_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { deriveSymbolSize } from "./geometry";

export function buildUpDownMarkers(reducedBars, env = {}) {
  const settings = useUserSettings();
  
  // ===== 合并设置：优先用户配置，兜底默认值 =====
  const chan = Object.assign(
    {},
    CHAN_DEFAULTS,
    (settings.chanTheory && settings.chanTheory.chanSettings) || {}
  );

  // ===== 几何计算：未暴露参数直接用常量 =====
  const { widthPx: markerW, heightPx: markerH, offsetBottomPx } = deriveSymbolSize({
    hostWidth: env.hostWidth,
    visCount: env.visCount,
    minPx: CHAN_DEFAULTS.markerMinPx,      // ← 未暴露，直接用常量
    maxPx: CHAN_DEFAULTS.markerMaxPx,      // ← 未暴露，直接用常量
    overrideWidth: env.symbolWidthPx,
    heightPx: CHAN_DEFAULTS.markerHeightPx,  // ← 未暴露，直接用常量
    yOffsetPx: CHAN_DEFAULTS.markerYOffsetPx,  // ← 未暴露，直接用常量
  });

  const upPoints = [];
  const downPoints = [];
  
  for (let i = 0; i < (reducedBars || []).length; i++) {
    const rb = reducedBars[i];
    const d = Number(rb?.dir_int || 0);
    if (!Number.isFinite(d) || d === 0) continue;
    
    const x = Number(rb?.anchor_idx_orig ?? rb?.end_idx_orig ?? i);
    const point = [x, 0];
    
    if (d > 0) upPoints.push(point);
    else downPoints.push(point);
  }

  // 降采样（未暴露参数）
  function downSample(arr, maxN) {
    const n = arr.length;
    if (n <= maxN) return arr;
    const step = Math.ceil(n / maxN);
    const out = [];
    for (let i = 0; i < n; i += step) out.push(arr[i]);
    return out;
  }
  
  const maxMarkers = CHAN_DEFAULTS.maxVisibleMarkers;  // ← 未暴露，直接用常量
  const upArr = downSample(upPoints, maxMarkers);
  const dnArr = downSample(downPoints, maxMarkers);

  // ===== 样式配置：已暴露参数从 chan 读取 =====
  const upShape = chan.upShape;      // ← 已暴露，从设置读取
  const downShape = chan.downShape;  // ← 已暴露，从设置读取
  const upFill = chan.upColor;       // ← 已暴露，从设置读取
  const downFill = chan.downColor;   // ← 已暴露，从设置读取
  const opacity = CHAN_DEFAULTS.opacity;  // ← 未暴露，直接用常量

  const commonScatter = {
    type: "scatter",
    yAxisIndex: 1,  // 隐藏 y 轴
    symbolSize: () => [markerW, markerH],
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