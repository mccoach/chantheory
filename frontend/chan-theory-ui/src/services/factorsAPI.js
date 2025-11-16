// src/services/factorsAPI.js
// ==============================
// V2.0 - 纯API层（职责单一）
// 
// 核心改造：
//   - 删除 applyAdjustment 函数（移至 engines/adjustment.js）
//   - 保持纯粹的API查询职责
// ==============================

import { api } from '@/api/client'

/**
 * 查询复权因子
 * 
 * @param {string} symbol - 标的代码
 * @param {Object} options - 可选参数 {startDate, endDate}
 * @returns {Promise<Array>} 因子数组
 */
export async function fetchFactors(symbol, options = {}) {
  const params = new URLSearchParams()
  params.set('symbol', symbol)
  
  if (options.startDate) {
    params.set('start_date', options.startDate)
  }
  if (options.endDate) {
    params.set('end_date', options.endDate)
  }
  
  const { data } = await api.get(`/api/factors?${params.toString()}`, {
    timeout: 10000
  })
  
  return data.factors || []
}

// ===== 删除：applyAdjustment 函数（已移至 engines/adjustment.js）=====