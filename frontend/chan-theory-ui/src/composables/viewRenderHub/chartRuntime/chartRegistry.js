// src/composables/viewRenderHub/chartRuntime/chartRegistry.js
// ==============================
// 图表实例注册表 + activePanel 管理 + 主图 focus sync
// 迁移自原 useViewRenderHub：registerChart/unregisterChart/getChart/getActiveChart/setActivePanel/_attachMainFocusSync 等。
// ==============================

export function createChartRegistry({ state }) {
  function attachMainFocusSync(chartInstance) {
    if (!chartInstance) return;

    try {
      chartInstance.off("updateAxisPointer");
    } catch {}

    try {
      chartInstance.on("updateAxisPointer", (e) => {
        try {
          const ai = Array.isArray(e?.axesInfo) ? e.axesInfo : [];
          const info = ai && ai.length ? ai[0] : null;
          const idx0 =
            info && typeof info.value !== "undefined" ? Number(info.value) : NaN;
          if (!Number.isFinite(idx0)) return;

          const vm = state.vmRef.vm;
          const len = Array.isArray(vm?.candles?.value) ? vm.candles.value.length : 0;
          if (!len) return;

          const idx = Math.max(0, Math.min(len - 1, Math.floor(idx0)));
          state.currentFocusIdx.value = idx;
        } catch {}
      });
    } catch {}
  }

  function registerChart(panelKey, chartInstance) {
    const key = String(panelKey);

    state.charts.set(key, chartInstance);

    // hover 模式是否显示 axisPointer 由 hoverMode 模块接管；
    // registry 只负责存储与主图 focus 绑定。
    if (key === "main") {
      attachMainFocusSync(chartInstance);
    }
  }

  function unregisterChart(panelKey) {
    const key = String(panelKey);

    try {
      const c = state.charts.get(key);
      if (c && key === "main") {
        try {
          c.off("updateAxisPointer");
        } catch {}
      }
    } catch {}

    state.charts.delete(key);

    if (String(state.activePanelKey.value || "") === key) {
      state.activePanelKey.value = "main";
    }
  }

  function setActivePanel(panelKey) {
    state.activePanelKey.value = String(panelKey);
  }

  function getActivePanel() {
    return String(state.activePanelKey.value || "main");
  }

  function getChart(panelKey) {
    return state.charts.get(String(panelKey)) || null;
  }

  function getActiveChart() {
    return state.charts.get(String(state.activePanelKey.value)) || null;
  }

  function syncFocusPosition(idx) {
    const vm = state.vmRef.vm;
    if (!vm) return;

    const arr = vm.candles.value || [];
    const len = arr.length;

    if (!Number.isFinite(idx) || idx < 0 || idx >= len) return;

    state.currentFocusIdx.value = idx;
  }

  function resetFocusIndex() {
    state.currentFocusIdx.value = -1;
  }

  return {
    registerChart,
    unregisterChart,
    setActivePanel,
    getActivePanel,
    getChart,
    getActiveChart,
    syncFocusPosition,
    resetFocusIndex,
  };
}
