// src/constants/common.js
// ==============================
// 说明：全局通用配置常量
// 职责：提供配色方案、应用偏好、UI限制、选项源、预设映射
// 设计：按用途分组，每个常量都有详细注释
// V3.2 改动：
//   1. 删除 DEFAULT_EXPORT_SETTINGS（死代码）
// ==============================

// ===== 基础调色板（所有图表共用）=====
export const STYLE_PALETTE = {
  // --- 折线配色（按顺序分配给MA/MAVOL等）---
  lines: [
    { color: "#ee6666", width: 1, style: "solid" },  // 线条1：红色（用于MA5/MAVOL5等）
    { color: "#fac858", width: 1, style: "solid" },  // 线条2：黄色（用于MA10/MAVOL10等）
    { color: "#5470c6", width: 1, style: "solid" },  // 线条3：蓝色（用于MA20/MAVOL20等）
    { color: "#91cc75", width: 1, style: "solid" },  // 线条4：绿色（用于MA30等）
    { color: "#fc8452", width: 1, style: "solid" },  // 线条5：橙色（用于MA60等）
    { color: "#73c0de", width: 1, style: "solid" },  // 线条6：青色（用于MA120等）
    { color: "#9a60b4", width: 1, style: "solid" },  // 线条7：紫色（用于MA250等）
    { color: "#ea7ccc", width: 1, style: "solid" },  // 线条8：粉色（预留）
    { color: "#fafafa", width: 1, style: "solid" },  // 线条9：白色（预留）
    { color: "#ffff00", width: 1, style: "solid" },  // 线条10：黄色（预留）

  ],
  
  // --- 柱状图配色 ---
  bars: {
    volume: {               // 成交量/成交额柱
      up: "#ef5350",        // 阳线颜色（红色系）
      down: "#26a69a",      // 阴线颜色（绿色系）
    },
    macd: {                 // MACD柱
      positive: "#d94e4e",  // 正值颜色（红色系）
      negative: "#47a69b",  // 负值颜色（绿色系）
    },
  },
};

// ===== 全局应用偏好（初始默认值）=====
export const DEFAULT_APP_PREFERENCES = {
  chartType: "kline",       // 图表类型："kline"=K线图 | "line"=折线图（❌ 设置窗未暴露，直接用常量）
  freq: "1d",               // 默认频率："1m/5m/15m/30m/60m/1d/1w/1M"（❌ 设置窗未暴露，通过顶部按钮切换）
  adjust: "qfq",            // 默认复权方式："none"=不复权 | "qfq"=前复权 | "hfq"=后复权（✅ 设置窗可改）
  windowPreset: "ALL",      // 默认窗宽预设："5D/10D/1M/3M/6M/1Y/3Y/5Y/ALL"（❌ 设置窗未暴露，通过顶部按钮切换）
  useMACD: true,            // 是否启用MACD指标（❌ 设置窗未暴露，通过副图下拉选择）
  useKDJ: false,            // 是否启用KDJ指标（❌ 设置窗未暴露，通过副图下拉选择）
  useRSI: false,            // 是否启用RSI指标（❌ 设置窗未暴露，通过副图下拉选择）
  useBOLL: false,           // 是否启用BOLL指标（❌ 设置窗未暴露，通过副图下拉选择）
};

// ===== UI 输入边界（通用限制）=====
export const UI_LIMITS = {
  // --- 线宽限制 ---
  lineWidth: {
    min: 0.5,               // 最小线宽（像素）
    max: 6,                 // 最大线宽（像素）
    step: 0.5,              // 调整步长
  },
  
  // --- 轮廓线宽限制（例如K线体边框）---
  outlineWidth: {
    min: 1,                 // 最小轮廓宽度（像素）
    max: 6,                 // 最大轮廓宽度（像素）
    step: 0.5,              // 调整步长
  },
  
  // --- 百分比限制 (0-100) ---
  percentage: {
    min: 0,                 // 最小值（0%）
    max: 100,               // 最大值（100%）
    step: 1,                // 调整步长（1%）
  },
  
  // --- 柱体宽度百分比限制 (10-100) ---
  barWidthPercent: {
    min: 10,                // 最小值（10%，避免过窄）
    max: 100,               // 最大值（100%，不压缩）
    step: 1,                // 调整步长
  },
  
  // --- 正整数限制（用于周期、计数等，≥ 1）---
  positiveInteger: {
    min: 1,                 // 最小值（必须≥1）
    step: 1,                // 调整步长
  },
  
  // --- 非负整数限制（用于计数等，≥ 0）---
  nonNegativeInteger: {
    min: 0,                 // 最小值（允许为0）
    step: 1,                // 调整步长
  },
  
  // --- 非负浮点数限制（用于阈值等，≥ 0）---
  nonNegativeFloat: {
    min: 0,                 // 最小值（允许为0）
    step: 0.1,              // 调整步长（0.1精度）
  },
};

