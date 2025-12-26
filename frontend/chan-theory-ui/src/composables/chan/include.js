// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\include.js
// ==============================
// 说明：从 useChan.js 拆分出的包含关系处理模块（Idx-Only Schema 版）
// - 核心职责：处理K线包含关系，生成合并后的K线序列（Reduced Bars）。
// - 依赖：detectContinuityBarriers（仅做原始K层面的连续性检测）。
//
// ✅ 本轮重构目标（严格执行“Idx-Only / 单一真相源”）：
//   - ReducedBar 禁止存储任何 ts / pri / reason_str / anchor_idx 等衍生字段；
//   - ReducedBar 仅保留索引字段 + 状态字段（gap_enum 允许，因其不携带价格数值）；
//   - 所有价格比较（H/L）必须回溯 candles（唯一真相源）。
//
// ReducedBar Schema（必须满足）：
//   - 覆盖范围：start_idx_orig, end_idx_orig
//   - 极值来源：g_idx_orig, d_idx_orig
//   - 状态标识：dir_int, seq_id, barrier_after_prev_bool, gap_enum
// ==============================

import { CONTINUITY_BARRIER } from "@/constants";
import { detectContinuityBarriers } from "./barriers";
import { candleH, candleL } from "./common";

export function computeInclude(candles, opts = {}) {
  const N = Array.isArray(candles) ? candles.length : 0;
  const reduced = [];
  const map = new Array(N);
  let lastDir = 0;

  // 仅透传，用于元信息；不再参与“存储字段”
  const anchorPolicy =
    opts.anchorPolicy === "extreme" || opts.anchorPolicy === "left" || opts.anchorPolicy === "right"
      ? opts.anchorPolicy
      : "right";

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

  // ===== 取 ReducedBar 的高/低（唯一真相源：candles）=====
  function rbHigh(rb) {
    if (!rb) return NaN;
    const idx = rb.g_idx_orig;
    const v = candleH(candles, idx);
    return Number.isFinite(v) ? v : NaN;
  }
  function rbLow(rb) {
    if (!rb) return NaN;
    const idx = rb.d_idx_orig;
    const v = candleL(candles, idx);
    return Number.isFinite(v) ? v : NaN;
  }

  // 关系判定：严格上涨(+1)、严格下跌(-1)、否则0（进入包含合并）
  function relation(a, b) {
    const aH = rbHigh(a);
    const aL = rbLow(a);
    const bH = rbHigh(b);
    const bL = rbLow(b);

    if (![aH, aL, bH, bL].every((x) => Number.isFinite(x))) return 0;

    const up = aH < bH && aL < bL;
    const dn = aH > bH && aL > bL;
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
    if (a && Number(a.dir_int || 0) !== 0) return Number(a.dir_int || 0);

    if (prev) {
      const r = relation(prev, a);
      if (r !== 0) return r;
    }

    if (lastDir !== 0) return lastDir;

    // 重心兜底：仅在本岛尚未形成任何方向时才会触发
    const aH = rbHigh(a);
    const aL = rbLow(a);
    const bH = rbHigh(b);
    const bL = rbLow(b);

    if (![aH, aL, bH, bL].every((x) => Number.isFinite(x))) return +1;

    const delta = (bH - aH) + (bL - aL); // 等价于比较 (H+L) 的变化
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

  // 跳空缺口计算：记录在“后一根合并K”上（只存 gap_enum，不存价格）
  function updateGapForIndex(idx) {
    if (idx < 0 || idx >= reduced.length) return;
    const cur = reduced[idx];

    if (idx === 0) {
      cur.gap_enum = "none";
      return;
    }

    const prev = reduced[idx - 1];
    if (!prev) {
      cur.gap_enum = "none";
      return;
    }

    const prevHigh = rbHigh(prev);
    const prevLow = rbLow(prev);
    const curHigh = rbHigh(cur);
    const curLow = rbLow(cur);

    if (![prevHigh, prevLow, curHigh, curLow].every((x) => Number.isFinite(x))) {
      cur.gap_enum = "none";
      return;
    }

    // 上跳空：前一根高点 < 当前低点
    const gapUp = prevHigh < curLow;

    // 下跳空：前一根低点 > 当前高点
    const gapDown = prevLow > curHigh;

    if (gapUp) cur.gap_enum = "up";
    else if (gapDown) cur.gap_enum = "down";
    else cur.gap_enum = "none";
  }

  for (let i = 0; i < N; i++) {
    const hi = candleH(candles, i);
    const lo = candleL(candles, i);
    if (!Number.isFinite(hi) || !Number.isFinite(lo)) continue;

    // 首根或屏障处开启新岛
    const openNewSeq = i === 0 || barrierSet.has(i);
    if (openNewSeq) {
      seq_id = seq_id + 1;
      lastDir = 0; // 每个岛内独立判定方向
    }

    // ===== Idx-Only ReducedBar（严禁 ts/pri/anchor/reason 等字段）=====
    const base = {
      start_idx_orig: i,
      end_idx_orig: i,
      g_idx_orig: i,
      d_idx_orig: i,
      dir_int: 0,
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
    const b = base;                        // 当前原始K（作为一个 ReducedBar 参与比较/合并）
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
    a.dir_int = Number(a.dir_int || 0) === 0 ? trend : Number(a.dir_int || 0);

    const aH = rbHigh(a);
    const aL = rbLow(a);

    if (a.dir_int >= 0) {
      // 上涨趋势：新高=max(高)，新低=max(低) —— 仅更新极值来源索引
      if (Number.isFinite(aH) && hi > aH) {
        a.g_idx_orig = i;
      }
      if (Number.isFinite(aL) && lo > aL) {
        a.d_idx_orig = i;
      }

      a.end_idx_orig = i;
      lastDir = a.dir_int;

      fillMapRange(
        a.start_idx_orig,
        a.end_idx_orig,
        reduced.length - 1,
        a.seq_id
      );

      updateGapForIndex(reduced.length - 1);
    } else {
      // 下跌趋势：新高=min(高)，新低=min(低) —— 仅更新极值来源索引
      if (Number.isFinite(aH) && hi < aH) {
        a.g_idx_orig = i;
      }
      if (Number.isFinite(aL) && lo < aL) {
        a.d_idx_orig = i;
      }

      a.end_idx_orig = i;
      lastDir = a.dir_int;

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
    anchorPolicy, // 仅作为元信息保留；ReducedBar 不再存 anchor 字段
    generated_at: new Date().toISOString(),
  };

  return { reducedBars: reduced, mapOrigToReduced: map, meta };
}
