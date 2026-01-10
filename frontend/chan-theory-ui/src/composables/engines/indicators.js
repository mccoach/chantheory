// src/composables/engines/indicators.js
// ==============================
// 说明：指标计算引擎（纯函数，零副作用）
// 职责：根据K线数据和配置计算所有技术指标
//
// V2.2 - ATR 计算入口收敛为 buildAtrBundle（单一真相源）
// 改动：
//   - 不再在本文件内直接调用 calculateAtrStops；
//   - 改为调用 engines/atrBundle.buildAtrBundle 统一产出 TR/MATR/ATR_stop。
// ==============================

import {
  calculateMA,
  calculateMACD,
  calculateKDJ,
  calculateRSI,
  calculateBOLL,
} from "@/services/technicalIndicators";

import { DEFAULT_ATR_STOP_SETTINGS } from "@/constants";
import { buildAtrBundle } from "@/composables/engines/atrBundle"; // NEW

export function computeIndicators(candles, config) {
  if (!Array.isArray(candles) || candles.length === 0) {
    return {};
  }

  const closes = candles.map((c) => c.c);
  const highs = candles.map((c) => c.h);
  const lows = candles.map((c) => c.l);

  const result = {};

  // MA（仅计算已启用的）
  if (config.maPeriodsMap && config.maConfigs) {
    const enabledMA = {};
    Object.entries(config.maPeriodsMap).forEach(([key, period]) => {
      if (config.maConfigs[key]?.enabled) {
        enabledMA[key] = period;
      }
    });

    if (Object.keys(enabledMA).length > 0) {
      Object.assign(result, calculateMA(closes, enabledMA));
    }
  }

  // MACD（使用设置行给定的周期）
  if (config.useMACD) {
    const macdCfg = config.macdSettings || {};
    const period = macdCfg.period || {};
    const fast = Number(period.fast) || 12;
    const slow = Number(period.slow) || 26;
    const signal = Number(period.signal) || 9;

    Object.assign(result, calculateMACD(closes, fast, slow, signal));
  }

  // KDJ
  if (config.useKDJ) {
    Object.assign(result, calculateKDJ(highs, lows, closes));
  }

  // RSI
  if (config.useRSI) {
    Object.assign(result, calculateRSI(closes));
  }

  // BOLL
  if (config.useBOLL) {
    Object.assign(result, calculateBOLL(closes));
  }

  // ATR_stop + TR + MATR（TR/MATR 仅 tooltip 使用；是否出图由渲染层决定）
  {
    const s =
      config && config.atrStopSettings
        ? config.atrStopSettings
        : DEFAULT_ATR_STOP_SETTINGS;

    const userBasePriceRaw =
      config && Object.prototype.hasOwnProperty.call(config, "atrBasePrice")
        ? config.atrBasePrice
        : null;

    const bundle = buildAtrBundle(candles, s, userBasePriceRaw); // NEW

    result.ATR_TR = bundle.ATR_TR;

    result.MATR_FIXED_LONG = bundle.MATR_FIXED_LONG;
    result.MATR_FIXED_SHORT = bundle.MATR_FIXED_SHORT;
    result.MATR_CHAN_LONG = bundle.MATR_CHAN_LONG;
    result.MATR_CHAN_SHORT = bundle.MATR_CHAN_SHORT;

    result.ATR_FIXED_LONG = bundle.ATR_FIXED_LONG;
    result.ATR_FIXED_SHORT = bundle.ATR_FIXED_SHORT;
    result.ATR_CHAN_LONG = bundle.ATR_CHAN_LONG;
    result.ATR_CHAN_SHORT = bundle.ATR_CHAN_SHORT;
  }

  return result;
}
