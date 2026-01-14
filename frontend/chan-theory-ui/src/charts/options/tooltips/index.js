// frontend/src/charts/options/tooltips/index.js
// ==============================
// V4.2 - NEW: 主图 Tooltip 增加“涨跌幅”（今收/昨收百分比）
// 变更要点：
//   - 仅在 tooltip 中展示，不出图、不写入 indicators
//   - 数据来源：candles（唯一真相源）
//   - 位置：C 行下面、MA 均线族上面
// ==============================

import { formatNumberScaled } from "@/utils/numberUtils";
import { DEFAULT_KLINE_STYLE, STYLE_PALETTE, DEFAULT_VOL_SETTINGS } from "@/constants";

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

function extractTimeLabel(params, _freq) {
  if (!Array.isArray(params) || !params.length) return "";
  const rawLabel = params[0].axisValue || params[0].axisValueLabel || "";
  return String(rawLabel);
}

function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

// ==============================
// 主图 Tooltip Formatter（显式注入 indicators）
// ==============================

export function makeMainTooltipFormatter({
  theme,
  chartType,
  freq,
  candles,
  indicators, // NEW: 显式注入（唯一来源）
  maConfigs,
  adjust,
  klineStyle,
  reducedBars,
  mapOrigToReduced,
  mergedGDByOrigIdx,
  atrStopSettings,
}) {
  const list = Array.isArray(candles) ? candles : [];
  const inds = asIndicators(indicators);

  const KS = klineStyle || DEFAULT_KLINE_STYLE || {};
  const MK = KS.mergedK || DEFAULT_KLINE_STYLE.mergedK || {};
  const gdArr = Array.isArray(mergedGDByOrigIdx) ? mergedGDByOrigIdx : null;

  // TR 永远显示（只读）
  const TR_KEY = "ATR_TR";

  // MATR keys（TR 的移动平均）：与 ATR_stop 成对
  const MATR_KEYS = {
    fixedLong: "MATR_FIXED_LONG",
    fixedShort: "MATR_FIXED_SHORT",
    chanLong: "MATR_CHAN_LONG",
    chanShort: "MATR_CHAN_SHORT",
  };

  // ATR_stop keys（最终止损价）
  const STOP_KEYS = {
    fixedLong: "ATR_FIXED_LONG",
    fixedShort: "ATR_FIXED_SHORT",
    chanLong: "ATR_CHAN_LONG",
    chanShort: "ATR_CHAN_SHORT",
  };

  // NEW: 统一从 atrStopSettings 取对应线颜色（与出图线一致）
  function getAtrLineColor(pairKey) {
    const s = atrStopSettings && typeof atrStopSettings === "object" ? atrStopSettings : null;
    if (!s) return null;

    if (pairKey === "fixedLong") return s.fixed?.long?.color || null;
    if (pairKey === "fixedShort") return s.fixed?.short?.color || null;
    if (pairKey === "chanLong") return s.chandelier?.long?.color || null;
    if (pairKey === "chanShort") return s.chandelier?.short?.color || null;

    return null;
  }

  function enabledFlags() {
    const s = atrStopSettings && typeof atrStopSettings === "object" ? atrStopSettings : null;
    return {
      fixedLong: s?.fixed?.long?.enabled === true,
      fixedShort: s?.fixed?.short?.enabled === true,
      chanLong: s?.chandelier?.long?.enabled === true,
      chanShort: s?.chandelier?.short?.enabled === true,
    };
  }

  // NEW: 计算涨跌幅（今收/昨收）
  function calcChgPctByClose(idx) {
    const i = Number(idx);
    if (!Number.isFinite(i)) return null;

    const cur = list[i];
    const prev = i > 0 ? list[i - 1] : null;

    const c = Number(cur?.c);
    const prevC = Number(prev?.c);

    if (!Number.isFinite(c) || !Number.isFinite(prevC) || prevC === 0) return null;

    return ((c - prevC) / prevC) * 100;
  }

  return function (params) {
    if (!Array.isArray(params) || !params.length) return "";

    const timeLabel = extractTimeLabel(params, freq);
    const adjLabel = { qfq: "前复权", hfq: "后复权" }[adjust] || "";

    const rows = [];
    const idx = params[0].dataIndex ?? 0;
    const k = list[idx] || {};

    // ===== 价格组（G/D/O/H/L/C）=====
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
    } catch { }

    let G = null;
    let D = null;
    try {
      const gd = gdArr && gdArr[idx] ? gdArr[idx] : null;
      const g0 = gd ? Number(gd.G) : NaN;
      const d0 = gd ? Number(gd.D) : NaN;
      G = Number.isFinite(g0) ? g0 : null;
      D = Number.isFinite(d0) ? d0 : null;
    } catch { }

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

      // ===== NEW: 涨跌幅（C 下、MA 上）=====
      {
        const chgPct = calcChgPctByClose(idx);
        rows.push(
          renderRow({
            color: null,
            label: "涨跌幅",
            value:
              chgPct == null
                ? "-"
                : `${formatNumberScaled(chgPct, {
                  digits: 2,
                  allowEmpty: true,
                  minIntDigitsToScale: 9,
                })}%`,
          })
        );
      }
    } else {
      const closeLineColor =
        (STYLE_PALETTE.lines[5] && STYLE_PALETTE.lines[5].color) || STYLE_PALETTE.lines[0].color;
      rows.push(
        renderRow({
          color: closeLineColor,
          label: "Close",
          value: formatNumberScaled(k.c, { digits: 3, allowEmpty: true }),
        })
      );
    }

    // ===== MA 均线族：从 params 读取（保持原有显示逻辑）=====
    // 说明：ATR_stop 线也属于 line，但必须移到后面与 MATR 配对显示，因此这里跳过四条 ATR_stop 的 seriesId。
    const stopIdSet = new Set(Object.values(STOP_KEYS));

    for (const p of params) {
      if (p.seriesType === "line" && p.seriesName !== "Close") {
        const sid = String(p?.seriesId || "");
        if (stopIdSet.has(sid)) continue;

        const val = Array.isArray(p.value) ? p.value[p.value.length - 1] : p.value;
        rows.push(
          renderRow({
            color: p.color,
            label: p.seriesName,
            value: formatNumberScaled(val, { digits: 3, allowEmpty: true }),
          })
        );
      }
    }

    // ===== TR（永远显示；只读 indicators）=====
    {
      const trArr = Array.isArray(inds[TR_KEY]) ? inds[TR_KEY] : null;
      const trVal = trArr ? trArr[idx] : null;
      rows.push(
        renderRow({
          color: null,
          label: "TR",
          value: formatNumberScaled(trVal, { digits: 3, allowEmpty: true }),
        })
      );
    }

    // ===== MATR / ATR_stop 对（仅对启用的 stop 显示）=====
    const enabled = enabledFlags();
    const pairs = [
      { k: "fixedLong", matrLabel: "MATR(倍-多)", stopLabel: "ATR止损价(倍-多)" },
      { k: "fixedShort", matrLabel: "MATR(倍-空)", stopLabel: "ATR止损价(倍-空)" },
      { k: "chanLong", matrLabel: "MATR(波-多)", stopLabel: "ATR止损价(波-多)" },
      { k: "chanShort", matrLabel: "MATR(波-空)", stopLabel: "ATR止损价(波-空)" },
    ];

    for (const it of pairs) {
      if (!enabled[it.k]) continue;

      const matrKey = MATR_KEYS[it.k];
      const stopKey = STOP_KEYS[it.k];

      const matrArr = Array.isArray(inds[matrKey]) ? inds[matrKey] : null;
      const matrVal = matrArr ? matrArr[idx] : null;

      const stopArr = Array.isArray(inds[stopKey]) ? inds[stopKey] : null;
      const stopVal = stopArr ? stopArr[idx] : null;

      // NEW: MATR 与 ATR_stop 行都使用对应止损线颜色（范式与 MA/价格一致）
      const pairColor = getAtrLineColor(it.k);

      rows.push(
        renderRow({
          color: pairColor,
          label: it.matrLabel,
          value: formatNumberScaled(matrVal, { digits: 3, allowEmpty: true }),
        })
      );
      rows.push(
        renderRow({
          color: pairColor,
          label: it.stopLabel,
          value: formatNumberScaled(stopVal, { digits: 3, allowEmpty: true }),
        })
      );
    }

    return [renderHeader(timeLabel, adjLabel), ...rows].join("");
  };
}

