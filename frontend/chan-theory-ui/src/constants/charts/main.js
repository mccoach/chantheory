// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\constants\charts\main.js
// ==============================
// 说明：主图相关的所有配置常量
// 职责：提供K线样式和MA均线的默认配置
// 设计：按功能模块分组，每个常量都有详细注释
//
// 本轮整理（按业务逻辑归置）：
//   - ATR_stop 刺破点属于“主图 overlay 的颗粒点集合”，不应塞进 ATR_stopSettings。
//   - 新增 ATR_BREACH_DEFAULTS，集中承载其点集上限等渲染约束。
//
// V2.0 - NEW: ATR_BREACH_DEFAULTS 扩展为完整“止损标记”默认配置
//   - enabled/shape/fill/markerPercent/markerHeightPx/hollowBorderWidth/pointLimit
//   - 宽度像素 clamp 常量 ATR_BREACH_MARKER_WIDTH_PX_LIMITS（与 fractal/updown/vol 对齐）
// ==============================

import { STYLE_PALETTE } from "../common";

// ===== 主图 K 线样式配置 =====
export const DEFAULT_KLINE_STYLE = {
  // --- 柱体宽度（设置窗已暴露）---
  // 说明：
  //   - 本字段作为主图所有“柱体宽度”的唯一参数（统一应用：原始K线 + 合并K线）。
  //   - 取值为百分比（10~100，整数），UI 约束使用 UI_LIMITS.barWidthPercent。
  //   - 本轮改动：柱宽计算不再使用 BAR_USABLE_RATIO 缩放；barWidth 直接使用本百分比。
  barPercent: 85,          // K线柱体宽度百分比（默认88）（✅ 设置窗已暴露）

  // --- 原始K线样式（设置窗已暴露）---
  upColor: "#f56c6c",       // 阳线颜色（✅ 设置窗可改）
  downColor: "#26a69a",     // 阴线颜色（✅ 设置窗可改）
  originalFadeUpPercent: 100,    // 阳线填充淡显百分比（0=透明，100=不透明）（✅ 设置窗可改）
  originalFadeDownPercent: 0,    // 阴线填充淡显百分比（0=透明，100=不透明）（✅ 设置窗可改）
  originalEnabled: true,    // 是否显示原始K线（✅ 设置窗可改）
  originalBorderWidth: 1.2, // 原始K线边框宽度（❌ 设置窗未暴露，直接用常量）

  // --- 合并K线开关（设置窗已暴露）---
  mergedEnabled: true,      // 是否显示合并K线（✅ 设置窗可改）

  // --- 合并K线样式（设置窗已暴露）---
  mergedK: {
    outlineWidth: 1.5,      // 合并K线轮廓线宽度（✅ 设置窗可改）
    upColor: "#FF0000",     // 上涨颜色（✅ 设置窗可改）
    downColor: "#00ff00",   // 下跌颜色（✅ 设置窗可改）
    fillFadePercent: 0,     // 填充淡显百分比（0=透明，100=不透明）（✅ 设置窗可改）
    displayOrder: "first",  // 显示层级："first"=前端 | "after"=后端（✅ 设置窗可改）
  },
};

// ===== NEW: 原始K线柱宽额外收缩（百分比点）=====
// 说明：
//   - 在“单一 barPercent”机制基础上，仅对“原始K线”额外减小该百分比点；
//   - 合并K线仍完全使用 barPercent（不受影响）；
//   - builder 内会对结果做 10~100 clamp，避免减到过小。
export const ORIGINAL_KLINE_BAR_SHRINK_PERCENT = 20;

