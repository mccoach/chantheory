// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useWatchlist.js
// ==============================
// V6.0 - BREAKING: SSE 契约对齐（task.finished）
// ==============================

import { ref, readonly } from "vue";
import * as api from "@/services/watchlistService";
import { useEventStream } from "@/composables/useEventStream";

const CACHE_KEY = "chan_watchlist_v1";
const CACHE_TS_KEY = "chan_watchlist_ts";
const CACHE_VALID_MS = 24 * 60 * 60 * 1000; // 24小时

const items = ref([]);
const loading = ref(false);
const error = ref("");

let _singleton = null;

function ts() {
  return new Date().toISOString();
}

export function useWatchlist() {
  if (_singleton) return _singleton;

  const eventStream = useEventStream();

  // ==============================
  // 缓存操作
  // ==============================

  function loadFromCache() {
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      items.value = raw ? JSON.parse(raw) : [];
      console.log(`${ts()} [Watchlist] cache-load count=${items.value.length}`);
    } catch {
      items.value = [];
    }
  }

  // 异步写入 LocalStorage，避免阻塞
  function saveToCache() {
    const asyncWrite = (fn) => {
      if (typeof requestIdleCallback === "function") {
        requestIdleCallback(fn, { timeout: 2000 });
      } else {
        setTimeout(fn, 0);
      }
    };

    asyncWrite(() => {
      try {
        localStorage.setItem(CACHE_KEY, JSON.stringify(items.value));
        localStorage.setItem(CACHE_TS_KEY, Date.now().toString());
      } catch {}
    });
  }

  function getCacheAge() {
    try {
      const tsStr = localStorage.getItem(CACHE_TS_KEY);
      if (!tsStr) return null;
      return Date.now() - Number(tsStr);
    } catch {
      return null;
    }
  }

  // ==============================
  // 智能加载（启动时调用）
  // ==============================

  async function smartLoad() {
    loadFromCache();

    const cacheAge = getCacheAge();

    if (cacheAge === null || cacheAge > CACHE_VALID_MS) {
      console.log(`${ts()} [Watchlist] cache-expired → refresh-from-backend`);
      await refresh();
    } else {
      const ageMin = Math.floor(cacheAge / 60000);
      console.log(`${ts()} [Watchlist] cache-valid age_min=${ageMin} skip-refresh`);
    }
  }

  // ==============================
  // SSE 同步（最终一致性保障）
  // ==============================

  // NEW: task.finished（新契约）
  eventStream.subscribe("task.finished", (data) => {
    try {
      if (!data || data.type !== "task.finished") return;
      if (data.task_type !== "watchlist_update") return;

      const ok = String(data.overall_status || "") === "success";

      const action = data.summary?.extra?.action;
      const list = Array.isArray(data.summary?.extra?.items)
        ? data.summary.extra.items
        : [];

      console.log(
        `${ts()} [Watchlist][SSE] task.finished action=${action || "null"} ok=${ok} count=${list.length}`
      );

      if (ok && list.length) {
        items.value = list;
        saveToCache();
        console.log(`${ts()} [Watchlist] sse-sync count=${items.value.length}`);
      }
    } catch (e) {
      console.error(`${ts()} [Watchlist] sse-task.finished-error`, e);
    }
  });

  // ==============================
  // 后端同步（跨设备/手动刷新）
  // ==============================

  async function refresh() {
    loading.value = true;
    error.value = "";
    try {
      const data = await api.list();
      items.value = data?.items || [];
      saveToCache();
      console.log(`${ts()} [Watchlist] backend-refresh count=${items.value.length}`);
    } catch (e) {
      error.value = e?.message || "同步失败";
      console.error(`${ts()} [Watchlist] refresh-failed`, e);
    } finally {
      loading.value = false;
    }
  }

  // ==============================
  // 核心：乐观更新
  // ==============================

  async function addOne(symbol) {
    const sym = String(symbol || "").trim();
    if (!sym) return;

    const snapshot = items.value.slice();

    const newItems = items.value.filter((item) => item.symbol !== sym);
    newItems.push({
      symbol: sym,
      added_at: new Date().toISOString(),
      source: "manual",
    });
    items.value = newItems;
    saveToCache();

    console.log(`${ts()} [Watchlist] optimistic-add symbol=${sym}`);

    loading.value = true;
    error.value = "";

    try {
      await api.add(sym);
      console.log(`${ts()} [Watchlist] backend-confirm-add symbol=${sym}`);
    } catch (e) {
      error.value = e?.message || "添加失败";
      console.error(`${ts()} [Watchlist] backend-add-failed symbol=${sym}`, e);

      items.value = snapshot;
      saveToCache();

      alert(`添加失败：${e?.message || "网络错误"}`);
    } finally {
      loading.value = false;
    }
  }

  async function removeOne(symbol) {
    const sym = String(symbol || "").trim();
    if (!sym) return;

    const snapshot = items.value.slice();

    items.value = items.value.filter((item) => item.symbol !== sym);
    saveToCache();

    console.log(`${ts()} [Watchlist] optimistic-remove symbol=${sym}`);

    loading.value = true;
    error.value = "";

    try {
      await api.remove(sym);
      console.log(`${ts()} [Watchlist] backend-confirm-remove symbol=${sym}`);
    } catch (e) {
      error.value = e?.message || "删除失败";
      console.error(`${ts()} [Watchlist] backend-remove-failed symbol=${sym}`, e);

      items.value = snapshot;
      saveToCache();

      alert(`删除失败：${e?.message || "网络错误"}`);
    } finally {
      loading.value = false;
    }
  }

  _singleton = {
    items: readonly(items),
    loading: readonly(loading),
    error: readonly(error),
    smartLoad,
    loadFromCache,
    refresh,
    addOne,
    removeOne,
  };

  return _singleton;
}
