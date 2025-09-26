// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\constants\index.js  // 文件路径（常量与工具的唯一可信源）
// ==============================                                           // 分隔注释
// 说明：集中管理“前端可见设置项”与“设置性质的不可见控制参数”的默认值。                   // 原则：集中定义，统一出口
// - 本文件是“唯一可信源”，所有默认值由此导出，其他文件一律引用这里的默认。                // 原则：集中定义，统一出口
// - 组织顺序按“功能与逻辑”分组：应用偏好 → 主题/调色 → 导出/交互 → 图表默认 →              // 组织结构说明
//   指标默认（MA/量窗）→ 缠论默认与预设 → 窗口预设。                                       // 组织结构说明（续）
// - 本次改动：                                                                  // 本轮改动摘要
//   1) 原始K线增加“阳线淡显/阴线淡显”（仅作用填充），保持上下影线/轮廓线100%不受影响；      // 变更点 1
//   2) 合并K线增加“填充淡显”与“显示层级（先/后，默认先）”；颜色同时作用于轮廓与填充；        // 变更点 2
//   3) 移除根层 displayOrder，改由 mergedK.displayOrder 管理合并K线的层级先后。              // 变更点 3
// ==============================                                           // 分隔注释

// ------------------------------                                          // 小节：应用偏好
// 一、应用偏好（用户可操作的全局偏好）                                       // 小节标题
// ------------------------------                                          // 分隔线
export const DEFAULT_APP_PREFERENCES = {
  // 导出默认应用偏好对象
  chartType: "kline", // 默认主图类型：k线模式
  freq: "1d", // 默认频率（日线）
  adjust: "qfq", // 默认复权类型：前复权
  windowPreset: "ALL", // 默认窗宽预设：ALL（全量）
  useMACD: true, // 指标默认：启用 MACD
  useKDJ: false, // 指标默认：禁用 KDJ
  useRSI: false, // 指标默认：禁用 RSI
  useBOLL: false, // 指标默认：禁用 BOLL
}; // 对象结束

// ------------------------------                                          // 小节：主题/调色
// 二、主题与调色（供图表/组件使用）                                           // 小节标题
// ------------------------------                                          // 分隔线
export const STYLE_PALETTE = {
  // 导出调色板
  lines: [
    // 折线系列的配色与样式（循环使用）
    { color: "#ee6666", width: 1, style: "solid" }, // 线色1
    { color: "#fac858", width: 1, style: "solid" }, // 线色2
    { color: "#5470c6", width: 1, style: "solid" }, // 线色3
    { color: "#91cc75", width: 1, style: "solid" }, // 线色4
    { color: "#fc8452", width: 1, style: "solid" }, // 线色5
    { color: "#73c0de", width: 1, style: "solid" }, // 线色6
    { color: "#9a60b4", width: 1, style: "solid" }, // 线色7
    { color: "#ea7ccc", width: 1, style: "solid" }, // 线色8
  ], // 数组结束
  bars: {
    // 柱图配色
    volume: { up: "#ef5350", down: "#26a69a" }, // 量窗柱色（红涨绿跌）
    macd: { positive: "#d94e4e", negative: "#47a69b" }, // MACD 柱正/负配色
  }, // bars 结束
}; // 调色板对象结束

// ------------------------------                                          // 小节：导出/交互
// 三、导出与交互控制（不可见但具“设置”性质的参数）                             // 小节标题
// ------------------------------                                          // 分隔线
export const DEFAULT_EXPORT_SETTINGS = {
  // 导出设置
  background: "#111", // 导出图像背景色（与页面主背景一致）
  pixelRatio: 2, // PNG/JPG 像素比
  includeDataDefault: false, // HTML 快照默认不内嵌数据
}; // 对象结束

export const DEFAULT_VOL_MARKER_SIZE = {
  // 量/额标记尺寸默认
  minPx: 1, // 标记宽度最小像素
  maxPx: 16, // 标记宽度最大像素
  baseHeightPx: 10, // 标记基准高度像素
  offsetK: 1.2, // 标记与柱底的垂直偏移倍数
}; // 对象结束

