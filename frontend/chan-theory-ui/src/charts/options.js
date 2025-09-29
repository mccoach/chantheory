// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options.js
// ==============================
// 说明：ECharts 选项生成（主/量/指标 · 逐行注释 · 全量文件）
// 本次与合并K线边框颜色相关的根因修复：
// - 合并K线默认颜色的回退改为使用 DEFAULT_KLINE_STYLE.mergedK.upColor/downColor，
//   不再回退到主题涨跌色，避免与设置项不一致。
// - 合并K线边框与填充均源自 MK.upColor/MK.downColor；填充再按淡显处理，边框始终100%。
// - 关键修复：applyUi 增加 initialRange 参数，让 setOption 时直接应用正确窗口，避免闪回 ALL。
// ==============================

/* =============================
 * 主题读取与默认常量
 * ============================= */
import { getChartTheme } from "@/charts/theme"; // 读取 CSS 变量映射到的 ECharts 主题颜色
import {
  STYLE_PALETTE, // 颜色调色板（线条、柱子）
  DEFAULT_VOL_SETTINGS, // 量窗默认设置（用于阈值/颜色等兜底）
  DEFAULT_VOL_MARKER_SIZE, // 量窗标记（放/缩量）尺寸与偏移默认值
  DEFAULT_KLINE_STYLE, // 主图K线默认（新增：原始/合并K线控制）
} from "@/constants"; // 集中默认（不含本文件内的 UI 常量）

/* =============================
 * 工具：固定 tooltip 定位器
 * ============================= */

// 全局 tooltip 固定侧（左/右）
let GLOBAL_TIP_SIDE = "left"; // 用于在左右边缘自动切换时记忆当前侧

/**
 * 创建固定 tooltip 定位器（主/量/指标复用）
 * - defaultSide：默认固定在哪一侧（left/right）
 * - getOffset：可选的偏移函数，返回 {x,y} 叠加到基础位置
 */
export function createFixedTooltipPositioner(defaultSide = "left", getOffset) {
  // 保护：若 GLOBAL_TIP_SIDE 非 left/right，则以 defaultSide 生效
  if (GLOBAL_TIP_SIDE !== "left" && GLOBAL_TIP_SIDE !== "right") {
    GLOBAL_TIP_SIDE = defaultSide === "right" ? "right" : "left";
  }
  // 返回 ECharts 的 position 回调
  return function (pos, _params, dom, _rect, size) {
    // 取宿主宽度（用于判断左右边缘）
    const host = dom && dom.parentElement ? dom.parentElement : null;
    const hostRect = host ? host.getBoundingClientRect() : { width: 800 };
    // tooltip 内容宽度估算（可靠性足够）
    const tipW = (size && size.contentSize && size.contentSize[0]) || 260;
    const margin = 8; // 画布边距
    const x = Array.isArray(pos) ? pos[0] : 0; // 当前坐标 x
    // 判断接近左/右边缘
    const nearLeft = x <= tipW + margin + 12;
    const nearRight = hostRect.width - x <= tipW + margin + 12;
    // 动态切换全局侧
    if (nearLeft) GLOBAL_TIP_SIDE = "right";
    else if (nearRight) GLOBAL_TIP_SIDE = "left";
    // 基础位置（固定在左/右上角）
    const baseX =
      GLOBAL_TIP_SIDE === "left"
        ? margin
        : Math.max(margin, hostRect.width - tipW - margin);
    const baseY = 8;
    // 叠加偏移
    let off = { x: 0, y: 0 };
    try {
      const t = typeof getOffset === "function" ? getOffset() : null;
      if (t && typeof t.x === "number" && typeof t.y === "number") off = t;
    } catch {}
    return [baseX + (off.x || 0), baseY + (off.y || 0)];
  };
}
/* =============================
 * 统一布局常量（基础 UI）
 * ============================= */
const LAYOUT = {
  TOP_TEXT_PX: 28, // 顶栏高度（画布内）
  LEFT_MARGIN_PX: 64, // 网格左边距
  RIGHT_MARGIN_PX: 10, // 网格右边距
  SLIDER_HEIGHT_PX: 26, // 主窗 slider 高度
  MAIN_AXIS_LABEL_SPACE_PX: 30, // 主窗横轴标签的预留空间（可通过 ui 覆盖）
  MAIN_BOTTOM_EXTRA_PX: 2, // 主窗网格底部额外空白
};

/* =============================
 * 小工具：时间/单位/数组等
 * ============================= */

// 安全返回数组
function asArray(x) {
  return Array.isArray(x) ? x : [];
}

// 安全返回对象
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

// 保留 3 位小数格式
function fmt3(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(3) : "";
}

// 是否分钟族（以 freq 后缀 m 判断）
function isMinuteFreq(freq) {
  return typeof freq === "string" && /m$/.test(freq);
}

// 两位补零
function pad2(n) {
  return String(n).padStart(2, "0");
}

/**
 * 将 ISO8601 时间（可能带时区）格式化为“无时区短文本”
 * - 分钟族：YYYY-MM-DD HH:MM
 * - 日/周/月：YYYY-MM-DD
 */
function fmtTimeByFreq(freq, isoVal) {
  try {
    const d = new Date(isoVal); // 浏览器本地解析
    if (Number.isNaN(d.getTime())) return String(isoVal || "");
    const Y = d.getFullYear();
    const M = pad2(d.getMonth() + 1);
    const D = pad2(d.getDate());
    const h = pad2(d.getHours());
    const m = pad2(d.getMinutes());
    return isMinuteFreq(freq) ? `${Y}-${M}-${D} ${h}:${m}` : `${Y}-${M}-${D}`;
  } catch {
    return String(isoVal || "");
  }
}

/**
 * 返回横轴标签格式化函数（依频率输出短文本）
 */
function makeAxisLabelFormatter(freq) {
  return (val) => fmtTimeByFreq(freq, val);
}

