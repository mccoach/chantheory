// src/composables/viewRenderHub/chartRuntime/cursorMove.js
// ==============================
// 键盘游标移动（ArrowLeft/ArrowRight）
// 迁移自原 useViewRenderHub：moveCursorByStep + _getZoomRangeOf + syncFocusPosition 的协同。
// ==============================

export function createCursorMove({ state, registry }) {
  function getZoomRangeOf(chartInstance) {
    try {
      const c = chartInstance;
      if (!c || typeof c.getOption !== "function") return null;
      const opt = c.getOption();
      const dz = Array.isArray(opt?.dataZoom) ? opt.dataZoom : [];
      if (!dz.length) return null;
      const z = dz.find((x) => typeof x.startValue !== "undefined" && typeof x.endValue !== "undefined");
      const len = (state.vmRef.vm?.candles?.value || []).length;
      if (z && len > 0) {
        const sIdx = Math.max(0, Math.min(len - 1, Number(z.startValue)));
        const eIdx = Math.max(0, Math.min(len - 1, Number(z.endValue)));
        return { sIdx: Math.min(sIdx, eIdx), eIdx: Math.max(sIdx, eIdx) };
      }
    } catch {}
    return null;
  }

  function moveCursorByStep(dir) {
    const vm = state.vmRef.vm;
    if (!vm) return;

    const arr = vm.candles.value || [];
    const len = arr.length;
    if (!len) return;

    const activeChart = registry.getActiveChart();
    const zoomRange = getZoomRangeOf(activeChart);
    const sIdxNow = zoomRange?.sIdx ?? 0;
    const eIdxNow = zoomRange?.eIdx ?? len - 1;

    let startIdx = state.currentFocusIdx.value;
    if (startIdx < 0 || startIdx >= len) startIdx = eIdxNow;

    const nextIdx = Math.max(0, Math.min(len - 1, startIdx + (dir < 0 ? -1 : 1)));
    registry.syncFocusPosition(nextIdx);

    activeChart?.dispatchAction({
      type: "showTip",
      seriesIndex: 0,
      dataIndex: nextIdx,
    });

    const inView = nextIdx >= sIdxNow && nextIdx <= eIdxNow;
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

  return { moveCursorByStep };
}
