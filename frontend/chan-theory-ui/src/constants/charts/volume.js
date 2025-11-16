// src/constants/charts/volume.js
// ==============================
// 说明：量窗相关的所有配置常量
// 职责：提供成交量/成交额的显示配置
// 设计：按功能模块分组，每个常量都有详细注释
// ==============================

import { STYLE_PALETTE } from "../common";

// ===== 量窗默认设置 =====
export const DEFAULT_VOL_SETTINGS = {
  // --- 显示模式（设置窗未直接暴露，通过下拉切换）---
  mode: "vol",              // 显示模式："vol"=成交量 | "amount"=成交额（❌ 设置窗未暴露，通过IndicatorPanel下拉切换）

  // --- 单位显示（设置窗未暴露）---
  unit: "auto",             // 单位显示："auto"=自动 | "hand"=手 | "share"=股（❌ 设置窗未暴露，直接用常量）

  // --- 相对成交量计算（设置窗未暴露）---
  rvolN: 20,                // 相对成交量的基准周期（RVOL = VOL / MA(VOL, N)）（❌ 设置窗未暴露，直接用常量）

  // --- 布局参数（设置窗未暴露）---
  layout: {
    barUsableRatio: 0.88,   // 可用绘图区占容器宽度的比例（0.88 = 88%）（❌ 设置窗未暴露，直接用常量）
    fallbackBarWidth: 8,    // 兜底柱宽（当计算失败时使用）（❌ 设置窗未暴露，直接用常量）
  },

  // --- 量额柱样式（设置窗已暴露）---
  volBar: {
    barPercent: 100,        // 柱体宽度百分比（100=不压缩）（✅ 设置窗可改）
    upColor: STYLE_PALETTE.bars.volume.up,    // 阳线颜色（✅ 设置窗可改）
    downColor: STYLE_PALETTE.bars.volume.down,  // 阴线颜色（✅ 设置窗可改）
  },

  // --- 均线样式（设置窗已暴露）---
  mavolStyles: {
    MAVOL5: {                // MAVOL5 配置（✅ 设置窗可改）
      enabled: true,         // 是否启用
      period: 5,             // 周期
      width: 1,              // 线宽
      style: "solid",        // 线型
      color: STYLE_PALETTE.lines[0].color,  // 颜色
      namePrefix: "MAVOL",   // 名称前缀（用于tooltip显示）
    },
    MAVOL10: {               // MAVOL10 配置（✅ 设置窗可改）
      enabled: true,
      period: 10,
      width: 1,
      style: "solid",
      color: STYLE_PALETTE.lines[1].color,
      namePrefix: "MAVOL",
    },
    MAVOL20: {               // MAVOL20 配置（✅ 设置窗可改）
      enabled: true,
      period: 20,
      width: 1,
      style: "solid",
      color: STYLE_PALETTE.lines[2].color,
      namePrefix: "MAVOL",
    },
  },

  // --- 放量标记（设置窗已暴露）---
  markerPump: {
    enabled: true,          // 是否启用（✅ 设置窗可改）
    shape: "arrow",         // 标记形状（✅ 设置窗可改）
    color: "#FFFF00",       // 标记颜色（✅ 设置窗可改）
    threshold: 1.5,         // 放量阈值（VOL ≥ threshold * MAVOL 时触发）（✅ 设置窗可改）
  },

  // --- 缩量标记（设置窗已暴露）---
  markerDump: {
    enabled: true,          // 是否启用（✅ 设置窗可改）
    shape: "arrow",         // 标记形状（✅ 设置窗可改）
    color: "#00ff00",       // 标记颜色（✅ 设置窗可改）
    threshold: 0.7,         // 缩量阈值（VOL ≤ threshold * MAVOL 时触发）（✅ 设置窗可改）
  },
};

// ===== 量窗标记尺寸（设置窗未暴露）=====
export const DEFAULT_VOL_MARKER_SIZE = {
  minPx: 1,                 // 标记最小宽度（像素）（❌ 设置窗未暴露，直接用常量）
  maxPx: 16,                // 标记最大宽度（像素）（❌ 设置窗未暴露，直接用常量）
  markerHeightPx: 10,       // 标记固定高度（像素）（❌ 设置窗未暴露，直接用常量）
  markerYOffsetPx: 2,       // 标记距柱顶的间距（像素）（❌ 设置窗未暴露，直接用常量）
};