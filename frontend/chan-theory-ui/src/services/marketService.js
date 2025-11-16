// frontend/src/services/marketService.js
// ==============================
// 说明：行情服务（V5.0 - 纯查询版）
// 改动：
//   - 删除废弃参数（adjust/window_preset/bars/anchor_ts/include/ma_periods）
//   - 简化参数白名单（仅保留 code/freq）
//   - 保留 signal 支持（请求取消）
// ==============================

import { api } from "@/api/client"; // 统一 axios 客户端（含 trace_id 拦截）

/**
 * 查询K线数据（纯查询，不触发拉取，不计算指标）
 * 
 * @param {string} symbol - 标的代码
 * @param {string} freq - 频率（1m|5m|15m|30m|60m|1d|1w|1M）
 * @param {Object} options - 可选参数 {signal?: AbortSignal}
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
  // 构造查询参数（仅保留后端支持的参数）
  const search = new URLSearchParams();
  search.set('code', symbol);
  search.set('freq', freq);

  if (import.meta.env?.DEV) {
    console.log(
      `[${Date.now()}][marketService] GET /api/candles?${search.toString()}`
    );
  }

  // ===== 增强日志 =====
  console.log('[MarketService] 📤 发送请求', {
    symbol,
    freq,
    url: `/api/candles?${search.toString()}`
  });

  // 发起请求（支持 AbortController.signal）
  const { data } = await api.get(`/api/candles?${search.toString()}`, {
    timeout: 15000,
    meta: options.signal ? { signal: options.signal } : undefined,
  });
  
  // ===== 新增：诊断日志 =====
  console.log('[MarketService] 后端返回样本:', {
    meta: data.meta,
    sample_candle: data.candles?.[0],
    total: data.candles?.length
  });
  
  // ===== 增强日志：详细对比 =====
  console.log('[MarketService] 📥 收到响应', {
    请求的频率: freq,                    // ← 前端发送的
    后端返回的频率: data.meta?.freq,    // ← 后端返回的
    后端返回的数据源: data.meta?.source, // ← 后端返回的
    后端返回的行数: data.candles?.length, // ← 实际数据量
    meta完整信息: data.meta,
  });
  
  // ===== 数据一致性检查 =====
  if (data.meta?.freq !== freq) {
    console.error('[MarketService] ⚠️ 频率不匹配！', {
      前端请求: freq,
      后端返回: data.meta?.freq
    });
  }
  
  return data;
}