// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\segments.js
// ==============================
// 说明：元线段识别模块（Idx-Only Schema 版）
//
// ✅ 核心原则：
//   - Segment 存储只记录索引字段（idx_orig/idx_red/idx_pen）与必要布尔属性；
//   - 不存 ts/pri/y 等衍生字段（单一真相源：candles）；
//   - 不跨 seq_id（岛内独立推进）；
//
// ✅ 结构说明：
//   1) 生成元线段序列 metaSegs
//   2) 基于 metaSegs 做连接/确认，生成最终线段 finalSegs（internal_gap_bool/confirmed_bool）
//
// 本轮改动（第三阶段）：
//   - 将 reducedBars 端点价域回溯（原 rbHighByRedIdx/rbLowByRedIdx/penHigh/penLow）迁移到 chan/accessors.js
//   - 进一步消除 segments.js 内部价格回溯细节，使其聚焦“线段识别规则”
// ==============================

import { toNonNegIntIdx } from "./common";
import { createChanAccessors } from "./accessors";

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

function hasInternalGapByFeatureSeq({
  candles,
  acc,
  arrEntries,
  sIdx,
  eIdx,
  segDirUp,
}) {
  const start = Number(sIdx);
  const end = Number(eIdx);

  if (!Array.isArray(arrEntries) || !arrEntries.length) return false;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end < start)
    return false;

  const nextPenEntry = arrEntries[end + 1] || null;
  if (!nextPenEntry?.p) return false;

  const featureRanges = [];

  for (let i = start + 1; i <= end - 1; i += 2) {
    const pen = arrEntries[i]?.p;
    const r = pen ? acc.penRange(pen) : null;
    if (r) featureRanges.push(r);
  }

  {
    const r = acc.penRange(nextPenEntry.p);
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

function isEndCreatesNewExtreme(acc, A, B) {
  const dirUp = isUpSeg(A);
  const aEnd = acc.segmentEndpointY(A, "end");
  const bEnd = acc.segmentEndpointY(B, "end");
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

function computeInternalGapBool({
  candles,
  acc,
  arrEntries,
  seg,
  penIndexToLocalEntryIdx,
}) {
  const rng = resolvePenEntryRange(seg, penIndexToLocalEntryIdx);
  if (!rng) return false;

  return hasInternalGapByFeatureSeq({
    candles,
    acc,
    arrEntries,
    sIdx: rng.sIdx,
    eIdx: rng.eIdx,
    segDirUp: isUpSeg(seg),
  });
}

function alignOppositeSegmentsByExtreme(acc, A, B) {
  const A2 = { ...A };
  const B2 = { ...B };

  const aEndIdx = toNonNegIntIdx(A2.end_idx_orig);
  const bStartIdx = toNonNegIntIdx(B2.start_idx_orig);

  // 兜底：无法读取端点 idx 时，仍按原逻辑强制共点（用 A.end）
  if (aEndIdx == null || bStartIdx == null) {
    B2.start_idx_orig = A2.end_idx_orig;
    return { A2, B2 };
  }

  const dirUp = isUpSeg(A2);

  // 反向且存在外部缺口时，连接点取闭区间 [A.end, B.start] 内的极值点
  const pivotIdx = acc.findExtremeIdxInClosedRange({
    leftIdxOrig: aEndIdx,
    rightIdxOrig: bStartIdx,
    dirUp,
  });

  if (pivotIdx == null) {
    // 兜底：无法找到极值点，退回到原先“端点二选一”逻辑
    const aEnd = acc.segmentEndpointY(A2, "end");
    const bStart = acc.segmentEndpointY(B2, "start");

    if (!Number.isFinite(aEnd) || !Number.isFinite(bStart)) {
      B2.start_idx_orig = A2.end_idx_orig;
      return { A2, B2 };
    }

    const aMoreExtreme = dirUp ? aEnd > bStart : aEnd < bStart;
    if (aMoreExtreme) B2.start_idx_orig = A2.end_idx_orig;
    else A2.end_idx_orig = B2.start_idx_orig;

    return { A2, B2 };
  }

  // 将前段终点与后段起点都对齐到 pivotIdx，使转折发生在区间极值点
  A2.end_idx_orig = pivotIdx;
  B2.start_idx_orig = pivotIdx;

  return { A2, B2 };
}

// ===== 最终线段生成（事件驱动剔骨刀规则版）=====
function buildFinalSegmentsInOneSeq({
  candles,
  acc,
  arrEntries,
  metaSegs,
  penIndexToLocalEntryIdx,
}) {
  const finalSegs = [];
  const segs = Array.isArray(metaSegs) ? metaSegs : [];
  if (!segs.length) return finalSegs;

  function makeFinal(seg) {
    return {
      ...seg,
      internal_gap_bool: computeInternalGapBool({
        candles,
        acc,
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
        acc,
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
        const aligned = alignOppositeSegmentsByExtreme(acc, A, B);
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

    if (isEndCreatesNewExtreme(acc, A, B)) {
      const oldEnd = Number(A.end_idx_orig);
      A.end_idx_orig = B.end_idx_orig;
      A.end_idx_red = B.end_idx_red;
      A.end_pen_idx = B.end_pen_idx;

      const endChanged = Number(A.end_idx_orig) !== oldEnd;
      if (endChanged) {
        A.internal_gap_bool = computeInternalGapBool({
          candles,
          acc,
          arrEntries,
          seg: A,
          penIndexToLocalEntryIdx,
        });
      }
      continue;
    }

    // ignore B
  }

  // 岛尾：最后一条元线段自动成立
  // FIX: 若存在 pendingA（最多一条），在岛尾无法再通过“下一次反向连接事件”触发确认，
  //      因此在收尾阶段直接确认并入列，避免漏段。
  if (pendingA) {
    confirm(pendingA);
    finalSegs.push(pendingA);
    pendingA = null;
  }

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

  const acc = createChanAccessors(candles);

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

  // 使用 accessors 统一“单笔价域”计算：按笔的 start/end_idx_red -> reducedBar 的极值价域组合
  function penRangeByReducedExtremes(p) {
    const s = toNonNegIntIdx(p?.start_idx_red);
    const e = toNonNegIntIdx(p?.end_idx_red);
    if (s == null || e == null || s < 0 || e < 0 || s >= rbs.length || e >= rbs.length) return null;

    const rs = acc.reducedBarRangeByExtreme(rbs[s]);
    const re = acc.reducedBarRangeByExtreme(rbs[e]);
    if (!rs || !re) return null;

    return {
      lo: Math.min(rs.lo, re.lo),
      hi: Math.max(rs.hi, re.hi),
    };
  }

  function checkPair(pCur, pNext) {
    const r1 = penRangeByReducedExtremes(pCur);
    const r2 = penRangeByReducedExtremes(pNext);
    if (!r1 || !r2) return { ok: false };

    const l1 = r1.lo, h1 = r1.hi;
    const l2 = r2.lo, h2 = r2.hi;

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
      acc,
      arrEntries: arr,
      metaSegs,
      penIndexToLocalEntryIdx,
    });

    for (const fs of finals) finalSegments.push(fs);
  }

  return { metaSegments, finalSegments };
}
