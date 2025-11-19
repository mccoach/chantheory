// src/services/technicalIndicators/macd.js
// ==============================
// 说明：MACD 指标
// 职责：计算 DIF / DEA / HIST 三条序列
//
// 定义（当前实现与你现有逻辑保持一致）：
//   - EMA_fast = EMA(closes, fast)
//   - EMA_slow = EMA(closes, slow)
//   - DIF = EMA_fast - EMA_slow
//   - DEA = EMA(DIF, signal)
//   - HIST = 2 * (DIF - DEA)
// ==============================

import { calculateEMA } from "./ema";

/**
 * 计算MACD指标
 * @param {Array<number>} closes - 收盘价序列
 * @param {number} fast - 快线周期（默认12）
 * @param {number} slow - 慢线周期（默认26）
 * @param {number} signal - 信号线周期（默认9）
 * @returns {Object} {MACD_DIF, MACD_DEA, MACD_HIST}
 */
export function calculateMACD(closes, fast = 12, slow = 26, signal = 9) {
  const emaFast = calculateEMA(closes, fast);
  const emaSlow = calculateEMA(closes, slow);

  const dif = emaFast.map((v, i) => v - emaSlow[i]);
  const dea = calculateEMA(dif, signal);
  const hist = dif.map((v, i) => (v - dea[i]) * 2);

  return {
    MACD_DIF: dif,
    MACD_DEA: dea,
    MACD_HIST: hist,
  };
}