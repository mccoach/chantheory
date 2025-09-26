// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers.js
// ==============================
// 缠论覆盖图层（逐行注释）
// - 新增：支持 env.symbolWidthPx 外部宽度覆盖（来自主窗广播的统一符号宽度）。
// - 涨跌标记：绑定隐藏 yAxis=1（不变量），优先使用 env.symbolWidthPx；否则根据 hostWidth+visCount 估算。
// - 分型标记：绑定主价格轴 yAxisIndex=0（不变量），同样支持外部宽度覆盖；高度按比例随宽度调整。
// ==============================

import {
  CHAN_MARKER_PRESETS, // 视觉预设集合
  CHAN_DEFAULTS, // 缺省参数（包含图形/颜色/最大数量）
  FRACTAL_DEFAULTS, // 分型默认（包含样式与间距）
} from "@/constants";

// 涨跌标记（横坐标 = anchor_idx；绑定隐藏 yAxis=1；支持外部 width 覆盖）
export function buildUpDownMarkers(reducedBars, env = {}) {
  const chan = Object.assign({}, CHAN_DEFAULTS, env.chanSettings || {}); // 合并设置
  const hostWidth = Math.max(1, Number(env.hostWidth || 0)); // 宿主宽度
  const visCount = Math.max(1, Number(env.visCount || 1)); // 可见根数
  const preset =
    CHAN_MARKER_PRESETS[chan.visualPreset] ||
    CHAN_MARKER_PRESETS["tri-default"];

  // NEW: 符号宽度统一覆盖（若提供）
  const extW = Number(env.symbolWidthPx || NaN); // 外部宽度像素
  const approxW =
    hostWidth > 1 && visCount > 0
      ? Math.floor((hostWidth * 0.88) / visCount)
      : 8; // 估算宽度
  const markerW = Number.isFinite(extW)
    ? Math.max(chan.markerMinPx, Math.min(chan.markerMaxPx, Math.round(extW))) // 使用外部宽度
    : Math.max(chan.markerMinPx, Math.min(chan.markerMaxPx, approxW)); // 使用估算宽度

  const markerH = 10; // —— 修复：高度恒定 10px —— //
  const offsetDownPx = Math.round(markerH * 1.2);

  const upPoints = [];
  const downPoints = []; // 承载点集合
  for (let i = 0; i < (reducedBars || []).length; i++) {
    const rb = reducedBars[i];
    const d = Number(rb?.dir || 0);
    if (!Number.isFinite(d) || d === 0) continue;
    const x = Number(rb.anchor_idx ?? rb.idx_end ?? i);
    const point = [x, 0]; // 隐藏轴固定 y=0
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

  const upShape = chan.upShape || preset.up.shape;
  const downShape = chan.downShape || preset.down.shape;
  const upFill = chan.upColor || preset.up.fill;
  const downFill = chan.downColor || preset.down.fill;

  const commonScatter = {
    type: "scatter",
    yAxisIndex: 1, // 不变量：隐藏 y 轴 index=1
    symbolSize: () => [markerW, markerH], // NEW：宽高统一受外部覆盖
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

  const extra = { xAxisLabelMargin: Math.max(14, markerH + 12) }; // 预留横轴 margin
  if (!upArr.length && !dnArr.length) {
    return {
      series: [
        { ...upSeries, data: [] },
        { ...downSeries, data: [] },
      ],
      extra,
    };
  }
  return { series: [upSeries, downSeries], extra };
}

// 分型标记：横坐标用 xIndex；绑定主轴 yAxisIndex=0；高度/间距按外部宽度与默认规则
export function buildFractalMarkers(reducedBars, fractals, env = {}) {
  const cfg = Object.assign({}, FRACTAL_DEFAULTS, env.fractalSettings || {}); // 合并配置
  if (!cfg.enabled) return { series: [] }; // 未启用不绘制

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
  const markerH = Math.max(8, Math.round(markerW * 0.8)); // 高度与宽度比例
  const apexGap = Math.abs(cfg.markerYOffsetPx || 2); // 顶点距 bar 间距（2px）
  const yOffTop = -(markerH / 2 + apexGap); // 顶分中心向上偏移（顶点与 bar 间距 2px）
  const yOffBottom = +(markerH / 2 + apexGap); // 底分中心向下偏移（顶点与 bar 间距 2px）

  const bins = {
    top: { strong: [], standard: [], weak: [] },
    bottom: { strong: [], standard: [], weak: [] },
  };

  for (const f of fractals || []) {
    if (!cfg.showStrength?.[f.strength]) continue;
    const x = Number(f.xIndex); // 横坐标（承载点索引）
    if (f.type === "top") bins.top[f.strength].push({ value: [x, f.G2] });
    else bins.bottom[f.strength].push({ value: [x, f.D2] });
  }

  const series = []; // 分型系列集合

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
      FRACTAL_DEFAULTS.topColors?.[sp.k];
    const fillMode = st.fill || "solid";
    const isHollow = fillMode === "hollow";

    series.push({
      id: `FR_TOP_${sp.k}`,
      name: sp.name,
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
      FRACTAL_DEFAULTS.bottomColors?.[sp.k];
    const fillMode = st.fill || "solid";
    const isHollow = fillMode === "hollow";

    series.push({
      id: `FR_BOT_${sp.k}`,
      name: sp.name,
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
    const extraGap = markerH + 4; // NEW：比常规再外移（与要求一致）
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
        symbolSize: () => [markerW, markerH], // 高度恒定 10px
        symbolOffset: [0, -(markerH / 2 + (cfg.markerYOffsetPx + extraGap))],
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
        symbolSize: () => [markerW, markerH], // 高度恒定 10px
        symbolOffset: [0, +(markerH / 2 + (cfg.markerYOffsetPx + extraGap))],
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
