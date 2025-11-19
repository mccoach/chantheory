// src/charts/options/builders/volume.js
// ==============================
// V10.0 - 架构统一版（复用 tech.js）
// + 柱体 barWidth 按 BAR_USABLE_RATIO 缩放，预留基础间隙
// ==============================

import { getChartTheme } from "@/charts/theme";
import { formatNumberScaled } from "@/utils/numberUtils";
import {
  STYLE_PALETTE,
  DEFAULT_VOL_SETTINGS,
  DEFAULT_VOL_MARKER_SIZE,
  BAR_USABLE_RATIO, // 统一柱体可用宽度比例
} from "@/constants";
import { makeVolumeTooltipFormatter } from "../tooltips/index";
import { createTechSkeleton } from "../skeleton/tech"; // 复用骨架
import { applyLayout } from "../positioning/layout"; // 覆盖布局

function asArray(x) {
  return Array.isArray(x) ? x : [];
}
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

export function buildVolumeOption(
  { candles, indicators, freq, volCfg, volEnv },
  ui
) {
  const theme = getChartTheme();
  const list = asArray(candles);
  const inds = asIndicators(indicators);

  const baseMode = volCfg && volCfg.mode === "amount" ? "amount" : "vol";
  const baseName = baseMode === "amount" ? "AMOUNT" : "VOL";
  const baseRaw =
    baseMode === "amount"
      ? list.map((d) => (typeof d.a === "number" ? d.a : null))
      : inds.VOLUME || list.map((d) => (typeof d.v === "number" ? d.v : null));

  // ===== 构造 series（量窗特有逻辑）=====
  const series = [];
  const vb = volCfg?.volBar || {};
  const barPercent = Number.isFinite(+vb.barPercent)
    ? Math.max(10, Math.min(100, Math.round(+vb.barPercent)))
    : 100;

  // 统一柱体宽度：通过 BAR_USABLE_RATIO 预留基础间隙
  // 即便用户配置 100%，实际 barWidth 也只占 BAR_USABLE_RATIO * 100%，避免挤成一团。
  const effectiveBarWidthPercent = Math.max(
    1,
    Math.min(100, Math.round(barPercent * BAR_USABLE_RATIO))
  );

  const upColor = vb.upColor || STYLE_PALETTE.bars.volume.up;
  const downColor = vb.downColor || STYLE_PALETTE.bars.volume.down;
  const baseScaled = baseRaw.map((v) => (Number.isFinite(+v) ? +v : null));

  series.push({
    id: baseName,
    type: "bar",
    name: baseName,
    data: baseScaled,
    itemStyle: {
      color: (p) => {
        const idx = p.dataIndex || 0;
        const k = list[idx] || {};
        return Number(k.c) >= Number(k.o) ? upColor : downColor;
      },
    },
    barWidth: `${effectiveBarWidthPercent}%`, // ← 使用缩放后的柱宽
  });

  const namePrefixCN = baseMode === "amount" ? "额MA" : "量MA";
  const mstyles = volCfg?.mavolStyles || {};
  const periods = Object.keys(mstyles)
    .map((k) => mstyles[k])
    .filter(
      (s) => s && s.enabled && Number.isFinite(+s.period) && +s.period > 0
    )
    .sort((a, b) => +a.period - +b.period);

  function sma(arr, n) {
    const out = new Array(arr.length).fill(null);
    if (!Array.isArray(arr) || !arr.length || !Number.isFinite(+n) || n <= 0)
      return out;
    let sum = 0,
      cnt = 0;
    for (let i = 0; i < arr.length; i++) {
      const v = Number(arr[i]);
      if (Number.isFinite(v)) {
        sum += v;
        cnt += 1;
      }
      if (i >= n) {
        const ov = Number(arr[i - n]);
        if (Number.isFinite(ov)) {
          sum -= ov;
          cnt -= 1;
        }
      }
      out[i] = cnt > 0 && i >= n - 1 ? sum / cnt : null;
    }
    return out;
  }

  const mavolMap = {};
  for (const st of periods) {
    mavolMap[+st.period] = sma(baseScaled, +st.period);
  }
  for (const st of periods) {
    const n = +st.period;
    const lineColor = st.color || STYLE_PALETTE.lines[0].color;
    series.push({
      id: `MAVOL-${n}`,
      type: "line",
      name: `${namePrefixCN}${n}`,
      data: mavolMap[n],
      showSymbol: false,
      smooth: false,
      lineStyle: {
        width: Number.isFinite(+st.width) ? +st.width : 1,
        type: st.style || "solid",
        color: lineColor,
      },
      itemStyle: { color: lineColor },
      color: lineColor,
      z: 3,
    });
  }

  // ===== 标记尺寸计算（量窗特有）=====
  const hostW = Math.max(1, Number(volEnv?.hostWidth || 0));
  const visCount = Math.max(1, Number(volEnv?.visCount || baseScaled.length));
  const overrideW = Number(volEnv?.overrideMarkWidth);
  const layoutCfg = DEFAULT_VOL_SETTINGS.layout;
  const approxBarWidthPx =
    hostW > 1 && visCount > 0
      ? Math.max(
          1,
          Math.floor(
            ((hostW *
              (layoutCfg.barUsableRatio ?? BAR_USABLE_RATIO)) /
              visCount) *
              (barPercent / 100)
          )
        )
      : layoutCfg.fallbackBarWidth;
  const MARKER_W_MIN = DEFAULT_VOL_MARKER_SIZE.minPx;
  const MARKER_W_MAX = DEFAULT_VOL_MARKER_SIZE.maxPx;
  const markerW = Number.isFinite(overrideW)
    ? Math.max(MARKER_W_MIN, Math.min(MARKER_W_MAX, Math.round(overrideW)))
    : Math.max(
        MARKER_W_MIN,
        Math.min(MARKER_W_MAX, Math.round(approxBarWidthPx))
      );
  const markerH = DEFAULT_VOL_MARKER_SIZE.markerHeightPx;
  const markerYOffset = DEFAULT_VOL_MARKER_SIZE.markerYOffsetPx;
  const offsetDownPx = Math.round(markerH + markerYOffset);
  const symbolOffsetBelow = [0, offsetDownPx];

  // ===== 标记计算（量窗特有）=====
  const allConfiguredPeriods = Object.values(volCfg?.mavolStyles || {})
    .filter((s) => s && Number.isFinite(+s.period) && +s.period > 0)
    .sort((a, b) => +a.period - +b.period);

  const primPeriodForMarkers = allConfiguredPeriods.length
    ? +allConfiguredPeriods[0].period
    : null;

  let primSeriesForMarkers = null;
  if (primPeriodForMarkers) {
    if (mavolMap[primPeriodForMarkers]) {
      primSeriesForMarkers = mavolMap[primPeriodForMarkers];
    } else {
      primSeriesForMarkers = sma(baseScaled, primPeriodForMarkers);
    }
  }

  const pumpK = Number.isFinite(+volCfg?.markerPump?.threshold)
    ? +volCfg.markerPump.threshold
    : DEFAULT_VOL_SETTINGS.markerPump.threshold;
  const dumpK = Number.isFinite(+volCfg?.markerDump?.threshold)
    ? +volCfg.markerDump.threshold
    : DEFAULT_VOL_SETTINGS.markerDump.threshold;
  const pumpEnabled = (volCfg?.markerPump?.enabled ?? true) === true;
  const dumpEnabled = (volCfg?.markerDump?.enabled ?? true) === true;
  const pumpPts = [];
  const dumpPts = [];

  if (primSeriesForMarkers) {
    if (pumpEnabled && pumpK > 0) {
      for (let i = 0; i < baseScaled.length; i++) {
        const v = baseScaled[i],
          m = primSeriesForMarkers[i];
        if (!Number.isFinite(v) || !Number.isFinite(m) || m <= 0) continue;
        if (v >= pumpK * m) pumpPts.push([i, 0]);
      }
    }
    if (dumpEnabled && dumpK > 0) {
      for (let i = 0; i < baseScaled.length; i++) {
        const v = baseScaled[i],
          m = primSeriesForMarkers[i];
        if (!Number.isFinite(v) || !Number.isFinite(m) || m <= 0) continue;
        if (v <= dumpK * m) dumpPts.push([i, 0]);
      }
    }
  }

  if (pumpEnabled && pumpPts.length) {
    series.push({
      id: "VOL_PUMP_MARK",
      type: "scatter",
      name: "放量标记",
      yAxisIndex: 1, // ← 使用标记专用轴
      data: pumpPts,
      symbol:
        volCfg?.markerPump?.shape || DEFAULT_VOL_SETTINGS.markerPump.shape,
      symbolSize: () => [markerW, markerH],
      symbolOffset: symbolOffsetBelow,
      itemStyle: {
        color:
          volCfg?.markerPump?.color || DEFAULT_VOL_SETTINGS.markerPump.color,
      },
      silent: true,
      z: 4,
    });
  }
  if (dumpEnabled && dumpPts.length) {
    series.push({
      id: "VOL_DUMP_MARK",
      type: "scatter",
      name: "缩量标记",
      yAxisIndex: 1, // ← 使用标记专用轴
      data: dumpPts,
      symbol:
        volCfg?.markerDump?.shape || DEFAULT_VOL_SETTINGS.markerDump.shape,
      symbolRotate: 180,
      symbolSize: () => [markerW, markerH],
      symbolOffset: symbolOffsetBelow,
      itemStyle: {
        color:
          volCfg?.markerDump?.color || DEFAULT_VOL_SETTINGS.markerDump.color,
      },
      silent: true,
      z: 4,
    });
  }

  // ===== 复用 tech.js 骨架 =====
  const option = createTechSkeleton(
    {
      candles: list,
      freq,
      tooltipFormatter: makeVolumeTooltipFormatter({
        candles: list,
        freq,
        baseName,
        mavolMap,
      }),
    },
    ui,
    (val) => formatNumberScaled(val, { minIntDigitsToScale: 5 })
  );

  // ===== 诊断日志3：volume.js 获取骨架后 =====
  console.log("[DIAG][volume.js] createTechSkeleton 返回", {
    yAxis数量: option.yAxis?.length,
    yAxis1_axisPointer: JSON.stringify(option.yAxis?.[1]?.axisPointer),
    yAxis1_完整: option.yAxis?.[1],
  });

  // 填充 series
  option.series = series;

  // ===== 诊断日志4：series 填充后 =====
  console.log("[DIAG][volume.js] series 填充后", {
    series数量: option.series?.length,
    使用yAxisIndex1的series: option.series
      ?.filter((s) => s.yAxisIndex === 1)
      .map((s) => s.id),
    yAxis1_axisPointer: JSON.stringify(option.yAxis?.[1]?.axisPointer),
  });

  // ===== 覆盖布局参数（量窗特有的底部间距）=====
  const anyMarkers =
    (pumpEnabled && pumpPts.length > 0) || (dumpEnabled && dumpPts.length > 0);
  const extraBottomPx = anyMarkers ? offsetDownPx : 0;
  const xAxisLabelMargin = anyMarkers ? offsetDownPx + 12 : 12;

  const finalOption = applyLayout(
    option,
    {
      ...ui,
      isMain: false,
      extraBottomPx,
      xAxisLabelMargin,
      leftPx: 72,
    },
    { candles: list, freq }
  );

  // ===== 诊断日志5：最终 applyLayout 后 =====
  console.log("[DIAG][volume.js] 最终 applyLayout 后", {
    yAxis数量: finalOption.yAxis?.length,
    yAxis1_axisPointer: JSON.stringify(finalOption.yAxis?.[1]?.axisPointer),
    yAxis1_完整: finalOption.yAxis?.[1],
  });

  // ===== 诊断日志6：最终返回前 =====
  console.log("[DIAG][volume.js] 最终返回配置", {
    完整yAxis配置: JSON.stringify(finalOption.yAxis, null, 2),
  });

  return finalOption;
}
