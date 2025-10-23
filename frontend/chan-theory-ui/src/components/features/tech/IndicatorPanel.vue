<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\tech\IndicatorPanel.vue -->
<!-- ============================== -->
<!-- 合并版 IndicatorPanel：既可渲染 成交量/成交额，也可渲染 MACD/KDJ/RSI/BOLL/OFF
     - FIX: 移除本地 setOption 调用，完全依赖渲染中枢的快照进行渲染。
     - FIX: onRender 回调中，从快照中查找为本面板ID预先生成的 option。
     - FIX: onKindChange 只 emit 更新，不再执行任何副作用。
-->
<template>
  <div
    ref="wrap"
    class="chart"
    @dblclick="openSettingsDialog"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
  >
    <div class="top-info">
      <select
        class="sel-kind"
        v-model="kindLocal"
        @change="onKindChange"
        title="选择副窗内容"
      >
        <option value="VOL">成交量</option>
        <option value="AMOUNT">成交额</option>
        <option value="MACD">MACD</option>
        <option value="KDJ">KDJ</option>
        <option value="RSI">RSI</option>
        <option value="BOLL">BOLL</option>
        <option value="OFF">OFF</option>
      </select>
      <div class="title">{{ displayTitle }}</div>
      <button
        class="btn-close"
        @click="$emit('close')"
        title="关闭此窗"
        aria-label="关闭"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
          <defs>
            <linearGradient id="gcx" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#3a3a3a" />
              <stop offset="1" stop-color="#242424" />
            </linearGradient>
          </defs>
          <rect
            x="2.5"
            y="2.5"
            rx="6"
            ry="6"
            width="19"
            height="19"
            fill="url(#gcx)"
            stroke="#8b8b8b"
            stroke-width="1"
          />
          <path
            d="M8 8 L16 16"
            stroke="#e6e6e6"
            stroke-width="1.8"
            stroke-linecap="round"
          />
          <path
            d="M16 8 L8 16"
            stroke="#e6e6e6"
            stroke-width="1.8"
            stroke-linecap="round"
          />
        </svg>
      </button>
    </div>

    <div ref="host" class="canvas-host"></div>

    <!-- 右侧悬浮拖动把手（仅悬停显示） -->
    <div
      class="drag-handle"
      draggable="true"
      title="拖动以调整顺序"
      @dragstart="onDragHandleStart"
      @dragend="onDragHandleEnd"
    >
      <div class="grip"></div>
    </div>

    <!-- 底部高度拖拽条 -->
    <div
      class="bottom-strip"
      title="上下拖拽调整窗体高度"
      @mousedown="onResizeHandleDown('bottom', $event)"
    ></div>
  </div>
</template>

<script setup>
import {
  inject,
  onMounted,
  onBeforeUnmount,
  ref,
  watch,
  nextTick,
  computed,
} from "vue";
import * as echarts from "echarts";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { openIndicatorSettings } from "@/settings/indicatorShell";

// props / emits
const props = defineProps({
  id: { type: [String, Number], required: true },
  kind: { type: String, default: "MACD" },
});
const emit = defineEmits(["update:kind", "close", "dragstart", "dragend"]);

// 注入
const vm = inject("marketView");
const hub = useViewCommandHub();
const renderHub = useViewRenderHub();
const settings = useUserSettings();
const { findBySymbol } = useSymbolIndex();
const dialogManager = inject("dialogManager");

// 渲染序号守护
let renderSeq = 0;
function isStale(seq) {
  return seq !== renderSeq;
}

// DOM / 实例
const wrap = ref(null);
const host = ref(null);
let chart = null;
let ro = null;

// 悬浮状态上报
function onMouseEnter() {
  renderHub.setHoveredPanel(`indicator:${props.id}`);
}
function onMouseLeave() {
  renderHub.setHoveredPanel(null);
}

