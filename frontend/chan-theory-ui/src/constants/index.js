// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\constants\index.js  // 文件路径
// ==============================                                          // 说明：前端全局常量与默认方案（全量+新增缠论默认）
// 说明：本文件在原有基础上，追加 CHAN_DEFAULTS 与 CHAN_MARKER_PRESETS 两个导出常量。 // 本次仅追加，原导出保持不变
// ==============================                                          // 结束头注释

// 统一样式调色板（线/柱）                                               // 原有导出：STYLE_PALETTE
export const STYLE_PALETTE = {
  // 样式调色板对象
  lines: [
    // 折线颜色/样式预设
    { color: "#ee6666", width: 1, style: "solid" }, // 线1：红
    { color: "#fac858", width: 1, style: "solid" }, // 线2：黄
    { color: "#5470c6", width: 1, style: "solid" }, // 线3：蓝
    { color: "#91cc75", width: 1, style: "solid" }, // 线4：绿
    { color: "#fc8452", width: 1, style: "solid" }, // 线5：橙
    { color: "#73c0de", width: 1, style: "solid" }, // 线6：青
    { color: "#9a60b4", width: 1, style: "solid" }, // 线7：紫
    { color: "#ea7ccc", width: 1, style: "solid" }, // 线8：粉
  ], // 结束 lines
  bars: {
    // 柱图配色
    volume: { up: "#ef5350", down: "#26a69a" }, // 量柱：涨红/跌绿
    macd: { positive: "#d94e4e", negative: "#47a69b" }, // MACD 柱：正/负色
  }, // 结束 bars
}; // 结束 STYLE_PALETTE

// 主窗 MA 默认配置（固定 key → 属性）                                 // 原有导出：DEFAULT_MA_CONFIGS
export const DEFAULT_MA_CONFIGS = {
  // MA 默认配置
  MA5: {
    // MA5
    enabled: true, // 启用
    period: 5, // 周期
    color: STYLE_PALETTE.lines[0].color, // 颜色
    width: 1, // 线宽
    style: "solid", // 线型
  }, // 结束 MA5
  MA10: {
    // MA10
    enabled: true, // 启用
    period: 10, // 周期
    color: STYLE_PALETTE.lines[1].color, // 颜色
    width: 1, // 线宽
    style: "solid", // 线型
  }, // 结束 MA10
  MA20: {
    // MA20
    enabled: true, // 启用
    period: 20, // 周期
    color: STYLE_PALETTE.lines[2].color, // 颜色
    width: 1, // 线宽
    style: "solid", // 线型
  }, // 结束 MA20
  MA30: {
    // MA30
    enabled: true, // 启用
    period: 30, // 周期
    color: STYLE_PALETTE.lines[3].color, // 颜色
    width: 1, // 线宽
    style: "dashed", // 线型
  }, // 结束 MA30
  MA60: {
    // MA60
    enabled: true, // 启用
    period: 60, // 周期
    color: STYLE_PALETTE.lines[4].color, // 颜色
    width: 1, // 线宽
    style: "dashed", // 线型
  }, // 结束 MA60
  MA120: {
    // MA120
    enabled: true, // 启用
    period: 120, // 周期
    color: STYLE_PALETTE.lines[5].color, // 颜色
    width: 1, // 线宽
    style: "dotted", // 线型
  }, // 结束 MA120
  MA250: {
    // MA250
    enabled: true, // 启用
    period: 250, // 周期
    color: STYLE_PALETTE.lines[6].color, // 颜色
    width: 1, // 线宽
    style: "dotted", // 线型
  }, // 结束 MA250
}; // 结束 DEFAULT_MA_CONFIGS

