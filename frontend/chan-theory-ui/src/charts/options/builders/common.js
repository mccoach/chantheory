// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options\builders\common.js
// ==============================
// 说明：通用的 ECharts Option 构造器辅助函数
// - createBaseTechOption: 创建所有技术指标副图通用的 Option 骨架。
// - 目的：消除在 macd.js, kdjRsi.js, boll.js, volume.js 中的重复配置。
// ==============================

import { getChartTheme } from "@/charts/theme";
import { applyUi } from "../ui/applyUi";
import { formatNumberScaled } from "@/utils/numberUtils";

/**
 * 创建技术指标图表的基础 Option 配置
 * @param {object} params
 * @param {Array} params.dates - 日期数组
 * @param {string} params.freq - 周期
 * @param {Function} params.tooltipFormatter - Tooltip 的格式化函数
 * @param {object} ui - UI 相关的配置
 * @param {Function} [yAxisLabelFormatter] - Y轴标签的格式化函数
 * @returns {object} - 一个包含通用配置的 ECharts Option 对象
 */
export function createBaseTechOption(
  { dates, freq, tooltipFormatter },
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
      data: dates,
    },
    yAxis: [
      {
        // 主Y轴，用于显示指标线
        scale: true,
        axisLabel: {
          color: theme.axisLabelColor,
          align: "right",
          formatter: primaryYAxisFormatter,
          margin: ui?.isHovered ? 6 : 6,
        },
        axisPointer: {
          show: true, // 保持为 true, 由 link 机制统一控制
          label: { show: !!ui?.isHovered },
          // 通过颜色控制可见性, 悬浮时可见, 否则透明
          lineStyle: {
            color: ui?.isHovered ? theme.axisLineColor : "transparent",
          },
        },
      },
      {
        // 隐藏的第二Y轴，用于承载图外的标记（如量窗的放量/缩量标记）
        type: "value",
        min: 0,
        max: 1,
        show: false,
        scale: false,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        // 显式禁用第二Y轴的指针
        axisPointer: {
          show: false,
        },
      },
    ],
    series: [], // series 由各个具体的 builder 填充
  };

  if (ui?.tooltipPositioner) {
    option.tooltip.position = ui.tooltipPositioner;
  }

  // 应用通用的 grid, dataZoom 等UI配置
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
