// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\utils\timeParse.js
// ==============================
// 说明：时间解析与基础日期运算工具（纯函数，零副作用）
// 职责：
//   - 将各种时间格式统一转换为 Date 对象（parseTimeValue）
//   - 在时间戳与 YYYYMMDD 整数之间转换（timestampToYYYYMMDD / ymdIntToDate / dateToYmdInt）
//   - 提供基础的工作日计数（countWeekdaysInclusive），仅做周历近似，不承载业务含义。
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
    return null;
  }
  
  // 已是 Date 对象
  if (timeValue instanceof Date) {
    return isNaN(timeValue.getTime()) ? null : timeValue;
  }
  
  // 数字类型（时间戳）
  if (typeof timeValue === "number") {
    // 秒级时间戳（10位数）→ 毫秒
    const ts =
      timeValue > 0 && timeValue < 10000000000 ? timeValue * 1000 : timeValue;
    
    const date = new Date(ts);
    return isNaN(date.getTime()) ? null : date;
  }
  
  // 字符串类型
  if (typeof timeValue === "string") {
    const date = new Date(timeValue);
    return isNaN(date.getTime()) ? null : date;
  }
  
  // 其他类型不支持
  return null;
}

/**
 * 时间戳转 YYYYMMDD 整数（用于复权因子匹配、按日对齐等）
 * 
 * @param {number} timestamp - 毫秒时间戳
 * @returns {number} YYYYMMDD 格式整数
 * 
 * @example
 *   timestampToYYYYMMDD(1730448000000) → 20241101
 */
export function timestampToYYYYMMDD(timestamp) {
  const date = parseTimeValue(timestamp);
  if (!date) return 0;
  
  const Y = date.getFullYear();
  const M = date.getMonth() + 1;
  const D = date.getDate();
  
  return Y * 10000 + M * 100 + D;
}

/**
 * YYYYMMDD 整数转 Date（本地时区，当天 00:00）
 * 
 * @param {number} ymdInt - 形如 20250115
 * @returns {Date|null}
 */
export function ymdIntToDate(ymdInt) {
  const n = Number(ymdInt);
  if (!Number.isFinite(n) || n <= 19000000 || n >= 30000000) return null;
  const y = Math.floor(n / 10000);
  const m = Math.floor((n % 10000) / 100) - 1;
  const d = n % 100;
  const dt = new Date(y, m, d);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

/**
 * Date 转 YYYYMMDD 整数
 * 
 * @param {Date} date 
 * @returns {number} YYYYMMDD 或 0
 */
export function dateToYmdInt(date) {
  if (!(date instanceof Date) || isNaN(date.getTime())) return 0;
  const Y = date.getFullYear();
  const M = date.getMonth() + 1;
  const D = date.getDate();
  return Y * 10000 + M * 100 + D;
}

/**
 * 计算两个日期之间（含起止）的工作日（周一~周五）数量
 * 
 * 用途：
 *   - 为“上市后第 N 个交易日”提供一个周历级别的近似；
 *   - 不依赖真实交易日历（节假日），避免 utils 模块承载业务规则。
 * 
 * @param {Date} startDate - 起始日期（含）
 * @param {Date} endDate   - 结束日期（含）
 * @returns {number} 工作日数量（若 end < start 则返回 0）
 */
export function countWeekdaysInclusive(startDate, endDate) {
  if (!(startDate instanceof Date) || !(endDate instanceof Date)) return 0;
  if (endDate < startDate) return 0;

  const MS_PER_DAY = 24 * 60 * 60 * 1000;
  const startDay = Math.floor(startDate.getTime() / MS_PER_DAY);
  const endDay = Math.floor(endDate.getTime() / MS_PER_DAY);
  const days = endDay - startDay + 1;
  if (days <= 0) return 0;

  const fullWeeks = Math.floor(days / 7);
  let weekdays = fullWeeks * 5;
  const remaining = days % 7;
  let startWeekday = startDate.getDay(); // 0=Sun..6=Sat

  for (let i = 0; i < remaining; i++) {
    const wd = (startWeekday + i) % 7;
    if (wd !== 0 && wd !== 6) {
      weekdays++;
    }
  }
  return weekdays;
}