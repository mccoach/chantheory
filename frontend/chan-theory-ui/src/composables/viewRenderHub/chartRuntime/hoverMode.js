// src/composables/viewRenderHub/chartRuntime/hoverMode.js
// ==============================
// hover axisPointer 模式切换（含 rAF 合并与 appliedMap）
// 迁移自原 useViewRenderHub：_applyAxisPointerModeToChart/_flushHoverUpdate 等。
// ==============================

export function createHoverMode({ state, registry }) {
  const lastHoveredKey = { value: null };
  const hoverModeApplied = new Map();
  let hoverRafPending = false;
  let hoverPendingKey = null;

  function applyAxisPointerModeToChart(chartInstance, isHovered) {
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
    } catch {}
  }

  function applyHoverModeByKey(panelKey, isHovered) {
    const key = String(panelKey || "");
    if (!key) return;

    const chart = registry.getChart(key) || null;
    if (!chart) return;

    const applied = hoverModeApplied.get(key);
    if (applied === !!isHovered) return;

    applyAxisPointerModeToChart(chart, !!isHovered);
    hoverModeApplied.set(key, !!isHovered);
  }

  function flushHoverUpdate() {
    hoverRafPending = false;

    const nextKey = hoverPendingKey ? String(hoverPendingKey) : null;
    hoverPendingKey = null;

    const prevKey = lastHoveredKey.value;

    if (prevKey === nextKey) return;

    state.hoveredPanelKey.value = nextKey;
    lastHoveredKey.value = nextKey;

    if (prevKey) applyHoverModeByKey(prevKey, false);
    if (nextKey) applyHoverModeByKey(nextKey, true);
  }

  function setHoveredPanel(panelKey) {
    const nextKey = panelKey ? String(panelKey) : null;

    if (hoverPendingKey === nextKey && hoverRafPending) return;
    if (lastHoveredKey.value === nextKey && !hoverRafPending) return;

    hoverPendingKey = nextKey;

    if (hoverRafPending) return;
    hoverRafPending = true;

    requestAnimationFrame(flushHoverUpdate);
  }

  // registerChart 后应能立刻应用 hover 状态（由外部在注册时调用）
  function applyCurrentHoverToChart(panelKey) {
    const key = String(panelKey || "");
    if (!key) return;

    const shouldHover = !!(state.hoveredPanelKey.value && key === state.hoveredPanelKey.value);
    applyHoverModeByKey(key, shouldHover);
    hoverModeApplied.set(key, shouldHover);
  }

  function clearChart(panelKey) {
    const key = String(panelKey || "");
    hoverModeApplied.delete(key);

    if (lastHoveredKey.value === key) {
      lastHoveredKey.value = null;
      state.hoveredPanelKey.value = null;
      hoverPendingKey = null;
    }
  }

  return {
    setHoveredPanel,
    applyCurrentHoverToChart,
    clearChart,
  };
}
