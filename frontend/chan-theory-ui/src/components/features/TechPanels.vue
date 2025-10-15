<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\TechPanels.vue -->
<!-- ============================== -->
<!-- 合并后：统一副窗容器（仅用 IndicatorPanel，一个组件覆盖成交量/成交额/各类指标）
     - 默认提供两个窗：成交量、MACD（兼容“原项目默认量窗+一个 MACD”）
     - 持久化 panes 到 useUserSettings.indicatorPanes；若历史数据未含 VOL/AMOUNT，自动在最前补 VOL
     - 新增：右侧悬浮拖动把手 → 父容器支持拖拽排序（HTML5 DnD）
-->
<template>
  <div class="tech-wrap" @dragover.prevent @drop.prevent="onDropToEnd">
    <IndicatorPanel
      v-for="(pane, i) in panes"
      :key="pane.id"
      :id="pane.id"
      v-model:kind="pane.kind"
      @close="removePane(i)"
      @dragstart="onDragStart(pane.id)"
      @dragend="onDragEnd"
      class="pane-wrapper"
      @dragover.prevent="onDragOver(i)"
      @drop.prevent="onDrop(i)"
      :class="{'drag-over': dragOverIndex === i}"
    />
    <div class="add-wrap">
      <button
        class="btn-add"
        @click="addPane"
        title="新增指标窗"
        aria-label="新增指标窗"
      >
        <svg viewBox="0 0 48 48" width="36" height="36" aria-hidden="true">
          <defs>
            <radialGradient id="gcircle" cx="30%" cy="30%" r="70%">
              <stop offset="0" stop-color="#2e2e2e" />
              <stop offset="1" stop-color="#151515" />
            </radialGradient>
          </defs>
          <circle
            cx="24"
            cy="24"
            r="22"
            fill="url(#gcircle)"
            stroke="#8a8a8a"
            stroke-width="1"
          />
          <circle
            cx="24"
            cy="24"
            r="21"
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            stroke-width="1"
          />
          <path
            d="M24 14 L24 34 M14 24 L34 24"
            stroke="#e8e8e8"
            stroke-width="2.2"
            stroke-linecap="round"
          />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch, onMounted, ref } from "vue";
import IndicatorPanel from "./tech/IndicatorPanel.vue";
import { useUserSettings } from "@/composables/useUserSettings";

// 初始：提供一个“成交量 + MACD”的双窗默认
const state = reactive({
  panes: [
    { id: Date.now() + Math.random(), kind: "VOL" },
    { id: Date.now() + Math.random() + 1, kind: "MACD" },
  ],
});
const panes = state.panes;

// 用户设置持久化
const settings = useUserSettings();

// 拖拽排序状态
const draggingId = ref(null);
const dragOverIndex = ref(-1);

onMounted(() => {
  try {
    const saved = settings.getIndicatorPanes();
    if (Array.isArray(saved) && saved.length > 0) {
      const mapped = saved.map((x, idx) => ({
        id: Date.now() + idx + Math.random(),
        kind: String(x.kind || "MACD").toUpperCase(),
      }));
      // 若历史记录中不含 VOL/AMOUNT（旧版本仅存指标），最前补上一个 VOL
      if (!mapped.some((x) => x.kind === "VOL" || x.kind === "AMOUNT")) {
        mapped.unshift({ id: Date.now() + Math.random(), kind: "VOL" });
      }
      panes.splice(0, panes.length, ...mapped);
    }
  } catch {}
});

// 持久化 panes 映射（仅 kind 顺序）
watch(
  () => panes.map((p) => p.kind),
  (arr) => {
    try {
      settings.setIndicatorPanes(arr.map((k) => ({ kind: String(k || "MACD") })));
    } catch {}
  },
  { deep: true }
);

function addPane() {
  panes.push({ id: Date.now() + Math.random(), kind: "MACD" });
}
function removePane(idx) {
  if (idx < 0 || idx >= panes.length) return;
  panes.splice(idx, 1);
}

// 拖拽排序实现
function onDragStart(id) {
  draggingId.value = id;
}
function onDragEnd() {
  draggingId.value = null;
  dragOverIndex.value = -1;
}
function onDragOver(i) {
  if (draggingId.value == null) return;
  dragOverIndex.value = i;
}
function onDrop(i) {
  try {
    if (draggingId.value == null) return;
    const fromIdx = panes.findIndex((p) => p.id === draggingId.value);
    if (fromIdx < 0) return;
    if (i === fromIdx || i === fromIdx + 1) {
      // 放回原位或紧邻原位等效，忽略
      onDragEnd();
      return;
    }
    const moving = panes.splice(fromIdx, 1)[0];
    // 计算插入下标：如果原位置在目标之前，目标索引要先减 1
    const insertAt = fromIdx < i ? i - 1 : i;
    panes.splice(insertAt, 0, moving);
  } finally {
    onDragEnd();
  }
}
// 放到末尾（容器空白区域）
function onDropToEnd() {
  if (draggingId.value == null) return;
  const fromIdx = panes.findIndex((p) => p.id === draggingId.value);
  if (fromIdx < 0) return;
  const moving = panes.splice(fromIdx, 1)[0];
  panes.push(moving);
  onDragEnd();
}
</script>

<style scoped>
.tech-wrap {
  display: flex;
  flex-direction: column;
  gap: 0px;
  margin: 0;
  padding: 0;
}
.add-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 8px 0 0 0;
}
.btn-add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  width: 36px;
  height: 36px;
}
.btn-add svg circle:first-child {
  transition: stroke 120ms ease, fill 120ms ease;
}
.btn-add svg path {
  transition: stroke 120ms ease;
}
.btn-add:hover svg circle:first-child {
  stroke: #bdbdbd;
}
.btn-add:hover svg path {
  stroke: #ffffff;
}
.btn-add:active svg circle:first-child {
  stroke: #d0d0d0;
}
.btn-add:active svg path {
  stroke: #ffffff;
}

/* 拖拽目标高亮（可按需增强） */
.pane-wrapper.drag-over {
  outline: 1px dashed #5b7fb3;
  outline-offset: 2px;
  border-radius: 8px;
}
</style>
