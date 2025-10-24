// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options\ui\applyUi.js
// ==============================
// 说明：通用 UI 合并器（grid/xAxis/yAxis/dataZoom/axisLabelFormatter）
// - 由各 builders 统一调用；不包含业务特有字段
// - 仅依赖主题与时间格式化工具
// ==============================

import { getChartTheme } from "@/charts/theme";
import { fmtTimeByFreq, makeAxisLabelFormatter } from "@/utils/timeFormat";

const LAYOUT = {
  LEFT_MARGIN_PX: 64,
  RIGHT_MARGIN_PX: 10,
  SLIDER_HEIGHT_PX: 26,
  MAIN_AXIS_LABEL_SPACE_PX: 30,
  MAIN_BOTTOM_EXTRA_PX: 2,
};

export function applyUi(option, ui, { dates, freq }) {
  const theme = getChartTheme();

  const leftPx = ui?.leftPx ?? LAYOUT.LEFT_MARGIN_PX;
  const rightPx = ui?.rightPx ?? LAYOUT.RIGHT_MARGIN_PX;
  const isMain = !!ui?.isMain;
  const nonMainExtra = ui?.extraBottomPx ? Number(ui.extraBottomPx) : 0;
  const gridBottom = isMain
    ? (ui?.sliderHeightPx ?? LAYOUT.SLIDER_HEIGHT_PX) +
      (ui?.mainAxisLabelSpacePx ?? LAYOUT.MAIN_AXIS_LABEL_SPACE_PX) +
      (ui?.mainBottomExtraPx ?? LAYOUT.MAIN_BOTTOM_EXTRA_PX)
    : nonMainExtra;

  option.grid = {
    left: leftPx,
    right: rightPx,
    top: 0,
    bottom: gridBottom,
    containLabel: false,
  };

  const len = Array.isArray(dates) ? dates.length : 0;

  option.xAxis = Object.assign({}, option.xAxis || {}, {
    type: "category",
    data: option.xAxis?.data || dates || [],
    boundaryGap: ["0%", "0%"],
    axisTick: Object.assign({}, option.xAxis?.axisTick || {}, {
      alignWithLabel: true,
    }),
    axisLabel: Object.assign({}, option.xAxis?.axisLabel || {}, {
      color: theme.axisLabelColor,
      margin: ui?.xAxisLabelMargin ?? 6,
      formatter: makeAxisLabelFormatter(freq),
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

  const yAxes = Array.isArray(option.yAxis) ? option.yAxis : [option.yAxis];
  option.yAxis = yAxes.map((y) =>
    Object.assign({}, y || {}, {
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
    })
  );

  const labelFmt = (val) => {
    if (Array.isArray(dates) && dates.length) {
      const idx = Number(val);
      if (Number.isInteger(idx) && idx >= 0 && idx < dates.length) {
        return fmtTimeByFreq(freq, dates[idx]);
      }
    }
    return fmtTimeByFreq(freq, val);
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
            height: ui?.sliderHeightPx ?? LAYOUT.SLIDER_HEIGHT_PX,
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
      ];

  return option;
}