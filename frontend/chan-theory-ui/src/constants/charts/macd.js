// src/constants/charts/macd.js
// ==============================
// 说明：技术指标相关配置常量
// 职责：提供 MACD 等副图指标的默认配置
// 设计：与 DEFAULT_VOL_SETTINGS 等风格保持一致
// ==============================

import { STYLE_PALETTE } from "../common";

// ===== MACD 默认设置 =====
export const DEFAULT_MACD_SETTINGS = {
  // --- 指标周期（设置窗已暴露）---
  period: {
    fast: 12,   // 快线周期（DIF 的 EMA 快线）
    slow: 26,   // 慢线周期（DIF 的 EMA 慢线）
    signal: 9,  // DEA 周期（对 DIF 的 EMA）
  },

  // --- 折线样式（设置窗已暴露）---
  lines: {
    enabled: true,                             // 是否绘制 DIF/DEA 折线
    difColor: STYLE_PALETTE.lines[8].color,    // DIF 颜色
    difStyle: "solid",                         // DIF 线型
    deaColor: STYLE_PALETTE.lines[9].color,    // DEA 颜色
    deaStyle: "solid",                         // DEA 线型
    width: 1.0,                                // 折线线宽
    z: 4,                                      // 折线图层 z 值
  },

  // --- 柱体样式（设置窗已暴露）---
  hist: {
    enabled: true,                             // 是否绘制 MACD 柱体
    barPercent: 80,                            // 柱宽百分比
    upColor: STYLE_PALETTE.bars.macd.positive, // 多方颜色（HIST>=0）
    downColor: STYLE_PALETTE.bars.macd.negative, // 空方颜色（HIST<0）
    z: 3,                                      // 柱体图层 z 值
  },
};