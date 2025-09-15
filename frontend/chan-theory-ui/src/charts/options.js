// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options.js
// ==============================
// 说明：ECharts 选项生成（主/量/指标）。
// 本版改动（与前文一致、补全中断部分）：
// 1) 量窗“放/缩量标记”尺寸控制由 constants/index.js 的 DEFAULT_VOL_MARKER_SIZE 提供，去除写死常量；
// 2) HL 柱模式下且当前位置为“去包含后承载点”时，主窗浮窗在 HL柱 行之后、O 之前追加两行：
//    G（处理完包含关系后的高点价格 reducedBar.hi）/ D（处理完包含关系后的低点价格 reducedBar.lo）。
// 其它渲染逻辑保持不变。
// ==============================

import { getChartTheme } from "@/charts/theme"; // 主题读取
import {
  STYLE_PALETTE,
  DEFAULT_VOL_SETTINGS,
  DEFAULT_VOL_MARKER_SIZE,
} from "@/constants"; // 集中默认

// 全局 tooltip 侧边（固定定位）
let GLOBAL_TIP_SIDE = "left";

/**
 * 创建固定 tooltip 定位器（主/量/指标复用）
 */
export function createFixedTooltipPositioner(defaultSide = "left", getOffset) {
  if (GLOBAL_TIP_SIDE !== "left" && GLOBAL_TIP_SIDE !== "right") {
    GLOBAL_TIP_SIDE = defaultSide === "right" ? "right" : "left";
  }
  return function (pos, _params, dom, _rect, size) {
    const host = dom && dom.parentElement ? dom.parentElement : null;
    const hostRect = host ? host.getBoundingClientRect() : { width: 800 };
    const tipW = (size && size.contentSize && size.contentSize[0]) || 260;
    const margin = 8;
    const x = Array.isArray(pos) ? pos[0] : 0;
    const nearLeft = x <= tipW + margin + 12;
    const nearRight = hostRect.width - x <= tipW + margin + 12;
    if (nearLeft) GLOBAL_TIP_SIDE = "right";
    else if (nearRight) GLOBAL_TIP_SIDE = "left";
    const baseX =
      GLOBAL_TIP_SIDE === "left"
        ? margin
        : Math.max(margin, hostRect.width - tipW - margin);
    const baseY = 8;
    let off = { x: 0, y: 0 };
    try {
      const t = typeof getOffset === "function" ? getOffset() : null;
      if (t && typeof t.x === "number" && typeof t.y === "number") off = t;
    } catch {}
    return [baseX + (off.x || 0), baseY + (off.y || 0)];
  };
}

/**
 * 多窗体缩放同步（主/量/指标）
 */
