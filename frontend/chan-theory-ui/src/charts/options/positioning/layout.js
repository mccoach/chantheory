// src/charts/options/positioning/layout.js
// ==============================
// 说明：图表布局配置应用器（拆分自 applyUi.js）
// 职责：应用 grid/xAxis/yAxis/dataZoom 配置
// 设计：纯函数，只做配置组装，不做计算
// 
// 拆分理由：
//   - 原 applyUi.js 混合了布局和格式化，职责过重
//   - 提取布局逻辑，提升可测试性
// ==============================

import { getChartTheme } from "@/charts/theme";
import { formatTimeByFreq } from "@/utils/timeFormat";
import { MAIN_CHART_LAYOUT, TECH_CHART_LAYOUT } from "@/constants/chartLayout";  // ← 使用新常量

/**
 * 应用图表布局配置
 * 
 * @param {Object} option - ECharts原始配置
 * @param {Object} ui - UI参数
 * @param {Object} data - 数据参数 {candles, freq}
 * @returns {Object} 应用布局后的配置
 */
export function applyLayout(option, ui, { candles, freq }) {
  const theme = getChartTheme();

  // ===== 使用统一布局常量 =====
  const leftPx = ui?.leftPx ?? (ui?.isMain ? MAIN_CHART_LAYOUT.LEFT_PX : TECH_CHART_LAYOUT.LEFT_PX);
  const rightPx = ui?.rightPx ?? (ui?.isMain ? MAIN_CHART_LAYOUT.RIGHT_PX : TECH_CHART_LAYOUT.RIGHT_PX);
  
  const isMain = !!ui?.isMain;
  const nonMainExtra = ui?.extraBottomPx ? Number(ui.extraBottomPx) : 0;
  
  const gridBottom = isMain
    ? (ui?.sliderHeightPx ?? MAIN_CHART_LAYOUT.SLIDER_HEIGHT_PX) +
      (ui?.mainAxisLabelSpacePx ?? MAIN_CHART_LAYOUT.AXIS_LABEL_SPACE_PX) +
      (ui?.mainBottomExtraPx ?? MAIN_CHART_LAYOUT.BOTTOM_EXTRA_PX)
    : nonMainExtra;

  option.grid = {
    left: leftPx,
    right: rightPx,
    top: ui?.topExtraPx ?? 0,
    bottom: gridBottom,
    containLabel: false,
  };

  // ===== 预格式化时间（保持V2.0架构）=====
  const list = Array.isArray(candles) ? candles : [];
  const len = list.length;
  const dates = list.map((d) => formatTimeByFreq(freq, d?.ts || 0));

  option.xAxis = Object.assign({}, option.xAxis || {}, {
    type: "category",
    data: dates,
    boundaryGap: ["0%", "0%"],
    axisTick: Object.assign({}, option.xAxis?.axisTick || {}, {
      alignWithLabel: true,
    }),
    axisLabel: Object.assign({}, option.xAxis?.axisLabel || {}, {
      color: theme.axisLabelColor,
      margin: ui?.xAxisLabelMargin ?? 6,
    }),
    axisLine: Object.assign({}, option.xAxis?.axisLine || {}, {
      lineStyle: Object.assign(
        { color: theme.axisLineColor },
        option.xAxis?.axisLine?.lineStyle || {}
      ),
    }),
    min: 0,
    max: len ? len - 1 : undefined,
    splitLine: Object.assign({}, option.xAxis?.splitLine || {}, {
      lineStyle: Object.assign(
        { color: theme.gridLineColor },
        option.xAxis?.splitLine?.lineStyle || {}
      ),
    }),
    axisPointer: Object.assign({}, option.xAxis?.axisPointer || {}, {
      label: Object.assign({}, option.xAxis?.axisPointer?.label || {}, {
        show: false,
      }),
    }),
  });

  // ===== 关键修改区域开始 =====
  
  // ===== 诊断日志7：处理前 =====
  const yAxes = Array.isArray(option.yAxis) ? option.yAxis : [option.yAxis];

  option.yAxis = yAxes.map((y) => {
    const processed = Object.assign({}, y || {}, {
      scale: y?.scale !== undefined ? y.scale : true,
      axisLabel: Object.assign({}, y?.axisLabel || {}, {
        color: theme.axisLabelColor,
        margin: (y?.axisLabel && y.axisLabel.margin) || 6,
        align: "right",
      }),
      axisLine: Object.assign({}, y?.axisLine || {}, {
        lineStyle: Object.assign(
          { color: theme.axisLineColor },
          y?.axisLine?.lineStyle || {}
        ),
      }),
      splitLine: Object.assign({}, y?.splitLine || {}, {
        lineStyle: Object.assign(
          { color: theme.gridLineColor },
          y?.splitLine?.lineStyle || {}
        ),
      }),
      // 显式保留 axisPointer
      axisPointer: y?.axisPointer,
    });

    return processed;
  });

  // ===== DataZoom配置 =====
  const labelFmt = (val) => {
    if (Array.isArray(dates) && dates.length) {
      const idx = Number(val);
      if (Number.isInteger(idx) && idx >= 0 && idx < dates.length) {
        return dates[idx];
      }
    }
    return formatTimeByFreq(freq, val);
  };

  const hasInitialRange =
    ui?.initialRange &&
    Number.isFinite(ui.initialRange.startValue) &&
    Number.isFinite(ui.initialRange.endValue);

  const initialRange = hasInitialRange
    ? {
        startValue: ui.initialRange.startValue,
        endValue: ui.initialRange.endValue,
      }
    : len
    ? { startValue: 0, endValue: len - 1 }
    : {};

  // NEW: 副图也补齐 slider，保证 dataZoom 结构一致；
  //      默认 sliderHeightPx=0 且 show=false，不在页面显示，仅用于联动信号接收。
  const nonMainSliderHeightPx =
    ui?.sliderHeightPx != null ? Number(ui.sliderHeightPx) : 0;

  option.dataZoom = isMain
    ? [
        Object.assign(
          { type: "inside" },
          initialRange,
          option.dataZoom && option.dataZoom[0] ? option.dataZoom[0] : {}
        ),
        Object.assign(
          {
            type: "slider",
            height: ui?.sliderHeightPx ?? MAIN_CHART_LAYOUT.SLIDER_HEIGHT_PX,
            bottom: 0,
            showDetail: true,
            labelFormatter: labelFmt,
          },
          initialRange,
          option.dataZoom && option.dataZoom[1] ? option.dataZoom[1] : {}
        ),
      ]
    : [
        Object.assign(
          { type: "inside" },
          initialRange,
          option.dataZoom && option.dataZoom[0] ? option.dataZoom[0] : {}
        ),
        Object.assign(
          {
            type: "slider",
            // 默认隐藏：高度为 0，且 show=false（不占视觉空间）
            show: false,
            height: nonMainSliderHeightPx,
            bottom: 0,
            showDetail: false,
            labelFormatter: labelFmt,
          },
          initialRange,
          // 若历史 option.dataZoom[1] 存在则合并（向后兼容，但不额外造逻辑）
          option.dataZoom && option.dataZoom[1] ? option.dataZoom[1] : {}
        ),
      ];

  return option;
}