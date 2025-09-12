// src/charts/options.js
// ==============================
// 说明：ECharts 选项生成器（前端纯函数层）
// - 提供主图/量窗/指标窗的 option 组装
// - 内置多窗体缩放同步（zoomSync）与固定 tooltip 定位器
// - 已实现：
//   1) 主图 HL 柱图支持“去包含合并后仅绘单根柱”渲染（基于 reducedBars）
//   2) 量窗放/缩量标记支持开关（markerPump.enabled / markerDump.enabled）
//   3) 量窗底部留白/坐标轴标签间距随标记开关动态调整（无标记则不留白）
//   4) 统一 dataZoom 与 x/y/tooltip 风格
//   5) 主图/量窗/指标窗 tooltip 与配色对齐显示层规范
// - 本文件为全量输出并尽可能逐行注���以便维护

// 引入主题与常量（颜色/默认参数）
import { getChartTheme } from "@/charts/theme";
import { STYLE_PALETTE, DEFAULT_VOL_SETTINGS } from "@/constants";

// 固定 tooltip 显示侧的全局状态（left/right）
let GLOBAL_TIP_SIDE = "left";

/**
 * 创建一个固定位置的 tooltip 定位器（主/量/指标复用）
 * - defaultSide：初始侧（left/right）
 * - getOffset：可选函数返回 {x,y} 偏移
 */
export function createFixedTooltipPositioner(defaultSide = "left", getOffset) {
  // 如果全局未设置过侧边，则采用传入默认值
  if (GLOBAL_TIP_SIDE !== "left" && GLOBAL_TIP_SIDE !== "right") {
    GLOBAL_TIP_SIDE = defaultSide === "right" ? "right" : "left";
  }
  // 返回实际供 ECharts 调用的定位函数
  return function (pos, _params, dom, _rect, size) {
    // 读取宿主元素与宽度
    const host = dom && dom.parentElement ? dom.parentElement : null;
    const hostRect = host ? host.getBoundingClientRect() : { width: 800 };
    // 当前 tooltip 内容宽度（估算）
    const tipW = (size && size.contentSize && size.contentSize[0]) || 260;
    const margin = 8;
    const x = Array.isArray(pos) ? pos[0] : 0;
    // 判断是否靠近左右边界，决定显示侧
    const nearLeft = x <= tipW + margin + 12;
    const nearRight = hostRect.width - x <= tipW + margin + 12;
    if (nearLeft) GLOBAL_TIP_SIDE = "right";
    else if (nearRight) GLOBAL_TIP_SIDE = "left";

    // 计算固定位置（左上 or 右上）
    const baseX =
      GLOBAL_TIP_SIDE === "left"
        ? margin
        : Math.max(margin, hostRect.width - tipW - margin);
    const baseY = 8;

    // 可选偏移
    let off = { x: 0, y: 0 };
    try {
      const t = typeof getOffset === "function" ? getOffset() : null;
      if (t && typeof t.x === "number" && typeof t.y === "number") off = t;
    } catch {}

    // 返回绝对位置（相对画布）
    return [baseX + (off.x || 0), baseY + (off.y || 0)];
  };
}

/**
 * 多窗体缩放同步（主/量/指标）
 * - attach：图表加入同步组
 * - detach：图表移除同步组
 * - setRangeByIndex：设置统一范围（索引制）
 */
