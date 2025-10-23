// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options\builders\volume.js
// ==============================
// 说明：量窗 option 构造器（成交量/成交额）
// - 柱 + MAVOL + 放/缩量标记（尺寸来源 DEFAULT_VOL_MARKER_SIZE）
// - tooltip 内容统一来自 tooltips 模块；position 由外部 ui.tooltipPositioner 注入
// - 仅联动 X 轴（竖线），不联动 Y 轴（水平线）
// - FIX: 精确控制双Y轴的 axisPointer 可见性，实现“悬浮窗十字，其余竖线”效果。
// ==============================

import { getChartTheme } from "@/charts/theme";
import { formatNumberScaled } from "@/utils/numberUtils";
import {
  STYLE_PALETTE,
  DEFAULT_VOL_SETTINGS,
  DEFAULT_VOL_MARKER_SIZE,
} from "@/constants";
import { applyUi } from "../ui/applyUi";
import { makeVolumeTooltipFormatter } from "../tooltips/index";

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
  const dates = list.map((d) => d.t);

  // 基础数据（量/额）
  const baseMode = volCfg && volCfg.mode === "amount" ? "amount" : "vol";
  const baseName = baseMode === "amount" ? "AMOUNT" : "VOL";
  const baseRaw =
    baseMode === "amount"
      ? list.map((d) => (typeof d.a === "number" ? d.a : null))
      : inds.VOLUME || list.map((d) => (typeof d.v === "number" ? d.v : null));

  // 柱系列
  const series = [];
  const vb = volCfg?.volBar || {};
  const barPercent = Number.isFinite(+vb.barPercent)
    ? Math.max(10, Math.min(100, Math.round(+vb.barPercent)))
    : 100;
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
    ...(barPercent && barPercent !== 100 ? { barWidth: `${barPercent}%` } : {}),
  });

  // MAVOL 线
  const namePrefixCN = baseMode === "amount" ? "额MA" : "量MA";
  const mstyles = volCfg?.mavolStyles || {};
  // `periods` 仅用于渲染显示的均线
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

  // 放/缩量标记尺寸估算（按可视柱宽）
  const hostW = Math.max(1, Number(volEnv?.hostWidth || 0));
  const visCount = Math.max(1, Number(volEnv?.visCount || baseScaled.length));
  const overrideW = Number(volEnv?.overrideMarkWidth);
  const approxBarWidthPx =
    hostW > 1 && visCount > 0
      ? Math.max(
          1,
          Math.floor(((hostW * 0.88) / visCount) * (barPercent / 100))
        )
      : 8;
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

  // 1. 从所有已配置的均线中（无论是否启用）找到周期最小的一条作为标记计算的基准。
  const allConfiguredPeriods = Object.values(volCfg?.mavolStyles || {})
      .filter(s => s && Number.isFinite(+s.period) && +s.period > 0)
      .sort((a, b) => +a.period - +b.period);
  
  const primPeriodForMarkers = allConfiguredPeriods.length ? +allConfiguredPeriods[0].period : null;

  // 2. 独立计算这条基准均线的SMA序列，仅用于标记判断。
  let primSeriesForMarkers = null;
  if (primPeriodForMarkers) {
      // 如果该均线已被启用并计算过，直接复用；否则，单独计算一次。
      if (mavolMap[primPeriodForMarkers]) {
          primSeriesForMarkers = mavolMap[primPeriodForMarkers];
      } else {
          primSeriesForMarkers = sma(baseScaled, primPeriodForMarkers);
      }
  }

  // 放/缩量散点
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

  // FIX-1: 使用独立计算的 `primSeriesForMarkers` 作为基准，不再依赖于显示的均线。
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
      yAxisIndex: 1, // 绑定到第二Y轴
      data: pumpPts,
      symbol: volCfg?.markerPump?.shape || "triangle",
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
      yAxisIndex: 1, // 绑定到第二Y轴
      data: dumpPts,
      symbol: volCfg?.markerDump?.shape || "diamond",
      symbolRotate: 180, // 缩量标记符号旋转180度
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

  // 顶部空间与横轴 margin（按是否有标记略作增加）
  const anyMarkers =
    (pumpEnabled && pumpPts.length > 0) || (dumpEnabled && dumpPts.length > 0);
  const extraBottomPx = anyMarkers ? offsetDownPx : 0;
  const xAxisLabelMargin = anyMarkers ? offsetDownPx + 12 : 12;

  const option = {
    animation: false,
    backgroundColor: theme.backgroundColor,
    axisPointer: {
      link: [{ xAxisIndex: "all" }],
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      appendToBody: false,
      confine: true,
      formatter: makeVolumeTooltipFormatter({
        candles: list,
        freq,
        baseName,
        mavolMap,
      }),
      className: "ct-fixed-tooltip",
      borderWidth: 0,
      backgroundColor: "rgba(20,20,20,0.85)",
      textStyle: { color: theme.textColor, fontSize: 12, align: "left" },
    },
    xAxis: { type: "category", data: dates },
    yAxis: [
      {
        min: 0,
        scale: true,
        axisLabel: {
          color: theme.axisLabelColor,
          align: "right",
          formatter: (val) => formatNumberScaled(val, { minIntDigitsToScale: 5 }),
          margin: ui?.isHovered ? 6 : 6,
        },
        axisPointer: {
          show: true, // 保持为 true, 由 link 机制统一控制
          label: { show: !!ui?.isHovered },
          // FIX: 通过颜色控制可见性, 悬浮时可见, 否则透明
          lineStyle: {
            color: ui?.isHovered ? theme.axisLineColor : "transparent",
          },
        },
      },
      {
        type: "value",
        min: 0,
        max: 1,
        show: false,
        scale: false,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        // FIX: 显式禁用第二Y轴的指针
        axisPointer: {
          show: false,
        },
      }
    ],
    series,
  };

  if (ui?.tooltipPositioner) {
    option.tooltip.position = ui.tooltipPositioner;
  }

  return applyUi(
    option,
    {
      ...ui,
      isMain: false,
      extraBottomPx,
      xAxisLabelMargin,
      leftPx: 72,
    },
    { dates, freq }
  );
}
