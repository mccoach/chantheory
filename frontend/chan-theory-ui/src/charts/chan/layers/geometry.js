// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\geometry.js
// ==============================
// 说明：缠论图层几何计算工具
// - 核心职责：提供一个统一的函数 deriveSymbolSize 来计算图层标记（如分型、涨跌标记）的动态尺寸和偏移。
// - 目的：消除在 upDownMarkers.js, fractals.js, volume.js 等模块中重复的尺寸计算逻辑。
// ==============================

/**
 * 派生图层标记的尺寸
 * @param {object} options
 * @param {number} options.hostWidth - 图表宿主容器的宽度 (px)
 * @param {number} options.visCount - 当前可见的K线/Bar数量
 * @param {number} options.minPx - 标记的最小宽度 (px)
 * @param {number} options.maxPx - 标记的最大宽度 (px)
 * @param {number} [options.overrideWidth] - 外部强制指定的宽度 (px)，例如来自 useViewRenderHub 的 markerWidthPx
 * @param {number} [options.heightPx] - 标记的固定高度 (px)
 * @param {number} [options.yOffsetPx] - 标记距离K线/Bar的Y轴偏移 (px)
 * @param {number} [options.barPercent=100] - 如果基于Bar估算，Bar的宽度百分比
 * @returns {{widthPx: number, heightPx: number, offsetBottomPx: number}}
 */
export function deriveSymbolSize({
  hostWidth,
  visCount,
  minPx,
  maxPx,
  overrideWidth,
  heightPx = 10,
  yOffsetPx = 2,
  barPercent = 100,
}) {
  const hW = Math.max(1, Number(hostWidth || 0));
  const vC = Math.max(1, Number(visCount || 1));

  let finalWidth;

  if (Number.isFinite(overrideWidth)) {
    // 优先使用外部覆盖宽度
    finalWidth = Math.round(overrideWidth);
  } else {
    // 否则根据可见根数估算
    const approxBarWidth = (hW * 0.88) / vC;
    const approxSymbolWidth = approxBarWidth * (barPercent / 100);
    finalWidth = Math.round(approxSymbolWidth);
  }

  // 应用最小/最大宽度限制
  const widthPx = Math.max(minPx, Math.min(maxPx, finalWidth));
  const height = Math.max(1, Math.round(heightPx));
  const offset = Math.round(height + yOffsetPx);

  return {
    widthPx: widthPx,
    heightPx: height,
    offsetBottomPx: offset,
  };
}
