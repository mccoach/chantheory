// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useViewRenderHub.js
// ==============================
// 说明：统一渲染快照中枢（上游唯一源头）
// - REFACTORED: 遵循方案A，将庞大的 _computeAndPublish 函数拆分为多个职责清晰的内部辅助函数，
//   以提高代码的可读性和可维护性，同时保持外部接口不变。
// ==============================

import { ref, watch } from "vue";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useUserSettings } from "@/composables/useUserSettings";
import {
  buildMainChartOption,
  buildVolumeOption,
  buildMacdOption,
  buildKdjOrRsiOption,
  createFixedTooltipPositioner,
  buildBollOption,
} from "@/charts/options";
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

  const hub = useViewCommandHub();
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

  const _interacting = ref(false);
  let _interactionSource = null;
  function beginInteraction(source) {
    if (!_interacting.value) {
      _interacting.value = true;
      _interactionSource = source || null;
    }
  }
  function endInteraction(source) {
    if (!_interacting.value) return;
    if (source && _interactionSource && source !== _interactionSource) return;
    _interacting.value = false;
    _interactionSource = null;
  }
  function isInteracting() {
    return !!_interacting.value;
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

  function _getZoomRangeOf(chartInstance) {
    try {
      const c = chartInstance;
      if (!c || typeof c.getOption !== "function") return null;
      const opt = c.getOption();
      const dz = Array.isArray(opt?.dataZoom) ? opt.dataZoom : [];
      if (!dz.length) return null;
      const z = dz.find((x) => typeof x.startValue !== "undefined" && typeof x.endValue !== "undefined");
      const len = (_vmRef.vm?.candles?.value || []).length;
      if (z && len > 0) {
        const sIdx = Math.max(0, Math.min(len - 1, Number(z.startValue)));
        const eIdx = Math.max(0, Math.min(len - 1, Number(z.endValue)));
        return { sIdx: Math.min(sIdx, eIdx), eIdx: Math.max(sIdx, eIdx) };
      }
    } catch {}
    return null;
  }

  function moveCursorByStep(dir) {
    const vm = _vmRef.vm;
    if (!vm) return;
    const arr = vm.candles.value || [];
    const len = arr.length;
    if (!len) return;

    const activeChart = getActiveChart();
    const zoomRange = _getZoomRangeOf(activeChart);
    const sIdxNow = zoomRange?.sIdx ?? vm.meta.value?.view_start_idx ?? 0;
    const eIdxNow = zoomRange?.eIdx ?? vm.meta.value?.view_end_idx ?? len - 1;

    const tsArr = arr.map((d) => Date.parse(d.t));
    let startIdx = tsArr.findIndex((t) => t === settings.getLastFocusTs(vm.code.value, vm.freq.value));
    if (startIdx < 0) startIdx = eIdxNow;

    const nextIdx = Math.max(0, Math.min(len - 1, startIdx + (dir < 0 ? -1 : 1)));
    
    activeChart?.dispatchAction({ type: "showTip", seriesIndex: 0, dataIndex: nextIdx });
    const tsv = tsArr[nextIdx];
    if (Number.isFinite(tsv)) {
      settings.setLastFocusTs(vm.code.value, vm.freq.value, tsv);
    }
    
    const inView = nextIdx >= sIdxNow && nextIdx <= eIdxNow;
    if (inView) return;

    const viewWidth = Math.max(1, eIdxNow - sIdxNow + 1);
    let newS = sIdxNow, newE = eIdxNow;
    if (nextIdx < sIdxNow) {
      newS = nextIdx;
      newE = Math.min(len - 1, newS + viewWidth - 1);
    } else if (nextIdx > eIdxNow) {
      newE = nextIdx;
      newS = Math.max(0, newE - viewWidth + 1);
    }
    activeChart?.dispatchAction({ type: "dataZoom", startValue: newS, endValue: newE });
    activeChart?.dispatchAction({ type: "showTip", seriesIndex: 0, dataIndex: nextIdx });
  }

  function setIndicatorPanes(panes) {
    _indicatorPanes.value = Array.isArray(panes) ? panes : [];
  }

  function setMarketView(vm) {
    _vmRef.vm = vm;
    watch(() => [vm.candles.value, vm.indicators.value, vm.meta.value, _indicatorPanes.value], _computeAndPublish, { deep: true });
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
      try { cb(snapshot); } catch {}
    });
  }

  // --- REFACTORED: 内部辅助函数 ---

  /** NEW: 根据指标类型获取对应的 ECharts Option */
  function _getIndicatorOption(kind, ui) {
    const vm = _vmRef.vm;
    if (!vm) return null;

    const commonParams = {
      candles: vm.candles.value,
      indicators: vm.indicators.value,
      freq: vm.freq.value,
    };

    switch (String(kind || "").toUpperCase()) {
      case "VOL":
      case "AMOUNT": {
        const volCfg = settings.chartDisplay.volSettings || {};
        const st = hub.getState();
        // 量窗标记尺寸计算依赖于主窗宽度和可见根数，以保持对齐
        const volEnv = {
          hostWidth: st.hostWidthPx,
          visCount: st.barsCount,
          overrideMarkWidth: st.markerWidthPx,
        };
        const finalVolCfg = { ...volCfg, mode: kind === 'AMOUNT' ? 'amount' : 'vol' };
        return buildVolumeOption({ ...commonParams, volCfg: finalVolCfg, volEnv }, ui);
      }
      case "MACD":
        return buildMacdOption(commonParams, ui);
      case "KDJ":
        return buildKdjOrRsiOption({ ...commonParams, useKDJ: true }, ui);
      case "RSI":
        return buildKdjOrRsiOption({ ...commonParams, useRSI: true }, ui);
      case "BOLL":
        return buildBollOption(commonParams, ui);
      default:
        return null;
    }
  }

  /** 步骤1: 计算所有缠论派生数据 */
  function _calculateChanStructures(candles) {
    if (!candles || !candles.length) {
      return { reduced: [], map: [], meta: null, fractals: [], pens: { confirmed: [] }, segments: [], barriersIndices: [], pivots: [] };
    }
    const policy = settings.chanTheory.chanSettings.anchorPolicy || CHAN_DEFAULTS.anchorPolicy;
    const res = computeInclude(candles, { anchorPolicy: policy });
    const fr = computeFractals(res.reducedBars || [], {
      minTickCount: settings.chanTheory.fractalSettings.minTickCount || 0,
      minPct: settings.chanTheory.fractalSettings.minPct || 0,
      minCond: String(settings.chanTheory.fractalSettings.minCond || "or"),
    });
    const pens = computePens(res.reducedBars || [], fr || [], res.mapOrigToReduced || [], { minGapReduced: 4 });
    const segments = computeSegments(pens.confirmed || []);
    const barrierIdxList = (res.reducedBars || []).reduce((acc, cur, i, arr) => {
      if (cur && cur.barrier_after_prev_bool) {
        const prev = i > 0 ? arr[i - 1] : null;
        if (prev) acc.push(prev.end_idx_orig);
        acc.push(cur.start_idx_orig);
      }
      return acc;
    }, []);
    const pivots = computePenPivots(pens.confirmed || []);
    return { reduced: res.reducedBars, map: res.mapOrigToReduced, meta: res.meta, fractals: fr, pens, segments, barriersIndices: barrierIdxList, pivots };
  }

  /** 步骤2: 构建主图的 Option */
  function _buildMainOption(vm, chanCache, context) {
    const { initialRange, tipPositioner, hoveredKey, st, bars } = context;
    const anyMarkers = (settings.chanTheory.chanSettings?.showUpDownMarkers ?? true) && chanCache?.reduced?.length > 0;
    const markerHeight = Math.max(1, Math.round(Number(CHAN_DEFAULTS.markerHeightPx)));
    const markerYOffset = Math.max(0, Math.round(Number(CHAN_DEFAULTS.markerYOffsetPx)));
    const offsetDownPx = markerHeight + markerYOffset;
    
    const baseMainOption = buildMainChartOption({
      candles: vm.candles.value,
      indicators: vm.indicators.value,
      chartType: vm.chartType.value,
      maConfigs: settings.chartDisplay.maConfigs,
      freq: vm.freq.value,
      klineStyle: settings.chartDisplay.klineStyle,
      adjust: vm.adjust.value,
      reducedBars: chanCache.reduced,
      mapOrigToReduced: chanCache.map,
    }, {
      initialRange,
      tooltipPositioner: tipPositioner,
      isHovered: hoveredKey === "main",
      mainAxisLabelSpacePx: 28,
      xAxisLabelMargin: anyMarkers ? offsetDownPx + 12 : 12,
      mainBottomExtraPx: anyMarkers ? offsetDownPx : 0,
    });
    
    const overlaySeries = _buildOverlaySeriesForOption({
      hostW: st.hostWidthPx,
      visCount: bars,
      markerW: st.markerWidthPx,
      chanCache: chanCache
    });
    
    return { ...baseMainOption, series: [...(baseMainOption.series || []), ...overlaySeries] };
  }

  /** 步骤2.1: 构建主图的缠论覆盖层 Series */
  function _buildOverlaySeriesForOption({ hostW, visCount, markerW, chanCache }) {
    const out = [];
    const { reduced, fractals, pens, segments, barriersIndices, pivots } = chanCache;
    if (barriersIndices?.length) out.push(...(buildBarrierLines(barriersIndices).series || []));
    if (settings.chanTheory.chanSettings.showUpDownMarkers && reduced?.length) {
        out.push(...(buildUpDownMarkers(reduced, { hostWidth: hostW, visCount, symbolWidthPx: markerW }).series || []));
    }
    if ((settings.chanTheory.fractalSettings?.enabled ?? true) && reduced?.length && fractals?.length) {
        out.push(...(buildFractalMarkers(reduced, fractals, { hostWidth: hostW, visCount, symbolWidthPx: markerW }).series || []));
    }
    const penEnabled = (settings.chanTheory.chanSettings?.pen?.enabled ?? PENS_DEFAULTS.enabled) === true;
    if (penEnabled && reduced?.length && (pens?.confirmed?.length || pens?.provisional)) {
        out.push(...(buildPenLines(pens, { barrierIdxList: barriersIndices }).series || []));
    }
    if (segments?.length) {
        out.push(...(buildSegmentLines(segments, { barrierIdxList: barriersIndices }).series || []));
    }
    if (pivots?.length) {
        out.push(...(buildPenPivotAreas(pivots, { barrierIdxList: barriersIndices }).series || []));
    }
    return out;
  }
  
  /** 步骤3: 构建所有指标窗的 Options */
  function _buildIndicatorOptions(context) {
    const { initialRange, tipPositioner, hoveredKey } = context;
    const indicatorOptions = {};
    for (const pane of _indicatorPanes.value) {
      if (!pane || !pane.id || pane.kind === 'OFF') continue;
      const paneKey = `indicator:${pane.id}`;
      const option = _getIndicatorOption(pane.kind, {
        initialRange,
        tooltipPositioner: tipPositioner,
        isHovered: hoveredKey === paneKey,
      });
      if (option) {
        indicatorOptions[pane.id] = option;
      }
    }
    return indicatorOptions;
  }

  /** 步骤4: 编排与发布 */
  function _computeAndPublish() {
    const vm = _vmRef.vm;
    // FIX: 当数据为空时，不再提前返回，而是继续流程以生成并发布一个“空”的 option 来清空图表。
    if (!vm) return;
    

    // 准备上下文
    const candles = vm.candles.value;
    const len = candles.length;
    const st = hub.getState();
    const bars = Math.max(1, Number(st.barsCount || 1));
    const tsArr = candles.map((d) => Date.parse(d.t));

    let eIdx = len - 1;
    if (Number.isFinite(st.rightTs)) {
      for (let i = len - 1; i >= 0; i--) {
        if (tsArr[i] <= st.rightTs) { eIdx = i; break; }
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

    // 执行计算和构建
    _chanCache.value = _calculateChanStructures(candles);
    const mainOption = _buildMainOption(vm, _chanCache.value, context);
    const indicatorOptions = _buildIndicatorOptions(context);
    
    // 组装并发布快照
    const snapshot = {
      seq: ++_renderSeq,
      core: {
        code: vm.code.value,
        freq: vm.freq.value,
        adjust: vm.adjust.value,
        barsCount: bars,
        rightTs: st.rightTs,
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

  // 订阅 hub 的两帧合并广播
  hub.onChange(_computeAndPublish);

  // FIX: 将 getTipPositioner 的定义移到 _singleton 创建之前
  function getTipPositioner() {
    return _getTipPositioner();
  }

  _singleton = {
    setMarketView,
    onRender,
    offRender,
    getTipPositioner,
    setHoveredPanel,
    beginInteraction,
    endInteraction,
    isInteracting,
    registerChart,
    unregisterChart,
    setActivePanel,
    getActivePanel,
    getChart,
    getActiveChart,
    moveCursorByStep,
    setIndicatorPanes,
  };
  return _singleton;
}