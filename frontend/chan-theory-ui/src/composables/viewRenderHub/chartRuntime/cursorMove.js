// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\viewRenderHub\chartRuntime\cursorMove.js
// ==============================
// 键盘游标移动（ArrowLeft/ArrowRight）
// ==============================

import { useViewCommandHub } from "@/composables/useViewCommandHub";

export function createCursorMove({ state, registry }) {
  const hub = useViewCommandHub();

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

  function resolveIdxByTipTs(ts) {
    const vm = state.vmRef.vm;
    if (!vm) return -1;

    const arr = vm.candles.value || [];
    const len = arr.length;
    if (!len) return -1;

    const t = Number(ts);
    if (!Number.isFinite(t)) return -1;

    for (let i = len - 1; i >= 0; i--) {
      const barTs = Number(arr[i]?.ts);
      if (Number.isFinite(barTs) && barTs <= t) return i;
    }
    return 0;
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

    const st = hub.getState();

    // 基点：最后一次显示 tooltip 的 bar.ts
    let startIdx = resolveIdxByTipTs(st.tipTs);

    // 若历史没有 tipTs：以当前视窗右端为起点，先 showTip 一次，让 showTip 监听自动持久化 tipTs
    if (startIdx < 0 || startIdx >= len) {
      startIdx = Math.max(0, Math.min(len - 1, eIdxNow));
      registry.syncFocusPosition(startIdx);
      activeChart?.dispatchAction({
        type: "showTip",
        seriesIndex: 0,
        dataIndex: startIdx,
      });
      return;
    }

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
