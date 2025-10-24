// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\segments.js
// ==============================
// 缠论图层：线段 (Segments)
// - 从 layers.js 拆分而来。
// - 核心职责：将线段数据转换为ECharts的线图系列。
// - 算法：同样按屏障进行分段渲染。
// ==============================
import { SEGMENT_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";

// 元线段（每段 series）
export function buildSegmentLines(segments, env = {}) {
  const settings = useUserSettings();
  const segCfg = Object.assign(
    {},
    SEGMENT_DEFAULTS,
    (settings.chanTheory &&
      settings.chanTheory.chanSettings &&
      settings.chanTheory.chanSettings.segment) ||
      {}
  );

  if (
    !Array.isArray(segments) ||
    !segments.length ||
    segCfg.enabled === false
  ) {
    return { series: [] };
  }

  const color = segCfg.color || SEGMENT_DEFAULTS.color;
  const lineWidth = Number.isFinite(+segCfg.lineWidth)
    ? +segCfg.lineWidth
    : SEGMENT_DEFAULTS.lineWidth;
  const lineStyle = String(segCfg.lineStyle || SEGMENT_DEFAULTS.lineStyle);

  const barrierIdxSet = new Set(
    Array.isArray(env.barrierIdxList) ? env.barrierIdxList.map((x) => +x) : []
  );

  function sampleSegmentToChunks(s) {
    const xStart = Number(s.start_idx_orig);
    const yStart = Number(s.start_y_pri);
    const xEnd = Number(s.end_idx_orig);
    const yEnd = Number(s.end_y_pri);
    if (![xStart, yStart, xEnd, yEnd].every((v) => Number.isFinite(v)))
      return [];

    const x0 = Math.min(xStart, xEnd);
    const x1 = Math.max(xStart, xEnd);

    const dx = xEnd - xStart;
    const dy = yEnd - yStart;
    const slope = dx !== 0 ? dy / dx : 0;

    const chunks = [];
    let curr = [];
    for (let xi = x0; xi <= x1; xi++) {
      if (barrierIdxSet.has(xi)) {
        if (curr.length >= 2) chunks.push(curr);
        curr = [];
        continue;
      }
      const t = xi - xStart;
      const yi = yStart + slope * t;
      curr.push([xi, yi]);
    }
    if (curr.length >= 2) chunks.push(curr);
    return chunks;
  }

  const out = [];
  let seqCounter = 0;
  for (const s of segments) {
    const chunks = sampleSegmentToChunks(s);
    for (let k = 0; k < chunks.length; k++) {
      const data = chunks[k];
      out.push({
        id: `CHAN_SEG_${s.start_idx_orig}_${
          s.end_idx_orig
        }_${k}_${seqCounter++}`,
        name: "CHAN_SEGMENTS",
        type: "line",
        yAxisIndex: 0,
        data,
        showSymbol: false,
        smooth: false,
        lineStyle: {
          color,
          width: lineWidth,
          type: lineStyle,
        },
        z: 6,
        connectNulls: false,
        tooltip: { show: false },
        emphasis: { disabled: true },
      });
    }
  }
  return { series: out };
}
