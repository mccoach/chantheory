// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useChartPanel.js
// ==============================
// V4.0 - 彻底简化（ECharts 原生优先）
// 
// 核心思想：
//   - ECharts 负责所有交互（拖动/缩放）
//   - 我们仅负责：监听事件 → 同步状态 → 持久化
//   - 不触发任何渲染（渲染由数据变化触发）
// 
// 删除的冗余：
//   - 所有 hub.execute("Pan/ScrollZoom/SetBarsManual")
//   - 所有 RAF/setTimeout/防抖逻辑
//   - 所有 isMouseDown/beginInteraction/endInteraction
// ==============================

import {
  ref,
  computed,
  onMounted,
  onBeforeUnmount,
  watch,
  nextTick,
} from "vue";
import * as echarts from "echarts";
import { useSymbolIndex } from "@/composables/useSymbolIndex";

export function useChartPanel({ panelKey, vm, hub, renderHub, onChartReady }) {
  const wrapRef = ref(null);
  const hostRef = ref(null);
  const chart = ref(null);
  
  const { findBySymbol } = useSymbolIndex();
  let ro = null;

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

    // ===== 监听 dataZoom（仅同步状态）=====
    instance.on("dataZoom", handleDataZoom);

    // ===== 监听十字线位置 =====
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
          
          if (Number.isFinite(v)) {
            idx = Math.max(0, Math.min(len - 1, Number(v)));
          } else if (typeof v === "string" && v) {
            const targetDate = new Date(v).getTime();
            idx = list.findIndex((d) => d.ts === targetDate);
          }
        }
        
        if (idx >= 0 && idx < len) {
          renderHub?.syncFocusPosition?.(idx);
        }
      } catch {}
    });

    try {
      ro = new ResizeObserver(safeResize);
      ro.observe(hostRef.value);
    } catch {}

    requestAnimationFrame(safeResize);

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
        chart.value.dispose();
      } catch {}
      chart.value = null;
    }
  });

  // ===== 面板高度调整 =====
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

  // ===== 核心功能：dataZoom 事件处理（仅同步状态）=====
  function handleDataZoom(params) {
    try {
      const info = (params?.batch?.[0]) || params || {};
      const arr = vm.candles.value || [];
      if (!arr.length) return;

      let sIdx, eIdx;
      
      if (
        typeof info.startValue !== "undefined" &&
        typeof info.endValue !== "undefined"
      ) {
        sIdx = Number(info.startValue);
        eIdx = Number(info.endValue);
      } else if (
        typeof info.start === "number" &&
        typeof info.end === "number"
      ) {
        const maxIdx = arr.length - 1;
        sIdx = Math.round((info.start / 100) * maxIdx);
        eIdx = Math.round((info.end / 100) * maxIdx);
      } else {
        return;
      }

      if (!Number.isFinite(sIdx) || !Number.isFinite(eIdx)) return;
      if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];
      
      sIdx = Math.max(0, sIdx);
      eIdx = Math.min(arr.length - 1, eIdx);

      const bars_new = Math.max(1, eIdx - sIdx + 1);
      const anchorTs = arr[eIdx]?.ts;

      if (!Number.isFinite(anchorTs)) return;

    // ===== 修复：删除 silent 参数（允许广播）=====
    hub.execute("SyncViewState", {
      barsCount: bars_new,
      rightTs: anchorTs,
    });
    
  } catch {}
}

  const onMouseEnter = () => renderHub.setHoveredPanel(panelKey.value);
  const onMouseLeave = () => renderHub.setHoveredPanel(null);

  // ===== 标题显示 =====
  const displayHeader = ref({ name: "", code: "", freq: "" });
  const displayTitle = computed(() => {
    const n = displayHeader.value.name || "",
      c = displayHeader.value.code || vm.code.value || "",
      f = displayHeader.value.freq || vm.freq.value || "";
    const src = (vm.meta.value?.source || "").trim(),
      srcLabel = src ? `（${src}）` : "";
    const adjText =
      { none: "", qfq: " 前复权", hfq: " 后复权" }[
        String(vm.adjust.value || "none")
      ] || "";
    return n
      ? `${n}（${c}）：${f}${srcLabel}${adjText}`
      : `${c}：${f}${srcLabel}${adjText}`;
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

  watch(
    () => vm.meta.value,
    () => {
      nextTick().then(updateHeaderFromCurrent);
    },
    { deep: true, immediate: true }
  );

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