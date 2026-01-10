// src/composables/viewRenderHub/chanEngine/chanCache.js
// ==============================
// Chan 结构编排与缓存（includeMemo + derivedMemo）
// 迁移自原 useViewRenderHub：_calculateChanStructures 及 key/memo 逻辑。
// 重要：此模块不持有单例；由 index 的 state/pipeline 创建一次并复用。
// ==============================

import {
  computeInclude,
  computeFractals,
  computeFractalConfirmPairs,
  computePens,
  computeSegments,
  computePenPivots,
} from "@/composables/chan";
import { CHAN_DEFAULTS } from "@/constants";

export function createChanCacheEngine({ settings, symbolIndex }) {
  const includeMemo = { key: null, value: null };
  const derivedMemo = { key: null, value: null };

  function makeCandlesKey(candles) {
    const arr = Array.isArray(candles) ? candles : [];
    const len = arr.length;
    if (!len) return "0";
    const first = arr[0]?.ts;
    const last = arr[len - 1]?.ts;
    return `${len}|${first}|${last}`;
  }

  function makeIncludeKey({ candlesKey, anchorPolicy, ipoYmd }) {
    return `${candlesKey}|ap=${anchorPolicy}|ipo=${ipoYmd ?? "null"}`;
  }

  function makeDerivedKey({ includeKey, frMinTick, frMinPct, frMinCond }) {
    return `${includeKey}|tick=${frMinTick}|pct=${frMinPct}|cond=${frMinCond}`;
  }

  function resolveSymbolMetaForCurrent(_candles) {
    let sym = "";
    try {
      sym = String(settings?.preferences?.lastSymbol || "").trim();
    } catch {
      sym = "";
    }
    if (!sym) return { symbol: "", ipoYmd: null };

    let ipoYmd = null;
    try {
      const entry = symbolIndex.findBySymbol(sym);
      if (entry) {
        const raw = entry.listingDate != null ? entry.listingDate : entry.listing_date;
        if (raw != null) {
          const n = Number(raw);
          if (Number.isFinite(n) && n > 19000000 && n < 30000000) ipoYmd = n;
        }
      }
    } catch {}

    return { symbol: sym, ipoYmd };
  }

  function emptyChanStruct() {
    return {
      reduced: [],
      map: [],
      meta: null,
      fractals: [],
      fractalConfirmPairs: { pairs: [], paired: [], role: [] },
      pens: { confirmed: [] },
      metaSegments: [],
      finalSegments: [],
      barriersIndices: [],
      pivots: [],
    };
  }

  function calculateChanStructures(candles) {
    if (!candles || !candles.length) {
      includeMemo.key = null;
      includeMemo.value = null;
      derivedMemo.key = null;
      derivedMemo.value = null;
      return emptyChanStruct();
    }

    const { ipoYmd } = resolveSymbolMetaForCurrent(candles);

    const anchorPolicy =
      settings.chanTheory.chanSettings.anchorPolicy || CHAN_DEFAULTS.anchorPolicy;

    const frMinTick = settings.chanTheory.fractalSettings.minTickCount || 0;
    const frMinPct = settings.chanTheory.fractalSettings.minPct || 0;
    const frMinCond = String(settings.chanTheory.fractalSettings.minCond || "or");

    const candlesKey = makeCandlesKey(candles);

    // ===== L1 include memo =====
    const includeKey = makeIncludeKey({ candlesKey, anchorPolicy, ipoYmd });

    let includeRes = null;
    if (includeMemo.key === includeKey && includeMemo.value) {
      includeRes = includeMemo.value;
    } else {
      includeRes = computeInclude(candles, { anchorPolicy, ipoYmd });

      includeMemo.key = includeKey;
      includeMemo.value = includeRes;

      // include 变更会导致 derived 全部失效（最简清理）
      derivedMemo.key = null;
      derivedMemo.value = null;
    }

    const reducedBars = includeRes?.reducedBars || [];
    const mapOrigToReduced = includeRes?.mapOrigToReduced || [];
    const meta = includeRes?.meta || null;

    // ===== L2 derived memo =====
    const derivedKey = makeDerivedKey({
      includeKey,
      frMinTick,
      frMinPct,
      frMinCond,
    });

    if (derivedMemo.key === derivedKey && derivedMemo.value) {
      const v = derivedMemo.value;
      return {
        reduced: reducedBars,
        map: mapOrigToReduced,
        meta,

        fractals: v.fractals,
        fractalConfirmPairs: v.fractalConfirmPairs,
        pens: v.pens,
        metaSegments: v.metaSegments,
        finalSegments: v.finalSegments,
        barriersIndices: v.barriersIndices,
        pivots: v.pivots,
      };
    }

    const fr = computeFractals(candles, reducedBars, {
      minTickCount: frMinTick,
      minPct: frMinPct,
      minCond: frMinCond,
    });

    const frConfirm = computeFractalConfirmPairs(candles, reducedBars, fr || []);

    const pens = computePens(
      candles,
      reducedBars,
      fr || [],
      mapOrigToReduced || [],
      { minGapReduced: 4 }
    );

    const segRes = computeSegments(candles, reducedBars, pens.confirmed || []);
    const metaSegments = Array.isArray(segRes?.metaSegments) ? segRes.metaSegments : [];
    const finalSegments = Array.isArray(segRes?.finalSegments) ? segRes.finalSegments : [];

    const barrierIdxList = (reducedBars || []).reduce((acc, cur, i, arr) => {
      if (cur && cur.barrier_after_prev_bool) {
        const prev = i > 0 ? arr[i - 1] : null;
        if (prev) acc.push(prev.end_idx_orig);
        acc.push(cur.start_idx_orig);
      }
      return acc;
    }, []);

    const pivots = computePenPivots(candles, pens.confirmed || []);

    derivedMemo.key = derivedKey;
    derivedMemo.value = {
      fractals: fr,
      fractalConfirmPairs: frConfirm,
      pens,
      metaSegments,
      finalSegments,
      barriersIndices: barrierIdxList,
      pivots,
    };

    return {
      reduced: reducedBars,
      map: mapOrigToReduced,
      meta,

      fractals: fr,
      fractalConfirmPairs: frConfirm,
      pens,
      metaSegments,
      finalSegments,
      barriersIndices: barrierIdxList,
      pivots,
    };
  }

  return { calculateChanStructures };
}