// 尺寸安全 resize
function safeResize() {
  if (!chart || !host.value) return;
  const seq = renderSeq;
  requestAnimationFrame(() => {
    if (isStale(seq)) return;
    try {
      chart.resize({
        width: host.value.clientWidth,
        height: host.value.clientHeight,
      });
    } catch {}
  });
}

// 选择种类
const kindLocal = ref(props.kind.toUpperCase());
watch(
  () => props.kind,
  (v) => {
    kindLocal.value = String(v || "MACD").toUpperCase();
  }
);
function onKindChange() {
  // FIX: 只 emit 更新，不执行任何本地 setOption
  emit("update:kind", kindLocal.value);
}

// 顶栏标题
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

// 设置窗
function openSettingsDialog() {
  openIndicatorSettings(dialogManager, { initialKind: kindLocal.value });
}

// dataZoom：会后承接
let dzIdleTimer = null;
const dzIdleDelayMs = 180;

let isMouseDown = false;
let zrMouseDownHandler = () => {
  isMouseDown = true;
};
let zrMouseUpHandler = () => {
  isMouseDown = false;
  try {
    renderHub.endInteraction(`indicator:${props.id}`);
  } catch {}
};
let winMouseUpHandler = () => {
  isMouseDown = false;
  try {
    renderHub.endInteraction(`indicator:${props.id}`);
  } catch {}
};

function onDataZoom(params) {
  try {
    const isActive = renderHub.getActiveChart?.() === chart;
    if (!isActive && !isMouseDown) return;

    const info = (params && params.batch && params.batch[0]) || params || {};
    const arr = vm.candles.value || [];
    const len = arr.length;
    if (!len) return;
    let sIdx, eIdx;
    if (
      typeof info.startValue !== "undefined" &&
      typeof info.endValue !== "undefined"
    ) {
      sIdx = Number(info.startValue);
      eIdx = Number(info.endValue);
    } else if (typeof info.start === "number" && typeof info.end === "number") {
      const maxIdx = len - 1;
      sIdx = Math.round((info.start / 100) * maxIdx);
      eIdx = Math.round((info.end / 100) * maxIdx);
    } else return;
    if (!Number.isFinite(sIdx) || !Number.isFinite(eIdx)) return;
    if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];
    sIdx = Math.max(0, sIdx);
    eIdx = Math.min(len - 1, eIdx);

    try {
      window.dispatchEvent(
        new CustomEvent("chan:preview-range", {
          detail: {
            code: vm.code.value,
            freq: vm.freq.value,
            sIdx,
            eIdx,
          },
        })
      );
    } catch {}

    renderHub.beginInteraction(`indicator:${props.id}`);
    if (dzIdleTimer) {
      clearTimeout(dzIdleTimer);
      dzIdleTimer = null;
    }
    dzIdleTimer = setTimeout(() => {
      try {
        const bars_new = Math.max(1, eIdx - sIdx + 1);
        const tsArr = arr.map((d) => Date.parse(d.t));
        const anchorTs = Number.isFinite(tsArr[eIdx])
          ? tsArr[eIdx]
          : hub.getState().rightTs;
        const st = hub.getState();
        const changedBars = bars_new !== Math.max(1, Number(st.barsCount || 1));
        const changedEIdx =
          Number.isFinite(tsArr[eIdx]) && tsArr[eIdx] !== st.rightTs;

        if (changedBars || changedEIdx) {
          if (changedBars && changedEIdx) {
            hub.execute("ScrollZoom", {
              nextBars: bars_new,
              nextRightTs: anchorTs,
            });
          } else if (changedBars) {
            hub.execute("SetBarsManual", { nextBars: bars_new });
          } else if (changedEIdx) {
            hub.execute("Pan", { nextRightTs: anchorTs });
          }
        }
      } finally {
        if (!isMouseDown) {
          renderHub.endInteraction(`indicator:${props.id}`);
        }
      }
    }, dzIdleDelayMs);
  } catch {}
}

