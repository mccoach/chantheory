// src/constants/charts/chan.js
// ==============================
// 说明：缠论相关的所有配置常量
// 职责：提供缠论标记/分型/笔/线段/中枢的默认配置
// 设计：按功能模块分组，每个常量都有详细注释
// ==============================

// ===== 涨跌标记配置 =====
export const CHAN_DEFAULTS = {
  // --- 总开关（设置窗已暴露）---
  showUpDownMarkers: true,  // 是否显示涨跌标记（✅ 设置窗可改）

  // --- 承载点策略（设置窗已暴露）---
  anchorPolicy: "extreme",  // 承载点位置："extreme"=极值点 | "right"=右端点（✅ 设置窗可改）

  // --- 标记尺寸（设置窗未暴露）---
  markerMinPx: 1,           // 标记最小宽度（像素）（❌ 设置窗未暴露，直接用常量）
  markerMaxPx: 16,          // 标记最大宽度（像素）（❌ 设置窗未暴露，直接用常量）
  markerHeightPx: 10,       // 标记固定高度（像素）（❌ 设置窗未暴露，直接用常量）
  markerYOffsetPx: 2,       // 标记距K线顶/底的间距（像素）（❌ 设置窗未暴露，直接用常量）

  // --- 标记样式（设置窗已暴露）---
  opacity: 0.9,             // 标记透明度（0-1）（❌ 设置窗未暴露，直接用常量）
  upShape: "arrow",         // 上涨标记形状（✅ 设置窗可改）
  upColor: "#f56c6c",       // 上涨标记颜色（✅ 设置窗可改）
  downShape: "arrow",       // 下跌标记形状（✅ 设置窗可改）
  downColor: "#00ff00",     // 下跌标记颜色（✅ 设置窗可改）

  // --- 性能优化（设置窗未暴露）---
  maxVisibleMarkers: 10000, // 最大可见标记数（降采样阈值）（❌ 设置窗未暴露，直接用常量）
};

// ===== 分型配置 =====
export const FRACTAL_DEFAULTS = {
  // --- 总开关（设置窗已暴露）---
  enabled: true,            // 是否启用分型识别（✅ 设置窗可改，通过三态总控）

  // --- 确认连线（设置窗未暴露）---
  showConfirmLink: false,   // 是否显示确认分型的连线（❌ 设置窗未暴露，直接用常量）
  confirmLinkStyle: {       // 确认连线样式（❌ 设置窗未暴露，直接用常量）
    color: "rgba(200,200,200,0.5)",  // 连线颜色
    width: 1.2,             // 连线宽度
    lineStyle: "dashed",    // 连线样式
  },

  // --- 空心边框（设置窗未暴露）---
  hollowBorderWidth: 1.2,   // 空心标记的边框宽度（❌ 设置窗未暴露，直接用常量）

  // --- 显著度判定（设置窗已暴露）---
  minTickCount: 0,          // 最小tick数（✅ 设置窗可改）
  minPct: 0,                // 最小幅度百分比（✅ 设置窗可改）
  minCond: "or",            // 判断条件："or"=满足一项即可 | "and"=必须同时满足（✅ 设置窗可改）

  // --- 强度显示控制（设置窗已暴露）---
  showStrength: {           // 各强度的显示开关（✅ 设置窗可改，通过复选框）
    strong: true,           // 显示强分型
    standard: true,         // 显示标准分型
    weak: true,             // 显示弱分型
  },

  // --- 标记尺寸（设置窗未暴露，与 CHAN_DEFAULTS 共享）---
  markerMinPx: 1,           // 标记最小宽度（❌ 设置窗未暴露，直接用常量）
  markerMaxPx: 16,          // 标记最大宽度（❌ 设置窗未暴露，直接用常量）
  markerHeightPx: 10,       // 标记固定高度（❌ 设置窗未暴露，直接用常量）
  markerYOffsetPx: 2,       // 标记距分型点的间距（❌ 设置窗未暴露，直接用常量）

  // --- 默认形状（设置窗未直接用，作为兜底）---
  topShape: "triangle",     // 顶分型默认形状（兜底值，实际从 styleByStrength 读取）
  bottomShape: "triangle",  // 底分型默认形状（兜底值，实际从 styleByStrength 读取）

  // --- 各强度样式（设置窗已暴露）---
  styleByStrength: {
    strong: {                // 强分型样式（✅ 设置窗可改）
      bottomShape: "triangle",  // 底分型形状
      bottomColor: "#FF0000",   // 底分型颜色
      topShape: "triangle",     // 顶分型形状
      topColor: "#FF0000",      // 顶分型颜色
      fill: "solid",            // 填充方式："solid"=实心 | "hollow"=空心
      enabled: true,            // 是否启用
    },
    standard: {              // 标准分型样式（✅ 设置窗可改）
      bottomShape: "triangle",
      bottomColor: "#FFFF00",
      topShape: "triangle",
      topColor: "#FFFF00",
      fill: "solid",
      enabled: true,
    },
    weak: {                  // 弱分型样式（✅ 设置窗可改）
      bottomShape: "triangle",
      bottomColor: "#90EE90",
      topShape: "triangle",
      topColor: "#90EE90",
      fill: "hollow",          // 弱分型默认空心
      enabled: true,
    },
  },

  // --- 确认分型样式（设置窗已暴露）---
  confirmStyle: {            // 确认分型样式（✅ 设置窗可改）
    bottomShape: "circle",   // 底部形状
    bottomColor: "#00ff00",  // 底部颜色
    topShape: "circle",      // 顶部形状
    topColor: "#00ff00",     // 顶部颜色
    fill: "solid",           // 填充方式
    enabled: true,           // 是否启用
  },
};

