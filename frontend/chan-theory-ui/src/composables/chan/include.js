// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\include.js
// ==============================
// 说明：从 useChan.js 拆分出的包含关系处理模块
// - 核心职责：处理K线包含关系，生成合并后的K线序列（Reduced Bars）。
// - 依赖：detectContinuityBarriers（仅做原始K层面的连续性检测）。
//
// 设计原则：
//   - 本模块保持“算法 + 参数驱动”，不自行做数据访问；
//   - 上市日期 ipoYmd 由调用方（如 useViewRenderHub）基于 symbol_index 获取后，
//     通过 opts.ipoYmd 显式传入；
//   - 本模块只负责将 ipoYmd 透传给 detectContinuityBarriers，以决定在哪里拆分“连续性岛”（seq_id）。
//
// 当前策略（与既有实现保持一致）：
//   1) 对相邻两根K线（或合并K vs 原始K），先判断是否“严格上涨”或“严格下跌”：
//        - 严格上涨：H_new > H_old && L_new > L_old
//        - 严格下跌：H_new < H_old && L_new < L_old
//      若满足其一，则视作“趋势推进”，直接将新K作为一根新的合并K（仅记录HL柱+方向）。
//   2) 否则，一律视作“存在包含/重叠关系”，进入包含合并逻辑：
//        - 若当前趋势为上涨：新高=两者高点max，新低=两者低点max（高高）
//        - 若当前趋势为下跌：新高=两者高点min，新低=两者低点min（低低）
//   3) 连续性屏障仅用于划分“岛”（seq_id），不跨岛做包含合并。
//   4) 每根合并K上记录：
//        - start_idx_orig / end_idx_orig：覆盖原始K索引范围
//        - g_pri / d_pri：合并后的高/低价
//        - g_idx_orig / d_idx_orig：高/低点来源的原始索引
//        - dir_int：方向（+1/-1/0）
//        - anchor_idx_orig：承载点索引（由 anchorPolicy 决定）
//        - seq_id：所属连续性岛
//        - barrier_after_prev_bool：是否为屏障后的首根
//        - gap_enum：相对上一根合并K的跳空状态（'up' | 'down' | 'none'）
//        - start_ts / end_ts：覆盖时间区间（毫秒时间戳）
// ==============================

import { CONTINUITY_BARRIER } from "@/constants";
import { detectContinuityBarriers } from "./barriers";

