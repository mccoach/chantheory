// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\fractals.js
// ==============================
// 缠论图层：分型标记 (Fractals) - Idx-Only Schema + confirmPairs 版
//
// 本轮改动：
//   - 分型宽度彻底迁移到通用 WidthController + widthState：
//       * 8 个分型 scatter series 共用 widthState key: "main:fractal"
//       * symbolSize 读取 widthState，避免 notMerge 覆盖造成的竞态
//   - 不再依赖 env.symbolWidthPx / renderHub 推导宽度
//
// V2 - 统一语义回溯：yOfFractal 迁移到 chan/accessors.js（消除重复语义）
// ==============================

import { FRACTAL_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { deriveSymbolSize } from "./geometry";
import { toNonNegIntIdx } from "@/composables/chan/common";
import { getWidthPx } from "@/charts/width/widthState";
import { createChanAccessors } from "@/composables/chan/accessors";

const WIDTH_KEY = "main:fractal";

export function buildFractalMarkers(_reducedBars, fractals, env = {}) {
  const settings = useUserSettings();

  const cfg = Object.assign(
    {},
    FRACTAL_DEFAULTS,
    (settings.chanTheory && settings.chanTheory.fractalSettings) || {}
  );

  if (!cfg.enabled) return { series: [] };

  const candles = Array.isArray(env?.candles) ? env.candles : null;
  if (!candles || !candles.length) return { series: [] };

  const acc = createChanAccessors(candles);

  const confirmPairs = env?.confirmPairs || null;
  const pairedArr = Array.isArray(confirmPairs?.paired) ? confirmPairs.paired : null;
  const pairsArr = Array.isArray(confirmPairs?.pairs) ? confirmPairs.pairs : [];

  // 高度仍按常量；宽度由 widthState 提供（fallback 使用 deriveSymbolSize）
  const { widthPx: fallbackW, heightPx: markerH } = deriveSymbolSize({
    hostWidth: env.hostWidth,
    visCount: env.visCount,
    minPx: FRACTAL_DEFAULTS.markerMinPx,
    maxPx: FRACTAL_DEFAULTS.markerMaxPx,
    overrideWidth: null,
    heightPx: FRACTAL_DEFAULTS.markerHeightPx,
  });

  const apexGap = FRACTAL_DEFAULTS.markerYOffsetPx;
  const yOffTop = -(markerH / 2 + apexGap);
  const yOffBottom = +(markerH / 2 + apexGap);

  function yOfFractal(f) {
    return acc.fractalY(f);
  }

  const bins = {
    top: { strong: [], standard: [], weak: [] },
    bottom: { strong: [], standard: [], weak: [] },
  };

  for (const f of fractals || []) {
    const strength = String(f?.strength_enum || "");
    if (!cfg.showStrength?.[strength]) continue;

    const x = toNonNegIntIdx(f?.k2_idx_orig);
    if (x == null) continue;

    const y = yOfFractal(f);
    if (!Number.isFinite(y)) continue;

    if (String(f.kind_enum) === "top") {
      bins.top[strength].push({ value: [x, y] });
    } else {
      bins.bottom[strength].push({ value: [x, y] });
    }
  }

  const series = [];

  // 关键：宽度从 widthState 读取；若尚未计算则用 fallbackW
  const symbolSizeFn = () => [getWidthPx(WIDTH_KEY, fallbackW), markerH];

  const topSpec = [
    { k: "strong", name: "TOP_STRONG" },
    { k: "standard", name: "TOP_STANDARD" },
    { k: "weak", name: "TOP_WEAK" },
  ];

  for (const sp of topSpec) {
    const data = bins.top[sp.k];
    if (!data.length) continue;

    const st = cfg.styleByStrength?.[sp.k] || {};
    const enabled = st.enabled ?? true;
    if (!enabled) continue;

    const shape = st.topShape || FRACTAL_DEFAULTS.topShape;
    const color = st.topColor || FRACTAL_DEFAULTS.styleByStrength?.[sp.k]?.topColor;
    const fillMode = st.fill || "solid";
    const isHollow = fillMode === "hollow";

    series.push({
      id: `FR_TOP_${sp.k}`,
      name: `TOP_${sp.k.toUpperCase()}`,
      type: "scatter",
      yAxisIndex: 0,
      data,
      symbol: shape,
      symbolRotate: 180,
      symbolSize: symbolSizeFn,
      symbolOffset: [0, yOffTop],
      itemStyle: isHollow
        ? {
            color: "transparent",
            borderColor: color,
            borderWidth: FRACTAL_DEFAULTS.hollowBorderWidth,
          }
        : { color },
      z: 5,
      emphasis: { scale: false },
      tooltip: { show: false },
    });
  }

  const botSpec = [
    { k: "strong", name: "BOT_STRONG" },
    { k: "standard", name: "BOT_STANDARD" },
    { k: "weak", name: "BOT_WEAK" },
  ];

  for (const sp of botSpec) {
    const data = bins.bottom[sp.k];
    if (!data.length) continue;

    const st = cfg.styleByStrength?.[sp.k] || {};
    const enabled = st.enabled ?? true;
    if (!enabled) continue;

    const shape = st.bottomShape || FRACTAL_DEFAULTS.bottomShape;
    const color = st.bottomColor || FRACTAL_DEFAULTS.styleByStrength?.[sp.k]?.bottomColor;
    const fillMode = st.fill || "solid";
    const isHollow = fillMode === "hollow";

    series.push({
      id: `FR_BOT_${sp.k}`,
      name: `BOT_${sp.k.toUpperCase()}`,
      type: "scatter",
      yAxisIndex: 0,
      data,
      symbol: shape,
      symbolRotate: 0,
      symbolSize: symbolSizeFn,
      symbolOffset: [0, yOffBottom],
      itemStyle: isHollow
        ? {
            color: "transparent",
            borderColor: color,
            borderWidth: FRACTAL_DEFAULTS.hollowBorderWidth,
          }
        : { color },
      z: 5,
      emphasis: { scale: false },
      tooltip: { show: false },
    });
  }

  const cs = cfg.confirmStyle || {};
  const confirmEnabled = cs.enabled === true;

  if (confirmEnabled && pairedArr && pairedArr.length === (fractals || []).length) {
    const topConfirmData = [];
    const botConfirmData = [];

    for (let i = 0; i < (fractals || []).length; i++) {
      if (!pairedArr[i]) continue;
      const f = fractals[i];
      const x = toNonNegIntIdx(f?.k2_idx_orig);
      if (x == null) continue;
      const y = yOfFractal(f);
      if (!Number.isFinite(y)) continue;

      if (String(f?.kind_enum || "") === "top") topConfirmData.push({ value: [x, y] });
      else if (String(f?.kind_enum || "") === "bottom") botConfirmData.push({ value: [x, y] });
    }

    const extraGap = FRACTAL_DEFAULTS.markerHeightPx + FRACTAL_DEFAULTS.markerYOffsetPx;

    if (topConfirmData.length) {
      const shape = cs.topShape || FRACTAL_DEFAULTS.confirmStyle.topShape;
      const color = cs.topColor || FRACTAL_DEFAULTS.confirmStyle.topColor;
      const isHollow = (cs.fill || "solid") === "hollow";

      series.push({
        id: "FR_TOP_CONFIRM",
        name: "TOP_CONFIRM",
        type: "scatter",
        yAxisIndex: 0,
        data: topConfirmData,
        symbol: shape,
        symbolRotate: 180,
        symbolSize: symbolSizeFn,
        symbolOffset: [0, -(markerH / 2 + apexGap + extraGap)],
        itemStyle: isHollow
          ? {
              color: "transparent",
              borderColor: color,
              borderWidth: FRACTAL_DEFAULTS.hollowBorderWidth,
            }
          : { color },
        z: 6,
        emphasis: { scale: false },
        tooltip: { show: false },
      });
    }

    if (botConfirmData.length) {
      const shape = cs.bottomShape || FRACTAL_DEFAULTS.confirmStyle.bottomShape;
      const color = cs.bottomColor || FRACTAL_DEFAULTS.confirmStyle.bottomColor;
      const isHollow = (cs.fill || "solid") === "hollow";

      series.push({
        id: "FR_BOT_CONFIRM",
        name: "BOT_CONFIRM",
        type: "scatter",
        yAxisIndex: 0,
        data: botConfirmData,
        symbol: shape,
        symbolRotate: 0,
        symbolSize: symbolSizeFn,
        symbolOffset: [0, +(markerH / 2 + apexGap + extraGap)],
        itemStyle: isHollow
          ? {
              color: "transparent",
              borderColor: color,
              borderWidth: FRACTAL_DEFAULTS.hollowBorderWidth,
            }
          : { color },
        z: 6,
        emphasis: { scale: false },
        tooltip: { show: false },
      });
    }
  }

  if (cfg.showConfirmLink && pairsArr.length) {
    const segs = [];

    for (const pr of pairsArr) {
      const aIdx = toNonNegIntIdx(pr?.a);
      const bIdx = toNonNegIntIdx(pr?.b);
      if (aIdx == null || bIdx == null) continue;

      const fa = fractals?.[aIdx];
      const fb = fractals?.[bIdx];
      if (!fa || !fb) continue;

      const xa = toNonNegIntIdx(fa.k2_idx_orig);
      const xb = toNonNegIntIdx(fb.k2_idx_orig);
      if (xa == null || xb == null) continue;

      const ya = yOfFractal(fa);
      const yb = yOfFractal(fb);
      if (!Number.isFinite(ya) || !Number.isFinite(yb)) continue;

      segs.push([xa, ya], [xb, yb], null);
    }

    if (segs.length) {
      const linkStyle = cfg.confirmLinkStyle || FRACTAL_DEFAULTS.confirmLinkStyle;

      series.push({
        id: "FR_CONFIRM_LINKS",
        name: "FR_CONFIRM",
        type: "line",
        yAxisIndex: 0,
        data: segs,
        connectNulls: false,
        showSymbol: false,
        lineStyle: {
          color: linkStyle.color,
          width: linkStyle.width,
          type: linkStyle.lineStyle,
        },
        z: 4,
        tooltip: { show: false },
        emphasis: { disabled: true },
      });
    }
  }

  return { series };
}
