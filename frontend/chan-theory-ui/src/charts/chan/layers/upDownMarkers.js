// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\upDownMarkers.js
// ==============================
// 缠论图层：涨跌标记 (Up/Down Markers)
// - 从 layers.js 拆分而来。
// - 核心职责：将合并K线中的方向信息（dir_int）转换为ECharts的散点图系列（scatter series）。
// ==============================
import { CHAN_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";

// 涨跌标记：横坐标 = anchor_idx_orig（承载点的原始索引），绑定隐藏 yAxis=1
export function buildUpDownMarkers(reducedBars, env = {}) {
  const settings = useUserSettings();
  const chan = Object.assign(
    {},
    CHAN_DEFAULTS,
    (settings.chanTheory && settings.chanTheory.chanSettings) || {}
  );

  const hostWidth = Math.max(1, Number(env.hostWidth || 0)); // 宿主宽度（几何计算）
  const visCount = Math.max(1, Number(env.visCount || 1)); // 可见根数（几何计算）
  // 统一符号宽度来源：优先外部 symbolWidthPx（中枢派生），否则根据 hostWidth+visCount 估算
  const extW = Number(env.symbolWidthPx || NaN);
  const approxW =
    hostWidth > 1 && visCount > 0
      ? Math.floor((hostWidth * 0.88) / visCount)
      : 8; // 估算宽度
  const markerW = Number.isFinite(extW)
    ? Math.max(chan.markerMinPx, Math.min(chan.markerMaxPx, Math.round(extW)))
    : Math.max(chan.markerMinPx, Math.min(chan.markerMaxPx, approxW));

  // 统一高度与偏移来源：仅由 index.js 的 CHAN_DEFAULTS 决定
  const markerH = Math.max(1, Math.round(Number(CHAN_DEFAULTS.markerHeightPx)));
  const offsetDownPx = Math.round(
    markerH + Number(CHAN_DEFAULTS.markerYOffsetPx)
  );

  const upPoints = [];
  const downPoints = []; // 承载点集合
  for (let i = 0; i < (reducedBars || []).length; i++) {
    const rb = reducedBars[i];
    const d = Number(rb?.dir_int || 0);
    if (!Number.isFinite(d) || d === 0) continue;
    const x = Number(rb?.anchor_idx_orig ?? rb?.end_idx_orig ?? i);
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

  // -- 直接从合并后的 chan 设置中获取形状和颜色 --
  const upShape = chan.upShape;
  const downShape = chan.downShape;
  const upFill = chan.upColor;
  const downFill = chan.downColor;

  const commonScatter = {
    type: "scatter",
    yAxisIndex: 1, // 不变量：隐藏 y 轴 index=1
    symbolSize: () => [markerW, markerH], // 宽高统一受中枢派生几何控制
    symbolOffset: [0, offsetDownPx], // 底部偏移
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
    itemStyle: { color: upFill, opacity: chan.opacity },
  };
  const downSeries = {
    ...commonScatter,
    id: "CHAN_DOWN",
    name: "CHAN_DOWN",
    data: dnArr,
    symbol: downShape,
    symbolRotate: 180,
    itemStyle: { color: downFill, opacity: chan.opacity },
  };

  return {
    series: [upSeries, downSeries],
  };
}