/**
 * 量/额的单位选择器（亿/万/无）
 */
function pickUnitDivider(maxAbs, isAmount) {
  if (maxAbs >= 1e8) return { div: 1e8, lab: "亿" + (isAmount ? "元" : "") };
  if (maxAbs >= 1e4) return { div: 1e4, lab: "万" + (isAmount ? "元" : "") };
  return { div: 1, lab: isAmount ? "元" : "" };
}

/**
 * 应用单位（带自动小数位）
 */
function fmtUnit(val, unit) {
  const n = Number(val);
  if (!Number.isFinite(n)) return "-";
  const x = n / (unit?.div || 1);
  const digits = Math.abs(x) >= 100 ? 0 : Math.abs(x) >= 10 ? 1 : 2;
  return x.toFixed(digits) + (unit?.lab || "");
}

/* =============================
 * 新增小工具：hex 转 rgba（用于合并K线淡显/空心/轮廓）
 * ============================= */
function hexToRgba(hex, alpha = 1.0) {
  try {
    const h = String(hex || "").replace("#", "");
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    const a = Math.max(0, Math.min(1, Number(alpha || 1)));
    return `rgba(${r},${g},${b},${a})`;
  } catch {
    return hex || "#999";
  }
}

/* =============================
 * 应用 UI：网格/坐标轴/dataZoom（含 slider labelFormatter）
 * ============================= */

/**
 * 将通用 UI 布局应用到 option（不覆盖上层业务特有字段）
 * - 参数：
 *   option：已构造好的基础 option
 *   ui：可选覆盖项，如 { isMain, sliderHeightPx, mainAxisLabelSpacePx, tooltipPositioner, initialRange }
 *   ctx：{ dates, freq } 用于时间格式化和缩放范围确定
 */
function applyUi(option, ui, { dates, freq }) {
  // 取主题颜色
  const theme = getChartTheme();

  // 读取 UI 覆盖或使用默认
  const leftPx = ui?.leftPx ?? LAYOUT.LEFT_MARGIN_PX;
  const rightPx = ui?.rightPx ?? LAYOUT.RIGHT_MARGIN_PX;
  const isMain = !!ui?.isMain;
  const gridTop = 0; // 顶部紧贴（顶栏占用画布内 28px）
  const nonMainExtra = ui?.extraBottomPx ? Number(ui.extraBottomPx) : 0;
  const gridBottom = isMain
    ? (ui?.sliderHeightPx ?? LAYOUT.SLIDER_HEIGHT_PX) +
      (ui?.mainAxisLabelSpacePx ?? LAYOUT.MAIN_AXIS_LABEL_SPACE_PX) +
      (ui?.mainBottomExtraPx ?? LAYOUT.MAIN_BOTTOM_EXTRA_PX)
    : nonMainExtra;

  // 应用网格
  option.grid = {
    left: leftPx,
    right: rightPx,
    top: gridTop,
    bottom: gridBottom,
    containLabel: false, // 我们手动控制 margin
  };

  // 横轴数据长度
  const len = Array.isArray(dates) ? dates.length : 0;

  // 合并 xAxis（不覆盖已有的 data 字段以外的特殊配置）
  option.xAxis = Object.assign({}, option.xAxis || {}, {
    type: "category",
    data: option.xAxis?.data || dates || [],
    boundaryGap: ["0%", "0%"], // 右端贴合
    axisTick: Object.assign({}, option.xAxis?.axisTick || {}, {
      alignWithLabel: true, // 与标签对齐
    }),
    axisLabel: Object.assign({}, option.xAxis?.axisLabel || {}, {
      color: theme.axisLabelColor, // 标签颜色
      margin: ui?.xAxisLabelMargin ?? 6, // 基础 margin（更大避让由主窗决定）
      formatter: makeAxisLabelFormatter(freq), // 短文本时间
    }),
    axisLine: Object.assign({}, option.xAxis?.axisLine || {}, {
      lineStyle: Object.assign(
        { color: theme.axisLineColor }, // 坐标轴线颜色（防止变亮）
        option.xAxis?.axisLine?.lineStyle || {}
      ),
    }),
    min: 0,
    max: len ? len - 1 : undefined,
    splitLine: Object.assign({}, option.xAxis?.splitLine || {}, {
      lineStyle: Object.assign(
        { color: theme.gridLineColor }, // 网格线颜色（防止变亮）
        option.xAxis?.splitLine?.lineStyle || {}
      ),
    }),
    // ——仅隐藏 X 轴的轴指示器标签（底部时间），保留 Y 轴数值标签——
    axisPointer: Object.assign({}, option.xAxis?.axisPointer || {}, {
      label: Object.assign({}, option.xAxis?.axisPointer?.label || {}, {
        show: false,
      }),
    }),
  });

  // 合并 yAxis（保留业务字段，如量窗的 min:0）
  option.yAxis = Object.assign({}, option.yAxis || {}, {
    scale: option.yAxis?.scale !== undefined ? option.yAxis.scale : true, // 默认启用 scale
    axisLabel: Object.assign({}, option.yAxis?.axisLabel || {}, {
      color: theme.axisLabelColor,
      margin: (option.yAxis?.axisLabel && option.yAxis.axisLabel.margin) || 6,
    }),
    axisLine: Object.assign({}, option.yAxis?.axisLine || {}, {
      lineStyle: Object.assign(
        { color: theme.axisLineColor },
        option.yAxis?.axisLine?.lineStyle || {}
      ),
    }),
    splitLine: Object.assign({}, option.yAxis?.splitLine || {}, {
      lineStyle: Object.assign(
        { color: theme.gridLineColor },
        option.yAxis?.splitLine?.lineStyle || {}
      ),
    }),
  });

  // slider 两端的 label 格式化（显示“无时区短文本”）
  const labelFmt = (val) => {
    if (Array.isArray(dates) && dates.length) {
      const idx = Number(val);
      if (Number.isInteger(idx) && idx >= 0 && idx < dates.length) {
        return fmtTimeByFreq(freq, dates[idx]);
      }
    }
    return fmtTimeByFreq(freq, val);
  };

  // --- 初始范围（仅在需要时注入；交互会话期间禁止我们回写范围） ---
  const wantInitialRange =
    ui?.initialRange &&
    Number.isFinite(ui.initialRange.startValue) &&
    Number.isFinite(ui.initialRange.endValue);
  // 新增：是否作为“交互源”（主窗=可交互；副窗=仅联动）
  const isInteractionSource = !!ui?.isInteractionSource;

  const initialRange = wantInitialRange
    ? {
        startValue: ui.initialRange.startValue,
        endValue: ui.initialRange.endValue,
      }
    : {};

  // dataZoom 角色配置
  // 主窗：inside + slider，启用鼠标滚轮缩放与拖动；realtime=true（会话交由 ECharts 内建）
  // 副窗：inside 仅联动，禁用用户缩放/拖动，但接收组内联动事件
  if (isMain && isInteractionSource) {
    const dzInside = Object.assign(
      {
        type: "inside",
        // 允许鼠标实时缩放与拖动（会话由 ECharts 内建）
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        moveOnMouseWheel: true,
        // 与主窗数据口径：不裁剪数据
        filterMode: "none",
        // 实时反馈给 UI；我们不在会话中落地范围，仅做会后承接
        realtime: true,
      },
      wantInitialRange ? initialRange : {}
    );
    const dzSlider = Object.assign(
          {
            type: "slider",
            height: ui?.sliderHeightPx ?? LAYOUT.SLIDER_HEIGHT_PX,
            bottom: 0,
            showDetail: true,
            labelFormatter: labelFmt,
        filterMode: "none",
        realtime: true,
      },
      wantInitialRange ? initialRange : {}
    );
    option.dataZoom = [dzInside, dzSlider];
  } else {
    // 副窗：仅联动 inside；禁止本窗用户交互，仍可接收组内同步
    const dzFollower = Object.assign(
      {
        type: "inside",
        zoomOnMouseWheel: false,
        moveOnMouseMove: false,
        moveOnMouseWheel: false,
        filterMode: "none",
        realtime: true,
      },
      wantInitialRange ? initialRange : {}
    );
    option.dataZoom = [dzFollower];
  }

  // 返回合并后的 option
  return option;
}

