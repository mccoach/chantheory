// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\barriers.js
// ==============================
// 缠论图层：连续性屏障 (Continuity Barriers)
// - 从 layers.js 拆分而来。
// - 核心职责：将屏障索引列表转换为贯穿主图的垂直标记线（markLine）。
// ==============================
import { CONTINUITY_BARRIER } from "@/constants";

/**
 * 连续性屏障竖线（贯穿主窗顶底）
 */
export function buildBarrierLines(barrierIdxList) {
  const idxs = Array.isArray(barrierIdxList) ? barrierIdxList : [];
  if (!CONTINUITY_BARRIER?.enabled || !idxs.length) return { series: [] };
  const lines = idxs
    .filter((i) => Number.isFinite(+i) && +i >= 0)
    .map((i) => ({ xAxis: +i }));

  if (!lines.length) return { series: [] };

  const series = {
    id: "CHAN_BARRIERS",
    name: "CHAN_BARRIERS",
    type: "line",
    yAxisIndex: 0,
    data: [],
    markLine: {
      symbol: "none",
      silent: true,
      label: { show: false },
      lineStyle: {
        color: CONTINUITY_BARRIER.lineColor,
        width: Number(CONTINUITY_BARRIER.lineWidth || 1.2),
        type: CONTINUITY_BARRIER.lineStyle || "solid",
      },
      data: lines,
    },
    z: 8,
    tooltip: { show: false },
    emphasis: { disabled: true },
  };
  return { series: [series] };
}