export const zoomSync = (function () {
  // 存储已注册的图表，key → { chart, getLen }
  const charts = new Map();
  // 当前统一范围（索引）
  let currentRange = null;
  // 正在广播标志，避免递归触发 dataZoom
  let inProgress = false;

  // 工具：将索引范围转换为 dataZoom 需要的百分比范围
  function idxToPercent(startIdx, endIdx, len) {
    const n = Math.max(1, Number(len || 0));
    const maxIdx = n - 1;
    const s = Math.max(0, Math.min(maxIdx, Number(startIdx || 0)));
    const e = Math.max(
      0,
      Math.min(maxIdx, Number(endIdx != null ? endIdx : maxIdx))
    );
    return { start: (s / maxIdx) * 100, end: (e / maxIdx) * 100 };
  }

  // 广播给其它图表
  function broadcastByIndex(startIdx, endIdx, sourceKey) {
    inProgress = true;
    try {
      charts.forEach((entry, key) => {
        if (key === sourceKey) return; // 源图不广播给自己
        const len = entry.getLen ? Number(entry.getLen()) : 0;
        if (!len || !entry.chart) return;
        const { start, end } = idxToPercent(startIdx, endIdx, len);
        try {
          entry.chart.dispatchAction({ type: "dataZoom", start, end });
        } catch {}
      });
    } finally {
      inProgress = false;
    }
  }

  // 设置统一索引范围，并广播
  function setRangeByIndex(startIdx, endIdx, sourceKey) {
    currentRange = {
      startIdx: Number(startIdx || 0),
      endIdx: Number(endIdx || 0),
    };
    broadcastByIndex(
      currentRange.startIdx,
      currentRange.endIdx,
      sourceKey || null
    );
  }

  // 将图表加入同步组
  function attach(key, chart, getLen) {
    if (!key || !chart || typeof chart.dispatchAction !== "function")
      return () => {};
    charts.set(key, { chart, getLen });

    // 监听该图表的 dataZoom，并转换为统一索引广播给其它图
    const onZoom = (params) => {
      if (inProgress) return; // 广播中，避免递归
      try {
        const len = typeof getLen === "function" ? Number(getLen()) : 0;
        if (!len) return;
        const info =
          (params && params.batch && params.batch[0]) || params || {};
        let sIdx, eIdx;
        if (
          typeof info.startValue !== "undefined" &&
          typeof info.endValue !== "undefined"
        ) {
          sIdx = Number(info.startValue);
          eIdx = Number(info.endValue);
        } else if (
          typeof info.start === "number" &&
          typeof info.end === "number"
        ) {
          const maxIdx = len - 1;
          sIdx = Math.round((info.start / 100) * maxIdx);
          eIdx = Math.round((info.end / 100) * maxIdx);
        }
        if (!Number.isFinite(sIdx) || !Number.isFinite(eIdx)) return;
        const maxIdx = len - 1;
        sIdx = Math.max(0, Math.min(maxIdx, sIdx));
        eIdx = Math.max(0, Math.min(maxIdx, eIdx));
        if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx]; // 保证 s<=e
        if (
          !currentRange ||
          currentRange.startIdx !== sIdx ||
          currentRange.endIdx !== eIdx
        ) {
          setRangeByIndex(sIdx, eIdx, key);
        }
      } catch {}
    };

    // 注册监听
    chart.on("dataZoom", onZoom);

    // 若已有统一范围，则新加入的图表立即应用一次
    if (currentRange && typeof getLen === "function") {
      const len = Number(getLen()) || 0;
      if (len) {
        const { start, end } = idxToPercent(
          currentRange.startIdx,
          currentRange.endIdx,
          len
        );
        try {
          chart.dispatchAction({ type: "dataZoom", start, end });
        } catch {}
      }
    }

    // 返回解绑函数
    return () => {
      try {
        chart.off("dataZoom", onZoom);
      } catch {}
      charts.delete(key);
    };
  }

  // 将图表移出同步组
  function detach(key) {
    const entry = charts.get(key);
    if (entry && entry.chart) {
      try {
        entry.chart.off("dataZoom");
      } catch {}
    }
    charts.delete(key);
  }

  return { attach, detach, setRangeByIndex };
})();

// 统一布局常量（画布内顶栏/边距/slider 等）
const LAYOUT = {
  TOP_TEXT_PX: 28, // 画布内顶栏高度（各窗统一）
  LEFT_MARGIN_PX: 64, // 左边距，容纳 y 轴刻度
  RIGHT_MARGIN_PX: 10, // 右边距
  SLIDER_HEIGHT_PX: 26, // 主窗 slider 高度
  MAIN_AXIS_LABEL_SPACE_PX: 30, // 主窗 x 轴标签与 slider 间距
  MAIN_BOTTOM_EXTRA_PX: 2, // 主窗底部少量余白
};