/* =============================
 * 主图 tooltip 格式化器（K 线/HL 柱 + MA 值）
 * ============================= */

/**
 * 返回主图 tooltip 的 formatter
 * - 内容：时间短文本 + K/HL 行 + O/H/L/C + MAx 行（如启用）
 * - 注意：这里不设置 position，由上层通过 ui 传入固定器
 */
function makeMainTooltipFormatter({
  theme, // 主题（用于默认颜色）
  chartType, // kline | line
  freq, // 频率（决定时间短文本）
  candles, // 蜡烛原始数组（用于 OHLC）
  maConfigs, // MA 配置映射（用于显示 MAx 行）
  adjust, // 复权标签文本
  klineStyle, // K 线样式（bar/candlestick）
  reducedBars, // 去包含后的 HL 柱（数组）
  mapOrigToReduced, // 原始索引 → HL 柱索引映射
}) {
  const list = asArray(candles); // 蜡烛列表（容错成数组）
  return function (params) {
    // 无参数时直接返回空
    if (!Array.isArray(params) || !params.length) return "";
    // 时间短文本（去时区）
    const rawLabel = params[0].axisValue || params[0].axisValueLabel || "";
    const timeLabel = fmtTimeByFreq(freq, rawLabel);
    // 复权标签（如 qfq/hfq）
    const adjLabel = { qfq: "前复权", hfq: "后复权" }[adjust] || "";
    // 组装行（时间 + 复权）
    const rows = [
      `<div style="margin-bottom:4px;">${timeLabel} ${adjLabel}</div>`,
    ];
    // 当前数据索引
    const idx = params[0].dataIndex ?? 0;
    // 当前 K 数据
    const k = list[idx] || {};

    // —— 统一：所有 bar 显示 G/D（优先取对应合并K线 hi/lo；失败兜底当前 bar H/L） —— //
    let G = k.h,
      D = k.l;
    try {
      const entry = mapOrigToReduced && mapOrigToReduced[idx];
      const rb =
        entry && typeof entry.reducedIndex === "number"
          ? reducedBars[entry.reducedIndex]
          : null;
      if (rb && Number.isFinite(rb.hi) && Number.isFinite(rb.lo)) {
        G = rb.hi;
        D = rb.lo;
      }
    } catch {}
    rows.push(
      `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>G: ${fmt3(
        G
      )}</div>`
    );
    rows.push(
      `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>D: ${fmt3(
        D
      )}</div>`
    );

    // 原始 K 的 O/H/L/C 或折线 Close
    if (chartType === "kline") {
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>O: ${fmt3(
          k.o
        )}</div>`
      );
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>H: ${fmt3(
          k.h
        )}</div>`
      );
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>L: ${fmt3(
          k.l
        )}</div>`
      );
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>C: ${fmt3(
          k.c
        )}</div>`
      );
    } else {
      // 折线模式（仅 Close）
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:#03a9f4;"></span>Close: ${fmt3(
          k.c
        )}</div>`
      );
    }

    // 追加 MA（若启用）
    for (const p of params) {
      if (p.seriesType === "line" && p.seriesName !== "Close") {
        const val = Array.isArray(p.value)
          ? p.value[p.value.length - 1]
          : p.value;
        rows.push(
          `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:${
            p.color
          };"></span>${p.seriesName}: ${fmt3(val)}</div>`
        );
      }
    }
    return rows.join("");
  };
}

