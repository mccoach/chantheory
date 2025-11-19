// src/composables/engines/indicators.js
// ==============================
// 说明：指标计算引擎（纯函数，零副作用）
// 职责：根据K线数据和配置计算所有技术指标
// 设计：完全独立，不依赖任何Vue响应式
// 
// 拆分理由：
//   - 从 useMarketView 提取，降低其职责复杂度
//   - 纯函数设计，易于单元测试
//   - 可被其他模块复用（如导出、回测）
// ==============================

import { 
  calculateMA, 
  calculateMACD, 
  calculateKDJ, 
  calculateRSI, 
  calculateBOLL 
} from '@/services/technicalIndicators'

/**
 * 指标计算引擎
 * 
 * @param {Array} candles - K线数据 [{ts, o, h, l, c, v}, ...]
 * @param {Object} config - 指标配置
 * @param {Object} config.maPeriodsMap - MA周期映射 {MA5: 5, MA10: 10}
 * @param {Object} config.maConfigs - MA启用配置（从settings读取）
 * @param {boolean} config.useMACD - 是否启用MACD
 * @param {boolean} config.useKDJ - 是否启用KDJ
 * @param {boolean} config.useRSI - 是否启用RSI
 * @param {boolean} config.useBOLL - 是否启用BOLL
 * @returns {Object} 指标数据 {MA5: [...], MACD_DIF: [...], ...}
 */
export function computeIndicators(candles, config) {
  // 输入验证
  if (!Array.isArray(candles) || candles.length === 0) {
    return {}
  }
  
  // 提取价格序列
  const closes = candles.map(c => c.c)
  const highs = candles.map(c => c.h)
  const lows = candles.map(c => c.l)
  
  const result = {}
  
  // MA（仅计算已启用的）
  if (config.maPeriodsMap && config.maConfigs) {
    const enabledMA = {}
    Object.entries(config.maPeriodsMap).forEach(([key, period]) => {
      if (config.maConfigs[key]?.enabled) {
        enabledMA[key] = period
      }
    })
    
    if (Object.keys(enabledMA).length > 0) {
      Object.assign(result, calculateMA(closes, enabledMA))
    }
  }
  
  // MACD（使用设置行给定的周期）
  if (config.useMACD) {
    const macdCfg = config.macdSettings || {}
    const period = macdCfg.period || {}
    const fast = Number(period.fast) || 12
    const slow = Number(period.slow) || 26
    const signal = Number(period.signal) || 9
    
    Object.assign(result, calculateMACD(closes, fast, slow, signal))
  }
  
  // KDJ
  if (config.useKDJ) {
    Object.assign(result, calculateKDJ(highs, lows, closes))
  }
  
  // RSI
  if (config.useRSI) {
    Object.assign(result, calculateRSI(closes))
  }
  
  // BOLL
  if (config.useBOLL) {
    Object.assign(result, calculateBOLL(closes))
  }
  
  return result
}