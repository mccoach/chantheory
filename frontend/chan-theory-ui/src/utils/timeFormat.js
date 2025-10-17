// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\utils\timeFormat.js
// ==============================
// 说明：时间格式化工具（统一复用）
// - 提供 pad2、isMinuteFreq、fmtTimeByFreq、makeAxisLabelFormatter、fmtShort
// - 解析均基于浏览器本地 new Date()，与现有实现保持一致口径。
// ==============================

/** 两位补零，如 3 → "03" */
export function pad2(n) {
  return String(n).padStart(2, "0");
}

/** 是否分钟族（字符串以 m 结尾，如 "1m"/"5m"） */
export function isMinuteFreq(freq) {
  return typeof freq === "string" && /m$/.test(freq);
}

/**
 * 将 ISO8601 时间（可能带时区）格式化为“无时区短文本”
 * - 分钟族：YYYY-MM-DD HH:MM
 * - 日/周/月：YYYY-MM-DD
 */
export function fmtTimeByFreq(freq, isoVal) {
  try {
    const d = new Date(isoVal);
    if (Number.isNaN(d.getTime())) return String(isoVal || "");
    const Y = d.getFullYear();
    const M = pad2(d.getMonth() + 1);
    const D = pad2(d.getDate());
    const h = pad2(d.getHours());
    const m = pad2(d.getMinutes());
    return isMinuteFreq(freq) ? `${Y}-${M}-${D} ${h}:${m}` : `${Y}-${M}-${D}`;
  } catch {
    return String(isoVal || "");
  }
}

/** 返回横轴标签格式化函数（依频率输出短文本） */
export function makeAxisLabelFormatter(freq) {
  return (val) => fmtTimeByFreq(freq, val);
}

/**
 * 短格式化（常用于预览文案）
 * - 分钟族：YYYY-MM-DD HH:MM
 * - 日/周/月：YYYY-MM-DD
 * - freq 可选：未传则按日期输出 YYYY-MM-DD（与现实现一致）
 */
export function fmtShort(isoVal, freq) {
  try {
    const d = new Date(isoVal);
    if (Number.isNaN(d.getTime())) return "";
    const Y = d.getFullYear();
    const M = pad2(d.getMonth() + 1);
    const D = pad2(d.getDate());
    if (isMinuteFreq(freq)) {
      const h = pad2(d.getHours());
      const m = pad2(d.getMinutes());
      return `${Y}-${M}-${D} ${h}:${m}`;
    }
    return `${Y}-${M}-${D}`;
  } catch {
    return "";
  }
}
