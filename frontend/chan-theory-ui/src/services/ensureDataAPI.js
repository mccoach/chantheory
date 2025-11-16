// frontend/src/services/ensureDataAPI.js
// ==============================
// V5.0 - 第一性原理版
// ==============================

import { api } from '@/api/client'

/**
 * 通用声明函数
 */
async function declare(payload) {
  const { data } = await api.post('/api/ensure-data', payload)
  return data
}

/**
 * 声明当前标的数据需求
 * P20: K线+因子（最高优先级，阻塞渲染）
 * P30: 档案（次优先级，不阻塞渲染）
 * @param {string} symbol - 标的代码
 * @param {string} freq - 频率
 * @param {Object} options - 可选参数 {force_fetch?: boolean}
 */
export async function declareCurrent(symbol, freq, options = {}) {
  console.log(`[API] 声明当前标的: ${symbol} ${freq}`, options.force_fetch ? '(强制拉取)' : '')
  
  return declare({
    requirements: [{
      scope: 'symbol',
      symbol: symbol,
      force_fetch: options.force_fetch || false,  // ← 新增字段
      includes: [
        {type: 'current_kline', freq: freq, priority: 20},
        {type: 'current_factors', priority: 20},
        {type: 'current_profile', priority: 30},
      ]
    }]
  })
}

/**
 * 声明全局数据需求
 * P40: 标的列表
 */
export async function declareGlobal() {
  console.log('[API] 声明全局数据: 标的列表')
  
  return declare({
    requirements: [{
      scope: 'global',
      includes: [
        {type: 'symbol_index', priority: 40}
      ]
    }]
  })
}