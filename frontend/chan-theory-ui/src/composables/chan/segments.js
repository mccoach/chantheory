// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\segments.js
// ==============================
// 说明：元线段识别模块（Idx-Only Schema 版）
//
// ✅ 核心原则：
//   - Segment 存储只记录索引字段（idx_orig/idx_red/idx_pen）与必要布尔属性；
//   - 不存 ts/pri/y 等衍生字段（单一真相源：candles）；
//   - 不跨 seq_id（岛内独立推进）；
//
// ✅ 结构说明（按最新需求校核后实现）：
//   1) 先生成元线段序列 metaSegs（保留不变，内部使用，不对外导出）
//   2) 再基于 metaSegs 做连接/确认，生成最终线段序列 finalSegs（用于渲染）
//      finalSegs 字段 = 元线段工程字段 + internal_gap_bool + confirmed_bool
//
// ✅ 两条“剔骨刀”硬规则（显式实现）：
//   A) “完成连接”事件点（只发生在一对线段之间）：
//      - 一旦 AB 变为 A.end_idx_orig === B.start_idx_orig（天然或后处理），立刻对前段A做内部缺口判断
//      - 若 A 无内部缺口：且 AB 必为反向连接 => A 立即 confirmed
//      - 若 A 有内部缺口：A 暂不 confirmed，挂到 pendingA（长度恒为1），等待“下一次 BC 反向连接成功”
//   B) 当存在 pendingA 时：只要发生一次 “BC 反向连接成功” 事件点，第一时间立即确认 pendingA 成立，
//      然后再对 B 做内部缺口判断（该判断由“完成连接事件点”统一触发）
//
// 注：为让上述规则只在一个地方发生，本文件将“连接完成处理”封装为 onOppositeConnected(...) 事件函数。
// ==============================

import { candleH, candleL, toNonNegIntIdx } from "./common";

/**
 * 将一条笔的端点，映射为对应的“端点价”（从 candles 回溯）
 */
function penEndpointY(candles, pen, which) {
  const dir = String(pen?.dir_enum || "").toUpperCase();
  const x =
    which === "start"
      ? toNonNegIntIdx(pen?.start_idx_orig)
      : toNonNegIntIdx(pen?.end_idx_orig);
  if (x == null) return NaN;

  if (dir === "UP") return which === "start" ? candleL(candles, x) : candleH(candles, x);
  if (dir === "DOWN") return which === "start" ? candleH(candles, x) : candleL(candles, x);
  return NaN;
}

function penPriceRange(candles, pen) {
  const a = penEndpointY(candles, pen, "start");
  const b = penEndpointY(candles, pen, "end");
  if (![a, b].every((v) => Number.isFinite(v))) return null;
  return { lo: Math.min(a, b), hi: Math.max(a, b) };
}

function isStrictDisjoint(a, b) {
  return a.hi < b.lo || b.hi < a.lo;
}
function isContainOrEqual(a, b) {
  return a.lo <= b.lo && a.hi >= b.hi;
}
function classifyRangeRelation(a, b) {
  if (isStrictDisjoint(a, b)) return "disjoint";
  if (isContainOrEqual(a, b) || isContainOrEqual(b, a)) return "contain";
  return "overlap";
}

function mergeContainedFeatureRanges(a, b, segDirUp) {
  if (segDirUp) return { lo: Math.max(a.lo, b.lo), hi: Math.max(a.hi, b.hi) };
  return { lo: Math.min(a.lo, b.lo), hi: Math.min(a.hi, b.hi) };
}

function isUpSeg(seg) {
  return String(seg?.dir_enum || "").toUpperCase() === "UP";
}