/* =============================
 * 量窗 tooltip 格式化器
 * ============================= */

/**
 * 量窗 tooltip：时间 + 当前量/额 + MAVOL 若有 + 换手率（如有）
 */
function makeVolumeTooltipFormatter({
  candles, // 蜡烛数组（取时间/涨跌/换手率）
  freq, // 频率（决定时间短文本）
  unitInfo, // 单位（亿/万）
  baseName, // VOL/AMOUNT
  mavolMap, // n -> 序列值
}) {
  const list = Array.isArray(candles) ? candles : [];
  return function (params) {
    if (!Array.isArray(params) || !params.length) return "";
    const p0 = params[0];
    const rawLabel = p0.axisValue || p0.axisValueLabel || "";
    const timeLabel = fmtTimeByFreq(freq, rawLabel);
    const idx = p0.dataIndex || 0;
    const k = list[idx] || {};
    const isVolMode = (baseName || "").toUpperCase() === "VOL";
    // 彩点颜色：按涨跌
    const isUp = Number(k.c) >= Number(k.o);
    const baseDotColor = isUp
      ? STYLE_PALETTE.bars.volume.up
      : STYLE_PALETTE.bars.volume.down;
    // 当前柱值
    const bar = params.find(
      (x) => (x.seriesType || "").toLowerCase() === "bar"
    );
    const baseRawVal = Array.isArray(bar?.value)
      ? bar.value[bar.value.length - 1]
      : bar?.value;
    const baseValText = fmtUnit(baseRawVal, unitInfo);
    // 放/缩量标签（若有散点叠加）
    const hasPump = params.some((pp) => pp.seriesName === "放量标记");
    const hasDump = params.some((pp) => pp.seriesName === "缩量标记");
    const statusTag = hasPump ? "（放）" : hasDump ? "（缩）" : "";
    // MAVOL 周期集合
    const periods = Object.keys(mavolMap || {})
      .map((x) => +x)
      .sort((a, b) => a - b);
    // 组装
    const rows = [];
    rows.push(`<div style="margin-bottom:4px;">${timeLabel}</div>`);
    rows.push(
      `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:${baseDotColor};"></span>${
        isVolMode ? "成交量" : "成交额"
      }: ${baseValText}${statusTag}</div>`
    );
    // MAVOL
    for (const n of periods) {
      const mv = mavolMap[n] ? mavolMap[n][idx] : null;
      if (mv == null || !Number.isFinite(+mv)) continue;
      const lineParam = params.find(
        (pp) =>
          (pp.seriesType || "").toLowerCase() === "line" &&
          typeof pp.seriesName === "string" &&
          pp.seriesName.endsWith(String(n))
      );
      const dotColor = lineParam?.color || "#ccc";
      const labelPrefix = isVolMode ? "量MA" : "额MA";
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:${dotColor};"></span>${labelPrefix}${n}: ${fmtUnit(
          +mv,
          unitInfo
        )}</div>`
      );
    }
    // 换手率（如有）
    if (typeof k.tr === "number") {
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>换手率: ${fmt3(
          k.tr
        )}%</div>`
      );
    }
    // 额/量的互补输出
    if (isVolMode) {
      if (typeof k.a === "number") {
        rows.push(
          `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>成交额: ${fmtUnit(
            k.a,
            pickUnitDivider(Math.abs(k.a || 0), true)
          )}</div>`
        );
      }
    } else {
      if (typeof k.v === "number") {
        rows.push(
          `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>成交量: ${fmtUnit(
            k.v,
            pickUnitDivider(Math.abs(k.v || 0), false)
          )}手</div>`
        );
      }
    }
    return rows.join("");
  };
}

/* =============================
 * 主图 option 生成（K 线/HL 柱 + MA）
 * ============================= */

/**
 * 生成主图 option
 * - candles：原始 K
 * - indicators：计算出的指标
 * - chartType：kline | line
 * - maConfigs：MA 配置映射
 * - freq：频率（决定时间短文本）
 * - klineStyle：主图样式（新增：originalEnabled/mergedEnabled/displayOrder/mergedK）
 * - adjust：复权类型
 * - reducedBars/mapOrigToReduced：去包含后的合并K线与映射
 * - ui：界面参数（含 tooltipPositioner 供固定浮窗位置）
 */
