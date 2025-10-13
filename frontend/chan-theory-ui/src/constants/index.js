// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\constants\index.js
// ==============================
// 说明（唯一可信源 · 前端默认与常量集中管理）
// - 本文件集中管理“前端可见设置项”与“设置性质的不可见控制参数”的默认值，其他模块一律引用这里的默认。
// - 组织规则：先放基础主题与调色，再放应用偏好与图表/指标/量窗/缠论/线段/分型等默认，随后是窗口预设、导出与交互默认、尺寸常量与工具函数。
// - 原有注释保留并适度优化；所有小节标题不再使用序号，便于后续插入不需顾虑调序。
// ==============================

// ------------------------------
// 主题与调色（供图表/组件使用）
// - 统一配色与线型的默认来源，供各模块引用（如 MA/量窗等）。
// ------------------------------
export const STYLE_PALETTE = {
  // 折线系列的配色与样式（循环使用）
  lines: [
    { color: "#ee6666", width: 1, style: "solid" }, // 线色1
    { color: "#fac858", width: 1, style: "solid" }, // 线色2
    { color: "#5470c6", width: 1, style: "solid" }, // 线色3
    { color: "#91cc75", width: 1, style: "solid" }, // 线色4
    { color: "#fc8452", width: 1, style: "solid" }, // 线色5
    { color: "#73c0de", width: 1, style: "solid" }, // 线色6
    { color: "#9a60b4", width: 1, style: "solid" }, // 线色7
    { color: "#ea7ccc", width: 1, style: "solid" }, // 线色8
  ],
  bars: {
    // 柱图配色（量窗/MACD）
    volume: { up: "#ef5350", down: "#26a69a" }, // 量窗柱色（红涨绿跌）
    macd: { positive: "#d94e4e", negative: "#47a69b" }, // MACD 柱正/负配色
  },
};

// ------------------------------
// 应用偏好（用户可操作的全局偏好）
// - 用户层面的图表类型、默认频率、复权方式、默认窗宽与指标开关。
// ------------------------------
export const DEFAULT_APP_PREFERENCES = {
  chartType: "kline", // 默认主图类型：k线模式
  freq: "1d", // 默认频率（日线）
  adjust: "qfq", // 默认复权类型：前复权
  windowPreset: "ALL", // 默认窗宽预设：ALL（全量）
  useMACD: true, // 指标默认：启用 MACD
  useKDJ: false, // 指标默认：禁用 KDJ
  useRSI: false, // 指标默认：禁用 RSI
  useBOLL: false, // 指标默认：禁用 BOLL
};

// ------------------------------
// 窗口预设（主窗控制条）
// - 窗口范围预设键集合；ALL = 当前已加载序列总根数。
// ------------------------------
export const WINDOW_PRESETS = [
  "5D",
  "10D", // 近 5/10 天
  "1M",
  "3M",
  "6M", // 近 1/3/6 月（近似）
  "1Y",
  "3Y",
  "5Y", // 近 1/3/5 年（近似）
  "ALL", // 全部（当前序列 n）
];

// ------------------------------
// 图表默认（主 K 线样式）
// - 原始K线（蜡烛）与合并K线（HL柱）的配色与淡显；层级控制通过 mergedK.displayOrder。
// ------------------------------
export const DEFAULT_KLINE_STYLE = {
  // 柱宽百分比（保留设置项，但设置窗当前不显示该项）
  barPercent: 100,

  // 原始K线（蜡烛）颜色与淡显（仅作用填充体）
  upColor: "#f56c6c", // 阳线主色（边线/影线/填充基色）
  downColor: "#26a69a", // 阴线主色（边线/影线/填充基色）
  originalFadeUpPercent: 100, // 阳线填充淡显（0~100；100=不淡显，纯色填充；仅作用填充，不影响边线/影线）
  originalFadeDownPercent: 0, // 阴线填充淡显（0~100；默认空心效果=0）
  originalEnabled: true, // 原始K线显示开关（默认选中）

  // 合并K线（HL柱）样式与层级
  mergedEnabled: true, // 合并K线显示开关（默认选中）
  mergedK: {
    outlineWidth: 1.2, // 轮廓线宽（作用于轮廓线）
    upColor: "#FF0000", // 上涨颜色（同时作用于轮廓线与填充体）
    downColor: "#00ff00", // 下跌颜色（同时作用于轮廓线与填充体）
    fillFadePercent: 0, // 填充淡显（0~100；仅作用填充，轮廓线始终100%）
    displayOrder: "first", // 显示层级：'first'（先）|'after'（后）；默认先
  },

  // 保留旧字段兼容（不再使用）
  subType: "candlestick",
};

