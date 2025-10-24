// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\pivots.js
// ==============================
// 说明：从 useChan.js 拆分出的笔中枢识别模块
// - 核心职责：从笔序列中识别出笔中枢（矩形区域）。
// - 算法：按岛（seq_id）独立进行，采用P1~P4滑窗进行判定并向右延续。
// ==============================

/**
 * 识别“笔中枢”（矩形）
 */
export function computePenPivots(pensConfirmed) {
  const pivots = [];
  const pens = Array.isArray(pensConfirmed) ? pensConfirmed : [];
  if (!pens.length) return pivots;

  // 按岛分组并按时间顺序排序（以 start_idx_orig）
  const bySeq = new Map();
  for (const p of pens) {
    const sid = Number(p?.seq_id || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push(p);
  }
  for (const [sid, arr] of bySeq.entries()) {
    const seqPens = (arr || []).slice().sort((a, b) => a.start_idx_orig - b.start_idx_orig);
    if (seqPens.length < 4) continue;

    // 取单笔的“高/低”：采用最终笔端点输出（唯一真相源），避免中间推导
    const penHigh = (p) => Math.max(Number(p.start_y_pri), Number(p.end_y_pri));
    const penLow = (p) => Math.min(Number(p.start_y_pri), Number(p.end_y_pri));

    let i = 0;
    while (i + 3 < seqPens.length) {
      const P1 = seqPens[i];
      const P2 = seqPens[i + 1];
      const P3 = seqPens[i + 2];
      const P4 = seqPens[i + 3];

      // 上下沿（零厚度不成立）
      const upper = Math.min(penHigh(P2), penHigh(P4));
      const lower = Math.max(penLow(P2), penLow(P4));
      if (!(Number.isFinite(upper) && Number.isFinite(lower))) {
        i += 1;
        continue;
      }
      if (!(upper > lower)) {
        i += 1;
        continue; // 零厚度不成立
      }

      // P1“外部性”修改：必须在 P2-P4 的整体包络范围以外（严格不等）
      const p1Start = Number(P1.start_y_pri);
      const envMax = Math.max(penHigh(P2), penHigh(P4));
      const envMin = Math.min(penLow(P2), penLow(P4));
      if (!Number.isFinite(p1Start) || !(p1Start > envMax || p1Start < envMin)) {
        i += 1;
        continue;
      }

      // 成立：记录左沿与方向（方向按 P1）
      const left_idx_orig = Number(P1.end_idx_orig);
      const dir_enum = String(P1?.dir_enum || "").toUpperCase(); // 'UP'|'DOWN'
      let right_idx_orig = null;

      // 延续：从 P5 开始
      let j = i + 4;
      let endedByOutside = false;
      while (j < seqPens.length) {
        const Pk = seqPens[j];
        const sY = Number(Pk.start_y_pri);
        const eY = Number(Pk.end_y_pri);
        if (!Number.isFinite(sY) || !Number.isFinite(eY)) {
          j += 1;
          continue;
        }
        // “完全在外”：起止两端都在上沿之上，或都在下沿之下（严格不等）
        const bothAbove = sY > upper && eY > upper;
        const bothBelow = sY < lower && eY < lower;
        if (bothAbove || bothBelow) {
          right_idx_orig = Number(Pk.start_idx_orig); // 右沿 = 第一根完全在外笔的“起点”
          endedByOutside = true;
          break;
        }
        j += 1;
      }
      if (!endedByOutside) {
        // 未遇到完全在外：以本岛最后一笔的“终点”作为右沿
        const lastPen = seqPens[seqPens.length - 1];
        right_idx_orig = Number(lastPen?.end_idx_orig ?? left_idx_orig);
      }

      // 写入中枢
      pivots.push({
        seq_id: sid,
        left_idx_orig,
        right_idx_orig,
        upper,
        lower,
        dir_enum, // 'UP'|'DOWN'
      });

      // 下一次扫描从“完全在外”的那一笔（或末尾）作为新的 P1
      if (endedByOutside) {
        // i 跳到 j - 1（该笔作为新的 P1）
        i = Math.max(0, j - 1);
      } else {
        // 已到岛末尾
        break;
      }
    }
  }

  return pivots;
}