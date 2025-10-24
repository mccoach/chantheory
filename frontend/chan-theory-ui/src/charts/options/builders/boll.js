// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options\builders\boll.js
// ==============================
// 说明：BOLL 窗 option 构造器（MID/UPPER/LOWER 三线）
// - tooltip 内容统一来自 tooltips 模块；position 由外部 ui.tooltipPositioner 注入
// - 仅联动 X 轴（竖线），不联动 Y 轴（水平线）
// - FIX: 精确控制双Y轴的 axisPointer 可见性，实现“悬浮窗十字，其余竖线”效果。
// ==============================

import { getChartTheme } from "@/charts/theme";
import { STYLE_PALETTE } from "@/constants";
import { applyUi } from "../ui/applyUi";
import { formatNumberScaled } from "@/utils/numberUtils";
import { makeBollTooltipFormatter } from "../tooltips/index";
import { createBaseTechOption } from "./common"; // NEW

function asArray(x) {
  return Array.isArray(x) ? x : [];
}
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

export function buildBollOption({ candles, indicators, freq }, ui) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const dates = list.map((d) => d.t);
  const series = [];

  if (inds.BOLL_MID && inds.BOLL_UPPER && inds.BOLL_LOWER) {
    series.push({
      id: "BOLL_MID",
      type: "line",
      name: "BOLL_MID",
      data: inds.BOLL_MID,
      showSymbol: false,
      lineStyle: { color: STYLE_PALETTE.lines[0].color, width: 1 },
      itemStyle: { color: STYLE_PALETTE.lines[0].color },
      color: STYLE_PALETTE.lines[0].color,
    });
    series.push({
      id: "BOLL_UPPER",
      type: "line",
      name: "BOLL_UPPER",
      data: inds.BOLL_UPPER,
      showSymbol: false,
      lineStyle: { color: STYLE_PALETTE.lines[2].color, width: 1 },
      itemStyle: { color: STYLE_PALETTE.lines[2].color },
      color: STYLE_PALETTE.lines[2].color,
    });
    series.push({
      id: "BOLL_LOWER",
      type: "line",
      name: "BOLL_LOWER",
      data: inds.BOLL_LOWER,
      showSymbol: false,
      lineStyle: { color: STYLE_PALETTE.lines[3].color, width: 1 },
      itemStyle: { color: STYLE_PALETTE.lines[3].color },
      color: STYLE_PALETTE.lines[3].color,
    });
  }

  // MODIFIED: Use createBaseTechOption to generate the skeleton
  const option = createBaseTechOption(
    {
      dates,
      freq,
      tooltipFormatter: makeBollTooltipFormatter({ freq }),
    },
    ui
  );

  // Fill in the series
  option.series = series;

  return option;
}
