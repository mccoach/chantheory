// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers.js
// ==============================
// 缠论覆盖图层（适配新命名）
// - 涨跌标记：x=anchor_idx_orig；yAxisIndex=1；符号尺寸集中来源。
// - 分型标记：x=k2_idx_orig；y取 k2_*；yAxisIndex=0。
// - 画笔/线段：x=*_idx_orig；y=*_y_pri；样式取默认配置。
//   本版：线段与笔采用“段落式 series”，不使用 null 分段，彻底避免跨断档连接。
// - 连续性屏障（竖线）：在 gap 两侧紧邻原始 K 处绘制贯穿主窗的竖线（markLine）。
// - NEW：笔中枢（矩形框）：markArea 透明填充 + markLine 四边框，颜色与填充一致，填充按透明度淡显。
// ==============================
import {
  CHAN_MARKER_PRESETS, // 视觉预设集合
  CHAN_DEFAULTS, // 缺省参数（包含图形/颜色/最大数量）
  FRACTAL_DEFAULTS, // 分型默认（包含样式与间距）
  PENS_DEFAULTS, // 画笔默认方案（线宽/颜色/线型/开关）
  SEGMENT_DEFAULTS, // 线段默认样式
  CONTINUITY_BARRIER, // 连续性屏障全局参数
  CHAN_PEN_PIVOT_DEFAULTS, // NEW: 笔中枢默认
} from "@/constants";

import { useUserSettings } from "@/composables/useUserSettings";

// 涨跌标记：横坐标 = anchor_idx_orig（承载点的原始索引），绑定隐藏 yAxis=1
export function buildUpDownMarkers(reducedBars, env = {}) {
  const settings = useUserSettings();
  const chan = Object.assign(
    {},
    CHAN_DEFAULTS,
    (settings.chanSettings && settings.chanSettings.value) || {}
  );

  const hostWidth = Math.max(1, Number(env.hostWidth || 0)); // 宿主宽度（几何计算）
  const visCount = Math.max(1, Number(env.visCount || 1)); // 可见根数（几何计算）
  // NEW: 统一符号宽度来源（设置项外）：优先外部 symbolWidthPx（中枢派生），否则根据 hostWidth+visCount 估算
  const extW = Number(env.symbolWidthPx || NaN);
  const approxW =
    hostWidth > 1 && visCount > 0
      ? Math.floor((hostWidth * 0.88) / visCount)
      : 8; // 估算宽度
  const markerW = Number.isFinite(extW)
    ? Math.max(chan.markerMinPx, Math.min(chan.markerMaxPx, Math.round(extW)))
    : Math.max(chan.markerMinPx, Math.min(chan.markerMaxPx, approxW));

  // 统一高度与偏移来源：仅由 index.js 的 CHAN_DEFAULTS 决定（不读持久化，不写死常量）
  const markerH = Math.max(1, Math.round(Number(CHAN_DEFAULTS.markerHeightPx)));
  const offsetDownPx = Math.round(
    markerH + Number(CHAN_DEFAULTS.markerYOffsetPx)
  );

  const upPoints = [];
  const downPoints = []; // 承载点集合
  for (let i = 0; i < (reducedBars || []).length; i++) {
    const rb = reducedBars[i];
    const d = Number(rb?.dir_int || 0);
    if (!Number.isFinite(d) || d === 0) continue;
    const x = Number(rb?.anchor_idx_orig ?? rb?.end_idx_orig ?? i);
    const point = [x, 0];
    if (d > 0) upPoints.push(point);
    else downPoints.push(point);
  }

  function downSample(arr, maxN) {
    const n = arr.length;
    if (n <= maxN) return arr;
    const step = Math.ceil(n / maxN);
    const out = [];
    for (let i = 0; i < n; i += step) out.push(arr[i]);
    return out;
  }
  const upArr = downSample(upPoints, chan.maxVisibleMarkers);
  const dnArr = downSample(downPoints, chan.maxVisibleMarkers);

  const preset =
    CHAN_MARKER_PRESETS[chan.visualPreset] ||
    CHAN_MARKER_PRESETS["tri-default"];

  const upShape = chan.upShape || preset.up.shape;
  const downShape = chan.downShape || preset.down.shape;
  const upFill = chan.upColor || preset.up.fill;
  const downFill = chan.downColor || preset.down.fill;

  const commonScatter = {
    type: "scatter",
    yAxisIndex: 1, // 不变量：隐藏 y 轴 index=1
    symbolSize: () => [markerW, markerH], // 宽高统一受中枢派生几何控制
    symbolOffset: [0, offsetDownPx], // 底部偏移
    clip: false,
    tooltip: { show: false },
    z: 2,
    emphasis: { scale: false },
  };

  const upSeries = {
    ...commonScatter,
    id: "CHAN_UP",
    name: "CHAN_UP", // 不变量：id: "CHAN_UP"
    data: upArr,
    symbol: upShape,
    symbolRotate: preset.up.rotate || 0,
    itemStyle: { color: upFill, opacity: chan.opacity },
  };
  const downSeries = {
    ...commonScatter,
    id: "CHAN_DOWN",
    name: "CHAN_DOWN", // 不变量：id: "CHAN_DOWN"
    data: dnArr,
    symbol: downShape,
    symbolRotate: preset.down.rotate || 180,
    itemStyle: { color: downFill, opacity: chan.opacity },
  };

  return {
    series: [upSeries, downSeries],
  };
}

