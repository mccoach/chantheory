// src/services/technicalIndicators/boll.js
// ==============================
// 说明：BOLL 指标（布林带）
// 职责：计算 MID / UPPER / LOWER 三条序列
//
// 定义：
//   - MID = MA(C, period)
//   - STD = 收盘在窗口内的标准差
//   - UPPER = MID + k * STD
//   - LOWER = MID - k * STD
// ==============================

import { calculateMA } from "./ma";

/**
 * 计算布林带
 * @param {Array<number>} closes - 收盘价序列
 * @param {number} period - 周期（默认20）
 * @param {number} k - 标准差倍数（默认2）
 * @returns {Object} {BOLL_MID, BOLL_UPPER, BOLL_LOWER}
 */
export function calculateBOLL(closes, period = 20, k = 2) {
  const mid = calculateMA(closes, { BOLL_MID: period }).BOLL_MID;

  const std = closes.map((_, i) => {
    if (i < period - 1) return 0;

    const window = closes.slice(i - period + 1, i + 1);
    const mean = mid[i];
    const variance =
      window
        .map((v) => Math.pow(v - mean, 2))
        .reduce((a, b) => a + b, 0) / period;

    return Math.sqrt(variance);
  });

  const upper = mid.map((v, i) => v + k * std[i]);
  const lower = mid.map((v, i) => v - k * std[i]);

  return {
    BOLL_MID: mid,
    BOLL_UPPER: upper,
    BOLL_LOWER: lower,
  };
}