// ==============================
// 量窗 Tooltip Formatter
// ==============================

function findFirst(params, pred) {
  return Array.isArray(params) ? params.find(pred) : null;
}

export function makeVolumeTooltipFormatter({ candles, freq, baseName, mavolMap, volCfg }) {
  const list = Array.isArray(candles) ? candles : [];
  const isVolMode = (baseName || "").toUpperCase() === "VOL";

  const allPeriods = Object.values(volCfg?.mavolStyles || {})
    .filter((s) => s && s.enabled && Number.isFinite(+s.period) && +s.period > 0)
    .map((s) => +s.period)
    .sort((a, b) => a - b);
  const primN = allPeriods.length ? allPeriods[0] : null;

  const pumpK = Number.isFinite(+volCfg?.markerPump?.threshold)
    ? +volCfg.markerPump.threshold
    : DEFAULT_VOL_SETTINGS.markerPump.threshold;
  const dumpK = Number.isFinite(+volCfg?.markerDump?.threshold)
    ? +volCfg.markerDump.threshold
    : DEFAULT_VOL_SETTINGS.markerDump.threshold;

  const pumpEnabled = (volCfg?.markerPump?.enabled ?? true) === true;
  const dumpEnabled = (volCfg?.markerDump?.enabled ?? true) === true;

  return function (params) {
    if (!Array.isArray(params) || !params.length) return "";

    const timeLabel = extractTimeLabel(params, freq);

    const p0 = params[0];
    const idx = p0.dataIndex || 0;
    const k = list[idx] || {};
    const isUp = Number(k.c) >= Number(k.o);

    const baseDotColor = isUp ? STYLE_PALETTE.bars.volume.up : STYLE_PALETTE.bars.volume.down;

    const bar = findFirst(params, (x) => (x.seriesType || "").toLowerCase() === "bar");
    const baseRawVal = Array.isArray(bar?.value) ? bar.value[bar.value.length - 1] : bar?.value;

    const baseValText = formatNumberScaled(baseRawVal, { minIntDigitsToScale: 5 });

    let statusTag = "";
    if (primN && mavolMap && mavolMap[primN]) {
      const mv = mavolMap[primN]?.[idx];
      const v = Number(baseRawVal);
      if (Number.isFinite(v) && Number.isFinite(+mv) && +mv > 0) {
        if (pumpEnabled && pumpK > 0 && v >= pumpK * mv) statusTag = "（放）";
        else if (dumpEnabled && dumpK > 0 && v <= dumpK * mv) statusTag = "（缩）";
      }
    }

    const periods = Object.keys(mavolMap || {})
      .map((x) => +x)
      .sort((a, b) => a - b);

    const rows = [];
    rows.push(
      renderRow({
        color: bar?.color || baseDotColor,
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
            value: formatNumberScaled(k.v, { minIntDigitsToScale: 5, suffix: "手" }),
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
      const val = Array.isArray(p.value)
        ? p.value[p.value.length - 1]
        : p.value;

      // 统一使用 p.color，确保与图形中的颜色一致（柱子 + 折线）
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
// BOLL Tooltip Formatter
// ==============================

export function makeBollTooltipFormatter({ freq }) {
  return function (params) {
    if (!Array.isArray(params) || !params.length) return "";

    // ===== 使用统一提取函数 =====
    const timeLabel = extractTimeLabel(params, freq);

    const rows = [];
    for (const p of params) {
      const val = Array.isArray(p.value)
        ? p.value[p.value.length - 1]
        : p.value;
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
      const val = Array.isArray(p.value)
        ? p.value[p.value.length - 1]
        : p.value;
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