export const zoomSync = (function () {
  const charts = new Map();
  let currentRange = null;
  let inProgress = false;

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

  function broadcastByIndex(startIdx, endIdx, sourceKey) {
    inProgress = true;
    try {
      charts.forEach((entry, key) => {
        if (key === sourceKey) return;
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

  function attach(key, chart, getLen) {
    if (!key || !chart || typeof chart.dispatchAction !== "function")
      return () => {};
    charts.set(key, { chart, getLen });

    const onZoom = (params) => {
      if (inProgress) return;
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
        if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];
        if (
          !currentRange ||
          currentRange.startIdx !== sIdx ||
          currentRange.endIdx !== eIdx
        ) {
          setRangeByIndex(sIdx, eIdx, key);
        }
      } catch {}
    };

    chart.on("dataZoom", onZoom);

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

    return () => {
      try {
        chart.off("dataZoom", onZoom);
      } catch {}
      charts.delete(key);
    };
  }

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

// 统一布局常量
const LAYOUT = {
  TOP_TEXT_PX: 28,
  LEFT_MARGIN_PX: 64,
  RIGHT_MARGIN_PX: 10,
  SLIDER_HEIGHT_PX: 26,
  MAIN_AXIS_LABEL_SPACE_PX: 30,
  MAIN_BOTTOM_EXTRA_PX: 2,
};

// 小工具
function asArray(x) {
  return Array.isArray(x) ? x : [];
}
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}
function fmt3(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(3) : "";
}
function isMinuteFreq(freq) {
  return typeof freq === "string" && /m$/.test(freq);
}
function pad2(n) {
  return String(n).padStart(2, "0");
}

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

function makeAxisLabelFormatter(freq) {
  return (val) => fmtTimeByFreq(freq, val);
}
function pickUnitDivider(maxAbs, isAmount) {
  if (maxAbs >= 1e8) return { div: 1e8, lab: "亿" + (isAmount ? "元" : "") };
  if (maxAbs >= 1e4) return { div: 1e4, lab: "万" + (isAmount ? "元" : "") };
  return { div: 1, lab: isAmount ? "元" : "" };
}
function fmtUnit(val, unit) {
  const n = Number(val);
  if (!Number.isFinite(n)) return "-";
  const x = n / (unit?.div || 1);
  const digits = Math.abs(x) >= 100 ? 0 : Math.abs(x) >= 10 ? 1 : 2;
  return x.toFixed(digits) + (unit?.lab || "");
}

function applyUi(option, ui, { dates, freq }) {
  const theme = getChartTheme();
  const leftPx = ui?.leftPx ?? LAYOUT.LEFT_MARGIN_PX;
  const rightPx = ui?.rightPx ?? LAYOUT.RIGHT_MARGIN_PX;
  const isMain = !!ui?.isMain;
  const gridTop = 0;
  const nonMainExtra = ui?.extraBottomPx ? Number(ui.extraBottomPx) : 0;
  const gridBottom = isMain
    ? (ui?.sliderHeightPx ?? LAYOUT.SLIDER_HEIGHT_PX) +
      (ui?.mainAxisLabelSpacePx ?? LAYOUT.MAIN_AXIS_LABEL_SPACE_PX) +
      (ui?.mainBottomExtraPx ?? LAYOUT.MAIN_BOTTOM_EXTRA_PX)
    : nonMainExtra;
  option.grid = {
    left: leftPx,
    right: rightPx,
    top: gridTop,
    bottom: gridBottom,
    containLabel: false,
  };
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
      margin: ui?.xAxisLabelMargin ?? 6,
      formatter: makeAxisLabelFormatter(freq),
    }),
    axisLine: { lineStyle: { color: theme.axisLineColor } },
    min: 0,
    max: len ? len - 1 : undefined,
  });
  option.yAxis = Object.assign({}, option.yAxis || {}, {
    scale: true,
    axisLabel: Object.assign({}, option.yAxis?.axisLabel || {}, {
      color: theme.axisLabelColor,
      margin: 6,
    }),
    axisLine: { lineStyle: { color: theme.axisLineColor } },
    splitLine: { lineStyle: { color: theme.gridLineColor } },
  });
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
 * 新增：HL 柱模式下、承载点位置追加 G/D 行（reducedBar.hi / reducedBar.lo）。
 */
