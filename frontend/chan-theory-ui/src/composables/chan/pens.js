// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\pens.js
// ==============================
// 说明：笔识别模块（Idx-Only Schema 版）
//
// 阶段1（已完成）：新增“K2整体升降”兜底筛选（严格不等，基于合并K区间）
//   - 不替代原有条件：排他/净距/方向/首尾相连/同类更极值 仍为硬条件
//   - 仅在排他通过且净距通过后，作为落笔前最后门槛
//
// 阶段2（已完成）：任务调度机制改造（选A + 策略C）
//   - 候选点搜索永远向右（怎么找）：扫描 seqArr（按 k2_idx_red 排序）向右推进
//   - 向左回溯是任务切换（做什么）：当发现“起点需要修正（fix=start / 同类更极值）”时，立即切换到更左一笔
//   - 选A：一旦触发更左任务，立即截断到更左笔（右侧全部失效）
//   - 策略C：更左笔端点一旦确认改变，右侧全部失效，从该笔开始继续向右重算
//
// 阶段3（本轮）：首笔纳入同一验证管线（仅改“候选生成”，不改“验证规则”）
//   - 首笔与后续笔共享同一套“确认笔”的硬条件管线：
//       方向/反向类型 -> 排他性(exclusivityOK，闭环) -> 净距(gapOK) -> K2整体升降(endpointsShiftOK)
//   - 首笔阶段的差异仅在于“候选点生成器”没有左侧可抢占任务：
//       exclusivityOK 若 fix=start，在首笔阶段直接把起点候选替换为 culprit（同类更极值修正），继续闭环；
//       fix=end 同理替换终点候选；从而保证首笔也严格通过同一管线。
//   - 本轮不改变输出 schema，不改变后续调度器机制，仅统一首笔确认过程。
// ==============================

import { candleH, candleL, toNonNegIntIdx } from "./common";

