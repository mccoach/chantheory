// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\pivots.js
// ==============================
// 说明：笔中枢识别模块（Idx-Only 工程字段对齐版）
// - 核心职责：从笔序列中识别出笔中枢（矩形区域）。
// - 算法：按岛（seq_id）独立进行，采用P1~P4滑窗进行判定并向右延续。
//
// 本轮改造目标：
//   1) 修复旧实现对 pen.start_y_pri/end_y_pri 的依赖（该字段已被 Idx-Only 重构移除）
//   2) 改为通过 candles 回溯端点价计算笔价域（唯一真相源：candles）
//   3) 输出对齐工程字段范式：在 pivot 上新增紧前级别索引锚点 start_pen_idx/end_pen_idx
//
// Pivot Schema（本轮确定）：
//   - seq_id
//   - left_idx_orig, right_idx_orig
//   - upper, lower
//   - dir_enum
//   - start_pen_idx, end_pen_idx
// ==============================

import { toNonNegIntIdx } from "./common";
import { createChanAccessors } from "./accessors";

/**
 * 识别“笔中枢”（矩形）
 *
 * @param {Array<object>} candles - 原始K线（唯一真相源）
 * @param {Array<object>} pensConfirmed - 确认笔序列（Idx-Only）
 * @returns {Array<object>} pivots
 */
export function computePenPivots(candles, pensConfirmed) {
  const pivots = [];
  const pens = Array.isArray(pensConfirmed) ? pensConfirmed : [];
  if (!pens.length) return pivots;

  const acc = createChanAccessors(candles);

  // 按岛分组并按时间顺序排序（以 start_idx_orig）
  const bySeq = new Map();
  for (let pi = 0; pi < pens.length; pi++) {
    const p = pens[pi];
    const sid = Number(p?.seq_id || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push({ p, pi });
  }

  for (const [sid, arr] of bySeq.entries()) {
    const seqPens = (arr || [])
      .slice()
      .sort((a, b) => Number(a.p?.start_idx_orig) - Number(b.p?.start_idx_orig));

    if (seqPens.length < 4) continue;

    // 取单笔的“高/低”：通过 candles 回溯端点价得到价域
    const penHigh = (p) => {
      const r = acc.penRange(p);
      return r ? r.hi : NaN;
    };
    const penLow = (p) => {
      const r = acc.penRange(p);
      return r ? r.lo : NaN;
    };

    let i = 0;
    while (i + 3 < seqPens.length) {
      const P1 = seqPens[i];
      const P2 = seqPens[i + 1];
      const P3 = seqPens[i + 2];
      const P4 = seqPens[i + 3];

      // 上下沿（零厚度不成立）
      const upper = Math.min(penHigh(P2.p), penHigh(P4.p));
      const lower = Math.max(penLow(P2.p), penLow(P4.p));
      if (!(Number.isFinite(upper) && Number.isFinite(lower))) {
        i += 1;
        continue;
      }
      if (!(upper > lower)) {
        i += 1;
        continue; // 零厚度不成立
      }

      // P1“外部性”修改：必须在 P2-P4 的整体包络范围以外（严格不等）
      const p1StartRange = acc.penRange(P1.p);
      if (!p1StartRange) {
        i += 1;
        continue;
      }
      const p1Start = acc.penEndpointY(P1.p, "start");
      const envMax = Math.max(penHigh(P2.p), penHigh(P4.p));
      const envMin = Math.min(penLow(P2.p), penLow(P4.p));
      if (!Number.isFinite(p1Start) || !(p1Start > envMax || p1Start < envMin)) {
        i += 1;
        continue;
      }

      // 成立：记录左沿与方向（方向按 P1）
      const left_idx_orig = toNonNegIntIdx(P1.p?.end_idx_orig);
      const dir_enum = String(P1.p?.dir_enum || "").toUpperCase(); // 'UP'|'DOWN'
      if (left_idx_orig == null || (dir_enum !== "UP" && dir_enum !== "DOWN")) {
        i += 1;
        continue;
      }

      // 工程字段：中枢起始笔锚点（按触发窗 P1）
      const start_pen_idx = toNonNegIntIdx(P1.pi);
      if (start_pen_idx == null) {
        i += 1;
        continue;
      }

      let right_idx_orig = null;
      let end_pen_idx = null;

      // 延续：从 P5 开始
      let j = i + 4;
      let endedByOutside = false;

      while (j < seqPens.length) {
        const Pk = seqPens[j];
        const sY = acc.penEndpointY(Pk.p, "start");
        const eY = acc.penEndpointY(Pk.p, "end");
        if (!Number.isFinite(sY) || !Number.isFinite(eY)) {
          j += 1;
          continue;
        }

        // “完全在外”：起止两端都在上沿之上，或都在下沿之下（严格不等）
        const bothAbove = sY > upper && eY > upper;
        const bothBelow = sY < lower && eY < lower;

        if (bothAbove || bothBelow) {
          // 右沿 = 第一根完全在外笔的“起点”
          right_idx_orig = toNonNegIntIdx(Pk.p?.start_idx_orig);
          end_pen_idx = toNonNegIntIdx(Pk.pi);
          endedByOutside = true;
          break;
        }

        j += 1;
      }

      if (!endedByOutside) {
        // 未遇到完全在外：以本岛最后一笔的“终点”作为右沿
        const lastPenEntry = seqPens[seqPens.length - 1];
        right_idx_orig = toNonNegIntIdx(lastPenEntry?.p?.end_idx_orig ?? left_idx_orig);
        end_pen_idx = toNonNegIntIdx(lastPenEntry?.pi);
      }

      if (right_idx_orig == null || end_pen_idx == null) {
        i += 1;
        continue;
      }

      // 写入中枢（带紧前级别 pen idx 锚点）
      pivots.push({
        seq_id: Number(sid || 1),
        left_idx_orig,
        right_idx_orig,
        upper,
        lower,
        dir_enum,
        start_pen_idx,
        end_pen_idx,
      });

      // 下一次扫描从“完全在外”的那一笔（或末尾）作为新的 P1
      if (endedByOutside) {
        i = Math.max(0, j - 1);
      } else {
        break;
      }
    }
  }

  return pivots;
}
