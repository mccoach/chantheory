// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers.js
// ==============================
// 缠论覆盖图层（逐行注释）
// - 统一“设置项”读取规则：优先取本地持久化（useUserSettings），缺失时回退 constants 中的默认预置；不再在本地写死兜底值。
// - 涨跌标记：绑定隐藏 yAxis=1（不变量），符号宽度统一来源于中枢派生（env.symbolWidthPx），若未传则按 hostWidth/visCount 估算，仅作为几何估算而非设置项。
// - 分型标记：绑定主价格轴 yAxisIndex=0（不变量）；样式与开关来自 FRACTAL_DEFAULTS + 本地持久化 fractalSettings。
// - 画笔折线：绑定主价格轴 yAxisIndex=0（不变量）；样式来自 PENS_DEFAULTS + 本地持久化 chanSettings.pen；不再从 env 读取样式。
// - 本次变动：标记高度集中归口 index.js —— 主窗涨跌用 CHAN_DEFAULTS.markerHeightPx / 分型用 FRACTAL_DEFAULTS.markerHeightPx。
import {
  CHAN_MARKER_PRESETS, // 视觉预设集合
  CHAN_DEFAULTS, // 缺省参数（包含图形/颜色/最大数量）
  FRACTAL_DEFAULTS, // 分型默认（包含样式与间距）
  PENS_DEFAULTS, // 画笔默认方案（线宽/颜色/线型/开关）
} from "@/constants";

import { useUserSettings } from "@/composables/useUserSettings";

// 涨跌标记（横坐标 = anchor_idx；绑定隐藏 yAxis=1；支持外部 width 覆盖）
// 设置项来源：useUserSettings().chanSettings（优先）→ CHAN_DEFAULTS（兜底）
// 几何宽度来源：env.symbolWidthPx（中枢统一广播，优先）→ 按 hostWidth/visCount 估算（仅几何，不属于设置项）
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
    const d = Number(rb?.dir || 0);
    if (!Number.isFinite(d) || d === 0) continue;
    const x = Number(rb.anchor_idx ?? rb.idx_end ?? i); // 横坐标：承载点（原始K索引）
    const point = [x, 0]; // 隐藏轴固定 y=0 —— 垂直定位锚点
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

// 分型标记：横坐标用 xIndex；绑定主轴 yAxisIndex=0；高度/间距按外部宽度与默认规则
// 设置项来源：useUserSettings().fractalSettings（优先）→ FRACTAL_DEFAULTS（兜底）
// 几何宽度来源：env.symbolWidthPx（中枢统一广播，优先）→ 按 hostWidth/visCount 估算（仅几何，不属于设置项）
// 本次变动：高度统一使用 FRACTAL_DEFAULTS.markerHeightPx（或持久化值），不再按宽度推导高度。
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
  const markerH = Math.max(1, Math.round(Number(FRACTAL_DEFAULTS.markerHeightPx)));
  const apexGap = Math.max(0, Math.round(Number(FRACTAL_DEFAULTS.markerYOffsetPx))); // 顶点距 bar 的预设间距
  const yOffTop = -(markerH / 2 + apexGap);     // 顶分中心向上偏移
  const yOffBottom = +(markerH / 2 + apexGap);  // 底分中心向下偏移

  const bins = {
    top: { strong: [], standard: [], weak: [] },
    bottom: { strong: [], standard: [], weak: [] },
  };

  for (const f of fractals || []) {
    // 根据 showStrength 开关过滤
    if (!cfg.showStrength?.[f.strength]) continue;
    const x = Number(f.xIndex); // 横坐标（承载点索引）
    if (f.type === "top") bins.top[f.strength].push({ value: [x, f.G2] });
    else bins.bottom[f.strength].push({ value: [x, f.D2] });
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

  // 确认分型标记（比常规分型再外移 markerH + 4 px）
  (function appendConfirmMarkers() {
    const cs = cfg.confirmStyle || {};
    if (!cs.enabled) return;
    const topConfirmData = [];
    const botConfirmData = [];
    for (const f of fractals || []) {
      if (!f?.confirm?.paired) continue;
      if (f.type === "top") topConfirmData.push({ value: [f.xIndex, f.G2] });
      else botConfirmData.push({ value: [f.xIndex, f.D2] });
    }

    // 统一额外外移量：仅用 FRACTAL_DEFAULTS.markerYOffsetPx，无硬编码常量
    const extraGap = Math.max(0, Math.round(Number(FRACTAL_DEFAULTS.markerHeightPx) + Number(FRACTAL_DEFAULTS.markerYOffsetPx)));

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
  })();

  // 确认分型连线（按设定绘制）
  if (cfg.showConfirmLink) {
    const segs = [];
    for (const f of fractals || []) {
      if (!f.confirm?.paired || f.confirm?.role !== "first") continue;
      const partner = (fractals || []).find(
        (x) =>
          x.confirm?.paired &&
          x.confirm?.pair_id === f.confirm.pair_id &&
          x.confirm?.role === "second"
      );
      if (!partner) continue;
      if (f.type === "top")
        segs.push([
          [f.xIndex, f.G2],
          [partner.xIndex, partner.G2],
        ]);
      else
        segs.push([
          [f.xIndex, f.D2],
          [partner.xIndex, partner.D2],
        ]);
    }
    if (segs.length) {
      const data = [];
      segs.forEach((s) => {
        data.push(s[0], s[1], null);
      });
      series.push({
        id: "FR_CONFIRM_LINKS",
        name: "FR_CONFIRM",
        type: "line",
        yAxisIndex: 0,
        data,
        connectNulls: false,
        showSymbol: false,
        lineStyle: {
          color: "rgba(200,200,200,0.5)",
          width: 1.2,
          type: "dashed",
        },
        z: 4,
        tooltip: { show: false },
      });
    }
  }

  return { series };
}