export function computePens(candles, reducedBars, fractals, _mapOrigToReduced, params = {}) {
  const pens = [];
  const MIN_GAP = Math.max(1, Number(params?.minGapReduced ?? 4));

  const frAll = Array.isArray(fractals) ? fractals : [];

  // 分型分岛并携带全局下标（用于 start_frac_idx/end_frac_idx）
  const bySeq = new Map(); // seq_id -> Array<{ f, fi }>
  for (let fi = 0; fi < frAll.length; fi++) {
    const f = frAll[fi];
    const sid = Number(f?.seq_id || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push({ f, fi });
  }

  // ===== 缓存（跨岛复用；值只依赖 candles/reducedBars，不影响语义）=====
  // 1) 分型极值缓存：key = `${kind}:${idx_orig}`
  const _fractalValueCache = new Map();
  // 2) 合并K区间缓存：key = redIdx
  const _mergedK2RangeCache = new Map();

  // ===== 原子：分型极值值（用于“更极值筛选”）=====
  function fractalValue(fr) {
    if (!fr) return NaN;

    const idx = toNonNegIntIdx(fr.k2_idx_orig);
    if (idx == null) return NaN;

    const kind = String(fr.kind_enum || "");
    if (kind !== "top" && kind !== "bottom") return NaN;

    const key = `${kind}:${idx}`;
    const cached = _fractalValueCache.get(key);
    if (cached != null) return cached;

    let v = NaN;
    if (kind === "top") {
      const x = candleH(candles, idx);
      v = Number.isFinite(x) ? x : NaN;
    } else {
      const x = candleL(candles, idx);
      v = Number.isFinite(x) ? x : NaN;
    }

    _fractalValueCache.set(key, v);
    return v;
  }

  function rid(fr) {
    const v = toNonNegIntIdx(fr?.k2_idx_red);
    return v == null ? NaN : v;
  }

  function ridGap(S, E) {
    if (!S || !E) return -1;
    const a = rid(S.f);
    const b = rid(E.f);
    if (!Number.isFinite(a) || !Number.isFinite(b)) return -1;
    return b - a;
  }

  function gapOK(S, E) {
    const g = ridGap(S, E);
    return g >= MIN_GAP;
  }

  function isOppositePair(S, E) {
    if (!S || !E) return false;
    const a = String(S.f.kind_enum || "");
    const b = String(E.f.kind_enum || "");
    return (a === "bottom" && b === "top") || (a === "top" && b === "bottom");
  }

  function dirOf(S, E) {
    if (!S || !E) return null;
    const a = String(S.f.kind_enum || "");
    const b = String(E.f.kind_enum || "");
    if (a === "bottom" && b === "top") return "UP";
    if (a === "top" && b === "bottom") return "DOWN";
    return null;
  }

  // ===== K2整体升降（严格不等），基于合并K区间（reducedBars）=====
  function mergedK2Range(fr) {
    const redIdx = toNonNegIntIdx(fr?.k2_idx_red);
    if (redIdx == null) return null;

    const cached = _mergedK2RangeCache.get(redIdx);
    if (cached !== undefined) return cached;

    const rb = Array.isArray(reducedBars) ? reducedBars[redIdx] : null;
    if (!rb) {
      _mergedK2RangeCache.set(redIdx, null);
      return null;
    }

    const gi = toNonNegIntIdx(rb.g_idx_orig);
    const di = toNonNegIntIdx(rb.d_idx_orig);
    if (gi == null || di == null) {
      _mergedK2RangeCache.set(redIdx, null);
      return null;
    }

    const h = candleH(candles, gi);
    const l = candleL(candles, di);
    if (!Number.isFinite(h) || !Number.isFinite(l)) {
      _mergedK2RangeCache.set(redIdx, null);
      return null;
    }

    const out = { h, l };
    _mergedK2RangeCache.set(redIdx, out);
    return out;
  }

  function k2ShiftOKByDir(startFr, endFr, dir) {
    const a = mergedK2Range(startFr);
    const b = mergedK2Range(endFr);
    if (!a || !b) return false;

    const d = String(dir || "").toUpperCase();
    if (d === "UP") return b.h > a.h && b.l > a.l;
    if (d === "DOWN") return b.h < a.h && b.l < a.l;
    return false;
  }

  function endpointsShiftOK(S, E) {
    const d = dirOf(S, E);
    if (!d) return false;
    return k2ShiftOKByDir(S.f, E.f, d);
  }

  // 本轮依旧：使用 Symbol 绑定每岛 posMap 到 seqArr 上
  const POS_BY_FI = Symbol("posByFi");

  // ===== 区间极值排他（硬约束）=====
  // 返回 {ok, fix, culprit}；culprit 为 {f,fi}
  function exclusivityOK(S, E, seqArr) {
    if (!S || !E) return { ok: false, fix: null, culprit: null };

    const left = rid(S.f);
    const right = rid(E.f);
    if (!Number.isFinite(left) || !Number.isFinite(right)) {
      return { ok: false, fix: null, culprit: null };
    }

    if (right - left <= 1) return { ok: true, fix: null, culprit: null };

    const l = Math.min(left, right);
    const r = Math.max(left, right);

    const sKind = String(S.f.kind_enum || "");
    const eKind = String(E.f.kind_enum || "");
    const sVal = fractalValue(S.f);
    const eVal = fractalValue(E.f);
    if (!Number.isFinite(sVal) || !Number.isFinite(eVal)) {
      return { ok: false, fix: null, culprit: null };
    }

    // 优化：优先按 pos 扫描区间切片；无法定位则回退全量扫描
    let startPos = -1;
    let endPos = -1;

    try {
      const posByFi = seqArr && seqArr[POS_BY_FI];
      if (posByFi && Number.isFinite(S.fi) && Number.isFinite(E.fi)) {
        const pS = posByFi.get(S.fi);
        const pE = posByFi.get(E.fi);
        if (Number.isFinite(pS) && Number.isFinite(pE)) {
          startPos = Math.min(pS, pE) + 1;
          endPos = Math.max(pS, pE) - 1;
        }
      }
    } catch {}

    const scanSlice =
      Number.isFinite(startPos) &&
      Number.isFinite(endPos) &&
      startPos >= 0 &&
      endPos < (seqArr?.length || 0) &&
      startPos <= endPos;

    const iter = scanSlice
      ? (function* () {
          for (let i = startPos; i <= endPos; i++) yield seqArr[i];
        })()
      : (seqArr || []);

    for (const it of iter) {
      const f = it.f;

      const k = rid(f);
      if (!Number.isFinite(k)) continue;
      if (k <= l || k >= r) continue;

      const kind = String(f.kind_enum || "");
      const v = fractalValue(f);
      if (!Number.isFinite(v)) continue;

      // UP：bottom -> top
      if (sKind === "bottom" && eKind === "top") {
        if (kind === "bottom" && v < sVal) return { ok: false, fix: "start", culprit: it };
        if (kind === "top" && v > eVal) return { ok: false, fix: "end", culprit: it };
      }

      // DOWN：top -> bottom
      if (sKind === "top" && eKind === "bottom") {
        if (kind === "top" && v > sVal) return { ok: false, fix: "start", culprit: it };
        if (kind === "bottom" && v < eVal) return { ok: false, fix: "end", culprit: it };
      }
    }

    return { ok: true, fix: null, culprit: null };
  }

  function buildPen(S, E, sid) {
    const d =
      dirOf(S, E) ||
      (String(S.f.kind_enum || "") === "bottom" ? "UP" : "DOWN");

    return {
      start_idx_red: toNonNegIntIdx(S.f.k2_idx_red),
      end_idx_red: toNonNegIntIdx(E.f.k2_idx_red),
      start_idx_orig: toNonNegIntIdx(S.f.k2_idx_orig),
      end_idx_orig: toNonNegIntIdx(E.f.k2_idx_orig),
      start_frac_idx: Number.isFinite(S.fi) ? S.fi : null,
      end_frac_idx: Number.isFinite(E.fi) ? E.fi : null,
      dir_enum: d,
      seq_id: Number(sid || 1),
    };
  }

  // 在 seqArr 中定位 entry 的位置（用于“从候选点继续向右”）
  function findEntryPos(seqArr, entry) {
    if (!entry) return -1;

    const m = seqArr && seqArr[POS_BY_FI];
    if (m && Number.isFinite(entry.fi)) {
      const p = m.get(entry.fi);
      if (p != null) return p;
    }

    const rr = rid(entry.f);
    if (!Number.isFinite(rr)) return -1;
    for (let i = 0; i < seqArr.length; i++) {
      if (Number(seqArr[i]?.f?.k2_idx_red) === rr) return i;
    }
    return -1;
  }

  // ===== 分岛推进 =====
  for (const [sid, arr0] of bySeq.entries()) {
    const seqArr = (arr0 || []).slice().sort((a, b) => Number(a.f.k2_idx_red) - Number(b.f.k2_idx_red));
    if (!seqArr.length) continue;

    const fiToEntry = new Map();
    for (const it of seqArr) fiToEntry.set(it.fi, it);

    const posByFi = new Map();
    for (let i = 0; i < seqArr.length; i++) posByFi.set(seqArr[i].fi, i);
    seqArr[POS_BY_FI] = posByFi;

    const pensLocal = [];

    function truncateToPenIndex(idxInclusive) {
      const n = pensLocal.length;
      const idx = Math.max(-1, Math.min(n - 1, Number(idxInclusive)));
      pensLocal.splice(idx + 1);
    }

    function getPenStartEntry(pen) {
      const sFi = toNonNegIntIdx(pen?.start_frac_idx);
      return sFi == null ? null : (fiToEntry.get(sFi) || null);
    }
    function getPenEndEntry(pen) {
      const eFi = toNonNegIntIdx(pen?.end_frac_idx);
      return eFi == null ? null : (fiToEntry.get(eFi) || null);
    }

    // ===== 统一的“确认一条笔”验证管线 =====
    // 输入：起点/终点候选 entry（{f,fi}）
    // 返回：{ ok:true, pen, S, E } 或 { ok:false, reason, S, E }
    // 说明：
    //   - 排他闭环：fix=end 直接修 E 并继续；fix=start 的处理由 caller 决定（首笔=就地修S；后续=触发更左任务）
    function confirmPenPipeline({ candS, candE, allowFixStartInPlace }) {
      if (!candS || !candE) return { ok: false, reason: "null", S: candS, E: candE };

      // 方向/反向类型硬约束
      if (!isOppositePair(candS, candE)) return { ok: false, reason: "not-opposite", S: candS, E: candE };

      // 排他闭环（硬约束）
      let S = candS;
      let E = candE;

      let guard = 0;
      while (guard++ < 50) {
        const ex = exclusivityOK(S, E, seqArr);
        if (ex.ok) break;

        if (ex.fix === "end" && ex.culprit) {
          E = ex.culprit;
          continue;
        }

        if (ex.fix === "start" && ex.culprit) {
          if (!allowFixStartInPlace) {
            return { ok: false, reason: "need-preempt", S, E, culprit: ex.culprit };
          }
          S = ex.culprit;
          continue;
        }

        return { ok: false, reason: "ex-bad", S, E };
      }

      // 净距硬约束
      if (!gapOK(S, E)) return { ok: false, reason: "gap", S, E };

      // K2整体升降硬约束
      if (!endpointsShiftOK(S, E)) return { ok: false, reason: "k2shift", S, E };

      const pen = buildPen(S, E, sid);
      if (
        pen.start_idx_red == null ||
        pen.end_idx_red == null ||
        pen.start_idx_orig == null ||
        pen.end_idx_orig == null
      ) {
        return { ok: false, reason: "schema", S, E };
      }

      return { ok: true, pen, S, E };
    }

    // ========= 阶段3：首笔候选生成器（bestTop/bestBottom），但确认走统一管线 =========
    let bestTop = null;
    let bestBottom = null;
    const betterTop = (a, b) => fractalValue(a.f) > fractalValue(b.f);
    const betterBottom = (a, b) => fractalValue(a.f) < fractalValue(b.f);

    // 首笔扫描位置
    let scanPos = 0;

    // 首笔生成：只要 bestTop/bestBottom 都存在，就尝试确认
    function tryConfirmFirstPenFromBests() {
      if (!bestTop || !bestBottom) return false;

      const rTop = rid(bestTop.f);
      const rBot = rid(bestBottom.f);
      if (!Number.isFinite(rTop) || !Number.isFinite(rBot)) return false;
      if (rTop === rBot) return false;

      // 按时间顺序决定 (S,E)
      let candS = null;
      let candE = null;
      if (rBot < rTop) {
        candS = bestBottom;
        candE = bestTop;
      } else {
        candS = bestTop;
        candE = bestBottom;
      }

      // 首笔阶段：允许 fix=start 就地修正（因为无更左可抢占）
      const res = confirmPenPipeline({ candS, candE, allowFixStartInPlace: true });
      if (!res.ok) {
        // 首笔未成：保持 best 指针继续向右扫描
        // 注意：res.S/res.E 可能已被 fix=end/fix=start 就地修正，但不强行写回 best，
        // 以保持与原先 “bestTop/bestBottom 仅由更极值触发更新” 的语义一致。
        return false;
      }

      pensLocal.push(res.pen);
      return true;
    }

    while (scanPos < seqArr.length && !pensLocal.length) {
      const cur = seqArr[scanPos++];
      const kind = String(cur.f.kind_enum || "");
      if (kind === "top") {
        if (!bestTop || betterTop(cur, bestTop)) {
          bestTop = cur;
          tryConfirmFirstPenFromBests();
        }
      } else if (kind === "bottom") {
        if (!bestBottom || betterBottom(cur, bestBottom)) {
          bestBottom = cur;
          tryConfirmFirstPenFromBests();
        }
      }
    }

    if (!pensLocal.length) continue;

    // ========= 阶段2调度器（保持不变） =========

    let activeStart = getPenEndEntry(pensLocal[pensLocal.length - 1]);
    if (!activeStart) continue;

    // 从“首笔扫描停止的位置”与“首笔终点之后”两者取最大，确保扫描单调不回退
    scanPos = Math.max(scanPos, Math.max(0, findEntryPos(seqArr, activeStart) + 1));

    let activeEnd = null;
    let activeEndVal = NaN;

    function moveActiveStartTo(entry) {
      activeStart = entry;
      activeEnd = null;
      activeEndVal = NaN;
      const p = findEntryPos(seqArr, entry);
      if (p >= 0) scanPos = Math.max(scanPos, p + 1);
    }

    function applyPendingShiftToPrevPenEnd(newEndEntry) {
      const lastIdx = pensLocal.length - 1;
      if (lastIdx < 0) return false;

      const pen = pensLocal[lastIdx];
      pen.end_idx_red = toNonNegIntIdx(newEndEntry.f.k2_idx_red);
      pen.end_idx_orig = toNonNegIntIdx(newEndEntry.f.k2_idx_orig);
      pen.end_frac_idx = newEndEntry.fi;
      return true;
    }

    function preemptToLeftPen(leftPenIndex, pendingEndEntry) {
      truncateToPenIndex(leftPenIndex);

      if (!pensLocal.length) return false;

      const tail = pensLocal[pensLocal.length - 1];
      tail.end_idx_red = toNonNegIntIdx(pendingEndEntry.f.k2_idx_red);
      tail.end_idx_orig = toNonNegIntIdx(pendingEndEntry.f.k2_idx_orig);
      tail.end_frac_idx = pendingEndEntry.fi;

      moveActiveStartTo(pendingEndEntry);
      return true;
    }

    function validateAndRepairTailPen() {
      const tailIdx = pensLocal.length - 1;
      if (tailIdx < 0) return { ok: false, preempt: false };

      const pen = pensLocal[tailIdx];
      const S = getPenStartEntry(pen);
      const E = getPenEndEntry(pen);
      if (!S || !E) return { ok: false, preempt: false };

      const sRid = toNonNegIntIdx(pen.start_idx_red);
      const eRid = toNonNegIntIdx(pen.end_idx_red);
      if (!Number.isFinite(sRid) || !Number.isFinite(eRid) || sRid >= eRid) {
        pensLocal.splice(tailIdx, 1);
        const newTail = pensLocal[pensLocal.length - 1];
        const newEnd = newTail ? getPenEndEntry(newTail) : null;
        if (newEnd) moveActiveStartTo(newEnd);
        return { ok: false, preempt: false };
      }

      let guard = 0;
      while (guard++ < 50) {
        const ex = exclusivityOK(S, E, seqArr);
        if (ex.ok) break;

        if (ex.fix === "end" && ex.culprit) {
          pen.end_idx_red = toNonNegIntIdx(ex.culprit.f.k2_idx_red);
          pen.end_idx_orig = toNonNegIntIdx(ex.culprit.f.k2_idx_orig);
          pen.end_frac_idx = ex.culprit.fi;
          moveActiveStartTo(ex.culprit);
          continue;
        }

        if (ex.fix === "start" && ex.culprit) {
          const leftIdx = tailIdx - 1;
          if (leftIdx < 0) return { ok: false, preempt: false };
          preemptToLeftPen(leftIdx, ex.culprit);
          return { ok: false, preempt: true };
        }

        break;
      }

      if (!gapOK(S, E)) return { ok: false, preempt: false };
      if (!endpointsShiftOK(S, E)) return { ok: false, preempt: false };

      return { ok: true, preempt: false };
    }

    const MAX_STEPS = Math.max(1000, seqArr.length * 50);
    let steps = 0;

    while (steps++ < MAX_STEPS && scanPos < seqArr.length && pensLocal.length) {
      const cur = seqArr[scanPos++];
      const sKind = String(activeStart?.f?.kind_enum || "");
      const dir = sKind === "bottom" ? "UP" : "DOWN";
      const endKind = dir === "UP" ? "top" : "bottom";
      const kind = String(cur.f.kind_enum || "");

      if (kind === sKind) {
        const sVal = fractalValue(activeStart.f);
        const cVal = fractalValue(cur.f);
        if (Number.isFinite(sVal) && Number.isFinite(cVal)) {
          const moreExtremeStart =
            (dir === "UP" && cVal < sVal) ||
            (dir === "DOWN" && cVal > sVal);

          if (moreExtremeStart) {
            applyPendingShiftToPrevPenEnd(cur);
            moveActiveStartTo(cur);

            const vr = validateAndRepairTailPen();
            if (vr.preempt) continue;
            continue;
          }
        }
        continue;
      }

      if (kind === endKind) {
        const cVal = fractalValue(cur.f);
        if (!Number.isFinite(cVal)) continue;

        if (!activeEnd) {
          activeEnd = cur;
          activeEndVal = cVal;
        } else {
          const moreExtremeEnd =
            (dir === "UP" && cVal > activeEndVal) ||
            (dir === "DOWN" && cVal < activeEndVal);

          if (moreExtremeEnd) {
            activeEnd = cur;
            activeEndVal = cVal;
          } else {
            continue;
          }
        }

        // 使用统一管线确认“后续笔”：不允许 fix=start 就地修（必须抢占）
        const res = confirmPenPipeline({ candS: activeStart, candE: activeEnd, allowFixStartInPlace: false });

        if (!res.ok) {
          if (res.reason === "need-preempt" && res.culprit) {
            const leftIdx = pensLocal.length - 1;
            if (leftIdx >= 0) {
              preemptToLeftPen(leftIdx, res.culprit);
            }
          }
          // 不成立：保持 scanPos 向右，按现有策略清空终点候选（避免状态污染）
          activeEnd = null;
          activeEndVal = NaN;
          continue;
        }

        const pen = res.pen;

        if (pensLocal.length) {
          const prevPen = pensLocal[pensLocal.length - 1];
          prevPen.end_idx_red = toNonNegIntIdx(activeStart.f.k2_idx_red);
          prevPen.end_idx_orig = toNonNegIntIdx(activeStart.f.k2_idx_orig);
          prevPen.end_frac_idx = activeStart.fi;
        }

        pensLocal.push(pen);

        // 下一笔起点=本笔终点
        moveActiveStartTo(res.E);

        activeEnd = null;
        activeEndVal = NaN;

        continue;
      }
    }

    for (const p of pensLocal) pens.push(p);
  }

  // ===== DEBUG SNAPSHOT（仅用于控制台导出排查断笔；不影响算法语义）=====
  try {
    if (typeof window !== "undefined") {
      window.__CHAN_DEBUG__ = window.__CHAN_DEBUG__ || {};
      window.__CHAN_DEBUG__.lastPensSnapshot = {
        t: Date.now(),
        candles,
        reducedBars,
        fractals,
        pens
      };
      // 可选：记录当前版本标识，方便你确认浏览器是否加载了最新代码
      window.__CHAN_DEBUG__.lastPensSnapshotTag = "pens.js debug snapshot enabled";
    }
  } catch {}

  return { confirmed: pens, provisional: null, all: pens };
}
