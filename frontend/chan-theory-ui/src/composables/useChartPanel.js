// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useChartPanel.js
// ==============================
// V7.1 - 主图 barPercentReader 去冗余：不再从 chart.getOption() 反解，改为直接读 settings
//
// 背景：
//   - 主图柱宽% 的唯一真相源是 settings.chartDisplay.klineStyle.barPercent（builder 明确设置 barWidth）
//   - WidthController 继续从 option 反解属于重复路径
//
// 本轮改动：
//   - isMain 分支 barPercentReader 改为读取 settings.chartDisplay.klineStyle.barPercent
//   - 移除 createMainBarPercentReader 的 import（避免死代码）
//   - 其它逻辑保持不变（完美回归）
// ==============================

import {
  ref,
  computed,
  onMounted,
  onBeforeUnmount,
  watch,
  nextTick,
} from "vue";
import * as echarts from "echarts";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useUserSettings } from "@/composables/useUserSettings";

import { createWidthController } from "@/charts/width/widthController";
import { createVolumeMarkerPointsController } from "@/charts/markers/markerPointsController";
import {
  FRACTAL_MARKER_WIDTH_PX_LIMITS,
  UPDOWN_MARKER_WIDTH_PX_LIMITS,
  VOL_MARKER_WIDTH_PX_LIMITS,
} from "@/constants";

function clampInt(n, min, max) {
  const x = Math.round(Number(n));
  if (!Number.isFinite(x)) return min;
  return Math.max(min, Math.min(max, x));
}

