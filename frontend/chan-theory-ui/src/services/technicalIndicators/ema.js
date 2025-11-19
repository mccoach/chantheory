// src/services/technicalIndicators/ema.js
// ==============================
// 说明：EMA（指数移动平均）计算核心
// 职责：提供通用的 calculateEMA 供其它指标复用（MACD/KDJ/RSI等）
// 设计：纯函数，零副作用
//
// 重要说明：
// - 旧实现只初始化 ema[period-1]，前面的元素为 undefined，
//   在 MACD 中对 DIF 再做 EMA 时会引入 NaN，导致 DEA / HIST 变成 NaN。
// - 本实现：
//   * 从第一个有效数据点开始递推 EMA；
//   * 对非法数值（NaN/undefined）沿用上一条 EMA，避免 NaN 传播。
// ==============================

/**
 * 计算 EMA（指数移动平均）
 * @param {Array<number>} data - 数据序列
 * @param {number} period - 周期
 * @returns {Array<number>} EMA 序列（前面的无效段为 null）
 */
export function calculateEMA(data, period) {
  const n = Number(period);
  if (!Array.isArray(data) || data.length === 0 || !Number.isFinite(n) || n <= 0) {
    return [];
  }

  const k = 2 / (n + 1);
  const ema = new Array(data.length);

  // 找到第一个有效数据点
  let firstIdx = 0;
  while (firstIdx < data.length && !Number.isFinite(Number(data[firstIdx]))) {
    firstIdx++;
  }
  if (firstIdx >= data.length) {
    // 全部无效 → 返回全 null
    return new Array(data.length).fill(null);
  }

  // 前面部分填 null，避免 undefined
  for (let i = 0; i < firstIdx; i++) {
    ema[i] = null;
  }

  let prev = Number(data[firstIdx]);
  ema[firstIdx] = prev;

  for (let i = firstIdx + 1; i < data.length; i++) {
    const v = Number(data[i]);
    if (!Number.isFinite(v)) {
      // 非法数值：沿用上一条 EMA
      ema[i] = ema[i - 1];
    } else {
      ema[i] = v * k + ema[i - 1] * (1 - k);
    }
  }

  return ema;
}