// 量窗默认配置（行为+样式）                                            // 原有导出：DEFAULT_VOL_SETTINGS
export const DEFAULT_VOL_SETTINGS = {
  // VOL 默认配置
  mode: "vol", // 模式：'vol' | 'amount'
  unit: "auto", // 单位策略（当前仅 auto）
  rvolN: 20, // RVOL 基数天数（仅日线）

  volBar: {
    // 柱体样式
    barPercent: 100, // 柱宽百分比
    upColor: STYLE_PALETTE.bars.volume.up, // 阳线色
    downColor: STYLE_PALETTE.bars.volume.down, // 阴线色
  }, // 结束 volBar

  mavolStyles: {
    // MAVOL 三条
    MAVOL5: {
      enabled: true,
      period: 5,
      width: 1,
      style: "solid",
      color: STYLE_PALETTE.lines[0].color,
      namePrefix: "MAVOL",
    }, // MAVOL5
    MAVOL10: {
      enabled: true,
      period: 10,
      width: 1,
      style: "solid",
      color: STYLE_PALETTE.lines[1].color,
      namePrefix: "MAVOL",
    }, // MAVOL10
    MAVOL20: {
      enabled: true,
      period: 20,
      width: 1,
      style: "solid",
      color: STYLE_PALETTE.lines[2].color,
      namePrefix: "MAVOL",
    }, // MAVOL20
  }, // 结束 mavolStyles

  markerPump: { enabled: true, shape: "triangle", color: "#FFFF00", threshold: 1.5 }, // 放量标记默认
  markerDump: { enabled: true, shape: "diamond", color: "#00ff00", threshold: 0.7 }, // 缩量标记默认
}; // 结束 DEFAULT_VOL_SETTINGS

// 每种 K 线周期对应的“默认时间窗口预设”                               // 原有导出：DEFAULT_WINDOW_BY_FREQ
export const DEFAULT_WINDOW_BY_FREQ = {
  // 周期默认窗口
  "1m": "ALL", // 1 分钟 → 近 5 天
  "5m": "ALL", // 5 分钟 → 近 1 月
  "15m": "ALL", // 15 分钟 → 近 1 月
  "30m": "ALL", // 30 分钟 → 近 3 月
  "60m": "ALL", // 60 分钟 → 近 6 月
  "1d": "ALL", // 日线 → 近 1 年
  "1w": "ALL", // 周线 → 近 3 年
  "1M": "ALL", // 月线 → 近 5 年
}; // 结束 DEFAULT_WINDOW_BY_FREQ

// ==============================                                          // 追加区域：缠论（Chan）相关默认与视觉预设
// 追加：缠论标记默认与视觉预设（Chan）                                   // 注：仅新增导出，不影响已有导出
export const CHAN_DEFAULTS = {
  // 缠论默认设置
  showUpDownMarkers: true, // 是否显示“去包含后”的涨跌标记（默认开启）
  anchorPolicy: "right", // 承载点策略：'right' | 'extreme'（右端或极值）
  visualPreset: "tri-default", // 视觉预设键（见 CHAN_MARKER_PRESETS）
  markerMinPx: 1, // 标记最小像素
  markerMaxPx: 14, // 标记最大像素
  opacity: 0.9, // 标记透明度
  // borderColor: "#99aabb", // 标记边框色（淡灰蓝）
  maxVisibleMarkers: 1000, // 可见窗口内最大标记数（超过触发抽稀）
  // 新增：单独配置上涨/下跌标记的形状与颜色（可覆盖预设）
  upShape: "triangle",
  upColor: "#f56c6c",
  downShape: "triangle",
  downColor: "#00ff00",
}; // 结束 CHAN_DEFAULTS

export const CHAN_MARKER_PRESETS = {
  // 缠论标记视觉预设
  "tri-default": {
    // 三角预设（与 K 线涨跌色一致）
    up: { shape: "triangle", rotate: 0, fill: "#f56c6c" }, // 上涨：正三角（红）
    down: { shape: "triangle", rotate: 180, fill: "#00ff00" }, // 下跌：倒三角（绿）
  }, // 结束 tri-default
  diamond: {
    // 菱形预设
    up: { shape: "diamond", rotate: 0, fill: "#f56c6c" }, // 上涨：菱形红
    down: { shape: "diamond", rotate: 0, fill: "#00ff00" }, // 下跌：菱形绿
  }, // 结束 diamond
  dot: {
    // 圆点预设
    up: { shape: "circle", rotate: 0, fill: "#f56c6c" }, // 上涨：圆点红
    down: { shape: "circle", rotate: 0, fill: "#00ff00" }, // 下跌：圆点绿
  }, // 结束 dot
  square: {
    // 方块预设
    up: { shape: "rect", rotate: 0, fill: "#f56c6c" }, // 上涨：方块红
    down: { shape: "rect", rotate: 0, fill: "#00ff00" }, // 下跌：方块绿
  }, // 结束 square
}; // 结束 CHAN_MARKER_PRESETS
