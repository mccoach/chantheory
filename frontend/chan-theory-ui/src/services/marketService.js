// src/services/marketService.js
// ==============================
// 说明：行情服务（最终入口版）
// 职责：
//   - 只负责向 /api/candles 请求最终行情结果
//   - 参数显式包含 market / code / freq / adjust / refresh_interval_seconds
//   - 不做复权、不做重采样、不做因子相关逻辑
//
// 本轮修复：
//   - 静态查看时传 0（而不是 "null" 字符串）
//   - 自动刷新时传 >=1 的整数秒数
//   - 始终显式传 refresh_interval_seconds，避免后端猜测
// ==============================

import { api } from "@/api/client";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function asMarket(x) {
  return asStr(x).toUpperCase();
}

function normalizeRefreshInterval(v) {
  if (v == null || v === "") return 0;
  const n = Number(v);
  if (!Number.isFinite(n)) return 0;
  const i = Math.floor(n);
  return i >= 1 ? i : 0;
}

/**
 * 查询K线数据（后端最终结果，唯一正式入口）
 *
 * @param {string} symbol - 标的代码
 * @param {string} market - 市场代码（SH/SZ/BJ）
 * @param {string} freq   - 频率（1m|5m|15m|30m|60m|1d|1w|1M）
 * @param {Object} options - 可选参数
 * @param {AbortSignal} [options.signal]
 * @param {'none'|'qfq'|'hfq'} [options.adjust='none']
 * @param {number|null} [options.refreshIntervalSeconds=0]
 * @returns {Promise<Object>} {ok, meta, candles}
 */
export async function fetchCandles(symbol, market, freq, options = {}) {
  const code = asStr(symbol);
  const mk = asMarket(market);
  const fr = asStr(freq);
  const adjust = asStr(options.adjust || "none") || "none";
  const refreshIntervalSeconds = normalizeRefreshInterval(
    options.refreshIntervalSeconds
  );

  if (!code || !mk || !fr) {
    throw new Error(
      `[MarketService] fetchCandles requires valid symbol/market/freq, got symbol=${symbol}, market=${market}, freq=${freq}`
    );
  }

  const search = new URLSearchParams();
  search.set("code", code);
  search.set("market", mk);
  search.set("freq", fr);
  search.set("adjust", adjust);

  // 始终显式传递：
  // 0  = 静态查看
  // >=1 = 自动刷新周期（秒）
  search.set("refresh_interval_seconds", String(refreshIntervalSeconds));

  const { data } = await api.get(`/api/candles?${search.toString()}`, {
    timeout: 60000,
    meta: options.signal ? { signal: options.signal } : undefined,
  });

  if (data?.meta?.freq && String(data.meta.freq) !== fr) {
    console.error("[MarketService] freq-mismatch", {
      requested: fr,
      returned: data.meta?.freq,
    });
  }

  return data;
}
