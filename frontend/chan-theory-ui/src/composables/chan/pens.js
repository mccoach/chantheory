// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\pens.js
// ==============================
// 说明：笔识别模块（Idx-Only Schema 版）
// - 核心职责：从分型序列中识别出符合规则的笔。
// - 规则要义（与原实现保持一致）：
//   1) 仅在同 seq_id（连续性岛）内识别与推进，不跨岛。
//   2) 先修极值（区间排他）、再验三条（方向/净距/排他）。
//   3) 首尾相连：后一笔起点必须等于前一笔终点；起点修正需向左传播，直到岛内稳定。
//   4) 净距 >= MIN_GAP（默认 4，保持原实现）。
//   5) 相等不触发修正（严格不等比较）。
//
// ✅ 本轮重构目标：
//   - 输出 Pen 严格按 Schema：只存 idx（start/end idx_red & idx_orig）+ 可选 fractal 下标 + dir_enum + seq_id；
//   - 严禁输出任何 pri/ts/y 等衍生字段；
//   - 任何价格比较通过 idx_orig 回溯 candles 读取（单一真相源）。
// ==============================

import { candleH, candleL, toNonNegIntIdx } from "./common";

/**
 * 识别笔（Idx-Only 输出）
 *
 * Pen Schema（必须满足）：
 *   - start_idx_red, end_idx_red
 *   - start_idx_orig, end_idx_orig
 *   - start_frac_idx, end_frac_idx（可选）
 *   - dir_enum ('UP'|'DOWN')
 *   - seq_id
 *
 * @param {Array<object>} candles - 原始K线（唯一真相源）
 * @param {Array<object>} reducedBars - 合并K线（Idx-Only，本算法不依赖其数值字段）
 * @param {Array<object>} fractals - 分型（Idx-Only）
 * @param {Array<any>} _mapOrigToReduced - 兼容保留（本算法不再依赖）
 * @param {object} params
 * @param {number} params.minGapReduced - 最小净距（默认 4，与原实现一致）
 * @returns {{confirmed:Array<object>, provisional:null, all:Array<object>}}
 */
