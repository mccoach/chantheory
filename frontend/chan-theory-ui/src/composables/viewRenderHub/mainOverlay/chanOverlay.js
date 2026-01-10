// src/composables/viewRenderHub/mainOverlay/chanOverlay.js
// ==============================
// 主图 Chan overlays 组装器（原 useViewRenderHub 内 _buildOverlaySeriesForOption）
// 职责：只负责把已算好的 chanCache 结构 + settings 组装成 overlay series。
// 不做识别算法，不做缓存（缓存由 chanCacheEngine 负责）。
// ==============================

import {
  buildUpDownMarkers,
  buildFractalMarkers,
  buildPenLines,
  buildSegmentLines,
  buildBarrierLines,
  buildPenPivotAreas,
} from "@/charts/chan/layers";
import { CHAN_DEFAULTS, PENS_DEFAULTS } from "@/constants";

export function buildChanOverlaySeries({ settings, chanCache, candles, hostW, visCount }) {
  const out = [];
  const cc = chanCache || {};

  const reduced = cc.reduced;
  const fractals = cc.fractals;
  const fractalConfirmPairs = cc.fractalConfirmPairs;
  const pens = cc.pens;
  const metaSegments = cc.metaSegments;
  const finalSegments = cc.finalSegments;
  const barriersIndices = cc.barriersIndices;
  const pivots = cc.pivots;

  if (barriersIndices?.length) out.push(...(buildBarrierLines(barriersIndices).series || []));

  if (settings.chanTheory.chanSettings.showUpDownMarkers && reduced?.length) {
    out.push(
      ...(buildUpDownMarkers(reduced, {
        hostWidth: hostW,
        visCount,
      }).series || [])
    );
  }

  if (
    (settings.chanTheory.fractalSettings?.enabled ?? true) &&
    reduced?.length &&
    fractals?.length
  ) {
    out.push(
      ...(buildFractalMarkers(reduced, fractals, {
        candles,
        confirmPairs: fractalConfirmPairs,
        hostWidth: hostW,
        visCount,
      }).series || [])
    );
  }

  const penEnabled =
    (settings.chanTheory.chanSettings?.pen?.enabled ?? PENS_DEFAULTS.enabled) === true;

  if (penEnabled && reduced?.length && (pens?.confirmed?.length || pens?.provisional)) {
    out.push(
      ...(buildPenLines(pens, {
        candles,
        barrierIdxList: barriersIndices,
      }).series || [])
    );
  }

  if (metaSegments?.length || finalSegments?.length) {
    out.push(
      ...(buildSegmentLines(
        { metaSegments, finalSegments },
        { candles, barrierIdxList: barriersIndices }
      ).series || [])
    );
  }

  if (pivots?.length) {
    out.push(...(buildPenPivotAreas(pivots, { barrierIdxList: barriersIndices }).series || []));
  }

  return out;
}
