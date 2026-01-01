// src/charts/chan/layers/geometry.js
// ==============================
// 说明：缠论图层几何计算工具
// 职责：提供统一的 deriveSymbolSize 函数计算标记尺寸
// 设计：纯函数，零副作用
//
// V2.0 - 去耦合：不再依赖 DEFAULT_VOL_SETTINGS / BAR_USABLE_RATIO
// 背景：marker 宽度已迁移到 WidthController + widthState，几何工具不应耦合量窗默认配置。
// 改动：
//   - 移除对 DEFAULT_VOL_SETTINGS / BAR_USABLE_RATIO 的引用；
//   - 新增参数 barUsableRatio（可选），默认 0.88，保持行为回归。
// ==============================

/**
 * 派生图层标记的尺寸
 *
 * @param {object} options
 * @param {number} options.hostWidth - 图表宿主容器的宽度 (px)
 * @param {number} options.visCount - 当前可见的K线/Bar数量
 * @param {number} options.minPx - 标记的最小宽度 (px)
 * @param {number} options.maxPx - 标记的最大宽度 (px)
 * @param {number} [options.overrideWidth] - 外部强制指定的宽度 (px)
 * @param {number} [options.heightPx=10] - 标记的固定高度 (px)
 * @param {number} [options.yOffsetPx=2] - 标记距离K线/Bar的Y轴偏移 (px)
 * @param {number} [options.barPercent=100] - 如果基于Bar估算，Bar的宽度百分比
 * @param {number} [options.barUsableRatio=0.88] - 图表宽度可用于柱体的比例（默认0.88，行为回归）
 * @returns {{widthPx: number, heightPx: number, offsetBottomPx: number}}
 *
 * 算法：
 *   1. 优先使用 overrideWidth
 *   2. 否则基于可见根数估算：(宿主宽度 * barUsableRatio) / 可见根数 * 柱宽百分比
 *   3. 应用 [minPx, maxPx] 限制
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
  barUsableRatio = 0.88,
}) {
  const hW = Math.max(1, Number(hostWidth || 0));
  const vC = Math.max(1, Number(visCount || 1));

  let finalWidth;

  if (Number.isFinite(overrideWidth)) {
    finalWidth = Math.round(overrideWidth);
  } else {
    const usable = Number(barUsableRatio);
    const ratio = Number.isFinite(usable) ? Math.max(0.1, Math.min(1, usable)) : 0.88;

    const approxBarWidth = (hW * ratio) / vC;
    const approxSymbolWidth = approxBarWidth * (barPercent / 100);
    finalWidth = Math.round(approxSymbolWidth);
  }

  const widthPx = Math.max(minPx, Math.min(maxPx, finalWidth));
  const height = Math.max(1, Math.round(heightPx));
  const offset = Math.round(height + yOffsetPx);

  return {
    widthPx: widthPx,
    heightPx: height,
    offsetBottomPx: offset,
  };
}