// ------------------------------                                          // 小节：图表默认
// 四、图表默认（主 K 线样式）                                                // 小节标题
// ------------------------------                                          // 分隔线
export const DEFAULT_KLINE_STYLE = {
  // 柱宽百分比（保留设置项，但设置窗当前不显示该项）
  barPercent: 100,

  // 原始K线（蜡烛）颜色与淡显（仅作用填充体）
  upColor: "#f56c6c",                // 阳线主色（边线/影线/填充基色）
  downColor: "#26a69a",              // 阴线主色（边线/影线/填充基色）
  originalFadeUpPercent: 100,        // 阳线填充淡显（0~100；100=不淡显，纯色填充；仅作用填充，不影响边线/影线）
  originalFadeDownPercent: 0,        // 阴线填充淡显（0~100；默认空心效果=0）
  originalEnabled: true,             // 原始K线显示开关（默认选中）

  // 合并K线（HL柱）样式与层级
  mergedEnabled: true,               // 合并K线显示开关（默认选中）
  mergedK: {
    outlineWidth: 1.2,               // 轮廓线宽（作用于轮廓线）
    upColor: "#FF0000",              // 上涨颜色（同时作用于轮廓线与填充体）
    downColor: "#00ff00",            // 下跌颜色（同时作用于轮廓线与填充体）
    fillFadePercent: 0,              // 填充淡显（0~100；仅作用填充，轮廓线始终100%）
    displayOrder: "first",           // 显示层级：'first'（先）|'after'（后）；默认先
  },

  // 保留旧字段兼容（不再使用）
  subType: "candlestick",
};

// ------------------------------                                          // 小节：指标默认
// 五、指标默认（MA / 量窗）                                                   // 小节标题
// ------------------------------                                          // 分隔线
export const DEFAULT_MA_CONFIGS = {
  // 主图 MA 默认
  MA5: {
    enabled: true,
    period: 5,
    color: STYLE_PALETTE.lines[0].color,
    width: 1,
    style: "solid",
  }, // MA5
  MA10: {
    enabled: true,
    period: 10,
    color: STYLE_PALETTE.lines[1].color,
    width: 1,
    style: "solid",
  }, // MA10
  MA20: {
    enabled: true,
    period: 20,
    color: STYLE_PALETTE.lines[2].color,
    width: 1,
    style: "solid",
  }, // MA20
  MA30: {
    enabled: false,
    period: 30,
    color: STYLE_PALETTE.lines[3].color,
    width: 1,
    style: "dashed",
  }, // MA30
  MA60: {
    enabled: false,
    period: 60,
    color: STYLE_PALETTE.lines[4].color,
    width: 1,
    style: "dashed",
  }, // MA60
  MA120: {
    enabled: false,
    period: 120,
    color: STYLE_PALETTE.lines[5].color,
    width: 1,
    style: "dotted",
  }, // MA120
  MA250: {
    enabled: false,
    period: 250,
    color: STYLE_PALETTE.lines[6].color,
    width: 1,
    style: "dotted",
  }, // MA250
}; // 对象结束

export const DEFAULT_VOL_SETTINGS = {
  // 量窗默认设置
  mode: "vol", // 模式（vol/amount）
  unit: "auto", // 单位策略（保留占位）
  rvolN: 20, // RVOL 基期（占位）
  volBar: {
    // 柱体样式
    barPercent: 100, // 柱宽百分比
    upColor: STYLE_PALETTE.bars.volume.up, // 阳柱色
    downColor: STYLE_PALETTE.bars.volume.down, // 阴柱色
  }, // volBar 结束
  mavolStyles: {
    // MAVOL 三条线默认
    MAVOL5: {
      enabled: true,
      period: 5,
      width: 1,
      style: "solid",
      color: STYLE_PALETTE.lines[0].color,
      namePrefix: "MAVOL",
    }, // 5
    MAVOL10: {
      enabled: true,
      period: 10,
      width: 1,
      style: "solid",
      color: STYLE_PALETTE.lines[1].color,
      namePrefix: "MAVOL",
    }, // 10
    MAVOL20: {
      enabled: true,
      period: 20,
      width: 1,
      style: "solid",
      color: STYLE_PALETTE.lines[2].color,
      namePrefix: "MAVOL",
    }, // 20
  }, // mavolStyles 结束
  markerPump: {
    enabled: true,
    shape: "triangle",
    color: "#FFFF00",
    threshold: 1.5,
  }, // 放量标记
  markerDump: {
    enabled: true,
    shape: "diamond",
    color: "#00ff00",
    threshold: 0.7,
  }, // 缩量标记
}; // 对象结束

