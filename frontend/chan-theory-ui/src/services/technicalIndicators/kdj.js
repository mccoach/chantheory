// src/services/technicalIndicators/kdj.js
// ==============================
// 说明：KDJ 指标
// 职责：计算 K / D / J 三条序列
//
// 定义：
//   - RSV = (C - Ln) / (Hn - Ln) * 100
//   - K = EMA(RSV, k)
//   - D = EMA(K, d)
//   - J = 3K - 2D
// ==============================

import { calculateEMA } from "./ema";

/**
 * 计算KDJ指标
 * @param {Array<number>} highs - 最高价序列
 * @param {Array<number>} lows - 最低价序列
 * @param {Array<number>} closes - 收盘价序列
 * @param {number} n - RSV周期（默认9）
 * @param {number} k - K值平滑（默认3）
 * @param {number} d - D值平滑（默认3）
 * @returns {Object} {KDJ_K, KDJ_D, KDJ_J}
 */
export function calculateKDJ(highs, lows, closes, n = 9, k = 3, d = 3) {
  // RSV（未成熟随机值）
  const rsv = closes.map((c, i) => {
    if (i < n - 1) return 50;

    const windowHigh = Math.max(...highs.slice(i - n + 1, i + 1));
    const windowLow = Math.min(...lows.slice(i - n + 1, i + 1));

    return ((c - windowLow) / (windowHigh - windowLow + 1e-12)) * 100;
  });

  const kLine = calculateEMA(rsv, k);
  const dLine = calculateEMA(kLine, d);
  const jLine = kLine.map((kv, i) => 3 * kv - 2 * dLine[i]);

  return {
    KDJ_K: kLine,
    KDJ_D: dLine,
    KDJ_J: jLine,
  };
}