export function buildMainChartOption(
  {
    candles,
    indicators,
    chartType,
    maConfigs,
    freq,
    klineStyle,
    adjust,
    reducedBars,
    mapOrigToReduced,
  },
  ui
) {
  // 主题
  const theme = getChartTheme();
  // 蜡烛数组与指标
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  // 横轴时间数组
  const dates = list.map((d) => d.t);
  // 系列集合
  const series = [];

  // —— 新增：显示控制（原始/合并）以及层级（z） —— //
  const ks = klineStyle || DEFAULT_KLINE_STYLE || {};
  const MK = ks.mergedK || DEFAULT_KLINE_STYLE.mergedK || {};
  const showOriginal = (ks.originalEnabled ?? true) === true;
  const showMerged = (ks.mergedEnabled ?? true) === true;
  const mergedFirst = String(MK.displayOrder || "first") === "first";
  const originalZ = showOriginal && showMerged ? (mergedFirst ? 2 : 3) : 3;
  const mergedZ = showOriginal && showMerged ? (mergedFirst ? 3 : 2) : 3;

  // K 线模式
  if (chartType === "kline") {
    // 原始K线（蜡烛）：淡显仅作用填充体；上下影线与轮廓线保持100%
    if (showOriginal) {
      const upColor = ks.upColor || DEFAULT_KLINE_STYLE.upColor;
      const downColor = ks.downColor || DEFAULT_KLINE_STYLE.downColor;
      const upPct =
        Math.max(0, Math.min(100, Number(ks.originalFadeUpPercent ?? 100))) /
        100;
      const downPct =
        Math.max(0, Math.min(100, Number(ks.originalFadeDownPercent ?? 0))) /
        100;

      // 淡显为0时用 "transparent" 确保空心
      const upFill = upPct === 0 ? "transparent" : hexToRgba(upColor, upPct);
      const downFill =
        downPct === 0 ? "transparent" : hexToRgba(downColor, downPct);

      const ohlc = list.map((d) => [d.o, d.c, d.l, d.h]);
      const klineSeries = {
        type: "candlestick",
        name: "原始K线",
        data: ohlc,
        itemStyle: {
          color: upFill, // 阳线主体填充（按淡显；0→透明）
          color0: downFill, // 阴线主体填充（按淡显；0→透明）
          borderColor: upColor, // 阳线轮廓/影线（100%）
          borderColor0: downColor, // 阴线轮廓/影线（100%）
          borderWidth: 1.2,
        },
        z: originalZ,
      };
      if (ks.barPercent && ks.barPercent < 100)
        klineSeries.barWidth = `${ks.barPercent}%`;
      series.push(klineSeries);
    }

    // 合并K线（HL 柱）
    if (showMerged && Array.isArray(reducedBars) && reducedBars.length) {
      const outlineW = Math.max(0.1, Number(MK.outlineWidth || 1.2));
      // 根因修复：默认颜色回退到 DEFAULT_KLINE_STYLE.mergedK.*，不再回退主题色
      const fallbackUp = DEFAULT_KLINE_STYLE.mergedK?.upColor || "#FF0000";
      const fallbackDn = DEFAULT_KLINE_STYLE.mergedK?.downColor || "#00ff00";
      const upC = MK.upColor || fallbackUp;
      const dnC = MK.downColor || fallbackDn;

      const fillAlpha = Math.max(
        0,
        Math.min(1, Number((MK.fillFadePercent ?? 0) / 100))
      );

      // 淡显为0时填充透明，实现空心；轮廓线始终100%
      const upFill =
        fillAlpha === 0 ? "transparent" : hexToRgba(upC, fillAlpha);
      const dnFill =
        fillAlpha === 0 ? "transparent" : hexToRgba(dnC, fillAlpha);

      const n = dates.length;
      const baseLow = new Array(n).fill(null);
      const hlSpan = new Array(n).fill(null);
      const upIndexSet = new Set();
      for (const rb of reducedBars) {
        const idx = Math.max(
          0,
          Math.min(n - 1, Number(rb?.anchor_idx ?? rb?.idx_end ?? 0))
        );
        const hi = Number(rb?.hi),
          lo = Number(rb?.lo);
        if (!Number.isFinite(hi) || !Number.isFinite(lo) || hi < lo) continue;
        baseLow[idx] = lo;
        hlSpan[idx] = hi - lo;
        if (Number(rb?.dir || 0) > 0) upIndexSet.add(idx);
      }
      // 透明底
      series.push({
        id: "MERGED_K_BASE",
        name: "合并K线",
        type: "bar",
        stack: "merged_k",
        data: baseLow,
        itemStyle: { color: "transparent" },
        ...(ks.barPercent && ks.barPercent < 100
          ? { barWidth: `${ks.barPercent}%` }
          : {}),
        barGap: "-100%",
        silent: true,
        z: mergedZ,
      });

      // 区间带（填充 + 轮廓）
      series.push({
        id: "MERGED_K_SPAN",
        name: "合并K线",
        type: "bar",
        stack: "merged_k",
        // 将每个数据项改写为对象，在 data 级别设置 itemStyle.borderColor（ECharts v6 不支持在系列级用函数设置 borderColor）
        data: hlSpan.map((v, i) =>
          v == null
            ? null
            : {
                value: v,
                itemStyle: {
                  borderColor: upIndexSet.has(i) ? MK.upColor : MK.downColor,
                },
              }
        ),
        ...(ks.barPercent && ks.barPercent < 100
          ? { barWidth: `${ks.barPercent}%` }
          : {}),
        barGap: "-100%",
        itemStyle: {
          // 填充色仍可用函数按涨跌设置
          color: (p) => (upIndexSet.has(p.dataIndex) ? upFill : dnFill),
          borderColor: (p) =>
            upIndexSet.has(p.dataIndex) ? MK.upColor : MK.downColor,
          borderWidth: outlineW,
          opacity: 1,
        },
        z: mergedZ,
      });
    }

    // MA 系列（若启用）
    Object.entries(maConfigs || {}).forEach(([key, conf]) => {
      if (!conf || !conf.enabled || !Number.isFinite(+conf.period)) return;
      const data = inds[key];
      if (!data) return;
      series.push({
        id: key,
        type: "line",
        name: `MA${conf.period}`,
        data,
        showSymbol: false,
        smooth: false,
        lineStyle: {
          width: conf.width ?? 1,
          type: conf.style ?? "solid",
          color: conf.color,
        },
        itemStyle: { color: conf.color },
        color: conf.color,
        emphasis: { disabled: true },
        z: 3,
      });
    });
  } else {
    // 折线模式（主图只画收盘价）
    series.push({
      type: "line",
      name: "Close",
      data: list.map((d) => d.c),
      showSymbol: false,
      smooth: true,
      lineStyle: { color: "#03a9f4", width: 1.0 },
      itemStyle: { color: "#03a9f4" },
      color: "#03a9f4",
    });
  }

  // 生成基础 option（先走 applyUi，后追加隐藏 overlay Y 轴）
  let option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    // 统一 tooltip（恢复“聚焦竖线 + 信息浮窗”）
    tooltip: {
      // 触发：按轴触发（显示竖线和多系列信息）
      trigger: "axis",
      // 轴指示器：用 cross 较清晰（也可改为 'line' 保持更轻）
      axisPointer: { type: "cross" },
      // 避免 body 附着与溢出滚动
      appendToBody: false,
      confine: true,
      // 自定义内容
      formatter: makeMainTooltipFormatter({
        theme,
        chartType,
        freq,
        candles: list,
        maConfigs,
        adjust,
        klineStyle: ks,
        reducedBars,
        mapOrigToReduced, // 用于判断当前是否承载点
      }),
      // 统一 className（与样式保持一致）
      className: "ct-fixed-tooltip",
      borderWidth: 0,
      backgroundColor: "rgba(20,20,20,0.85)",
      textStyle: { color: theme.textColor, fontSize: 12, align: "left" },
    },
    // 基础坐标轴（具体颜色/label 等在 applyUi 中合并）
    xAxis: { type: "category", data: dates },
    yAxis: { scale: true },
    // 系列
    series,
  };

  // MOD: 仅当传入了定位器时才设置 position；否则保留默认（跟随鼠标）
  if (ui?.tooltipPositioner) {
    option.tooltip.position = ui.tooltipPositioner;
  }

  // 先应用通用 UI
  option = applyUi(
    option,
    {
      ...ui,
      isMain: true, // 主窗
    },
    { dates, freq }
  );

  // 核心新增：为主图添加第二条隐藏的 Y 轴（用于承载涨跌标记，不影响价格轴自适应）
  // - yAxis[0]：主价格轴（来自 applyUi）
  // - yAxis[1]：隐藏标记轴，固定范围 [0,1]，不显示，不参与缩放计算
  const mainYAxisObj =
    Array.isArray(option.yAxis) && option.yAxis.length
      ? option.yAxis[0]
      : option.yAxis; // 兼容对象/数组
  const overlayMarkerYAxis = {
    type: "value",
    min: 0,
    max: 1,
    show: false,
    scale: false,
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { show: false },
  };
  option.yAxis = [mainYAxisObj, overlayMarkerYAxis];

  return option;
}

