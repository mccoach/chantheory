// frontend/src/charts/options/tooltips/index.js
// ==============================
// V3.0 - 按需格式化架构（零冗余版）
// 
// 核心改动：
//   1. 新增 extractTimeLabel() 统一时间提取逻辑
//   2. 支持 xAxis.data 为对象数组或字符串数组
//   3. 所有 formatter 复用统一提取函数
// 
// 职责：
//   - 构造各类图表的 Tooltip 内容
//   - 智能识别 axisValue 类型（对象/字符串/数字）
//   - 格式化为统一的 HTML 模板
// ==============================

import { formatTimeByFreq } from "@/utils/timeFormat";
import { formatNumberScaled } from "@/utils/numberUtils";
import { DEFAULT_KLINE_STYLE, STYLE_PALETTE } from "@/constants";

// ==============================
// 工具函数：模板渲染
// ==============================

/**
 * 渲染 Tooltip 首行（时间 + 可选附加信息）
 */
function renderHeader(timeLabel, extraText) {
  const ext = extraText ? ` ${extraText}` : "";
  return `<div style="margin-bottom:4px;">${timeLabel}${ext}</div>`;
}

/**
 * 渲染 Tooltip 数据行（颜色圆点 + 标签 + 值）
 */
function renderRow({ color, label, value }) {
  const dot =
    color && typeof color === "string"
      ? `<span style="display:inline-block;margin-right:6px;width:8px;height:8px;border-radius:50%;background:${color};"></span>`
      : `<span style="display:inline-block;margin-right:6px;width:8px;height:8px;"></span>`;
  return `<div>${dot}${label}: ${value}</div>`;
}

/**
 * 从 params 数组中查找第一个匹配条件的项
 */
function findFirst(params, pred) {
  return Array.isArray(params) ? params.find(pred) : null;
}

// ==============================
// 核心：统一时间提取逻辑（新增）
// ==============================

/**
 * 智能提取 Tooltip 的时间标签
 * 
 * 职责：
 *   - 从 ECharts params 中提取 axisValue
 *   - 智能识别类型（对象/字符串/数字/时间戳）
 *   - 格式化为可读时间字符串
 * 
 * 支持的数据源：
 *   - xAxis.data = [{ts, o, h, l, c, v}, ...]  → axisValue 是对象
 *   - xAxis.data = ["2003-10-09", ...]         → axisValue 是字符串
 *   - xAxis.data = [1065682800000, ...]        → axisValue 是时间戳
 * 
 * @param {Array} params - ECharts tooltip params
 * @param {string} freq - 频率（用于判断格式）
 * @returns {string} 格式化后的时间字符串
 */
function extractTimeLabel(params, freq) {
  if (!Array.isArray(params) || !params.length) return "";
  
  const rawLabel = params[0].axisValue || params[0].axisValueLabel || "";
  
  // ===== 修改：直接返回字符串，不再格式化 =====
  return String(rawLabel);
}

// ==============================
// 主图 Tooltip Formatter
// ==============================