function hasInternalGapByFeatureSeq({ candles, arrEntries, sIdx, eIdx, segDirUp }) {
  const start = Number(sIdx);
  const end = Number(eIdx);

  if (!Array.isArray(arrEntries) || !arrEntries.length) return false;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end < start) return false;

  const nextPenEntry = arrEntries[end + 1] || null;
  if (!nextPenEntry?.p) return false;

  const featureRanges = [];

  for (let i = start + 1; i <= end - 1; i += 2) {
    const pen = arrEntries[i]?.p;
    const r = pen ? penPriceRange(candles, pen) : null;
    if (r) featureRanges.push(r);
  }

  {
    const r = penPriceRange(candles, nextPenEntry.p);
    if (r) featureRanges.push(r);
  }

  if (featureRanges.length < 2) return false;

  const merged = [];
  for (let i = 0; i < featureRanges.length; i++) {
    const cur = featureRanges[i];
    if (!merged.length) {
      merged.push(cur);
      continue;
    }
    const last = merged[merged.length - 1];
    const rel = classifyRangeRelation(last, cur);
    if (rel === "contain") {
      merged[merged.length - 1] = mergeContainedFeatureRanges(last, cur, segDirUp);
    } else {
      merged.push(cur);
    }
  }

  if (merged.length < 2) return false;

  const a = merged[merged.length - 2];
  const b = merged[merged.length - 1];
  const finalRel = classifyRangeRelation(a, b);
  return finalRel === "disjoint";
}

function isExternallyConnected(A, B) {
  return Number(A?.end_idx_orig) === Number(B?.start_idx_orig);
}

function endpointPriceOfSegment(candles, seg, which) {
  const dir = String(seg?.dir_enum || "").toUpperCase();
  const idx =
    which === "start"
      ? toNonNegIntIdx(seg?.start_idx_orig)
      : toNonNegIntIdx(seg?.end_idx_orig);
  if (idx == null) return NaN;

  if (dir === "UP") return which === "start" ? candleL(candles, idx) : candleH(candles, idx);
  if (dir === "DOWN") return which === "start" ? candleH(candles, idx) : candleL(candles, idx);
  return NaN;
}

function isEndCreatesNewExtreme(candles, A, B) {
  const dirUp = isUpSeg(A);
  const aEnd = endpointPriceOfSegment(candles, A, "end");
  const bEnd = endpointPriceOfSegment(candles, B, "end");
  if (!Number.isFinite(aEnd) || !Number.isFinite(bEnd)) return false;
  return dirUp ? bEnd > aEnd : bEnd < aEnd;
}

function resolvePenEntryRange(seg, penIndexToLocalEntryIdx) {
  const sp = toNonNegIntIdx(seg?.start_pen_idx);
  const ep = toNonNegIntIdx(seg?.end_pen_idx);
  if (sp == null || ep == null) return null;

  const sIdx = penIndexToLocalEntryIdx.get(sp);
  const eIdx = penIndexToLocalEntryIdx.get(ep);
  if (!Number.isFinite(sIdx) || !Number.isFinite(eIdx)) return null;

  return { sIdx, eIdx };
}

function computeInternalGapBool({ candles, arrEntries, seg, penIndexToLocalEntryIdx }) {
  const rng = resolvePenEntryRange(seg, penIndexToLocalEntryIdx);
  if (!rng) return false;

  return hasInternalGapByFeatureSeq({
    candles,
    arrEntries,
    sIdx: rng.sIdx,
    eIdx: rng.eIdx,
    segDirUp: isUpSeg(seg),
  });
}

function alignOppositeSegmentsByExtreme(candles, A, B) {
  const A2 = { ...A };
  const B2 = { ...B };

  const dirUp = isUpSeg(A2);
  const aEnd = endpointPriceOfSegment(candles, A2, "end");
  const bStart = endpointPriceOfSegment(candles, B2, "start");

  if (!Number.isFinite(aEnd) || !Number.isFinite(bStart)) {
    B2.start_idx_orig = A2.end_idx_orig;
    return { A2, B2 };
  }

  const aMoreExtreme = dirUp ? aEnd > bStart : aEnd < bStart;
  if (aMoreExtreme) B2.start_idx_orig = A2.end_idx_orig;
  else A2.end_idx_orig = B2.start_idx_orig;

  return { A2, B2 };
}