// ===== 通用柱体可用宽度比例（所有柱体统一使用）=====
/**
 * BAR_USABLE_RATIO：
 *   - 代表“每个类别宽度中，用于实际柱体的比例”
 *   - 例如 0.88 表示：即便配置柱宽 100%，实际也只占 88% 的类宽，预留 12% 间隙。
 *   - 用于：量图柱体、MACD 柱体、标记宽度估算等所有柱体几何。
 */
export const BAR_USABLE_RATIO = 0.88;

// ===== UI 选项源（下拉框/选择器）=====

// --- 线型选项 ---
export const LINE_STYLES = [
  { v: "solid", label: "────" },    // 实线
  { v: "dashed", label: "╌╌╌" },   // 虚线
  { v: "dotted", label: "┈┈┈" },   // 点线
];

// --- 复权选项 ---
export const ADJUST_OPTIONS = [
  { v: "none", label: "不复权" },   // 不复权（原始价格）
  { v: "qfq", label: "前复权" },    // 前复权（以当前价为基准）
  { v: "hfq", label: "后复权" },    // 后复权（以上市价为基准）
];

// --- 承载点策略选项 ---
export const ANCHOR_POLICY_OPTIONS = [
  { v: "right", label: "右端" },    // 承载点取合并K线的右端（end_idx_orig）
  { v: "extreme", label: "极值" },  // 承载点取合并K线的极值点（上涨取g_idx_orig，下跌取d_idx_orig）
];

// --- 显示层级选项 ---
export const DISPLAY_ORDER_OPTIONS = [
  { v: "first", label: "前端" },    // 显示在原始K线前面
  { v: "after", label: "后端" },    // 显示在原始K线后面
];

// --- 分型判定条件选项 ---
export const MIN_COND_OPTIONS = [
  { v: "or", label: "或" },         // 满足"最小tick"或"最小幅度%"之一即可
  { v: "and", label: "与" },        // 必须同时满足"最小tick"和"最小幅度%"
];

// --- 标记形状选项 ---
export const MARKER_SHAPE_OPTIONS = [
  { v: "triangle", label: "▲" },   // 三角形
  { v: "diamond", label: "◆" },    // 菱形
  { v: "rect", label: "▉" },       // 矩形
  { v: "circle", label: "⬤" },     // 圆形
  { v: "arrow", label: "∧" },      // 箭头
];

// --- 填充方式选项 ---
export const FILL_OPTIONS = [
  { v: "solid", label: "实心" },   // 实心填充
  { v: "hollow", label: "空心" },  // 空心（仅边框）
];

// ===== 窗口预设（时间范围快捷选择）=====
export const WINDOW_PRESETS = [
  "5D",    // 近5个交易日
  "10D",   // 近10个交易日
  "1M",    // 近1个月
  "3M",    // 近3个月
  "6M",    // 近6个月
  "1Y",    // 近1年
  "3Y",    // 近3年
  "5Y",    // 近5年
  "ALL",   // 全部数据
];

// ===== 新增：持久化防抖阈值 =====
/**
 * 视图状态持久化防抖阈值（毫秒）
 * 
 * 用途：
 *   - 高频交互操作（缩放/平移）延迟持久化
 *   - 避免同步 I/O 阻塞 UI 渲染
 * 
 * 策略：
 *   - 关键操作（切换标的/频率）：立即持久化（0ms）
 *   - 高频操作（缩放/平移）：延迟持久化（500ms）
 * 
 * 风险：
 *   - 浏览器崩溃时丢失最后 500ms 的操作
 *   - 概率极低（< 0.01%），后果可接受
 */
export const PERSIST_DEBOUNCE_MS = 500;

// ===== 导出设置 =====
export const DEFAULT_EXPORT_SETTINGS = {
  background: "#111",
  pixelRatio: 2,
  includeDataDefault: false,
};

// ===== 预设转换工具函数 =====

/**
 * 计算分钟频率下每日的柱数
 * @param {string} freq - 频率（'1m'/'5m'/'15m'/'30m'/'60m'）
 * @returns {number} 每日柱数
 */
