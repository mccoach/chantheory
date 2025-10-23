// src/constants/charts/chan.js

// 缠论涨跌标记
export const CHAN_DEFAULTS = {
  showUpDownMarkers: true,
  anchorPolicy: "extreme",
  visualPreset: "tri-default",
  markerMinPx: 1,
  markerMaxPx: 16,
  markerHeightPx: 10,
  markerYOffsetPx: 2,
  opacity: 0.9,
  upShape: "triangle",
  upColor: "#f56c6c",
  downShape: "triangle",
  downColor: "#00ff00",
  maxVisibleMarkers: 10000,
};

// 缠论标记视觉预设
export const CHAN_MARKER_PRESETS = {
  "tri-default": {
    up: { shape: "triangle", rotate: 0, fill: "#f56c6c" },
    down: { shape: "triangle", rotate: 180, fill: "#00ff00" },
  },
  diamond: {
    up: { shape: "diamond", rotate: 0, fill: "#f56c6c" },
    down: { shape: "diamond", rotate: 0, fill: "#00ff00" },
  },
  dot: {
    up: { shape: "circle", rotate: 0, fill: "#f56c6c" },
    down: { shape: "circle", rotate: 0, fill: "#00ff00" },
  },
  square: {
    up: { shape: "rect", rotate: 0, fill: "#f56c6c" },
    down: { shape: "rect", rotate: 0, fill: "#00ff00" },
  },
};

// 分型
export const FRACTAL_DEFAULTS = {
  enabled: true,
  showConfirmLink: false,
  showStrength: { strong: true, standard: true, weak: true },
  minTickCount: 0,
  minPct: 0,
  minCond: "or",
  markerMinPx: 1,
  markerMaxPx: 16,
  markerHeightPx: 10,
  markerYOffsetPx: 2,
  topShape: "triangle",
  bottomShape: "triangle",
  styleByStrength: {
    strong:   { bottomShape: "triangle", bottomColor: "#FF0000", topShape: "triangle", topColor: "#FF0000", fill: "solid", enabled: true },
    standard: { bottomShape: "triangle", bottomColor: "#FFFF00", topShape: "triangle", topColor: "#FFFF00", fill: "solid", enabled: true },
    weak:     { bottomShape: "diamond", bottomColor: "#90EE90", topShape: "diamond", topColor: "#90EE90", fill: "hollow", enabled: true },
  },
  confirmStyle: {
    bottomShape: "circle", bottomColor: "#00ff00", topShape: "circle", topColor: "#00ff00", fill: "solid", enabled: true,
  },
};

// 笔
export const PENS_DEFAULTS = {
  enabled: true,
  lineWidth: 2,
  color: "#ffffff",
  confirmedStyle: "solid",
  provisionalStyle: "dashed",
};

// 线段
export const SEGMENT_DEFAULTS = {
  enabled: false,
  color: "#FFD700",
  lineWidth: 3,
  lineStyle: "solid",
};

// 笔中枢
export const CHAN_PEN_PIVOT_DEFAULTS = {
  enabled: true,
  upColor: "#FF0000",
  downColor: "#00FF00",
  lineWidth: 1.5,
  lineStyle: "solid",
  alphaPercent: 5,
  z: 7,
};

// 连续性屏障
export const CONTINUITY_BARRIER = {
  enabled: true,
  basePct: 0.5,
  lineColor: "#ffdd00",
  lineWidth: 1.2,
  lineStyle: "solid",
};
