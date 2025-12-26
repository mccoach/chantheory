// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useViewRenderHub.js
// ==============================
// V10.2 - 连续性屏障接入上市日期 + 交易日历版
//
// 当前版本改动点：
//   - 同时绘制元线段(metaSegments)与最终线段(finalSegments)
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

  // ===== 批处理控制变量 =====
  const _batchFlag = ref(false); // 批处理模式标志
  const _pendingCompute = ref(false); // 待处理计算标志

  // ===== 标记宽度缓存（用于检测变化）=====
  const _lastMarkerWidth = ref(8); // 默认值与 hub 初始值一致

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
      // 悬浮窗体变化时，刷新各图的 axisPointer 模式
      _updateAxisPointerModes();
    }
  }

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

  // 根据当前悬浮窗体切换各图的 axisPointer 模式
  function _updateAxisPointerModes() {
    const hovered = _hoveredPanelKey.value;

    _charts.forEach((chartInstance, panelKey) => {
      try {
        const isHovered = hovered && panelKey === hovered;
        const opt = chartInstance.getOption ? chartInstance.getOption() : null;
        if (!opt) return;

        // 1) 调整 tooltip：只区分 cross / line，不再控制 showContent
        const tooltipOpt = opt.tooltip || {};
        const tooltipAxisPointer = tooltipOpt.axisPointer || {};

        const newTooltip = {
          ...tooltipOpt,
          // showContent: !!isHovered,
          axisPointer: {
            ...tooltipAxisPointer,
            type: isHovered ? "cross" : "line",
          },
        };

        // 2) 调整主 y 轴的 axisPointer：仅悬浮窗体显示水平线 + y 轴气泡数字
        const yAxisOpt = opt.yAxis;
        const yAxisArr = Array.isArray(yAxisOpt)
          ? yAxisOpt
          : yAxisOpt
          ? [yAxisOpt]
          : [];

        const newYAxis = yAxisArr.map((y, idx) => {
          if (!y) return y;
          if (idx !== 0) {
            // 只控制第一个 y 轴（主轴），其余保持原样（如量窗标记轴）
            return y;
          }
          const axisPtr = y.axisPointer || {};
          const axisLabel = axisPtr.label || {};
          return {
            ...y,
            axisPointer: {
              ...axisPtr,
              show: !!isHovered,
              label: {
                ...axisLabel,
                show: !!isHovered,
              },
            },
          };
        });

        // 3) 应用部分更新（不合并 series，不触发布局重算）
        const partial = {
          tooltip: newTooltip,
        };
        if (newYAxis.length > 0) {
          partial.yAxis = newYAxis;
        }

        chartInstance.setOption(partial, false);
      } catch {}
    });
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

  // ===== 核心修复：每次设置时使用新数组引用，触发内部 watch =====
  function setIndicatorPanes(panes) {
    _indicatorPanes.value = Array.isArray(panes) ? [...panes] : [];
  }

  function setMarketView(vm) {
    _vmRef.vm = vm;

    const hub = useViewCommandHub();
    hub.setMarketView(vm);

    // ===== 原有：数据变化触发渲染 =====
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

    // ===== 新增：订阅标记宽度变化（缩放时刷新标记）=====
    hub.onChange((state) => {
      // 检测标记宽度是否变化
      if (state.markerWidthPx !== _lastMarkerWidth.value) {
        _lastMarkerWidth.value = state.markerWidthPx;

        // 触发重新渲染（更新标记宽度）
        if (!_batchFlag.value) {
          _computeAndPublish();
        }
      }
    });
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
    } catch {}

    return { symbol: sym, ipoYmd };
  }

  function _calculateChanStructures(candles) {
    if (!candles || !candles.length) {
      return {
        reduced: [],
        map: [],
        meta: null,
        fractals: [],
        fractalConfirmPairs: { pairs: [], paired: [], role: [] },
        pens: { confirmed: [] },
        // NEW: metaSegments / finalSegments
        metaSegments: [],
        finalSegments: [],
        barriersIndices: [],
        pivots: [],
      };
    }

    const { ipoYmd } = _resolveSymbolMetaForCurrent();

    const policy =
      settings.chanTheory.chanSettings.anchorPolicy ||
      CHAN_DEFAULTS.anchorPolicy;

    const res = computeInclude(candles, {
      anchorPolicy: policy,
      ipoYmd,
    });

    // ===== 改动点：computeFractals 需要 candles（Single Source of Truth）=====
    const fr = computeFractals(candles, res.reducedBars || [], {
      minTickCount: settings.chanTheory.fractalSettings.minTickCount || 0,
      minPct: settings.chanTheory.fractalSettings.minPct || 0,
      minCond: String(settings.chanTheory.fractalSettings.minCond || "or"),
    });

    // ===== NEW: 确认分型（派生结构）=====
    const frConfirm = computeFractalConfirmPairs(
      candles,
      res.reducedBars || [],
      fr || []
    );

    // NEW: 笔算法改为显式传入 candles（单一真相源）
    const pens = computePens(
      candles,
      res.reducedBars || [],
      fr || [],
      res.mapOrigToReduced || [],
      { minGapReduced: 4 }
    );

    // NEW: computeSegments 返回 { metaSegments, finalSegments }
    const segRes = computeSegments(candles, res.reducedBars || [], pens.confirmed || []);
    const metaSegments = Array.isArray(segRes?.metaSegments) ? segRes.metaSegments : [];
    const finalSegments = Array.isArray(segRes?.finalSegments) ? segRes.finalSegments : [];

    const barrierIdxList = (res.reducedBars || []).reduce((acc, cur, i, arr) => {
      if (cur && cur.barrier_after_prev_bool) {
        const prev = i > 0 ? arr[i - 1] : null;
        if (prev) acc.push(prev.end_idx_orig);
        acc.push(cur.start_idx_orig);
      }
      return acc;
    }, []);

    const pivots = computePenPivots(pens.confirmed || []);

    return {
      reduced: res.reducedBars,
      map: res.mapOrigToReduced,
      meta: res.meta,
      fractals: fr,
      fractalConfirmPairs: frConfirm,
      pens,
      metaSegments,
      finalSegments,
      barriersIndices: barrierIdxList,
      pivots,
    };
  }

  function _buildOverlaySeriesForOption({
    hostW,
    visCount,
    markerW,
    chanCache,
    candles,
  }) {
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
          candles,
          confirmPairs: fractalConfirmPairs,
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
      // NEW: 笔渲染需要 candles 以回溯端点 y
      out.push(
        ...(buildPenLines(pens, {
          candles,
          barrierIdxList: barriersIndices,
        }).series || [])
      );
    }

    // NEW: 同时绘制 元线段 + 最终线段
    // 最终线段样式：沿用当前 settings.chanTheory.chanSettings.segment（由 buildSegmentLines 内部处理）
    // 元线段样式：由 buildSegmentLines 内部使用 META_SEGMENT_DEFAULTS 常量处理
    if ((metaSegments?.length || finalSegments?.length)) {
      out.push(
        ...(buildSegmentLines(
          { metaSegments, finalSegments },
          { candles, barrierIdxList: barriersIndices }
        ).series || [])
      );
    }

    if (pivots?.length) {
      out.push(
        ...(buildPenPivotAreas(pivots, { barrierIdxList: barriersIndices }).series || [])
      );
    }

    return out;
  }

  async function _buildMainOption(vm, chanCache, context) {
    const { initialRange, tipPositioner, hoveredKey, st, bars } = context;

    const buildMain = await chartBuilderRegistry.get("MAIN");
    if (!buildMain) {
      return { series: [] };
    }

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
        // NEW: 传给主图 builder，用于合并K动态锚点推导
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
      markerW: st.markerWidthPx,
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
    if (!builder) {
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

    if (key === "MACD") {
      const macdCfg = settings.chartDisplay.macdSettings || {};
      return builder({ ...commonParams, macdCfg }, ui);
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
      } catch {}
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
    // 每次完整渲染后，按当前悬浮窗体重新修正各图的 axisPointer 模式
    _updateAxisPointerModes();
  }

  // ===== 批处理执行函数 =====
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
