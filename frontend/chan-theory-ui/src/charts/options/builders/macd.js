// src/charts/options/builders/macd.js
// ==============================
// 说明：MACD 副图 Option 构造器（使用集中预设 DEFAULT_MACD_SETTINGS）
// - 周期：由 engines/indicators.js 按 macdSettings.period 计算好 DIF/DEA/HIST
// - 本文件只负责：用 macdSettings.lines / macdSettings.hist 渲染样式
// - 本轮改动：柱宽仅由 hist.barPercent 决定，不再进行 BAR_USABLE_RATIO 缩放
//
// V2.1 - 删除未使用导入（getChartTheme）与未使用变量（theme）
// ==============================

import { DEFAULT_MACD_SETTINGS } from "@/constants";
import { makeMacdTooltipFormatter } from "../tooltips/index";
import { createTechSkeleton } from "../skeleton/tech";
import { formatNumberScaled } from "@/utils/numberUtils";

function asArray(x) {
  return Array.isArray(x) ? x : [];
}
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

export function buildMacdOption({ candles, indicators, freq, macdCfg }, ui) {
  const list = asArray(candles);
  const inds = asIndicators(indicators);
  const series = [];

  const cfg = macdCfg || DEFAULT_MACD_SETTINGS;
  const linesCfg = cfg.lines || DEFAULT_MACD_SETTINGS.lines;
  const histCfg = cfg.hist || DEFAULT_MACD_SETTINGS.hist;

  const hasDIF = Array.isArray(inds.MACD_DIF) && inds.MACD_DIF.length > 0;
  const hasDEA = Array.isArray(inds.MACD_DEA) && inds.MACD_DEA.length > 0;
  const hasHIST = Array.isArray(inds.MACD_HIST) && inds.MACD_HIST.length > 0;

  // ===== 柱体（HIST）=====
  if (histCfg.enabled && hasHIST) {
    const barPercent = Math.max(
      10,
      Math.min(
        100,
        Math.round(histCfg.barPercent ?? DEFAULT_MACD_SETTINGS.hist.barPercent)
      )
    );

    series.push({
      id: "MACD_HIST",
      type: "bar",
      name: "MACD",
      yAxisIndex: 0,
      data: inds.MACD_HIST,
      itemStyle: {
        color: (params) => {
          const idx = params.dataIndex || 0;
          const val = inds.MACD_HIST[idx];
          return Number(val) >= 0
            ? (histCfg.upColor ?? DEFAULT_MACD_SETTINGS.hist.upColor)
            : (histCfg.downColor ?? DEFAULT_MACD_SETTINGS.hist.downColor);
        },
      },
      barWidth: `${barPercent}%`, // ← 单一参数
      z: histCfg.z ?? DEFAULT_MACD_SETTINGS.hist.z,
    });
  }

  // ===== 折线（DIF / DEA）=====
  if (linesCfg.enabled && hasDIF && hasDEA) {
    series.push({
      id: "MACD_DIF",
      type: "line",
      name: "DIF",
      yAxisIndex: 0,
      data: inds.MACD_DIF,
      showSymbol: false,
      lineStyle: {
        width: linesCfg.width ?? DEFAULT_MACD_SETTINGS.lines.width,
        type: linesCfg.difStyle ?? DEFAULT_MACD_SETTINGS.lines.difStyle,
      },
      color: linesCfg.difColor ?? DEFAULT_MACD_SETTINGS.lines.difColor,
      z: linesCfg.z ?? DEFAULT_MACD_SETTINGS.lines.z,
    });

    series.push({
      id: "MACD_DEA",
      type: "line",
      name: "DEA",
      yAxisIndex: 0,
      data: inds.MACD_DEA,
      showSymbol: false,
      lineStyle: {
        width: linesCfg.width ?? DEFAULT_MACD_SETTINGS.lines.width,
        type: linesCfg.deaStyle ?? DEFAULT_MACD_SETTINGS.lines.deaStyle,
      },
      color: linesCfg.deaColor ?? DEFAULT_MACD_SETTINGS.lines.deaColor,
      z: linesCfg.z ?? DEFAULT_MACD_SETTINGS.lines.z,
    });
  }

  const option = createTechSkeleton(
    {
      candles: list,
      freq,
      tooltipFormatter: makeMacdTooltipFormatter({ freq }),
    },
    ui,
    (val) => formatNumberScaled(val, { digits: 3, allowEmpty: true })
  );

  option.series = series;
  return option;
}