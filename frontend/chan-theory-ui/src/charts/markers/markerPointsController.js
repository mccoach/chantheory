// src/charts/markers/markerPointsController.js
// ==============================
// 说明：量窗放/缩量标记点集控制器（实例侧）
// - 职责：基于当前 dataZoom 可见范围，计算放/缩量 marker 点集，并做最小 patch 更新。
// - 设计：rAF 节流；只扫描可见区间；不依赖 finished；宽度由 WidthController 管理。
//
// V2.2 - 高并发减负：支持外部注入 zoomRange，避免 dataZoom 高频下 chart.getOption() 反解
// 改动：
//   - 新增 setZoomRange({sIdx,eIdx})
//   - computeVisiblePoints 优先使用注入的 zoomRange，否则 fallback safeGetZoomRange()
// ==============================

function safeGetZoomRange(chart, len) {
  try {
    const opt = chart?.getOption?.();
    const dz = Array.isArray(opt?.dataZoom) ? opt.dataZoom : [];
    const inside = dz.find(
      (z) =>
        z &&
        typeof z.startValue !== "undefined" &&
        typeof z.endValue !== "undefined"
    );

    if (inside) {
      const s = Number(inside.startValue);
      const e = Number(inside.endValue);
      if (Number.isFinite(s) && Number.isFinite(e)) {
        const sIdx = Math.max(0, Math.min(len - 1, Math.floor(Math.min(s, e))));
        const eIdx = Math.max(0, Math.min(len - 1, Math.floor(Math.max(s, e))));
        return { sIdx, eIdx };
      }
    }
  } catch {}

  return { sIdx: 0, eIdx: Math.max(0, len - 1) };
}

function smaAt(i, n, prefixSum) {
  if (i < n - 1) return null;
  const a = prefixSum[i] - (i - n >= 0 ? prefixSum[i - n] : 0);
  return a / n;
}

function buildPrefixSum(arr) {
  const out = new Array(arr.length);
  let sum = 0;
  for (let i = 0; i < arr.length; i++) {
    const v = Number(arr[i]);
    if (Number.isFinite(v)) sum += v;
    out[i] = sum;
  }
  return out;
}

function downSamplePoints(points, maxN) {
  const arr = Array.isArray(points) ? points : [];
  const n = arr.length;
  const cap = Math.max(1, Number(maxN || 1));
  if (n <= cap) return arr;

  const out = [];
  const step = Math.ceil(n / cap);
  for (let i = 0; i < n; i += step) out.push(arr[i]);

  const last = arr[n - 1];
  if (out.length && out[out.length - 1] !== last) out.push(last);
  return out;
}

