// src/utils/timeFormat.js
// ==============================
// 说明：时间格式化工具（纯函数，零副作用）
// 职责：将 Date 对象格式化为字符串
// 设计：单一职责，只做格式化，不做解析
// 
// V3.0 重构：
//   - 删除别名导出（fmtTimeByFreq）
//   - 删除内部解析逻辑（移至 timeParse.js）
//   - 删除频率判断逻辑（移至 timeCheck.js）
//   - 保持原有调用签名（确保功能回归）
// ==============================

import { parseTimeValue } from './timeParse'
import { isMinuteFreq } from './timeCheck'

/**
 * 两位补零（原子工具）
 * @param {number} n - 数字
 * @returns {string}
 */
export function pad2(n) {
  return String(n).padStart(2, '0')
}

/**
 * 格式化 Date 对象为字符串
 * 
 * @param {Date} date - Date对象
 * @param {boolean} includeTime - 是否包含时分
 * @returns {string}
 * 
 * @example
 *   formatDateTime(new Date(2024,10,1,15,0), false) → "2024-11-01"
 *   formatDateTime(new Date(2024,10,1,15,0), true)  → "2024-11-01 15:00"
 */
export function formatDateTime(date, includeTime = false) {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) {
    return ''
  }
  
  const Y = date.getFullYear()
  const M = pad2(date.getMonth() + 1)
  const D = pad2(date.getDate())
  
  if (!includeTime) {
    return `${Y}-${M}-${D}`
  }
  
  const h = pad2(date.getHours())
  const m = pad2(date.getMinutes())
  
  return `${Y}-${M}-${D} ${h}:${m}`
}

/**
 * 按频率格式化时间（业务组合函数）
 * 
 * 职责：
 *   1. 调用 parseTimeValue() 解析输入
 *   2. 调用 isMinuteFreq() 判断精度
 *   3. 调用 formatDateTime() 输出格式
 * 
 * @param {string} freq - 频率
 * @param {number|string|Date} timeValue - 时间值
 * @returns {string}
 * 
 * @example
 *   formatTimeByFreq('1d', 1730448000000) → "2024-11-01"
 *   formatTimeByFreq('5m', 1730448000000) → "2024-11-01 15:00"
 */
export function formatTimeByFreq(freq, timeValue) {
  const date = parseTimeValue(timeValue)
  if (!date) {
    return ''
  }
  
  const includeTime = isMinuteFreq(freq)
  return formatDateTime(date, includeTime)
}