export function makeMainTooltipFormatter({
  theme,
  chartType,
  freq,
  candles,
  maConfigs,
  adjust,
  klineStyle,
  reducedBars,
  mapOrigToReduced,
}) {
  const list = Array.isArray(candles) ? candles : [];
  const KS = klineStyle || DEFAULT_KLINE_STYLE || {};
  const MK = KS.mergedK || DEFAULT_KLINE_STYLE.mergedK || {};

  return function (params) {
    if (!Array.isArray(params) || !params.length) return "";
    
    // ===== 使用统一提取函数 =====
    const timeLabel = extractTimeLabel(params, freq);
    const adjLabel = { qfq: "前复权", hfq: "后复权" }[adjust] || "";

    const rows = [];
    const idx = params[0].dataIndex ?? 0;
    const k = list[idx] || {};

    // 合并K方向色
    let mergedDotColor = null;
    try {
      const entry = mapOrigToReduced && mapOrigToReduced[idx];
      const reducedIdx =
        entry && typeof entry.reduced_idx === "number"
          ? entry.reduced_idx
          : null;
      const rb =
        reducedIdx != null && reducedBars && reducedBars[reducedIdx]
          ? reducedBars[reducedIdx]
          : null;
      const dir = Number(rb?.dir_int || 0);
      if (dir !== 0) {
        mergedDotColor = dir > 0 ? MK.upColor : MK.downColor;
      }
    } catch {}

    // G/D（来自合并K极值；若无映射退到原始K的 h/l）
    let G = k.h,
      D = k.l;
    try {
      const entry = mapOrigToReduced && mapOrigToReduced[idx];
      const reducedIdx =
        entry && typeof entry.reduced_idx === "number"
          ? entry.reduced_idx
          : null;
      const rb =
        reducedIdx != null && reducedBars && reducedBars[reducedIdx]
          ? reducedBars[reducedIdx]
          : null;
      if (rb && Number.isFinite(rb.g_pri) && Number.isFinite(rb.d_pri)) {
        G = rb.g_pri;
        D = rb.d_pri;
      }
    } catch {}

    rows.push(
      renderRow({
        color: mergedDotColor,
        label: "G",
        value: formatNumberScaled(G, { digits: 3, allowEmpty: true }),
      })
    );
    rows.push(
      renderRow({
        color: mergedDotColor,
        label: "D",
        value: formatNumberScaled(D, { digits: 3, allowEmpty: true }),
      })
    );

    if (chartType === "kline") {
      const origUp = Number(k.c) >= Number(k.o);
      const origDotColor = origUp
        ? KS.upColor || DEFAULT_KLINE_STYLE.upColor
        : KS.downColor || DEFAULT_KLINE_STYLE.downColor;
      rows.push(
        renderRow({
          color: origDotColor,
          label: "O",
          value: formatNumberScaled(k.o, { digits: 3, allowEmpty: true }),
        })
      );
      rows.push(
        renderRow({
          color: null,
          label: "H",
          value: formatNumberScaled(k.h, { digits: 3, allowEmpty: true }),
        })
      );
      rows.push(
        renderRow({
          color: null,
          label: "L",
          value: formatNumberScaled(k.l, { digits: 3, allowEmpty: true }),
        })
      );
      rows.push(
        renderRow({
          color: origDotColor,
          label: "C",
          value: formatNumberScaled(k.c, { digits: 3, allowEmpty: true }),
        })
      );
    } else {
      const closeLineColor =
        (STYLE_PALETTE.lines[5] && STYLE_PALETTE.lines[5].color) ||
        STYLE_PALETTE.lines[0].color;
      rows.push(
        renderRow({
          color: closeLineColor,
          label: "Close",
          value: formatNumberScaled(k.c, { digits: 3, allowEmpty: true }),
        })
      );
    }

    // MA 行
    for (const p of params) {
      if (p.seriesType === "line" && p.seriesName !== "Close") {
        const val = Array.isArray(p.value)
          ? p.value[p.value.length - 1]
          : p.value;
        rows.push(
          renderRow({
            color: p.color,
            label: p.seriesName,
            value: formatNumberScaled(val, { digits: 3, allowEmpty: true }),
          })
        );
      }
    }

    return [renderHeader(timeLabel, adjLabel), ...rows].join("");
  };
}

// ==============================
// 量窗 Tooltip Formatter
// ==============================

