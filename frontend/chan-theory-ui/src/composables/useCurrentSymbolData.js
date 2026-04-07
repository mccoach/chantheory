// src/composables/useCurrentSymbolData.js
// ==============================
// 当前标的命令中心（最终收口版）
//
// 职责：
//   - 当前链路只负责确保 symbol_index 可读
//   - 不再声明 current_kline
//   - 不再声明 current_factors
//   - 不再等待任何当前行情任务
//
// 原因：
//   - /api/candles 已成为单标的行情唯一正式入口
//   - 后端会在 /api/candles 内部完成数据保障、补缺、复权和成品返回
// ==============================

import { useSymbolIndex } from "@/composables/useSymbolIndex";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function asMarket(x) {
  return asStr(x).toUpperCase();
}

let _singleton = null;

export function useCurrentSymbolData() {
  if (_singleton) return _singleton;

  const symbolIndex = useSymbolIndex();

  async function prepare({
    symbol,
    market,
    freq,
    adjust = "none",
  } = {}) {
    const sym = asStr(symbol);
    const mk = asMarket(market);
    const fr = asStr(freq);
    const adj = asStr(adjust || "none") || "none";

    if (!sym || !mk || !fr) {
      throw new Error("[useCurrentSymbolData] symbol/market/freq is required");
    }

    const idxReadable = await symbolIndex.waitReadable({ timeoutMs: 60000 });
    if (!idxReadable?.ok) {
      throw new Error(idxReadable?.message || "symbol_index still importing");
    }

    const entry = symbolIndex.findBySymbol(sym, mk);
    if (!entry) {
      throw new Error(
        `[useCurrentSymbolData] symbol not found in symbol_index: market=${mk}, symbol=${sym}`
      );
    }

    return {
      ok: true,
      symbol: sym,
      market: mk,
      freq: fr,
      adjust: adj,
    };
  }

  _singleton = {
    prepare,
  };

  return _singleton;
}
