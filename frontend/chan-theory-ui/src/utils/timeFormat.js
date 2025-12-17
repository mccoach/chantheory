// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\utils\timeFormat.js
// ==============================
// 说明：时间格式化工具（纯函数，零副作用）
// 职责：将 Date 对象或时间值格式化为字符串
// 设计：
//   - Core：pad2 / formatDateTime
//   - Freq 感知层：formatTimeByFreq（根据频率决定是否带时分）
//   - 辅助：formatYmdInt（YYYYMMDD整数 → "YYYY-MM-DD"）
// ==============================

import { parseTimeValue } from "./timeParse";
import { isMinuteFreq } from "./timeCheck";

/**
 * 两位补零（原子工具）
 * @param {number} n - 数字
 * @returns {string}
 */
export function pad2(n) {
  return String(n).padStart(2, "0");
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
    return "";
  }
  
  const Y = date.getFullYear();
  const M = pad2(date.getMonth() + 1);
  const D = pad2(date.getDate());
  
  if (!includeTime) {
    return `${Y}-${M}-${D}`;
  }
  
  const h = pad2(date.getHours());
  const m = pad2(date.getMinutes());
  
  return `${Y}-${M}-${D} ${h}:${m}`;
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
 * @returns {string} 格式化后的字符串
 * 
 * @example
 *   formatTimeByFreq('1d', 1730448000000) → "2024-11-01"
 *   formatTimeByFreq('5m', 1730448000000) → "2024-11-01 15:00"
 */
export function formatTimeByFreq(freq, timeValue) {
  const date = parseTimeValue(timeValue);
  if (!date) {
    return "";
  }
  
  const includeTime = isMinuteFreq(freq);
  return formatDateTime(date, includeTime);
}

/**
 * 将 YYYYMMDD 整数格式化为 "YYYY-MM-DD"
 * 
 * @param {number} ymdInt - 形如 20250115
 * @returns {string}
 * 
 * @example
 *   formatYmdInt(20241101) → "2024-11-01"
 */
export function formatYmdInt(ymdInt) {
  const n = Number(ymdInt);
  if (!Number.isFinite(n)) return "";
  const s = String(n).padStart(8, "0");
  if (s.length !== 8) return "";
  const y = s.slice(0, 4);
  const m = s.slice(4, 6);
  const d = s.slice(6, 8);
  return `${y}-${m}-${d}`;
}