// ------------------------------                                          // 小节：缠论默认
// 六、缠论默认与视觉预设                                                      // 小节标题
// ------------------------------                                          // 分隔线
export const CHAN_DEFAULTS = {
  // 缠论覆盖层默认
  showUpDownMarkers: true, // 显示涨跌标记
  anchorPolicy: "extreme", // 承载点策略（right/extreme）
  visualPreset: "tri-default", // 视觉预设键
  markerMinPx: 1, // 标记最小宽度
  markerMaxPx: 16, // 标记最大宽度
  opacity: 0.9, // 标记透明度
  upShape: "triangle",
  upColor: "#f56c6c", // 上涨符号与颜色
  downShape: "triangle",
  downColor: "#00ff00", // 下跌符号与颜色
  maxVisibleMarkers: 1000, // 单视窗可见标记上限（超过抽稀）
}; // 对象结束

export const CHAN_MARKER_PRESETS = {
  // 缠论预设（符号/旋转/填充）
  "tri-default": {
    up: { shape: "triangle", rotate: 0, fill: "#f56c6c" },
    down: { shape: "triangle", rotate: 180, fill: "#00ff00" },
  }, // 三角预设
  diamond: {
    up: { shape: "diamond", rotate: 0, fill: "#f56c6c" },
    down: { shape: "diamond", rotate: 0, fill: "#00ff00" },
  }, // 菱形预设
  dot: {
    up: { shape: "circle", rotate: 0, fill: "#f56c6c" },
    down: { shape: "circle", rotate: 0, fill: "#00ff00" },
  }, // 圆点预设
  square: {
    up: { shape: "rect", rotate: 0, fill: "#f56c6c" },
    down: { shape: "rect", rotate: 0, fill: "#00ff00" },
  }, // 方块预设
}; // 预设结束

// ------------------------------                                          // 小节：窗口预设
// 七、窗口预设（主窗控制条按钮集合）                                           // 小节标题
// ------------------------------                                          // 分隔线
// 注：删除 YTD，仅保留 ALL 与其余原有窗宽项；ALL = 当前“已加载序列”的总根数 n。            // 解释说明
export const WINDOW_PRESETS = [
  // 窗口预设列表
  "5D",
  "10D", // 近 5/10 天
  "1M",
  "3M",
  "6M", // 近 1/3/6 月（近似）
  "1Y",
  "3Y",
  "5Y", // 近 1/3/5 年（近似）
  "ALL", // 全部（当前序列 n）
]; // 数组结束

// ------------------------------                                          // 小节：分型默认
// 八、分型默认（基于 HL 柱）                                                  // 小节标题
// ------------------------------                                          // 分隔线
export const FRACTAL_DEFAULTS = {
  // 分型默认配置
  enabled: true, // 显示分型标记
  showConfirmLink: false, // 显示确认分型连线（默认关闭）
  showStrength: { strong: true, standard: true, weak: true }, // 三档分型显示开关
  minTickCount: 0, // 显著度：最小跳动单位个数（0=关闭）
  minPct: 0, // 显著度：最小百分比（0=关闭）
  minCond: "or", // 判定条件（or/and）
  markerMinPx: 1,
  markerMaxPx: 16,
  markerYOffsetPx: 2, // 标记尺寸与极值偏移
  topShape: "triangle",
  bottomShape: "triangle", // 顶/底默认形状
  styleByStrength: {
    // 三档分型外观默认
    strong: {
      bottomShape: "triangle",
      bottomColor: "#FF0000",
      topShape: "triangle",
      topColor: "#FF0000",
      fill: "solid",
      enabled: true,
    }, // 强
    standard: {
      bottomShape: "triangle",
      bottomColor: "#FFFF00",
      topShape: "triangle",
      topColor: "#FFFF00",
      fill: "solid",
      enabled: true,
    }, // 标准
    weak: {
      bottomShape: "diamond",
      bottomColor: "#90EE90",
      topShape: "diamond",
      topColor: "#90EE90",
      fill: "hollow",
      enabled: true,
    }, // 弱
  }, // styleByStrength 结束
  confirmStyle: {
    bottomShape: "circle",
    bottomColor: "#00ff00",
    topShape: "circle",
    topColor: "#00ff00",
    fill: "solid",
    enabled: true,
  }, // 确认分型样式
}; // 对象结束

