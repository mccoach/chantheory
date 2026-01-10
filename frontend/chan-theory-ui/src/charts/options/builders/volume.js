// src/charts/options/builders/volume.js
// ==============================
// V17.0 - 量窗放/缩量标记回归：一次性全量落地 + 超限保右端完整
// 说明：
//   - 点集在 builder 阶段一次性全量计算并落地到 series.data；
//   - dataZoom 平移不触发任何业务 patch；
//   - 超限上限归入 DEFAULT_VOL_SETTINGS.markerLimit.maxPoints；
//   - 超限策略：保右端（最新）完整，截断左侧（更早期）。
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

function buildPrefixSum(arr) {
  const out = new Array(arr.length);
  let sum = 0;
  for (let i = 0; i < arr.length; i++) {
    const v = Number(arr[i]);
    if (Number.isFinite(v)) sum += v;
    out[i] = sum;
  }
  return out;
}

function smaAt(i, n, prefixSum) {
  if (i < n - 1) return null;
  const a = prefixSum[i] - (i - n >= 0 ? prefixSum[i - n] : 0);
  return a / n;
}

function pickMinEnabledPeriod(mavolStyles) {
  let minP = null;
  const obj = mavolStyles && typeof mavolStyles === "object" ? mavolStyles : {};
  for (const v of Object.values(obj)) {
    if (!v || v.enabled !== true) continue;
    const p = Number(v.period);
    if (!Number.isFinite(p) || p <= 0) continue;
    if (minP == null || p < minP) minP = p;
  }
  return minP;
}

function capPointsKeepRight(arr, maxN) {
  const a = Array.isArray(arr) ? arr : [];
  const cap = Math.max(1, Math.floor(Number(maxN || 1)));
  if (a.length <= cap) return a;
  return a.slice(a.length - cap);
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

  // ===== marker series：点集在 builder 阶段一次性全量落地 =====
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

  const maxPts = Number(
    volCfg?.markerLimit?.maxPoints ??
    DEFAULT_VOL_SETTINGS.markerLimit?.maxPoints ??
    20000
  );

  let pumpPtsRaw = [];
  let dumpPtsRaw = [];

  if ((pumpEnabled || dumpEnabled) && list.length) {
    const primN = pickMinEnabledPeriod(volCfg?.mavolStyles);
    const pumpK = Number.isFinite(+volCfg?.markerPump?.threshold)
      ? +volCfg.markerPump.threshold
      : DEFAULT_VOL_SETTINGS.markerPump.threshold;
    const dumpK = Number.isFinite(+volCfg?.markerDump?.threshold)
      ? +volCfg.markerDump.threshold
      : DEFAULT_VOL_SETTINGS.markerDump.threshold;

    if (primN && primN > 0) {
      const prefix = buildPrefixSum(baseScaled);

      const pArr = [];
      const dArr = [];

      for (let i = 0; i < baseScaled.length; i++) {
        const v = Number(baseScaled[i]);
        if (!Number.isFinite(v)) continue;

        const m = smaAt(i, primN, prefix);
        if (!Number.isFinite(m) || m <= 0) continue;

        if (pumpEnabled && pumpK > 0 && v >= pumpK * m) pArr.push([i, 0]);
        if (dumpEnabled && dumpK > 0 && v <= dumpK * m) dArr.push([i, 0]);
      }

      pumpPtsRaw = pArr;
      dumpPtsRaw = dArr;
    }
  }

  const pumpPts = capPointsKeepRight(pumpPtsRaw, maxPts);
  const dumpPts = capPointsKeepRight(dumpPtsRaw, maxPts);

  if (pumpEnabled) {
    series.push({
      id: "VOL_PUMP_MARK",
      type: "scatter",
      name: "放量标记",
      yAxisIndex: 1,
      data: pumpPts,
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
      data: dumpPts,
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
        volCfg,
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