function makeMainTooltipFormatter({
  theme,
  chartType,
  freq,
  candles,
  maConfigs,
  adjust,
  klineStyle,
  reducedBars,
  mapOrigToReduced, // 用于确定当前 idx 是否为承载点
}) {
  const list = asArray(candles);
  return function (params) {
    if (!Array.isArray(params) || !params.length) return "";
    const rawLabel = params[0].axisValue || params[0].axisValueLabel || "";
    const timeLabel = fmtTimeByFreq(freq, rawLabel);
    const adjLabel = { qfq: "前复权", hfq: "后复权" }[adjust] || "";
    const rows = [
      `<div style="margin-bottom:4px;">${timeLabel} ${adjLabel}</div>`,
    ];
    const idx = params[0].dataIndex ?? 0;
    const k = list[idx] || {};

    if (chartType === "kline") {
      const ks = klineStyle || {};
      const upColor = ks.upColor || theme.candle.rise;
      const downColor = ks.downColor || theme.candle.fall;
      const kSeries = params.find(
        (p) => p.seriesType === "candlestick" || p.seriesName === "H-L Bar"
      );
      const kLabel =
        kSeries && kSeries.seriesName === "H-L Bar" ? "H-L柱" : "K线";

      // 颜色小点
      let dotColor = "transparent";
      if (
        ks.subType === "bar" &&
        Array.isArray(reducedBars) &&
        reducedBars.length
      ) {
        const mapEntry = mapOrigToReduced && mapOrigToReduced[idx];
        if (mapEntry) {
          const reducedBar = reducedBars[mapEntry.reducedIndex];
          if (reducedBar && idx === reducedBar.anchor_idx) {
            dotColor = reducedBar.dir > 0 ? upColor : downColor;
          }
        }
      } else {
        const isUp = Number(k.c) >= Number(k.o);
        dotColor = isUp ? upColor : downColor;
      }

      // 输出 K/H-L 标题行
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:${dotColor};"></span>${kLabel}</div>`
      );

      // 新增：在 HL 柱模式且当前位置为“去包含后承载点”时，追加 G/D 两行（位于 O 行之前）
      if (
        ks.subType === "bar" &&
        Array.isArray(reducedBars) &&
        reducedBars.length &&
        mapOrigToReduced &&
        mapOrigToReduced[idx]
      ) {
        const entry = mapOrigToReduced[idx];
        const rb =
          entry && typeof entry.reducedIndex === "number"
            ? reducedBars[entry.reducedIndex]
            : null;
        // 必须要求当前 idx 为承载点，保证“有 HL 柱”
        if (rb && idx === rb.anchor_idx) {
          // G = 去包含后的高点价格（rb.hi）
          rows.push(
            `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>G: ${fmt3(
              rb.hi
            )}</div>`
          );
          // D = 去包含后的低点价格（rb.lo）
          rows.push(
            `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>D: ${fmt3(
              rb.lo
            )}</div>`
          );
        }
      }

      // 继续输出 O/H/L/C（保持原顺序与样式）
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
      // 折线模式（Close）
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:#03a9f4;"></span>Close: ${fmt3(
          k.c
        )}</div>`
      );
    }

    // 追加各条 MA（或其它线）的值
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
    const hasPump = params.some((pp) => pp.seriesName === "放量标记");
    const hasDump = params.some((pp) => pp.seriesName === "缩量���记");
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
    if (typeof k.tr === "number") {
      rows.push(
        `<div><span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>换手率: ${fmt3(
          k.tr
        )}%</div>`
      );
    }
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
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const dates = list.map((d) => d.t);
  const series = [];

  if (chartType === "kline") {
    const ks = klineStyle || {};
    const barPercent = Number.isFinite(+ks.barPercent) ? +ks.barPercent : 100;
    const upColor = ks.upColor || theme.candle.rise;
    const downColor = ks.downColor || theme.candle.fall;
    if (ks.subType === "bar") {
      if (Array.isArray(reducedBars) && reducedBars.length) {
        const n = dates.length;
        const baseLow = new Array(n).fill(null);
        const hlSpan = new Array(n).fill(null);
        const upIndexSet = new Set();
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
        klineStyle,
        reducedBars,
        mapOrigToReduced, // 关键修改：提供映射以判断是否承载点
      }),
    },
    xAxis: { type: "category", data: dates },
    yAxis: { scale: true },
    series,
  };
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
 */
export function buildVolumeOption(
  { candles, indicators, freq, volCfg, volEnv },
  ui
) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const dates = list.map((d) => d.t);
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
  const hostW = Math.max(1, Number(volEnv?.hostWidth || 0));
  const visCount = Math.max(1, Number(volEnv?.visCount || baseScaled.length));
  const approxBarWidthPx =
    hostW > 1 && visCount > 0
      ? Math.max(
          1,
          Math.floor(((hostW * 0.88) / visCount) * (barPercent / 100))
        )
      : 8;
  // 改为引用集中默认（最小/最大宽度、基准高度、偏移倍数）
  const MARKER_W_MIN = DEFAULT_VOL_MARKER_SIZE.minPx;
  const MARKER_W_MAX = DEFAULT_VOL_MARKER_SIZE.maxPx;
  const markerW = Math.max(
    MARKER_W_MIN,
    Math.min(MARKER_W_MAX, Math.round(approxBarWidthPx))
  );
  const markerH = DEFAULT_VOL_MARKER_SIZE.baseHeightPx;
  const symbolOffsetBelow = [
    0,
    Math.round(markerH * DEFAULT_VOL_MARKER_SIZE.offsetK),
  ];
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
  const anyMarkers =
    (pumpEnabled && pumpPts.length > 0) || (dumpEnabled && dumpPts.length > 0);
  const extraBottomPx = anyMarkers ? markerH : 0;
  const xAxisLabelMargin = anyMarkers ? Math.max(12, markerH + 12) : 12;
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
  return applyUi(
    option,
    {
      ...ui,
      isMain: false,
      tooltipPositioner: createFixedTooltipPositioner("left"),
      extraBottomPx,
      xAxisLabelMargin,
    },
    { dates, freq }
  );
}

/**
 * MACD 窗 option 组装
 */
export function buildMacdOption({ candles, indicators, freq }, ui) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const dates = list.map((d) => d.t);
  const series = [];
  if (inds.MACD_DIF && inds.MACD_DEA && inds.MACD_HIST) {
    let lineStyleIndex = 0;
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
