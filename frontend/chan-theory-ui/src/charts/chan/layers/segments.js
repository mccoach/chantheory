// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\segments.js
// ==============================
// 缠论图层：线段 (Segments)
// - 同时绘制元线段(metaSegments) + 最终线段(finalSegments)
// - 元线段样式：chanSettings.metaSegment（与 segment 平起平坐，已进入设置窗）
// - 最终线段样式：chanSettings.segment（原有）
// ==============================

import { SEGMENT_DEFAULTS, META_SEGMENT_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { sampleSeriesByBarriers } from "./sampler";
import { candleH, candleL, toNonNegIntIdx } from "@/composables/chan/common";

/**
 * 把单条 Segment（Idx-Only）采样为多段 series data
 */
function sampleSegmentToChunks(seg, candles, barrierIdxSet) {
  const xStart = toNonNegIntIdx(seg?.start_idx_orig);
  const xEnd = toNonNegIntIdx(seg?.end_idx_orig);
  if (xStart == null || xEnd == null) return [];

  const dir = String(seg?.dir_enum || "").toUpperCase();

  function endpointY(which, x) {
    if (dir === "UP") {
      return which === "start" ? candleL(candles, x) : candleH(candles, x);
    }
    if (dir === "DOWN") {
      return which === "start" ? candleH(candles, x) : candleL(candles, x);
    }
    return NaN;
  }

  const yStart = endpointY("start", xStart);
  const yEnd = endpointY("end", xEnd);
  if (![yStart, yEnd].every((v) => Number.isFinite(v))) return [];

  const dx = xEnd - xStart;
  const dy = yEnd - yStart;
  const slope = dx !== 0 ? dy / dx : 0;

  const yResolver = (xi) => yStart + slope * (xi - xStart);

  return sampleSeriesByBarriers({
    xStart,
    xEnd,
    yResolver,
    barriersSet: barrierIdxSet,
  });
}

function normalizeInput(segmentsOrObj) {
  // 兼容旧调用：Array => finalSegments
  if (Array.isArray(segmentsOrObj)) {
    return { metaSegments: [], finalSegments: segmentsOrObj };
  }
  const obj = segmentsOrObj && typeof segmentsOrObj === "object" ? segmentsOrObj : {};
  return {
    metaSegments: Array.isArray(obj.metaSegments) ? obj.metaSegments : [],
    finalSegments: Array.isArray(obj.finalSegments) ? obj.finalSegments : [],
  };
}

function resolveStyle(cfg, defaults) {
  const color = cfg.color || defaults.color;
  const lineWidth = Number.isFinite(+cfg.lineWidth) ? +cfg.lineWidth : defaults.lineWidth;
  const lineStyle = String(cfg.lineStyle || defaults.lineStyle);
  return { color, lineWidth, lineStyle };
}

export function buildSegmentLines(segmentsOrObj, env = {}) {
  const settings = useUserSettings();
  const segCfg = Object.assign(
    {},
    SEGMENT_DEFAULTS,
    (settings.chanTheory &&
      settings.chanTheory.chanSettings &&
      settings.chanTheory.chanSettings.segment) ||
      {}
  );

  const metaCfg = Object.assign(
    {},
    META_SEGMENT_DEFAULTS,
    (settings.chanTheory &&
      settings.chanTheory.chanSettings &&
      settings.chanTheory.chanSettings.metaSegment) ||
      {}
  );

  const candles = Array.isArray(env?.candles) ? env.candles : null;
  if (!candles || !candles.length) return { series: [] };

  const barrierIdxSet = new Set(
    Array.isArray(env.barrierIdxList) ? env.barrierIdxList.map((x) => +x) : []
  );

  const { metaSegments, finalSegments } = normalizeInput(segmentsOrObj);

  // 最终线段总开关沿用现有 segCfg.enabled（设置窗已暴露）
  const finalEnabled = segCfg.enabled !== false;
  const metaEnabled = metaCfg.enabled !== false;

  const metaStyle = resolveStyle(metaCfg, META_SEGMENT_DEFAULTS);
  const finalStyle = resolveStyle(segCfg, SEGMENT_DEFAULTS);

  const out = [];
  let seqCounter = 0;

  // 元线段（z 低一些）
  if (metaEnabled && metaSegments.length) {
    for (const s of metaSegments) {
      const chunks = sampleSegmentToChunks(s, candles, barrierIdxSet);
      for (let k = 0; k < chunks.length; k++) {
        out.push({
          id: `CHAN_META_SEG_${s.start_idx_orig}_${s.end_idx_orig}_${k}_${seqCounter++}`,
          name: "CHAN_META_SEGMENTS",
          type: "line",
          yAxisIndex: 0,
          data: chunks[k],
          showSymbol: false,
          smooth: false,
          lineStyle: {
            color: metaStyle.color,
            width: metaStyle.lineWidth,
            type: metaStyle.lineStyle,
          },
          z: 6,
          connectNulls: false,
          tooltip: { show: false },
          emphasis: { disabled: true },
        });
      }
    }
  }

  // 最终线段（z 高一些）
  if (finalEnabled && finalSegments.length) {
    for (const s of finalSegments) {
      const chunks = sampleSegmentToChunks(s, candles, barrierIdxSet);
      for (let k = 0; k < chunks.length; k++) {
        out.push({
          id: `CHAN_FINAL_SEG_${s.start_idx_orig}_${s.end_idx_orig}_${k}_${seqCounter++}`,
          name: "CHAN_SEGMENTS",
          type: "line",
          yAxisIndex: 0,
          data: chunks[k],
          showSymbol: false,
          smooth: false,
          lineStyle: {
            color: finalStyle.color,
            width: finalStyle.lineWidth,
            type: finalStyle.lineStyle,
          },
          z: 7,
          connectNulls: false,
          tooltip: { show: false },
          emphasis: { disabled: true },
        });
      }
    }
  }

  return { series: out };
}