// ------------------------------
// 指标默认（MA）
// - 主图多条 MA 的默认配置（周期/颜色/线型/线宽）；颜色引用 STYLE_PALETTE.lines。
// ------------------------------
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

// ------------------------------
// 量窗默认设置（VOL/AMOUNT）
// - 成交量/额的图形样式（柱体与 MAVOL 三条线）；颜色引用 STYLE_PALETTE。
// ------------------------------
export const DEFAULT_VOL_SETTINGS = {
  mode: "vol", // 模式（vol/amount）
  unit: "auto", // 单位策略（保留占位）
  rvolN: 20, // RVOL 基期（占位）

  // 柱体样式
  volBar: {
    barPercent: 100,
    upColor: STYLE_PALETTE.bars.volume.up, // 阳柱色
    downColor: STYLE_PALETTE.bars.volume.down, // 阴柱色
  },

  // MAVOL 三条线默认
  mavolStyles: {
    MAVOL5: {
      enabled: true,
      period: 5,
      width: 1,
      style: "solid",
      color: STYLE_PALETTE.lines[0].color,
      namePrefix: "MAVOL",
    },
    MAVOL10: {
      enabled: true,
      period: 10,
      width: 1,
      style: "solid",
      color: STYLE_PALETTE.lines[1].color,
      namePrefix: "MAVOL",
    },
    MAVOL20: {
      enabled: true,
      period: 20,
      width: 1,
      style: "solid",
      color: STYLE_PALETTE.lines[2].color,
      namePrefix: "MAVOL",
    },
  },

  // 放/缩量标记
  markerPump: {
    enabled: true,
    shape: "triangle",
    color: "#FFFF00",
    threshold: 1.5,
  },
  markerDump: {
    enabled: true,
    shape: "diamond",
    color: "#00ff00",
    threshold: 0.7,
  },
};

// ------------------------------
// 缠论覆盖层默认（涨跌标记等）
// - 涨跌标记的形状/颜色/透明度与尺寸；视觉预设键用于选择符号与填充组合。
// ------------------------------
export const CHAN_DEFAULTS = {
  showUpDownMarkers: true, // 显示涨跌标记
  anchorPolicy: "extreme", // 承载点策略（right/extreme）
  visualPreset: "tri-default", // 视觉预设键

  // 几何尺寸与透明度
  markerMinPx: 1, // 标记最小宽度
  markerMaxPx: 16, // 标记最大宽度
  markerHeightPx: 10, // 主窗涨跌标记统一高度（唯一数据源）
  markerYOffsetPx: 2, // 标记尺寸与极值偏移
  opacity: 0.9, // 标记透明度

  // 符号与颜色
  upShape: "triangle",
  upColor: "#f56c6c",
  downShape: "triangle",
  downColor: "#00ff00",

  maxVisibleMarkers: 10000, // 单视窗可见标记上限（超过抽稀）
};

// 缠论预设（符号/旋转/填充）
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

