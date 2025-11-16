// src/charts/options/skeleton/tech.js
// ==============================
// 说明：技术指标图表骨架生成器（重命名自 common.js）
// 职责：生成副图的通用 Option 结构
// 设计：纯函数，不包含具体指标逻辑
// 
// 重命名理由：
//   - "common" 过于宽泛，不表达实际职责
//   - "tech" 明确指向技术指标副图
//   - "skeleton" 强调其为骨架生成器
// ==============================

import { getChartTheme } from "@/charts/theme";
import { applyLayout } from "../positioning/layout";  // ← 新路径
import { formatNumberScaled } from "@/utils/numberUtils";

/**
 * 创建技术指标图表的骨架配置
 * 
 * @param {Object} params
 * @param {Array} params.candles - K线数据
 * @param {string} params.freq - 频率
 * @param {Function} params.tooltipFormatter - Tooltip格式化函数
 * @param {Object} ui - UI配置
 * @param {Function} [yAxisLabelFormatter] - Y轴标签格式化函数
 * @returns {Object} ECharts Option骨架
 */
export function createTechSkeleton(
  { candles, freq, tooltipFormatter },
  ui,
  yAxisLabelFormatter
) {
  const theme = getChartTheme();

  const primaryYAxisFormatter =
    typeof yAxisLabelFormatter === "function"
      ? yAxisLabelFormatter
      : (val) => formatNumberScaled(val, { minIntDigitsToScale: 5 });

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
          margin: ui?.isHovered ? 6 : 6,
        },
        axisPointer: {
          show: true,
          label: { show: !!ui?.isHovered },
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
        axisPointer: {
          show: false,
        },
      },
    ],
    series: [],
  };

  if (ui?.tooltipPositioner) {
    option.tooltip.position = ui.tooltipPositioner;
  }

  return applyLayout(
    option,
    { ...ui, isMain: false, leftPx: 72 },
    { candles: Array.isArray(candles) ? candles : [], freq }
  );
}