export function computeInclude(candles, opts = {}) {
  const anchorPolicy = opts.anchorPolicy === "extreme" ? "extreme" : "right";
  const N = Array.isArray(candles) ? candles.length : 0;
  const reduced = [];
  const map = new Array(N);
  let lastDir = 0;

  const ipoYmd =
    typeof opts.ipoYmd === "number" && Number.isFinite(opts.ipoYmd)
      ? opts.ipoYmd
      : null;

  // ===== 连续性屏障：仅用于划分 seq_id，不跨岛合并 =====
  const { set: barrierSet } = detectContinuityBarriers(
    candles,
    CONTINUITY_BARRIER?.basePct,
    { ipoYmd }
  );

  let seq_id = 0; // 连续性岛编号（从 1 起）

  const H = (i) => Number(candles[i]?.h ?? candles[i]?.high ?? NaN);
  const L = (i) => Number(candles[i]?.l ?? candles[i]?.low ?? NaN);
  const TS = (i) => Number(candles[i]?.ts ?? NaN); // 统一使用毫秒时间戳

  // 关系判定：严格上涨(+1)、严格下跌(-1)、否则0（进入包含合并）
  function relation(a, b) {
    const up = a.g_pri < b.g_pri && a.d_pri < b.d_pri;
    const dn = a.g_pri > b.g_pri && a.d_pri > b.d_pri;
    if (up) return +1;
    if (dn) return -1;
    return 0;
  }

  // 决定当前合并K的趋势方向：
  //   - 若 a.dir_int 已有方向 → 直接沿用
  //   - 否则优先参考上一个合并K prev 与当前 a 的关系
  //   - 再否则，使用 lastDir（岛内记忆）
  //   - 最后兜底：使用 a/b 的极值重心变化决定 (+1/-1)
  function decideDirection(a, prev, b) {
    if (a.dir_int !== 0) return a.dir_int;
    if (prev) {
      const r = relation(prev, a);
      if (r !== 0) return r;
    }
    if (lastDir !== 0) return lastDir;

    // 重心兜底：仅在本岛尚未形成任何方向时才会触发
    const delta =
      (b.g_pri - a.g_pri) + (b.d_pri - a.d_pri); // 等价于比较 (H+L) 的变化
    return delta >= 0 ? +1 : -1;
  }

  function fillMapRange(s, e, reducedIndex, seqId) {
    for (let k = s; k <= e; k++) {
      map[k] = {
        reduced_idx: reducedIndex,
        role_str:
          k === reduced[reducedIndex].end_idx_orig ? "carrier" : "merged",
        seq_id: seqId,
      };
    }
  }

  // 跳空缺口计算：记录在“后一根合并K”上
  function updateGapForIndex(idx) {
    if (idx < 0 || idx >= reduced.length) return;
    const cur = reduced[idx];

    if (idx === 0) {
      // 第一根无法与前一根比较，默认不跳空
      cur.gap_enum = "none";
      return;
    }

    const prev = reduced[idx - 1];
    if (!prev) {
      cur.gap_enum = "none";
      return;
    }

    // 上跳空：前一根高点 < 当前低点
    const gapUp =
      Number.isFinite(prev.g_pri) &&
      Number.isFinite(cur.d_pri) &&
      prev.g_pri < cur.d_pri;

    // 下跳空：前一根低点 > 当前高点
    const gapDown =
      Number.isFinite(prev.d_pri) &&
      Number.isFinite(cur.g_pri) &&
      prev.d_pri > cur.g_pri;

    if (gapUp) cur.gap_enum = "up";
    else if (gapDown) cur.gap_enum = "down";
    else cur.gap_enum = "none";
  }

  for (let i = 0; i < N; i++) {
    const hi = H(i);
    const lo = L(i);
    if (!Number.isFinite(hi) || !Number.isFinite(lo)) continue;

    // 首根或屏障处开启新岛
    const openNewSeq = i === 0 || barrierSet.has(i);
    if (openNewSeq) {
      seq_id = seq_id + 1;
      lastDir = 0; // 每个岛内独立判定方向
    }

    const base = {
      start_idx_orig: i,
      end_idx_orig: i,
      g_pri: hi,
      d_pri: lo,
      dir_int: 0,
      start_ts: TS(i),
      end_ts: TS(i),
      g_idx_orig: i,
      d_idx_orig: i,
      anchor_idx_orig: i,
      reason_str: "normal",
      seq_id,
      barrier_after_prev_bool: openNewSeq && i > 0,
      gap_enum: "none",
    };

    if (reduced.length === 0 || openNewSeq) {
      // 整个序列的第一根，或新岛首根：直接作为一根独立合并K
      reduced.push(base);
      map[i] = {
        reduced_idx: reduced.length - 1,
        role_str: "carrier",
        seq_id,
      };
      updateGapForIndex(reduced.length - 1);
      continue;
    }

    const a = reduced[reduced.length - 1]; // 最新合并K
    const b = base;                        // 当前原始K
    const r = relation(a, b);

    if (r === +1 || r === -1) {
      // 严格上涨 / 严格下跌：直接追加为新合并K
      b.dir_int = r;
      lastDir = r;
      reduced.push(b);
      map[i] = {
        reduced_idx: reduced.length - 1,
        role_str: "carrier",
        seq_id,
      };
      updateGapForIndex(reduced.length - 1);
      continue;
    }

    // r===0：包含/重叠合并（仅在同一岛内合并）
    const prev = reduced.length >= 2 ? reduced[reduced.length - 2] : null;
    const trend = decideDirection(a, prev, b);
    a.dir_int = a.dir_int === 0 ? trend : a.dir_int;

    if (a.dir_int >= 0) {
      // 上涨趋势：高高 / 低高
      const prevHi = a.g_pri,
        prevLo = a.d_pri;
      const newHi = Math.max(a.g_pri, b.g_pri);
      const newLo = Math.max(a.d_pri, b.d_pri);
      a.g_pri = newHi;
      a.d_pri = newLo;

      if (newHi !== prevHi && newHi === b.g_pri) a.g_idx_orig = i;
      if (newLo !== prevLo && newLo === b.d_pri) a.d_idx_orig = i;

      a.end_idx_orig = i;
      a.end_ts = b.end_ts;
      a.reason_str = "inclusion-merge-up";
      lastDir = a.dir_int;

      a.anchor_idx_orig =
        anchorPolicy === "extreme"
          ? a.dir_int > 0
            ? a.g_idx_orig
            : a.d_idx_orig
          : a.end_idx_orig;

      fillMapRange(
        a.start_idx_orig,
        a.end_idx_orig,
        reduced.length - 1,
        a.seq_id
      );

      updateGapForIndex(reduced.length - 1);
    } else {
      // 下跌趋势：高低 / 低低
      const prevHi = a.g_pri,
        prevLo = a.d_pri;
      const newHi = Math.min(a.g_pri, b.g_pri);
      const newLo = Math.min(a.d_pri, b.d_pri);
      a.g_pri = newHi;
      a.d_pri = newLo;

      if (newHi !== prevHi && newHi === b.g_pri) a.g_idx_orig = i;
      if (newLo !== prevLo && newLo === b.d_pri) a.d_idx_orig = i;

      a.end_idx_orig = i;
      a.end_ts = b.end_ts;
      a.reason_str = "inclusion-merge-down";
      lastDir = a.dir_int;

      a.anchor_idx_orig =
        anchorPolicy === "extreme"
          ? a.dir_int < 0
            ? a.d_idx_orig
            : a.g_idx_orig
          : a.end_idx_orig;

      fillMapRange(
        a.start_idx_orig,
        a.end_idx_orig,
        reduced.length - 1,
        a.seq_id
      );

      updateGapForIndex(reduced.length - 1);
    }
  }

  // 单根映射补齐（若有）
  for (let j = 0; j < reduced.length; j++) {
    const rj = reduced[j];
    if (rj.start_idx_orig === rj.end_idx_orig) {
      map[rj.start_idx_orig] = {
        reduced_idx: j,
        role_str: "carrier",
        seq_id: rj.seq_id,
      };
    }
  }

  const meta = {
    algo: "include_v1",
    anchorPolicy,
    generated_at: new Date().toISOString(), // 元信息：不参与计算，按现状保留
  };
  return { reducedBars: reduced, mapOrigToReduced: map, meta };
}
