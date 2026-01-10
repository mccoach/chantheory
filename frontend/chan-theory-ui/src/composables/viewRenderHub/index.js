// src/composables/viewRenderHub/index.js
// ==============================
// ViewRenderHub 包入口（folder + index）
//
// 调序说明（必读）：
// - 原先所有实现集中在 src/composables/useViewRenderHub.js（巨无霸）。
// - 本次为满足“职责单一/高内聚低耦合/单例语义唯一状态源”，
//   将其拆分为多个模块；本文件负责：
//     1) 创建并持有唯一的共享 state（Single Source of Truth）；
//     2) 组装各子模块并导出对外 API；
//     3) 维持原 useViewRenderHub 的对外方法与语义完全一致；
//     4) 禁止任何子模块各自持有单例，避免隐性多例。
// - 拆分是结构性调序，不改变业务行为。
// ==============================

import { ref } from "vue";

import { createRenderPipeline } from "./renderPipeline";
import { createChartRegistry } from "./chartRuntime/chartRegistry";
import { createHoverMode } from "./chartRuntime/hoverMode";
import { createCursorMove } from "./chartRuntime/cursorMove";

let _singleton = null;

export function useViewRenderHub() {
  if (_singleton) return _singleton;

  // ==============================
  // 统一共享状态（唯一真相源）
  // ==============================
  const state = {
    settings: null,     // lazy set in createRenderPipeline
    symbolIndex: null,  // lazy set in createRenderPipeline

    vmRef: { vm: null },

    hoveredPanelKey: ref(null),

    subs: new Map(),
    nextSubId: 1,

    lastSnapshot: ref(null),
    renderSeq: 0,

    indicatorPanes: ref([]),
    chanCache: ref({}),

    charts: new Map(),
    activePanelKey: ref("main"),

    currentFocusIdx: ref(-1),

    // batch compute flags
    batchFlag: ref(false),
    pendingCompute: ref(false),

    // tooltip mode
    tipMode: ref("follow"),
  };

  // ==============================
  // chart runtime: registry + hover + cursor
  // ==============================
  const registryCore = createChartRegistry({ state });
  const hover = createHoverMode({ state, registry: registryCore });
  const cursor = createCursorMove({ state, registry: registryCore });

  // registry wrapper：注册时同步 hover 模式（行为回归）
  const registry = {
    ...registryCore,
    registerChart(panelKey, chartInstance) {
      registryCore.registerChart(panelKey, chartInstance);
      hover.applyCurrentHoverToChart(panelKey);
    },
    unregisterChart(panelKey) {
      registryCore.unregisterChart(panelKey);
      hover.clearChart(panelKey);
    },
  };

  // ==============================
  // render pipeline
  // ==============================
  const pipeline = createRenderPipeline({
    state,
    registry,
  });

  // tooltip mode global event (保持原逻辑)
  try {
    window.addEventListener("chan:set-tooltip-mode", (e) => {
      const m = String(e?.detail?.mode || "").toLowerCase();
      state.tipMode.value = m === "follow" ? "follow" : "fixed";
      pipeline.computeAndPublish();
    });
  } catch {}

  // ==============================
  // 对外 API（保持原 useViewRenderHub 完全一致）
  // ==============================
  _singleton = {
    // core binding
    setMarketView: pipeline.setMarketView,

    // render subscribe
    onRender: pipeline.onRender,
    offRender: pipeline.offRender,

    // tooltip positioner getter (for external)
    getTipPositioner: pipeline.getTipPositioner,

    // hover
    setHoveredPanel: hover.setHoveredPanel,

    // chart runtime registry
    registerChart: registry.registerChart,
    unregisterChart: registry.unregisterChart,
    setActivePanel: registry.setActivePanel,
    getActivePanel: registry.getActivePanel,
    getChart: registry.getChart,
    getActiveChart: registry.getActiveChart,

    // cursor move (keyboard)
    moveCursorByStep: cursor.moveCursorByStep,

    // indicator panes
    setIndicatorPanes: pipeline.setIndicatorPanes,

    // explicit render request
    requestRender: pipeline.requestRender,

    // focus sync
    syncFocusPosition: registry.syncFocusPosition,
    resetFocusIndex: registry.resetFocusIndex,

    // batch executor (used by MarketView)
    _executeBatch: pipeline.executeBatch,
  };

  return _singleton;
}