export function makeVolumeTooltipFormatter({ candles, freq, baseName, mavolMap }) {
  const list = Array.isArray(candles) ? candles : [];
  const isVolMode = (baseName || "").toUpperCase() === "VOL";

  return function (params) {
    if (!Array.isArray(params) || !params.length) return "";
    
    // ===== 使用统一提取函数 =====
    const timeLabel = extractTimeLabel(params, freq);
    
    const p0 = params[0];
    const idx = p0.dataIndex || 0;
    const k = list[idx] || {};
    const isUp = Number(k.c) >= Number(k.o);

    const baseDotColor = isUp
      ? STYLE_PALETTE.bars.volume.up
      : STYLE_PALETTE.bars.volume.down;

    const bar = findFirst(params, (x) => (x.seriesType || "").toLowerCase() === "bar");
    const baseRawVal = Array.isArray(bar?.value)
      ? bar.value[bar.value.length - 1]
      : bar?.value;

    const baseValText = formatNumberScaled(baseRawVal, {
      minIntDigitsToScale: 5,
    });

    const hasPump = params.some((pp) => pp.seriesName === "放量标记");
    const hasDump = params.some((pp) => pp.seriesName === "缩量标记");
    const statusTag = hasPump ? "（放）" : hasDump ? "（缩）" : "";

    const periods = Object.keys(mavolMap || {})
      .map((x) => +x)
      .sort((a, b) => a - b);

    const rows = [];
    rows.push(
      renderRow({
        color: baseDotColor,
        label: isVolMode ? "成交量" : "成交额",
        value: `${baseValText}${statusTag}`,
      })
    );

    for (const n of periods) {
      const mv = mavolMap[n] ? mavolMap[n][idx] : null;
      if (mv == null || !Number.isFinite(+mv)) continue;
      const lineParam = findFirst(
        params,
        (pp) =>
          (pp.seriesType || "").toLowerCase() === "line" &&
          typeof pp.seriesName === "string" &&
          pp.seriesName.endsWith(String(n))
      );
      const dotColor = lineParam?.color || "#ccc";
      const labelPrefix = isVolMode ? "量MA" : "额MA";
      rows.push(
        renderRow({
          color: dotColor,
          label: `${labelPrefix}${n}`,
          value: formatNumberScaled(mv, { minIntDigitsToScale: 5 }),
        })
      );
    }

    if (typeof k.tr === "number") {
      rows.push(
        renderRow({
          color: null,
          label: "换手率",
          value: formatNumberScaled(k.tr, {
            digits: 2,
            percent: { base: 1 },
            allowEmpty: true,
          }),
        })
      );
    }

    if (isVolMode) {
      if (typeof k.a === "number") {
        rows.push(
          renderRow({
            color: null,
            label: "成交额",
            value: formatNumberScaled(k.a, { minIntDigitsToScale: 5 }),
          })
        );
      }
    } else {
      if (typeof k.v === "number") {
        rows.push(
          renderRow({
            color: null,
            label: "成交量",
            value: formatNumberScaled(k.v, {
              minIntDigitsToScale: 5,
              suffix: "手",
            }),
          })
        );
      }
    }

    return [renderHeader(timeLabel), ...rows].join("");
  };
}

// ==============================
// MACD Tooltip Formatter
// ==============================

export function makeMacdTooltipFormatter({ freq }) {
  return function (params) {
    if (!Array.isArray(params) || !params.length) return "";
    
    // ===== 使用统一提取函数 =====
    const timeLabel = extractTimeLabel(params, freq);

    const rows = [];
    for (const p of params) {
      const val = Array.isArray(p.value) ? p.value[p.value.length - 1] : p.value;
      if ((p.seriesType || "").toLowerCase() === "bar") {
        const color =
          Number(val) >= 0
            ? STYLE_PALETTE.bars.macd.positive
            : STYLE_PALETTE.bars.macd.negative;
        rows.push(
          renderRow({
            color,
            label: p.seriesName,
            value: formatNumberScaled(val, { digits: 3, allowEmpty: true }),
          })
        );
      } else {
        rows.push(
          renderRow({
            color: p.color,
            label: p.seriesName || "",
            value: formatNumberScaled(val, { digits: 3, allowEmpty: true }),
          })
        );
      }
    }
    return [renderHeader(timeLabel), ...rows].join("");
  };
}

// ==============================
// BOLL Tooltip Formatter
// ==============================

export function makeBollTooltipFormatter({ freq }) {
  return function (params) {
    if (!Array.isArray(params) || !params.length) return "";
    
    // ===== 使用统一提取函数 =====
    const timeLabel = extractTimeLabel(params, freq);

    const rows = [];
    for (const p of params) {
      const val = Array.isArray(p.value) ? p.value[p.value.length - 1] : p.value;
      rows.push(
        renderRow({
          color: p.color,
          label: p.seriesName || "",
          value: formatNumberScaled(val, { digits: 3, allowEmpty: true }),
        })
      );
    }
    return [renderHeader(timeLabel), ...rows].join("");
  };
}

// ==============================
// KDJ/RSI Tooltip Formatter
// ==============================

export function makeKdjRsiTooltipFormatter({ freq }) {
  return function (params) {
    if (!Array.isArray(params) || !params.length) return "";
    
    // ===== 使用统一提取函数 =====
    const timeLabel = extractTimeLabel(params, freq);

    const rows = [];
    for (const p of params) {
      const val = Array.isArray(p.value) ? p.value[p.value.length - 1] : p.value;
      rows.push(
        renderRow({
          color: p.color,
          label: p.seriesName || "",
          value: formatNumberScaled(val, { digits: 3, allowEmpty: true }),
        })
      );
    }
    return [renderHeader(timeLabel), ...rows].join("");
  };
}