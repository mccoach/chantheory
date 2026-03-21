// frontend/src/services/ensureDataAPI.js
// ==============================
// V8.0 - CHANGED: index/profile 固定语义导入任务 + 保留其它旧任务声明
//
// 职责：
//   - symbol_index / profile_snapshot：固定语义最小请求体
//   - 其它尚未改造完成的任务：暂继续使用 declareTask 旧壳
//
// 说明：
//   - 本文件只负责 HTTP 声明，不做等待、不做状态管理
//   - current_profile 旧路径已彻底删除
// ==============================

import { api } from "@/api/client";

/**
 * 旧通用壳任务声明（仅供尚未完成契约改造的任务继续使用）
 *
 * @param {Object} payload
 * @param {string} payload.type
 * @param {string} payload.scope
 * @param {string|null} [payload.symbol]
 * @param {string|null} [payload.freq]
 * @param {string} [payload.adjust='none']
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
 * 固定语义最小请求体任务声明
 *
 * @param {string} type
 * @returns {Promise<{ok:boolean, task_id:string, message:string, trace_id:string|null}>}
 */
async function declareFixedTypeTask(type) {
  const body = {
    type: String(type || "").trim(),
  };

  const { data } = await api.post("/api/ensure-data", body);
  return data;
}

/**
 * trade_calendar（旧链路暂保留）
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
 * symbol_index 集中导入（固定语义）
 * 请求体：
 *   { "type": "symbol_index" }
 */
export async function declareSymbolIndex() {
  return declareFixedTypeTask("symbol_index");
}

/**
 * profile 集中导入（固定语义）
 * 请求体：
 *   { "type": "profile_snapshot" }
 */
export async function declareProfileSnapshot() {
  return declareFixedTypeTask("profile_snapshot");
}

/**
 * current_kline（旧链路暂保留）
 *
 * @param {Object} options
 * @param {string} options.symbol
 * @param {string} options.freq
 * @param {string} [options.adjust='none']
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
 * current_factors（旧链路暂保留）
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
 * 盘后批量入队
 *
 * @param {object} payload
 * @returns {Promise<object>}
 */
export async function declareEnsureDataBulk(payload) {
  const body = payload && typeof payload === "object" ? payload : {};
  const { data } = await api.post("/api/ensure-data/bulk", body);
  return data;
}