export function computePens(
  candles,
  reducedBars,
  fractals,
  _mapOrigToReduced,
  params = {}
) {
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

  // === 分型值（顶/底）===（严格从 candles 回溯，不落盘）
  function fractalValue(fr) {
    if (!fr) return NaN;
    const idx = toNonNegIntIdx(fr.k2_idx_orig);
    if (idx == null) return NaN;
    const kind = String(fr.kind_enum || "");
    if (kind === "top") {
      const v = candleH(candles, idx);
      return Number.isFinite(v) ? v : NaN;
    }
    if (kind === "bottom") {
      const v = candleL(candles, idx);
      return Number.isFinite(v) ? v : NaN;
    }
    return NaN;
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

  // 区间极值排他（开区间），返回 {ok, fix, culprit}
  // culprit 为 {f,fi}（与 seqArr 同构）
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

    for (const it of seqArr || []) {
      const f = it.f;
      const k = rid(f);
      if (!Number.isFinite(k)) continue;
      if (k <= l || k >= r) continue; // 开区间

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

  /**
   * 首尾相连 + 极值修正的“无限向左递归传播”
   *
   * ✅ 对齐旧实现要点：
   *   - 每次将上一笔的 end 强制对齐为 carryEnd；
   *   - 若该笔退化（start>=end）则删除并继续向更左；
   *   - 对该笔执行 exclusivityOK：
   *       * fix=start：调整 start -> culprit，并令 carryEnd=culprit，继续向更左传播（这就是“无限向左直到稳定”）
   *       * fix=end  ：调整 end -> culprit，并结束传播（与旧实现一致：该分支很少见）
   *       * ok       ：结束传播
   *
   * @param {{f:object,fi:number}} newStart
   * @param {number} sid
   * @param {Map<number, {f:object,fi:number}>} fiToEntry
   * @param {Array<{f:object,fi:number}>} seqArr
   */
  function propagateToPreviousPens(newStart, sid, fiToEntry, seqArr) {
    if (!pens.length || !newStart) return;

    let i = pens.length - 1;
    let carryEnd = newStart;

    while (i >= 0) {
      const pen = pens[i];
      if (Number(pen?.seq_id) !== Number(sid)) break;

      const nextEndRed = toNonNegIntIdx(carryEnd.f.k2_idx_red);
      const nextEndOrig = toNonNegIntIdx(carryEnd.f.k2_idx_orig);
      if (nextEndRed == null || nextEndOrig == null) break;

      // 1) 先强制对齐上一笔的终点
      pen.end_idx_red = nextEndRed;
      pen.end_idx_orig = nextEndOrig;
      pen.end_frac_idx = carryEnd.fi;

      // 2) 若退化则删除该笔并继续向左（carryEnd 不变）
      if (
        !Number.isFinite(pen.start_idx_red) ||
        !Number.isFinite(pen.end_idx_red) ||
        pen.start_idx_red >= pen.end_idx_red
      ) {
        pens.splice(i, 1);
        i -= 1;
        continue;
      }

      // 3) 执行排他性复验（使用分型下标快速定位 S/E）
      const sFi = toNonNegIntIdx(pen.start_frac_idx);
      const eFi = toNonNegIntIdx(pen.end_frac_idx);
      if (sFi == null || eFi == null) break;

      const S = fiToEntry.get(sFi) || null;
      const E = fiToEntry.get(eFi) || null;
      if (!S || !E) break;

      const ex = exclusivityOK(S, E, seqArr);

      if (!ex.ok && ex.fix === "start" && ex.culprit) {
        // fix=start：调整起点为更极值，并把 carryEnd 设为该新起点，继续向更左传播（无限递归本质）
        pen.start_idx_red = toNonNegIntIdx(ex.culprit.f.k2_idx_red);
        pen.start_idx_orig = toNonNegIntIdx(ex.culprit.f.k2_idx_orig);
        pen.start_frac_idx = ex.culprit.fi;

        carryEnd = ex.culprit;
        i -= 1;
        continue;
      }

      if (!ex.ok && ex.fix === "end" && ex.culprit) {
        // fix=end：对当前笔自身调整终点为更极值（与旧实现一致：不继续左传）
        pen.end_idx_red = toNonNegIntIdx(ex.culprit.f.k2_idx_red);
        pen.end_idx_orig = toNonNegIntIdx(ex.culprit.f.k2_idx_orig);
        pen.end_frac_idx = ex.culprit.fi;
        break;
      }

      // ok：稳定，停止回溯
      break;
    }
  }

  // ===== 分岛推进 =====
  for (const [sid, arr0] of bySeq.entries()) {
    const seqArr = (arr0 || [])
      .slice()
      .sort((a, b) => Number(a.f.k2_idx_red) - Number(b.f.k2_idx_red));
    if (!seqArr.length) continue;

    // 建立 fi->entry 映射（保障回溯传播稳定不“找不到S/E”而提前中断）
    const fiToEntry = new Map();
    for (const it of seqArr) {
      fiToEntry.set(it.fi, it);
    }

    let bestTop = null;
    let bestBottom = null;
    let haveFirstPen = false;

    let S = null;
    let E = null;

    const betterTop = (a, b) => fractalValue(a.f) > fractalValue(b.f);
    const betterBottom = (a, b) => fractalValue(a.f) < fractalValue(b.f);

    const tryMakeFirstPen = () => {
      if (!bestTop || !bestBottom) return false;

      let candS = null,
        candE = null;

      const rTop = rid(bestTop.f);
      const rBot = rid(bestBottom.f);
      if (!Number.isFinite(rTop) || !Number.isFinite(rBot)) return false;

      if (rBot < rTop) {
        candS = bestBottom;
        candE = bestTop;
      } else if (rTop < rBot) {
        candS = bestTop;
        candE = bestBottom;
      } else {
        return false;
      }

      if (!isOppositePair(candS, candE)) return false;

      const ex = exclusivityOK(candS, candE, seqArr);
      if (!ex.ok) {
        if (ex.culprit) {
          const ck = String(ex.culprit.f.kind_enum || "");
          if (ck === "top") {
            if (!bestTop || betterTop(ex.culprit, bestTop)) bestTop = ex.culprit;
          } else if (ck === "bottom") {
            if (!bestBottom || betterBottom(ex.culprit, bestBottom)) bestBottom = ex.culprit;
          }
        }
        return false;
      }

      if (!gapOK(candS, candE)) return false;

      const pen = buildPen(candS, candE, sid);
      if (
        pen.start_idx_red == null ||
        pen.end_idx_red == null ||
        pen.start_idx_orig == null ||
        pen.end_idx_orig == null
      ) {
        return false;
      }

      pens.push(pen);
      S = candE;
      E = null;
      haveFirstPen = true;
      return true;
    };

    for (let i = 0; i < seqArr.length; i++) {
      const cur = seqArr[i];

      if (!haveFirstPen) {
        if (String(cur.f.kind_enum || "") === "top") {
          if (!bestTop || betterTop(cur, bestTop)) {
            bestTop = cur;
            tryMakeFirstPen();
          }
        } else if (String(cur.f.kind_enum || "") === "bottom") {
          if (!bestBottom || betterBottom(cur, bestBottom)) {
            bestBottom = cur;
            tryMakeFirstPen();
          }
        }
        continue;
      }

      const sKind = String(S?.f?.kind_enum || "");
      const curDir = sKind === "bottom" ? "UP" : "DOWN";

      const kind = String(cur.f.kind_enum || "");
      if (kind === sKind) {
        const sVal = fractalValue(S.f);
        const cVal = fractalValue(cur.f);
        if (!Number.isFinite(sVal) || !Number.isFinite(cVal)) continue;

        const shouldMoveStart =
          (curDir === "UP" && cVal < sVal) ||
          (curDir === "DOWN" && cVal > sVal);

        if (shouldMoveStart) {
          S = cur;
          propagateToPreviousPens(S, sid, fiToEntry, seqArr);
          if (E && rid(S.f) >= rid(E.f)) E = null;
        }
      } else {
        if (!E) {
          E = cur;
        } else {
          const eVal = fractalValue(E.f);
          const cVal = fractalValue(cur.f);
          if (!Number.isFinite(eVal) || !Number.isFinite(cVal)) continue;

          const shouldReplaceEnd =
            (curDir === "UP" && cVal > eVal) ||
            (curDir === "DOWN" && cVal < eVal);

          if (shouldReplaceEnd) {
            E = cur;
          }
        }
      }

      if (E) {
        const ex = exclusivityOK(S, E, seqArr);
        if (!ex.ok) {
          if (ex.fix === "start" && ex.culprit) {
            S = ex.culprit;
            propagateToPreviousPens(S, sid, fiToEntry, seqArr);
            if (E && rid(S.f) >= rid(E.f)) E = null;
          } else if (ex.fix === "end" && ex.culprit) {
            E = ex.culprit;
          }
          continue;
        }

        if (gapOK(S, E)) {
          // 兜底：确保上一笔终点=当前 S（首尾相连）
          if (pens.length) {
            const prevPen = pens[pens.length - 1];
            if (Number(prevPen?.seq_id) === Number(sid)) {
              const nextEndRed = toNonNegIntIdx(S.f.k2_idx_red);
              const nextEndOrig = toNonNegIntIdx(S.f.k2_idx_orig);
              if (nextEndRed != null && nextEndOrig != null) {
                prevPen.end_idx_red = nextEndRed;
                prevPen.end_idx_orig = nextEndOrig;
                prevPen.end_frac_idx = S.fi;
              }
            }
          }

          const pen = buildPen(S, E, sid);
          if (
            pen.start_idx_red == null ||
            pen.end_idx_red == null ||
            pen.start_idx_orig == null ||
            pen.end_idx_orig == null
          ) {
            S = E;
            E = null;
            continue;
          }

          pens.push(pen);

          S = E;
          E = null;
        }
      }
    }
  }

  return { confirmed: pens, provisional: null, all: pens };
}
