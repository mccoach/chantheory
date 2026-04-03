// src/services/watchlistService.js
// ==============================
// 说明：自选池服务（双主键最终版）
// 职责：
//   - 只做 watchlist 相关 HTTP 封装
//   - 不做状态管理
//   - 不做 UI 推导
//
// 最终契约：
//   - GET    /api/watchlist
//   - POST   /api/watchlist                 body: { symbol, market }
//   - DELETE /api/watchlist/{market}/{symbol}
//
// 约束：
//   - watchlist 唯一标识统一为 (symbol, market)
//   - 不再支持 symbol-only 旧链路
// ==============================

import { api } from "@/api/client";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function normalizeIdentity(input = {}) {
  return {
    symbol: asStr(input.symbol),
    market: asStr(input.market).toUpperCase(),
  };
}

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
 * @param {{symbol:string, market:string}} identity
 * @returns {Promise<object>}
 */
export async function add(identity) {
  const id = normalizeIdentity(identity);
  if (!id.symbol || !id.market) {
    throw new Error("[watchlistService] add requires valid symbol and market");
  }

  const { data } = await api.post("/api/watchlist", {
    symbol: id.symbol,
    market: id.market,
  });
  return data;
}

/**
 * 从自选池移除一个标的
 * @param {{symbol:string, market:string}} identity
 * @returns {Promise<object>}
 */
export async function remove(identity) {
  const id = normalizeIdentity(identity);
  if (!id.symbol || !id.market) {
    throw new Error("[watchlistService] remove requires valid symbol and market");
  }

  const { data } = await api.delete(
    `/api/watchlist/${encodeURIComponent(id.market)}/${encodeURIComponent(id.symbol)}`
  );
  return data;
}
