// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\constants\index.js
// ==============================
// 说明：集中管理“前端可见设置项”与“设置性质的不可见控制参数”的默认值。
// - 本文件是“唯一可信源”，所有默认值由此导出，其他文件一律引用这里的默认。
// - 组织顺序按“功能与逻辑”分组：应用偏好 → 主题/调色 → 导出/交互 → 图表默认 → 指标默认（MA/量窗）→ 缠论默认与预设 → 窗口预设。
// - 本轮扩展：
//   * 新增 DEFAULT_APP_PREFERENCES，含 freq/windowPreset 等（窗长与频率解耦，窗口预设默认 'ALL'，频率默认 '1d'）。
//   * 新增 DEFAULT_EXPORT_SETTINGS（导出背景/像素比/HTML是否嵌数据）。
//   * 新增 DEFAULT_VOL_MARKER_SIZE（量/额放缩量标记尺寸与偏移控制，之前分散在 options.js 内部常量）。
//   * 保留并集中 DEFAULT_KLINE_STYLE / DEFAULT_MA_CONFIGS / DEFAULT_VOL_SETTINGS / CHAN_DEFAULTS / CHAN_MARKER_PRESETS。
//   * 统一窗口按钮集合 WINDOW_PRESETS。
// ==============================

// ------------------------------
// 一、应用偏好（用户可操作的全局偏好）
// ------------------------------
export const DEFAULT_APP_PREFERENCES = {
  // 主图类型（kline|line），用户可切换，启动时从本地读取，失败回退此值
  chartType: "kline",
  // 频率（与窗长解耦），启动时从本地读取，失败回退 '1d'
  freq: "1d",
  // 复权选项（none|qfq|hfq），启动时从本地读取，失败回退 'none'
  adjust: "qfq",
  // 窗长预设（与频率解耦），启动时从本地读取，失败回退 'ALL'
  windowPreset: "ALL",
  // 指标开关（默认仅启用 MACD）
  useMACD: true,
  useKDJ: false,
  useRSI: false,
  useBOLL: false,
};

// ------------------------------
// 二、主题与调色（供图表/组件使用）
// ------------------------------
export const STYLE_PALETTE = {
  // 折线配色与样式（颜色尽量与 ECharts 默认风格相近）
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
  // 柱图配色（量窗与 MACD 柱使用）
  bars: {
    volume: { up: "#ef5350", down: "#26a69a" }, // 量柱：涨红/跌绿
    macd: { positive: "#d94e4e", negative: "#47a69b" }, // MACD 柱：正/负
  },
};

// ------------------------------
// 三、导出与交互控制（不可见但具“设置”性质的参数）
// ------------------------------
export const DEFAULT_EXPORT_SETTINGS = {
  // 图片导出背景色（与页面主背景一致）
  background: "#111",
  // PNG/JPG 像素比（内插缩放）
  pixelRatio: 2,
  // HTML 快照是否默认内嵌数据（合规默认不内嵌）
  includeDataDefault: false,
};

// 量/额标记（放量/缩量）的可视尺寸控制（图内不可见设置项，集中管理以便统一调整）
export const DEFAULT_VOL_MARKER_SIZE = {
  // 宽度像素下限/上限（根据可见柱数与容器宽度估算后再夹取）
  minPx: 1,
  maxPx: 16,
  // 基准高度（像素）
  baseHeightPx: 10,
  // 垂直偏移倍数（用于将标记与柱底对齐，留出视觉间距）
  offsetK: 1.2,
};

// ------------------------------
// 四、图表默认（主 K 线样式）
// ------------------------------
export const DEFAULT_KLINE_STYLE = {
  // 柱宽百分比（仅当 subType='candlestick' 或 'bar' 时生效）
  barPercent: 100,
  // 主图阳/阴颜色（与主题涨跌色对应）
  upColor: "#f56c6c",
  downColor: "#26a69a",
  // K 线子类型：'candlestick'（蜡烛图）或 'bar'（H-L 柱）
  subType: "candlestick",
};

// ------------------------------
// 五、指标默认（MA / 量窗）
// ------------------------------
// 5.1 MA 默认（固定 key → 属性）
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
    enabled: true,
    period: 30,
    color: STYLE_PALETTE.lines[3].color,
    width: 1,
    style: "dashed",
  },
  MA60: {
    enabled: true,
    period: 60,
    color: STYLE_PALETTE.lines[4].color,
    width: 1,
    style: "dashed",
  },
  MA120: {
    enabled: true,
    period: 120,
    color: STYLE_PALETTE.lines[5].color,
    width: 1,
    style: "dotted",
  },
  MA250: {
    enabled: true,
    period: 250,
    color: STYLE_PALETTE.lines[6].color,
    width: 1,
    style: "dotted",
  },
};

// 5.2 量窗默认（模式、柱样式、MAVOL 三线、放/缩量标记）
export const DEFAULT_VOL_SETTINGS = {
  // 模式（'vol'/'amount'），默认显示成交量
  mode: "vol",
  // 单位策略（保留占位，目前仅 'auto'）
  unit: "auto",
  // RVOL 计算的基期（仅日线可见时用于提示/统计，当前逻辑中仅占位）
  rvolN: 20,
  // 柱体样式
  volBar: {
    barPercent: 100,
    upColor: STYLE_PALETTE.bars.volume.up,
    downColor: STYLE_PALETTE.bars.volume.down,
  },
  // MAVOL 三条线样式（开启/周期/线宽/线型/颜色）
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
  // 放量/缩量标记（启用/符号/颜色/阈值）
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
// 六、缠论默认与视觉预设
// ------------------------------
export const CHAN_DEFAULTS = {
  // 启用“去包含后涨跌标记”叠加层
  showUpDownMarkers: true,
  // 承载点策略（'right' | 'extreme'）
  anchorPolicy: "extreme",
  // 视觉预设键（参见 CHAN_MARKER_PRESETS）
  visualPreset: "tri-default",
  // 标记尺寸边界（像素）
  markerMinPx: 1,
  markerMaxPx: 14,
  // 标记透明度
  opacity: 0.9,
  // 上涨/下跌标记的形状与颜色（可与预设不同步，优先级更高）
  upShape: "triangle",
  upColor: "#f56c6c",
  downShape: "triangle",
  downColor: "#00ff00",
  // 可见窗口最大标记数（超过则抽稀）
  maxVisibleMarkers: 1000,
};

// 缠论标记视觉预设（shape/rotate/fill）
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
// 七、窗口预设（主窗控制条按钮集合）
// ------------------------------
export const WINDOW_PRESETS = [
  "5D",
  "10D", // 近 5、10 天
  "1M",
  "3M",
  "6M", // 近 1、3、6 月（近似）
  "YTD", // 年初至今
  "1Y",
  "3Y",
  "5Y", // 近 1、3、5 年（近似）
  "ALL", // 全部（默认预设）
];

// 备注：历史上曾存在“按频率选择默认窗长”的映射（DEFAULT_WINDOW_BY_FREQ），现已与频率解绑，
//       由本文件 DEFAULT_APP_PREFERENCES.windowPreset 与 WINDOW_PRESETS 统一管理窗口预设逻辑。
//       若外部仍有残留引用该映射的代码，应当移除（本轮已删去相关依赖）。