onMounted(async () => {
  const el = host.value;
  if (!el) return;
  chart = echarts.init(el, null, {
    renderer: "canvas",
    width: el.clientWidth,
    height: el.clientHeight,
  });
  chart.group = "ct-sync";
  try {
    echarts.connect("ct-sync");
  } catch {}

  const thisPanelKey = `indicator:${props.id}`;
  try {
    renderHub.registerChart(thisPanelKey, chart);
    el.addEventListener("mouseenter", () => {
      renderHub.setActivePanel(thisPanelKey);
    });
  } catch {}

  try {
    const zr = chart.getZr();
    zr.on("mousedown", zrMouseDownHandler);
    zr.on("mouseup", zrMouseUpHandler);
    window.addEventListener("mouseup", winMouseUpHandler);
  } catch {}

  chart.on("updateAxisPointer", (params) => {
    try {
      const list = vm.candles.value || [];
      const len = list.length;
      if (!len) return;

      let idx = -1;

      // 1) 优先使用 seriesData 的 dataIndex（最可靠）
      const sd = Array.isArray(params?.seriesData)
        ? params.seriesData.find((x) => Number.isFinite(x?.dataIndex))
        : null;
      if (sd && Number.isFinite(sd.dataIndex)) {
        idx = sd.dataIndex;
      } else {
        // 2) 回退：明确寻找 x 轴信息（axisDim === 'x'），严禁使用 axesInfo[0]
        const xInfo = Array.isArray(params?.axesInfo)
          ? params.axesInfo.find((ai) => ai && ai.axisDim === "x")
          : null;
        const v = xInfo?.value;

        if (Number.isFinite(v)) {
          // 某些情况下 value 就是索引
          idx = Math.max(0, Math.min(len - 1, Number(v)));
        } else if (typeof v === "string" && v) {
          // 类目轴返回日期字符串，按时间查索引
          const dates = list.map((d) => d.t);
          idx = dates.indexOf(v);
        } else {
          // 3) 再兜底：尝试 batch 内的 dataIndex（部分版本/场景下可用）
          const b0 = Array.isArray(params?.batch)
            ? params.batch.find((b) => Number.isFinite(b?.dataIndex))
            : null;
          if (b0 && Number.isFinite(b0.dataIndex)) {
            idx = Math.max(0, Math.min(len - 1, Number(b0.dataIndex)));
          }
        }
      }

      if (idx < 0 || idx >= len) return;
      const tIso = list[idx]?.t;
      const tsVal = tIso ? Date.parse(tIso) : NaN;
      if (Number.isFinite(tsVal)) {
        settings.setLastFocusTs(vm.code.value, vm.freq.value, tsVal);
      }
    } catch {}
  });

  chart.on("dataZoom", onDataZoom);

  try {
    ro = new ResizeObserver(() => {
      safeResize();
    });
    ro.observe(el);
  } catch {}
  requestAnimationFrame(() => {
    safeResize();
  });

  updateHeaderFromCurrent();
});

// 订阅上游渲染
const unsubId = renderHub.onRender((snapshot) => {
  try {
    if (!chart) return;
    const mySeq = ++renderSeq;

    const kind = String(kindLocal.value || "").toUpperCase();
    if (kind === "OFF") {
      chart.clear();
      return;
    }

    const notMerge = !renderHub.isInteracting();

    // FIX: 从快照中查找为本面板预先生成的 option
    const option = snapshot.indicatorOptions?.[props.id];
    if (!option) return;

    chart.setOption(option, { notMerge, silent: true });
  } catch (e) {
    console.error(`IndicatorPanel[${props.id}] onRender error:`, e);
  }
});

