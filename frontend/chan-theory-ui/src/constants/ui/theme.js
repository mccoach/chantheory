// src/constants/ui/theme.js
// ==============================
// 说明：主题色默认值（CSS变量兜底）
// 职责：提供CSS变量的兜底值（当用户删除CSS变量时使用）
// 设计：与 styles/global.css 中的CSS变量一一对应
// ==============================

/**
 * 默认主题色配置（深色主题）
 * 
 * 用途：
 *   - 当 CSS 变量未定义时，作为兜底值
 *   - charts/theme.js 读取CSS变量失败时使用
 * 
 * 对应关系：
 *   bgMain   → --bg-main（主背景色）
 *   fgMain   → --fg-main（主前景色/文字颜色）
 *   axisLine → --axis-line（坐标轴线颜色）
 *   axisLabel → --axis-label（坐标轴标签颜色）
 *   gridLine → --grid-line（网格线颜色）
 *   riseColor → --rise-color（上涨色/阳线色）
 *   fallColor → --fall-color（下跌色/阴线色）
 */
export const DEFAULT_THEME_COLORS = {
  bgMain: "#111",           // 主背景色（深灰黑）
  fgMain: "#ddd",           // 主前景色（浅灰白）
  axisLine: "#555",         // 坐标轴线颜色（中灰）
  axisLabel: "#aaa",        // 坐标轴标签颜色（浅灰）
  gridLine: "#2a2a2a",      // 网格线颜色（深灰）
  riseColor: "#f56c6c",     // 上涨色（红色系）
  fallColor: "#26a69a",     // 下跌色（绿色系）
};