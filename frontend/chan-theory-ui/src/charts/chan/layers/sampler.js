// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\sampler.js
// ==============================
// 说明：图层数据采样器
// - 核心职责：提供一个统一的函数 sampleSeriesByBarriers，用于将连续的数据点序列按屏障（discontinuity barriers）切分成多段。
// - 目的：消除在 pens.js, segments.js, pivots.js 中重复的切分逻辑。
// ==============================

/**
 * 根据屏障索引将一个线段数据切分为多个块（chunks）
 * @param {object} options
 * @param {number} options.xStart - 起点的x轴索引
 * @param {number} options.xEnd - 终点的x轴索引
 * @param {Function} options.yResolver - 一个函数 (x) => y，用于计算任意x索引处的y值
 * @param {Set<number>} options.barriersSet - 包含所有屏障x索引的Set集合
 * @returns {Array<Array<[number, number]>>} - 返回一个二维数组，每个子数组是一个连续的线段块
 */
export function sampleSeriesByBarriers({
  xStart,
  xEnd,
  yResolver,
  barriersSet,
}) {
  const chunks = [];
  if (
    !Number.isFinite(xStart) ||
    !Number.isFinite(xEnd) ||
    typeof yResolver !== "function" ||
    !barriersSet
  ) {
    return chunks;
  }

  const xa = Math.min(xStart, xEnd);
  const xb = Math.max(xStart, xEnd);

  let currentChunk = [];

  for (let xi = xa; xi <= xb; xi++) {
    if (barriersSet.has(xi)) {
      // 遇到屏障，如果当前块有两个或更多点，则存入结果
      if (currentChunk.length >= 2) {
        chunks.push(currentChunk);
      }
      // 重置当前块
      currentChunk = [];
      continue;
    }

    // 计算y值并加入当前块
    const yi = yResolver(xi);
    if (Number.isFinite(yi)) {
      currentChunk.push([xi, yi]);
    }
  }

  // 循环结束后，保存最后一段
  if (currentChunk.length >= 2) {
    chunks.push(currentChunk);
  }

  return chunks;
}