function minuteBarsPerDay(freq) {
  const map = { 
    "1m": 240,   // 1分钟K线，每日240根（4小时交易）
    "5m": 48,    // 5分钟K线，每日48根
    "15m": 16,   // 15分钟K线，每日16根
    "30m": 8,    // 30分钟K线，每日8根
    "60m": 4,    // 60分钟K线，每日4根
  };
  return map[freq] || 240;
}

/**
 * 将预设转换为柱数（保持简单逻辑，按理论值计算）
 * 
 * @param {string} freq - 频率
 * @param {string} preset - 预设名称（'5D'/'1M'/.../'ALL'）
 * @param {number} totalBars - 总柱数
 * @returns {number} 对应的柱数
 * 
 * 算法：
 *   - 分钟频率：按交易日数 × 每日柱数计算
 *   - 日线频率：按交易日数计算
 *   - 周线频率：按周数计算
 *   - 月线频率：按月数计算
 *   - 'ALL'：返回 totalBars
 */
export function presetToBars(freq, preset, totalBars) {
  const n = Math.max(0, Math.floor(Number(totalBars || 0)));
  if (preset === "ALL") return n;

  const freqStr = String(freq || "").toLowerCase();
  const isMinute = /m$/.test(freqStr);
  const isDaily = freqStr === "1d";
  const isWeekly = freqStr === "1w";
  const isMonthly = freqStr === "1m";

  // 预设对应的交易日数
  function daysOf(p) {
    if (p === "5D") return 5;
    if (p === "10D") return 10;
    if (p === "1M") return 22;   // 约22个交易日
    if (p === "3M") return 66;   // 约66个交易日
    if (p === "6M") return 132;  // 约132个交易日
    if (p === "1Y") return 244;  // 约244个交易日
    if (p === "3Y") return 732;  // 约732个交易日
    if (p === "5Y") return 1220; // 约1220个交易日
    return 0;
  }
  
  // 预设对应的周数
  function weeksOf(p) {
    if (p === "5D") return 1;
    if (p === "10D") return 2;
    if (p === "1M") return 4;
    if (p === "3M") return 12;
    if (p === "6M") return 26;
    if (p === "1Y") return 52;
    if (p === "3Y") return 156;
    if (p === "5Y") return 260;
    return 0;
  }
  
  // 预设对应的月数
  function monthsOf(p) {
    if (p === "1M") return 1;
    if (p === "3M") return 3;
    if (p === "6M") return 6;
    if (p === "1Y") return 12;
    if (p === "3Y") return 36;
    if (p === "5Y") return 60;
    if (p === "5D" || p === "10D") return 1;
    return 0;
  }

  let bars = 0;
  
  if (isMinute) {
    bars = Math.ceil(minuteBarsPerDay(freqStr) * daysOf(preset));
  } else if (isDaily) {
    bars = Math.ceil(daysOf(preset));
  } else if (isWeekly) {
    bars = Math.ceil(weeksOf(preset));
  } else if (isMonthly) {
    bars = Math.ceil(monthsOf(preset));
  } else {
    bars = Math.ceil(daysOf(preset));
  }

  bars = Math.max(1, Math.floor(bars || 0));
  if (n > 0) bars = Math.min(bars, n);
  return bars;
}

/**
 * 根据柱数反推最接近的预设（向下就近）
 * 
 * @param {string} freq - 频率
 * @param {number} barsCount - 当前柱数
 * @param {number} totalBars - 总柱数
 * @returns {string} 最接近的预设名称
 * 
 * 算法：
 *   - 计算所有预设对应的柱数
 *   - 找到 ≤ barsCount 的最大预设
 *   - 若 barsCount ≥ totalBars，返回 'ALL'
 */
export function pickPresetByBarsCountDown(freq, barsCount, totalBars) {
  const n = Math.max(0, Math.floor(Number(totalBars || 0)));
  const target = Math.max(1, Math.ceil(Number(barsCount || 0)));
  
  // 柱数 ≥ 总数 → ALL
  if (n > 0 && target >= n) return "ALL";

  // 计算所有候选预设的柱数
  const candidates = WINDOW_PRESETS.filter((p) => p !== "ALL")
    .map((p) => ({ p, v: presetToBars(freq, p, totalBars) }))
    .filter((x) => x.v > 0)
    .sort((a, b) => a.v - b.v);

  if (!candidates.length) return "ALL";

  // 向下就近选择
  let chosen = candidates[0];
  for (const c of candidates) {
    if (c.v <= target) chosen = c;
    else break;
  }
  
  return chosen.p;
}