// 常用小工具
function asArray(x) {
  return Array.isArray(x) ? x : [];
} // 保证数组
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
} // 保证对象
function fmt3(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(3) : "";
} // 数值格式化
function isMinuteFreq(freq) {
  return typeof freq === "string" && /m$/.test(freq);
} // 是否分钟频率
function pad2(n) {
  return String(n).padStart(2, "0");
} // 两位补零

// 将 ISO 时间按频率格式化（分钟含时分，日/周/月仅日期）
function fmtTimeByFreq(freq, isoVal) {
  try {
    const d = new Date(isoVal);
    if (Number.isNaN(d.getTime())) return String(isoVal || "");
    const Y = d.getFullYear(),
      M = pad2(d.getMonth() + 1),
      D = pad2(d.getDate());
    const h = pad2(d.getHours()),
      m = pad2(d.getMinutes());
    return isMinuteFreq(freq) ? `${Y}-${M}-${D} ${h}:${m}` : `${Y}-${M}-${D}`;
  } catch {
    return String(isoVal || "");
  }
}

// x 轴标签格式化器工厂
function makeAxisLabelFormatter(freq) {
  return (val) => fmtTimeByFreq(freq, val);
}

// 数量单位换算（量：手，额：元）
// - 返回 {div, lab}，显示时用 val/div + lab
function pickUnitDivider(maxAbs, isAmount) {
  if (maxAbs >= 1e8) return { div: 1e8, lab: "亿" + (isAmount ? "元" : "") };
  if (maxAbs >= 1e4) return { div: 1e4, lab: "万" + (isAmount ? "元" : "") };
  return { div: 1, lab: isAmount ? "元" : "" };
}

// 单位化格式化输出
function fmtUnit(val, unit) {
  const n = Number(val);
  if (!Number.isFinite(n)) return "-";
  const x = n / (unit?.div || 1);
  const digits = Math.abs(x) >= 100 ? 0 : Math.abs(x) >= 10 ? 1 : 2;
  return x.toFixed(digits) + (unit?.lab || "");
}

/**
 * 统一将 UI（grid/x/y/tooltip/dataZoom）应用到 option
 * - ui.isMain：主窗；否则为量窗/指标窗
 * - ui.extraBottomPx：非主窗底部留白（例如量窗标记需要）
 * - ui.xAxisLabelMargin：x 轴标签与底部间距（非主窗可能需要加大）
 */
function applyUi(option, ui, { dates, freq }) {
  const theme = getChartTheme();

  // 水平边距与顶部
  const leftPx = ui?.leftPx ?? LAYOUT.LEFT_MARGIN_PX;
  const rightPx = ui?.rightPx ?? LAYOUT.RIGHT_MARGIN_PX;
  const isMain = !!ui?.isMain;
  const gridTop = 0;

  // 非主窗动态底部留白（量窗标记开启时可能有额外空间）
  const nonMainExtra = ui?.extraBottomPx ? Number(ui.extraBottomPx) : 0;

  // 主窗底部 = slider + 轴标签空间 + 微小余白；否则用动态 extra
  const gridBottom = isMain
    ? (ui?.sliderHeightPx ?? LAYOUT.SLIDER_HEIGHT_PX) +
      (ui?.mainAxisLabelSpacePx ?? LAYOUT.MAIN_AXIS_LABEL_SPACE_PX) +
      (ui?.mainBottomExtraPx ?? LAYOUT.MAIN_BOTTOM_EXTRA_PX)
    : nonMainExtra;

  // 应用 grid
  option.grid = {
    left: leftPx,
    right: rightPx,
    top: gridTop,
    bottom: gridBottom,
    containLabel: false,
  };

  // x 轴：统一 boundaryGap、对齐、颜色与时间格式
  const len = Array.isArray(dates) ? dates.length : 0;
  option.xAxis = Object.assign({}, option.xAxis || {}, {
    type: "category",
    data: option.xAxis?.data || dates || [],
    boundaryGap: ["0%", "0%"],
    axisTick: Object.assign({}, option.xAxis?.axisTick || {}, {
      alignWithLabel: true,
    }),
    axisLabel: Object.assign({}, option.xAxis?.axisLabel || {}, {
      color: theme.axisLabelColor,
      margin: ui?.xAxisLabelMargin ?? 6, // 非主窗可能需要更大的 margin（量窗标记）
      formatter: makeAxisLabelFormatter(freq),
    }),
    axisLine: { lineStyle: { color: theme.axisLineColor } },
    min: 0,
    max: len ? len - 1 : undefined,
  });

  // y 轴：统一颜色与网格
  option.yAxis = Object.assign({}, option.yAxis || {}, {
    scale: true,
    axisLabel: Object.assign({}, option.yAxis?.axisLabel || {}, {
      color: theme.axisLabelColor,
      margin: 6,
    }),
    axisLine: { lineStyle: { color: theme.axisLineColor } },
    splitLine: { lineStyle: { color: theme.gridLineColor } },
  });

  // 通用 tooltip ��线（位置器由上层注入）
  const baseTooltip = {
    trigger: "axis",
    appendToBody: false,
    enterable: true,
    confine: true,
    className: ui?.tooltipClass || "ct-fixed-tooltip",
    backgroundColor: "rgba(20,20,20,0.85)",
    borderWidth: 0,
    textStyle: { color: theme.textColor, fontSize: 12, align: "left" },
    axisPointer: { type: "line" },
  };
  option.tooltip = Object.assign(
    {},
    baseTooltip,
    option.tooltip || {},
    ui?.tooltipPositioner ? { position: ui.tooltipPositioner } : {}
  );

  // dataZoom：主窗包含 slider，其它窗仅 inside
  const lenRange = len ? { startValue: 0, endValue: len - 1 } : {};
  option.dataZoom = isMain
    ? [
        { type: "inside", ...lenRange },
        {
          type: "slider",
          height: ui?.sliderHeightPx ?? LAYOUT.SLIDER_HEIGHT_PX,
          bottom: 0,
          ...lenRange,
        },
      ]
    : [{ type: "inside" }];

  return option;
}

