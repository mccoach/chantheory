// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\include.js
// ==============================
// 说明：从 useChan.js 拆分出的包含关系处理模块
// - 核心职责：处理K线包含关系，生成合并后的K线序列（Reduced Bars）。
// - 依赖：detectContinuityBarriers
// ==============================

import { CONTINUITY_BARRIER } from "@/constants";
import { detectContinuityBarriers } from "./barriers";

export function computeInclude(candles, opts = {}) {
  const anchorPolicy = opts.anchorPolicy === "extreme" ? "extreme" : "right";
  const N = Array.isArray(candles) ? candles.length : 0;
  const reduced = [];
  const map = new Array(N);
  let lastDir = 0;

  // 按静态阈值检测原始K屏障（前10日豁免）
  const { set: barrierSet } = detectContinuityBarriers(
    candles,
    CONTINUITY_BARRIER?.basePct
  );

  let seq_id = 0; // 连续性岛编号（从 1 起）

  const H = (i) => Number(candles[i]?.h ?? candles[i]?.high ?? NaN);
  const L = (i) => Number(candles[i]?.l ?? candles[i]?.low ?? NaN);
  const T_iso = (i) => String(candles[i]?.t ?? "");

  function relation(a, b) {
    const up = a.g_pri < b.g_pri && a.d_pri < b.d_pri;
    const dn = a.g_pri > b.g_pri && a.d_pri > b.d_pri;
    if (up) return +1;
    if (dn) return -1;
    return 0;
  }
  function decideDirection(a, prev, b) {
    if (a.dir_int !== 0) return a.dir_int;
    if (prev) {
      const r = relation(prev, a);
      if (r !== 0) return r;
    }
    if (lastDir !== 0) return lastDir;
    if (a.g_pri !== b.g_pri || a.d_pri !== b.d_pri)
      return b.g_pri - a.g_pri + (b.d_pri - a.d_pri) >= 0 ? +1 : -1;
    return +1;
  }
  function fillMapRange(s, e, reducedIndex, seqId) {
    for (let k = s; k <= e; k++) {
      map[k] = {
        reduced_idx: reducedIndex,
        role_str: k === reduced[reducedIndex].end_idx_orig ? "carrier" : "merged",
        seq_id: seqId,
      };
    }
  }

  for (let i = 0; i < N; i++) {
    const hi = H(i);
    const lo = L(i);
    if (!Number.isFinite(hi) || !Number.isFinite(lo)) continue;

    // 首根或屏障处开启新岛
    const openNewSeq = i === 0 || barrierSet.has(i);
    if (openNewSeq) {
      seq_id = seq_id + 1;
      lastDir = 0;
    }

    const base = {
      start_idx_orig: i,
      end_idx_orig: i,
      g_pri: hi,
      d_pri: lo,
      dir_int: 0,
      start_t_iso: T_iso(i),
      end_t_iso: T_iso(i),
      g_idx_orig: i,
      d_idx_orig: i,
      anchor_idx_orig: i,
      reason_str: "normal",
      seq_id,
      barrier_after_prev_bool: openNewSeq && i > 0,
    };

    if (reduced.length === 0 || openNewSeq) {
      reduced.push(base);
      map[i] = { reduced_idx: reduced.length - 1, role_str: "carrier", seq_id };
      continue;
    }

    const a = reduced[reduced.length - 1];
    const b = base;
    const r = relation(a, b);

    if (r === +1 || r === -1) {
      b.dir_int = r;
      lastDir = r;
      reduced.push(b);
      map[i] = { reduced_idx: reduced.length - 1, role_str: "carrier", seq_id };
      continue;
    }

    // r===0：包含合并（不跨岛）
    const prev = reduced.length >= 2 ? reduced[reduced.length - 2] : null;
    const trend = decideDirection(a, prev, b);
    a.dir_int = a.dir_int === 0 ? trend : a.dir_int;

    if (a.dir_int >= 0) {
      const prevHi = a.g_pri, prevLo = a.d_pri;
      const newHi = Math.max(a.g_pri, b.g_pri);
      const newLo = Math.max(a.d_pri, b.d_pri);
      a.g_pri = newHi; a.d_pri = newLo;
      if (newHi !== prevHi && newHi === b.g_pri) a.g_idx_orig = i;
      if (newLo !== prevLo && newLo === b.d_pri) a.d_idx_orig = i;
      a.end_idx_orig = i; a.end_t_iso = b.end_t_iso;
      a.reason_str = "inclusion-merge-up";
      lastDir = a.dir_int;
      a.anchor_idx_orig =
        anchorPolicy === "extreme"
          ? a.dir_int > 0
            ? a.g_idx_orig
            : a.d_idx_orig
          : a.end_idx_orig;
      fillMapRange(a.start_idx_orig, a.end_idx_orig, reduced.length - 1, a.seq_id);
    } else {
      const prevHi = a.g_pri, prevLo = a.d_pri;
      const newHi = Math.min(a.g_pri, b.g_pri);
      const newLo = Math.min(a.d_pri, b.d_pri);
      a.g_pri = newHi; a.d_pri = newLo;
      if (newHi !== prevHi && newHi === b.g_pri) a.g_idx_orig = i;
      if (newLo !== prevLo && newLo === b.d_pri) a.d_idx_orig = i;
      a.end_idx_orig = i; a.end_t_iso = b.end_t_iso;
      a.reason_str = "inclusion-merge-down";
      lastDir = a.dir_int;
      a.anchor_idx_orig =
        anchorPolicy === "extreme"
          ? a.dir_int < 0
            ? a.d_idx_orig
            : a.g_idx_orig
          : a.end_idx_orig;
      fillMapRange(a.start_idx_orig, a.end_idx_orig, reduced.length - 1, a.seq_id);
    }
  }

  // 单根映射补齐（若有）
  for (let j = 0; j < reduced.length; j++) {
    const rj = reduced[j];
    if (rj.start_idx_orig === rj.end_idx_orig) {
      map[rj.start_idx_orig] = { reduced_idx: j, role_str: "carrier", seq_id: rj.seq_id };
    }
  }

  const meta = {
    algo: "include_v1",
    anchorPolicy,
    generated_at: new Date().toISOString(),
  };
  return { reducedBars: reduced, mapOrigToReduced: map, meta };
}