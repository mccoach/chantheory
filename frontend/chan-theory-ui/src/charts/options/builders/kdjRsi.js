// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options\builders\kdjRsi.js
// ==============================
// 说明：KDJ/RSI 窗 option 构造器（同一容器复用）
// - tooltip 内容统一来自 tooltips 模块；position 由外部 ui.tooltipPositioner 注入
// - 使用 formatNumberScaled（digits:2，minIntDigitsToScale:5）统一数值格式
// - 仅联动 X 轴（竖线），不联动 Y 轴（水平线）
// ==============================

import { getChartTheme } from "@/charts/theme";
import { STYLE_PALETTE } from "@/constants";
import { applyUi } from "../ui/applyUi";
import { formatNumberScaled } from "@/utils/numberUtils";
import { makeKdjRsiTooltipFormatter } from "../tooltips/index";

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
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const dates = list.map((d) => d.t);
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

  const option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    axisPointer: {
      link: [{ xAxisIndex: "all" }],
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      appendToBody: false,
      confine: true,
      formatter: makeKdjRsiTooltipFormatter({ freq }),
      className: "ct-fixed-tooltip",
      borderWidth: 0,
      backgroundColor: "rgba(20,20,20,0.85)",
      textStyle: { color: theme.textColor, fontSize: 12, align: "left" },
    },
    xAxis: { type: "category", data: dates },
    yAxis: {
      scale: true,
      axisLabel: {
        color: theme.axisLabelColor,
        align: "right",
        formatter: (val) =>
          formatNumberScaled(val, {
            digits: 2,
            allowEmpty: true,
            minIntDigitsToScale: 5,
          }),
        margin: ui?.isHovered ? 6 : 6,
      },
      axisPointer: { show: !!ui?.isHovered, label: { show: !!ui?.isHovered } },
    },
    series,
  };

  if (ui?.tooltipPositioner) {
    option.tooltip.position = ui.tooltipPositioner;
  }

  return applyUi(
    option,
    {
      ...ui,
      isMain: false,
      leftPx: 72,
    },
    { dates, freq }
  );
}
        