/**
 * 主图 tooltip 格式化函数
 * - 为与“带圆点的行”左边对齐，在 OHLC 行前使用一个 8px 的透明占位圆点（span）
 * - 支持 K 线/HL 柱/分时 Close 的统一样式
 */
function makeMainTooltipFormatter({
  theme,
  chartType,
  freq,
  candles,
  maConfigs,
  adjust,
}) {
  const list = asArray(candles);
  return function (params) {
    if (!Array.isArray(params) || !params.length) return "";
    // 时间标签（含复权标识）
    const rawLabel = params[0].axisValue || params[0].axisValueLabel || "";
    const timeLabel = fmtTimeByFreq(freq, rawLabel);
    const adjLabel = { qfq: "前复权", hfq: "后复权" }[adjust] || "";
    const rows = [
      `<div style="margin-bottom:4px;">${timeLabel} ${adjLabel}</div>`,
    ];

    // 当前索引与蜡烛
    const idx = params[0].dataIndex ?? 0;
    const k = list[idx] || {};

    if (chartType === "kline") {
      // K 线 or HL 柱
      const kSeries = params.find(
        (p) => p.seriesType === "candlestick" || p.seriesName === "H-L Bar"
      );
      const kLabel =
        kSeries && kSeries.seriesName === "H-L Bar" ? "H-L柱" : "K线";
      // 行标题（带占位）
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>${kLabel}</div>`
      );
      // OHLC 四行（带透明占位 8px 以左对齐）
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
      // 分时 Close 行（带圆点）
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:#03a9f4;"></span>Close: ${fmt3(
          k.c
        )}</div>`
      );
    }

    // 若有 MA 叠加线，统一展示（带圆点）
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

/**
 * 量窗 tooltip 格式化函数
 * - 主行显示“量/额 + 放/缩量状态”，带圆点（涨跌色）
 * - MAVOL 行带圆点（颜色与折线一致）
 * - 换手率行与“另一指标”行取消圆点，但保留透明占位，保持左对齐
 */
function makeVolumeTooltipFormatter({
  candles,
  freq,
  unitInfo,
  baseName,
  mavolMap,
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

    // 主指标行（量/额）圆点颜色：涨红/跌绿
    const isUp = Number(k.c) >= Number(k.o);
    const baseDotColor = isUp
      ? STYLE_PALETTE.bars.volume.up
      : STYLE_PALETTE.bars.volume.down;
    const bar = params.find(
      (x) => (x.seriesType || "").toLowerCase() === "bar"
    );
    const baseRawVal = Array.isArray(bar?.value)
      ? bar.value[bar.value.length - 1]
      : bar?.value;
    const baseValText = fmtUnit(baseRawVal, unitInfo);

    // 放缩量状态（仅为提示标签）
    const hasPump = params.some((pp) => pp.seriesName === "放量标记");
    const hasDump = params.some((pp) => pp.seriesName === "缩量标记");
    const statusTag = hasPump ? "（放）" : hasDump ? "（缩）" : "";

    const periods = Object.keys(mavolMap || {})
      .map((x) => +x)
      .sort((a, b) => a - b);
    const rows = [];
    rows.push(`<div style="margin-bottom:4px;">${timeLabel}</div>`);
    rows.push(
      `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:${baseDotColor};"></span>${
        isVolMode ? "成交量" : "成交额"
      }: ${baseValText}${statusTag}</div>`
    );

    // MAVOL 行（带圆点，颜色取线的颜色）
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

    // 换手率（取消圆点，保留占位）
    if (typeof k.tr === "number") {
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>换手率: ${fmt3(
          k.tr
        )}%</div>`
      );
    }

    // “另一指标”（量模式下展示额；额模式下展示量）取消圆点，保留占位
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

/**
 * 主图 option 组装
 * - 支持：K 线/HL 柱/分时 Close
 * - 新增：当 subType === 'bar' 且传入 reducedBars 时，仅在 anchor_idx 位置绘制合并后的 HL 柱
 */
export function buildMainChartOption(
  {
    candles, // 源蜡烛序列（t,o,h,l,c,v,a,tr）
    indicators, // 指标对象
    chartType, // 'kline' | 其它（分时）
    maConfigs, // MA 配置
    freq, // 频率（x 轴格式）
    klineStyle, // K 线样式（含 subType/barPercent/colors）
    adjust, // 复权标识（仅用于 tooltip 展示）
    reducedBars, // 可选：去包含合并后的复合K（[{idx_start,idx_end,hi,lo,dir,anchor_idx}...]）
  },
  ui // UI 参数（tooltipPositioner 等）
) {
  // 读取主题颜色
  const theme = getChartTheme();
  // 筛选数据/指标
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  // x 轴时间序列
  const dates = list.map((d) => d.t);
  // series 容器
  const series = [];

  if (chartType === "kline") {
    // K 线或 HL 柱模式
    const ks = klineStyle || {};
    const barPercent = Number.isFinite(+ks.barPercent) ? +ks.barPercent : 100;
    // 颜色：上涨红、下跌绿（按你的主题映射）
    const upColor = ks.upColor || theme.candle.rise;
    const downColor = ks.downColor || theme.candle.fall;

    if (ks.subType === "bar") {
      // HL 柱图
      if (Array.isArray(reducedBars) && reducedBars.length) {
        // 使用合并后的“单根 HL”渲染：只在 anchor_idx 位置绘制（其它索引为 null）
        const n = dates.length;
        const baseLow = new Array(n).fill(null); // 栈底（low）
        const hlSpan = new Array(n).fill(null); // 高度（hi - lo）
        const upIndexSet = new Set(); // 上涨复合K的锚点集合（用于着色）

        // 将 reducedBars 映射到 anchor_idx 索引位置
        for (const rb of reducedBars) {
          const idx = Math.max(
            0,
            Math.min(n - 1, Number(rb?.anchor_idx ?? rb?.idx_end ?? 0))
          );
          const hi = Number(rb?.hi);
          const lo = Number(rb?.lo);
          if (!Number.isFinite(hi) || !Number.isFinite(lo) || hi < lo) continue;
          baseLow[idx] = lo;
          hlSpan[idx] = hi - lo;
          if (Number(rb?.dir || 0) > 0) upIndexSet.add(idx);
        }

        // 基线（透明） + HL 柱（彩色）堆叠
        series.push({
          name: "L-Base",
          type: "bar",
          stack: "hl_stack",
          itemStyle: { color: "transparent" },
          emphasis: { itemStyle: { color: "transparent" } },
          data: baseLow,
          ...(barPercent && barPercent !== 100
            ? { barWidth: `${barPercent}%` }
            : {}),
        });
        series.push({
          name: "H-L Bar",
          type: "bar",
          stack: "hl_stack",
          itemStyle: {
            color: (p) => (upIndexSet.has(p.dataIndex) ? upColor : downColor),
          },
          data: hlSpan,
          ...(barPercent && barPercent !== 100
            ? { barWidth: `${barPercent}%` }
            : {}),
        });
      } else {
        // 回退：逐根 HL 柱（原始行为）
        series.push({
          name: "L-Base",
          type: "bar",
          stack: "hl_stack",
          itemStyle: { color: "transparent" },
          emphasis: { itemStyle: { color: "transparent" } },
          data: list.map((d) => d.l),
          ...(barPercent && barPercent !== 100
            ? { barWidth: `${barPercent}%` }
            : {}),
        });
        series.push({
          name: "H-L Bar",
          type: "bar",
          stack: "hl_stack",
          itemStyle: {
            color: (p) => {
              const k = list[p.dataIndex];
              return Number(k.c) >= Number(k.o) ? upColor : downColor;
            },
          },
          data: list.map((d) => d.h - d.l),
          ...(barPercent && barPercent !== 100
            ? { barWidth: `${barPercent}%` }
            : {}),
        });
      }
    } else {
      // 正常 K 线（candlestick）
      // 注意：ECharts candlestick 数据列顺序是 [open, close, low, high]
      const ohlc = list.map((d) => [d.o, d.c, d.l, d.h]);
      const klineSeries = {
        type: "candlestick",
        name: "K",
        data: ohlc,
        itemStyle: {
          color: upColor,
          color0: "transparent",
          borderColor: upColor,
          borderColor0: downColor,
          borderWidth: 1.2,
        },
      };
      if (barPercent < 100) klineSeries.barWidth = `${barPercent}%`;
      series.push(klineSeries);
    }

    // 叠加 MA 线（启用才绘制）
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
    // 分时线（Close）
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

  // 组装 option 并应用 UI
  const option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    tooltip: {
      formatter: makeMainTooltipFormatter({
        theme,
        chartType,
        freq,
        candles: list,
        maConfigs,
        adjust,
      }),
    },
    xAxis: { type: "category", data: dates },
    yAxis: { scale: true },
    series,
  };

  // 返回应用 UI 后的 option（主窗）
  return applyUi(
    option,
    {
      ...ui,
      isMain: true,
      tooltipPositioner: createFixedTooltipPositioner("left"),
    },
    { dates, freq }
  );
}

/**
 * 量窗 option 组装
 * - 支持量/额切换、MAVOL、多标记（放/缩量）
 * - 关键点：
 *   * 标记开关：markerPump.enabled / markerDump.enabled（默认 true）
 *   * 动态底部留白：有任一标记显示时才为 marker 预留底部空间，否则不留
 *   * x 轴标签 margin：随标记留白动态调整
 */
export function buildVolumeOption(
  { candles, indicators, freq, volCfg, volEnv },
  ui
) {
  // 读取主题
  const theme = getChartTheme();

  // 输入数据与指标
  const list = asArray(candles);
  const inds = asIndicators(indicators);

  // x 轴时间
  const dates = list.map((d) => d.t);

  // 模式：量 or 额
  const baseMode = volCfg && volCfg.mode === "amount" ? "amount" : "vol";
  const baseName = baseMode === "amount" ? "AMOUNT" : "VOL";

  // 主序列（量 or 额）
  const baseRaw =
    baseMode === "amount"
      ? list.map((d) => (typeof d.a === "number" ? d.a : null))
      : inds.VOLUME || list.map((d) => (typeof d.v === "number" ? d.v : null));

  // 单位估算
  const baseMaxAbs = baseRaw.reduce(
    (m, x) => (Number.isFinite(+x) ? Math.max(m, Math.abs(+x)) : m),
    0
  );
  const unitInfo = pickUnitDivider(baseMaxAbs, baseMode === "amount");

  // series 容器
  const series = [];

  // 柱体样式与颜色
  const vb = volCfg?.volBar || {};
  const barPercent = Number.isFinite(+vb.barPercent)
    ? Math.max(10, Math.min(100, Math.round(+vb.barPercent)))
    : 100;
  const upColor = vb.upColor || STYLE_PALETTE.bars.volume.up;
  const downColor = vb.downColor || STYLE_PALETTE.bars.volume.down;

  // 有效数据（null 过滤交给 ECharts）
  const baseScaled = baseRaw.map((v) => (Number.isFinite(+v) ? +v : null));

  // 主柱（量 or 额）
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

  // MAVOL 配置解析
  const namePrefixCN = baseMode === "amount" ? "额MA" : "量MA";
  const mstyles = volCfg?.mavolStyles || {};
  const periods = Object.keys(mstyles)
    .map((k) => mstyles[k])
    .filter(
      (s) => s && s.enabled && Number.isFinite(+s.period) && +s.period > 0
    )
    .sort((a, b) => +a.period - +b.period);

  // 简单 MA（SMA）实现
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

  // 生成各周期 MAVOL
  const mavolMap = {};
  for (const st of periods) {
    mavolMap[+st.period] = sma(baseScaled, +st.period);
  }

  // 绘制各条 MAVOL 线
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

  // 估算柱宽用于标记尺寸
  const hostW = Math.max(1, Number(volEnv?.hostWidth || 0));
  const visCount = Math.max(1, Number(volEnv?.visCount || baseScaled.length));
  const approxBarWidthPx =
    hostW > 1 && visCount > 0
      ? Math.max(
          2,
          Math.floor(((hostW * 0.88) / visCount) * (barPercent / 100))
        )
      : 8;
  const MARKER_W_MIN = 6,
    MARKER_W_MAX = 14;
  const markerW = Math.max(
    MARKER_W_MIN,
    Math.min(MARKER_W_MAX, Math.round(approxBarWidthPx))
  );
  const markerH = 10;
  const symbolOffsetBelow = [0, Math.round(markerH * 1.2)];

  // 主基线：启用的最小 MAVOL 周期
  const primPeriod = periods.length ? +periods[0].period : null;
  const primSeries = primPeriod ? mavolMap[primPeriod] : null;

  // 阈值与开关
  const pumpK = Number.isFinite(+volCfg?.markerPump?.threshold)
    ? +volCfg.markerPump.threshold
    : DEFAULT_VOL_SETTINGS.markerPump.threshold;
  const dumpK = Number.isFinite(+volCfg?.markerDump?.threshold)
    ? +volCfg.markerDump.threshold
    : DEFAULT_VOL_SETTINGS.markerDump.threshold;
  const pumpEnabled = (volCfg?.markerPump?.enabled ?? true) === true;
  const dumpEnabled = (volCfg?.markerDump?.enabled ?? true) === true;

  // 标记点集合
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

  // 条件渲染放量标记
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
  // 条件渲染缩量标记
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

  // 动态底部留白与 x 轴标签距离：
  // - 有任一标记显示才预留 markerH 的底部空间，并将 label margin 调大；
  // - 否则不留白，label margin 使用较小值。
  const anyMarkers =
    (pumpEnabled && pumpPts.length > 0) || (dumpEnabled && dumpPts.length > 0);
  const extraBottomPx = anyMarkers ? markerH : 0;
  const xAxisLabelMargin = anyMarkers ? Math.max(12, markerH + 12) : 12;

  // 组装 option
  const option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    tooltip: {
      formatter: makeVolumeTooltipFormatter({
        candles: list,
        freq,
        unitInfo,
        baseName,
        mavolMap,
      }),
    },
    xAxis: { type: "category", data: dates },
    yAxis: {
      min: 0,
      scale: true,
      axisLabel: {
        color: getChartTheme().axisLabelColor,
        margin: 6,
        formatter: (val) => fmtUnit(val, unitInfo),
      },
      axisLine: { lineStyle: { color: getChartTheme().axisLineColor } },
      splitLine: { lineStyle: { color: getChartTheme().gridLineColor } },
    },
    series,
  };

  // 应用 UI（非主窗）
  return applyUi(
    option,
    {
      ...ui,
      isMain: false,
      tooltipPositioner: createFixedTooltipPositioner("left"),
      extraBottomPx, // 动态底部留白
      xAxisLabelMargin, // 动态 x 轴标签间距
    },
    { dates, freq }
  );
}

/**
 * MACD 窗 option 组装
 * - 柱（HIST）+ 线（DIF/DEA）
 */
export function buildMacdOption({ candles, indicators, freq }, ui) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const dates = list.map((d) => d.t);
  const series = [];

  if (inds.MACD_DIF && inds.MACD_DEA && inds.MACD_HIST) {
    let lineStyleIndex = 0;
    // 柱：正负不同颜色
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
    // 线：DIF
    const difStyle =
      STYLE_PALETTE.lines[lineStyleIndex++ % STYLE_PALETTE.lines.length];
    series.push({
      id: "MACD_DIF",
      type: "line",
      name: "DIF",
      data: inds.MACD_DIF,
      showSymbol: false,
      lineStyle: difStyle,
      itemStyle: { color: difStyle.color },
      color: difStyle.color,
    });
    // 线：DEA
    const deaStyle =
      STYLE_PALETTE.lines[lineStyleIndex++ % STYLE_PALETTE.lines.length];
    series.push({
      id: "MACD_DEA",
      type: "line",
      name: "DEA",
      data: inds.MACD_DEA,
      showSymbol: false,
      lineStyle: deaStyle,
      itemStyle: { color: deaStyle.color },
      color: deaStyle.color,
    });
  }

  const option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    tooltip: {
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
    },
  };

  option.xAxis = { type: "category", data: dates };
  option.yAxis = { scale: true };
  option.series = series;

  return applyUi(
    option,
    {
      ...ui,
      isMain: false,
      tooltipPositioner: createFixedTooltipPositioner("left"),
    },
    { dates, freq }
  );
}

/**
 * KDJ/RSI 窗 option 组装
 * - KDJ：K/D/J 三线
 * - RSI：一条线
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
  let lineStyleIndex = 0;

  if (useKDJ) {
    // KDJ：三线
    const K = inds.KDJ_K,
      D = inds.KDJ_D,
      J = inds.KDJ_J;
    if (K && D && J) {
      const stK =
        STYLE_PALETTE.lines[lineStyleIndex++ % STYLE_PALETTE.lines.length];
      const stD =
        STYLE_PALETTE.lines[lineStyleIndex++ % STYLE_PALETTE.lines.length];
      const stJ =
        STYLE_PALETTE.lines[lineStyleIndex++ % STYLE_PALETTE.lines.length];
      series.push({
        id: "KDJ_K",
        type: "line",
        name: "K",
        data: K,
        showSymbol: false,
        lineStyle: stK,
        itemStyle: { color: stK.color },
        color: stK.color,
      });
      series.push({
        id: "KDJ_D",
        type: "line",
        name: "D",
        data: D,
        showSymbol: false,
        lineStyle: stD,
        itemStyle: { color: stD.color },
        color: stD.color,
      });
      series.push({
        id: "KDJ_J",
        type: "line",
        name: "J",
        data: J,
        showSymbol: false,
        lineStyle: stJ,
        itemStyle: { color: stJ.color },
        color: stJ.color,
      });
    }
  } else if (useRSI) {
    // RSI：单线
    const R = inds.RSI;
    if (R) {
      const st =
        STYLE_PALETTE.lines[lineStyleIndex++ % STYLE_PALETTE.lines.length];
      series.push({
        id: "RSI",
        type: "line",
        name: "RSI",
        data: R,
        showSymbol: false,
        lineStyle: st,
        itemStyle: { color: st.color },
        color: st.color,
      });
    }
  }

  const option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    tooltip: {
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
    },
  };

  option.xAxis = { type: "category", data: dates };
  option.yAxis = { scale: true };
  option.series = series;

  return applyUi(
    option,
    {
      ...ui,
      isMain: false,
      tooltipPositioner: createFixedTooltipPositioner("left"),
    },
    { dates, freq }
  );
}
