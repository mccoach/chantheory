// src/composables/engines/atrLines.js
// ==============================
// 说明：ATR止损线局部重算引擎（纯函数，零副作用）
// 职责：
//   - 为“实例侧最小 patch 更新”提供 ATR_stop 最终线（4条）的 data 数组；
//   - TR / MATR 属于 tooltip-only，不通过本模块输出给图形层。
//
// V2.1 - ATR 计算入口收敛为 buildAtrBundle（单一真相源）
// 改动：
//   - 不再直接调用 calculateAtrStops；
//   - 改为调用 engines/atrBundle.buildAtrBundle 统一产出，再取 ATR_* 四条。
// ==============================

import { buildAtrBundle } from "@/composables/engines/atrBundle"; // NEW

/**
 * @param {Array<object>} candles - [{o,h,l,c,...}, ...]
 * @param {object} args
 * @param {number|null} args.userBasePrice
 * @param {object} args.trCfg
 * @param {object} args.fixedLongCfg
 * @param {object} args.fixedShortCfg
 * @param {object} args.chanLongCfg
 * @param {object} args.chanShortCfg
 * @returns {{
 *   ATR_TR: Array<number|null>,
 *   ATR_FIXED_LONG: Array<number|null>,
 *   ATR_FIXED_SHORT: Array<number|null>,
 *   ATR_CHAN_LONG: Array<number|null>,
 *   ATR_CHAN_SHORT: Array<number|null>,
 * }}
 */
export function computeAtrLineSeries(candles, args = {}) {
  // 注意：本模块的契约是“局部 patch”，因此这里不做 settings 兜底合并；
  // 由调用方（MainChartControls）传入正确的各线 cfg（包含 enabled/atrPeriod/n/lookback 等）。
  // 但为保证“单一真相源”，计算入口仍统一收敛到 buildAtrBundle。

  // 将本模块入参 cfg 组装为 atrStopSettings 形态（与 DEFAULT_ATR_STOP_SETTINGS 对齐的结构）
  const atrStopSettings = {
    fixed: {
      long: args.fixedLongCfg || null,
      short: args.fixedShortCfg || null,
    },
    chandelier: {
      long: args.chanLongCfg || null,
      short: args.chanShortCfg || null,
    },
  };

  const bundle = buildAtrBundle(
    Array.isArray(candles) ? candles : [],
    atrStopSettings,
    args.userBasePrice ?? null
  );

  return {
    // 保持返回结构兼容（TR 虽不用于出图，但历史上本模块会返回；继续保留不产生额外副作用）
    ATR_TR: bundle.ATR_TR,

    ATR_FIXED_LONG: bundle.ATR_FIXED_LONG,
    ATR_FIXED_SHORT: bundle.ATR_FIXED_SHORT,
    ATR_CHAN_LONG: bundle.ATR_CHAN_LONG,
    ATR_CHAN_SHORT: bundle.ATR_CHAN_SHORT,
  };
}