// ------------------------------
// 分型默认（基于 HL 柱）
// - 分型标记的开关与样式（强/标/弱三档）及确认分型样式；高度与间距集中归口。
// ------------------------------
export const FRACTAL_DEFAULTS = {
  enabled: true, // 显示分型标记
  showConfirmLink: false, // 显示确认分型连线（默认关闭）
  showStrength: { strong: true, standard: true, weak: true }, // 三档分型显示开关

  // 显著度判定参数
  minTickCount: 0,
  minPct: 0,
  minCond: "or",

  // 几何尺寸
  markerMinPx: 1,
  markerMaxPx: 16,
  markerHeightPx: 10, // 分型标记高度（px，集中归口）
  markerYOffsetPx: 2, // 标记尺寸与极值偏移

  // 顶/底默认形状
  topShape: "triangle",
  bottomShape: "triangle",

  // 三档分型外观默认
  styleByStrength: {
    strong: {
      bottomShape: "triangle",
      bottomColor: "#FF0000",
      topShape: "triangle",
      topColor: "#FF0000",
      fill: "solid",
      enabled: true,
    },
    standard: {
      bottomShape: "triangle",
      bottomColor: "#FFFF00",
      topShape: "triangle",
      topColor: "#FFFF00",
      fill: "solid",
      enabled: true,
    },
    weak: {
      bottomShape: "diamond",
      bottomColor: "#90EE90",
      topShape: "diamond",
      topColor: "#90EE90",
      fill: "hollow",
      enabled: true,
    },
  },

  // 确认分型样式
  confirmStyle: {
    bottomShape: "circle",
    bottomColor: "#00ff00",
    topShape: "circle",
    topColor: "#00ff00",
    fill: "solid",
    enabled: true,
  },
};

// 设置窗下拉：符号备选
export const FRACTAL_SHAPES = [
  { v: "triangle", label: "▲" }, // 三角
  { v: "diamond", label: "◆" }, // 菱形
  { v: "rect", label: "■" }, // 方块
  { v: "circle", label: "●" }, // 圆形
  { v: "pin", label: "📍" }, // 图钉
  { v: "arrow", label: "⬇" }, // 箭头
];

// 设置窗下拉：填充方式
export const FRACTAL_FILLS = [
  { v: "solid", label: "实心" },
  { v: "hollow", label: "空心" },
];

// ------------------------------
// 画笔默认方案
// - 简笔的开关/线宽/颜色与确认/预备线型，供主图设置窗引用；渲染层通过该预置提供默认值。
// ------------------------------
export const PENS_DEFAULTS = {
  enabled: true, // 是否显示画笔
  lineWidth: 2, // 线宽（px）
  color: "#ffffff", // 颜色（白色）
  confirmedStyle: "solid", // 确认笔线型：solid|dashed|dotted
  provisionalStyle: "dashed", // 预备笔线型：solid|dashed|dotted
};

// ------------------------------
// 线段默认（元线段样式配置）
// - 元线段为直线折线（端点相连），默认明黄色、线宽 3、实线。
// ------------------------------
export const SEGMENT_DEFAULTS = {
  color: "#FFD700", // 明黄色
  lineWidth: 3, // 线宽 3
  lineStyle: "solid", // 实线
};

// ------------------------------
// 连续性屏障（全局参数 · 统一管理）
// - 用于在价格突变（gap）处分岛处理，所有连续性元素不跨屏障。
// - 更正：动态阈值 basePct=11%，相邻两合并K的原始K索引差值为 n，则阈值为 (1+basePct)^n - 1。
// ------------------------------
export const CONTINUITY_BARRIER = {
  enabled: true,
  basePct: 0.5, // 单日涨跌幅限值基准百分比（50%）
  lineColor: "#ffdd00",
  lineWidth: 1.2,
  lineStyle: "solid", // solid | dashed | dotted
};

// ------------------------------
// 导出与交互控制（不可见但具“设置”性质的参数）
// - HTML/图片快照时的背景与像素比，是否内嵌数据的默认选择。
// ------------------------------
export const DEFAULT_EXPORT_SETTINGS = {
  background: "#111", // 导出图像背景色（与页面主背景一致）
  pixelRatio: 2, // PNG/JPG 像素比
  includeDataDefault: false, // HTML 快照默认不内嵌数据
};

// ------------------------------
// 量/额标记尺寸默认（量窗标记）
// - 标记宽度范围、基准高度与相对偏移，统一用作量窗标记几何尺寸来源。
// ------------------------------
export const DEFAULT_VOL_MARKER_SIZE = {
  minPx: 1, // 标记宽度最小像素
  maxPx: 16, // 标记宽度最大像素
  markerHeightPx: 10, // 标记基准高度像素
  markerYOffsetPx: 2, // 标记尺寸与极值偏移
};