// 分型标记：横坐标用 k2_idx_orig；绑定主轴 yAxisIndex=0；高度与间距由 FRACTAL_DEFAULTS 集中决定
export function buildFractalMarkers(reducedBars, fractals, env = {}) {
  const settings = useUserSettings();
  const cfg = Object.assign(
    {},
    FRACTAL_DEFAULTS,
    (settings.fractalSettings && settings.fractalSettings.value) || {}
  );
  if (!cfg.enabled) return { series: [] };

  const hostWidth = Math.max(1, Number(env.hostWidth || 0)); // 宿主宽
  const visCount = Math.max(1, Number(env.visCount || 1)); // 可见根数

  // NEW: 外部宽度覆盖（来自主窗广播）
  const extW = Number(env.symbolWidthPx || NaN);
  const approxW =
    hostWidth > 1 && visCount > 0
      ? Math.floor((hostWidth * 0.88) / visCount)
      : 8;
  const markerW = Number.isFinite(extW)
    ? Math.max(cfg.markerMinPx, Math.min(cfg.markerMaxPx, Math.round(extW)))
    : Math.max(cfg.markerMinPx, Math.min(cfg.markerMaxPx, approxW));

  // 统一高度与顶/底偏移来源：仅使用 index.js 的 FRACTAL_DEFAULTS（不读持久化，不写死常量）
  const markerH = Math.max(
    1,
    Math.round(Number(FRACTAL_DEFAULTS.markerHeightPx))
  );
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
      symbolRotate: shape === "triangle" ? 180 : 0,
      symbolSize: () => [markerW, markerH],
      symbolOffset: [0, yOffTop], // NEW：宽度统一覆盖
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
      symbolOffset: [0, yOffBottom], // NEW：宽度统一覆盖
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
        symbolRotate: shape === "triangle" ? 180 : 0,
        symbolSize: () => [markerW, markerH],
        // 比常规分型再外移一个预设偏移量：markerH/2 + apexGap + extraGap
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

  // 预留：确认分型连线（保持默认关闭）、若启用仍沿用旧逻辑
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

// 画笔折线（每段 series）
// 不跨断档与屏障：通过 barrierIdxList 将笔在断点处分段，每段独立 line 系列。
export function buildPenLines(pensObj, env = {}) {
  const settings = useUserSettings();
  const penCfg = Object.assign(
    {},
    PENS_DEFAULTS,
    (settings.chanSettings &&
      settings.chanSettings.value &&
      settings.chanSettings.value.pen) ||
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

    // 保证加入起点
    for (let xi = xa; xi <= xb; xi++) {
      // 屏障处分段（不包含屏障点）
      if (barrierIdxSet.has(xi)) {
        if (curr.length >= 2) {
          chunks.push(curr);
        }
        curr = [];
        continue;
      }
      const t = xi - x1; // 相对原“起点”的位移（保持端点 y 精确重合）
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
        connectNulls: false, // 片段间断开，便于裁切后“只显示可见部分”
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

// 元线段（每段 series）
// 不跨断档：每个 segment 独立 series，不使用 null。

export function buildSegmentLines(segments, env = {}) {
  // NEW: 引入用户设置，并与默认值合并
  const settings = useUserSettings();
  const segCfg = Object.assign(
    {},
    SEGMENT_DEFAULTS,
    (settings.chanSettings &&
      settings.chanSettings.value &&
      settings.chanSettings.value.segment) ||
      {}
  );

  // 无数据或显式禁用 → 不渲染
  if (
    !Array.isArray(segments) ||
    !segments.length ||
    segCfg.enabled === false
  ) {
    return { series: [] };
  }

  // 取绘制样式（用户设置优先，缺失回退默认）
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
          color, // 使用用户配置颜色
          width: lineWidth, // 使用用户配置线宽
          type: lineStyle, // 使用用户配置线型
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

/**
 * 连续性屏障竖线（贯穿主窗顶底）
 * - barrierIdxList: number[]（原始 K 的索引列表）
 * - 用空数据的 line 系列承载 markLine，silent & symbol none，随 dataZoom 同步
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

// ==============================
// NEW: 十六进制 → RGBA（用于矩形填充淡显）
// ==============================
function _hexToRgba(hex, alpha = 1.0) {
  try {
    const h = String(hex || "").replace("#", "");
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    const a = Math.max(0, Math.min(1, Number(alpha || 1)));
    return `rgba(${r},${g},${b},${a})`;
  } catch {
    return hex || "#999";
  }
}

// ==============================
// NEW: 笔中枢矩形绘制（markArea + markLine 四边）
// - 每个中枢使用一个独立 series 以便设置独立颜色与 z。
// - 边框颜色与填充颜色一致，填充透明度按 alphaPercent。
// - buildPenPivotAreas 改为“静态框线”绘制（保留 markArea 填充；新增四条边以 line series 绘制；传入 sIdx/eIdx 限定显示范围）
// ==============================
export function buildPenPivotAreas(pivots, env = {}) {
  const settings = useUserSettings();
  const pvCfg = Object.assign(
    {},
    CHAN_PEN_PIVOT_DEFAULTS,
    (settings.chanSettings &&
      settings.chanSettings.value &&
      settings.chanSettings.value.penPivot) ||
      {}
  );
  if (!(pvCfg.enabled ?? true)) return { series: [] };

  const z = Number.isFinite(+pvCfg.z) ? +pvCfg.z : CHAN_PEN_PIVOT_DEFAULTS.z;
  const lineWidth = Number.isFinite(+pvCfg.lineWidth)
    ? +pvCfg.lineWidth
    : CHAN_PEN_PIVOT_DEFAULTS.lineWidth;
  const lineStyle = String(
    pvCfg.lineStyle || CHAN_PEN_PIVOT_DEFAULTS.lineStyle
  );
  const alpha =
    Math.max(0, Math.min(100, Number(pvCfg.alphaPercent || CHAN_PEN_PIVOT_DEFAULTS.alphaPercent))) /
    100;

  // 与简笔折线一致：遇屏障分段 + 稠密点列（逐索引采点） + 不使用 null 分段
  const barrierIdxSet = new Set(
    Array.isArray(env.barrierIdxList) ? env.barrierIdxList.map((x) => +x) : []
  );

  // 顶/底边按 x 从 left..right 逐一采点；遇屏障断开为独立 series
  function sampleEdgeToChunks(left, right, yConst) {
    const chunks = [];
    let curr = [];
    const xa = Math.min(left, right);
    const xb = Math.max(left, right);
    for (let xi = xa; xi <= xb; xi++) {
      // 屏障处分段（不包含屏障点）
      if (barrierIdxSet.has(xi)) {
        if (curr.length >= 2) chunks.push(curr);
        curr = [];
        continue;
      }
      curr.push([xi, yConst]);
    }
    if (curr.length >= 2) chunks.push(curr);
    return chunks;
  }

  const out = [];
  let seqCounter = 0;

  for (let idx = 0; idx < (pivots || []).length; idx++) {
    const p = pivots[idx];
    const left = Number(p.left_idx_orig);
    const right = Number(p.right_idx_orig);
    const upper = Number(p.upper);
    const lower = Number(p.lower);
    if (![left, right, upper, lower].every((v) => Number.isFinite(v))) continue;
    if (!(upper > lower)) continue; // 零厚度不呈现

    const isUp = String(p.dir_enum || "").toUpperCase() === "UP";
    const color = isUp
      ? pvCfg.upColor || CHAN_PEN_PIVOT_DEFAULTS.upColor
      : pvCfg.downColor || CHAN_PEN_PIVOT_DEFAULTS.downColor;

    // 保留内部填充（淡显），注意两端均在视窗外时 markArea 可能不显示
    out.push({
      id: `CHAN_PIVOT_AREA_${p.seq_id}_${left}_${right}_${idx}`,
      name: "CHAN_PIVOT_AREA",
      type: "line",
      yAxisIndex: 0,
      data: [],
      markArea: {
        silent: true,
        itemStyle: { color: _hexToRgba(color, alpha) },
        label: { show: false },
        data: [[{ xAxis: left, yAxis: upper }, { xAxis: right, yAxis: lower }]],
      },
      z,
      tooltip: { show: false },
      emphasis: { disabled: true },
    });

    // 顶边：段落式折线（与简笔折线相同的“段落式 series”）
    const topChunks = sampleEdgeToChunks(left, right, upper);
    for (let k = 0; k < topChunks.length; k++) {
      const data = topChunks[k];
    out.push({
        id: `CHAN_PIVOT_TOP_${p.seq_id}_${left}_${right}_${k}_${seqCounter++}`,
        name: "CHAN_PIVOT_TOP",
      type: "line",
      yAxisIndex: 0,
        data,
      showSymbol: false,
      smooth: false,
        // 不使用 null 分段（每段独立 series）
        connectNulls: false,
        lineStyle: { color, width: lineWidth, type: lineStyle },
      z,
      tooltip: { show: false },
      emphasis: { disabled: true },
    });
    }

    // 底边：段落式折线
    const bottomChunks = sampleEdgeToChunks(left, right, lower);
    for (let k = 0; k < bottomChunks.length; k++) {
      const data = bottomChunks[k];
    out.push({
        id: `CHAN_PIVOT_BOTTOM_${p.seq_id}_${left}_${right}_${k}_${seqCounter++}`,
        name: "CHAN_PIVOT_BOTTOM",
      type: "line",
      yAxisIndex: 0,
        data,
      showSymbol: false,
      smooth: false,
        connectNulls: false,
        lineStyle: { color, width: lineWidth, type: lineStyle },
      z,
      tooltip: { show: false },
      emphasis: { disabled: true },
    });
    }

    // 垂直边（左/右）：段落式不适用，中枢垂直边用两点线段即可（与简笔技术路线一致的 line series）
    out.push({
      id: `CHAN_PIVOT_LEFT_${p.seq_id}_${left}_${seqCounter++}`,
      name: "CHAN_PIVOT_LEFT",
      type: "line",
      yAxisIndex: 0,
      data: [
        [left, lower],
        [left, upper],
      ],
      showSymbol: false,
      smooth: false,
      connectNulls: false,
      lineStyle: { color, width: lineWidth, type: lineStyle },
      z,
      tooltip: { show: false },
      emphasis: { disabled: true },
    });
    // 右边（垂直）——静态全高
    out.push({
      id: `CHAN_PIVOT_RIGHT_${p.seq_id}_${right}_${seqCounter++}`,
      name: "CHAN_PIVOT_RIGHT",
      type: "line",
      yAxisIndex: 0,
      data: [
        [right, lower],
        [right, upper],
      ],
      showSymbol: false,
      smooth: false,
      connectNulls: false,
      lineStyle: { color, width: lineWidth, type: lineStyle },
      z,
      tooltip: { show: false },
      emphasis: { disabled: true },
    });
  }
  return { series: out };
}
