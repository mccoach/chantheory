// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\fractals.js
// ==============================
// 缠论图层：分型标记 (Fractals)
// - 从 layers.js 拆分而来。
// - 核心职责：将分型数据转换为ECharts的散点图系列，并处理不同强度和确认状态的样式。
// ==============================
import { FRACTAL_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { deriveSymbolSize } from "./geometry"; // NEW

// 分型标记：横坐标用 k2_idx_orig；绑定主轴 yAxisIndex=0；高度与间距由 FRACTAL_DEFAULTS 集中决定
export function buildFractalMarkers(reducedBars, fractals, env = {}) {
  const settings = useUserSettings();
  const cfg = Object.assign(
    {},
    FRACTAL_DEFAULTS,
    (settings.chanTheory && settings.chanTheory.fractalSettings) || {}
  );
  if (!cfg.enabled) return { series: [] };

  // MODIFIED: Use deriveSymbolSize for unified geometry calculation
  const { widthPx: markerW, heightPx: markerH } = deriveSymbolSize({
    hostWidth: env.hostWidth,
    visCount: env.visCount,
    minPx: cfg.markerMinPx,
    maxPx: cfg.markerMaxPx,
    overrideWidth: env.symbolWidthPx,
    heightPx: FRACTAL_DEFAULTS.markerHeightPx,
  });

  // 统一高度与顶/底偏移来源
  const apexGap = Math.max(
    0,
    Math.round(Number(FRACTAL_DEFAULTS.markerYOffsetPx))
  ); // 顶点距 bar 的预设间距
  const yOffTop = -(markerH / 2 + apexGap); // 顶分中心向上偏移
  const yOffBottom = +(markerH / 2 + apexGap); // 底分中心向下偏移

  const bins = {
    top: { strong: [], standard: [], weak: [] },
    bottom: { strong: [], standard: [], weak: [] },
  };

  for (const f of fractals || []) {
    if (!cfg.showStrength?.[f.strength_enum]) continue;
    const x = Number(f?.k2_idx_orig);
    if (f.kind_enum === "top")
      bins.top[f.strength_enum].push({ value: [x, f.k2_g_pri] });
    else bins.bottom[f.strength_enum].push({ value: [x, f.k2_d_pri] });
  }

  const series = []; // 分型系列集合

  // 顶分系列（三档）
  const topSpec = [
    { k: "strong", name: "TOP_STRONG" },
    { k: "standard", name: "TOP_STANDARD" },
    { k: "weak", name: "TOP_WEAK" },
  ];
  for (const sp of topSpec) {
    const data = bins.top[sp.k];
    if (!data.length) continue;
    const st = (cfg.styleByStrength && cfg.styleByStrength[sp.k]) || {};
    const enabled = (st.enabled ?? true) === true;
    if (!enabled) continue;
    const shape = st.topShape || cfg.topShape || "triangle";
    const color =
      st.topColor ||
      cfg.topColors?.[sp.k] ||
      FRACTAL_DEFAULTS.styleByStrength?.[sp.k]?.topColor;
    const fillMode = st.fill || "solid";
    const isHollow = fillMode === "hollow";

    series.push({
      id: `FR_TOP_${sp.k}`,
      name: "TOP_STRONG".replace("STRONG", sp.k.toUpperCase()),
      type: "scatter",
      yAxisIndex: 0, // 不变量：yAxisIndex: 0
      data,
      symbol: shape,
      symbolRotate: 180,
      symbolSize: () => [markerW, markerH],
      symbolOffset: [0, yOffTop],
      itemStyle: isHollow
        ? { color: "transparent", borderColor: color, borderWidth: 1.2 }
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
    const st = (cfg.styleByStrength && cfg.styleByStrength[sp.k]) || {};
    const enabled = (st.enabled ?? true) === true;
    if (!enabled) continue;
    const shape = st.bottomShape || cfg.bottomShape || "triangle";
    const color =
      st.bottomColor ||
      cfg.bottomColors?.[sp.k] ||
      FRACTAL_DEFAULTS.styleByStrength?.[sp.k]?.bottomColor;
    const fillMode = st.fill || "solid";
    const isHollow = fillMode === "hollow";
    series.push({
      id: `FR_BOT_${sp.k}`,
      name: "BOT_STRONG".replace("STRONG", sp.k.toUpperCase()),
      type: "scatter",
      yAxisIndex: 0, // 不变量：yAxisIndex: 0
      data,
      symbol: shape,
      symbolRotate: 0,
      symbolSize: () => [markerW, markerH],
      symbolOffset: [0, yOffBottom],
      itemStyle: isHollow
        ? { color: "transparent", borderColor: color, borderWidth: 1.2 }
        : { color },
      z: 5,
      emphasis: { scale: false },
      tooltip: { show: false },
    });
  }

  // 确认分型
  const cs = cfg.confirmStyle || {};
  if (cs.enabled) {
    const topConfirmData = [];
    const botConfirmData = [];
    for (const f of fractals || []) {
      if (!f?.cf_paired_bool) continue;
      if (f.kind_enum === "top")
        topConfirmData.push({ value: [f.k2_idx_orig, f.k2_g_pri] });
      else botConfirmData.push({ value: [f.k2_idx_orig, f.k2_d_pri] });
    }
    const extraGap = Math.max(
      0,
      Math.round(
        Number(FRACTAL_DEFAULTS.markerHeightPx) +
          Number(FRACTAL_DEFAULTS.markerYOffsetPx)
      )
    );
    if (topConfirmData.length) {
      const shape = cs.topShape || "triangle";
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
        symbolSize: () => [markerW, markerH],
        symbolOffset: [0, -(markerH / 2 + apexGap + extraGap)],
        itemStyle: isHollow
          ? { color: "transparent", borderColor: color, borderWidth: 1.2 }
          : { color },
        z: 6,
        emphasis: { scale: false },
        tooltip: { show: false },
      });
    }
    if (botConfirmData.length) {
      const shape = cs.bottomShape || "triangle";
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
        symbolSize: () => [markerW, markerH],
        symbolOffset: [0, +(markerH / 2 + apexGap + extraGap)],
        itemStyle: isHollow
          ? { color: "transparent", borderColor: color, borderWidth: 1.2 }
          : { color },
        z: 6,
        emphasis: { scale: false },
        tooltip: { show: false },
      });
    }
  }

  // 预留：确认分型连线
  if (cfg.showConfirmLink) {
    const segs = [];
    for (const f of fractals || []) {
      if (!f.cf_paired_bool || f.cf_role_enum !== "first") continue;
      const partner = (fractals || []).find(
        (x) =>
          x.cf_paired_bool &&
          x.cf_pair_id_str === f.cf_pair_id_str &&
          x.cf_role_enum === "second"
      );
      if (!partner) continue;
      if (f.kind_enum === "top")
        segs.push(
          [f.k2_idx_orig, f.k2_g_pri],
          [partner.k2_idx_orig, partner.k2_g_pri],
          null
        );
      else
        segs.push(
          [f.k2_idx_orig, f.k2_d_pri],
          [partner.k2_idx_orig, partner.k2_d_pri],
          null
        );
    }
    if (segs.length) {
      series.push({
        id: "FR_CONFIRM_LINKS",
        name: "FR_CONFIRM",
        type: "line",
        yAxisIndex: 0,
        data: segs,
        connectNulls: false,
        showSymbol: false,
        lineStyle: {
          color: "rgba(200,200,200,0.5)",
          width: 1.2,
          type: "dashed",
        },
        z: 4,
        tooltip: { show: false },
        emphasis: { disabled: true },
      });
    }
  }

  return { series };
}