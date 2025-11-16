// src/charts/theme.js
// ==============================
// V2.0 - 使用常量兜底
// ==============================
import { DEFAULT_THEME_COLORS } from '@/constants/ui/theme'
/** 读取根元素的 CSS 变量 */
function cssVar(name) {
  // 通过 getComputedStyle 读取 CSS 变量
  return getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
}

/** 返回图表主题对象（供 options 生成器使用） */
export function getChartTheme() {
  // 从 CSS 变量读取颜色
  const bg = cssVar("--bg-main") || DEFAULT_THEME_COLORS.bgMain;
  const fg = cssVar("--fg-main") || DEFAULT_THEME_COLORS.fgMain;
  const axisLine = cssVar("--axis-line") || DEFAULT_THEME_COLORS.axisLine;
  const axisLabel = cssVar("--axis-label") || DEFAULT_THEME_COLORS.axisLabel;
  const gridLine = cssVar("--grid-line") || DEFAULT_THEME_COLORS.gridLine;
  const rise = cssVar("--rise-color") || DEFAULT_THEME_COLORS.riseColor;
  const fall = cssVar("--fall-color") || DEFAULT_THEME_COLORS.fallColor;

  // 返回统一主题对象
  return {
    backgroundColor: bg, // 背景色
    textColor: fg, // 文字颜色
    axisLineColor: axisLine, // 坐标轴线
    axisLabelColor: axisLabel, // 坐标文本
    gridLineColor: gridLine, // 网格线
    candle: { rise, fall }, // K 线涨跌色
  };
}