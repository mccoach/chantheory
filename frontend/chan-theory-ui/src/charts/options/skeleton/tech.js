// src/charts/options/skeleton/tech.js
// ==============================
// V8.0 - 新增 legend 支持
// 改动：
//   - 新增可选参数 options.showLegend（默认 false）
//   - 添加 legend 配置对象
//   - legend 开启时，grid.top 自动增加空间
// ==============================

import { getChartTheme } from "@/charts/theme";
import { applyLayout } from "../positioning/layout";
import { formatNumberScaled } from "@/utils/numberUtils";

export function createTechSkeleton(
  { candles, freq, tooltipFormatter },
  ui,
  yAxisLabelFormatter,
  options = {}  // ← 可选配置参数
) {
  const theme = getChartTheme();

  const primaryYAxisFormatter =
    typeof yAxisLabelFormatter === "function"
      ? yAxisLabelFormatter
      : (val) => formatNumberScaled(val, { minIntDigitsToScale: 5 });

  // ===== legend 开关 =====
  const showLegend = options?.showLegend ?? false;

  const option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    
    // ===== legend 配置 =====
    legend: showLegend ? {
      show: true,
      top: 4,
      left: 'center',
      textStyle: {
        color: theme.axisLabelColor || '#aaa',
        fontSize: 12
      },
      itemWidth: 14,
      itemHeight: 10,
      itemGap: 12,
    } : {
      show: false
    },
    
    axisPointer: {
      link: [{ xAxisIndex: "all" }],
    },
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "cross",
        crossStyle: {
          color: theme.axisLineColor || "#999",
          width: 1,
          type: "dashed",
        },
      },
      appendToBody: false,
      confine: true,
      formatter: tooltipFormatter,
      className: "ct-fixed-tooltip",
      borderWidth: 0,
      backgroundColor: "rgba(20,20,20,0.85)",
      textStyle: { color: theme.textColor, fontSize: 12, align: "left" },
    },
    xAxis: {
      type: "category",
      data: [],
    },
    yAxis: [
      {
        scale: true,
        axisLabel: {
          color: theme.axisLabelColor,
          align: "right",
          formatter: primaryYAxisFormatter,
          margin: 6,
        },
        axisPointer: {
          show: true,
          triggerOn: 'mousemove|click',
          label: {
            show: true,
            formatter: function (params) {
              const val =
                typeof params.value === "object" && params.value !== null
                  ? params.value.value
                  : params.value;
              return typeof yAxisLabelFormatter === "function"
                ? yAxisLabelFormatter(val)
                : formatNumberScaled(val, { digits: 2, allowEmpty: true });
            },
          },
          lineStyle: {
            color: theme.axisLineColor,
            width: 1,
            type: "dashed",
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
        axisPointer: {
          show: false,
          triggerOn: 'none',
          label: { show: false },
          lineStyle: {
            color: 'transparent',
            width: 0,
          },
        },
      },
    ],
    series: [],
  };

  if (ui?.tooltipPositioner) {
    option.tooltip.position = ui.tooltipPositioner;
  }

  const result = applyLayout(
    option,
    { 
      ...ui, 
      isMain: false, 
      leftPx: 72,
      // ===== legend 开启时，top 增加空间 =====
      topExtraPx: showLegend ? 24 : 0
    },
    { candles: Array.isArray(candles) ? candles : [], freq }
  );

  return result;
}