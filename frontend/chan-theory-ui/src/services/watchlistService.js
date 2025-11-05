// src/services/watchlistService.js
// ==============================
// 说明：自选池服务 (REFACTORED)
// - 移除 `syncAll` 和 `syncOne`，因为同步由后台统一管理。
// - 路由路径更新为 `/api/user/watchlist/*`
// ==============================

import { api } from "@/api/client";

/**
 * 获取自选池列表
 * @returns {Promise<object>}
 */
export async function list() {
  const { data } = await api.get("/api/user/watchlist");
  return data;
}

/**
 * 添加一个标的到自选池
 * @param {string} symbol
 * @returns {Promise<object>}
 */
export async function add(symbol) {
  const { data } = await api.post("/api/user/watchlist", { symbol });
  return data;
}

/**
 * 从自选池移除一个标的
 * @param {string} symbol
 * @returns {Promise<object>}
 */
export async function remove(symbol) {
  const { data } = await api.delete(
    `/api/user/watchlist/${encodeURIComponent(symbol)}`
  );
  return data;
}