export function useChartPanel({ panelKey, vm, hub, renderHub, onChartReady, getPanelKind }) {
  const wrapRef = ref(null);
  const hostRef = ref(null);
  const chart = ref(null);

  const { findBySymbol } = useSymbolIndex();
  const settings = useUserSettings();

  let ro = null;

  let _widthCtl = null;
  let _markerPtsCtl = null;

  function safeResize() {
    if (!chart.value || !hostRef.value) return;
    requestAnimationFrame(() => {
      try {
        chart.value.resize({
          width: hostRef.value.clientWidth,
          height: hostRef.value.clientHeight,
        });
      } catch {}
    });
  }

  function scheduleWidthUpdate() {
    try {
      _widthCtl?.scheduleUpdate();
    } catch {}
  }

  function scheduleMarkerUpdate() {
    try {
      _markerPtsCtl?.scheduleUpdate();
    } catch {}
  }

  function disposeWidthController() {
    if (!_widthCtl) return;
    try {
      _widthCtl.dispose();
    } catch {}
    _widthCtl = null;
  }

  function disposeMarkerPointsController() {
    if (!_markerPtsCtl) return;
    try {
      _markerPtsCtl.dispose();
    } catch {}
    _markerPtsCtl = null;
  }

  function buildMainRefreshIdsGetter() {
    return () => {
      const out = [];

      const updownOn =
        (settings?.chanTheory?.chanSettings?.showUpDownMarkers ?? true) === true;
      if (updownOn) out.push("CHAN_UP", "CHAN_DOWN");

      const fr = settings?.chanTheory?.fractalSettings || {};
      const frEnabled = (fr.enabled ?? true) === true;
      if (frEnabled) {
        const sb = fr.styleByStrength || {};
        if ((sb.strong?.enabled ?? true) === true) out.push("FR_TOP_strong", "FR_BOT_strong");
        if ((sb.standard?.enabled ?? true) === true) out.push("FR_TOP_standard", "FR_BOT_standard");
        if ((sb.weak?.enabled ?? true) === true) out.push("FR_TOP_weak", "FR_BOT_weak");

        const cs = fr.confirmStyle || {};
        if ((cs.enabled ?? true) === true) out.push("FR_TOP_CONFIRM", "FR_BOT_CONFIRM");
      }

      return out;
    };
  }

  function buildVolRefreshIdsGetter() {
    return () => {
      const vs = settings?.chartDisplay?.volSettings || {};
      const pumpOn = (vs.markerPump?.enabled ?? true) === true;
      const dumpOn = (vs.markerDump?.enabled ?? true) === true;

      const out = [];
      if (pumpOn) out.push("VOL_PUMP_MARK");
      if (dumpOn) out.push("VOL_DUMP_MARK");
      return out;
    };
  }

  onMounted(() => {
    if (!hostRef.value) return;

    const instance = echarts.init(hostRef.value, null, {
      renderer: "canvas",
      width: hostRef.value.clientWidth,
      height: hostRef.value.clientHeight,
    });

    instance.group = "ct-sync";
    try {
      echarts.connect("ct-sync");
    } catch {}

    chart.value = instance;

    // 单一 dataZoom 入口（由 handleDataZoom 统一注入范围 + 调度宽度/点集）
    instance.on("dataZoom", handleDataZoom);

    const pk = String(panelKey?.value || panelKey || "");
    const isMain = pk === "main";
    const isIndicator = pk.startsWith("indicator:");

    if (isMain) {
      // PERF: 主图 barPercent 直接来自 settings（唯一真相源），不再从 option 反解
      const barPercentReader = () => {
        const bp = settings?.chartDisplay?.klineStyle?.barPercent;
        return clampInt(bp, 10, 100) || 88;
      };

      _widthCtl = createWidthController({
        chart: instance,
        getCandlesLen: () => {
          const arr = vm?.candles?.value || [];
          return Array.isArray(arr) ? arr.length : 0;
        },
        getBarPercent: barPercentReader,
        targets: [
          {
            key: "main:fractal",
            percent: () => settings?.chanTheory?.fractalSettings?.markerPercent,
            minPx: FRACTAL_MARKER_WIDTH_PX_LIMITS.minPx,
            maxPx: FRACTAL_MARKER_WIDTH_PX_LIMITS.maxPx,
            capToBar: true,
          },
          {
            key: "main:updown",
            percent: () => settings?.chanTheory?.chanSettings?.upDownMarkerPercent,
            minPx: UPDOWN_MARKER_WIDTH_PX_LIMITS.minPx,
            maxPx: UPDOWN_MARKER_WIDTH_PX_LIMITS.maxPx,
            capToBar: true,
          },
        ],
        refreshSeriesIds: buildMainRefreshIdsGetter(),
      });
    }

    if (isIndicator) {
      const paneId = pk.slice("indicator:".length);

      const barPercentReader = () => {
        const bp = settings?.chartDisplay?.volSettings?.volBar?.barPercent;
        return clampInt(bp, 10, 100) || 88;
      };

      const markerPercentReader = () => {
        const mp = settings?.chartDisplay?.volSettings?.markerPercent;
        return clampInt(mp, 50, 100) || 90;
      };

      const widthKey = `indicator:${paneId}:volMarker`;

      function isVolKindNow() {
        const k =
          typeof getPanelKind === "function"
            ? String(getPanelKind() || "").toUpperCase()
            : "";
        return k === "VOL" || k === "AMOUNT";
      }

      const baseSeriesCache = {
        candlesRef: null,
        kind: "",
        len: 0,
        series: null,
      };

      function getKindUpper() {
        return typeof getPanelKind === "function"
          ? String(getPanelKind() || "").toUpperCase()
          : "";
      }

      function getBaseSeriesCached() {
        const arr = vm?.candles?.value || [];
        if (!Array.isArray(arr) || !arr.length) {
          baseSeriesCache.candlesRef = null;
          baseSeriesCache.kind = "";
          baseSeriesCache.len = 0;
          baseSeriesCache.series = null;
          return null;
        }

        const kind = getKindUpper();
        const len = arr.length;

        if (
          baseSeriesCache.candlesRef === arr &&
          baseSeriesCache.kind === kind &&
          baseSeriesCache.len === len &&
          Array.isArray(baseSeriesCache.series) &&
          baseSeriesCache.series.length === len
        ) {
          return baseSeriesCache.series;
        }

        const baseMode = kind === "AMOUNT" ? "amount" : "vol";
        const series =
          baseMode === "amount"
            ? arr.map((d) => (typeof d?.a === "number" ? d.a : null))
            : arr.map((d) => (typeof d?.v === "number" ? d.v : null));

        baseSeriesCache.candlesRef = arr;
        baseSeriesCache.kind = kind;
        baseSeriesCache.len = len;
        baseSeriesCache.series = series;
        return series;
      }

      function ensureIndicatorControllers() {
        if (!isVolKindNow()) {
          disposeMarkerPointsController();
          disposeWidthController();
          baseSeriesCache.candlesRef = null;
          baseSeriesCache.kind = "";
          baseSeriesCache.len = 0;
          baseSeriesCache.series = null;
          return;
        }

        if (!_widthCtl) {
          _widthCtl = createWidthController({
            chart: instance,
            getCandlesLen: () => {
              const arr = vm?.candles?.value || [];
              return Array.isArray(arr) ? arr.length : 0;
            },
            getBarPercent: barPercentReader,
            targets: [
              {
                key: widthKey,
                percent: markerPercentReader,
                minPx: VOL_MARKER_WIDTH_PX_LIMITS.minPx,
                maxPx: VOL_MARKER_WIDTH_PX_LIMITS.maxPx,
                capToBar: true,
              },
            ],
            refreshSeriesIds: buildVolRefreshIdsGetter(),
          });
        }

        if (!_markerPtsCtl) {
          _markerPtsCtl = createVolumeMarkerPointsController({
            chart: instance,
            getCandles: () => (vm?.candles?.value || []),
            getVolCfg: () => settings?.chartDisplay?.volSettings || {},
            getBaseSeries: getBaseSeriesCached,
          });
        }
      }

      ensureIndicatorControllers();

      if (typeof getPanelKind === "function") {
        watch(
          () => String(getPanelKind() || "").toUpperCase(),
          () => {
            ensureIndicatorControllers();
          }
        );
      }
    }

    // ts->idx 缓存（按 candles 引用缓存）
    const tsIdxCache = {
      candlesRef: null,
      map: null,
    };

    function ensureTsIdxMap(arr) {
      if (!Array.isArray(arr) || !arr.length) {
        tsIdxCache.candlesRef = null;
        tsIdxCache.map = null;
        return null;
      }
      if (tsIdxCache.candlesRef === arr && tsIdxCache.map) return tsIdxCache.map;

      const m = new Map();
      for (let i = 0; i < arr.length; i++) {
        const ts = arr[i]?.ts;
        if (Number.isFinite(ts)) m.set(ts, i);
      }
      tsIdxCache.candlesRef = arr;
      tsIdxCache.map = m;
      return m;
    }

    instance.on("updateAxisPointer", (params) => {
      try {
        const list = vm.candles.value || [];
        const len = list.length;
        if (!len) return;

        let idx = -1;
        const sd = Array.isArray(params?.seriesData)
          ? params.seriesData.find((x) => Number.isFinite(x?.dataIndex))
          : null;

        if (sd && Number.isFinite(sd.dataIndex)) {
          idx = sd.dataIndex;
        } else {
          const xInfo = Array.isArray(params?.axesInfo)
            ? params.axesInfo.find((ai) => ai && ai.axisDim === "x")
            : null;
          const v = xInfo?.value;

          if (Number.isFinite(v)) {
            idx = Math.max(0, Math.min(len - 1, Number(v)));
          } else if (typeof v === "string" && v) {
            const targetDate = new Date(v).getTime();
            const map = ensureTsIdxMap(list);
            const hit = map ? map.get(targetDate) : undefined;
            idx = Number.isFinite(hit) ? hit : -1;
          }
        }

        if (idx >= 0 && idx < len) {
          renderHub?.syncFocusPosition?.(idx);
        }
      } catch {}
    });

    try {
      ro = new ResizeObserver(() => {
        safeResize();
        scheduleWidthUpdate();
      });
      ro.observe(hostRef.value);
    } catch {}

    requestAnimationFrame(() => {
      safeResize();
      scheduleWidthUpdate();
      scheduleMarkerUpdate();
    });

    if (typeof onChartReady === "function") {
      onChartReady(instance);
    }
  });

  onBeforeUnmount(() => {
    disposeMarkerPointsController();
    disposeWidthController();

    if (ro) {
      ro.disconnect();
      ro = null;
    }
    if (chart.value) {
      try {
        chart.value.dispose();
      } catch {}
      chart.value = null;
    }
  });

  let dragging = false,
    startY = 0,
    startH = 0;

  function onResizeHandleMove(e) {
    if (!dragging || !wrapRef.value) return;
    const next = Math.max(160, Math.min(800, startH + (e.clientY - startY)));
    wrapRef.value.style.height = `${Math.floor(next)}px`;
    safeResize();
  }

  function onResizeHandleUp() {
    dragging = false;
    window.removeEventListener("mousemove", onResizeHandleMove);
  }

  function onResizeHandleDown(e) {
    dragging = true;
    startY = e.clientY;
    startH = wrapRef.value?.clientHeight || 0;
    window.addEventListener("mousemove", onResizeHandleMove);
    window.addEventListener("mouseup", onResizeHandleUp, { once: true });
  }

  function handleDataZoom(params) {
    try {
      const info = params?.batch?.[0] || params || {};
      const arr = vm.candles.value || [];
      if (!arr.length) return;

      let sIdx, eIdx;

      if (
        typeof info.startValue !== "undefined" &&
        typeof info.endValue !== "undefined"
      ) {
        sIdx = Number(info.startValue);
        eIdx = Number(info.endValue);
      } else if (typeof info.start === "number" && typeof info.end === "number") {
        const maxIdx = arr.length - 1;
        sIdx = Math.round((info.start / 100) * maxIdx);
        eIdx = Math.round((info.end / 100) * maxIdx);
      } else {
        return;
      }

      if (!Number.isFinite(sIdx) || !Number.isFinite(eIdx)) return;
      if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];

      sIdx = Math.max(0, sIdx);
      eIdx = Math.min(arr.length - 1, eIdx);

      try {
        _widthCtl?.setZoomRange?.({ sIdx, eIdx });
      } catch {}
      try {
        _markerPtsCtl?.setZoomRange?.({ sIdx, eIdx });
      } catch {}

      scheduleWidthUpdate();
      scheduleMarkerUpdate();

      const bars_new = Math.max(1, eIdx - sIdx + 1);
      const anchorTs = arr[eIdx]?.ts;

      if (!Number.isFinite(anchorTs)) return;

      hub.execute("SyncViewState", {
        barsCount: bars_new,
        rightTs: anchorTs,
      });
    } catch {}
  }

  const onMouseEnter = () => renderHub.setHoveredPanel(panelKey.value);
  const onMouseLeave = () => renderHub.setHoveredPanel(null);

  const displayHeader = ref({ name: "", code: "", freq: "" });
  const displayTitle = computed(() => {
    const n = displayHeader.value.name || "",
      c = displayHeader.value.code || vm.code.value || "",
      f = displayHeader.value.freq || vm.freq.value || "";
    const src = (vm.meta.value?.source || "").trim(),
      srcLabel = src ? `（${src}）` : "";
    const adjText =
      { none: "", qfq: " 前复权", hfq: " 后复权" }[
        String(vm.adjust.value || "none")
      ] || "";
    return n
      ? `${n}（${c}）：${f}${srcLabel}${adjText}`
      : `${c}：${f}${srcLabel}${adjText}`;
  });

  function updateHeaderFromCurrent() {
    const sym = (vm.meta.value?.symbol || vm.code.value || "").trim();
    const frq = String(vm.meta.value?.freq || vm.freq.value || "").trim();
    let name = "";
    try {
      name = findBySymbol(sym)?.name?.trim() || "";
    } catch {}
    displayHeader.value = { name, code: sym, freq: frq };
  }

  watch(
    () => vm.meta.value,
    () => {
      nextTick().then(updateHeaderFromCurrent);
    },
    { deep: true, immediate: true }
  );

  return {
    wrapRef,
    hostRef,
    chart,
    displayTitle,
    onResizeHandleDown,
    onMouseEnter,
    onMouseLeave,
    scheduleWidthUpdate,
    scheduleMarkerUpdate,
  };
}
