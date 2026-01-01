// src/charts/options/builders/volume.js
// ==============================
// V15.0 - 放/缩量点集迁移到实例侧 MarkerPointsController（去掉 builder 全量扫描 O(N)）
// 改动：
//   - 删除 pumpPts/dumpPts 的全量扫描逻辑（O(N)）
//   - marker series 仍保留（用于渲染），data 初始为空；点集由实例侧最小 patch 更新
//   - marker symbolSize 仍读取 widthState（宽度由 WidthController 管理）
// ==============================

import { getChartTheme } from "@/charts/theme";
import { formatNumberScaled } from "@/utils/numberUtils";
import {
  STYLE_PALETTE,
  DEFAULT_VOL_SETTINGS,
  DEFAULT_VOL_MARKER_SIZE,
} from "@/constants";
import { makeVolumeTooltipFormatter } from "../tooltips/index";
import { createTechSkeleton } from "../skeleton/tech";
import { applyLayout } from "../positioning/layout";
import { getWidthPx } from "@/charts/width/widthState";

function asArray(x) {
  return Array.isArray(x) ? x : [];
}
function asIndicators(x) {
  return x && typeof x === "object" ? x : {};
}

export function buildVolumeOption(
  { candles, indicators, freq, volCfg },
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
    barWidth: `${barPercent}%`,
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

  // ===== marker series：仅保留形状/颜色/offset/宽度读取；点集由实例侧 patch =====
  const markerH = DEFAULT_VOL_MARKER_SIZE.markerHeightPx;
  const markerYOffset = DEFAULT_VOL_MARKER_SIZE.markerYOffsetPx;
  const offsetDownPx = Math.round(markerH + markerYOffset);
  const symbolOffsetBelow = [0, offsetDownPx];

  const paneId = ui?.paneId != null ? String(ui.paneId) : "";
  const widthKey = paneId ? `indicator:${paneId}:volMarker` : "vol:marker";
  const fallbackW = Math.max(1, DEFAULT_VOL_MARKER_SIZE.minPx);
  const markerW = () => getWidthPx(widthKey, fallbackW);

  const pumpEnabled = (volCfg?.markerPump?.enabled ?? true) === true;
  const dumpEnabled = (volCfg?.markerDump?.enabled ?? true) === true;

  if (pumpEnabled) {
    series.push({
      id: "VOL_PUMP_MARK",
      type: "scatter",
      name: "放量标记",
      yAxisIndex: 1,
      data: [], // 点集由实例侧 MarkerPointsController patch
      symbol:
        volCfg?.markerPump?.shape || DEFAULT_VOL_SETTINGS.markerPump.shape,
      symbolSize: () => [markerW(), markerH],
      symbolOffset: symbolOffsetBelow,
      itemStyle: {
        color:
          volCfg?.markerPump?.color || DEFAULT_VOL_SETTINGS.markerPump.color,
      },
      silent: true,
      z: 4,
    });
  }

  if (dumpEnabled) {
    series.push({
      id: "VOL_DUMP_MARK",
      type: "scatter",
      name: "缩量标记",
      yAxisIndex: 1,
      data: [], // 点集由实例侧 MarkerPointsController patch
      symbol:
        volCfg?.markerDump?.shape || DEFAULT_VOL_SETTINGS.markerDump.shape,
      symbolRotate: 180,
      symbolSize: () => [markerW(), markerH],
      symbolOffset: symbolOffsetBelow,
      itemStyle: {
        color:
          volCfg?.markerDump?.color || DEFAULT_VOL_SETTINGS.markerDump.color,
      },
      silent: true,
      z: 4,
    });
  }

  const option = createTechSkeleton(
    {
      candles: list,
      freq,
      tooltipFormatter: makeVolumeTooltipFormatter({
        candles: list,
        freq,
        baseName,
        mavolMap,
        volCfg, // NEW: tooltip 内按 idx 计算放/缩状态
      }),
    },
    ui,
    (val) => formatNumberScaled(val, { minIntDigitsToScale: 5 })
  );

  option.series = series;

  const anyMarkers = pumpEnabled || dumpEnabled;
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

  return finalOption;
}
