// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useWatchlist.js
// ==============================
// V8.1 - BREAKING: watchlist 彻底升级为双主键最终版
//
// 当前职责：
//   - 读取本地缓存
//   - 显式刷新后端结果
//   - 乐观更新 add / remove
//   - 监听 task.finished 做最终一致性同步
//
// 最终约束：
//   - watchlist 唯一标识统一为 (symbol, market)
//   - 不再支持 symbol-only 旧链路
//   - 本地缓存 schema 升级为 v2，不迁移旧缓存
//
// 设计原则：
//   - 唯一真相源：后端 watchlist items（含 symbol + market）
//   - 状态层只负责 cache / refresh / optimistic update / SSE sync
//   - UI 层只传 {symbol, market}
// ==============================

import { ref, readonly } from "vue";
import * as api from "@/services/watchlistService";
import { useEventStream } from "@/composables/useEventStream";

const CACHE_KEY = "chan_watchlist_v2";
const CACHE_TS_KEY = "chan_watchlist_v2_ts";

const items = ref([]);
const loading = ref(false);
const error = ref("");

let _singleton = null;
let _sseSubscribed = false;

function ts() {
  return new Date().toISOString();
}

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function asMarket(x) {
  return asStr(x).toUpperCase();
}

function normalizeIdentity(input = {}) {
  return {
    symbol: asStr(input.symbol),
    market: asMarket(input.market),
  };
}

function identityKey(symbol, market) {
  return `${asMarket(market)}:${asStr(symbol)}`;
}

function normalizeWatchlistItem(raw) {
  const src = raw && typeof raw === "object" ? raw : {};
  const symbol = asStr(src.symbol);
  const market = asMarket(src.market);

  if (!symbol || !market) return null;

  return {
    symbol,
    market,
    added_at: src.added_at ? String(src.added_at) : "",
    source: src.source ? String(src.source) : "manual",
    note: src.note == null ? "" : String(src.note),
    tags: Array.isArray(src.tags) ? src.tags.slice() : [],
    sort_order: Number.isFinite(+src.sort_order) ? +src.sort_order : 0,
    updated_at: src.updated_at ? String(src.updated_at) : "",
    name: src.name == null ? "" : String(src.name),
    type: src.type == null ? "" : String(src.type),
    class: src.class == null ? "" : String(src.class),
    listing_date:
      src.listing_date != null && Number.isFinite(+src.listing_date)
        ? +src.listing_date
        : null,
  };
}

function normalizeWatchlistItems(list) {
  const arr = Array.isArray(list) ? list : [];
  const out = [];
  const seen = new Set();

  for (const raw of arr) {
    const item = normalizeWatchlistItem(raw);
    if (!item) continue;

    const key = identityKey(item.symbol, item.market);
    if (seen.has(key)) continue;

    seen.add(key);
    out.push(item);
  }

  return out;
}

function replaceAllItems(nextItems) {
  items.value = normalizeWatchlistItems(nextItems);
}

export function useWatchlist() {
  if (_singleton) return _singleton;

  const eventStream = useEventStream();

  function loadFromCache() {
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      replaceAllItems(parsed);
      console.log(`${ts()} [Watchlist] cache-load count=${items.value.length}`);
    } catch {
      items.value = [];
    }
  }

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

  function ensureSseSubscription() {
    if (_sseSubscribed) return;
    _sseSubscribed = true;

    eventStream.subscribe("task.finished", (data) => {
      try {
        if (!data) return;
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
          replaceAllItems(list);
          saveToCache();
          console.log(`${ts()} [Watchlist] sse-sync count=${items.value.length}`);
        }
      } catch (e) {
        console.error(`${ts()} [Watchlist] sse-task.finished-error`, e);
      }
    });
  }

  async function refresh() {
    ensureSseSubscription();

    loading.value = true;
    error.value = "";
    try {
      const data = await api.list();
      replaceAllItems(data?.items || []);
      saveToCache();
      console.log(`${ts()} [Watchlist] backend-refresh count=${items.value.length}`);
    } catch (e) {
      error.value = e?.message || "同步失败";
      console.error(`${ts()} [Watchlist] refresh-failed`, e);
    } finally {
      loading.value = false;
    }
  }

  async function addOne(identity) {
    ensureSseSubscription();

    const id = normalizeIdentity(identity);
    if (!id.symbol || !id.market) return;

    const snapshot = items.value.slice();
    const key = identityKey(id.symbol, id.market);

    const nextItems = snapshot.filter(
      (item) => identityKey(item.symbol, item.market) !== key
    );
    nextItems.push({
      symbol: id.symbol,
      market: id.market,
      added_at: new Date().toISOString(),
      source: "manual",
      note: "",
      tags: [],
      sort_order: 0,
      updated_at: "",
      name: "",
      type: "",
      class: "",
      listing_date: null,
    });

    items.value = nextItems;
    saveToCache();

    console.log(`${ts()} [Watchlist] optimistic-add key=${key}`);

    loading.value = true;
    error.value = "";

    try {
      await api.add(id);
      console.log(`${ts()} [Watchlist] backend-confirm-add key=${key}`);
    } catch (e) {
      error.value = e?.message || "添加失败";
      console.error(`${ts()} [Watchlist] backend-add-failed key=${key}`, e);

      items.value = snapshot;
      saveToCache();

      alert(`添加失败：${e?.message || "网络错误"}`);
    } finally {
      loading.value = false;
    }
  }

  async function removeOne(identity) {
    ensureSseSubscription();

    const id = normalizeIdentity(identity);
    if (!id.symbol || !id.market) return;

    const snapshot = items.value.slice();
    const key = identityKey(id.symbol, id.market);

    items.value = items.value.filter(
      (item) => identityKey(item.symbol, item.market) !== key
    );
    saveToCache();

    console.log(`${ts()} [Watchlist] optimistic-remove key=${key}`);

    loading.value = true;
    error.value = "";

    try {
      await api.remove(id);
      console.log(`${ts()} [Watchlist] backend-confirm-remove key=${key}`);
    } catch (e) {
      error.value = e?.message || "删除失败";
      console.error(`${ts()} [Watchlist] backend-remove-failed key=${key}`, e);

      items.value = snapshot;
      saveToCache();

      alert(`删除失败：${e?.message || "网络错误"}`);
    } finally {
      loading.value = false;
    }
  }

  ensureSseSubscription();

  _singleton = {
    items: readonly(items),
    loading: readonly(loading),
    error: readonly(error),
    loadFromCache,
    refresh,
    addOne,
    removeOne,
  };

  return _singleton;
}
