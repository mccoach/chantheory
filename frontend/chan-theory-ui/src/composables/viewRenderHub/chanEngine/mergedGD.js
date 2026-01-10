// src/composables/viewRenderHub/chanEngine/mergedGD.js
// ==============================
// 原始K -> 合并K G/D 派生表（一次 O(N)）
// 迁移自原 useViewRenderHub 内 _buildMergedGDByOrigIdx。
// ==============================

export function buildMergedGDByOrigIdx({ candles, reducedBars, mapOrigToReduced }) {
  const list = Array.isArray(candles) ? candles : [];
  const rbs = Array.isArray(reducedBars) ? reducedBars : [];
  const map = Array.isArray(mapOrigToReduced) ? mapOrigToReduced : [];

  const n = list.length;
  const out = new Array(n);

  for (let i = 0; i < n; i++) {
    const m = map[i];
    const rIdx = m && Number.isFinite(+m.reduced_idx) ? +m.reduced_idx : null;
    const rb = rIdx != null && rIdx >= 0 && rIdx < rbs.length ? rbs[rIdx] : null;

    const gi = rb && Number.isFinite(+rb.g_idx_orig) ? +rb.g_idx_orig : null;
    const di = rb && Number.isFinite(+rb.d_idx_orig) ? +rb.d_idx_orig : null;

    const G =
      gi != null && gi >= 0 && gi < n
        ? (Number.isFinite(+list[gi]?.h) ? +list[gi].h : null)
        : null;

    const D =
      di != null && di >= 0 && di < n
        ? (Number.isFinite(+list[di]?.l) ? +list[di].l : null)
        : null;

    out[i] = { G, D };
  }

  return out;
}
