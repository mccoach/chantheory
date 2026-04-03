// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useTradeCalendar.js
// ==============================
// 说明：交易日历前端缓存与查询（单例 composable）
//
// 当前职责（纯业务执行器）：
//   - 读取 trade_calendar 快照
//   - 构建前端交易日索引
//   - 提供 getTradingIndex / isWithinNTradingDays 查询
//   - 提供 waitReadable 等待能力
//
// 命令权收敛：
//   - 本模块不再自行触发“准备任务”
//   - 触发 declareTradeCalendar 的权力只允许存在于：
//       1) App 启动链
//       2) 未来若有明确页面按钮，则由按钮路径显式调用
// ==============================

import { ref, readonly } from "vue";
import { fetchTradeCalendarSnapshot } from "@/services/tradeCalendarService";

const ready = ref(false);
const loading = ref(false);
const error = ref("");

// 全局“交易日”序列（注意：不是自然日序列）
let _dates = [];
let _indexByDate = new Map();

let _singleton = null;
let _loadingPromise = null;

function isTradingDayRow(row) {
  const flag = Number(row?.is_trading_day);
  return flag === 1;
}

function buildMarketIndex(items) {
  _dates = [];
  _indexByDate = new Map();

  for (const row of items || []) {
    if (!isTradingDayRow(row)) continue;

    const date = Number(row?.date);
    if (!Number.isFinite(date) || date <= 0) continue;

    _dates.push(date);
  }

  _dates.sort((a, b) => a - b);
  _dates.forEach((d, idx) => _indexByDate.set(d, idx));
}

async function loadSnapshot() {
  const { items } = await fetchTradeCalendarSnapshot();
  buildMarketIndex(items);
  ready.value = true;
}

async function ensureLoaded() {
  if (ready.value) return { ok: true };
  if (_loadingPromise) return _loadingPromise;

  loading.value = true;
  error.value = "";

  _loadingPromise = (async () => {
    try {
      await loadSnapshot();
      return { ok: true };
    } catch (e) {
      console.error("[useTradeCalendar] load snapshot failed", e);
      error.value = e?.message || "load trade_calendar failed";
      return { ok: false, message: error.value };
    } finally {
      loading.value = false;
      _loadingPromise = null;
    }
  })();

  return _loadingPromise;
}

async function waitReadable({ timeoutMs = 60000, pollMs = 100 } = {}) {
  const deadline = Date.now() + Math.max(1000, Number(timeoutMs || 60000));

  while (loading.value) {
    if (Date.now() > deadline) {
      return { ok: false, message: "[useTradeCalendar] waitReadable timeout" };
    }
    await new Promise((resolve) => setTimeout(resolve, Math.max(20, Number(pollMs || 100))));
  }

  return { ok: true };
}

function getTradingIndex(ymd) {
  const d = Number(ymd);
  if (!Number.isFinite(d)) return -1;
  const idx = _indexByDate.get(d);
  return typeof idx === "number" ? idx : -1;
}

function isWithinNTradingDays({ startYmd, endYmd, n }) {
  const s = Number(startYmd);
  const e = Number(endYmd);
  const limit = Math.max(1, Number(n || 1));

  if (!Number.isFinite(s) || !Number.isFinite(e)) return false;

  const sIdx = getTradingIndex(s);
  const eIdx = getTradingIndex(e);

  if (sIdx < 0 || eIdx < 0) return false;

  const delta = eIdx - sIdx;
  return delta >= 0 && delta < limit;
}

export function useTradeCalendar() {
  if (_singleton) return _singleton;

  _singleton = {
    ready: readonly(ready),
    loading: readonly(loading),
    error: readonly(error),

    ensureLoaded,
    waitReadable,

    getTradingIndex,
    isWithinNTradingDays,
  };

  return _singleton;
}
