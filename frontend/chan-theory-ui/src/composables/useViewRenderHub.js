// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useViewRenderHub.js
// ==============================
// V13.4 - Chan 结构缓存分层：include 与派生结构拆分缓存（进一步降低设置保存触发的卡顿）
//
// 背景（延续 V13.3）：
//   - V13.3 已缓存 tsArr + Chan 结构，并用 O(logN) 二分替代倒序扫。
//   - 但 Chan 结构缓存仍是“大一坨”：当分型显著度参数变更时，会导致 include/fractals/pens/segments/pivots 全量重算。
//   - include（合并K+屏障+映射）在“仅改变分型显著度参数”场景下是确定冗余，可复用。
//
// 本轮改动：
//   1) 将 Chan 结构缓存拆为两层：
//        - includeMemo：key = candlesKey + anchorPolicy + ipoYmd
//        - derivedMemo：key = includeKey + fractalParams（minTick/minPct/minCond）
//      使得仅变更分型显著度参数时，不再重算 include。
//   2) 对外返回结构保持完全一致：_calculateChanStructures(candles) 仍返回同一 shape。
//   3) 严控范围：仅改本文件；不改算法实现、不改渲染层、不改设置协议。
// ==============================

import { ref, watch, nextTick } from "vue";
import { getCommandState } from "@/composables/useViewCommandHub";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { chartBuilderRegistry } from "@/charts/builderRegistry";
import { createFixedTooltipPositioner } from "@/charts/options";
import {
  computeInclude,
  computeFractals,
  computeFractalConfirmPairs,
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
  const symbolIndex = useSymbolIndex();

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

  const _batchFlag = ref(false);
  const _pendingCompute = ref(false);

  const tipMode = ref("follow");
  try {
    window.addEventListener("chan:set-tooltip-mode", (e) => {
      const m = String(e?.detail?.mode || "").toLowerCase();
      tipMode.value = m === "follow" ? "follow" : "fixed";
      _computeAndPublish();
    });
  } catch { }

  function _getTipPositioner() {
    if (tipMode.value === "fixed") return createFixedTooltipPositioner("left");
    return undefined;
  }

  // ===== Hover AxisPointer（保持原逻辑）=====
  const _lastHoveredKey = ref(null);
  const _hoverModeApplied = new Map();
  let _hoverRafPending = false;
  let _hoverPendingKey = null;

  function _applyAxisPointerModeToChart(chartInstance, isHovered) {
    if (!chartInstance) return;

    const crossStyle = isHovered
      ? { color: "#999", width: 1, type: "dashed" }
      : { color: "transparent", width: 0, type: "solid" };

    const tooltip = {
      axisPointer: {
        type: "cross",
        crossStyle,
      },
    };

    const yAxis = [
      {
        axisPointer: {
          show: !!isHovered,
          label: { show: !!isHovered },
        },
      },
    ];

    try {
      chartInstance.setOption({ tooltip, yAxis }, false);
    } catch { }
  }

  function _applyHoverModeByKey(panelKey, isHovered) {
    const key = String(panelKey || "");
    if (!key) return;

    const chart = _charts.get(key) || null;
    if (!chart) return;

    const applied = _hoverModeApplied.get(key);
    if (applied === !!isHovered) return;

    _applyAxisPointerModeToChart(chart, !!isHovered);
    _hoverModeApplied.set(key, !!isHovered);
  }

  function _flushHoverUpdate() {
    _hoverRafPending = false;

    const nextKey = _hoverPendingKey ? String(_hoverPendingKey) : null;
    _hoverPendingKey = null;

    const prevKey = _lastHoveredKey.value;

    if (prevKey === nextKey) return;

    _hoveredPanelKey.value = nextKey;
    _lastHoveredKey.value = nextKey;

    if (prevKey) _applyHoverModeByKey(prevKey, false);
    if (nextKey) _applyHoverModeByKey(nextKey, true);
  }

  function setHoveredPanel(panelKey) {
    const nextKey = panelKey ? String(panelKey) : null;

    if (_hoverPendingKey === nextKey && _hoverRafPending) return;
    if (_lastHoveredKey.value === nextKey && !_hoverRafPending) return;

    _hoverPendingKey = nextKey;

    if (_hoverRafPending) return;
    _hoverRafPending = true;

    requestAnimationFrame(_flushHoverUpdate);
  }

  function registerChart(panelKey, chartInstance) {
    const key = String(panelKey);

    _charts.set(key, chartInstance);

    const shouldHover = !!(
      _hoveredPanelKey.value && key === _hoveredPanelKey.value
    );
    _applyAxisPointerModeToChart(chartInstance, shouldHover);
    _hoverModeApplied.set(key, shouldHover);
  }

  function unregisterChart(panelKey) {
    const key = String(panelKey);

    _charts.delete(key);
    _hoverModeApplied.delete(key);

    if (_lastHoveredKey.value === key) {
      _lastHoveredKey.value = null;
      _hoveredPanelKey.value = null;
      _hoverPendingKey = null;
    }
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

    if (!Number.isFinite(idx) || idx < 0 || idx >= len) return;

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
    if (startIdx < 0 || startIdx >= len) startIdx = eIdxNow;

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
    } catch { }
    return null;
  }

  function setIndicatorPanes(panes) {
    _indicatorPanes.value = Array.isArray(panes) ? [...panes] : [];
  }

  function setMarketView(vm) {
    _vmRef.vm = vm;

    const hub = useViewCommandHub();
    hub.setMarketView(vm);

    watch(
      () => [
        vm.candles.value,
        vm.indicators.value,
        vm.meta.value,
        _indicatorPanes.value,
      ],
      () => {
        if (_batchFlag.value) {
          _pendingCompute.value = true;
          return;
        }
        _computeAndPublish();
      }
    );

    // RenderHub 不再因“宽度变化”做全量重算；宽度由实例侧 WidthController+widthState 驱动。
  }

  function onRender(cb) {
    const id = _nextId++;
    _subs.set(id, typeof cb === "function" ? cb : () => { });
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
      } catch { }
    });
  }

  function _resolveSymbolMetaForCurrent() {
    const vm = _vmRef.vm;
    if (!vm) return { symbol: "", ipoYmd: null };

    let sym = "";
    try {
      if (vm.code && typeof vm.code.value === "string" && vm.code.value) {
        sym = vm.code.value.trim();
      } else if (vm.meta && vm.meta.value && vm.meta.value.symbol) {
        sym = String(vm.meta.value.symbol || "").trim();
      }
    } catch {
      sym = "";
    }
    if (!sym) return { symbol: "", ipoYmd: null };

    let ipoYmd = null;
    try {
      const entry = symbolIndex.findBySymbol(sym);
      if (entry) {
        const raw =
          entry.listingDate != null ? entry.listingDate : entry.listing_date;
        if (raw != null) {
          const n = Number(raw);
          if (Number.isFinite(n) && n > 19000000 && n < 30000000) {
            ipoYmd = n;
          }
        }
      }
    } catch { }

    return { symbol: sym, ipoYmd };
  }

  // ===== tsArr 缓存（避免每次 candles.map(ts)）=====
  const _tsArrMemo = {
    candlesRef: null,
    len: 0,
    firstTs: null,
    lastTs: null,
    tsArr: null,
  };

  function _getTsArr(candles) {
    const arr = Array.isArray(candles) ? candles : [];
    const len = arr.length;
    if (!len) {
      _tsArrMemo.candlesRef = null;
      _tsArrMemo.len = 0;
      _tsArrMemo.firstTs = null;
      _tsArrMemo.lastTs = null;
      _tsArrMemo.tsArr = [];
      return [];
    }

    const firstTs = arr[0]?.ts;
    const lastTs = arr[len - 1]?.ts;

    if (
      _tsArrMemo.candlesRef === arr &&
      _tsArrMemo.len === len &&
      _tsArrMemo.firstTs === firstTs &&
      _tsArrMemo.lastTs === lastTs &&
      Array.isArray(_tsArrMemo.tsArr) &&
      _tsArrMemo.tsArr.length === len
    ) {
      return _tsArrMemo.tsArr;
    }

    const tsArr = new Array(len);
    for (let i = 0; i < len; i++) tsArr[i] = arr[i]?.ts;

    _tsArrMemo.candlesRef = arr;
    _tsArrMemo.len = len;
    _tsArrMemo.firstTs = firstTs;
    _tsArrMemo.lastTs = lastTs;
    _tsArrMemo.tsArr = tsArr;

    return tsArr;
  }

  // upperBound: 返回最后一个 <= target 的索引（若全部 > target 则返回 -1）
  function upperBoundLE(arr, target) {
    const n = Array.isArray(arr) ? arr.length : 0;
    if (!n) return -1;
    let lo = 0,
      hi = n - 1,
      ans = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const v = Number(arr[mid]);
      if (!Number.isFinite(v)) {
        hi = mid - 1;
        continue;
      }
      if (v <= target) {
        ans = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    return ans;
  }

  // ===== Chan 缓存分层：includeMemo + derivedMemo =====
  const _includeMemo = {
    key: null,
    value: null,
  };
  const _chanDerivedMemo = {
    key: null,
    value: null,
  };

  function _makeCandlesKey(candles) {
    const arr = Array.isArray(candles) ? candles : [];
    const len = arr.length;
    if (!len) return "0";
    const first = arr[0]?.ts;
    const last = arr[len - 1]?.ts;
    return `${len}|${first}|${last}`;
  }

  function _makeIncludeKey({ candlesKey, anchorPolicy, ipoYmd }) {
    return `${candlesKey}|ap=${anchorPolicy}|ipo=${ipoYmd ?? "null"}`;
  }

  function _makeDerivedKey({ includeKey, frMinTick, frMinPct, frMinCond }) {
    return `${includeKey}|tick=${frMinTick}|pct=${frMinPct}|cond=${frMinCond}`;
  }

  function _emptyChanStruct() {
    return {
      reduced: [],
      map: [],
      meta: null,
      fractals: [],
      fractalConfirmPairs: { pairs: [], paired: [], role: [] },
      pens: { confirmed: [] },
      metaSegments: [],
      finalSegments: [],
      barriersIndices: [],
      pivots: [],
    };
  }

  function _calculateChanStructures(candles) {
    if (!candles || !candles.length) {
      // 清理 memo（避免旧引用误用）
      _includeMemo.key = null;
      _includeMemo.value = null;
      _chanDerivedMemo.key = null;
      _chanDerivedMemo.value = null;
      return _emptyChanStruct();
    }

    const { ipoYmd } = _resolveSymbolMetaForCurrent();
    const anchorPolicy =
      settings.chanTheory.chanSettings.anchorPolicy || CHAN_DEFAULTS.anchorPolicy;

    const frMinTick = settings.chanTheory.fractalSettings.minTickCount || 0;
    const frMinPct = settings.chanTheory.fractalSettings.minPct || 0;
    const frMinCond = String(settings.chanTheory.fractalSettings.minCond || "or");

    const candlesKey = _makeCandlesKey(candles);

    // ===== L1: include 缓存 =====
    const includeKey = _makeIncludeKey({ candlesKey, anchorPolicy, ipoYmd });

    let includeRes = null;
    if (_includeMemo.key === includeKey && _includeMemo.value) {
      includeRes = _includeMemo.value;
    } else {
      includeRes = computeInclude(candles, { anchorPolicy, ipoYmd });

      // 仅当结果结构可用时写入 memo
      _includeMemo.key = includeKey;
      _includeMemo.value = includeRes;

      // include 变更会导致 derived 全部失效（最简清理）
      _chanDerivedMemo.key = null;
      _chanDerivedMemo.value = null;
    }

    const reducedBars = includeRes?.reducedBars || [];
    const mapOrigToReduced = includeRes?.mapOrigToReduced || [];
    const meta = includeRes?.meta || null;

    // ===== L2: derived 缓存（基于 includeKey + fractal 参数）=====
    const derivedKey = _makeDerivedKey({
      includeKey,
      frMinTick,
      frMinPct,
      frMinCond,
    });

    if (_chanDerivedMemo.key === derivedKey && _chanDerivedMemo.value) {
      const v = _chanDerivedMemo.value;
      return {
        reduced: reducedBars,
        map: mapOrigToReduced,
        meta,
        fractals: v.fractals,
        fractalConfirmPairs: v.fractalConfirmPairs,
        pens: v.pens,
        metaSegments: v.metaSegments,
        finalSegments: v.finalSegments,
        barriersIndices: v.barriersIndices,
        pivots: v.pivots,
      };
    }

    const fr = computeFractals(candles, reducedBars, {
      minTickCount: frMinTick,
      minPct: frMinPct,
      minCond: frMinCond,
    });

    const frConfirm = computeFractalConfirmPairs(candles, reducedBars, fr || []);

    const pens = computePens(
      candles,
      reducedBars,
      fr || [],
      mapOrigToReduced || [],
      { minGapReduced: 4 }
    );

    const segRes = computeSegments(candles, reducedBars, pens.confirmed || []);
    const metaSegments = Array.isArray(segRes?.metaSegments)
      ? segRes.metaSegments
      : [];
    const finalSegments = Array.isArray(segRes?.finalSegments)
      ? segRes.finalSegments
      : [];

    const barrierIdxList = (reducedBars || []).reduce((acc, cur, i, arr) => {
      if (cur && cur.barrier_after_prev_bool) {
        const prev = i > 0 ? arr[i - 1] : null;
        if (prev) acc.push(prev.end_idx_orig);
        acc.push(cur.start_idx_orig);
      }
      return acc;
    }, []);

    const pivots = computePenPivots(pens.confirmed || []);

    _chanDerivedMemo.key = derivedKey;
    _chanDerivedMemo.value = {
      fractals: fr,
      fractalConfirmPairs: frConfirm,
      pens,
      metaSegments,
      finalSegments,
      barriersIndices: barrierIdxList,
      pivots,
    };

    return {
      reduced: reducedBars,
      map: mapOrigToReduced,
      meta,
      fractals: fr,
      fractalConfirmPairs: frConfirm,
      pens,
      metaSegments,
      finalSegments,
      barriersIndices: barrierIdxList,
      pivots,
    };
  }

  function _buildOverlaySeriesForOption({ hostW, visCount, chanCache, candles }) {
    const out = [];
    const {
      reduced,
      fractals,
      fractalConfirmPairs,
      pens,
      metaSegments,
      finalSegments,
      barriersIndices,
      pivots,
    } = chanCache;

    if (barriersIndices?.length)
      out.push(...(buildBarrierLines(barriersIndices).series || []));

    if (settings.chanTheory.chanSettings.showUpDownMarkers && reduced?.length) {
      out.push(
        ...(buildUpDownMarkers(reduced, {
          hostWidth: hostW,
          visCount,
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
          candles,
          confirmPairs: fractalConfirmPairs,
          hostWidth: hostW,
          visCount,
        }).series || [])
      );
    }

    const penEnabled =
      (settings.chanTheory.chanSettings?.pen?.enabled ?? PENS_DEFAULTS.enabled) ===
      true;
    if (penEnabled && reduced?.length && (pens?.confirmed?.length || pens?.provisional)) {
      out.push(
        ...(buildPenLines(pens, {
          candles,
          barrierIdxList: barriersIndices,
        }).series || [])
      );
    }

    if (metaSegments?.length || finalSegments?.length) {
      out.push(
        ...(buildSegmentLines(
          { metaSegments, finalSegments },
          { candles, barrierIdxList: barriersIndices }
        ).series || [])
      );
    }

    if (pivots?.length) {
      out.push(
        ...(buildPenPivotAreas(pivots, { barrierIdxList: barriersIndices }).series ||
          [])
      );
    }

    return out;
  }

  async function _buildMainOption(vm, chanCache, context) {
    const { initialRange, tipPositioner, hoveredKey, st, bars } = context;

    const buildMain = await chartBuilderRegistry.get("MAIN");
    if (!buildMain) return { series: [] };

    const anyMarkers =
      (settings.chanTheory.chanSettings.showUpDownMarkers ?? true) &&
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
        anchorPolicy: settings.chanTheory.chanSettings.anchorPolicy,
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
      chanCache,
      candles: vm.candles.value,
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
    if (!builder) return null;

    const commonParams = {
      candles: vm.candles.value,
      indicators: vm.indicators.value,
      freq: vm.freq.value,
    };

    if (key === "VOL" || key === "AMOUNT") {
      const volCfg = settings.chartDisplay.volSettings || {};
      const finalVolCfg = { ...volCfg, mode: key === "AMOUNT" ? "amount" : "vol" };
      return builder({ ...commonParams, volCfg: finalVolCfg }, ui);
    }

    if (key === "MACD") {
      const macdCfg = settings.chartDisplay.macdSettings || {};
      return builder({ ...commonParams, macdCfg }, ui);
    }

    if (key === "KDJ") return builder({ ...commonParams, useKDJ: true }, ui);
    if (key === "RSI") return builder({ ...commonParams, useRSI: true }, ui);

    return builder(commonParams, ui);
  }

  async function _buildIndicatorOptions(context) {
    const { initialRange, tipPositioner, hoveredKey } = context;
    const indicatorOptions = {};

    for (const pane of _indicatorPanes.value) {
      if (!pane || !pane.id || pane.kind === "OFF") continue;
      const paneKey = `indicator:${pane.id}`;

      try {
        const kind = String(pane.kind || "").toUpperCase();

        const ui =
          kind === "VOL" || kind === "AMOUNT"
            ? {
              initialRange,
              tooltipPositioner: tipPositioner,
              isHovered: hoveredKey === paneKey,
              paneId: pane.id,
            }
            : {
              initialRange,
              tooltipPositioner: tipPositioner,
              isHovered: hoveredKey === paneKey,
            };

        const option = await _getIndicatorOption(pane.kind, ui);

        if (option) indicatorOptions[pane.id] = option;
      } catch { }
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

    const tsArr = _getTsArr(candles);

    let eIdx = len - 1;
    if (Number.isFinite(st.rightTs)) {
      const pos = upperBoundLE(tsArr, st.rightTs);
      eIdx = pos >= 0 ? pos : 0;
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

    // DEV ONLY: 暴露 Chan 结构中间数据，便于控制台导出定位（不影响生产）
    if (import.meta.env.DEV) {
      try {
        window.__DEBUG__ = window.__DEBUG__ || {};
        window.__DEBUG__.chanCache = _chanCache.value;
      } catch { }
    }

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

    // DEV ONLY: 暴露最后一次渲染快照（含 main option / indicatorOptions）
    if (import.meta.env.DEV) {
      try {
        window.__DEBUG__ = window.__DEBUG__ || {};
        window.__DEBUG__.lastSnapshot = snapshot;
      } catch { }
    }

    _publish(snapshot);
  }

  async function _executeBatch(asyncTask) {
    _batchFlag.value = true;
    _pendingCompute.value = false;

    try {
      await asyncTask();
    } finally {
      _batchFlag.value = false;

      if (_pendingCompute.value) {
        await nextTick();
        _computeAndPublish();
      }
    }
  }

  _singleton = {
    setMarketView,
    onRender,
    offRender,
    getTipPositioner() {
      return _getTipPositioner();
    },
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
    _executeBatch,
  };

  return _singleton;
}
