// src/charts/chan/layers/fractals.js
// ==============================
// 缠论图层：分型标记 (Fractals)
// 职责：将分型数据转换为ECharts散点图系列
// 算法：处理不同强度和确认状态的样式
// 
// 修复要点：
//   - 已暴露参数：从 cfg 读取（topColor/bottomColor/fill等）
//   - 未暴露参数：直接用常量（markerHeightPx/markerYOffsetPx等）
// ==============================

import { FRACTAL_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { deriveSymbolSize } from "./geometry";

export function buildFractalMarkers(reducedBars, fractals, env = {}) {
  const settings = useUserSettings();
  
  // ===== 合并设置：优先用户配置，兜底默认值 =====
  const cfg = Object.assign(
    {},
    FRACTAL_DEFAULTS,
    (settings.chanTheory && settings.chanTheory.fractalSettings) || {}
  );
  
  if (!cfg.enabled) return { series: [] };

  // ===== 几何计算：已暴露参数走settings，未暴露参数用常量 =====
  const { widthPx: markerW, heightPx: markerH } = deriveSymbolSize({
    hostWidth: env.hostWidth,
    visCount: env.visCount,
    minPx: FRACTAL_DEFAULTS.markerMinPx,      // ← 未暴露，直接用常量
    maxPx: FRACTAL_DEFAULTS.markerMaxPx,      // ← 未暴露，直接用常量
    overrideWidth: env.symbolWidthPx,
    heightPx: FRACTAL_DEFAULTS.markerHeightPx,  // ← 未暴露，直接用常量
  });

  // ===== 偏移计算：未暴露参数直接用常量 =====
  const apexGap = FRACTAL_DEFAULTS.markerYOffsetPx;  // ← 未暴露，直接用常量
  const yOffTop = -(markerH / 2 + apexGap);
  const yOffBottom = +(markerH / 2 + apexGap);

  const bins = {
    top: { strong: [], standard: [], weak: [] },
    bottom: { strong: [], standard: [], weak: [] },
  };

  // ===== 数据分组 =====
  for (const f of fractals || []) {
    if (!cfg.showStrength?.[f.strength_enum]) continue;
    const x = Number(f?.k2_idx_orig);
    if (f.kind_enum === "top")
      bins.top[f.strength_enum].push({ value: [x, f.k2_g_pri] });
    else 
      bins.bottom[f.strength_enum].push({ value: [x, f.k2_d_pri] });
  }

  const series = [];

  // ===== 顶分系列（强/标/弱）=====
  const topSpec = [
    { k: "strong", name: "TOP_STRONG" },
    { k: "standard", name: "TOP_STANDARD" },
    { k: "weak", name: "TOP_WEAK" },
  ];
  
  for (const sp of topSpec) {
    const data = bins.top[sp.k];
    if (!data.length) continue;
    
    // ===== 读取配置：已暴露参数从cfg读取 =====
    const st = cfg.styleByStrength?.[sp.k] || {};
    const enabled = st.enabled ?? true;
    if (!enabled) continue;
    
    const shape = st.topShape || FRACTAL_DEFAULTS.topShape;  // ← 已暴露
    const color = st.topColor || FRACTAL_DEFAULTS.styleByStrength?.[sp.k]?.topColor;  // ← 已暴露
    const fillMode = st.fill || "solid";  // ← 已暴露
    const isHollow = fillMode === "hollow";

    series.push({
      id: `FR_TOP_${sp.k}`,
      name: `TOP_${sp.k.toUpperCase()}`,
      type: "scatter",
      yAxisIndex: 0,
      data,
      symbol: shape,
      symbolRotate: 180,
      symbolSize: () => [markerW, markerH],
      symbolOffset: [0, yOffTop],
      itemStyle: isHollow
        ? { 
            color: "transparent", 
            borderColor: color, 
            borderWidth: FRACTAL_DEFAULTS.hollowBorderWidth  // ← 未暴露，直接用常量
          }
        : { color },
      z: 5,
      emphasis: { scale: false },
      tooltip: { show: false },
    });
  }

  // ===== 底分系列（强/标/弱）=====
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
    
    const shape = st.bottomShape || FRACTAL_DEFAULTS.bottomShape;  // ← 已暴露
    const color = st.bottomColor || FRACTAL_DEFAULTS.styleByStrength?.[sp.k]?.bottomColor;  // ← 已暴露
    const fillMode = st.fill || "solid";  // ← 已暴露
    const isHollow = fillMode === "hollow";
    
    series.push({
      id: `FR_BOT_${sp.k}`,
      name: `BOT_${sp.k.toUpperCase()}`,
      type: "scatter",
      yAxisIndex: 0,
      data,
      symbol: shape,
      symbolRotate: 0,
      symbolSize: () => [markerW, markerH],
      symbolOffset: [0, yOffBottom],
      itemStyle: isHollow
        ? { 
            color: "transparent", 
            borderColor: color, 
            borderWidth: FRACTAL_DEFAULTS.hollowBorderWidth  // ← 未暴露，直接用常量
          }
        : { color },
      z: 5,
      emphasis: { scale: false },
      tooltip: { show: false },
    });
  }

  // ===== 确认分型 =====
  const cs = cfg.confirmStyle || {};
  if (cs.enabled) {
    const topConfirmData = [];
    const botConfirmData = [];
    
    for (const f of fractals || []) {
      if (!f?.cf_paired_bool) continue;
      if (f.kind_enum === "top")
        topConfirmData.push({ value: [f.k2_idx_orig, f.k2_g_pri] });
      else 
        botConfirmData.push({ value: [f.k2_idx_orig, f.k2_d_pri] });
    }
    
    // 额外间距（未暴露参数）
    const extraGap = FRACTAL_DEFAULTS.markerHeightPx + FRACTAL_DEFAULTS.markerYOffsetPx;
    
    if (topConfirmData.length) {
      const shape = cs.topShape || FRACTAL_DEFAULTS.confirmStyle.topShape;  // ← 已暴露
      const color = cs.topColor || FRACTAL_DEFAULTS.confirmStyle.topColor;  // ← 已暴露
      const isHollow = (cs.fill || "solid") === "hollow";  // ← 已暴露
      
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
          ? { 
              color: "transparent", 
              borderColor: color, 
              borderWidth: FRACTAL_DEFAULTS.hollowBorderWidth  // ← 未暴露，直接用常量
            }
          : { color },
        z: 6,
        emphasis: { scale: false },
        tooltip: { show: false },
      });
    }
    
    if (botConfirmData.length) {
      const shape = cs.bottomShape || FRACTAL_DEFAULTS.confirmStyle.bottomShape;  // ← 已暴露
      const color = cs.bottomColor || FRACTAL_DEFAULTS.confirmStyle.bottomColor;  // ← 已暴露
      const isHollow = (cs.fill || "solid") === "hollow";  // ← 已暴露
      
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
          ? { 
              color: "transparent", 
              borderColor: color, 
              borderWidth: FRACTAL_DEFAULTS.hollowBorderWidth  // ← 未暴露，直接用常量
            }
          : { color },
        z: 6,
        emphasis: { scale: false },
        tooltip: { show: false },
      });
    }
  }

  // ===== 确认连线（未暴露功能，直接用常量）=====
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
      // ===== 未暴露参数直接用常量 =====
      const linkStyle = FRACTAL_DEFAULTS.confirmLinkStyle;

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