/* =============================
 * 量窗 option 生成
 * ============================= */

/**
 * 生成量窗 option
 * - candles：原始 K
 * - indicators：已计算指标
 * - freq：频率（决定时间短文本）
 * - volCfg：量窗配置
 * - volEnv：{ hostWidth, visCount } 供标记尺寸估算
 * - ui：界面参数（含 tooltipPositioner）
 */
export function buildVolumeOption(
  { candles, indicators, freq, volCfg, volEnv },
  ui
) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const dates = list.map((d) => d.t);

  // 基础数据（量/额）
  const baseMode = volCfg && volCfg.mode === "amount" ? "amount" : "vol";
  const baseName = baseMode === "amount" ? "AMOUNT" : "VOL";
  const baseRaw =
    baseMode === "amount"
      ? list.map((d) => (typeof d.a === "number" ? d.a : null))
      : inds.VOLUME || list.map((d) => (typeof d.v === "number" ? d.v : null));
  const baseMaxAbs = baseRaw.reduce(
    (m, x) => (Number.isFinite(+x) ? Math.max(m, Math.abs(+x)) : m),
    0
  );
  const unitInfo = pickUnitDivider(baseMaxAbs, baseMode === "amount");

  // 柱系列
  const series = [];
  const vb = volCfg?.volBar || {};
  const barPercent = Number.isFinite(+vb.barPercent)
    ? Math.max(10, Math.min(100, Math.round(+vb.barPercent)))
    : 100;
  const upColor = vb.upColor || STYLE_PALETTE.bars.volume.up;
  const downColor = vb.downColor || STYLE_PALETTE.bars.volume.down;
  const baseScaled = baseRaw.map((v) => (Number.isFinite(+v) ? +v : null));
  series.push({
    id: baseName,
    type: "bar",
    name: baseName,
    data: baseScaled,
    itemStyle: {
      color: (p) => {
        const idx = p.dataIndex || 0;
        const k = list[idx] || {};
        return Number(k.c) >= Number(k.o) ? upColor : downColor;
      },
    },
    ...(barPercent && barPercent !== 100 ? { barWidth: `${barPercent}%` } : {}),
  });

  // MAVOL 线
  const namePrefixCN = baseMode === "amount" ? "额MA" : "量MA";
  const mstyles = volCfg?.mavolStyles || {};
  const periods = Object.keys(mstyles)
    .map((k) => mstyles[k])
    .filter(
      (s) => s && s.enabled && Number.isFinite(+s.period) && +s.period > 0
    )
    .sort((a, b) => +a.period - +b.period);
  function sma(arr, n) {
    const out = new Array(arr.length).fill(null);
    if (!Array.isArray(arr) || !arr.length || !Number.isFinite(+n) || n <= 0)
      return out;
    let sum = 0,
      cnt = 0;
    for (let i = 0; i < arr.length; i++) {
      const v = Number(arr[i]);
      if (Number.isFinite(v)) {
        sum += v;
        cnt += 1;
      }
      if (i >= n) {
        const ov = Number(arr[i - n]);
        if (Number.isFinite(ov)) {
          sum -= ov;
          cnt -= 1;
        }
      }
      out[i] = cnt > 0 && i >= n - 1 ? sum / cnt : null;
    }
    return out;
  }
  const mavolMap = {};
  for (const st of periods) {
    mavolMap[+st.period] = sma(baseScaled, +st.period);
  }
  for (const st of periods) {
    const n = +st.period;
    const lineColor = st.color || STYLE_PALETTE.lines[0].color;
    series.push({
      id: `MAVOL-${n}`,
      type: "line",
      name: `${namePrefixCN}${n}`,
      data: mavolMap[n],
      showSymbol: false,
      smooth: false,
      lineStyle: {
        width: Number.isFinite(+st.width) ? +st.width : 1,
        type: st.style || "solid",
        color: lineColor,
      },
      itemStyle: { color: lineColor },
      color: lineColor,
      z: 3,
    });
  }

  // 放/缩量标记尺寸估算（按可视柱宽）
  const hostW = Math.max(1, Number(volEnv?.hostWidth || 0));
  const visCount = Math.max(1, Number(volEnv?.visCount || baseScaled.length));
  // 新增：全局覆写优先（统一宽度源）
  const overrideW = Number(volEnv?.overrideMarkWidth);
  const approxBarWidthPx =
    hostW > 1 && visCount > 0
      ? Math.max(
          1,
          Math.floor(((hostW * 0.88) / visCount) * (barPercent / 100))
        )
      : 8;
  const MARKER_W_MIN = DEFAULT_VOL_MARKER_SIZE.minPx;
  const MARKER_W_MAX = DEFAULT_VOL_MARKER_SIZE.maxPx;
  const markerW = Number.isFinite(overrideW)
    ? Math.max(MARKER_W_MIN, Math.min(MARKER_W_MAX, Math.round(overrideW))) // 覆写优先
    : Math.max(
        MARKER_W_MIN,
        Math.min(MARKER_W_MAX, Math.round(approxBarWidthPx))
      );
  const markerH = DEFAULT_VOL_MARKER_SIZE.baseHeightPx;
  const symbolOffsetBelow = [
    0,
    Math.round(markerH * DEFAULT_VOL_MARKER_SIZE.offsetK),
  ];

  // 放/缩量散点
  const primPeriod = periods.length ? +periods[0].period : null;
  const primSeries = primPeriod ? mavolMap[primPeriod] : null;
  const pumpK = Number.isFinite(+volCfg?.markerPump?.threshold)
    ? +volCfg.markerPump.threshold
    : DEFAULT_VOL_SETTINGS.markerPump.threshold;
  const dumpK = Number.isFinite(+volCfg?.markerDump?.threshold)
    ? +volCfg.markerDump.threshold
    : DEFAULT_VOL_SETTINGS.markerDump.threshold;
  const pumpEnabled = (volCfg?.markerPump?.enabled ?? true) === true;
  const dumpEnabled = (volCfg?.markerDump?.enabled ?? true) === true;
  const pumpPts = [];
  const dumpPts = [];
  if (primSeries) {
    if (pumpEnabled && pumpK > 0) {
      for (let i = 0; i < baseScaled.length; i++) {
        const v = baseScaled[i],
          m = primSeries[i];
        if (!Number.isFinite(v) || !Number.isFinite(m) || m <= 0) continue;
        if (v >= pumpK * m) pumpPts.push([i, 0]);
      }
    }
    if (dumpEnabled && dumpK > 0) {
      for (let i = 0; i < baseScaled.length; i++) {
        const v = baseScaled[i],
          m = primSeries[i];
        if (!Number.isFinite(v) || !Number.isFinite(m) || m <= 0) continue;
        if (v <= dumpK * m) dumpPts.push([i, 0]);
      }
    }
  }
  if (pumpEnabled && pumpPts.length) {
    series.push({
      id: "VOL_PUMP_MARK",
      type: "scatter",
      name: "放量标记",
      data: pumpPts,
      symbol: volCfg?.markerPump?.shape || "triangle",
      symbolSize: () => [markerW, markerH],
      symbolOffset: symbolOffsetBelow,
      itemStyle: { color: volCfg?.markerPump?.color || "#ffb74d" },
      z: 4,
    });
  }
  if (dumpEnabled && dumpPts.length) {
    series.push({
      id: "VOL_DUMP_MARK",
      type: "scatter",
      name: "缩量标记",
      data: dumpPts,
      symbol: volCfg?.markerDump?.shape || "diamond",
      symbolSize: () => [markerW, markerH],
      symbolOffset: symbolOffsetBelow,
      itemStyle: { color: volCfg?.markerDump?.color || "#8d6e63" },
      z: 4,
    });
  }

  // 顶部空间与横轴 margin（按是否有标记略作增加）
  const anyMarkers =
    (pumpEnabled && pumpPts.length > 0) || (dumpEnabled && dumpPts.length > 0);
  const extraBottomPx = anyMarkers ? markerH : 0;
  const xAxisLabelMargin = anyMarkers ? Math.max(12, markerH + 12) : 12;

  // 量窗 option
  const option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    // 恢复“聚焦竖线 + 信息浮窗”
    tooltip: {
      trigger: "axis",
      // 修复：副窗仅纵向联动（x 轴），避免水平线与左下角数值
      axisPointer: { type: "line", axis: "x" },   // 关键：仅 x 轴
      appendToBody: false,
      confine: true,
      formatter: makeVolumeTooltipFormatter({
        candles: list,
        freq,
        unitInfo,
        baseName,
        mavolMap,
      }),
      className: "ct-fixed-tooltip",
      borderWidth: 0,
      backgroundColor: "rgba(20,20,20,0.85)",
      textStyle: { color: theme.textColor, fontSize: 12, align: "left" },
    },
    xAxis: { type: "category", data: dates },
    yAxis: {
      // 量窗保持从 0 起（业务共识）
      min: 0,
      scale: true,
      // 修复：彻底禁用 y 轴轴指示与标签，避免出现水平线与左下角气泡数值
      axisPointer: { show: false, label: { show: false } },  // 关键：关闭 y 轴指示
    },
    series,
  };
  if (ui?.tooltipPositioner) {
    option.tooltip.position = ui.tooltipPositioner;
  }

  // 应用通用 UI
  return applyUi(
    option,
    {
      ...ui,
      isMain: false, // 量窗
      extraBottomPx, // 底部额外空间（腾给标记）
      xAxisLabelMargin, // 横轴标签 margin（略为增大）
    },
    { dates, freq }
  );
}

