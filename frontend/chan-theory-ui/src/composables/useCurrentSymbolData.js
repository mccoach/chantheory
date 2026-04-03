// src/composables/useCurrentSymbolData.js
// ==============================
// 当前标的命令中心（唯一命令权归口）
//
// 职责：
//   - 统一发起“当前标的相关”的后端准备命令
//   - 统一等待当前标的相关任务完成
//
// 明确边界：
//   - 这里只负责“命令 + 等待”
//   - 不负责设置 vm 状态
//   - 不负责调用 vm.reload()
//   - 不负责读取结果
//
// 执行层（读取/展示）应由外部显式调用：
//   - 启动链
//   - 页面交互
// ==============================

import { declareCurrentKline, declareCurrentFactors } from "@/services/ensureDataAPI";
import { waitTasksDone } from "@/composables/useTaskWaiter";
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
    force_refresh = false,
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
    const cls = String(entry?.class || "").toLowerCase();
    const isStock = cls === "stock";

    const requestAdjust = isStock ? "none" : adj;
    const shouldFetchFactors = isStock;

    const taskIds = [];

    const kTask = await declareCurrentKline({
      symbol: sym,
      freq: fr,
      adjust: requestAdjust,
      force_fetch: !!force_refresh,
    });
    if (kTask?.task_id) {
      taskIds.push(String(kTask.task_id));
    }

    if (shouldFetchFactors) {
      const fTask = await declareCurrentFactors({
        symbol: sym,
        force_fetch: !!force_refresh,
      });
      if (fTask?.task_id) {
        taskIds.push(String(fTask.task_id));
      }
    }

    if (taskIds.length) {
      await waitTasksDone({
        taskIds,
        timeoutMs: 30000,
      });
    }

    return {
      ok: true,
      symbol: sym,
      market: mk,
      freq: fr,
      adjust: adj,
      requestAdjust,
      isStock,
      shouldFetchFactors,
    };
  }

  _singleton = {
    prepare,
  };

  return _singleton;
}