// ===== 笔配置 =====
export const PENS_DEFAULTS = {
  // --- 总开关（设置窗已暴露）---
  enabled: true,            // 是否绘制笔（✅ 设置窗可改）

  // --- 线条样式（设置窗已暴露）---
  lineWidth: 2,             // 笔线宽度（✅ 设置窗可改）
  color: "#ffffff",         // 笔线颜色（✅ 设置窗可改）
  confirmedStyle: "solid",  // 确认笔的线型（✅ 设置窗可改）
  provisionalStyle: "dashed",  // 预备笔的线型（✅ 设置窗可改）
};

// ===== 线段配置 =====
export const SEGMENT_DEFAULTS = {
  // --- 总开关（设置窗已暴露）---
  enabled: false,           // 是否绘制线段（默认关闭）（✅ 设置窗可改）

  // --- 线条样式（设置窗已暴露）---
  color: "#FFD700",         // 线段颜色（✅ 设置窗可改）
  lineWidth: 3,             // 线段宽度（✅ 设置窗可改）
  lineStyle: "solid",       // 线段样式（✅ 设置窗可改）
};

// ===== 笔中枢配置 =====
export const CHAN_PEN_PIVOT_DEFAULTS = {
  // --- 总开关（设置窗已暴露）---
  enabled: true,            // 是否绘制笔中枢（✅ 设置窗可改）

  // --- 颜色样式（设置窗已暴露）---
  upColor: "#FF0000",       // 上涨中枢颜色（✅ 设置窗可改）
  downColor: "#00FF00",     // 下跌中枢颜色（✅ 设置窗可改）
  alphaPercent: 5,          // 填充透明度（0-100）（✅ 设置窗可改）

  // --- 边框样式（设置窗已暴露）---
  lineWidth: 1.5,           // 中枢边框宽度（✅ 设置窗可改）
  lineStyle: "solid",       // 中枢边框样式（✅ 设置窗可改）

  // --- 图层层级（设置窗未暴露）---
  z: 7,                     // 中枢的 z-index（❌ 设置窗未暴露，直接用常量）
};

// ===== 连续性屏障配置 =====
export const CONTINUITY_BARRIER = {
  // --- 总开关（设置窗未暴露）---
  enabled: true,            // 是否启用屏障检测（❌ 设置窗未暴露，直接用常量）

  // --- 检测参数（设置窗未暴露）---
  basePct: 0.5,             // 跳空阈值（相对百分比）（❌ 设置窗未暴露，直接用常量）

  // --- 线条样式（设置窗未暴露）---
  lineColor: "#ffdd00",     // 屏障线颜色（❌ 设置窗未暴露，直接用常量）
  lineWidth: 1.2,           // 屏障线宽度（❌ 设置窗未暴露，直接用常量）
  lineStyle: "solid",       // 屏障线样式（❌ 设置窗未暴露，直接用常量）
};