// ===== 主图 MA 均线配置 =====
export const DEFAULT_MA_CONFIGS = {
  // --- MA5（设置窗已暴露）---
  MA5: {
    enabled: true,          // 是否启用（✅ 设置窗可改）
    period: 5,              // 周期（✅ 设置窗可改）
    color: STYLE_PALETTE.lines[0].color,  // 颜色（✅ 设置窗可改）
    width: 1,               // 线宽（✅ 设置窗可改）
    style: "solid",         // 线型："solid"=实线 | "dashed"=虚线 | "dotted"=点线（✅ 设置窗可改）
  },

  // --- MA10（设置窗已暴露）---
  MA10: {
    enabled: true,          // 是否启用（✅ 设置窗可改）
    period: 10,             // 周期（✅ 设置窗可改）
    color: STYLE_PALETTE.lines[1].color,  // 颜色（✅ 设置窗可改）
    width: 1,               // 线宽（✅ 设置窗可改）
    style: "solid",         // 线型（✅ 设置窗可改）
  },

  // --- MA20（设置窗已暴露）---
  MA20: {
    enabled: true,          // 是否启用（✅ 设置窗可改）
    period: 20,             // 周期（✅ 设置窗可改）
    color: STYLE_PALETTE.lines[2].color,  // 颜色（✅ 设置窗可改）
    width: 1,               // 线宽（✅ 设置窗可改）
    style: "solid",         // 线型（✅ 设置窗可改）
  },

  // --- MA30（设置窗已暴露，默认关闭）---
  MA30: {
    enabled: true,         // 是否启用（默认关闭）（✅ 设置窗可改）
    period: 30,             // 周期（✅ 设置窗可改）
    color: STYLE_PALETTE.lines[3].color,  // 颜色（✅ 设置窗可改）
    width: 1,               // 线宽（✅ 设置窗可改）
    style: "solid",        // 线型（虚线，区分短期MA）（✅ 设置窗可改）
  },

  // --- MA60（设置窗已暴露，默认关闭）---
  MA60: {
    enabled: true,         // 是否启用（默认关闭）（✅ 设置窗可改）
    period: 60,             // 周期（✅ 设置窗可改）
    color: STYLE_PALETTE.lines[4].color,  // 颜色（✅ 设置窗可改）
    width: 1,               // 线宽（✅ 设置窗可改）
    style: "solid",        // 线型（✅ 设置窗可改）
  },

  // --- MA120（设置窗已暴露，默认关闭）---
  MA120: {
    enabled: false,         // 是否启用（默认关闭）（✅ 设置窗可改）
    period: 120,            // 周期（✅ 设置窗可改）
    color: STYLE_PALETTE.lines[5].color,  // 颜色（✅ 设置窗可改）
    width: 1,               // 线宽（✅ 设置窗可改）
    style: "solid",        // 线型（点线，区分中长期MA）（✅ 设置窗可改）
  },

  // --- MA250（设置窗已暴露，默认关闭）---
  MA250: {
    enabled: false,         // 是否启用（默认关闭）（✅ 设置窗可改）
    period: 250,            // 周期（年线）（✅ 设置窗可改）
    color: STYLE_PALETTE.lines[6].color,  // 颜色（✅ 设置窗可改）
    width: 1,               // 线宽（✅ 设置窗可改）
    style: "solid",        // 线型（✅ 设置窗可改）
  },
};

// ===== ATR_stop 设置（按行独立；无总开关字段）=====
// 约束：
//   - TR 与 MATR 不出图且无样式设置入口；这里仅保留最终止损线 ATR_stop 的配置。
//   - 倍数 n 不在设置页出现，但仍作为计算参数存在：由顶栏输入写入 long/short。
//   - 颜色必须为 #RRGGBB，保证 color input 显示一致。
export const DEFAULT_ATR_STOP_SETTINGS = {
  // 固定倍数止损（多/空分别独立）
  fixed: {
    long: {
      enabled: true,
      atrPeriod: 14,
      n: 3,                  // 不在设置页编辑（顶栏输入改它）
      basePriceMode: "user",  // 仍由顶栏“基准价”控制（或未来扩展），设置页不展示
      lineWidth: 1.2,
      lineStyle: "dashed",
      color: "#ffc107",
    },
    short: {
      enabled: false,
      atrPeriod: 14,
      n: 3,
      basePriceMode: "user",
      lineWidth: 1.2,
      lineStyle: "dashed",
      color: "#00bcd4",
    },
  },

  // 波动通道止损（多/空分别独立）
  chandelier: {
    long: {
      enabled: true,
      atrPeriod: 14,
      n: 5,         // 不在设置页编辑（顶栏输入改它）
      lookback: 22,
      lineWidth: 1.2,
      lineStyle: "dashed",
      color: "#ff7878",
    },
    short: {
      enabled: false,
      atrPeriod: 14,
      n: 5,
      lookback: 22,
      lineWidth: 1.2,
      lineStyle: "dashed",
      color: "#78ffb4",
    },
  },
};

// ===== NEW/UPDATED: ATR_stop 刺破点 overlay 默认配置（不进设置窗：仅默认值）=====
// 注意：
//   - 用户可通过 chartDisplay.atrBreachSettings 覆盖 enabled/shape/fill/markerPercent；
//   - 颜色不在此处配置：严格跟随对应 ATR_stop 线颜色（atrStopSettings.*.color）。
export const ATR_BREACH_DEFAULTS = {
  // 总开关（设置页可改）
  enabled: true,

  // 形状（设置页可改；选项复用 MARKER_SHAPE_OPTIONS）
  shape: "triangle",

  // 填充（设置页可改；选项复用 FILL_OPTIONS）
  fill: "solid", // 'solid'|'hollow'

  // 标记宽%（设置页可改；范围复用 UI_LIMITS.markerWidthPercent）
  markerPercent: 80,

  // 高度固定：与主图分型/涨跌/量窗 marker 一致（均为 10px）
  markerHeightPx: 10,

  // 空心边框宽度（仅空心时使用）
  hollowBorderWidth: 1.2,

  // 点集容量约束（不进设置窗）
  pointLimit: {
    maxPoints: 20000,
  },
};

// ===== NEW: ATR breach marker 宽度 clamp（像素）=====
// 说明：与 FRACTAL_MARKER_WIDTH_PX_LIMITS / UPDOWN_MARKER_WIDTH_PX_LIMITS / VOL_MARKER_WIDTH_PX_LIMITS 对齐。
export const ATR_BREACH_MARKER_WIDTH_PX_LIMITS = {
  minPx: 1,
  maxPx: 16,
};
