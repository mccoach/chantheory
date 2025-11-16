// src/utils/timeParse.js
// ==============================
// 说明：时间解析工具（纯函数，零副作用）
// 职责：将各种时间格式统一转换为 Date 对象
// 设计：单一职责，只做解析，不做格式化
// ==============================

/**
 * 解析时间值为 Date 对象
 * 
 * 支持输入类型：
 *   - 毫秒时间戳（13位）
 *   - 秒时间戳（10位，自动转换）
 *   - ISO字符串（'2024-11-05T15:00:00'）
 *   - Date对象（直接返回）
 * 
 * @param {number|string|Date} timeValue - 时间值
 * @returns {Date|null} Date对象，解析失败返回 null
 * 
 * @example
 *   parseTimeValue(1730448000000) → Date(2024-11-01 15:00:00)
 *   parseTimeValue(1730448000)    → Date(2024-11-01 15:00:00)
 *   parseTimeValue("2024-11-01")  → Date(2024-11-01 00:00:00)
 *   parseTimeValue(new Date())    → Date(...)
 *   parseTimeValue(null)          → null
 */
export function parseTimeValue(timeValue) {
  // 处理空值
  if (timeValue == null) {
    return null
  }
  
  // 已是 Date 对象
  if (timeValue instanceof Date) {
    return isNaN(timeValue.getTime()) ? null : timeValue
  }
  
  // 数字类型（时间戳）
  if (typeof timeValue === 'number') {
    // 秒级时间戳（10位数）→ 毫秒
    const ts = timeValue > 0 && timeValue < 10000000000 
      ? timeValue * 1000 
      : timeValue
    
    const date = new Date(ts)
    return isNaN(date.getTime()) ? null : date
  }
  
  // 字符串类型
  if (typeof timeValue === 'string') {
    const date = new Date(timeValue)
    return isNaN(date.getTime()) ? null : date
  }
  
  // 其他类型不支持
  return null
}

/**
 * 时间戳转 YYYYMMDD 整数（用于复权因子匹配）
 * 
 * @param {number} timestamp - 毫秒时间戳
 * @returns {number} YYYYMMDD 格式整数
 * 
 * @example
 *   timestampToYYYYMMDD(1730448000000) → 20241101
 */
export function timestampToYYYYMMDD(timestamp) {
  const date = parseTimeValue(timestamp)
  if (!date) return 0
  
  const Y = date.getFullYear()
  const M = date.getMonth() + 1
  const D = date.getDate()
  
  return Y * 10000 + M * 100 + D
}