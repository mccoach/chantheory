// src/constants/charts/main.js
// ==============================
// 说明：主图相关的所有配置常量
// 职责：提供K线样式和MA均线的默认配置
// 设计：按功能模块分组，每个常量都有详细注释
// ==============================

import { STYLE_PALETTE } from "../common";

// ===== 主图 K 线样式配置 =====
export const DEFAULT_KLINE_STYLE = {
  // --- 柱体宽度（设置窗未暴露）---
  barPercent: 100,          // K线柱体宽度百分比（100=不压缩）（❌ 设置窗未暴露，直接用常量）

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
    enabled: false,         // 是否启用（默认关闭）（✅ 设置窗可改）
    period: 30,             // 周期（✅ 设置窗可改）
    color: STYLE_PALETTE.lines[3].color,  // 颜色（✅ 设置窗可改）
    width: 1,               // 线宽（✅ 设置窗可改）
    style: "dashed",        // 线型（虚线，区分短期MA）（✅ 设置窗可改）
  },

  // --- MA60（设置窗已暴露，默认关闭）---
  MA60: {
    enabled: false,         // 是否启用（默认关闭）（✅ 设置窗可改）
    period: 60,             // 周期（✅ 设置窗可改）
    color: STYLE_PALETTE.lines[4].color,  // 颜色（✅ 设置窗可改）
    width: 1,               // 线宽（✅ 设置窗可改）
    style: "dashed",        // 线型（✅ 设置窗可改）
  },

  // --- MA120（设置窗已暴露，默认关闭）---
  MA120: {
    enabled: false,         // 是否启用（默认关闭）（✅ 设置窗可改）
    period: 120,            // 周期（✅ 设置窗可改）
    color: STYLE_PALETTE.lines[5].color,  // 颜色（✅ 设置窗可改）
    width: 1,               // 线宽（✅ 设置窗可改）
    style: "dotted",        // 线型（点线，区分中长期MA）（✅ 设置窗可改）
  },

  // --- MA250（设置窗已暴露，默认关闭）---
  MA250: {
    enabled: false,         // 是否启用（默认关闭）（✅ 设置窗可改）
    period: 250,            // 周期（年线）（✅ 设置窗可改）
    color: STYLE_PALETTE.lines[6].color,  // 颜色（✅ 设置窗可改）
    width: 1,               // 线宽（✅ 设置窗可改）
    style: "dotted",        // 线型（✅ 设置窗可改）
  },
};