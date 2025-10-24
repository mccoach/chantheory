// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\barriers.js
// ==============================
// 说明：从 useChan.js 拆分出的连续性屏障检测模块
// - 核心职责：检测 K 线序列中的不连续点（屏障）。
// - 算法：基于相邻K线的价格跳空百分比，与一个静态阈值比较。
// ==============================

import { CONTINUITY_BARRIER } from "@/constants";

/**
 * 连续性屏障检测（静态阈值版）
 * 规则：
 *  - 仅在 i>=10（前10个交易日豁免）时开始检测；
 *  - 取前一日收盘 prevC 与当日最高/最低 thisH/thisL；
 *  - 计算 risePct = |(thisH - prevC) / prevC|，dropPct = |(prevC - thisL) / prevC|；
 *  - 两者任一 ≥ basePct 则在 i 之前判定为屏障（set.add(i)）。
 * 返回：{ set, list }，list含调试信息。
 */
export function detectContinuityBarriers(candles, basePct) {
  const set = new Set();
  const list = [];
  const n = Array.isArray(candles) ? candles.length : 0;
  const thr = Math.max(0, Number(CONTINUITY_BARRIER?.basePct ?? basePct ?? 0.15));

  const C = (i) => Number(candles[i]?.c);
  const H = (i) => Number(candles[i]?.h ?? candles[i]?.high);
  const L = (i) => Number(candles[i]?.l ?? candles[i]?.low);

  for (let i = 1; i < n; i++) {
    // 前10个交易日视为连续（从第11个开始比对）
    if (i < 10) continue;
    const prevC = C(i - 1);
    const thisH = H(i);
    const thisL = L(i);
    if (!Number.isFinite(prevC) || prevC === 0) continue;
    if (!Number.isFinite(thisH) || !Number.isFinite(thisL)) continue;

    const risePct = Math.abs((thisH - prevC) / prevC);
    const dropPct = Math.abs((prevC - thisL) / prevC);
    if (risePct >= thr || dropPct >= thr) {
      set.add(i); // 屏障发生在 i 之前
      list.push({ iLeft: i - 1, iRight: i, risePct, dropPct, thrPct: thr });
    }
  }
  return { set, list };
}
