// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers.js  // 全量输出：缠论覆盖图层
// ==============================
// 缠论覆盖图层（逐行注释）
// - 涨跌标记：改为使用“第二条隐藏 yAxis（index=1，范围 0~1）”定位，彻底与主价格 y 轴解耦；不再影响主轴自适应。
// - 分型标记：仍使用主轴（yAxisIndex=0）；如需解绑可按需扩展。
// - 顶/底三角顶点精确落在 G-2px / D+2px（通过 symbolOffset = ±(markerH/2+2) 实现）
// ==============================

import {
  CHAN_MARKER_PRESETS, // 视觉预设
  CHAN_DEFAULTS, // 缺省参数
  FRACTAL_DEFAULTS, // 分型缺省
} from "@/constants"; // 常量源

/* 涨跌标记（横坐标 = anchor_idx 原始索引；绑定到隐藏 yAxis=1，y 固定为 0） */
export function buildUpDownMarkers(reducedBars, env = {}) {
  const chan = Object.assign({}, CHAN_DEFAULTS, env.chanSettings || {}); // 合并设置
  const hostWidth = Math.max(1, Number(env.hostWidth || 0)); // 宿主宽度
  const visCount = Math.max(1, Number(env.visCount || 1)); // 可见根数
  const preset =
    CHAN_MARKER_PRESETS[chan.visualPreset] ||
    CHAN_MARKER_PRESETS["tri-default"]; // 视觉预设

  const approxBarWidthPx =
    hostWidth > 1 ? Math.max(1, Math.floor((hostWidth * 0.88) / visCount)) : 8; // 粗估柱宽
  const markerW = Math.max(
    chan.markerMinPx,
    Math.min(chan.markerMaxPx, approxBarWidthPx)
  ); // 标记宽
  const markerH = 10; // 标记高
  const offsetDownPx = Math.round(markerH * 1.2); // 向下偏移（相对隐藏轴底部）

  // 收集上涨/下跌 anchor 点
  const upPoints = []; // 上涨承载点
  const downPoints = []; // 下跌承载点
  for (let i = 0; i < (reducedBars || []).length; i++) {
    const rb = reducedBars[i]; // 当前复合柱
    const d = Number(rb?.dir || 0); // 方向
    if (!Number.isFinite(d) || d === 0) continue; // 跳过方向不明
    const x = Number(rb.anchor_idx ?? rb.idx_end ?? i); // 横坐标：承载点原始索引
    const point = [x, 0]; // y 固定为 0（隐藏轴的底部）
    if (d > 0) upPoints.push(point);
    else downPoints.push(point); // 分桶
  }

  // 简单抽稀：避免过多点渲染
  function downSample(arr, maxN) {
    const n = arr.length;
    if (n <= maxN) return arr;
    const step = Math.ceil(n / maxN);
    const out = [];
    for (let i = 0; i < n; i += step) out.push(arr[i]);
    return out;
  }
  const upArr = downSample(upPoints, chan.maxVisibleMarkers); // 上涨抽稀
  const dnArr = downSample(downPoints, chan.maxVisibleMarkers); // 下跌抽稀

  const upShape = chan.upShape || preset.up.shape; // 上涨形状
  const downShape = chan.downShape || preset.down.shape; // 下跌形状
  const upFill = chan.upColor || preset.up.fill; // 上涨颜色
  const downFill = chan.downColor || preset.down.fill; // 下跌颜色

  const commonScatter = {
    type: "scatter", // 散点
    yAxisIndex: 1, // 绑定到隐藏 yAxis（index=1，范围 0~1）
    symbolSize: () => [markerW, markerH], // 自适应尺寸
    symbolOffset: [0, offsetDownPx], // 底部偏移（向下）
    clip: false, // 不裁剪
    tooltip: { show: false }, // 不显示 tooltip
    z: 2, // 层级
    emphasis: { scale: false }, // 悬停不放大
  };

  const upSeries = {
    ...commonScatter,
    id: "CHAN_UP", // 系列 ID（供局部更新/清空）
    name: "CHAN_UP",
    data: upArr,
    symbol: upShape,
    symbolRotate: preset.up.rotate || 0,
    itemStyle: { color: upFill, opacity: chan.opacity },
  };

  const downSeries = {
    ...commonScatter,
    id: "CHAN_DOWN",
    name: "CHAN_DOWN",
    data: dnArr,
    symbol: downShape,
    symbolRotate: preset.down.rotate || 180,
    itemStyle: { color: downFill, opacity: chan.opacity },
  };

  const extra = { xAxisLabelMargin: Math.max(14, markerH + 12) }; // 预留横轴 margin
  if (!upArr.length && !dnArr.length) {
    // 无点时清空
    return {
      series: [
        { ...upSeries, data: [] },
        { ...downSeries, data: [] },
      ],
      extra,
    };
  }
  return { series: [upSeries, downSeries], extra }; // 返回系列
}

