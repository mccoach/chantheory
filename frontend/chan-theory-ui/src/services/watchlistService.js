// src/services/watchlistService.js
// ==============================
// 说明：自选池服务，对接 /api/watchlist*
// - list(): 获取自选与状态
// - add(symbol)
// - remove(symbol)
// - syncAll()
// - syncOne(symbol)
// ==============================

import { api } from "@/api/client"; // 统一客户端

export async function list() {
  // GET /api/watchlist
  const { data } = await api.get("/api/watchlist");
  return data;
}

export async function add(symbol) {
  // POST /api/watchlist
  const { data } = await api.post("/api/watchlist", { symbol });
  return data;
}

export async function remove(symbol) {
  // DELETE /api/watchlist/{symbol}
  const { data } = await api.delete(
    `/api/watchlist/${encodeURIComponent(symbol)}`
  );
  return data;
}

export async function syncAll() {
  // POST /api/watchlist/sync
  const { data } = await api.post("/api/watchlist/sync");
  return data;
}

export async function syncOne(symbol) {
  // POST /api/watchlist/sync/{symbol}
  const { data } = await api.post(
    `/api/watchlist/sync/${encodeURIComponent(symbol)}`
  );
  return data;
}