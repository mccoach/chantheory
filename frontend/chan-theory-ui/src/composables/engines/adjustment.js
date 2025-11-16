// src/composables/engines/adjustment.js
// ==============================
// 说明：复权计算引擎（纯函数，零副作用）
// 职责：根据复权因子计算调整后的价格
// 设计：完全独立，不依赖任何Vue响应式
// 
// 拆分理由：
//   - 从 factorsAPI.js 提取，职责更单一
//   - 纯函数设计，易于测试和复用
// ==============================

import { timestampToYYYYMMDD } from '@/utils/timeParse'

/**
 * 应用复权调整
 * 
 * @param {Array} candles - 原始K线 [{ts, o, h, l, c, v}, ...]
 * @param {Array} factors - 复权因子 [{date, qfq_factor, hfq_factor}, ...]
 * @param {string} adjustType - 复权方式 'none'|'qfq'|'hfq'
 * @returns {Array} 调整后的K线
 */
export function applyAdjustment(candles, factors, adjustType) {
  // 不复权，直接返回
  if (adjustType === 'none' || !Array.isArray(factors) || factors.length === 0) {
    return candles
  }
  
  // 建立日期 → 因子的快速查找表
  const factorMap = new Map(
    factors.map(f => [f.date, f])
  )
  
  return candles.map(bar => {
    const barDate = timestampToYYYYMMDD(bar.ts)
    const factor = factorMap.get(barDate)
    
    if (!factor) {
      // 因子缺失，保持原值
      return bar
    }
    
    const f = adjustType === 'qfq' 
      ? factor.qfq_factor 
      : factor.hfq_factor
    
    return {
      ts: bar.ts,
      o: bar.o * f,
      h: bar.h * f,
      l: bar.l * f,
      c: bar.c * f,
      v: bar.v,
      // 保留原始值（用于tooltip对比）
      _raw: {
        o: bar.o,
        h: bar.h,
        l: bar.l,
        c: bar.c
      }
    }
  })
}