export const FRACTAL_SHAPES = [
  // 设置窗下拉：符号备选
  { v: "triangle", label: "▲" }, // 三角
  { v: "diamond", label: "◆" }, // 菱形
  { v: "rect", label: "■" }, // 方块
  { v: "circle", label: "●" }, // 圆形
  { v: "pin", label: "📍" }, // 图钉
  { v: "arrow", label: "⬇" }, // 箭头
]; // 数组结束

export const FRACTAL_FILLS = [
  // 设置窗下拉：填充方式
  { v: "solid", label: "实心" }, // 实心
  { v: "hollow", label: "空心" }, // 空心
]; // 数组结束

// ======================================================================                                     // 小节：预设映射与高亮
// 预设 → barsCount 映射工具（以“原始 K 根数”为单位；ALL = totalBars）                                         // 标题说明
// ======================================================================                                     // 分隔注释

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
} // 函数结束

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
    if (p === "5D") return 5; // 5 天
    if (p === "10D") return 10; // 10 天
    if (p === "1M") return 22; // 1 月 ~ 22 个交易日近似
    if (p === "3M") return 66; // 3 月
    if (p === "6M") return 132; // 6 月
    if (p === "1Y") return 244; // 1 年
    if (p === "3Y") return 732; // 3 年
    if (p === "5Y") return 1220; // 5 年
    return 0; // 其它返回 0
  } // 函数结束
  function weeksOf(p) {
    // 预设 → 周数近似
    if (p === "5D") return 1; // 约 1 周
    if (p === "10D") return 2; // 约 2 周
    if (p === "1M") return 4; // 1 月约 4 周
    if (p === "3M") return 12; // 3 月约 12 周
    if (p === "6M") return 26; // 6 月约 26 周
    if (p === "1Y") return 52; // 1 年约 52 周
    if (p === "3Y") return 156; // 3 年约 156 周
    if (p === "5Y") return 260; // 5 年约 260 周
    return 0; // 其它返回 0
  } // 函数结束
  function monthsOf(p) {
    // 预设 → 月数近似
    if (p === "1M") return 1; // 1 月
    if (p === "3M") return 3; // 3 月
    if (p === "6M") return 6; // 6 月
    if (p === "1Y") return 12; // 1 年
    if (p === "3Y") return 36; // 3 年
    if (p === "5Y") return 60; // 5 年
    if (p === "5D" || p === "10D") return 1; // 5/10天最少也回退为 1 月显示
    return 0; // 其它返回 0
  } // 函数结束

  let bars = 0; // barsCount 变量
  if (isMinute) {
    // 分钟族处理（向上取整）
    const perDay = minuteBarsPerDay(String(freq)); // 每日根数估算
    bars = Math.ceil(perDay * daysOf(preset)); // 天数换算为bars（向上取整）
  } else if (isDaily) {
    // 日线（整数）
    bars = Math.ceil(daysOf(preset)); // 向上取整（整数保持不变）
  } else if (isWeekly) {
    // 周线
    bars = Math.ceil(weeksOf(preset)); // 向上取整
  } else if (isMonthly) {
    // 月线
    bars = Math.ceil(monthsOf(preset)); // 向上取整
  } else {
    // 兜底
    bars = Math.ceil(daysOf(preset)); // 向上取整
  }

  bars = Math.max(1, Math.floor(bars || 0)); // 下限：至少 1 根
  if (n > 0) bars = Math.min(bars, n); // 上限不超过 n
  return bars; // 返回 barsCount
} // 函数结束

export function pickPresetByBarsCountDown(freq, barsCount, totalBars) {
  // 向下就近高亮
  const candidates = WINDOW_PRESETS.filter((p) => p !== "ALL") // 从预设生成候选表 // 去掉 ALL（避免无平移空间默认 ALL）
    .map((p) => ({ p, v: presetToBars(freq, p, totalBars) })) // 计算每项 bars（内部已向上取整）
    .filter((x) => x.v > 0) // 过滤无效条目
    .sort((a, b) => a.v - b.v); // 按 bars 升序
  if (!candidates.length) return "ALL"; // 无候选则回退 ALL
  const target = Math.max(1, Math.ceil(Number(barsCount || 0))); // 目标 barsCount（向上取整）
  let chosen = candidates[0]; // 缺省取最小
  for (const c of candidates) {
    // 遍历找 <= target 的最大项
    if (c.v <= target) chosen = c;
    else break; // 超出则停止
  }
  return chosen.p; // 返回预设键
} // 函数结束