// ------------------------------
// 预设 → barsCount 映射工具（以“原始 K 根数”为单位；ALL = totalBars）
// - minuteBarsPerDay：分钟族每日根数估算
// - presetToBars：预设键映射为 barsCount（向上取整、下限 1）
// - pickPresetByBarsCountDown：缩放后向下就近选取预设，高亮 ALL 逻辑护航
// ------------------------------
function minuteBarsPerDay(freq) {
  // 分钟族：估算“每日根数”
  const map = {
    "1m": 240,
    "5m": 240 / 5,
    "15m": 240 / 15,
    "30m": 240 / 30,
    "60m": 240 / 60,
  }; // 1m 基于 240 估算
  return map[freq] || 240; // 未知频率按 1m 估算
}

export function presetToBars(freq, preset, totalBars) {
  // 预设→barsCount（整数；非整数一律向上取整；下限 1）
  const n = Math.max(0, Math.floor(Number(totalBars || 0))); // ALL = 序列总根数 n
  if (preset === "ALL") return n; // ALL 直接返回 n

  const isMinute = /m$/.test(String(freq || "")); // 是否分钟族
  const isDaily = String(freq) === "1d"; // 是否日线
  const isWeekly = String(freq) === "1w"; // 是否周线
  const isMonthly = String(freq) === "1M"; // 是否月线

  function daysOf(p) {
    // 预设 → 天数近似
    if (p === "5D") return 5;
    if (p === "10D") return 10;
    if (p === "1M") return 22;
    if (p === "3M") return 66;
    if (p === "6M") return 132;
    if (p === "1Y") return 244;
    if (p === "3Y") return 732;
    if (p === "5Y") return 1220;
    return 0;
  }
  function weeksOf(p) {
    // 预设 → 周数近似
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
  function monthsOf(p) {
    // 预设 → 月数近似
    if (p === "1M") return 1;
    if (p === "3M") return 3;
    if (p === "6M") return 6;
    if (p === "1Y") return 12;
    if (p === "3Y") return 36;
    if (p === "5Y") return 60;
    if (p === "5D" || p === "10D") return 1; // 5/10天最少也回退为 1 月显示
    return 0;
  }

  let bars = 0;
  if (isMinute) {
    const perDay = minuteBarsPerDay(String(freq)); // 每日根数估算
    bars = Math.ceil(perDay * daysOf(preset)); // 天数换算为bars（向上取整）
  } else if (isDaily) {
    bars = Math.ceil(daysOf(preset)); // 日线（整数）
  } else if (isWeekly) {
    bars = Math.ceil(weeksOf(preset)); // 周线
  } else if (isMonthly) {
    bars = Math.ceil(monthsOf(preset)); // 月线
  } else {
    bars = Math.ceil(daysOf(preset)); // 兜底
  }

  bars = Math.max(1, Math.floor(bars || 0)); // 下限：至少 1 根
  if (n > 0) bars = Math.min(bars, n); // 上限不超过 n
  return bars;
}

export function pickPresetByBarsCountDown(freq, barsCount, totalBars) {
  // 缩放后向下就近；全覆盖时高亮 ALL
  const n = Math.max(0, Math.floor(Number(totalBars || 0)));
  const target = Math.max(1, Math.ceil(Number(barsCount || 0)));
  if (n > 0 && target >= n) {
    return "ALL";
  }

  const candidates = WINDOW_PRESETS.filter((p) => p !== "ALL")
    .map((p) => ({ p, v: presetToBars(freq, p, totalBars) }))
    .filter((x) => x.v > 0)
    .sort((a, b) => a.v - b.v);

  if (!candidates.length) return "ALL";

  let chosen = candidates[0];
  for (const c of candidates) {
    // 遍历找 <= target 的最大项
    if (c.v <= target) chosen = c;
    else break; // 超出则停止
  }
  return chosen.p;
}
