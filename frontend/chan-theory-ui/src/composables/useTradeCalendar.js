// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useTradeCalendar.js
// ==============================
// 说明：交易日历前端缓存与查询（单例 composable）
// 职责：
//   - 启动时从后端加载 trade_calendar 快照；
//   - 在内存中按“全局交易日序列”缓存（DB 中仅存交易日，故直接将所有 items 按 date 排序即得序列）；
//   - 提供 YYYYMMDD → 交易日索引 的查询与“是否在前 N 个交易日内”的判断。
// ==============================

import { ref, readonly } from "vue";
import { fetchTradeCalendarSnapshot } from "@/services/tradeCalendarService";

const ready = ref(false);
const loading = ref(false);
const error = ref("");

// 全局交易日序列（忽略 market 维度，假定全为 CN）
let _dates = [];
let _indexByDate = new Map();

let _singleton = null;

/**
 * 从后端快照构建全局交易日索引
 * @param {Array<{date:number,market:string,is_trading_day:number}>} items
 */
function buildMarketIndex(items) {
  _dates = [];
  _indexByDate = new Map();

  for (const row of items || []) {
    const date = Number(row?.date);
    // DB 仅存交易日，理论上每条都应视为有效；加上 >0 校验更稳健
    if (!Number.isFinite(date) || date <= 0) continue;
    _dates.push(date);
  }

  // 按日期升序排序，确保索引能够正确反映时间先后
  _dates.sort((a, b) => a - b);
  _dates.forEach((d, idx) => _indexByDate.set(d, idx));
}

/**
 * 保证交易日历已加载（幂等）
 */
async function ensureLoaded() {
  if (ready.value || loading.value) return;
  loading.value = true;
  error.value = "";

  try {
    const { items } = await fetchTradeCalendarSnapshot();
    buildMarketIndex(items);
    ready.value = true;
  } catch (e) {
    console.error("[useTradeCalendar] load snapshot failed", e);
    error.value = e?.message || "load trade_calendar failed";
  } finally {
    loading.value = false;
  }
}

/**
 * 获取指定日期（YYYYMMDD）的“交易日索引”（全局）
 * - 若该日期不在表中（即非交易日或未收录），返回 -1。
 */
function getTradingIndex(ymd) {
  const d = Number(ymd);
  if (!Number.isFinite(d)) return -1;
  const idx = _indexByDate.get(d);
  return typeof idx === "number" ? idx : -1;
}

/**
 * 判断 endYmd 是否处于 “自 startYmd 起的前 n 个交易日” 之内（全局）
 * - 依赖：startYmd 和 endYmd 都必须是有效交易日（能查到索引）。
 * - 逻辑：0 <= (idxEnd - idxStart) < n
 */
function isWithinNTradingDays({ startYmd, endYmd, n }) {
  const s = Number(startYmd);
  const e = Number(endYmd);
  const limit = Math.max(1, Number(n || 1));

  if (!Number.isFinite(s) || !Number.isFinite(e)) return false;

  const sIdx = getTradingIndex(s);
  const eIdx = getTradingIndex(e);
  
  // 若 IPO 日或当前 K 线日期不在交易日历中（数据缺失或非交易日），视为“无法判断”，返回 false（不豁免）
  if (sIdx < 0 || eIdx < 0) return false;

  const delta = eIdx - sIdx;
  return delta >= 0 && delta < limit;
}

/**
 * 单例导出
 */
export function useTradeCalendar() {
  if (_singleton) return _singleton;

  _singleton = {
    ready: readonly(ready),
    loading: readonly(loading),
    error: readonly(error),
    ensureLoaded,
    getTradingIndex,
    isWithinNTradingDays,
  };

  return _singleton;
}