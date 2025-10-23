// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useViewRenderHub.js
// ==============================
// 说明：统一渲染快照中枢（上游唯一源头）
// - FIX: 彻底重构为唯一的 option 生成器。
// - `_computeAndPublish` 现在会遍历由 `TechPanels` 上报的 `_indicatorPanes` 数组。
// - 为每个副图指标（包括主图）预先生成完整、正确的 option。
// - 快照中包含 `indicatorOptions` 映射表，供 `IndicatorPanel` 按 ID 查找并应用。
// - 移除了 `getIndicatorOption` 的导出，变为内部辅助函数。
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
// NEW: 引入覆盖层和缠论计算
import {
  computeInclude,
  computeFractals,
  computePens,
  computeSegments,
  computePenPivots,
} from "@/composables/useChan";
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

  // --- FIX: 将 settings 的初始化移入工厂函数内部，确保其在正确的 setup 上下文中执行 ---
  const hub = useViewCommandHub();
  const settings = useUserSettings();

  const _vmRef = { vm: null };
  const _hoveredPanelKey = ref(null);
  const _subs = new Map();
  let _nextId = 1;
  const _lastSnapshot = ref(null);
  let _renderSeq = 0;

  // FIX: 新增 _indicatorPanes 状态，由 TechPanels 上报
  const _indicatorPanes = ref([]);

  const tipMode = ref("follow");
  try {
    window.addEventListener("chan:set-tooltip-mode", (e) => {
      const m = String(e?.detail?.mode || "").toLowerCase();
      tipMode.value = m === "follow" ? "follow" : "fixed";
      try { _computeAndPublish(); } catch {}
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

  const _charts = new Map();
  const _activePanelKey = ref("main");
  function registerChart(panelKey, chartInstance) {
    try { if (!panelKey || !chartInstance) return; _charts.set(String(panelKey), chartInstance); } catch {}
  }
  function unregisterChart(panelKey) {
    try { if (!panelKey) return; _charts.delete(String(panelKey)); } catch {}
  }
  function setActivePanel(panelKey) {
    try { if (!panelKey) return; _activePanelKey.value = String(panelKey); } catch {}
  }
  function getActivePanel() { return String(_activePanelKey.value || "main"); }
  function getChart(panelKey) { try { return _charts.get(String(panelKey)) || null; } catch { return null; } }
  function getActiveChart() { try { return _charts.get(String(_activePanelKey.value)) || null; } catch { return null; } }

  function _getZoomRangeOf(chartInstance) {
    try {
      const c = chartInstance;
      if (!c || typeof c.getOption !== "function") return null;
      const opt = c.getOption();
      const dz = Array.isArray(opt?.dataZoom) ? opt.dataZoom : [];
      if (!dz.length) return null;
      const z = dz.find( (x) => typeof x.startValue !== "undefined" && typeof x.endValue !== "undefined" );
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
    try {
      const vm = _vmRef.vm;
      if (!vm) return;
      const arr = vm.candles.value || [];
      const len = arr.length;
      if (!len) return;

      const activeChart = getActiveChart();
      const zoomRange = _getZoomRangeOf(activeChart);
      const sIdxNow = zoomRange && Number.isFinite(zoomRange.sIdx) ? zoomRange.sIdx : Number(vm.meta.value?.view_start_idx ?? 0);
      const eIdxNow = zoomRange && Number.isFinite(zoomRange.eIdx) ? zoomRange.eIdx : Number(vm.meta.value?.view_end_idx ?? len - 1);

      const tsArr = arr.map((d) => Date.parse(d.t));

      let startIdx = -1;
      try {
        const lastTs = settings.getLastFocusTs(vm.code.value, vm.freq.value);
        if (Number.isFinite(lastTs)) {
          const found = tsArr.findIndex((t) => Number.isFinite(t) && t === lastTs);
          if (found >= 0) startIdx = found;
        }
      } catch {}
      if (startIdx < 0) startIdx = eIdxNow;

      let nextIdx = Math.max(0, Math.min(len - 1, startIdx + (dir < 0 ? -1 : +1)));
      const inView = nextIdx >= sIdxNow && nextIdx <= eIdxNow;

      try {
        activeChart?.dispatchAction({ type: "showTip", seriesIndex: 0, dataIndex: nextIdx });
      } catch {}

      try {
        const tsv = tsArr[nextIdx];
        if (Number.isFinite(tsv)) {
          settings.setLastFocusTs(vm.code.value, vm.freq.value, tsv);
        }
      } catch {}

      if (inView) return;

      const viewWidth = Math.max(1, eIdxNow - sIdxNow + 1);
      let newS = sIdxNow;
      let newE = eIdxNow;
      if (nextIdx < sIdxNow) {
        newS = nextIdx;
        newE = Math.min(len - 1, newS + viewWidth - 1);
      } else if (nextIdx > eIdxNow) {
        newE = nextIdx;
        newS = Math.max(0, newE - viewWidth + 1);
      }
      try {
        activeChart?.dispatchAction({ type: "dataZoom", startValue: newS, endValue: newE });
        const edgeIdx = nextIdx < sIdxNow ? newS : newE;
        activeChart?.dispatchAction({ type: "showTip", seriesIndex: 0, dataIndex: edgeIdx });
      } catch {}
    } catch {}
  }

  // FIX: 新增 setIndicatorPanes 方法，供 TechPanels 调用
  function setIndicatorPanes(panes) {
    _indicatorPanes.value = Array.isArray(panes) ? panes : [];
  }

  function setMarketView(vm) {
    _vmRef.vm = vm;
    // FIX: 监听数据和 indicatorPanes 的变化
    watch(
      () => [vm.candles.value, vm.indicators.value, vm.meta.value, _indicatorPanes.value],
      () => {
        _computeAndPublish();
      },
      { deep: true }
    );
  }

  function onRender(cb) {
    const id = _nextId++;
    _subs.set(id, typeof cb === "function" ? cb : () => {});
    try { if (_lastSnapshot.value) cb(_lastSnapshot.value); } catch {}
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
  
  // FIX: _getIndicatorOption 变为内部函数，负责为单个指标生成option
  function _getIndicatorOption(kind, ui) {
    const vm = _vmRef.vm;
    if (!vm) return null;
    
    const base = {
      candles: vm.candles.value,
      indicators: vm.indicators.value,
      freq: vm.freq.value,
    };

    const K = String(kind || "").toUpperCase();
    if (K === "MACD") return buildMacdOption(base, ui);
    if (K === "KDJ") return buildKdjOrRsiOption({ ...base, useKDJ: true, useRSI: false }, ui);
    if (K === "RSI") return buildKdjOrRsiOption({ ...base, useKDJ: false, useRSI: true }, ui);
    if (K === "BOLL") return buildBollOption(base, ui);
    if (K === "VOL" || K === "AMOUNT") {
      const volCfg = {
        ...(settings.volSettings.value || {}),
        mode: K === "AMOUNT" ? "amount" : "vol",
      };
      return buildVolumeOption(
        {
          ...base,
          volCfg,
          volEnv: {
            hostWidth: 0,
            visCount: Math.max(1, hub.barsCount.value || 1),
            overrideMarkWidth: hub.markerWidthPx.value,
          },
        },
        ui
      );
    }
    return null; // 对于 "OFF" 或未知类型返回 null
  }

  // --- NEW: 将 MainChartPanel 的逻辑移入此处 ---
  const _chanCache = ref({});
  function _recomputeChan() {
      const vm = _vmRef.vm;
      if (!vm) return;
      const arr = vm.candles.value || [];
      if (!arr.length) {
          _chanCache.value = { reduced: [], map: [], meta: null, fractals: [], pens: { confirmed: [], provisional: null, all: [] }, segments: [], barriersIndices: [], pivots: [] };
          return;
      }
      const policy = settings.chanSettings.value.anchorPolicy || CHAN_DEFAULTS.anchorPolicy;
      const res = computeInclude(arr, { anchorPolicy: policy });
      const fr = computeFractals(res.reducedBars || [], {
          minTickCount: settings.fractalSettings.value.minTickCount || 0,
          minPct: settings.fractalSettings.value.minPct || 0,
          minCond: String(settings.fractalSettings.value.minCond || "or"),
      });
      const pens = computePens(res.reducedBars || [], fr || [], res.mapOrigToReduced || [], { minGapReduced: 4 });
      const segments = computeSegments(pens.confirmed || []);
      const barrierIdxList = [];
      const rb = res.reducedBars || [];
      for (let i = 0; i < rb.length; i++) {
          const cur = rb[i];
          if (cur && cur.barrier_after_prev_bool) {
              const prev = i > 0 ? rb[i - 1] : null;
              const left = prev ? prev.end_idx_orig : null;
              const right = cur.start_idx_orig;
              if (Number.isFinite(+left)) barrierIdxList.push(+left);
              if (Number.isFinite(+right)) barrierIdxList.push(+right);
          }
      }
      const pivots = computePenPivots(pens.confirmed || []);
      _chanCache.value = { reduced: res.reducedBars || [], map: res.mapOrigToReduced || [], meta: res.meta || null, fractals: fr || [], pens, segments, barriersIndices: barrierIdxList, pivots };
  }

  function _buildOverlaySeriesForOption({ hostW, visCount, markerW }) {
    const out = [];
    const cache = _chanCache.value || {};
    const { reduced, fractals, pens, segments, barriersIndices, pivots } = cache;
    if (barriersIndices?.length) out.push(...(buildBarrierLines(barriersIndices).series || []));
    if (settings.chanSettings.value.showUpDownMarkers && reduced?.length) {
        out.push(...(buildUpDownMarkers(reduced, { hostWidth: hostW, visCount, symbolWidthPx: markerW }).series || []));
    }
    if ((settings.fractalSettings.value?.enabled ?? true) && reduced?.length && fractals?.length) {
        out.push(...(buildFractalMarkers(reduced, fractals, { hostWidth: hostW, visCount, symbolWidthPx: markerW }).series || []));
    }
    const penEnabled = (settings.chanSettings.value?.pen?.enabled ?? PENS_DEFAULTS.enabled) === true;
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
  // --- END: 逻辑移动结束 ---

  function _computeAndPublish() {
    const vm = _vmRef.vm;
    if (!vm) return;

    const candles = vm.candles.value || [];
    const len = candles.length;
    if (!len) return;
    
    _recomputeChan(); // NEW: 先计算缠论

    // FIX: 从 hub.getState() 获取所有状态
    const st = hub.getState();
    const bars = Math.max(1, Number(st.barsCount || 1));
    const tsArr = candles.map((d) => { try { return Date.parse(d.t); } catch { return NaN; } });

    let eIdx = len - 1;
    if (Number.isFinite(st.rightTs)) {
      for (let i = len - 1; i >= 0; i--) {
        const tsv = tsArr[i];
        if (Number.isFinite(tsv) && tsv <= st.rightTs) { eIdx = i; break; }
      }
    }
    let sIdx = Math.max(0, eIdx - bars + 1);
    if (sIdx === 0 && eIdx - sIdx + 1 < bars) {
      eIdx = Math.min(len - 1, bars - 1);
    }

    const initialRange = { startValue: sIdx, endValue: eIdx };
    const tipPositioner = _getTipPositioner();
    const hoveredKey = _hoveredPanelKey.value;

    // --- REFACTORED: 构建主图 option ---
    const anyMarkers = (settings.chanSettings.value?.showUpDownMarkers ?? true) === true && _chanCache.value?.reduced?.length > 0;
    const markerHeight = Math.max(1, Math.round(Number(CHAN_DEFAULTS.markerHeightPx)));
    const markerYOffset = Math.max(0, Math.round(Number(CHAN_DEFAULTS.markerYOffsetPx)));
    const offsetDownPx = Math.round(markerHeight + markerYOffset);
    const mainBottomExtraPx = anyMarkers ? offsetDownPx : 0;
    const xAxisLabelMargin = anyMarkers ? offsetDownPx + 12 : 12;

    const baseMainOption = buildMainChartOption(
      {
        candles,
        indicators: vm.indicators.value || {},
        chartType: vm.chartType.value || "kline",
        maConfigs: settings.maConfigs.value,
        freq: vm.freq.value || "1d",
        klineStyle: settings.klineStyle.value,
        adjust: vm.adjust.value || "none",
        reducedBars: _chanCache.value.reduced,
        mapOrigToReduced: _chanCache.value.map,
      },
      {
        initialRange,
        tooltipPositioner: tipPositioner,
        isHovered: hoveredKey === "main",
        mainAxisLabelSpacePx: 28,
        xAxisLabelMargin,
        mainBottomExtraPx,
      }
    );

    const overlaySeries = _buildOverlaySeriesForOption({
      hostW: st.hostWidthPx, // FIX: 从 st 获取 hostWidthPx
      visCount: bars,
      markerW: st.markerWidthPx,
    });
    
    const finalMainOption = {
      ...baseMainOption,
      series: [...(baseMainOption.series || []), ...overlaySeries],
    };
    // --- END REFACTOR ---

    // FIX: 遍历 _indicatorPanes，为每个副图生成 option
    const indicatorOptions = {};
    for (const pane of _indicatorPanes.value) {
      if (!pane || !pane.id || pane.kind === 'OFF') continue;
      const paneKey = `indicator:${pane.id}`;
      const isPaneHovered = hoveredKey === paneKey;
      const option = _getIndicatorOption(pane.kind, {
        initialRange,
        tooltipPositioner: tipPositioner,
        isHovered: isPaneHovered,
      });
      if (option) {
        indicatorOptions[pane.id] = option;
      }
    }

    const snapshot = {
      seq: ++_renderSeq,
      core: {
        code: vm.code.value || "",
        freq: vm.freq.value || "1d",
        adjust: vm.adjust.value || "none",
        barsCount: bars,
        rightTs: st.rightTs,
        sIdx,
        eIdx,
        allRows: len,
        atRightEdge: !!st.atRightEdge,
        markerWidthPx: st.markerWidthPx,
        hoveredPanelKey: hoveredKey,
      },
      main: {
        option: finalMainOption, // REFACTORED: 直接提供构建好的 option
        range: initialRange,
      },
      // FIX: 新增 indicatorOptions 映射表
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
  hub.onChange(() => {
    _computeAndPublish();
  });

  // 新增：暴露统一源头的 tooltip 位置获取
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
    setIndicatorPanes, // FIX: 暴露上报方法
  };
  return _singleton;
}
