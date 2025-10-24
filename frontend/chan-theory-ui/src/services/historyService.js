// src/services/historyService.js
// ==============================
// 说明：用户历史记录服务，对接 /api/user/history*
// - add({symbol,freq})
// - list({limit})
// - clear()
// ==============================

import { api } from "@/api/client";

export async function add({ symbol, freq }) {
  const { data } = await api.post("/api/user/history", { symbol, freq });
  return data;
}

export async function list({ limit = 50 } = {}) {
  const { data } = await api.get(`/api/user/history?limit=${Math.max(1, limit)}`);
  return data;
}

export async function clear() {
  const { data } = await api.delete("/api/user/history");
  return data;
}