// src/composables/engines/atrBundle.js
// ==============================
// V1.0 - ATR 结果包构建器（单一真相源入口）
//
// 目标：消除 ATR 计算双源：
//   - computeIndicators 与实例侧最小 patch（atrLines）不再各自调用 calculateAtrStops
//   - 统一通过 buildAtrBundle 生成 TR / MATR_* / ATR_*（stop）
//
// 约束：
//   - 纯函数、零副作用、无缓存、无全局状态（明确性优于隐晦性）
//   - TR/MATR 仅用于 tooltip：是否出图由上层决定；此模块只负责产出数据。
// ==============================

import { calculateAtrStops } from "@/services/technicalIndicators";
import { DEFAULT_ATR_STOP_SETTINGS } from "@/constants";

function asArray(x) {
  return Array.isArray(x) ? x : [];
}

function numOrNull(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
}

/**
 * 构建 ATR 相关全量序列（TR + MATR_* + ATR_stop_*）
 *
 * @param {Array<object>} candles - [{o,h,l,c,...}, ...]
 * @param {object|null} atrStopSettings - settings.chartDisplay.atrStopSettings
 * @param {number|null} atrBasePrice - settings.preferences.atrBasePrice（允许 null 表示“自动对齐”由上层处理）
 * @returns {{
 *   ATR_TR: Array<number|null>,
 *   MATR_FIXED_LONG: Array<number|null>,
 *   MATR_FIXED_SHORT: Array<number|null>,
 *   MATR_CHAN_LONG: Array<number|null>,
 *   MATR_CHAN_SHORT: Array<number|null>,
 *   ATR_FIXED_LONG: Array<number|null>,
 *   ATR_FIXED_SHORT: Array<number|null>,
 *   ATR_CHAN_LONG: Array<number|null>,
 *   ATR_CHAN_SHORT: Array<number|null>,
 * }}
 */
export function buildAtrBundle(candles, atrStopSettings, atrBasePrice) {
  const arr = asArray(candles);

  const opens = arr.map((d) => d?.o);
  const highs = arr.map((d) => d?.h);
  const lows = arr.map((d) => d?.l);
  const closes = arr.map((d) => d?.c);

  const latestClose =
    arr.length > 0 ? numOrNull(arr[arr.length - 1]?.c) : null;

  const s =
    atrStopSettings && typeof atrStopSettings === "object"
      ? atrStopSettings
      : DEFAULT_ATR_STOP_SETTINGS;

  const userBasePrice = numOrNull(atrBasePrice);

  const out = calculateAtrStops(opens, highs, lows, closes, {
    latestClose,
    userBasePrice,

    fixedLongCfg: s?.fixed?.long || DEFAULT_ATR_STOP_SETTINGS.fixed.long,
    fixedShortCfg: s?.fixed?.short || DEFAULT_ATR_STOP_SETTINGS.fixed.short,

    chanLongCfg:
      s?.chandelier?.long || DEFAULT_ATR_STOP_SETTINGS.chandelier.long,
    chanShortCfg:
      s?.chandelier?.short || DEFAULT_ATR_STOP_SETTINGS.chandelier.short,
  });

  return {
    ATR_TR: Array.isArray(out?.ATR_TR) ? out.ATR_TR : [],

    MATR_FIXED_LONG: Array.isArray(out?.MATR_FIXED_LONG) ? out.MATR_FIXED_LONG : [],
    MATR_FIXED_SHORT: Array.isArray(out?.MATR_FIXED_SHORT) ? out.MATR_FIXED_SHORT : [],
    MATR_CHAN_LONG: Array.isArray(out?.MATR_CHAN_LONG) ? out.MATR_CHAN_LONG : [],
    MATR_CHAN_SHORT: Array.isArray(out?.MATR_CHAN_SHORT) ? out.MATR_CHAN_SHORT : [],

    ATR_FIXED_LONG: Array.isArray(out?.ATR_FIXED_LONG) ? out.ATR_FIXED_LONG : [],
    ATR_FIXED_SHORT: Array.isArray(out?.ATR_FIXED_SHORT) ? out.ATR_FIXED_SHORT : [],
    ATR_CHAN_LONG: Array.isArray(out?.ATR_CHAN_LONG) ? out.ATR_CHAN_LONG : [],
    ATR_CHAN_SHORT: Array.isArray(out?.ATR_CHAN_SHORT) ? out.ATR_CHAN_SHORT : [],
  };
}
