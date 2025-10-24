// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\pens.js
// ==============================
// 缠论图层：笔 (Pens)
// - 从 layers.js 拆分而来。
// - 核心职责：将笔数据（确认和预备）转换为ECharts的线图系列（line series）。
// - 算法：通过 barrierIdxList 将笔在断点处分段，每段独立 line 系列，避免跨屏障连接。
// ==============================
import { PENS_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";

// 画笔折线（每段 series）
export function buildPenLines(pensObj, env = {}) {
  const settings = useUserSettings();
  const penCfg = Object.assign(
    {},
    PENS_DEFAULTS,
    (settings.chanTheory &&
      settings.chanTheory.chanSettings &&
      settings.chanTheory.chanSettings.pen) ||
      {}
  );

  const pens = pensObj || {};
  const confirmed = Array.isArray(pens.confirmed) ? pens.confirmed : [];
  const provisional = pens.provisional ? [pens.provisional] : [];

  const baseColor = penCfg.color;
  const lineW = Number.isFinite(+penCfg.lineWidth)
    ? +penCfg.lineWidth
    : PENS_DEFAULTS.lineWidth;
  const confirmedStyle = String(
    penCfg.confirmedStyle || PENS_DEFAULTS.confirmedStyle
  );
  const provisionalStyle = String(
    penCfg.provisionalStyle || PENS_DEFAULTS.provisionalStyle
  );

  const barrierIdxSet = new Set(
    Array.isArray(env.barrierIdxList) ? env.barrierIdxList.map((x) => +x) : []
  );

  // 将笔采样为若干段（每段为单独 series）
  function samplePenToChunks(p) {
    const x1 = Number(p.start_idx_orig);
    const y1 = Number(p.start_y_pri);
    const x2 = Number(p.end_idx_orig);
    const y2 = Number(p.end_y_pri);
    if (![x1, y1, x2, y2].every((v) => Number.isFinite(v))) return [];

    const xa = Math.min(x1, x2);
    const xb = Math.max(x1, x2);
    const dx = x2 - x1;
    const dy = y2 - y1;
    const slope = dx !== 0 ? dy / dx : 0;

    const chunks = [];
    let curr = [];

    for (let xi = xa; xi <= xb; xi++) {
      if (barrierIdxSet.has(xi)) {
        if (curr.length >= 2) {
          chunks.push(curr);
        }
        curr = [];
        continue;
      }
      const t = xi - x1;
      const yi = y1 + slope * t;
      curr.push([xi, yi]);
    }
    if (curr.length >= 2) {
      chunks.push(curr);
    }
    return chunks;
  }

  const series = [];
  let seqCounter = 0;

  for (const p of confirmed) {
    const chunks = samplePenToChunks(p);
    for (let k = 0; k < chunks.length; k++) {
      const data = chunks[k];
      series.push({
        id: `CHAN_PEN_CONF_${p.start_idx_orig}_${
          p.end_idx_orig
        }_${k}_${seqCounter++}`,
        name: "CHAN_PENS_CONFIRMED",
        type: "line",
        yAxisIndex: 0,
        data,
        showSymbol: false,
        smooth: false,
        lineStyle: { color: baseColor, width: lineW, type: confirmedStyle },
        z: 4,
        connectNulls: false,
        tooltip: { show: false },
        emphasis: { disabled: true },
      });
    }
  }

  for (const p of provisional) {
    const chunks = samplePenToChunks(p);
    for (let k = 0; k < chunks.length; k++) {
      const data = chunks[k];
      series.push({
        id: `CHAN_PEN_PROV_${p.start_idx_orig}_${
          p.end_idx_orig
        }_${k}_${seqCounter++}`,
        name: "CHAN_PENS_PROVISIONAL",
        type: "line",
        yAxisIndex: 0,
        data,
        showSymbol: false,
        smooth: false,
        lineStyle: { color: baseColor, width: lineW, type: provisionalStyle },
        z: 3,
        connectNulls: false,
        tooltip: { show: false },
        emphasis: { disabled: true },
      });
    }
  }

  return { series };
}
