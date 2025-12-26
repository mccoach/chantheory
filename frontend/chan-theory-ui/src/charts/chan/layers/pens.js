// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\pens.js
// ==============================
// 缠论图层：笔 (Pens) - Idx-Only Schema 版
// - 核心职责：将笔数据转换为 ECharts 线图系列（line series）。
// - 按屏障分段渲染：通过 barrierIdxList 切段，避免跨屏障连接。
// - 单一真相源：笔不存 y/pri，渲染端点 y 值通过 idx_orig 回溯 candles 读取。
// ==============================

import { PENS_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { sampleSeriesByBarriers } from "./sampler";
import { candleH, candleL, toNonNegIntIdx } from "@/composables/chan/common";

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

  const candles = Array.isArray(env?.candles) ? env.candles : null;
  if (!candles || !candles.length) return { series: [] };

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

  function endpointY(pen, which) {
    const dir = String(pen?.dir_enum || "").toUpperCase();
    const x =
      which === "start"
        ? toNonNegIntIdx(pen?.start_idx_orig)
        : toNonNegIntIdx(pen?.end_idx_orig);
    if (x == null) return NaN;

    if (dir === "UP") {
      // UP：start=bottom(low)，end=top(high)
      return which === "start" ? candleL(candles, x) : candleH(candles, x);
    }
    if (dir === "DOWN") {
      // DOWN：start=top(high)，end=bottom(low)
      return which === "start" ? candleH(candles, x) : candleL(candles, x);
    }
    return NaN;
  }

  function samplePenToChunks(p) {
    const x1 = toNonNegIntIdx(p?.start_idx_orig);
    const x2 = toNonNegIntIdx(p?.end_idx_orig);
    if (x1 == null || x2 == null) return [];

    const y1 = endpointY(p, "start");
    const y2 = endpointY(p, "end");
    if (![y1, y2].every((v) => Number.isFinite(v))) return [];

    const dx = x2 - x1;
    const dy = y2 - y1;
    const slope = dx !== 0 ? dy / dx : 0;

    const yResolver = (xi) => y1 + slope * (xi - x1);

    return sampleSeriesByBarriers({
      xStart: x1,
      xEnd: x2,
      yResolver,
      barriersSet: barrierIdxSet,
    });
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