/* =============================
 * MACD 窗 option 生成
 * ============================= */

/**
 * 生成 MACD 窗 option：柱（HIST）+ DIF/DEA 线
 */
export function buildMacdOption({ candles, indicators, freq }, ui) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const dates = list.map((d) => d.t);
  const series = [];

  if (inds.MACD_DIF && inds.MACD_DEA && inds.MACD_HIST) {
    // 柱：正/负不同颜色
    series.push({
      id: "MACD_HIST",
      type: "bar",
      name: "MACD_HIST",
      data: inds.MACD_HIST,
      itemStyle: {
        color: (p) =>
          Number(p.data) >= 0
            ? STYLE_PALETTE.bars.macd.positive
            : STYLE_PALETTE.bars.macd.negative,
      },
    });
    // DIF 线
    series.push({
      id: "MACD_DIF",
      type: "line",
      name: "DIF",
      data: inds.MACD_DIF,
      showSymbol: false,
      lineStyle: { color: "#ee6666", width: 1 },
      itemStyle: { color: "#ee6666" },
      color: "#ee6666",
    });
    // DEA 线
    series.push({
      id: "MACD_DEA",
      type: "line",
      name: "DEA",
      data: inds.MACD_DEA,
      showSymbol: false,
      lineStyle: { color: "#5470c6", width: 1 },
      itemStyle: { color: "#5470c6" },
      color: "#5470c6",
    });
  }

  // option（含 tooltip 恢复）
  const option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      appendToBody: false,
      confine: true,
      formatter: (params) => {
        if (!Array.isArray(params) || !params.length) return "";
        const rawLabel = params[0].axisValue || params[0].axisValueLabel || "";
        const timeLabel = fmtTimeByFreq(freq, rawLabel);
        const rows = [`<div style="margin-bottom:4px;">${timeLabel}</div>`];
        for (const p of params) {
          const val = Array.isArray(p.value)
            ? p.value[p.value.length - 1]
            : p.value;
          if ((p.seriesType || "").toLowerCase() === "bar") {
            const color =
              Number(val) >= 0
                ? STYLE_PALETTE.bars.macd.positive
                : STYLE_PALETTE.bars.macd.negative;
            rows.push(
              `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:${color};"></span>${
                p.seriesName
              }: ${fmt3(val)}</div>`
            );
          } else {
            rows.push(
              `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:${
                p.color
              };"></span>${p.seriesName}: ${fmt3(val)}</div>`
            );
          }
        }
        return rows.join("");
      },
      className: "ct-fixed-tooltip",
      borderWidth: 0,
      backgroundColor: "rgba(20,20,20,0.85)",
      textStyle: { color: theme.textColor, fontSize: 12, align: "left" },
    },
  };

  option.xAxis = { type: "category", data: dates };
  option.yAxis = { scale: true };
  option.series = series;
  if (ui?.tooltipPositioner) {
    option.tooltip.position = ui.tooltipPositioner;
  }

  // 应用通用 UI
  return applyUi(
    option,
    {
      ...ui,
      isMain: false, // 技术窗
    },
    { dates, freq }
  );
}

