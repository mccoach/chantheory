// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\barriers.js
// ==============================
// 说明：从 useChan.js 拆分出的连续性屏障检测模块
// - 核心职责：检测 K 线序列中的不连续点（屏障）。
//
// 业务规则摘要：
//   1) 判定对象：今开 / 昨收
//        prevC = C[i-1]
//        open  = O[i]
//        gapPct = (open - prevC) / prevC
//
//   2) 阈值：默认 CONTINUITY_BARRIER.basePct = 0.2（20%）；
//        当 |gapPct| >= basePct 时，认为在该日开盘前存在连续性屏障。
//
//   3) 新股豁免（利用真实交易日历）：
//      - 若提供上市日期 ipoYmd（YYYYMMDD 整数），
//        则从全局 trade_calendar 中取交易日序列：
//          * ipoIdx = index(date == ipoYmd)
//          * barIdx = index(date == ymd)
//          * 若 0 <= barIdx - ipoIdx < 7，则当前 bar 视为“上市后前 7 个交易日”之一，豁免；
//      - 若无法查到 trade_calendar 或 ipoYmd 缺失，则退回到“前7根K线豁免”（i < 7）。
//
//   4) 处理对象：始终作用于原始 K 线（candles），与合并 K 线无关。
// ==============================
import { CONTINUITY_BARRIER } from "@/constants";
import { timestampToYYYYMMDD } from "@/utils/timeParse";
import { useTradeCalendar } from "@/composables/useTradeCalendar";

/**
 * 连续性屏障检测
 *
 * @param {Array<object>} candles - 原始K线数组 [{ts,o,h,l,c,...},...]
 * @param {number} basePct        - 跳空阈值（相对比例，如 0.2=20%）；若未提供则使用 CONTINUITY_BARRIER.basePct
 * @param {object} [env]
 * @param {number} [env.ipoYmd]   - 上市日期（YYYYMMDD 整数）
 *
 * 返回：
 *   { set, list }
 *   - set : Set<number>，包含所有被判为屏障的 K 索引（屏障发生在该索引之前）
 *   - list: 调试信息数组 [{iLeft,iRight,gapPct,thrPct,ipoYmd}, ...]
 */
export function detectContinuityBarriers(candles, basePct, env = {}) {
  const set = new Set();
  const list = [];

  const n = Array.isArray(candles) ? candles.length : 0;
  if (n <= 1) return { set, list };

  const thr = Math.max(
    0,
    Number(CONTINUITY_BARRIER?.basePct ?? basePct ?? 0.2)
  );

  const ipoYmdRaw = Number(env?.ipoYmd);
  const hasIpoYmd =
    Number.isFinite(ipoYmdRaw) &&
    ipoYmdRaw > 19000000 &&
    ipoYmdRaw < 30000000;

  const tradeCal = useTradeCalendar();
  const canUseCalendar = tradeCal?.ready?.value && hasIpoYmd;

  // 诊断计数器
  let checkedCount = 0;
  let hitCount = 0;

  for (let i = 1; i < n; i++) {
    const barPrev = candles[i - 1];
    const barNow = candles[i];

    const prevC = Number(barPrev?.c);
    const openNow = Number(barNow?.o);

    if (!Number.isFinite(prevC) || prevC === 0) continue;
    if (!Number.isFinite(openNow)) continue;

    // IPO 豁免：优先使用真实交易日历；退化时使用 i < 7 的近似。
    if (canUseCalendar) {
      const ymd = timestampToYYYYMMDD(barNow.ts);
      if (Number.isFinite(ymd) && ymd >= ipoYmdRaw) {
        const within = tradeCal.isWithinNTradingDays({
          startYmd: ipoYmdRaw,
          endYmd: ymd,
          n: 7,
        });
        if (within) {
          continue;
        }
      }
    } else {
      if (i < 7) continue;
    }

    checkedCount += 1;  // NEW: 实际参与 gap 判定的 K 数量

    const gapPct = Math.abs((openNow - prevC) / prevC);

    if (gapPct >= thr) {
      hitCount += 1;    // NEW: 命中屏障的数量
      set.add(i);       // 屏障发生在 i 之前
      list.push({
        iLeft: i - 1,
        iRight: i,
        gapPct,
        thrPct: thr,
        ipoYmd: hasIpoYmd ? ipoYmdRaw : null,
      });
    }
  }

  // NEW: 诊断日志（仅 DEV 环境）
  if (import.meta.env.DEV) {
    console.log(
      "[Barriers] detectContinuityBarriers",
      "candles=", n,
      "checked=", checkedCount,
      "hits=", hitCount,
      "thr=", thr,
      "ipoYmd=", hasIpoYmd ? ipoYmdRaw : null
    );
  }

  return { set, list };
}