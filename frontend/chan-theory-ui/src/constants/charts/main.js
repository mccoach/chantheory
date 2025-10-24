// src/constants/charts/main.js
import { STYLE_PALETTE } from "../common";

// 主图 K 线样式
export const DEFAULT_KLINE_STYLE = {
  barPercent: 100,
  upColor: "#f56c6c",
  downColor: "#26a69a",
  originalFadeUpPercent: 100,
  originalFadeDownPercent: 0,
  originalEnabled: true,
  mergedEnabled: true,
  mergedK: {
    outlineWidth: 1.5,
    upColor: "#FF0000",
    downColor: "#00ff00",
    fillFadePercent: 0,
    displayOrder: "first",
  },
};

// 主图 MA 指标
export const DEFAULT_MA_CONFIGS = {
  MA5: {
    enabled: true,
    period: 5,
    color: STYLE_PALETTE.lines[0].color,
    width: 1,
    style: "solid",
  },
  MA10: {
    enabled: true,
    period: 10,
    color: STYLE_PALETTE.lines[1].color,
    width: 1,
    style: "solid",
  },
  MA20: {
    enabled: true,
    period: 20,
    color: STYLE_PALETTE.lines[2].color,
    width: 1,
    style: "solid",
  },
  MA30: {
    enabled: false,
    period: 30,
    color: STYLE_PALETTE.lines[3].color,
    width: 1,
    style: "dashed",
  },
  MA60: {
    enabled: false,
    period: 60,
    color: STYLE_PALETTE.lines[4].color,
    width: 1,
    style: "dashed",
  },
  MA120: {
    enabled: false,
    period: 120,
    color: STYLE_PALETTE.lines[5].color,
    width: 1,
    style: "dotted",
  },
  MA250: {
    enabled: false,
    period: 250,
    color: STYLE_PALETTE.lines[6].color,
    width: 1,
    style: "dotted",
  },
};