/* 分型标记：横坐标用 fractal.xIndex（承载点原始索引）；顶/底三角顶点严格贴 G-2px / D+2px */
export function buildFractalMarkers(reducedBars, fractals, env = {}) {
  const cfg = Object.assign({}, FRACTAL_DEFAULTS, env.fractalSettings || {}); // 合并配置
  if (!cfg.enabled) return { series: [] }; // 未启用直接返回

  const hostWidth = Math.max(1, Number(env.hostWidth || 0)); // 宿主宽
  const visCount = Math.max(1, Number(env.visCount || 1)); // 可见根数
  const approxBarWidthPx =
    hostWidth > 1 ? Math.max(1, Math.floor((hostWidth * 0.88) / visCount)) : 8; // 柱宽估算
  const markerW = Math.max(
    cfg.markerMinPx,
    Math.min(cfg.markerMaxPx, approxBarWidthPx)
  ); // 标记宽
  const markerH = Math.max(8, Math.round(markerW * 0.8)); // 标记高
  const apexGap = Math.abs(cfg.markerYOffsetPx || 2); // 顶点偏移

  // 顶点与中心的关系：上三角顶点在 center - H/2；下三角顶点在 center + H/2
  const yOffTop = -(markerH / 2 + apexGap); // 顶分中心向上偏移
  const yOffBottom = +(markerH / 2 + apexGap); // 底分中心向下偏移

  // 按类型与强弱分桶
  const bins = {
    top: { strong: [], standard: [], weak: [] },
    bottom: { strong: [], standard: [], weak: [] },
  };

  // 采集散点：x 用 fractal.xIndex（承载点原始索引），y 用 G2/D2（顶点所对 y 值）
  for (const f of fractals || []) {
    if (!cfg.showStrength?.[f.strength]) continue; // 强弱开关
    const x = Number(f.xIndex); // 横坐标（承载点索引）
    if (f.type === "top")
      bins.top[f.strength].push({ value: [x, f.G2] }); // 顶分
    else bins.bottom[f.strength].push({ value: [x, f.D2] }); // 底分
  }

  const series = []; // 输出系列数组

  // 顶分（下三角）：逐档样式
  const topSpec = [
    { k: "strong", name: "TOP_STRONG" },
    { k: "standard", name: "TOP_STANDARD" },
    { k: "weak", name: "TOP_WEAK" },
  ];
  for (const sp of topSpec) {
    const data = bins.top[sp.k];
    if (!data.length) continue;

    const st = (cfg.styleByStrength && cfg.styleByStrength[sp.k]) || {};
    const enabled =
      (sp.k === "strong"
        ? cfg.showStrength?.strong
        : sp.k === "standard"
        ? cfg.showStrength?.standard
        : cfg.showStrength?.weak) &&
      (st.enabled ?? true);
    if (!enabled) continue;

    const shape = st.topShape || cfg.topShape || "triangle";
    const color =
      st.topColor ||
      cfg.topColors?.[sp.k] ||
      FRACTAL_DEFAULTS.topColors?.[sp.k];
    const fillMode = st.fill || "solid";
    const isHollow = fillMode === "hollow";

    series.push({
      id: `FR_TOP_${sp.k}`, // 系列 ID
      name: sp.name,
      type: "scatter",
      yAxisIndex: 0, // 使用主价格轴
      data,
      symbol: shape,
      symbolRotate: shape === "triangle" ? 180 : 0, // 下三角
      symbolSize: () => [markerW, markerH],
      symbolOffset: [0, yOffTop], // 顶点贴合（G - 2px）
      itemStyle: isHollow
        ? { color: "transparent", borderColor: color, borderWidth: 1.2 }
        : { color },
      z: 5,
      emphasis: { scale: false },
      tooltip: { show: false },
    });
  }

  // 底分（上三角）：逐档样式
  const botSpec = [
    { k: "strong", name: "BOT_STRONG" },
    { k: "standard", name: "BOT_STANDARD" },
    { k: "weak", name: "BOT_WEAK" },
  ];
  for (const sp of botSpec) {
    const data = bins.bottom[sp.k];
    if (!data.length) continue;

    const st = (cfg.styleByStrength && cfg.styleByStrength[sp.k]) || {};
    const enabled =
      (sp.k === "strong"
        ? cfg.showStrength?.strong
        : sp.k === "standard"
        ? cfg.showStrength?.standard
        : cfg.showStrength?.weak) &&
      (st.enabled ?? true);
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
      yAxisIndex: 0, // 使用主价格轴
      data,
      symbol: shape,
      symbolRotate: 0, // 上三角
      symbolSize: () => [markerW, markerH],
      symbolOffset: [0, yOffBottom], // 顶点贴合（D + 2px）
      itemStyle: isHollow
        ? { color: "transparent", borderColor: color, borderWidth: 1.2 }
        : { color },
      z: 5,
      emphasis: { scale: false },
      tooltip: { show: false },
    });
  }

  // 确认分型标记（在原有分型标记基础上再偏离 2px）
  (function appendConfirmMarkers() {
    const cs = cfg.confirmStyle || {};
    if (!cs.enabled) return;

    const topConfirmData = [];
    const botConfirmData = [];

    for (const f of fractals || []) {
      if (!f?.confirm?.paired) continue; // 仅配对成功
      if (f.type === "top") topConfirmData.push({ value: [f.xIndex, f.G2] });
      else botConfirmData.push({ value: [f.xIndex, f.D2] });
    }

    if (topConfirmData.length) {
      const isHollow = (cs.fill || "solid") === "hollow";
      series.push({
        id: "FR_TOP_CONFIRM",
        name: "TOP_CONFIRM",
        type: "scatter",
        yAxisIndex: 0, // 使用主价格轴
        data: topConfirmData,
        symbol: cs.topShape || "triangle",
        symbolRotate: (cs.topShape || "triangle") === "triangle" ? 180 : 0, // 下三角
        symbolSize: () => [markerW, markerH],
        symbolOffset: [
          0,
          -(markerH / 2 + (Math.abs(cfg.markerYOffsetPx || 2) + markerH + 2)),
        ], // 再远离 2px
        itemStyle: isHollow
          ? {
              color: "transparent",
              borderColor:
                cs.topColor || FRACTAL_DEFAULTS.confirmStyle.topColor,
              borderWidth: 1.2,
            }
          : { color: cs.topColor || FRACTAL_DEFAULTS.confirmStyle.topColor },
        z: 6,
        emphasis: { scale: false },
        tooltip: { show: false },
      });
    }

    if (botConfirmData.length) {
      const isHollow = (cs.fill || "solid") === "hollow";
      series.push({
        id: "FR_BOT_CONFIRM",
        name: "BOT_CONFIRM",
        type: "scatter",
        yAxisIndex: 0, // 使用主价格轴
        data: botConfirmData,
        symbol: cs.bottomShape || "triangle",
        symbolRotate: 0, // 上三角
        symbolSize: () => [markerW, markerH],
        symbolOffset: [
          0,
          +(markerH / 2 + (Math.abs(cfg.markerYOffsetPx || 2) + markerH + 2)),
        ], // 再远离 2px
        itemStyle: isHollow
          ? {
              color: "transparent",
              borderColor:
                cs.bottomColor || FRACTAL_DEFAULTS.confirmStyle.bottomColor,
              borderWidth: 1.2,
            }
          : {
              color:
                cs.bottomColor || FRACTAL_DEFAULTS.confirmStyle.bottomColor,
            },
        z: 6,
        emphasis: { scale: false },
        tooltip: { show: false },
      });
    }
  })();

  // 确认分型连线（同样使用 xIndex）
  if (cfg.showConfirmLink) {
    const segs = [];
    for (const f of fractals || []) {
      if (!f.confirm?.paired || f.confirm?.role !== "first") continue; // 只取 first
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
      for (const s of segs) data.push(s[0], s[1], null);
      series.push({
        id: "FR_CONFIRM_LINKS",
        name: "FR_CONFIRM",
        type: "line",
        yAxisIndex: 0, // 使用主价格轴
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

  return { series }; // 返回系列集合
}
