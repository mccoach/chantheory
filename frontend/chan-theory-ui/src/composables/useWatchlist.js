// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useWatchlist.js
// ==============================
// V5.2 - SSE 对齐版（Task/Job 模型 + 扁平日志）
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
    // 使用 requestIdleCallback 延迟写入（不阻塞主线程）
    const asyncWrite = (fn) => {
      if (typeof requestIdleCallback === "function") {
        // 现代浏览器：在空闲时执行
        requestIdleCallback(fn, { timeout: 2000 });
      } else {
        // 降级方案：Safari/旧浏览器不支持 requestIdleCallback
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
    // 1. 先读缓存（立即可用）
    loadFromCache();

    // 2. 检查新鲜度
    const cacheAge = getCacheAge();

    if (cacheAge === null || cacheAge > CACHE_VALID_MS) {
      console.log(`${ts()} [Watchlist] cache-expired → refresh-from-backend`);
      await refresh();
    } else {
      const ageMin = Math.floor(cacheAge / 60000);
      console.log(
        `${ts()} [Watchlist] cache-valid age_min=${ageMin} skip-refresh`
      );
    }
  }

  // ==============================
  // SSE 同步（最终一致性保障）
  // ==============================

  eventStream.subscribe("task_done", (data) => {
    try {
      if (!data || data.task_type !== "watchlist_update") return;

      const action = data.summary?.extra?.action;
      const list = Array.isArray(data.summary?.extra?.items)
        ? data.summary.extra.items
        : [];

      const ok = data.overall_status === "success";

      console.log(
        `${ts()} [Watchlist][SSE] task_done action=${action || "null"} ok=${ok} count=${list.length}`
      );

      if (list.length) {
        items.value = list;
        saveToCache();
        console.log(
          `${ts()} [Watchlist] sse-sync count=${items.value.length}`
        );
      }
    } catch (e) {
      console.error(`${ts()} [Watchlist] sse-task_done-error`, e);
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

    // ===== 步骤1：乐观更新（立即生效）=====
    const snapshot = items.value.slice(); // 备份（用于回滚）

    // 去重后追加
    const newItems = items.value.filter((item) => item.symbol !== sym);
    newItems.push({
      symbol: sym,
      added_at: new Date().toISOString(),
      source: "manual",
    });
    items.value = newItems;
    saveToCache();

    console.log(`${ts()} [Watchlist] optimistic-add symbol=${sym}`);

    // ===== 步骤2：后台同步（不阻塞）=====
    loading.value = true;
    error.value = "";

    try {
      await api.add(sym);
      console.log(`${ts()} [Watchlist] backend-confirm-add symbol=${sym}`);
    } catch (e) {
      error.value = e?.message || "添加失败";
      console.error(`${ts()} [Watchlist] backend-add-failed symbol=${sym}`, e);

      // ===== 步骤3：失败回滚 =====
      items.value = snapshot;
      saveToCache();

      // 显示错误提示（可选：集成 Toast 组件）
      alert(`添加失败：${e?.message || "网络错误"}`);
    } finally {
      loading.value = false;
    }
  }

  async function removeOne(symbol) {
    const sym = String(symbol || "").trim();
    if (!sym) return;

    // ===== 步骤1：乐观删除 =====
    const snapshot = items.value.slice();

    items.value = items.value.filter((item) => item.symbol !== sym);
    saveToCache();

    console.log(`${ts()} [Watchlist] optimistic-remove symbol=${sym}`);

    // ===== 步骤2：后台同步 =====
    loading.value = true;
    error.value = "";

    try {
      await api.remove(sym);
      console.log(`${ts()} [Watchlist] backend-confirm-remove symbol=${sym}`);
    } catch (e) {
      error.value = e?.message || "删除失败";
      console.error(`${ts()} [Watchlist] backend-remove-failed symbol=${sym}`, e);

      // ===== 步骤3：失败回滚 =====
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