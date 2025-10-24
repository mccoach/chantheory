// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useChartPanel.js
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from "vue";
import * as echarts from "echarts";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useUserSettings } from "@/composables/useUserSettings";

/**
 * @description 一个封装了图表展板所有通用逻辑的 Vue Composable.
 * 职责包括：ECharts实例生命周期、面板高度拖拽、dataZoom事件处理、鼠标悬浮状态管理、标题生成。
 * @param {object} options
 * @param {import('vue').Ref<string>} options.panelKey - 面板的唯一标识符 (e.g., 'main').
 * @param {object} options.vm - useMarketView 的实例.
 * @param {object} options.hub - useViewCommandHub 的实例.
 * @param {object} options.renderHub - useViewRenderHub 的实例.
 * @param {Function} [options.onChartReady] - ECharts 实例初始化完成后的回调.
 * @returns {object} 包含模板所需的 refs 和事件处理器.
 */
export function useChartPanel({ panelKey, vm, hub, renderHub, onChartReady }) {
  // --- Refs for Template ---
  const wrapRef = ref(null);
  const hostRef = ref(null);

  // --- Internal State ---
  const chart = ref(null);
  const { findBySymbol } = useSymbolIndex();
  const settings = useUserSettings();
  let ro = null;

  // ============================
  // Section 1: ECharts Lifecycle
  // ============================
  function safeResize() {
    if (!chart.value || !hostRef.value) return;
    requestAnimationFrame(() => {
      try {
        chart.value.resize({
          width: hostRef.value.clientWidth,
          height: hostRef.value.clientHeight,
        });
      } catch {}
    });
  }

  onMounted(() => {
    if (!hostRef.value) return;
    const instance = echarts.init(hostRef.value, null, {
      renderer: "canvas",
      width: hostRef.value.clientWidth,
      height: hostRef.value.clientHeight,
    });
    instance.group = "ct-sync";
    try {
      echarts.connect("ct-sync");
    } catch {}
    chart.value = instance;

    // 绑定 dataZoom 事件
    instance.on("dataZoom", handleDataZoom);

    // 绑定 updateAxisPointer 事件
    instance.on("updateAxisPointer", (params) => {
      try {
        const list = vm.candles.value || [];
        const len = list.length;
        if (!len) return;
        let idx = -1;
        const sd = Array.isArray(params?.seriesData)
          ? params.seriesData.find((x) => Number.isFinite(x?.dataIndex))
          : null;
        if (sd && Number.isFinite(sd.dataIndex)) {
          idx = sd.dataIndex;
        } else {
          const xInfo = Array.isArray(params?.axesInfo)
            ? params.axesInfo.find((ai) => ai && ai.axisDim === "x")
            : null;
          const v = xInfo?.value;
          if (Number.isFinite(v)) idx = Math.max(0, Math.min(len - 1, Number(v)));
          else if (typeof v === "string" && v) idx = list.map((d) => d.t).indexOf(v);
        }
        if (idx < 0 || idx >= len) return;
        const tIso = list[idx]?.t;
        const tsVal = tIso ? Date.parse(tIso) : NaN;
        if (Number.isFinite(tsVal)) {
          settings.setLastFocusTs(vm.code.value, vm.freq.value, tsVal);
        }
      } catch {}
    });

    // 绑定鼠标交互以管理会话
    try {
      const zr = instance.getZr();
      zr.on("mousedown", zrMouseDownHandler);
      zr.on("mouseup", zrMouseUpHandler);
      window.addEventListener("mouseup", winMouseUpHandler);
    } catch {}

    // 监听尺寸变化
    try {
      ro = new ResizeObserver(safeResize);
      ro.observe(hostRef.value);
    } catch {}
    
    requestAnimationFrame(safeResize);

    // 执行组件传入的 ready 回调
    if (typeof onChartReady === "function") {
      onChartReady(instance);
    }
  });

  onBeforeUnmount(() => {
    if (ro) {
      ro.disconnect();
      ro = null;
    }
    if (chart.value) {
      try {
        const zr = chart.value.getZr ? chart.value.getZr() : null;
        zr?.off("mousedown", zrMouseDownHandler);
        zr?.off("mouseup", zrMouseUpHandler);
        chart.value.dispose();
      } catch {}
      chart.value = null;
    }
    window.removeEventListener("mouseup", winMouseUpHandler);
  });

  // ============================
  // Section 2: Panel Height Resizer
  // ============================
  let dragging = false, startY = 0, startH = 0;

  function onResizeHandleMove(e) {
    if (!dragging || !wrapRef.value) return;
    const next = Math.max(160, Math.min(800, startH + (e.clientY - startY)));
    wrapRef.value.style.height = `${Math.floor(next)}px`;
    safeResize();
  }

  function onResizeHandleUp() {
    dragging = false;
    window.removeEventListener("mousemove", onResizeHandleMove);
  }

  function onResizeHandleDown(e) {
    dragging = true;
    startY = e.clientY;
    startH = wrapRef.value?.clientHeight || 0;
    window.addEventListener("mousemove", onResizeHandleMove);
    window.addEventListener("mouseup", onResizeHandleUp, { once: true });
  }

  // ============================
  // Section 3: DataZoom Handling
  // ============================
  let dzIdleTimer = null;
  const dzIdleDelayMs = 180;
  let isMouseDown = false;

  const zrMouseDownHandler = () => { isMouseDown = true; };
  const zrMouseUpHandler = () => {
    isMouseDown = false;
    try { renderHub.endInteraction(panelKey.value); } catch {}
  };
  const winMouseUpHandler = () => {
    if (isMouseDown) {
        isMouseDown = false;
        try { renderHub.endInteraction(panelKey.value); } catch {}
    }
  };

  function handleDataZoom(params) {
    try {
      renderHub.beginInteraction(panelKey.value);
      const info = (params && params.batch && params.batch[0]) || params || {};
      const arr = vm.candles.value || [];
      if (!arr.length) return;

      let sIdx, eIdx;
      if (typeof info.startValue !== "undefined" && typeof info.endValue !== "undefined") {
        sIdx = Number(info.startValue);
        eIdx = Number(info.endValue);
      } else if (typeof info.start === "number" && typeof info.end === "number") {
        const maxIdx = arr.length - 1;
        sIdx = Math.round((info.start / 100) * maxIdx);
        eIdx = Math.round((info.end / 100) * maxIdx);
      } else return;

      if (!Number.isFinite(sIdx) || !Number.isFinite(eIdx)) return;
      if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];
      sIdx = Math.max(0, sIdx);
      eIdx = Math.min(arr.length - 1, eIdx);

      // 广播预览事件
      try {
        window.dispatchEvent(
          new CustomEvent("chan:preview-range", {
            detail: { code: vm.code.value, freq: vm.freq.value, sIdx, eIdx },
          })
        );
      } catch {}

      if (dzIdleTimer) clearTimeout(dzIdleTimer);
      dzIdleTimer = setTimeout(() => {
        try {
          const bars_new = Math.max(1, eIdx - sIdx + 1);
          const tsArr = arr.map((d) => Date.parse(d.t));
          const anchorTs = Number.isFinite(tsArr[eIdx]) ? tsArr[eIdx] : hub.getState().rightTs;
          const st = hub.getState();
          const changedBars = bars_new !== Math.max(1, Number(st.barsCount || 1));
          const changedEIdx = Number.isFinite(tsArr[eIdx]) && tsArr[eIdx] !== st.rightTs;

          if (changedBars || changedEIdx) {
            if (changedBars && changedEIdx) hub.execute("ScrollZoom", { nextBars: bars_new, nextRightTs: anchorTs });
            else if (changedBars) hub.execute("SetBarsManual", { nextBars: bars_new });
            else if (changedEIdx) hub.execute("Pan", { nextRightTs: anchorTs });
          }
        } finally {
          if (!isMouseDown) {
            renderHub.endInteraction(panelKey.value);
          }
        }
      }, dzIdleDelayMs);
    } catch {}
  }

  // ============================
  // Section 4: Hover & Header
  // ============================
  const onMouseEnter = () => renderHub.setHoveredPanel(panelKey.value);
  const onMouseLeave = () => renderHub.setHoveredPanel(null);

  const displayHeader = ref({ name: "", code: "", freq: "" });
  const displayTitle = computed(() => {
    const n = displayHeader.value.name || "",
      c = displayHeader.value.code || vm.code.value || "",
      f = displayHeader.value.freq || vm.freq.value || "";
    const src = (vm.meta.value?.source || "").trim(),
      srcLabel = src ? `（${src}）` : "";
    const adjText = { none: "", qfq: " 前复权", hfq: " 后复权" }[String(vm.adjust.value || "none")] || "";
    return n ? `${n}（${c}）：${f}${srcLabel}${adjText}` : `${c}：${f}${srcLabel}${adjText}`;
  });

  function updateHeaderFromCurrent() {
    const sym = (vm.meta.value?.symbol || vm.code.value || "").trim();
    const frq = String(vm.meta.value?.freq || vm.freq.value || "").trim();
    let name = "";
    try {
      name = findBySymbol(sym)?.name?.trim() || "";
    } catch {}
    displayHeader.value = { name, code: sym, freq: frq };
  }

  watch(() => vm.meta.value,
    () => {
      nextTick().then(updateHeaderFromCurrent);
    },
    { deep: true, immediate: true }
  );

  // --- Returned API for component ---
  return {
    wrapRef,
    hostRef,
    chart,
    displayTitle,
    onResizeHandleDown,
    onMouseEnter,
    onMouseLeave,
  };
}