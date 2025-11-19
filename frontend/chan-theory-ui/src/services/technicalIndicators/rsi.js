// src/services/technicalIndicators/rsi.js
// ==============================
// 说明：RSI 指标
// 职责：计算单条 RSI 序列
//
// 定义：
//   - ΔC = C_t - C_{t-1}
//   - G = max(ΔC, 0), L = max(-ΔC, 0)
//   - AvgGain = EMA(G, period)
//   - AvgLoss = EMA(L, period)
//   - RSI = 100 - 100 / (1 + AvgGain / AvgLoss)
// ==============================

import { calculateEMA } from "./ema";

/**
 * 计算RSI指标
 * @param {Array<number>} closes - 收盘价序列
 * @param {number} period - 周期（默认14）
 * @returns {Object} {RSI}
 */
export function calculateRSI(closes, period = 14) {
  const changes = [];
  for (let i = 1; i < closes.length; i++) {
    changes.push(closes[i] - closes[i - 1]);
  }

  const gains = changes.map((c) => (c > 0 ? c : 0));
  const losses = changes.map((c) => (c < 0 ? -c : 0));

  const avgGain = calculateEMA(gains, period);
  const avgLoss = calculateEMA(losses, period);

  const rsi = avgGain.map((g, i) => {
    const rs = g / (avgLoss[i] + 1e-12);
    return 100 - 100 / (1 + rs);
  });

  // 前面补一个 null，对齐原始收盘长度
  return { RSI: [null, ...rsi] };
}