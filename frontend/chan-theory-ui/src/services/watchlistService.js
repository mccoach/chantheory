// src/services/watchlistService.js
// ==============================
// 说明：自选池服务 (V7.0 - URL重构版)
// 改动：
//   - URL前缀从 /api/user/watchlist 改为 /api/watchlist
//   - 与后端路由彻底对齐
// ==============================

import { api } from "@/api/client";

/**
 * 获取自选池列表
 * @returns {Promise<object>}
 */
export async function list() {
  const { data } = await api.get("/api/watchlist");
  return data;
}

/**
 * 添加一个标的到自选池
 * @param {string} symbol
 * @returns {Promise<object>}
 */
export async function add(symbol) {
  const { data } = await api.post("/api/watchlist", { symbol });
  return data;
}

/**
 * 从自选池移除一个标的
 * @param {string} symbol
 * @returns {Promise<object>}
 */
export async function remove(symbol) {
  const { data } = await api.delete(
    `/api/watchlist/${encodeURIComponent(symbol)}`
  );
  return data;
}