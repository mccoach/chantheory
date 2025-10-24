// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options\builders\macd.js
// ==============================
// 说明：MACD 窗 option 构造器（HIST 柱 + DIF/DEA 线）
// - tooltip 内容统一来自 tooltips 模块；position 由外部 ui.tooltipPositioner 注入
// - 仅联动 X 轴（竖线），不联动 Y 轴（水平线）
// - FIX: 精确控制双Y轴的 axisPointer 可见性，实现“悬浮窗十字，其余竖线”效果。
// ==============================

import { getChartTheme } from "@/charts/theme";
import { STYLE_PALETTE } from "@/constants";
import { applyUi } from "../ui/applyUi";
import { makeMacdTooltipFormatter } from "../tooltips/index";
import { createBaseTechOption } from "./common"; // NEW

function asArray(x) {
  return Array.isArray(x) ? x : [];
}
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

export function buildMacdOption({ candles, indicators, freq }, ui) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const dates = list.map((d) => d.t);
  const series = [];

  if (inds.MACD_DIF && inds.MACD_DEA && inds.MACD_HIST) {
    series.push({
      id: "MACD_HIST",
      type: "bar",
      name: "MACD_HIST",
      data: inds.MACD_HIST,
      itemStyle: {
        color: (p) =>
          Number(p.data) >= 0
            ? STYLE_PALETTE.bars.macd.positive
            : STYLE_PALETTE.bars.macd.negative,
      },
    });
    series.push({
      id: "MACD_DIF",
      type: "line",
      name: "DIF",
      data: inds.MACD_DIF,
      showSymbol: false,
      lineStyle: { color: STYLE_PALETTE.lines[0].color, width: 1 },
      itemStyle: { color: STYLE_PALETTE.lines[0].color },
      color: STYLE_PALETTE.lines[0].color,
    });
    series.push({
      id: "MACD_DEA",
      type: "line",
      name: "DEA",
      data: inds.MACD_DEA,
      showSymbol: false,
      lineStyle: { color: STYLE_PALETTE.lines[2].color, width: 1 },
      itemStyle: { color: STYLE_PALETTE.lines[2].color },
      color: STYLE_PALETTE.lines[2].color,
    });
  }

  // MODIFIED: Use createBaseTechOption to generate the skeleton
  const option = createBaseTechOption(
    {
      dates,
      freq,
      tooltipFormatter: makeMacdTooltipFormatter({ freq }),
    },
    ui
  );

  // Fill in the series
  option.series = series;

  return option;
}
