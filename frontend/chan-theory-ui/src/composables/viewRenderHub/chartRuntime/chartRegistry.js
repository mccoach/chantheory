// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\viewRenderHub\chartRuntime\chartRegistry.js
// ==============================
// 图表实例注册表 + activePanel 管理 + 主图 focus sync
// ==============================

import { useViewCommandHub } from "@/composables/useViewCommandHub";

export function createChartRegistry({ state }) {
  function attachMainFocusSync(chartInstance) {
    if (!chartInstance) return;

    const hub = useViewCommandHub();

    // 清理旧监听，避免重复注册（单一链路）
    try { chartInstance.off("updateAxisPointer"); } catch {}
    try { chartInstance.off("showTip"); } catch {}

    // 1) updateAxisPointer：仅用于维护渲染侧 currentFocusIdx（不做持久化）
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

    // 2) showTip：唯一“持久化 tooltip 基点”的入口
    // 语义严格按你定义：只要系统显示了某根 bar 的 tooltip，就立刻持久化该 bar.ts。
    try {
      chartInstance.on("showTip", (e) => {
        try {
          const vm = state.vmRef.vm;
          const arr = vm?.candles?.value || [];
          const len = Array.isArray(arr) ? arr.length : 0;
          if (!len) return;

          const idx0 = Number(e?.dataIndex);
          if (!Number.isFinite(idx0)) return;

          const idx = Math.max(0, Math.min(len - 1, Math.floor(idx0)));
          const ts = Number(arr[idx]?.ts);
          if (!Number.isFinite(ts)) return;

          hub.execute("SyncTipTs", { tipTs: ts, silent: false });
        } catch {}
      });
    } catch {}
  }

  function registerChart(panelKey, chartInstance) {
    const key = String(panelKey);

    state.charts.set(key, chartInstance);

    if (key === "main") {
      attachMainFocusSync(chartInstance);
    }
  }

  function unregisterChart(panelKey) {
    const key = String(panelKey);

    try {
      const c = state.charts.get(key);
      if (c && key === "main") {
        try { c.off("updateAxisPointer"); } catch {}
        try { c.off("showTip"); } catch {}
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
