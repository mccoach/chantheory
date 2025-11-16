// src/constants/ui/tooltip.js
// ==============================
// 说明：Tooltip UI 常量（提示框样式参数）
// 职责：定义提示框的样式和定位参数
// 设计：按用途分组，所有参数都是像素值或字符串
// ==============================

/**
 * Tooltip 样式常量（设置窗未暴露）
 * 
 * 用途：
 *   - charts/options/tooltips/index.js 中渲染圆点
 *   - charts/options/positioning/tooltip.js 中计算定位
 */
export const TOOLTIP_STYLE = {
  // --- 圆点样式（用于渲染数据行前的颜色指示器）---
  dotSize: 8,               // 圆点直径（像素）（❌ 设置窗未暴露，直接用常量）
  dotMargin: 6,             // 圆点右边距（像素）（❌ 设置窗未暴露，直接用常量）
  dotRadius: '50%',         // 圆点圆角（CSS值）（❌ 设置窗未暴露，直接用常量）
  
  // --- 定位参数（用于计算Tooltip的显示位置）---
  defaultWidth: 260,        // 默认宽度（像素）（❌ 设置窗未暴露，直接用常量）
  margin: 8,                // 距屏幕边缘的安全间距（像素）（❌ 设置窗未暴露，直接用常量）
  baseY: 8,                 // 距容器顶部的偏移（像素）（❌ 设置窗未暴露，直接用常量）
};