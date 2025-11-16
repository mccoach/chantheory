// src/utils/timeCheck.js
// ==============================
// 说明：频率判断工具（纯函数，零副作用）
// 职责：判断频率类型
// 设计：单一职责，只做判断，不做计算
// ==============================

/**
 * 判断是否分钟族频率
 * 
 * @param {string} freq - 频率字符串
 * @returns {boolean}
 * 
 * @example
 *   isMinuteFreq('1m')  → true
 *   isMinuteFreq('5m')  → true
 *   isMinuteFreq('1d')  → false
 */
export function isMinuteFreq(freq) {
  return typeof freq === 'string' && /m$/.test(freq)
}

/**
 * 判断是否日线族频率
 * 
 * @param {string} freq - 频率字符串
 * @returns {boolean}
 * 
 * @example
 *   isDailyFreq('1d') → true
 *   isDailyFreq('1w') → true
 *   isDailyFreq('1M') → true
 *   isDailyFreq('5m') → false
 */
export function isDailyFreq(freq) {
  return typeof freq === 'string' && /^(1d|1w|1M)$/.test(freq)
}