// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useTradeCalendar.js
// ==============================
// 说明：交易日历前端缓存与查询（单例 composable）
//
// V2.0 - NEW: ensureReady（唯一编排链路）
// 背景约定：所有任务由前端发起，后端收到请求先做缺口判断，必要时远端拉取落库后通知前端。
// 目标：将 App.vue 中“declare + wait + ensureLoaded”两段逻辑收敛到本模块，形成唯一工作路径。
// 失败策略：失败只返回结果（ok=false），不 throw、不 alert、不做额外副作用。
// ==============================

import { ref, readonly } from "vue";
import { fetchTradeCalendarSnapshot } from "@/services/tradeCalendarService";
import { declareTradeCalendar } from "@/services/ensureDataAPI";
import { waitTasksDone } from "@/composables/useTaskWaiter";

const ready = ref(false);
const loading = ref(false);
const error = ref("");

// 全局交易日序列
let _dates = [];
let _indexByDate = new Map();

let _singleton = null;

function buildMarketIndex(items) {
  _dates = [];
  _indexByDate = new Map();

  for (const row of items || []) {
    const date = Number(row?.date);
    if (!Number.isFinite(date) || date <= 0) continue;
    _dates.push(date);
  }

  _dates.sort((a, b) => a - b);
  _dates.forEach((d, idx) => _indexByDate.set(d, idx));
}

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
 * 唯一入口：确保 trade_calendar 已就绪
 * - force_fetch=false：后端缺口判断，无缺口则直接使用 DB
 * - force_fetch=true：强制远端拉取（如你未来需要）
 *
 * 失败策略：返回 {ok:false}，不 throw、不做额外副作用
 */
async function ensureReady({ force_fetch = false, timeoutMs = 60000 } = {}) {
  // 幂等：已 ready 且不要求强制刷新 => 直接成功
  if (ready.value === true && force_fetch !== true) {
    return { ok: true };
  }

  // 1) 声明任务（后端缺口判断/必要时拉取）
  try {
    const t = await declareTradeCalendar({ force_fetch: !!force_fetch });
    const tid = t?.task_id ? String(t.task_id) : null;
    if (tid) {
      await waitTasksDone({ taskIds: [tid], timeoutMs: Math.max(1000, Number(timeoutMs || 60000)) });
    }
  } catch (e) {
    console.error("[useTradeCalendar] declare/wait failed", e);
    return { ok: false, message: e?.message || "declare/wait failed" };
  }

  // 2) 拉取快照并加载到内存索引
  try {
    await ensureLoaded();
    return { ok: ready.value === true };
  } catch (e) {
    // ensureLoaded 内部不 throw，这里只是兜底
    return { ok: false, message: e?.message || "ensureLoaded failed" };
  }
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

    // loaders
    ensureLoaded,
    ensureReady,

    // query
    getTradingIndex,
    isWithinNTradingDays,
  };

  return _singleton;
}