// ==============================
// 画笔折线 —— buildPenLines
// - 输入 pens（computePens 的输出），生成���条系列：confirmed 与 provisional。
// - 横轴为“原始K索引”，纵轴为分型极值（G2/D2），绑定主轴 yAxisIndex=0。
// 设置项来源：useUserSettings().chanSettings.pen（优先）→ PENS_DEFAULTS（兜底）
// ==============================
export function buildPenLines(pensObj /* 不再从 env 读取样式项 */, env = {}) {
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

  const baseColor = penCfg.color; // 颜色来自本地持久化 → PENS_DEFAULTS
  const dashedColor = penCfg.color; // 预备线与确认线同色，靠线型区分
  const lineW = Number.isFinite(+penCfg.lineWidth)
    ? +penCfg.lineWidth
    : PENS_DEFAULTS.lineWidth;
  const confirmedStyle = String(
    penCfg.confirmedStyle || PENS_DEFAULTS.confirmedStyle
  );
  const provisionalStyle = String(
    penCfg.provisionalStyle || PENS_DEFAULTS.provisionalStyle
  );

  function toLineData(arr) {
    const data = [];
    for (const p of arr) {
      // 修复点：横坐标改用“原始K索引”，与主图 dates 类目轴一致
      const x1 = Number(p.startOrigIdx);
      const y1 = Number(p.startY);
      const x2 = Number(p.endOrigIdx);
      const y2 = Number(p.endY);
      if (
        Number.isFinite(x1) &&
        Number.isFinite(y1) &&
        Number.isFinite(x2) &&
        Number.isFinite(y2)
      ) {
        data.push([x1, y1]);
        data.push([x2, y2]);
        data.push(null); // 断段
      }
    }
    return data;
  }

  const confirmedData = toLineData(confirmed);
  const provisionalData = toLineData(provisional);

  const series = [];
  if (confirmedData.length) {
    series.push({
      id: "CHAN_PENS_CONFIRMED",
      name: "CHAN_PENS_CONFIRMED",
      type: "line",
      yAxisIndex: 0,
      data: confirmedData,
      showSymbol: false,
      smooth: false,
      lineStyle: { color: baseColor, width: lineW, type: confirmedStyle },
      itemStyle: { color: baseColor },
      color: baseColor,
      z: 4,
      connectNulls: false,
      tooltip: { show: false },
      emphasis: { disabled: true },
    });
  }
  if (provisionalData.length) {
    series.push({
      id: "CHAN_PENS_PROVISIONAL",
      name: "CHAN_PENS_PROVISIONAL",
      type: "line",
      yAxisIndex: 0,
      data: provisionalData,
      showSymbol: false,
      smooth: false,
      lineStyle: { color: dashedColor, width: lineW, type: provisionalStyle },
      itemStyle: { color: dashedColor },
      color: dashedColor,
      z: 3,
      connectNulls: false,
      tooltip: { show: false },
      emphasis: { disabled: true },
    });
  }
  return { series };
}
