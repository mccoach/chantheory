// src/services/marketService.js
// ==============================
// 说明：行情服务（前端调用后端 /api/candles）
// - 本轮变更：请求快照日志仅在开发模式打印（import.meta.env.DEV），避免生产环境噪音。
// ==============================

import { api } from "@/api/client"; // 统一 axios 客户端（含 trace_id 拦截）

// 工具：YYYY-MM-DD 字符串化
function toDateStr(d) {
  const pad = (n) => String(n).padStart(2, "0"); // 两位补零
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; // 组装日期
}

// 默认起止（严格）
const DEFAULT_START = "1996-01-01"; // 默认最早日期
function todayStr() {
  return toDateStr(new Date()); // 今日 YYYY-MM-DD
}

// 解析：若为 YYYY-MM-DD 返回 Date；若为毫秒/数字串，转 Date；否则返回 null
function parseToDate(x) {
  if (x == null || x === "") return null;               // 空值
  const s = String(x).trim();                            // 规范化
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {                   // YYYY-MM-DD
    const d = new Date(`${s}T00:00:00`);                 // 当天 00:00
    return isNaN(d.getTime()) ? null : d;                // 失败则 null
  }
  if (!Number.isNaN(Number(s))) {                        // 数字（毫秒）
    const ms = Number(s);                                 // 转数值
    const d = new Date(ms);                               // 毫秒→Date
    return isNaN(d.getTime()) ? null : d;                 // 失败则 null
  }
  return null;                                           // 无法解析
}

export async function fetchCandles(params) {
  const q = { ...params }; // 拷贝参数

  // 1) 统一强制 start/end 存在
  let dStart = parseToDate(q.start);
  let dEnd = parseToDate(q.end);
  if (!dStart) dStart = new Date(`${DEFAULT_START}T00:00:00`); // 默认起始
  if (!dEnd) dEnd = new Date(`${todayStr()}T00:00:00`);        // 默认结束

  // 2) 若反向，自动交换
  if (dStart.getTime() > dEnd.getTime()) {
    const t = dStart; dStart = dEnd; dEnd = t;
  }

  // 3) 以 YYYY-MM-DD 传参（后端已能兜底毫秒/日期，但前端也保证规范）
  q.start = toDateStr(dStart);
  q.end = toDateStr(dEnd);

  // 4) 组装查询串
  const search = new URLSearchParams();
  Object.entries(q).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") search.set(k, v);
  });

  // 开发期打印请求快照（生产关闭，避免噪音）
  if (import.meta.env?.DEV) {
    // NEW: 统一毫秒时间戳 + url 快照（仅开发模式）
    // eslint-disable-next-line no-console
    console.log(
      `[${Date.now()}][frontend/services/marketService.js] GET /api/candles?${search.toString()} (normalized params)`,
      q
    );
  }

  // 实际请求
  const { data } = await api.get(`/api/candles?${search.toString()}`, {
    timeout: 15000,
  });
  return data; // 返回后端数据
}
