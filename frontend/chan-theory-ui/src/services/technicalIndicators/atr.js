// src/services/technicalIndicators/atr.js
// ==============================
// 说明：ATR（TR + ATR）与 ATR止损线（固定倍数 / 波动通道）
// - 数据源：原始K（open/high/low/close）
// - 纯函数，零副作用
// - ATR = SMA(TR, atrPeriod)（可按各线独立周期计算）
//
// V2.1 - CHANGED: MATR 严格不共用、严格随对应止损线开关计算
//   - TR（单根真实波动幅度）必算（始终计算）
//   - MATR（TR 的 SMA）是中间量：仅在计算对应最终止损价线时才计算
//   - 四条止损线（倍-多/空、波-多/空）各自拥有独立 MATR 计算过程：不做跨线复用/缓存
// ==============================

function toNum(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
}

function sma(arr, n) {
  const N = Math.max(1, Math.floor(Number(n || 1)));
  const out = new Array(arr.length).fill(null);
  if (!Array.isArray(arr) || !arr.length) return out;

  let sum = 0;
  let cnt = 0;

  for (let i = 0; i < arr.length; i++) {
    const v = toNum(arr[i]);
    if (v != null) {
      sum += v;
      cnt += 1;
    }

    if (i >= N) {
      const ov = toNum(arr[i - N]);
      if (ov != null) {
        sum -= ov;
        cnt -= 1;
      }
    }

    out[i] = i >= N - 1 && cnt > 0 ? sum / cnt : null;
  }

  return out;
}

function rollingExtreme(arr, lookback, mode) {
  const N = Math.max(1, Math.floor(Number(lookback || 1)));
  const out = new Array(arr.length).fill(null);
  if (!Array.isArray(arr) || !arr.length) return out;

  for (let i = 0; i < arr.length; i++) {
    const s = Math.max(0, i - N + 1);
    let best = mode === "min" ? Infinity : -Infinity;
    let has = false;

    for (let j = s; j <= i; j++) {
      const v = toNum(arr[j]);
      if (v == null) continue;
      has = true;
      if (mode === "min") best = Math.min(best, v);
      else best = Math.max(best, v);
    }

    out[i] = has ? best : null;
  }

  return out;
}

function fillConst(n, value) {
  const v = toNum(value);
  if (v == null) return new Array(n).fill(null);
  const out = new Array(n);
  for (let i = 0; i < n; i++) out[i] = v;
  return out;
}

function calculateTR(highs, lows, closes) {
  const H = Array.isArray(highs) ? highs : [];
  const L = Array.isArray(lows) ? lows : [];
  const C = Array.isArray(closes) ? closes : [];

  const n0 = Math.min(H.length, L.length, C.length);
  const tr = new Array(n0).fill(null);

  for (let i = 0; i < n0; i++) {
    const hi = toNum(H[i]);
    const lo = toNum(L[i]);
    if (hi == null || lo == null) continue;

    const prevC = i > 0 ? toNum(C[i - 1]) : null;

    const r1 = hi - lo;
    const r2 = prevC == null ? null : Math.abs(hi - prevC);
    const r3 = prevC == null ? null : Math.abs(lo - prevC);

    let best = r1;
    if (r2 != null) best = Math.max(best, r2);
    if (r3 != null) best = Math.max(best, r3);

    tr[i] = Number.isFinite(best) ? best : null;
  }

  return tr;
}

/**
 * @param {Array<number>} opens
 * @param {Array<number>} highs
 * @param {Array<number>} lows
 * @param {Array<number>} closes
 * @param {object} args
 * @param {number|null} args.latestClose
 * @param {number|null} args.userBasePrice
 * @param {object|null} args.fixedLongCfg
 * @param {object|null} args.fixedShortCfg
 * @param {object|null} args.chanLongCfg
 * @param {object|null} args.chanShortCfg
 * @returns {{
 *   ATR_TR: Array<number|null>,
 *   // MATR（仅 tooltip 使用；不用于绘制）
 *   MATR_FIXED_LONG: Array<number|null>,
 *   MATR_FIXED_SHORT: Array<number|null>,
 *   MATR_CHAN_LONG: Array<number|null>,
 *   MATR_CHAN_SHORT: Array<number|null>,
 *   // ATR_stop（最终止损价）
 *   ATR_FIXED_LONG: Array<number|null>,
 *   ATR_FIXED_SHORT: Array<number|null>,
 *   ATR_CHAN_LONG: Array<number|null>,
 *   ATR_CHAN_SHORT: Array<number|null>,
 * }}
 */
