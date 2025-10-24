// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\pens.js
// ==============================
// 说明：从 useChan.js 拆分出的笔识别模块
// - 核心职责：从分型序列中识别出符合规则的笔。
// - 算法：遵循“先修极值、再验三条、首尾相连、净距≥3、不跨屏障、相等不触发修正”的核心规则。
// ==============================

/**
 * 识别笔 —— 重写版
 * 变更：仅在同 seq_id 内识别与推进；笔对象新增 seq_id。
 */
export function computePens(
  reducedBars,
  fractals,
  _mapOrigToReduced,
  params = {}
) {
  const pens = [];
  const MIN_GAP = Math.max(1, Number(params?.minGapReduced ?? 4));

  // 分岛：按 seq_id 将 fractals 分组
  const bySeq = new Map();
  for (const f of Array.isArray(fractals) ? fractals : []) {
    const sid = Number(f?.seq_id || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push(f);
  }

  // id->索引映射（用于 pen 中回填 start/end 的 fractal 索引）
  const id2idxGlobal = new Map();
  (Array.isArray(fractals) ? fractals : []).forEach((f, i) => {
    if (f?.id_str) id2idxGlobal.set(String(f.id_str), i);
  });

  function ridGap(S, E) {
    if (!S || !E) return -1;
    return Number(E.k2_idx_red) - Number(S.k2_idx_red);
  }
  function gapOK(S, E) {
    const g = ridGap(S, E);
    return g >= MIN_GAP;
  }
  function isOppositePair(S, E) {
    if (!S || !E) return false;
    const a = String(S.kind_enum || "");
    const b = String(E.kind_enum || "");
    return (a === "bottom" && b === "top") || (a === "top" && b === "bottom");
  }
  // 区间极值排他（开区间），返回 {ok, fix, culprit}
  function exclusivityOK(S, E, frArr) {
    if (!S || !E) return { ok: false, fix: null, culprit: null };
    const left = Number(S.k2_idx_red), right = Number(E.k2_idx_red);
    if (right - left <= 1) return { ok: true, fix: null, culprit: null };
    const l = Math.min(left, right), r = Math.max(left, right);
    for (const f of frArr || []) {
      const rid = Number(f.k2_idx_red);
      if (rid <= l || rid >= r) continue; // 开区间
      if (S.kind_enum === "bottom" && E.kind_enum === "top") {
        if (f.kind_enum === "bottom" && Number(f.k2_d_pri) < Number(S.k2_d_pri))
          return { ok: false, fix: "start", culprit: f };
        if (f.kind_enum === "top" && Number(f.k2_g_pri) > Number(E.k2_g_pri))
          return { ok: false, fix: "end", culprit: f };
      } else if (S.kind_enum === "top" && E.kind_enum === "bottom") {
        if (f.kind_enum === "top" && Number(f.k2_g_pri) > Number(S.k2_g_pri))
          return { ok: false, fix: "start", culprit: f };
        if (f.kind_enum === "bottom" && Number(f.k2_d_pri) < Number(E.k2_d_pri))
          return { ok: false, fix: "end", culprit: f };
      }
    }
    return { ok: true, fix: null, culprit: null };
  }

  function dirOf(S, E) {
    if (!S || !E) return null;
    if (S.kind_enum === "bottom" && E.kind_enum === "top") return "UP";
    if (S.kind_enum === "top" && E.kind_enum === "bottom") return "DOWN";
    return null;
  }

  // 合并K价格获取
  function barAtRed(idx) {
    return reducedBars && reducedBars[Number(idx)] ? reducedBars[Number(idx)] : {};
  }

  // 生成一笔
  function buildPen(S, E, sid) {
    const start_idx_red = Number(S.k2_idx_red);
    const end_idx_red = Number(E.k2_idx_red);
    const start_idx_orig = Number(S.k2_idx_orig);
    const end_idx_orig = Number(E.k2_idx_orig);

    const sBar = barAtRed(start_idx_red);
    const eBar = barAtRed(end_idx_red);

    const start_g_pri = Number(sBar.g_pri);
    const start_d_pri = Number(sBar.d_pri);
    const end_g_pri = Number(eBar.g_pri);
    const end_d_pri = Number(eBar.d_pri);

    const d = dirOf(S, E) || (S.kind_enum === "bottom" ? "UP" : "DOWN");
    const start_y_pri = d === "UP" ? start_d_pri : start_g_pri;
    const end_y_pri = d === "UP" ? end_g_pri : end_d_pri;

    const start_frac_idx_int = id2idxGlobal.has(String(S.id_str || "")) ? Number(id2idxGlobal.get(String(S.id_str))) : -1;
    const end_frac_idx_int = id2idxGlobal.has(String(E.id_str || "")) ? Number(id2idxGlobal.get(String(E.id_str))) : -1;

    return {
      start_frac_idx_int,
      end_frac_idx_int,
      start_frac_id_str: String(S.id_str || ""),
      end_frac_id_str: String(E.id_str || ""),

      start_idx_red,
      end_idx_red,
      start_idx_orig,
      end_idx_orig,

      start_g_pri,
      start_d_pri,
      end_g_pri,
      end_d_pri,
      start_y_pri,
      end_y_pri,

      span_red_cnt_int: end_idx_red - start_idx_red,
      amp_abs_pri: Math.abs(end_y_pri - start_y_pri),
      dir_enum: d,
      seq_id: sid,
    };
  }

  // 将“上一笔终点”同步为 newStartFractal（保持首尾相连），并向左连锁回溯到稳定
  function propagateToPreviousPens(newStartFractal, sid, frArr) {
    if (!pens.length) return;
    // 仅处理同岛范围
    let i = pens.length - 1;
    let carryEndFr = newStartFractal;
    while (i >= 0) {
      const pen = pens[i];
      if (Number(pen.seq_id) !== Number(sid)) break;

      // 更新 pen 的终点为 carryEndFr
      if (Number(pen.end_idx_red) !== Number(carryEndFr.k2_idx_red)) {
        pen.end_idx_red = Number(carryEndFr.k2_idx_red);
        pen.end_idx_orig = Number(carryEndFr.k2_idx_orig);
        const eBar = barAtRed(pen.end_idx_red);
        pen.end_g_pri = Number(eBar.g_pri);
        pen.end_d_pri = Number(eBar.d_pri);
        pen.end_y_pri = pen.dir_enum === "UP" ? pen.end_g_pri : pen.end_d_pri;
        pen.span_red_cnt_int = pen.end_idx_red - pen.start_idx_red;
      }

      // 若笔退化（起点>=终点），移除该笔并继续向更左一笔传播
      if (pen.start_idx_red >= pen.end_idx_red) {
        pens.splice(i, 1);
        // carryEndFr 不变（仍然是新的起点），继续 i-- 回溯
        i -= 1;
        continue;
      }

      // 构造此笔的起止分型快照，检查区间排他
      const S = {
        kind_enum: pen.dir_enum === "UP" ? "bottom" : "top",
        k2_idx_red: pen.start_idx_red,
        k2_idx_orig: pen.start_idx_orig,
        k2_d_pri: pen.start_d_pri,
        k2_g_pri: pen.start_g_pri,
        id_str: pen.start_frac_id_str,
      };
      const E = {
        kind_enum: pen.dir_enum === "UP" ? "top" : "bottom",
        k2_idx_red: pen.end_idx_red,
        k2_idx_orig: pen.end_idx_orig,
        k2_d_pri: pen.end_d_pri,
        k2_g_pri: pen.end_g_pri,
        id_str: pen.end_frac_id_str,
      };

      const ex = exclusivityOK(S, E, frArr);
      if (!ex.ok && ex.fix === "start" && ex.culprit) {
        // 起点右移为“更大极值”
        const c = ex.culprit;
        pen.start_idx_red = Number(c.k2_idx_red);
        pen.start_idx_orig = Number(c.k2_idx_orig);
        const sBar = barAtRed(pen.start_idx_red);
        pen.start_g_pri = Number(sBar.g_pri);
        pen.start_d_pri = Number(sBar.d_pri);
        pen.start_y_pri = pen.dir_enum === "UP" ? pen.start_d_pri : pen.start_g_pri;
        pen.span_red_cnt_int = pen.end_idx_red - pen.start_idx_red;
        pen.start_frac_id_str = String(c.id_str || "");
        pen.start_frac_idx_int = id2idxGlobal.has(String(c.id_str || "")) ? Number(id2idxGlobal.get(String(c.id_str))) : -1;

        // 同步更左一笔的“终点”为该新起点（继续回溯）
        carryEndFr = c;
        i -= 1;
        continue;
      } else if (!ex.ok && ex.fix === "end" && ex.culprit) {
        // 此分支很少见：将当前笔的终点也调整为更大极值（不继续左传）
        const c = ex.culprit;
        pen.end_idx_red = Number(c.k2_idx_red);
        pen.end_idx_orig = Number(c.k2_idx_orig);
        const eBar = barAtRed(pen.end_idx_red);
        pen.end_g_pri = Number(eBar.g_pri);
        pen.end_d_pri = Number(eBar.d_pri);
        pen.end_y_pri = pen.dir_enum === "UP" ? pen.end_g_pri : pen.end_d_pri;
        pen.span_red_cnt_int = pen.end_idx_red - pen.start_idx_red;
        pen.end_frac_id_str = String(c.id_str || "");
        pen.end_frac_idx_int = id2idxGlobal.has(String(c.id_str || "")) ? Number(id2idxGlobal.get(String(c.id_str))) : -1;
        // 不继续连锁，视为稳定
        break;
      } else {
        // 已稳定，结束回溯
        break;
      }
    }
  }

  // 分岛推进
  for (const [sid, arrF0] of bySeq.entries()) {
    // 同岛分型序列按 k2_idx_red 递增
    const frArr = (arrF0 || []).slice().sort((a, b) => a.k2_idx_red - b.k2_idx_red);
    if (!frArr.length) continue;

    // 首笔：同步维护“最高顶”与“最低底”，任一端刷新后立即重验净距与排他
    let S = null; // 当前笔起点分型
    let E = null; // 当前笔终点分型
    let haveFirstPen = false;

    let bestTop = null;
    let bestBottom = null;

    const tryMakeFirstPen = () => {
      if (!bestTop || !bestBottom) return false;
      // 自然决定方向：按左右顺序
      let candS = null, candE = null;
      if (bestBottom.k2_idx_red < bestTop.k2_idx_red) {
        candS = bestBottom; candE = bestTop;
      } else if (bestTop.k2_idx_red < bestBottom.k2_idx_red) {
        candS = bestTop; candE = bestBottom;
      } else {
        return false; // 同 rid 不可能成笔
      }
      if (!isOppositePair(candS, candE)) return false;

      // 先修极值（区间排他）
      const ex = exclusivityOK(candS, candE, frArr);
      if (!ex.ok) {
        if (ex.fix === "start" && ex.culprit) {
          if (candS.kind_enum === "top") {
            if (!bestTop || ex.culprit.k2_g_pri > bestTop.k2_g_pri) bestTop = ex.culprit;
          } else {
            if (!bestBottom || ex.culprit.k2_d_pri < bestBottom.k2_d_pri) bestBottom = ex.culprit;
          }
        } else if (ex.fix === "end" && ex.culprit) {
          if (candE.kind_enum === "top") {
            if (!bestTop || ex.culprit.k2_g_pri > bestTop.k2_g_pri) bestTop = ex.culprit;
          } else {
            if (!bestBottom || ex.culprit.k2_d_pri < bestBottom.k2_d_pri) bestBottom = ex.culprit;
          }
        }
        return false;
      }

      // 净距
      if (!gapOK(candS, candE)) return false;

      // 成笔
      const pen = buildPen(candS, candE, sid);
      pens.push(pen);
      S = candE; // 下一笔起点 = 本笔终点（首尾相连）
      E = null;
      haveFirstPen = true;
      return true;
    };

    for (let i = 0; i < frArr.length; i++) {
      const f = frArr[i];

      if (!haveFirstPen) {
        // 跟踪双向极值（严格更高顶/更低底；相等不更新）
        if (f.kind_enum === "top") {
          if (!bestTop || Number(f.k2_g_pri) > Number(bestTop.k2_g_pri)) {
            bestTop = f;
            // 端更新后立即尝试成笔
            tryMakeFirstPen();
          }
        } else {
          if (!bestBottom || Number(f.k2_d_pri) < Number(bestBottom.k2_d_pri)) {
            bestBottom = f;
            tryMakeFirstPen();
          }
        }
        continue;
      }

      // 常规阶段：已确定上一笔，当前笔起点 S 已定（=上一笔终点）
      // 方向由 S 决定：S=bottom -> UP；S=top -> DOWN
      const curDir = S.kind_enum === "bottom" ? "UP" : "DOWN";

      if (f.kind_enum === S.kind_enum) {
        // 起点方向分型：遇“更极值”则右移起点（相等不触发）
        if (
          (curDir === "UP" && Number(f.k2_d_pri) < Number(S.k2_d_pri)) ||
          (curDir === "DOWN" && Number(f.k2_g_pri) > Number(S.k2_g_pri))
        ) {
          S = f;
          // 首尾相连：同步上一笔终点 = 新起点；并向左回溯到稳定
          propagateToPreviousPens(S, sid, frArr);
          // 若终点在新起点左侧/被覆盖则清空 E
          if (E && Number(S.k2_idx_red) >= Number(E.k2_idx_red)) E = null;
        }
      } else {
        // 终点方向：初次赋值或遇“更极值”则替换终点
        if (!E) E = f;
        else {
          if (
            (curDir === "UP" && Number(f.k2_g_pri) > Number(E.k2_g_pri)) ||
            (curDir === "DOWN" && Number(f.k2_d_pri) < Number(E.k2_d_pri))
          ) {
            E = f;
          }
        }
      }

      // 每次 S/E 变化后，先修极值、再验三条
      if (E) {
        // 先修：区间排他
        const ex = exclusivityOK(S, E, frArr);
        if (!ex.ok) {
          if (ex.fix === "start" && ex.culprit) {
            S = ex.culprit;
            propagateToPreviousPens(S, sid, frArr);
            if (E && Number(S.k2_idx_red) >= Number(E.k2_idx_red)) E = null;
          } else if (ex.fix === "end" && ex.culprit) {
            E = ex.culprit;
          }
          // 修正后继续下一轮扫描
          continue;
        }

        // 三硬条件：1) 反向分型（由构造保证）；2) 净距；3) 排他（已通过）
        if (gapOK(S, E)) {
          // 在压入新笔前，首尾相连：上一笔终点 = 当前 S（若上一步未通过 propagate 同步）
          if (pens.length) {
            const prev = pens[pens.length - 1];
            if (Number(prev.seq_id) === Number(sid)) {
              if (Number(prev.end_idx_red) !== Number(S.k2_idx_red)) {
                prev.end_idx_red = Number(S.k2_idx_red);
                prev.end_idx_orig = Number(S.k2_idx_orig);
                const eBar = barAtRed(prev.end_idx_red);
                prev.end_g_pri = Number(eBar.g_pri);
                prev.end_d_pri = Number(eBar.d_pri);
                prev.end_y_pri = prev.dir_enum === "UP" ? prev.end_g_pri : prev.end_d_pri;
                prev.span_red_cnt_int = prev.end_idx_red - prev.start_idx_red;
              }
            }
          }
          // 压入当前笔
          const pen = buildPen(S, E, sid);
          pens.push(pen);
          // 下一笔：起点=本笔终点；清空 E；方向自然交替
          S = E;
          E = null;
        }
      }
    }
    // 本 seq 结束：无需输出“预备笔”，按规则仅返回最终已成的笔序列
  }

  return { confirmed: pens, provisional: null, all: pens };
}
