// src/charts/options/builders/macd.js
// ==============================
// V2.0 - 清理冗余导入
// ==============================

import { getChartTheme } from "@/charts/theme";
import { STYLE_PALETTE } from "@/constants";
import { makeMacdTooltipFormatter } from "../tooltips/index";
import { createTechSkeleton } from "../skeleton/tech";  // ← 唯一导入

function asArray(x) {
  return Array.isArray(x) ? x : [];
}
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

export function buildMacdOption({ candles, indicators, freq }, ui) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const series = [];

  if (inds.MACD_DIF && inds.MACD_DEA && inds.MACD_HIST) {
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
    series.push({
      id: "MACD_DIF",
      type: "line",
      name: "DIF",
      data: inds.MACD_DIF,
      showSymbol: false,
      lineStyle: { color: STYLE_PALETTE.lines[0].color, width: 1 },
      itemStyle: { color: STYLE_PALETTE.lines[0].color },
      color: STYLE_PALETTE.lines[0].color,
    });
    series.push({
      id: "MACD_DEA",
      type: "line",
      name: "DEA",
      data: inds.MACD_DEA,
      showSymbol: false,
      lineStyle: { color: STYLE_PALETTE.lines[2].color, width: 1 },
      itemStyle: { color: STYLE_PALETTE.lines[2].color },
      color: STYLE_PALETTE.lines[2].color,
    });
  }

  const option = createTechSkeleton(
    {
      candles: list,
      freq,
      tooltipFormatter: makeMacdTooltipFormatter({ freq }),
    },
    ui
  );

  option.series = series;

  return option;
}