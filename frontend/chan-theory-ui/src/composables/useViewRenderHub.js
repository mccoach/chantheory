// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useViewRenderHub.js
// ==============================
// V8.0 - 删除交互触发的渲染
// 
// 核心改造：
//   - 仅在数据变化时调用 _computeAndPublish
//   - 删除 hub.onChange 触发渲染（冗余）
// ==============================

import { ref, watch } from "vue";
import { getCommandState } from "@/composables/useViewCommandHub";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useUserSettings } from "@/composables/useUserSettings";
import { chartBuilderRegistry } from "@/charts/builderRegistry";
import { createFixedTooltipPositioner } from "@/charts/options";
import {
  computeInclude,
  computeFractals,
  computePens,
  computeSegments,
  computePenPivots,
} from "@/composables/chan";
import {
  buildUpDownMarkers,
  buildFractalMarkers,
  buildPenLines,
  buildSegmentLines,
  buildBarrierLines,
  buildPenPivotAreas,
} from "@/charts/chan/layers";
import { CHAN_DEFAULTS, PENS_DEFAULTS } from "@/constants";

let _singleton = null;

export function useViewRenderHub() {
  if (_singleton) return _singleton;

  const settings = useUserSettings();

  const _vmRef = { vm: null };
  const _hoveredPanelKey = ref(null);
  const _subs = new Map();
  let _nextId = 1;
  const _lastSnapshot = ref(null);
  let _renderSeq = 0;

  const _indicatorPanes = ref([]);
  const _chanCache = ref({});
  const _charts = new Map();
  const _activePanelKey = ref("main");

  const _currentFocusIdx = ref(-1);

  const tipMode = ref("follow");
  try {
    window.addEventListener("chan:set-tooltip-mode", (e) => {
      const m = String(e?.detail?.mode || "").toLowerCase();
      tipMode.value = m === "follow" ? "follow" : "fixed";
      _computeAndPublish();
    });
  } catch {}

  function _getTipPositioner() {
    if (tipMode.value === "fixed") return createFixedTooltipPositioner("left");
    return undefined;
  }

  function setHoveredPanel(panelKey) {
    if (_hoveredPanelKey.value !== panelKey) {
      _hoveredPanelKey.value = panelKey;
    }
  }

  watch(_hoveredPanelKey, () => {
    _computeAndPublish();
  });

  function registerChart(panelKey, chartInstance) {
    _charts.set(String(panelKey), chartInstance);
  }

  function unregisterChart(panelKey) {
    _charts.delete(String(panelKey));
  }

  function setActivePanel(panelKey) {
    _activePanelKey.value = String(panelKey);
  }

  function getActivePanel() {
    return String(_activePanelKey.value || "main");
  }

  function getChart(panelKey) {
    return _charts.get(String(panelKey)) || null;
  }

  function getActiveChart() {
    return _charts.get(String(_activePanelKey.value)) || null;
  }

  function syncFocusPosition(idx) {
    const vm = _vmRef.vm;
    if (!vm) return;

    const arr = vm.candles.value || [];
    const len = arr.length;

    if (!Number.isFinite(idx) || idx < 0 || idx >= len) {
      return;
    }

    _currentFocusIdx.value = idx;
  }

  function moveCursorByStep(dir) {
    const vm = _vmRef.vm;
    if (!vm) return;
    const arr = vm.candles.value || [];
    const len = arr.length;
    if (!len) return;

    const activeChart = getActiveChart();
    const zoomRange = _getZoomRangeOf(activeChart);
    const sIdxNow = zoomRange?.sIdx ?? 0;
    const eIdxNow = zoomRange?.eIdx ?? len - 1;

    let startIdx = _currentFocusIdx.value;

    if (startIdx < 0 || startIdx >= len) {
      startIdx = eIdxNow;
    }

    const nextIdx = Math.max(
      0,
      Math.min(len - 1, startIdx + (dir < 0 ? -1 : 1))
    );

    syncFocusPosition(nextIdx);

    activeChart?.dispatchAction({
      type: "showTip",
      seriesIndex: 0,
      dataIndex: nextIdx,
    });

    const inView = nextIdx >= sIdxNow && nextIdx <= eIdxNow;
    if (inView) return;

    const viewWidth = Math.max(1, eIdxNow - sIdxNow + 1);
    let newS = sIdxNow,
      newE = eIdxNow;

    if (nextIdx < sIdxNow) {
      newS = nextIdx;
      newE = Math.min(len - 1, newS + viewWidth - 1);
    } else if (nextIdx > eIdxNow) {
      newE = nextIdx;
      newS = Math.max(0, newE - viewWidth + 1);
    }

    activeChart?.dispatchAction({
      type: "dataZoom",
      startValue: newS,
      endValue: newE,
    });

    activeChart?.dispatchAction({
      type: "showTip",
      seriesIndex: 0,
      dataIndex: nextIdx,
    });
  }

  function _getZoomRangeOf(chartInstance) {
    try {
      const c = chartInstance;
      if (!c || typeof c.getOption !== "function") return null;
      const opt = c.getOption();
      const dz = Array.isArray(opt?.dataZoom) ? opt.dataZoom : [];
      if (!dz.length) return null;
      const z = dz.find(
        (x) =>
          typeof x.startValue !== "undefined" &&
          typeof x.endValue !== "undefined"
      );
      const len = (_vmRef.vm?.candles?.value || []).length;
      if (z && len > 0) {
        const sIdx = Math.max(0, Math.min(len - 1, Number(z.startValue)));
        const eIdx = Math.max(0, Math.min(len - 1, Number(z.endValue)));
        return { sIdx: Math.min(sIdx, eIdx), eIdx: Math.max(sIdx, eIdx) };
      }
    } catch {}
    return null;
  }

  function setIndicatorPanes(panes) {
    _indicatorPanes.value = Array.isArray(panes) ? panes : [];
  }

  function setMarketView(vm) {
    _vmRef.vm = vm;

    const hub = useViewCommandHub();
    hub.setMarketView(vm);

    // ===== 唯一渲染触发点：数据变化 =====
    watch(
      () => [
        vm.candles.value,
        vm.indicators.value,
        vm.meta.value,
        _indicatorPanes.value,
      ],
      _computeAndPublish,
      { deep: true }
    );
  }

  function onRender(cb) {
    const id = _nextId++;
    _subs.set(id, typeof cb === "function" ? cb : () => {});
    if (_lastSnapshot.value) cb(_lastSnapshot.value);
    return id;
  }

  function offRender(id) {
    _subs.delete(id);
  }

  function _publish(snapshot) {
    _lastSnapshot.value = snapshot;
    _subs.forEach((cb) => {
      try {
        cb(snapshot);
      } catch {}
    });
  }

  function _calculateChanStructures(candles) {
    if (!candles || !candles.length) {
      return {
        reduced: [],
        map: [],
        meta: null,
        fractals: [],
        pens: { confirmed: [] },
        segments: [],
        barriersIndices: [],
        pivots: [],
      };
    }

    const policy =
      settings.chanTheory.chanSettings.anchorPolicy ||
      CHAN_DEFAULTS.anchorPolicy;
    const res = computeInclude(candles, { anchorPolicy: policy });

    const fr = computeFractals(res.reducedBars || [], {
      minTickCount: settings.chanTheory.fractalSettings.minTickCount || 0,
      minPct: settings.chanTheory.fractalSettings.minPct || 0,
      minCond: String(settings.chanTheory.fractalSettings.minCond || "or"),
    });

    const pens = computePens(
      res.reducedBars || [],
      fr || [],
      res.mapOrigToReduced || [],
      { minGapReduced: 4 }
    );

    const segments = computeSegments(pens.confirmed || []);

    const barrierIdxList = (res.reducedBars || []).reduce(
      (acc, cur, i, arr) => {
        if (cur && cur.barrier_after_prev_bool) {
          const prev = i > 0 ? arr[i - 1] : null;
          if (prev) acc.push(prev.end_idx_orig);
          acc.push(cur.start_idx_orig);
        }
        return acc;
      },
      []
    );

    const pivots = computePenPivots(pens.confirmed || []);

    return {
      reduced: res.reducedBars,
      map: res.mapOrigToReduced,
      meta: res.meta,
      fractals: fr,
      pens,
      segments,
      barriersIndices: barrierIdxList,
      pivots,
    };
  }

  function _buildOverlaySeriesForOption({
    hostW,
    visCount,
    markerW,
    chanCache,
  }) {
    const out = [];
    const { reduced, fractals, pens, segments, barriersIndices, pivots } =
      chanCache;

    if (barriersIndices?.length) {
      out.push(...(buildBarrierLines(barriersIndices).series || []));
    }

    if (settings.chanTheory.chanSettings.showUpDownMarkers && reduced?.length) {
      out.push(
        ...(buildUpDownMarkers(reduced, {
          hostWidth: hostW,
          visCount,
          symbolWidthPx: markerW,
        }).series || [])
      );
    }

    if (
      (settings.chanTheory.fractalSettings?.enabled ?? true) &&
      reduced?.length &&
      fractals?.length
    ) {
      out.push(
        ...(buildFractalMarkers(reduced, fractals, {
          hostWidth: hostW,
          visCount,
          symbolWidthPx: markerW,
        }).series || [])
      );
    }

    const penEnabled =
      (settings.chanTheory.chanSettings?.pen?.enabled ??
        PENS_DEFAULTS.enabled) === true;
    if (
      penEnabled &&
      reduced?.length &&
      (pens?.confirmed?.length || pens?.provisional)
    ) {
      out.push(
        ...(buildPenLines(pens, { barrierIdxList: barriersIndices }).series ||
          [])
      );
    }

    if (segments?.length) {
      out.push(
        ...(buildSegmentLines(segments, { barrierIdxList: barriersIndices })
          .series || [])
      );
    }

    if (pivots?.length) {
      out.push(
        ...(buildPenPivotAreas(pivots, { barrierIdxList: barriersIndices })
          .series || [])
      );
    }

    return out;
  }

  async function _buildMainOption(vm, chanCache, context) {
    const { initialRange, tipPositioner, hoveredKey, st, bars } = context;

    const buildMain = await chartBuilderRegistry.get("MAIN");
    if (!buildMain) {
      console.error("[RenderHub] ❌ Main chart builder not found");
      return { series: [] };
    }

    const anyMarkers =
      (settings.chanTheory.chanSettings?.showUpDownMarkers ?? true) &&
      chanCache?.reduced?.length > 0;
    const markerHeight = CHAN_DEFAULTS.markerHeightPx;
    const markerYOffset = CHAN_DEFAULTS.markerYOffsetPx;
    const offsetDownPx = markerHeight + markerYOffset;

    const baseMainOption = buildMain(
      {
        candles: vm.candles.value,
        indicators: vm.indicators.value,
        chartType: vm.chartType.value,
        maConfigs: settings.chartDisplay.maConfigs,
        freq: vm.freq.value,
        klineStyle: settings.chartDisplay.klineStyle,
        adjust: vm.adjust.value,
        reducedBars: chanCache.reduced,
        mapOrigToReduced: chanCache.map,
      },
      {
        initialRange,
        tooltipPositioner: tipPositioner,
        isHovered: hoveredKey === "main",
        mainAxisLabelSpacePx: 28,
        xAxisLabelMargin: anyMarkers ? offsetDownPx + 12 : 12,
        mainBottomExtraPx: anyMarkers ? offsetDownPx : 0,
      }
    );

    const overlaySeries = _buildOverlaySeriesForOption({
      hostW: st.hostWidthPx,
      visCount: bars,
      markerW: st.markerWidthPx,
      chanCache: chanCache,
    });

    return {
      ...baseMainOption,
      series: [...(baseMainOption.series || []), ...overlaySeries],
    };
  }

  async function _getIndicatorOption(kind, ui) {
    const vm = _vmRef.vm;
    if (!vm) return null;

    const key = String(kind || "").toUpperCase();

    const builder = await chartBuilderRegistry.get(key);
    if (!builder) {
      console.warn(`[RenderHub] ⚠️ No builder for indicator '${kind}'`);
      return null;
    }

    const commonParams = {
      candles: vm.candles.value,
      indicators: vm.indicators.value,
      freq: vm.freq.value,
    };

    if (key === "VOL" || key === "AMOUNT") {
      const volCfg = settings.chartDisplay.volSettings || {};
      const st = getCommandState();
      const volEnv = {
        hostWidth: st.hostWidthPx,
        visCount: st.barsCount,
        overrideMarkWidth: st.markerWidthPx,
      };
      const finalVolCfg = {
        ...volCfg,
        mode: key === "AMOUNT" ? "amount" : "vol",
      };
      return builder({ ...commonParams, volCfg: finalVolCfg, volEnv }, ui);
    }

    if (key === "KDJ") {
      return builder({ ...commonParams, useKDJ: true }, ui);
    }
    if (key === "RSI") {
      return builder({ ...commonParams, useRSI: true }, ui);
    }

    return builder(commonParams, ui);
  }

  async function _buildIndicatorOptions(context) {
    const { initialRange, tipPositioner, hoveredKey } = context;
    const indicatorOptions = {};

    for (const pane of _indicatorPanes.value) {
      if (!pane || !pane.id || pane.kind === "OFF") continue;
      const paneKey = `indicator:${pane.id}`;

      try {
        const option = await _getIndicatorOption(pane.kind, {
          initialRange,
          tooltipPositioner: tipPositioner,
          isHovered: hoveredKey === paneKey,
        });

        if (option) {
          indicatorOptions[pane.id] = option;
        }
      } catch (e) {
        console.error(`[RenderHub] ❌ Failed to build ${pane.kind}`, e);
      }
    }

    return indicatorOptions;
  }

  async function _computeAndPublish() {
    const vm = _vmRef.vm;
    if (!vm) return;

    const candles = vm.candles.value;
    const len = candles.length;
    const st = getCommandState();
    const bars = Math.max(1, Number(st.barsCount || 1));

    const tsArr = candles.map((d) => d.ts);

    let eIdx = len - 1;
    if (Number.isFinite(st.rightTs)) {
      for (let i = len - 1; i >= 0; i--) {
        if (tsArr[i] <= st.rightTs) {
          eIdx = i;
          break;
        }
      }
    }
    let sIdx = Math.max(0, eIdx - bars + 1);
    if (sIdx === 0 && eIdx - sIdx + 1 < bars) {
      eIdx = Math.min(len - 1, bars - 1);
    }

    const context = {
      initialRange: { startValue: sIdx, endValue: eIdx },
      tipPositioner: _getTipPositioner(),
      hoveredKey: _hoveredPanelKey.value,
      st,
      bars,
    };

    _chanCache.value = _calculateChanStructures(candles);

    const mainOption = await _buildMainOption(vm, _chanCache.value, context);
    const indicatorOptions = await _buildIndicatorOptions(context);

    const snapshot = {
      seq: ++_renderSeq,
      core: {
        code: vm.code.value,
        freq: vm.freq.value,
        adjust: vm.adjust.value,
        barsCount: bars,
        rightTs: st.rightTs,
        leftTs: st.leftTs,
        sIdx,
        eIdx,
        allRows: len,
        atRightEdge: !!st.atRightEdge,
        markerWidthPx: st.markerWidthPx,
        hoveredPanelKey: context.hoveredKey,
      },
      main: {
        option: mainOption,
        range: context.initialRange,
      },
      indicatorOptions,
      metaLink: {
        generated_at: vm.meta.value?.generated_at || "",
        source: vm.meta.value?.source || "",
        downsample_from: vm.meta.value?.downsample_from || null,
      },
    };

    _publish(snapshot);
  }

  function getTipPositioner() {
    return _getTipPositioner();
  }

  _singleton = {
    setMarketView,
    onRender,
    offRender,
    getTipPositioner,
    setHoveredPanel,
    registerChart,
    unregisterChart,
    setActivePanel,
    getActivePanel,
    getChart,
    getActiveChart,
    moveCursorByStep,
    setIndicatorPanes,
    requestRender: _computeAndPublish,
    syncFocusPosition,
    resetFocusIndex() {
      _currentFocusIdx.value = -1;
    },
  };

  return _singleton;
}