export function calculateAtrStops(opens, highs, lows, closes, args = {}) {
  const O = Array.isArray(opens) ? opens : [];
  const H = Array.isArray(highs) ? highs : [];
  const L = Array.isArray(lows) ? lows : [];
  const C = Array.isArray(closes) ? closes : [];

  const n0 = Math.min(O.length, H.length, L.length, C.length);

  // TR 必算：单根原始K的真实波动幅度
  const tr = calculateTR(H, L, C);

  function resolveBasePrice(mode) {
    const m = String(mode || "user");
    if (m === "latest_close") return toNum(args.latestClose);
    return toNum(args.userBasePrice);
  }

  // ===== 输出数组（默认全 null）=====
  const fixedLong = new Array(n0).fill(null);
  const fixedShort = new Array(n0).fill(null);
  const chanLong = new Array(n0).fill(null);
  const chanShort = new Array(n0).fill(null);

  // ===== MATR_*（默认全 null；仅当对应线 enabled 时才计算并填充；且不共用）=====
  const matrFixedLong = new Array(n0).fill(null);
  const matrFixedShort = new Array(n0).fill(null);
  const matrChanLong = new Array(n0).fill(null);
  const matrChanShort = new Array(n0).fill(null);

  // ===== 固定倍数（多）：bp - n*MATR =====
  {
    const cfg = args.fixedLongCfg || {};
    if (cfg.enabled === true) {
      const period = Number.isFinite(+cfg.atrPeriod) ? Math.max(1, Math.floor(+cfg.atrPeriod)) : 14;

      // MATR（该线独立计算，不共用）
      const matr = sma(tr, period);
      for (let i = 0; i < n0; i++) matrFixedLong[i] = matr[i];

      const n = Number.isFinite(+cfg.n) ? +cfg.n : 2;
      const base = fillConst(n0, resolveBasePrice(cfg.basePriceMode));
      for (let i = 0; i < n0; i++) {
        const m = toNum(matr[i]);
        const bp = toNum(base[i]);
        if (m == null || bp == null) continue;
        fixedLong[i] = Math.max(0, bp - n * m);
      }
    }
  }

  // ===== 固定倍数（空）：bp + n*MATR =====
  {
    const cfg = args.fixedShortCfg || {};
    if (cfg.enabled === true) {
      const period = Number.isFinite(+cfg.atrPeriod) ? Math.max(1, Math.floor(+cfg.atrPeriod)) : 14;

      const matr = sma(tr, period);
      for (let i = 0; i < n0; i++) matrFixedShort[i] = matr[i];

      const n = Number.isFinite(+cfg.n) ? +cfg.n : 2;
      const base = fillConst(n0, resolveBasePrice(cfg.basePriceMode));
      for (let i = 0; i < n0; i++) {
        const m = toNum(matr[i]);
        const bp = toNum(base[i]);
        if (m == null || bp == null) continue;
        fixedShort[i] = Math.max(0, bp + n * m);
      }
    }
  }

  // ===== 波动通道（多）：HH(lookback) - n*MATR =====
  {
    const cfg = args.chanLongCfg || {};
    if (cfg.enabled === true) {
      const period = Number.isFinite(+cfg.atrPeriod) ? Math.max(1, Math.floor(+cfg.atrPeriod)) : 14;

      const matr = sma(tr, period);
      for (let i = 0; i < n0; i++) matrChanLong[i] = matr[i];

      const n = Number.isFinite(+cfg.n) ? +cfg.n : 2.5;
      const lookback = Number.isFinite(+cfg.lookback) ? Math.max(1, Math.floor(+cfg.lookback)) : 22;
      const hh = rollingExtreme(H, lookback, "max");
      for (let i = 0; i < n0; i++) {
        const m = toNum(matr[i]);
        const hhi = toNum(hh[i]);
        if (m == null || hhi == null) continue;
        chanLong[i] = Math.max(0, hhi - n * m);
      }
    }
  }

  // ===== 波动通道（空）：LL(lookback) + n*MATR =====
  {
    const cfg = args.chanShortCfg || {};
    if (cfg.enabled === true) {
      const period = Number.isFinite(+cfg.atrPeriod) ? Math.max(1, Math.floor(+cfg.atrPeriod)) : 14;

      const matr = sma(tr, period);
      for (let i = 0; i < n0; i++) matrChanShort[i] = matr[i];

      const n = Number.isFinite(+cfg.n) ? +cfg.n : 2.5;
      const lookback = Number.isFinite(+cfg.lookback) ? Math.max(1, Math.floor(+cfg.lookback)) : 22;
      const ll = rollingExtreme(L, lookback, "min");
      for (let i = 0; i < n0; i++) {
        const m = toNum(matr[i]);
        const lli = toNum(ll[i]);
        if (m == null || lli == null) continue;
        chanShort[i] = Math.max(0, lli + n * m);
      }
    }
  }

  return {
    ATR_TR: tr,

    MATR_FIXED_LONG: matrFixedLong,
    MATR_FIXED_SHORT: matrFixedShort,
    MATR_CHAN_LONG: matrChanLong,
    MATR_CHAN_SHORT: matrChanShort,

    ATR_FIXED_LONG: fixedLong,
    ATR_FIXED_SHORT: fixedShort,
    ATR_CHAN_LONG: chanLong,
    ATR_CHAN_SHORT: chanShort,
  };
}