function hashPoints(points) {
  const arr = Array.isArray(points) ? points : [];
  let h = 2166136261;
  for (let i = 0; i < arr.length; i++) {
    const p = arr[i];
    const x = Array.isArray(p) ? Number(p[0]) : NaN;
    if (!Number.isFinite(x)) continue;
    h ^= x | 0;
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function createVolumeMarkerPointsController({
  chart,
  getCandles,
  getVolCfg,
  getBaseSeries,
}) {
  if (!chart) throw new Error("[MarkerPointsController] chart is required");

  let disposed = false;
  let rafId = null;

  let _lastBaseRef = null;
  let _lastBaseLen = 0;
  let _prefixSum = null;

  let _lastSig = null;

  // NEW: 外部注入的 zoomRange（优先使用，避免 dataZoom 高频 getOption）
  let _zoomS = null;
  let _zoomE = null;

  const MAX_MARKERS_PER_SERIES = 4000;

  function ensurePrefixSum(base) {
    if (!Array.isArray(base) || !base.length) {
      _lastBaseRef = null;
      _lastBaseLen = 0;
      _prefixSum = null;
      return;
    }
    if (base === _lastBaseRef && _prefixSum && _lastBaseLen === base.length) return;

    _lastBaseRef = base;
    _lastBaseLen = base.length;
    _prefixSum = buildPrefixSum(base);
  }

  function pickMinEnabledPeriod(mavolStyles) {
    let minP = null;
    const obj = mavolStyles && typeof mavolStyles === "object" ? mavolStyles : {};
    for (const v of Object.values(obj)) {
      if (!v || v.enabled !== true) continue;
      const p = Number(v.period);
      if (!Number.isFinite(p) || p <= 0) continue;
      if (minP == null || p < minP) minP = p;
    }
    return minP;
  }

  function normalizeZoomRangeFromInjected(len) {
    if (!Number.isFinite(_zoomS) || !Number.isFinite(_zoomE)) return null;
    const s = Math.max(0, Math.min(len - 1, Math.floor(Math.min(_zoomS, _zoomE))));
    const e = Math.max(0, Math.min(len - 1, Math.floor(Math.max(_zoomS, _zoomE))));
    return { sIdx: s, eIdx: e };
  }

  function computeVisiblePoints() {
    const candles = typeof getCandles === "function" ? getCandles() : [];
    const base = typeof getBaseSeries === "function" ? getBaseSeries() : null;
    const cfg = typeof getVolCfg === "function" ? getVolCfg() : {};

    const len = Array.isArray(candles) ? candles.length : 0;
    if (!len || !Array.isArray(base) || base.length !== len) {
      return { pump: [], dump: [], sig: null };
    }

    const pumpOn = (cfg?.markerPump?.enabled ?? true) === true;
    const dumpOn = (cfg?.markerDump?.enabled ?? true) === true;

    const primN = pickMinEnabledPeriod(cfg?.mavolStyles);
    const pumpK = Number.isFinite(+cfg?.markerPump?.threshold) ? +cfg.markerPump.threshold : 1.5;
    const dumpK = Number.isFinite(+cfg?.markerDump?.threshold) ? +cfg.markerDump.threshold : 0.7;

    // NEW: 优先使用注入的 zoomRange
    const injected = normalizeZoomRangeFromInjected(len);
    const zr = injected || safeGetZoomRange(chart, len);
    const sIdx = zr.sIdx;
    const eIdx = zr.eIdx;

    const sigBase = {
      baseRef: base,
      len,
      sIdx,
      eIdx,
      primN: primN || 0,
      pumpOn: pumpOn ? 1 : 0,
      dumpOn: dumpOn ? 1 : 0,
      pumpK,
      dumpK,
    };

    if ((!pumpOn && !dumpOn) || !primN) {
      return {
        pump: [],
        dump: [],
        sig: { ...sigBase, pumpHash: 0, dumpHash: 0, pumpCount: 0, dumpCount: 0 },
      };
    }

    ensurePrefixSum(base);

    const pumpPts = [];
    const dumpPts = [];

    for (let i = sIdx; i <= eIdx; i++) {
      const v = Number(base[i]);
      if (!Number.isFinite(v)) continue;

      const m = _prefixSum ? smaAt(i, primN, _prefixSum) : null;
      if (!Number.isFinite(m) || m <= 0) continue;

      if (pumpOn && pumpK > 0 && v >= pumpK * m) pumpPts.push([i, 0]);
      if (dumpOn && dumpK > 0 && v <= dumpK * m) dumpPts.push([i, 0]);
    }

    const pumpFinal = downSamplePoints(pumpPts, MAX_MARKERS_PER_SERIES);
    const dumpFinal = downSamplePoints(dumpPts, MAX_MARKERS_PER_SERIES);

    const sig = {
      ...sigBase,
      pumpHash: hashPoints(pumpFinal),
      dumpHash: hashPoints(dumpFinal),
      pumpCount: pumpFinal.length,
      dumpCount: dumpFinal.length,
    };

    return { pump: pumpFinal, dump: dumpFinal, sig };
  }

  function patchSeriesData({ pump, dump }) {
    const series = [
      { id: "VOL_PUMP_MARK", data: Array.isArray(pump) ? pump : [] },
      { id: "VOL_DUMP_MARK", data: Array.isArray(dump) ? dump : [] },
    ];
    try {
      chart.setOption({ series }, { notMerge: false, silent: true });
    } catch {}
  }

  function sameSig(a, b) {
    if (!a || !b) return false;
    return (
      a.baseRef === b.baseRef &&
      a.len === b.len &&
      a.sIdx === b.sIdx &&
      a.eIdx === b.eIdx &&
      a.primN === b.primN &&
      a.pumpOn === b.pumpOn &&
      a.dumpOn === b.dumpOn &&
      a.pumpK === b.pumpK &&
      a.dumpK === b.dumpK &&
      a.pumpHash === b.pumpHash &&
      a.dumpHash === b.dumpHash &&
      a.pumpCount === b.pumpCount &&
      a.dumpCount === b.dumpCount
    );
  }

  function runOnce() {
    if (disposed) return;

    const { pump, dump, sig } = computeVisiblePoints();
    if (sameSig(_lastSig, sig)) return;

    _lastSig = sig;
    patchSeriesData({ pump, dump });
  }

  function scheduleUpdate() {
    if (disposed) return;
    if (rafId != null) return;
    rafId = requestAnimationFrame(() => {
      rafId = null;
      runOnce();
    });
  }

  // NEW: 注入 zoomRange（仅存储，不触发计算）
  function setZoomRange({ sIdx, eIdx } = {}) {
    if (disposed) return;
    const s = Number(sIdx);
    const e = Number(eIdx);
    if (!Number.isFinite(s) || !Number.isFinite(e)) {
      _zoomS = null;
      _zoomE = null;
      return;
    }
    _zoomS = s;
    _zoomE = e;
  }

  function dispose() {
    disposed = true;
    if (rafId != null) {
      try {
        cancelAnimationFrame(rafId);
      } catch {}
      rafId = null;
    }
    _lastBaseRef = null;
    _lastBaseLen = 0;
    _prefixSum = null;
    _lastSig = null;
    _zoomS = null;
    _zoomE = null;
  }

  return { scheduleUpdate, setZoomRange, dispose };
}
