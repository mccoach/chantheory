// src/composables/useWatchlist.js
// ==============================
// 说明：自选池组合式 (REFACTORED)
// - 移除 `status` 和同步相关的函数 (`syncAll`, `syncOne`)，因为同步逻辑
//   已由后台 `HistoricalSyncManager` 统一管理。
// - `refresh` 函数现在只从 `/api/user/watchlist` 获取列表。
// - 采用单例模式，确保全局共享同一份自选池状态。
// ==============================

import { ref, readonly } from "vue";
import * as api from "@/services/watchlistService";

const items = ref([]);
const loading = ref(false);
const error = ref("");

let _singleton = null;

export function useWatchlist() {
  if (_singleton) return _singleton;

  async function refresh() {
    loading.value = true;
    error.value = "";
    try {
      const data = await api.list();
      items.value = data?.items || [];
    } catch (e) {
      error.value = e?.message || "加载失败";
    } finally {
      loading.value = false;
    }
  }

  async function addOne(symbol) {
    loading.value = true;
    error.value = "";
    try {
      const data = await api.add(symbol);
      items.value = data?.items || items.value;
    } catch (e) {
      error.value = e?.message || "添加失败";
      // 即使失败也刷新一次，确保与后端状态同步
      await refresh();
    } finally {
      loading.value = false;
    }
  }

  async function removeOne(symbol) {
    loading.value = true;
    error.value = "";
    try {
      const data = await api.remove(symbol);
      items.value = data?.items || items.value;
    } catch (e) {
      error.value = e?.message || "移除失败";
      await refresh();
    } finally {
      loading.value = false;
    }
  }
  
  _singleton = {
    items: readonly(items),
    loading: readonly(loading),
    error: readonly(error),
    refresh,
    addOne,
    removeOne,
  };
  
  return _singleton;
}
