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
  onBeforeUnmount,
  ref,
  watch,
  computed,
} from "vue";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import { openIndicatorSettings } from "@/settings/indicatorShell";
import { useChartPanel } from "@/composables/useChartPanel"; // NEW: Import the common panel hook

// --- props / emits (No changes) ---
const props = defineProps({
  id: { type: [String, Number], required: true },
  kind: { type: String, default: "MACD" },
});
const emit = defineEmits(["update:kind", "close", "dragstart", "dragend"]);

// --- Injected Services ---
const vm = inject("marketView");
const hub = inject("viewCommandHub");
const renderHub = inject("renderHub");
const dialogManager = inject("dialogManager");

// --- NEW: Use the common chart panel logic ---
const panelKey = computed(() => `indicator:${props.id}`);
const {
  wrapRef: wrap,
  hostRef: host,
  displayTitle,
  onResizeHandleDown,
  onMouseEnter,
  onMouseLeave,
} = useChartPanel({
  panelKey,
  vm,
  hub,
  renderHub,
  onChartReady: (instance) => {
    // 指标图特有的初始化逻辑
    try {
      renderHub.registerChart(panelKey.value, instance);
      host.value?.addEventListener("mouseenter", () => {
        renderHub.setActivePanel(panelKey.value);
      });
      
      // FIX: Unified render subscription logic
      const unsubId = renderHub.onRender((snapshot) => {
        try {
          if (!instance) return;
          const kind = String(kindLocal.value || "").toUpperCase();
          if (kind === "OFF") {
            instance.clear();
            return;
          }
          const option = snapshot.indicatorOptions?.[props.id];
          if (option) {
            // Ensure clean state on each render
            instance.setOption(option, { notMerge: true, silent: true });
          }
        } catch (e) {
          console.error(`IndicatorPanel[${props.id}] onRender error:`, e);
        }
      });
      onBeforeUnmount(() => renderHub.offRender(unsubId));
    } catch {}
  }
});

// --- Component-Specific Logic ---

// Indicator Kind Selector
const kindLocal = ref(props.kind.toUpperCase());
watch(
  () => props.kind,
  (v) => {
    kindLocal.value = String(v || "MACD").toUpperCase();
  }
);
function onKindChange() {
  emit("update:kind", kindLocal.value);
}

// Settings Dialog
function openSettingsDialog() {
  openIndicatorSettings(dialogManager, { initialKind: kindLocal.value });
}

// Drag & Drop Sorting
function onDragHandleStart(e) {
  try {
    e.dataTransfer?.setData("text/plain", String(props.id));
  } catch {}
  emit("dragstart");
}
function onDragHandleEnd() {
  emit("dragend");
}

onBeforeUnmount(() => {
  renderHub.unregisterChart(panelKey.value);
});
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