// src/services/candlesCacheService.js
// ==============================
// 行情缓存释放服务（HTTP 访问层）
// 职责：
//   - 只做 /api/candles/cache/release 的调用封装
//   - 不做状态管理
//   - 不做业务推导
// ==============================

import { api } from "@/api/client";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function asMarket(x) {
  return asStr(x).toUpperCase();
}

/**
 * 释放某标的某请求频率的后端运行时缓存
 *
 * @param {object} payload
 * @param {string} payload.market
 * @param {string} payload.code
 * @param {string} payload.freq
 * @returns {Promise<{ok:boolean,released:boolean,message:string}>}
 */
export async function releaseCandlesCache({ market, code, freq } = {}) {
  const mk = asMarket(market);
  const cd = asStr(code);
  const fr = asStr(freq);

  if (!mk || !cd || !fr) {
    throw new Error(
      `[candlesCacheService] releaseCandlesCache requires valid market/code/freq, got market=${market}, code=${code}, freq=${freq}`
    );
  }

  const { data } = await api.post("/api/candles/cache/release", {
    market: mk,
    code: cd,
    freq: fr,
  });

  return {
    ok: data?.ok === true,
    released: data?.released === true,
    message: asStr(data?.message),
  };
}
