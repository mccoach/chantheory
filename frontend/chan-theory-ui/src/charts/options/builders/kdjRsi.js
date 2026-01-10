// src/charts/options/builders/kdjRsi.js
// ==============================
// V2.1 - 删除未使用导入（getChartTheme）与未使用变量（theme）
// ==============================

import { STYLE_PALETTE } from "@/constants";
import { formatNumberScaled } from "@/utils/numberUtils";
import { makeKdjRsiTooltipFormatter } from "../tooltips/index";
import { createTechSkeleton } from "../skeleton/tech";  // ← 唯一导入

function asArray(x) {
  return Array.isArray(x) ? x : [];
}
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

export function buildKdjOrRsiOption(
  { candles, indicators, freq, useKDJ = false, useRSI = false },
  ui
) {
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const series = [];

  if (useKDJ) {
    if (inds.KDJ_K && inds.KDJ_D && inds.KDJ_J) {
      series.push({
        id: "KDJ_K",
        type: "line",
        name: "K",
        data: inds.KDJ_K,
        showSymbol: false,
        lineStyle: { color: STYLE_PALETTE.lines[0].color, width: 1 },
        itemStyle: { color: STYLE_PALETTE.lines[0].color },
        color: STYLE_PALETTE.lines[0].color,
      });
      series.push({
        id: "KDJ_D",
        type: "line",
        name: "D",
        data: inds.KDJ_D,
        showSymbol: false,
        lineStyle: { color: STYLE_PALETTE.lines[1].color, width: 1 },
        itemStyle: { color: STYLE_PALETTE.lines[1].color },
        color: STYLE_PALETTE.lines[1].color,
      });
      series.push({
        id: "KDJ_J",
        type: "line",
        name: "J",
        data: inds.KDJ_J,
        showSymbol: false,
        lineStyle: { color: STYLE_PALETTE.lines[2].color, width: 1 },
        itemStyle: { color: STYLE_PALETTE.lines[2].color },
        color: STYLE_PALETTE.lines[2].color,
      });
    }
  } else if (useRSI) {
    if (inds.RSI) {
      series.push({
        id: "RSI",
        type: "line",
        name: "RSI",
        data: inds.RSI,
        showSymbol: false,
        lineStyle: { color: STYLE_PALETTE.lines[0].color, width: 1 },
        itemStyle: { color: STYLE_PALETTE.lines[0].color },
        color: STYLE_PALETTE.lines[0].color,
      });
    }
  }

  const yAxisFormatter = (val) =>
    formatNumberScaled(val, {
      digits: 2,
      allowEmpty: true,
      minIntDigitsToScale: 5,
    });

  const option = createTechSkeleton(
    {
      candles: list,
      freq,
      tooltipFormatter: makeKdjRsiTooltipFormatter({ freq }),
    },
    ui,
    yAxisFormatter
  );

  option.series = series;

  return option;
}