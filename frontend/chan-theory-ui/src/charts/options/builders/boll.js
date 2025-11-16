// src/charts/options/builders/boll.js
// ==============================
// V2.0 - 清理冗余导入
// ==============================

import { getChartTheme } from "@/charts/theme";
import { STYLE_PALETTE } from "@/constants";
import { makeBollTooltipFormatter } from "../tooltips/index";
import { createTechSkeleton } from "../skeleton/tech";  // ← 唯一导入

function asArray(x) {
  return Array.isArray(x) ? x : [];
}
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

export function buildBollOption({ candles, indicators, freq }, ui) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const series = [];

  if (inds.BOLL_MID && inds.BOLL_UPPER && inds.BOLL_LOWER) {
    series.push({
      id: "BOLL_MID",
      type: "line",
      name: "BOLL_MID",
      data: inds.BOLL_MID,
      showSymbol: false,
      lineStyle: { color: STYLE_PALETTE.lines[0].color, width: 1 },
      itemStyle: { color: STYLE_PALETTE.lines[0].color },
      color: STYLE_PALETTE.lines[0].color,
    });
    series.push({
      id: "BOLL_UPPER",
      type: "line",
      name: "BOLL_UPPER",
      data: inds.BOLL_UPPER,
      showSymbol: false,
      lineStyle: { color: STYLE_PALETTE.lines[2].color, width: 1 },
      itemStyle: { color: STYLE_PALETTE.lines[2].color },
      color: STYLE_PALETTE.lines[2].color,
    });
    series.push({
      id: "BOLL_LOWER",
      type: "line",
      name: "BOLL_LOWER",
      data: inds.BOLL_LOWER,
      showSymbol: false,
      lineStyle: { color: STYLE_PALETTE.lines[3].color, width: 1 },
      itemStyle: { color: STYLE_PALETTE.lines[3].color },
      color: STYLE_PALETTE.lines[3].color,
    });
  }

  const option = createTechSkeleton(
    {
      candles: list,
      freq,
      tooltipFormatter: makeBollTooltipFormatter({ freq }),
    },
    ui
  );

  option.series = series;

  return option;
}