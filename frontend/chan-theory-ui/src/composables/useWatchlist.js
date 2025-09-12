// src/composables/useWatchlist.js
// ==============================
// 说明：自选池组合式
// - 状态：items, status, loading, error
// - 行为：refresh, addOne, removeOne, syncAll, syncOne
// ==============================

import { ref } from "vue"; // 响应式
import * as api from "@/services/watchlistService"; // 自选服务

export function useWatchlist() {
  // 状态
  const items = ref([]); // 自选列表
  const status = ref({}); // 同步状态快照
  const loading = ref(false); // 加载中
  const error = ref(""); // 错误信息

  // 刷新自选与状态
  async function refresh() {
    loading.value = true;
    error.value = "";
    try {
      const data = await api.list();
      items.value = data?.items || [];
      status.value = data?.status || {};
    } catch (e) {
      error.value = e?.message || "加载失败";
    } finally {
      loading.value = false;
    }
  }

  // 添加一个
  async function addOne(symbol) {
    loading.value = true;
    error.value = "";
    try {
      await api.add(symbol);
      await refresh();
    } catch (e) {
      error.value = e?.message || "添加失败";
    } finally {
      loading.value = false;
    }
  }

  // 移除一个
  async function removeOne(symbol) {
    loading.value = true;
    error.value = "";
    try {
      await api.remove(symbol);
      await refresh();
    } catch (e) {
      error.value = e?.message || "移除失败";
    } finally {
      loading.value = false;
    }
  }

  // 同步全部
  async function syncAll() {
    try {
      await api.syncAll();
    } catch {}
    // 提交后不阻塞，稍后刷新状态
    setTimeout(refresh, 800);
  }

  // 同步单个
  async function syncOne(symbol) {
    try {
      await api.syncOne(symbol);
    } catch {}
    setTimeout(refresh, 800);
  }

  return {
    items,
    status,
    loading,
    error,
    refresh,
    addOne,
    removeOne,
    syncAll,
    syncOne,
  };
}
