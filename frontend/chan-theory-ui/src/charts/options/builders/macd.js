// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options\builders\macd.js
// ==============================
// 说明：MACD 窗 option 构造器（HIST 柱 + DIF/DEA 线）
// - tooltip 内容统一来自 tooltips 模块；position 由外部 ui.tooltipPositioner 注入
// - 仅联动 X 轴（竖线），不联动 Y 轴（水平线）
// - FIX: 精确控制双Y轴的 axisPointer 可见性，实现“悬浮窗十字，其余竖线”效果。
// ==============================

import { getChartTheme } from "@/charts/theme";
import { STYLE_PALETTE } from "@/constants";
import { applyUi } from "../ui/applyUi";
import { makeMacdTooltipFormatter } from "../tooltips/index";

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
  const dates = list.map((d) => d.t);
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
      formatter: makeMacdTooltipFormatter({ freq }),
      className: "ct-fixed-tooltip",
      borderWidth: 0,
      backgroundColor: "rgba(20,20,20,0.85)",
      textStyle: { color: theme.textColor, fontSize: 12, align: "left" },
    },
    xAxis: { type: "category", data: dates },
    yAxis: [
      {
        scale: true,
        axisLabel: {
          color: theme.axisLabelColor,
          align: "right",
          margin: ui?.isHovered ? 6 : 6,
        },
        axisPointer: {
          show: true, // 保持为 true, 由 link 机制统一控制
          label: { show: !!ui?.isHovered },
          // FIX: 通过颜色控制可见性, 悬浮时可见, 否则透明
          lineStyle: {
            color: ui?.isHovered ? theme.axisLineColor : "transparent",
          },
        },
      },
      {
        type: "value",
        min: 0,
        max: 1,
        show: false,
        scale: false,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        // FIX: 显式禁用第二Y轴的指针
        axisPointer: {
          show: false,
        },
      },
    ],
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