// ===== 最终线段生成（事件驱动剔骨刀规则版）=====
function buildFinalSegmentsInOneSeq({ candles, arrEntries, metaSegs, penIndexToLocalEntryIdx }) {
  const finalSegs = [];
  const segs = Array.isArray(metaSegs) ? metaSegs : [];
  if (!segs.length) return finalSegs;

  function makeFinal(seg) {
    return {
      ...seg,
      internal_gap_bool: computeInternalGapBool({
        candles,
        arrEntries,
        seg,
        penIndexToLocalEntryIdx,
      }),
      confirmed_bool: false,
    };
  }
  function confirm(seg) {
    seg.confirmed_bool = true;
    return seg;
  }

  let pendingA = null;

  function onOppositeConnected(X, Y, { xEndChanged }) {
    // 若 pendingA 存在，则本次 BC 反向连接成功，先确认 pendingA（剔骨刀硬规则）
    if (pendingA) {
      confirm(pendingA);
      finalSegs.push(pendingA);
      pendingA = null;
    }

    // 完成连接 => 对前段做内部缺口判断（若终点变化则重算，否则复用）
    if (xEndChanged) {
      X.internal_gap_bool = computeInternalGapBool({
        candles,
        arrEntries,
        seg: X,
        penIndexToLocalEntryIdx,
      });
    }

    if (!X.internal_gap_bool) {
      confirm(X);
      finalSegs.push(X);
    } else {
      pendingA = X;
    }

    return Y;
  }

  let A = makeFinal(segs[0]);
  for (let i = 1; i < segs.length; i++) {
    let B = makeFinal(segs[i]);
    const opposite = isUpSeg(A) !== isUpSeg(B);

    if (opposite) {
      if (!isExternallyConnected(A, B)) {
        const aligned = alignOppositeSegmentsByExtreme(candles, A, B);
        const A2 = makeFinal(aligned.A2);
        const B2 = makeFinal(aligned.B2);

        const xEndChanged = Number(A2.end_idx_orig) !== Number(A.end_idx_orig);
        if (!isExternallyConnected(A2, B2)) {
          A = A2;
          continue;
        }
        A = onOppositeConnected(A2, B2, { xEndChanged });
      } else {
        // 天然连接：A终点未变，复用
        A = onOppositeConnected(A, B, { xEndChanged: false });
      }
      continue;
    }

    // 同向且外部缺口：创新极值合并，否则忽略
    if (isExternallyConnected(A, B)) {
      // 同向共点不应发生，兜底推进
      confirm(A);
      finalSegs.push(A);
      A = B;
      continue;
    }

    if (isEndCreatesNewExtreme(candles, A, B)) {
      const oldEnd = Number(A.end_idx_orig);
      A.end_idx_orig = B.end_idx_orig;
      A.end_idx_red = B.end_idx_red;
      A.end_pen_idx = B.end_pen_idx;

      const endChanged = Number(A.end_idx_orig) !== oldEnd;
      if (endChanged) {
        A.internal_gap_bool = computeInternalGapBool({
          candles,
          arrEntries,
          seg: A,
          penIndexToLocalEntryIdx,
        });
      }
      continue;
    }

    // ignore B
  }

  // 岛尾：最后一条最终线段自动成立（不用于兜底 pendingA）
  confirm(A);
  finalSegs.push(A);

  return finalSegs;
}

/**
 * computeSegments
 * 返回：{ metaSegments, finalSegments }
 */
