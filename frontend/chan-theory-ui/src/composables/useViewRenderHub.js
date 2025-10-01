// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useViewRenderHub.js
// ==============================
// 说明：统一渲染快照中枢（上游唯一源头）
// - 责任：一次性计算并发布所有窗体所需的渲染参数（统一离散范围 sIdx/eIdx、markerWidthPx、主窗/量窗 option）。
// - 下游：主窗/量窗/技术窗一次订阅一次渲染（不再分散监听 meta/事件、不再使用 zoomSync    chan:marker-size）。
// - 触发：hub.onChange（两帧合并后的最终态）与 vm 数据落地（candles/indicators/meta）。
// ==============================

import { ref, watch } from "vue";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useUserSettings } from "@/composables/useUserSettings";
import {
  buildMainChartOption,
  buildVolumeOption,
  buildMacdOption,
  buildKdjOrRsiOption,
  createFixedTooltipPositioner,        // MOD: 引入固定定位器
} from "@/charts/options";

let _singleton = null;

export function useViewRenderHub() {
  if (_singleton) return _singleton;

  const hub = useViewCommandHub();
  const settings = useUserSettings();

  // 上游数据句柄（由 App 注入）
  const _vmRef = { vm: null };

  // 新增：当前悬浮的面板 key ('main'|'volume'|'indicator'|null)
  const _hoveredPanelKey = ref(null); // NEW

  // 订阅者
  const _subs = new Map();
  let _nextId = 1;

  // 最近一次快照与序号
  const _lastSnapshot = ref(null);
  let _renderSeq = 0;

  // MOD: 统一 tooltip 模式（ fixed | follow ），默认固定；提供全局事件切换
  const tipMode = ref("follow"); // 默认固定（与现实现一致）
  try {
    window.addEventListener("chan:set-tooltip-mode", (e) => {
      const m = String(e?.detail?.mode || "").toLowerCase();
      tipMode.value = m === "follow" ? "follow" : "fixed";
      // 可选：立即推送一次快照，促使各窗重绘（避免等待下一次中枢状态变化）
      try { _computeAndPublish(); } catch {}
    });
  } catch {}

  // 统一获取定位器：fixed → 返回固定器；follow → 返回 undefined（让 ECharts 跟随鼠标）
  function _getTipPositioner() {
    if (tipMode.value === "fixed") return createFixedTooltipPositioner("left");
    return undefined; // 不设 position 即默认跟随鼠标
  }

  // ==============================
  // NEW: 交互会话锁（ECharts-first 禁止抢权）
  // ==============================
  const _interacting = ref(false);
  let _interactionSource = null;

  function beginInteraction(source) {
    // 交互开始：各窗 dataZoom 会话内调用
    _interacting.value = true;
    _interactionSource = source || _interactionSource;
  }
  function endInteraction(source) {
    // 交互结束：idle-commit 后调用
    _interacting.value = false;
    _interactionSource = null;
  }
  function isInteracting() {
    return !!_interacting.value;
  }

  // 新增：由各窗体调用，上报悬浮状态
  function setHoveredPanel(panelKey) {
    if (_hoveredPanelKey.value !== panelKey) {
      _hoveredPanelKey.value = panelKey;
    }
  }

  // 新增：监听悬浮面板变化，触发一次渲染快照的重新计算与发布
  watch(_hoveredPanelKey, () => {
    _computeAndPublish();
  });

  // ==============================
  // NEW: 图表实例注册与“激活窗体”管理
  // 用途：键盘动作/程序化驱动应作用于当前激活窗体的 chart 实例
  // ==============================
  const _charts = new Map();           // panelKey -> chartInstance
  const _activePanelKey = ref("main"); // 默认主窗激活

  function registerChart(panelKey, chartInstance) {
    try {
      if (!panelKey || !chartInstance) return;
      _charts.set(String(panelKey), chartInstance);
    } catch {}
  }
  function unregisterChart(panelKey) {
    try {
      if (!panelKey) return;
      _charts.delete(String(panelKey));
    } catch {}
  }
  function setActivePanel(panelKey) {
    try {
      if (!panelKey) return;
      _activePanelKey.value = String(panelKey);
    } catch {}
  }
  function getActivePanel() {
    return String(_activePanelKey.value || "main");
  }
  function getChart(panelKey) {
    try {
      return _charts.get(String(panelKey)) || null;
    } catch { return null; }
  }
  function getActiveChart() {
    try {
      return _charts.get(String(_activePanelKey.value)) || null;
    } catch { return null; }
  }

  /**
   * NEW: 读取指定 chart 的当前 dataZoom 范围（startValue/endValue）
   */
  function _getZoomRangeOf(chartInstance) {
    try {
      const c = chartInstance;
      if (!c || typeof c.getOption !== "function") return null;
      const opt = c.getOption();
      const dz = Array.isArray(opt?.dataZoom) ? opt.dataZoom : [];
      if (!dz.length) return null;
      const z = dz.find(
        (x) =>
          typeof x.startValue !== "undefined" && typeof x.endValue !== "undefined"
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

  /**
   * NEW: 键盘步进移动十字线（ECharts-first；作用于当前激活窗体）
   * @param {number} dir -1 左，一步；+1 右，一步
   */
  function moveCursorByStep(dir) {
    try {
      const vm = _vmRef.vm;
      if (!vm) return;
      const arr = vm.candles.value || [];
      const len = arr.length;
      if (!len) return;

      const activeChart = getActiveChart();
      const zoomRange = _getZoomRangeOf(activeChart);
      const sIdxNow =
        zoomRange && Number.isFinite(zoomRange.sIdx)
          ? zoomRange.sIdx
          : Number(vm.meta.value?.view_start_idx ?? 0);
      const eIdxNow =
        zoomRange && Number.isFinite(zoomRange.eIdx)
          ? zoomRange.eIdx
          : Number(vm.meta.value?.view_end_idx ?? len - 1);

      const tsArr = arr.map((d) => Date.parse(d.t));

      // 起点优先 lastFocusTs；缺失时退回右端
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

      // 视界内：仅移动十字线
      try {
        activeChart?.dispatchAction({
          type: "showTip",
          seriesIndex: 0,
          dataIndex: nextIdx,
        });
      } catch {}

      // 持久化起点（鼠标/键盘一致）
      try {
        const tsv = tsArr[nextIdx];
        if (Number.isFinite(tsv)) {
          settings.setLastFocusTs(vm.code.value, vm.freq.value, tsv);
        }
      } catch {}

      if (inView) return;

      // 越界：轻推视窗一格，并把十字线停在边缘
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
        activeChart?.dispatchAction({
          type: "dataZoom",
          startValue: newS,
          endValue: newE,
        });
        const edgeIdx = nextIdx < sIdxNow ? newS : newE;
        activeChart?.dispatchAction({
          type: "showTip",
          seriesIndex: 0,
          dataIndex: edgeIdx,
        });
      } catch {}
      // 会后承接按各窗 onDataZoom 的 idle-commit 完成。
    } catch {}
  }
  function setMarketView(vm) {
    _vmRef.vm = vm;
    // 订阅数据变更以触发统一计算
    watch(
      () => [vm.candles.value, vm.indicators.value, vm.meta.value],
      () => {
        _computeAndPublish();
      },
      { deep: true }
    );
  }

  function onRender(cb) {
    const id = _nextId++;
    _subs.set(id, typeof cb === "function" ? cb : () => {});
    // 初次订阅时若已有快照，立即推送一次
    try {
      if (_lastSnapshot.value) cb(_lastSnapshot.value);
    } catch {}
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

  function _computeAndPublish() {
    const vm = _vmRef.vm;
    if (!vm) return;

    const candles = vm.candles.value || [];
    const indicators = vm.indicators.value || {};
    const freq = vm.freq.value || "1d";

    const len = candles.length;
    if (!len) return;

    // 统一离散范围（基于 hub 快照：barsCount + rightTs）
    const st = hub.getState();
    const bars = Math.max(1, Number(st.barsCount || 1));
    const tsArr = candles.map((d) => {
      try {
        return Date.parse(d.t);
      } catch {
        return NaN;
      }
    });

    let eIdx = len - 1;
    if (Number.isFinite(st.rightTs)) {
      for (let i = len - 1; i >= 0; i--) {
        const tsv = tsArr[i];
        if (Number.isFinite(tsv) && tsv <= st.rightTs) {
          eIdx = i;
          break;
        }
      }
    }
    let sIdx = Math.max(0, eIdx - bars + 1);
    if (sIdx === 0 && eIdx - sIdx + 1 < bars) {
      eIdx = Math.min(len - 1, bars - 1);
    }

    const initialRange = { startValue: sIdx, endValue: eIdx };
    const markerW = st.markerWidthPx; // 统一来源：hub 派生宽度

    // MOD: 统一生成定位器（fixed or follow）
    const tipPositioner = _getTipPositioner();

    // NEW: 获取当前悬浮面板 key
    const hoveredKey = _hoveredPanelKey.value;

    // 主窗 option（上游统一位置源写入）
    const mainOption = buildMainChartOption(
      {
        candles,
        indicators,
        chartType: vm.chartType.value || "kline",
        maConfigs: settings.maConfigs.value,
        freq,
        klineStyle: settings.klineStyle.value,
        adjust: vm.adjust.value || "none",
        // CHAN 数据由主窗内现有 computeInclude/computeFractals 继续处理，保持最小改动
        reducedBars: [],
        mapOrigToReduced: [],
      },
      {
        initialRange,
        tooltipPositioner: tipPositioner, // MOD: 统一注入定位器
        isHovered: hoveredKey === "main", // NEW: 传入悬浮状态
      }
    );

    // 构建量窗 option（一次；统一 overrideMarkWidth）
    const volumeOption = buildVolumeOption(
      {
        candles,
        indicators,
        freq,
        volCfg: settings.volSettings.value,
        volEnv: {
          hostWidth: 0, // 由 ECharts 计算，保持 0；真实宽度不影响 initialRange
          visCount: bars,
          overrideMarkWidth: markerW,
        },
      },
      {
        initialRange,
        tooltipPositioner: tipPositioner, // MOD: 统一注入定位器
        isHovered: hoveredKey === "volume", // NEW: 传入悬浮状态
      }
    );

    // 构建默认指标窗（提供工具方法获取具体 kind 的 option；此处留空由 IndicatorPanel 请求）
    const dataForIndicators = { candles, indicators, freq, initialRange };

    const snapshot = {
      seq: ++_renderSeq,
      core: {
        code: vm.code.value || "",
        freq,
        adjust: vm.adjust.value || "none",
        barsCount: bars,
        rightTs: st.rightTs,
        sIdx,
        eIdx,
        allRows: len,
        atRightEdge: !!st.atRightEdge,
        markerWidthPx: markerW,
      },
      // MOD: 根因修复 - 将 isHovered 状态存入快照
      main: {
        option: mainOption,
        range: initialRange,
        isHovered: hoveredKey === "main",
      },
      volume: {
        option: volumeOption,
        range: initialRange,
        isHovered: hoveredKey === "volume",
      },
      indicatorsBase: {
        candles,
        indicators,
        freq,
        initialRange,
        isHovered: hoveredKey === "indicator",
      },
      metaLink: {
        generated_at: vm.meta.value?.generated_at || "",
        source: vm.meta.value?.source || "",
        downsample_from: vm.meta.value?.downsample_from || null,
      },
    };

    _publish(snapshot);
  }

  // 订阅 hub 的两帧合并广播，统一触发一次计算
  hub.onChange(() => {
    _computeAndPublish();
  });

  function getIndicatorOption(kind) {
    const base = _lastSnapshot.value?.indicatorsBase;
    if (!base) return null;

    // MOD: 指标窗也复用同一定位器
    const tipPositioner = _getTipPositioner();
    // NEW: 指标窗也需要 isHovered 状态
    const ui = {
      initialRange: base.initialRange,
      tooltipPositioner: tipPositioner,
      isHovered: base.isHovered, // 从快照中读取
    };

    const K = String(kind || "").toUpperCase();
    if (K === "MACD") {
      return buildMacdOption({ candles: base.candles, indicators: base.indicators, freq: base.freq }, ui);
    }
    if (K === "KDJ") {
      return buildKdjOrRsiOption({ candles: base.candles, indicators: base.indicators, freq: base.freq, useKDJ: true, useRSI: false }, ui);
    }
    if (K === "RSI") {
      return buildKdjOrRsiOption({ candles: base.candles, indicators: base.indicators, freq: base.freq, useKDJ: false, useRSI: true }, ui);
    }
    if (K === "BOLL") {
      return buildKdjOrRsiOption({ candles: base.candles, indicators: base.indicators, freq: base.freq, useKDJ: false, useRSI: true }, ui);
    }
    return buildMacdOption({ candles: base.candles, indicators: base.indicators, freq: base.freq }, ui);
  }

  // 新增：暴露统一源头的 tooltip 位置获取（供主窗订阅使用）
  function getTipPositioner() {
    return _getTipPositioner();
  }

  _singleton = {
    setMarketView,
    onRender,
    offRender,
    getIndicatorOption,
    getTipPositioner,
    setHoveredPanel, // NEW: 暴露给各窗体调用
    // NEW: 交互会话锁导出（供各窗体使用）
    beginInteraction,
    endInteraction,
    isInteracting,
    // NEW: 图表注册与激活面板管理
    registerChart,
    unregisterChart,
    setActivePanel,
    getActivePanel,
    getChart,
    getActiveChart,
    // NEW: 键盘步进移动
    moveCursorByStep,
  };
  return _singleton;
}
