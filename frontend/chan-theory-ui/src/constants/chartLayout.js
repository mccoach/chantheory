// src/constants/chartLayout.js
// ==============================
// 说明：图表布局常量（统一真相源）
// 职责：定义所有图表的边距、高度等布局参数
// 设计：按图表类型分组，消除魔法数字
// ==============================

/**
 * 主图布局常量（设置窗未暴露）
 */
export const MAIN_CHART_LAYOUT = {
  LEFT_PX: 72,              // 左边距（Y轴标签空间，像素）（❌ 设置窗未暴露，直接用常量）
  RIGHT_PX: 10,             // 右边距（像素）（❌ 设置窗未暴露，直接用常量）
  SLIDER_HEIGHT_PX: 26,     // dataZoom滑块高度（像素）（❌ 设置窗未暴露，直接用常量）
  AXIS_LABEL_SPACE_PX: 30,  // X轴标签空间（像素）（❌ 设置窗未暴露，直接用常量）
  BOTTOM_EXTRA_PX: 2,       // 底部额外间距（像素）（❌ 设置窗未暴露，直接用常量）
  
  // --- 派生属性：总底部高度 ---
  get TOTAL_BOTTOM_PX() {
    return this.SLIDER_HEIGHT_PX + this.AXIS_LABEL_SPACE_PX + this.BOTTOM_EXTRA_PX;
  }
};

/**
 * 副图（技术指标）布局常量（设置窗未暴露）
 */
export const TECH_CHART_LAYOUT = {
  LEFT_PX: 72,              // 左边距（与主图对齐）（❌ 设置窗未暴露，直接用常量）
  RIGHT_PX: 10,             // 右边距（❌ 设置窗未暴露，直接用常量）
  DEFAULT_BOTTOM_PX: 8,     // 默认底部间距（❌ 设置窗未暴露，直接用常量）
  AXIS_LABEL_MARGIN_PX: 6,  // X轴标签边距（❌ 设置窗未暴露，直接用常量）
};

/**
 * 通用图表常量（设置窗未暴露）
 */
export const COMMON_CHART_LAYOUT = {
  MIN_HEIGHT_PX: 160,       // 图表最小高度（像素）（❌ 设置窗未暴露，直接用常量）
  MAX_HEIGHT_PX: 800,       // 图表最大高度（像素）（❌ 设置窗未暴露，直接用常量）
  RESIZE_HANDLE_HEIGHT: 8,  // 底部拖拽条高度（像素）（❌ 设置窗未暴露，直接用常量）
};