export function computeSegments(candles, reducedBars, pensConfirmed) {
  const pens = Array.isArray(pensConfirmed) ? pensConfirmed : [];
  const rbs = Array.isArray(reducedBars) ? reducedBars : [];
  const metaSegments = [];
  const finalSegments = [];

  if (!candles || !candles.length || !rbs.length || !pens.length) {
    return { metaSegments, finalSegments };
  }

  // ===== 分岛 =====
  const bySeq = new Map(); // seq_id -> Array<{ p, pi }>
  for (let pi = 0; pi < pens.length; pi++) {
    const p = pens[pi];
    const sid = Number(p?.seq_id || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push({ p, pi });
  }

  function dirUpPen(p) {
    return String(p?.dir_enum || "").toUpperCase() === "UP";
  }

  function rbHighByRedIdx(redIdx) {
    const ri = toNonNegIntIdx(redIdx);
    if (ri == null || ri >= rbs.length) return NaN;
    const gi = toNonNegIntIdx(rbs[ri]?.g_idx_orig);
    if (gi == null) return NaN;
    const v = candleH(candles, gi);
    return Number.isFinite(v) ? v : NaN;
  }
  function rbLowByRedIdx(redIdx) {
    const ri = toNonNegIntIdx(redIdx);
    if (ri == null || ri >= rbs.length) return NaN;
    const di = toNonNegIntIdx(rbs[ri]?.d_idx_orig);
    if (di == null) return NaN;
    const v = candleL(candles, di);
    return Number.isFinite(v) ? v : NaN;
  }
  function penLow(p) {
    const a = rbLowByRedIdx(p?.start_idx_red);
    const b = rbLowByRedIdx(p?.end_idx_red);
    return Math.min(a, b);
  }
  function penHigh(p) {
    const a = rbHighByRedIdx(p?.start_idx_red);
    const b = rbHighByRedIdx(p?.end_idx_red);
    return Math.max(a, b);
  }

  function checkPair(pCur, pNext) {
    const l1 = penLow(pCur), h1 = penHigh(pCur);
    const l2 = penLow(pNext), h2 = penHigh(pNext);
    if (![l1, h1, l2, h2].every((x) => Number.isFinite(x))) return { ok: false };

    const overlapLow = Math.max(l1, l2);
    const overlapHigh = Math.min(h1, h2);
    const overlapOk = overlapHigh > overlapLow;

    const c1 = l1 < l2 && h1 > h2;
    const c2 = l2 < l1 && h2 > h1;
    const notContainOk = !(c1 || c2);

    let trendOk = false;
    if (dirUpPen(pCur) && dirUpPen(pNext)) trendOk = l2 > l1 && h2 > h1;
    else if (!dirUpPen(pCur) && !dirUpPen(pNext)) trendOk = h2 < h1 && l2 < l1;

    return { ok: overlapOk && notContainOk && trendOk };
  }

  for (const [sid, arrEntries] of bySeq.entries()) {
    const arr = Array.isArray(arrEntries) ? arrEntries : [];
    let s = 0;

    const metaSegs = [];

    while (s < arr.length) {
      const startEntry = arr[s];
      const startPen = startEntry?.p;
      if (!startPen) break;

      const up = dirUpPen(startPen);

      let hasSuccess = false;
      let curIdx = s;
      let lastSuccessNextIdx = -1;

      while (curIdx + 2 < arr.length) {
        const nextIdx = curIdx + 2;
        const pCur = arr[curIdx]?.p;
        const pNext = arr[nextIdx]?.p;
        if (!pCur || !pNext) break;
        if (dirUpPen(pCur) !== dirUpPen(pNext)) break;

        const evalRes = checkPair(pCur, pNext);
        if (evalRes.ok) {
          hasSuccess = true;
          lastSuccessNextIdx = nextIdx;
          curIdx = nextIdx;
        } else {
          break;
        }
      }

      if (hasSuccess && lastSuccessNextIdx >= 0) {
        const endEntry = arr[lastSuccessNextIdx];
        const endPen = endEntry?.p;
        if (!endPen) {
          s = Math.min(arr.length, s + 1);
          continue;
        }

        const start_idx_red = toNonNegIntIdx(startPen.start_idx_red);
        const end_idx_red = toNonNegIntIdx(endPen.end_idx_red);
        const start_idx_orig = toNonNegIntIdx(startPen.start_idx_orig);
        const end_idx_orig = toNonNegIntIdx(endPen.end_idx_orig);

        if (
          start_idx_red == null ||
          end_idx_red == null ||
          start_idx_orig == null ||
          end_idx_orig == null
        ) {
          s = Math.min(arr.length, s + 1);
          continue;
        }

        metaSegs.push({
          start_idx_red,
          end_idx_red,
          start_idx_orig,
          end_idx_orig,
          start_pen_idx: toNonNegIntIdx(startEntry.pi),
          end_pen_idx: toNonNegIntIdx(endEntry.pi),
          dir_enum: up ? "UP" : "DOWN",
          seq_id: Number(sid || 1),
        });

        s = lastSuccessNextIdx + 1;
      } else {
        const mid = typeof curIdx === "number" ? curIdx + 1 : s + 1;
        if (mid < arr.length) s = mid;
        else break;
      }
    }

    // 记录元线段（全局保留）
    for (const ms of metaSegs) metaSegments.push(ms);

    if (!metaSegs.length) continue;

    const penIndexToLocalEntryIdx = new Map();
    for (let li = 0; li < arr.length; li++) {
      const pi = toNonNegIntIdx(arr[li]?.pi);
      if (pi != null) penIndexToLocalEntryIdx.set(pi, li);
    }

    const finals = buildFinalSegmentsInOneSeq({
      candles,
      arrEntries: arr,
      metaSegs,
      penIndexToLocalEntryIdx,
    });

    for (const fs of finals) finalSegments.push(fs);
  }

  return { metaSegments, finalSegments };
}
