// src/services/technicalIndicators/ma.js
// ==============================
// 说明：MA（简单移动平均）
// 职责：计算多条 MA，用于主图均线等
// 设计：纯函数，零副作用
// ==============================

/**
 * 计算多条移动平均线
 * @param {Array<number>} closes - 收盘价序列
 * @param {Object} periodsMap - MA配置 {MA5: 5, MA10: 10, ...}
 * @returns {Object} {MA5: [...], MA10: [...]}（前 period-1 个为 null）
 */
export function calculateMA(closes, periodsMap) {
  const result = {};

  Object.entries(periodsMap || {}).forEach(([key, period]) => {
    const n = parseInt(period);
    if (!Number.isFinite(n) || n <= 0) return;

    result[key] = closes.map((_, i) => {
      if (i < n - 1) return null;

      let sum = 0;
      for (let j = i - n + 1; j <= i; j++) {
        sum += closes[j];
      }
      return sum / n;
    });
  });

  return result;
}