onBeforeUnmount(() => {
  renderHub.offRender(unsubId);
  const thisPanelKey = `indicator:${props.id}`;

  if (ro) {
    try {
      ro.disconnect();
    } catch {}
    ro = null;
  }

  if (chart) {
    try {
      const zr = chart.getZr ? chart.getZr() : null;
      zr && zr.off && zr.off("mousedown", zrMouseDownHandler);
      zr && zr.off && zr.off("mouseup", zrMouseUpHandler);
      chart.dispose();
    } catch {}
    chart = null;
  }
  try {
    renderHub.unregisterChart(thisPanelKey);
  } catch {}

  window.removeEventListener("mouseup", winMouseUpHandler);
});

// 监听元信息变化以刷新左上标题
watch(
  () => vm.meta.value,
  async () => {
    await nextTick();
    updateHeaderFromCurrent();
  },
  { deep: true }
);

// 右侧拖动把手
function onDragHandleStart(e) {
  try {
    e.dataTransfer && e.dataTransfer.setData("text/plain", String(props.id));
  } catch {}
  emit("dragstart");
}
function onDragHandleEnd() {
  emit("dragend");
}

// 底部高度拖拽
let dragging = false,
  startY = 0,
  startH = 0;
function onResizeHandleDown(_pos, e) {
  dragging = true;
  startY = e.clientY;
  startH = wrap.value?.clientHeight || 0;
  window.addEventListener("mousemove", onResizeHandleMove);
  window.addEventListener("mouseup", onResizeHandleUp, { once: true });
}
function onResizeHandleMove(e) {
  if (!dragging) return;
  const next = Math.max(160, Math.min(800, startH + (e.clientY - startY)));
  if (wrap.value) {
    wrap.value.style.height = `${Math.floor(next)}px`;
    safeResize();
  }
}
function onResizeHandleUp() {
  dragging = false;
  window.removeEventListener("mousemove", onResizeHandleMove);
}
</script>

<style scoped>
.chart {
  position: relative;
  width: 100%;
  height: 220px;
  background: #111;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  overflow: hidden;
  margin: 0;
}
.top-info {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 28px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  z-index: 5;
  background: linear-gradient(
    to bottom,
    rgba(17, 17, 17, 0.85),
    rgba(17, 17, 17, 0.35),
    rgba(17, 17, 17, 0)
  );
}
.sel-kind {
  height: 22px;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #8a8a8a;
  border-radius: 6px;
  padding: 0 6px;
}
.title {
  font-size: 13px;
  font-weight: 600;
  color: #ddd;
  user-select: none;
  margin-left: 8px;
}
.btn-close {
  margin-left: auto;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
}

/* 画布区域 */
.canvas-host {
  position: absolute;
  left: 0;
  right: 0;
  top: 28px;
  bottom: 8px;
}

/* 底部高度拖拽条 */
.bottom-strip {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 8px;
  background: transparent;
}
.bottom-strip:hover {
  cursor: ns-resize;
}

/* 右侧悬浮拖动把手（仅在悬停 chart 时显示） */
.drag-handle {
  position: absolute;
  top: 28px;
  bottom: 8px;
  right: 0;
  width: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(
    to left,
    rgba(255, 255, 255, 0.08),
    rgba(255, 255, 255, 0)
  );
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  opacity: 0;
  transition: opacity 120ms ease;
}

.chart:hover .drag-handle {
  opacity: 1;
}

.drag-handle:hover {
  cursor: grab;
  background: linear-gradient(
    to left,
    rgba(255, 255, 255, 0.14),
    rgba(255, 255, 255, 0)
  );
  border-left-color: rgba(255, 255, 255, 0.12);
}

.drag-handle:active {
  cursor: grabbing;
}

.drag-handle .grip {
  width: 4px;
  height: 40%;
  border-radius: 2px;
  background-image: radial-gradient(#bfbfbf 1px, transparent 1px);
  background-size: 4px 6px;
  background-position: center;
  opacity: 0.7;
}

/* 指标设置占位提示 */
.settings-hint {
  color: #bbb;
  font-size: 13px;
  padding: 4px 2px;
}
</style>
