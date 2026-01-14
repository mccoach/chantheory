// frontend/src/services/ensureDataAPI.js
// ==============================
// V5.0 - Task/Job 契约适配版（单 Task 请求）
//
// 职责：
//   - 为 /api/ensure-data 提供薄封装（每次请求 = 一个 Task）；
//   - 不做任何业务编排，只负责声明 Task 并返回响应；
//   - 具体等待逻辑由 waitTasksDone（composables/useTaskWaiter.js）负责。
// ==============================

import { api } from "@/api/client";

/**
 * 底层声明函数：向 /api/ensure-data 发送一个 Task
 *
 * @param {Object} payload
 * @param {string} payload.type   - 任务类型，如 'current_kline'
 * @param {string} payload.scope  - 'global' | 'symbol'
 * @param {string|null} [payload.symbol]
 * @param {string|null} [payload.freq]
 * @param {string} [payload.adjust='none'] - 'none' | 'qfq' | 'hfq'
 * @param {Object} [payload.params]
 * @returns {Promise<{ok:boolean, task_id:string, message:string, trace_id:string|null}>}
 */
async function declareTask(payload) {
  const body = {
    type: String(payload.type || "").trim(),
    scope: String(payload.scope || "").trim(),
    symbol:
      payload.symbol == null || payload.symbol === ""
        ? null
        : String(payload.symbol).trim(),
    freq:
      payload.freq == null || payload.freq === ""
        ? null
        : String(payload.freq).trim(),
    adjust: payload.adjust || "none",
    params: {
      force_fetch: !!payload.params?.force_fetch,
      start_date:
        payload.params && payload.params.start_date != null
          ? payload.params.start_date
          : null,
      end_date:
        payload.params && payload.params.end_date != null
          ? payload.params.end_date
          : null,
    },
  };

  const { data } = await api.post("/api/ensure-data", body);
  return data;
}

/**
 * 声明：同步交易日历（trade_calendar）
 *
 * @param {{force_fetch?:boolean}} [options]
 */
export async function declareTradeCalendar(options = {}) {
  const force = !!options.force_fetch;

  return declareTask({
    type: "trade_calendar",
    scope: "global",
    symbol: null,
    freq: null,
    adjust: "none",
    params: {
      force_fetch: force,
    },
  });
}

/**
 * 声明：同步标的列表（symbol_index）
 *
 * @param {{force_fetch?:boolean}} [options]
 */
export async function declareSymbolIndex(options = {}) {
  const force = !!options.force_fetch;

  return declareTask({
    type: "symbol_index",
    scope: "global",
    symbol: null,
    freq: null,
    adjust: "none",
    params: {
      force_fetch: force,
    },
  });
}

/**
 * 声明：同步当前标的的 K 线（current_kline）
 *
 * @param {Object} options
 * @param {string} options.symbol   - 标的代码
 * @param {string} options.freq     - 频率（1m|5m|15m|30m|60m|1d|1w|1M）
 * @param {string} [options.adjust] - 'none' | 'qfq' | 'hfq'
 * @param {boolean} [options.force_fetch]
 */
export async function declareCurrentKline({
  symbol,
  freq,
  adjust = "none",
  force_fetch = false,
}) {
  if (!symbol || !freq) {
    throw new Error(
      `[ensureDataAPI] declareCurrentKline 需要有效的 symbol/freq，当前 symbol=${symbol}, freq=${freq}`
    );
  }

  return declareTask({
    type: "current_kline",
    scope: "symbol",
    symbol,
    freq,
    adjust,
    params: {
      force_fetch: !!force_fetch,
    },
  });
}

/**
 * 声明：同步当前标的的复权因子（current_factors）
 *
 * @param {Object} options
 * @param {string} options.symbol
 * @param {boolean} [options.force_fetch]
 */
export async function declareCurrentFactors({ symbol, force_fetch = false }) {
  if (!symbol) {
    throw new Error(
      `[ensureDataAPI] declareCurrentFactors 需要有效的 symbol，当前 symbol=${symbol}`
    );
  }

  return declareTask({
    type: "current_factors",
    scope: "symbol",
    symbol,
    freq: null,
    adjust: "none",
    params: {
      force_fetch: !!force_fetch,
    },
  });
}

/**
 * 声明：同步当前标的档案信息（current_profile）
 *
 * @param {Object} options
 * @param {string} options.symbol
 * @param {boolean} [options.force_fetch]
 */
export async function declareCurrentProfile({ symbol, force_fetch = false }) {
  if (!symbol) {
    throw new Error(
      `[ensureDataAPI] declareCurrentProfile 需要有效的 symbol，当前 symbol=${symbol}`
    );
  }

  return declareTask({
    type: "current_profile",
    scope: "symbol",
    symbol,
    freq: null,
    adjust: "none",
    params: {
      force_fetch: !!force_fetch,
    },
  });
}

/**
 * NEW: 批量入队（盘后批量任务契约）
 * - POST /api/ensure-data/bulk
 * - 本函数只做薄封装：不做分片/不做等待/不做重试（这些属于业务层，如 DataDownloadDialog）
 *
 * @param {object} payload
 * @returns {Promise<object>} - 后端 bulk 响应体（opaque，前端仅按契约字段读取）
 */
export async function declareEnsureDataBulk(payload) {
  const body = payload && typeof payload === "object" ? payload : {};

  const { data } = await api.post("/api/ensure-data/bulk", body);
  return data;
}
