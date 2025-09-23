// src/services/marketService.js
// ==============================
// 说明：行情服务（前端仅转发“频率/窗宽/锚点/或bars”到后端；不再本地计算视窗）
// - 新增：支持传入 options.signal（AbortController.signal），通过 axios meta.signal 透传给底层请求。
// - 依然支持 include / ma_periods；start/end 在新模式下不再使用（保持参数兼容）
import { api } from "@/api/client"; // 统一 axios 客户端（含 trace_id 拦截)

// 工具：YYYY-MM-DD（保留兼容）
function toDateStr(d) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
const DEFAULT_START = "1990-01-01";
function todayStr() {
  return toDateStr(new Date());
}

function parseToDate(x) {
  if (x == null || x === "") return null;
  const s = String(x).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
    const d = new Date(`${s}T00:00:00`);
    return isNaN(d.getTime()) ? null : d;
  }
  if (!Number.isNaN(Number(s))) {
    const ms = Number(s);
    const d = new Date(ms);
    return isNaN(d.getTime()) ? null : d;
  }
  return null;
}

/**
 * fetchCandles(params, options?)
 * params: 见调用处（code/freq/adjust/include/ma_periods/window_preset/bars/anchor_ts）
 * options: { signal?: AbortSignal }
 */
export async function fetchCandles(params, options = {}) {
  // 仅组装后端所需：code/freq/adjust/include/ma_periods + window_preset/bars/anchor_ts
  const q = { ...params };

  // 新模式：不依赖 start/end；保留兼容（不传亦可）
  let dStart = parseToDate(q.start);
  let dEnd = parseToDate(q.end);
  if (!dStart) dStart = new Date(`${DEFAULT_START}T00:00:00`);
  if (!dEnd) dEnd = new Date(`${todayStr()}T00:00:00`);
  if (dStart.getTime() > dEnd.getTime()) {
    const t = dStart;
    dStart = dEnd;
    dEnd = t;
  }

  // 构造查询串（含 window_preset/bars/anchor_ts）
  const search = new URLSearchParams();
  const allowKeys = new Set([
    "code",
    "freq",
    "adjust",
    "include",
    "ma_periods",
    "window_preset",
    "bars",
    "anchor_ts",
  ]);
  Object.entries(q).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    if (!allowKeys.has(k)) return;
    search.set(k, v);
  });

  if (import.meta.env?.DEV) {
    console.log(
      `[${Date.now()}][frontend/services/marketService.js] GET /api/candles?${search.toString()}`,
      q
    );
  }

  // 关键点：通过 meta.signal 传入 axios -> config.signal（由 api/client.js 拦截器完成）
  const { data } = await api.get(`/api/candles?${search.toString()}`, {
    timeout: 15000,
    meta: options.signal ? { signal: options.signal } : undefined,
  });
  return data;
}