/* =============================
 * KDJ/RSI 窗 option 生成
 * ============================= */

/**
 * 生成 KDJ/RSI 窗 option（同一容器复用）
 */
export function buildKdjOrRsiOption(
  { candles, indicators, freq, useKDJ = false, useRSI = false },
  ui
) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const dates = list.map((d) => d.t);
  const series = [];

  // KDJ 三线
  if (useKDJ) {
    if (inds.KDJ_K && inds.KDJ_D && inds.KDJ_J) {
      series.push({
        id: "KDJ_K",
        type: "line",
        name: "K",
        data: inds.KDJ_K,
        showSymbol: false,
        lineStyle: { color: "#ee6666", width: 1 },
        itemStyle: { color: "#ee6666" },
        color: "#ee6666",
      });
      series.push({
        id: "KDJ_D",
        type: "line",
        name: "D",
        data: inds.KDJ_D,
        showSymbol: false,
        lineStyle: { color: "#fac858", width: 1 },
        itemStyle: { color: "#fac858" },
        color: "#fac858",
      });
      series.push({
        id: "KDJ_J",
        type: "line",
        name: "J",
        data: inds.KDJ_J,
        showSymbol: false,
        lineStyle: { color: "#5470c6", width: 1 },
        itemStyle: { color: "#5470c6" },
        color: "#5470c6",
      });
    }
  } else if (useRSI) {
    // RSI 单线
    if (inds.RSI) {
      series.push({
        id: "RSI",
        type: "line",
        name: "RSI",
        data: inds.RSI,
        showSymbol: false,
        lineStyle: { color: "#ee6666", width: 1 },
        itemStyle: { color: "#ee6666" },
        color: "#ee6666",
      });
    }
  }

  // option（含 tooltip 恢复）
  const option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      appendToBody: false,
      confine: true,
      formatter: (params) => {
        if (!Array.isArray(params) || !params.length) return "";
        const rawLabel = params[0].axisValue || params[0].axisValueLabel || "";
        const timeLabel = fmtTimeByFreq(freq, rawLabel);
        const rows = [`<div style="margin-bottom:4px;">${timeLabel}</div>`];
        for (const p of params) {
          const val = Array.isArray(p.value)
            ? p.value[p.value.length - 1]
            : p.value;
          rows.push(
            `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:${
              p.color
            };"></span>${p.seriesName || ""}: ${fmt3(val)}</div>`
          );
        }
        return rows.join("");
      },
      className: "ct-fixed-tooltip",
      borderWidth: 0,
      backgroundColor: "rgba(20,20,20,0.85)",
      textStyle: { color: theme.textColor, fontSize: 12, align: "left" },
    },
  };

  option.xAxis = { type: "category", data: dates };
  option.yAxis = { scale: true };
  option.series = series;
  if (ui?.tooltipPositioner) {
    option.tooltip.position = ui.tooltipPositioner;
  }

  // 应用通用 UI（含轴与网格颜色、防止变亮）
  return applyUi(
    option,
    {
      ...ui,
      isMain: false, // 技术窗
    },
    { dates, freq }
  );
}
