// src/constants/common.js

// ==============================
// 基础调色板
// ==============================
export const STYLE_PALETTE = {
  lines: [
    { color: "#ee6666", width: 1, style: "solid" },
    { color: "#fac858", width: 1, style: "solid" },
    { color: "#5470c6", width: 1, style: "solid" },
    { color: "#91cc75", width: 1, style: "solid" },
    { color: "#fc8452", width: 1, style: "solid" },
    { color: "#73c0de", width: 1, style: "solid" },
    { color: "#9a60b4", width: 1, style: "solid" },
    { color: "#ea7ccc", width: 1, style: "solid" },
  ],
  bars: {
    volume: { up: "#ef5350", down: "#26a69a" },
    macd: { positive: "#d94e4e", negative: "#47a69b" },
  },
};

// ==============================
// 全局应用偏好
// ==============================
export const DEFAULT_APP_PREFERENCES = {
  chartType: "kline",
  freq: "1d",
  adjust: "qfq",
  windowPreset: "ALL",
  useMACD: true,
  useKDJ: false,
  useRSI: false,
  useBOLL: false,
};

// ==============================
// UI 输入边界（彻底通用化）
// ==============================
export const UI_LIMITS = {
  // 通用折线线宽
  lineWidth: {
    min: 0.5,
    max: 6,
    step: 0.5,
  },
  // 通用轮廓线宽（例如K线体边框）
  outlineWidth: {
    min: 1,
    max: 6,
    step: 1,
  },
  // 通用百分比 (0-100)
  percentage: {
    min: 0,
    max: 100,
    step: 1,
  },
  // 特例：柱体宽度百分比 (10-100)
  barWidthPercent: {
    min: 10,
    max: 100,
    step: 1,
  },
  // 通用正整数（用于周期、计数等，>= 1）
  positiveInteger: {
    min: 1,
    step: 1,
  },
  // 通用非负整数（用于计数等，>= 0）
  nonNegativeInteger: {
    min: 0,
    step: 1,
  },
  // 通用非负浮点数（用于阈值等，>= 0）
  nonNegativeFloat: {
    min: 0,
    step: 0.1,
  },
};

// ==============================
// UI 选项源
// ─
export const LINE_STYLES = [
  { v: "solid", label: "────" },
  { v: "dashed", label: "╌╌╌" },
  { v: "dotted", label: "┈┈┈" },
];

export const ADJUST_OPTIONS = [
  { v: "none", label: "不复权" },
  { v: "qfq", label: "前复权" },
  { v: "hfq", label: "后复权" },
];

export const ANCHOR_POLICY_OPTIONS = [
  { v: "right", label: "右端" },
  { v: "extreme", label: "极值" },
];

export const DISPLAY_ORDER_OPTIONS = [
  { v: "first", label: "前端" },
  { v: "after", label: "后端" },
];

export const MIN_COND_OPTIONS = [
  { v: "or", label: "或" },
  { v: "and", label: "与" },
];

export const MARKER_SHAPE_OPTIONS = [
  { v: "triangle", label: "▲" },
  { v: "diamond", label: "◆" },
  { v: "rect", label: "■" },
  { v: "circle", label: "⬤" },
  { v: "pin", label: "📍" },
  { v: "arrow", label: "⬇" },
];

export const FILL_OPTIONS = [
  { v: "solid", label: "实心" },
  { v: "hollow", label: "空心" },
];

// ==============================
// 窗口与导出预设
// ==============================
export const WINDOW_PRESETS = [
  "5D", "10D", "1M", "3M", "6M", "1Y", "3Y", "5Y", "ALL",
];

export const DEFAULT_EXPORT_SETTINGS = {
  background: "#111",
  pixelRatio: 2,
  includeDataDefault: false,
};

// ==============================
// 预设转换工具函数
// ==============================
function minuteBarsPerDay(freq) {
  const map = { "1m": 240, "5m": 48, "15m": 16, "30m": 8, "60m": 4 };
  return map[freq] || 240;
}

export function presetToBars(freq, preset, totalBars) {
  const n = Math.max(0, Math.floor(Number(totalBars || 0)));
  if (preset === "ALL") return n;

  const isMinute = /m$/.test(String(freq || ""));
  const isDaily = String(freq) === "1d";
  const isWeekly = String(freq) === "1w";
  const isMonthly = String(freq) === "1M";

  function daysOf(p) {
    if (p === "5D") return 5; if (p === "10D") return 10;
    if (p === "1M") return 22; if (p === "3M") return 66;
    if (p === "6M") return 132; if (p === "1Y") return 244;
    if (p === "3Y") return 732; if (p === "5Y") return 1220;
    return 0;
  }
  function weeksOf(p) {
    if (p === "5D") return 1; if (p === "10D") return 2;
    if (p === "1M") return 4; if (p === "3M") return 12;
    if (p === "6M") return 26; if (p === "1Y") return 52;
    if (p === "3Y") return 156; if (p === "5Y") return 260;
    return 0;
  }
  function monthsOf(p) {
    if (p === "1M") return 1; if (p === "3M") return 3;
    if (p === "6M") return 6; if (p === "1Y") return 12;
    if (p === "3Y") return 36; if (p === "5Y") return 60;
    if (p === "5D" || p === "10D") return 1;
    return 0;
  }

  let bars = 0;
  if (isMinute) bars = Math.ceil(minuteBarsPerDay(String(freq)) * daysOf(preset));
  else if (isDaily) bars = Math.ceil(daysOf(preset));
  else if (isWeekly) bars = Math.ceil(weeksOf(preset));
  else if (isMonthly) bars = Math.ceil(monthsOf(preset));
  else bars = Math.ceil(daysOf(preset));

  bars = Math.max(1, Math.floor(bars || 0));
  if (n > 0) bars = Math.min(bars, n);
  return bars;
}

export function pickPresetByBarsCountDown(freq, barsCount, totalBars) {
  const n = Math.max(0, Math.floor(Number(totalBars || 0)));
  const target = Math.max(1, Math.ceil(Number(barsCount || 0)));
  if (n > 0 && target >= n) return "ALL";

  const candidates = WINDOW_PRESETS.filter((p) => p !== "ALL")
    .map((p) => ({ p, v: presetToBars(freq, p, totalBars) }))
    .filter((x) => x.v > 0)
    .sort((a, b) => a.v - b.v);

  if (!candidates.length) return "ALL";

  let chosen = candidates[0];
  for (const c of candidates) {
    if (c.v <= target) chosen = c;
    else break;
  }
  return chosen.p;
}
