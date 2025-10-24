// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\segments.js
// ==============================
// 说明：从 useChan.js 拆分出的线段识别模块
// - 核心职责：从笔序列中识别出元线段。
// - 算法：按岛（seq_id）独立进行。
// ==============================

/**
 * 元线段识别（完全重写版）
 * 变更：按 seq_id 分组推进；线段对象新增 seq_id。
 */
export function computeSegments(pensConfirmed) {
  const segs = [];
  const pens = Array.isArray(pensConfirmed) ? pensConfirmed : [];

  const bySeq = new Map();
  for (const p of pens) {
    const sid = Number(p?.seq_id || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push(p);
  }

  function dirUp(p) { return String(p?.dir_enum || "").toUpperCase() === "UP"; }
  function penLow(p) { const a = Number(p?.start_d_pri), b = Number(p?.end_d_pri); return Math.min(a, b); }
  function penHigh(p) { const a = Number(p?.start_g_pri), b = Number(p?.end_g_pri); return Math.max(a, b); }

  // 成功判定（严格不等）
  function checkPair(pCur, pNext) {
    const l1 = penLow(pCur), h1 = penHigh(pCur);
    const l2 = penLow(pNext), h2 = penHigh(pNext);
    const overlapLow = Math.max(l1, l2), overlapHigh = Math.min(h1, h2);
    const overlapOk = overlapHigh > overlapLow;
    const c1 = l1 < l2 && h1 > h2; const c2 = l2 < l1 && h2 > h1;
    const notContainOk = !(c1 || c2);

    // 发展一致（严格）
    let trendOk = false;
    if (dirUp(pCur) && dirUp(pNext)) trendOk = l2 > l1 && h2 > h1;
    else if (!dirUp(pCur) && !dirUp(pNext)) trendOk = h2 < h1 && l2 < l1;
    return { ok: overlapOk && notContainOk && trendOk };
  }

  for (const [sid, arr] of bySeq.entries()) {
    let s = 0;
    while (s < arr.length) {
      const startPen = arr[s];
      if (!startPen) break;

      const up = dirUp(startPen);

      let hasSuccess = false;
      let curIdx = s;
      let lastSuccessNextIdx = -1;
      const successNextIdxList = [];
      const checks = [];

      while (curIdx + 2 < arr.length) {
        const nextIdx = curIdx + 2;
        const pCur = arr[curIdx], pNext = arr[nextIdx];
        if (dirUp(pCur) !== dirUp(pNext)) { checks.push({ ok: false }); break; }
        const evalRes = checkPair(pCur, pNext);
        checks.push({ ok: evalRes.ok });
        if (evalRes.ok) {
          hasSuccess = true;
          lastSuccessNextIdx = nextIdx;
          successNextIdxList.push(nextIdx);
          curIdx = nextIdx;
          continue;
        } else {
          break;
        }
      }

      if (hasSuccess && lastSuccessNextIdx >= 0) {
        const endPen = arr[lastSuccessNextIdx];
        const start_idx_orig = Number(startPen.start_idx_orig);
        const end_idx_orig = Number(endPen.end_idx_orig);
        const start_y_pri = up ? Number(startPen.start_d_pri) : Number(startPen.start_g_pri);
        const end_y_pri = up ? Number(endPen.end_g_pri) : Number(endPen.end_d_pri);

        const segment = {
          start_pen_idx_int: s,
          end_pen_idx_int: lastSuccessNextIdx,
          start_frac_idx_int: Number(startPen.start_frac_idx_int ?? -1),
          end_frac_idx_int: Number(endPen.end_frac_idx_int ?? -1),
          start_idx_red: Number(startPen.start_idx_red),
          end_idx_red: Number(endPen.end_idx_red),
          start_idx_orig,
          end_idx_orig,
          start_g_pri: Number(startPen.start_g_pri),
          start_d_pri: Number(startPen.start_d_pri),
          end_g_pri: Number(endPen.end_g_pri),
          end_d_pri: Number(endPen.end_d_pri),
          start_y_pri,
          end_y_pri,
          dir_enum: up ? "UP" : "DOWN",
          success_pen_idx_arr: successNextIdxList.slice(),
          checks_arr: checks.slice(),
          end_gap_exists_bool: (function () {
            const lookA = lastSuccessNextIdx + 1;
            const lookB = lastSuccessNextIdx + 3;
            if (lookB >= arr.length) return true;
            const a = arr[lookA], b = arr[lookB];
            if (!a || !b) return true;
            if (dirUp(a) !== dirUp(b)) return true;
            return !checkPair(a, b).ok;
          })(),
          seq_id: sid,
        };

        segs.push(segment);
        s = lastSuccessNextIdx + 1;
      } else {
        const mid = (typeof curIdx === "number") ? curIdx + 1 : s + 1;
        if (mid < arr.length) s = mid; else break;
      }
    }
  }

  return segs;
}
