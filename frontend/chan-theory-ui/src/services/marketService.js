// src/services/marketService.js
// ==============================
// 说明：行情服务（V5.2 - 增加 adjust 透传版 + 精简日志）
// ==============================

import { api } from "@/api/client"; // 统一 axios 客户端（含 trace_id 拦截）

/**
 * 查询K线数据（纯查询，不触发拉取，不计算指标）
 *
 * @param {string} symbol - 标的代码
 * @param {string} freq   - 频率（1m|5m|15m|30m|60m|1d|1w|1M）
 * @param {Object} options - 可选参数 { signal?: AbortSignal, adjust?: 'none'|'qfq'|'hfq' }
 * @returns {Promise<Object>} {ok, meta, candles}
 *
 * 响应格式：
 * {
 *   "ok": true,
 *   "meta": {
 *     "symbol": "600519",
 *     "freq": "1d",
 *     "all_rows": 5794,
 *     "is_latest": true,
 *     "latest_bar_time": "2025-11-05 15:00:00",
 *     "source": "akshare.get_stock_bars",
 *     "generated_at": "2025-11-05T15:00:05+08:00"
 *   },
 *   "candles": [
 *     {"ts": 1730444400000, "o": 1850.5, "h": 1865.0, "l": 1840.0, "c": 1855.2, "v": 12500000},
 *     ...
 *   ]
 * }
 */
export async function fetchCandles(symbol, freq, options = {}) {
  const search = new URLSearchParams();
  search.set("code", symbol);
  search.set("freq", freq);

  // 若上层提供了复权类型（none/qfq/hfq），透传给后端，以便后端选择正确的数据源（尤其是基金）。
  const adj = options.adjust;
  if (typeof adj === "string" && adj) {
    search.set("adjust", adj);
  }

  const { data } = await api.get(`/api/candles?${search.toString()}`, {
    timeout: 60000,
    meta: options.signal ? { signal: options.signal } : undefined,
  });

  if (data.meta?.freq !== freq) {
    console.error("[MarketService] freq-mismatch", {
      requested: freq,
      returned: data.meta?.freq,
    });
  }

  return data;
}