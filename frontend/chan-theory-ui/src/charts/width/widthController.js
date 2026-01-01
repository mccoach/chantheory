// src/charts/width/widthController.js
// ==============================
// 说明：通用“宽度控制器”
// - 职责：在 ECharts 实例侧，根据当前视野估算宽度，写入 widthState，并触发最小重绘。
// - 设计：
//   * rAF 节流；
//   * widthState 单一真相源；
//   * 空 patch 触发 symbolSize 重算；
//   * 仅对存在的 series id 做 patch；
//   * refreshSeriesIds 支持动态 getter；
//   * 宽度未变则不写/不 patch；
//   * 仅写入变化的 key（delta set）。
//
// V2.4 - 高并发减负：支持外部注入 zoomRange，避免 dataZoom 高频下 chart.getOption() 反解
// 改动：
//   - 新增 setZoomRange({sIdx,eIdx})
//   - estimateBaseBarWidthPx 优先使用注入的 zoomRange，否则 fallback safeGetZoomRange
// ==============================

import { setWidthPxBatch } from "@/charts/width/widthState";

function clamp(n, min, max) {
  const x = Number(n);
  if (!Number.isFinite(x)) return min;
  return Math.max(min, Math.min(max, x));
}

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

function normalizeZoomRange(zoomRange, len) {
  if (!zoomRange) return null;
  const s0 = Number(zoomRange.sIdx);
  const e0 = Number(zoomRange.eIdx);
  if (!Number.isFinite(s0) || !Number.isFinite(e0) || len <= 0) return null;

  const sIdx = Math.max(0, Math.min(len - 1, Math.floor(Math.min(s0, e0))));
  const eIdx = Math.max(0, Math.min(len - 1, Math.floor(Math.max(s0, e0))));
  return { sIdx, eIdx };
}

function readBarPercentFromMainOption(chart, fallback = 88) {
  try {
    const opt = chart?.getOption?.();
    const seriesArr = Array.isArray(opt?.series) ? opt.series : [];
    const k = seriesArr.find((s) => String(s?.type || "") === "candlestick");
    const bw = k?.barWidth;
    if (typeof bw === "string" && bw.endsWith("%")) {
      const n = Number(bw.slice(0, -1));
      if (Number.isFinite(n)) return clamp(Math.round(n), 10, 100);
    }
  } catch {}
  return clamp(Math.round(Number(fallback)), 10, 100);
}

function estimateBaseBarWidthPx({ chart, candlesLen, barPercent, zoomRange }) {
  const len = Math.max(0, Number(candlesLen || 0));
  if (!len) return null;

  const zr = normalizeZoomRange(zoomRange, len) || safeGetZoomRange(chart, len);
  const vis = Math.max(1, zr.eIdx - zr.sIdx + 1);

  const chartW = Number(chart?.getWidth?.() || 0);
  if (!Number.isFinite(chartW) || chartW <= 0) return null;

  const approxStepPx = chartW / vis;
  const bp = clamp(Math.round(Number(barPercent)), 10, 100);
  const barWidthPxStar = approxStepPx * (bp / 100);

  return barWidthPxStar;
}

function normalizeRefreshIds(refreshSeriesIds) {
  if (typeof refreshSeriesIds === "function") {
    try {
      const v = refreshSeriesIds();
      return Array.isArray(v) ? v : [];
    } catch {
      return [];
    }
  }
  return Array.isArray(refreshSeriesIds) ? refreshSeriesIds : [];
}

function nearlyEqual(a, b, eps) {
  if (!Number.isFinite(a) || !Number.isFinite(b)) return false;
  return Math.abs(a - b) <= eps;
}

export function createWidthController({
  chart,
  getCandlesLen,
  getBarPercent,
  targets,
  refreshSeriesIds,
}) {
  if (!chart) throw new Error("[WidthController] chart is required");

  let disposed = false;
  let rafId = null;

  const lastWidthByKey = new Map();
  const EPS = 0.1;

  // NEW: 外部注入的 zoomRange（优先使用，避免 dataZoom 高频 getOption）
  let _zoomS = null;
  let _zoomE = null;

  function computeAndStoreDelta() {
    const len = Number(getCandlesLen?.() || 0);
    if (!Number.isFinite(len) || len <= 0) return null;

    const bp = Number(getBarPercent?.() || 88);

    const injectedRange =
      Number.isFinite(_zoomS) && Number.isFinite(_zoomE)
        ? { sIdx: _zoomS, eIdx: _zoomE }
        : null;

    const baseBarW = estimateBaseBarWidthPx({
      chart,
      candlesLen: len,
      barPercent: bp,
      zoomRange: injectedRange,
    });

    if (!Number.isFinite(baseBarW) || baseBarW <= 0) return null;

    const list = Array.isArray(targets) ? targets : [];

    const delta = {};
    let changed = false;

    for (const t of list) {
      const key = String(t?.key || "").trim();
      if (!key) continue;

      const mpRaw = Number(typeof t.percent === "function" ? t.percent() : NaN);
      const mp = clamp(Math.round(mpRaw), 50, 100);

      let w = baseBarW * (mp / 100);

      if (t?.capToBar !== false) {
        w = Math.min(w, baseBarW);
      }

      const minPx = Number.isFinite(+t.minPx) ? +t.minPx : 1;
      const maxPx = Number.isFinite(+t.maxPx) ? +t.maxPx : 16;
      w = clamp(w, minPx, maxPx);

      const prev = lastWidthByKey.get(key);
      if (!nearlyEqual(prev, w, EPS)) {
        changed = true;
        lastWidthByKey.set(key, w);
        delta[key] = w;
      }
    }

    return changed ? delta : null;
  }

  function getExistingSeriesIdSet() {
    try {
      const opt = chart?.getOption?.();
      const seriesArr = Array.isArray(opt?.series) ? opt.series : [];
      const set = new Set();
      for (const s of seriesArr) {
        const id = s?.id;
        if (id != null && String(id).trim()) set.add(String(id));
      }
      return set;
    } catch {
      return null;
    }
  }

  function triggerMinimalRefresh() {
    const ids = normalizeRefreshIds(refreshSeriesIds);
    if (!ids.length) return;

    const existSet = getExistingSeriesIdSet();
    const filtered = existSet
      ? ids.map((x) => String(x)).filter((id) => existSet.has(id))
      : ids;

    if (!filtered.length) return;

    const series = filtered.map((id) => ({ id }));

    try {
      chart.setOption(
        { series },
        {
          notMerge: false,
          silent: true,
        }
      );
    } catch {}
  }

  function runOnce() {
    if (disposed) return;

    const delta = computeAndStoreDelta();
    if (!delta) return;

    setWidthPxBatch(delta);
    triggerMinimalRefresh();
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
    lastWidthByKey.clear();
    _zoomS = null;
    _zoomE = null;
  }

  return { scheduleUpdate, setZoomRange, dispose };
}

export function createMainBarPercentReader(chart, fallback = 88) {
  return () => readBarPercentFromMainOption(chart, fallback);
}
