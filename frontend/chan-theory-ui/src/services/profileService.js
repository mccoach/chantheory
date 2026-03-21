// src/services/profileService.js
// ==============================
// 说明：标的档案快照读取服务
//
// 职责：
//   - 只做本地 profile 快照读取
//   - 不做任务声明
//   - 不做等待逻辑
//
// 新契约：
//   GET /api/profile/current?symbol=xxx&market=XXX
// ==============================

import { api } from "@/api/client";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

/**
 * 读取单一标的档案快照（只读）
 *
 * @param {string} symbol
 * @param {string} market
 * @returns {Promise<object|null>}
 */
export async function fetchProfile(symbol, market) {
  const sym = asStr(symbol);
  const mk = asStr(market).toUpperCase();

  if (!sym || !mk) {
    throw new Error(
      `[profileService] fetchProfile 需要有效的 symbol/market，当前 symbol=${symbol}, market=${market}`
    );
  }

  const params = new URLSearchParams();
  params.set("symbol", sym);
  params.set("market", mk);

  const { data } = await api.get(`/api/profile/current?${params.toString()}`);
  return data?.item ?? null;
}
