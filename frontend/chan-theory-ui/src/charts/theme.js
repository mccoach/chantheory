// src/charts/theme.js
// ==============================
// 说明：从 CSS 变量读取主题色，映射到 ECharts 配置消费
// - 暴露 getChartTheme()：返回颜色/轴线/背景等
// - 主题切换时可重新读取并 setOption 覆盖
// ==============================

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
  const bg = cssVar("--bg-main") || "#111";
  const fg = cssVar("--fg-main") || "#ddd";
  const axisLine = cssVar("--axis-line") || "#555";
  const axisLabel = cssVar("--axis-label") || "#aaa";
  const gridLine = cssVar("--grid-line") || "#2a2a2a";
  const rise = cssVar("--rise-color") || "#f56c6c";
  const fall = cssVar("--fall-color") || "#26a69a";

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
