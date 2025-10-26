<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\TechPanels.vue -->
<!-- ============================== -->
<!-- 合并后：统一副窗容器（仅用 IndicatorPanel，一个组件覆盖成交量/成交额/各类指标）
     - 默认提供两个窗：成交量、MACD（兼容“原项目默认量窗+一个 MACD”）
     - 持久化 panes 到 useUserSettings.indicatorPanes；若历史数据未含 VOL/AMOUNT，自动在最前补 VOL
     - 新增：右侧悬浮拖动把手 → 父容器支持拖拽排序（HTML5 DnD）
     - FIX: 将 panes 状态上报给 useViewRenderHub，作为生成 indicator options 的唯一来源。
     - REFACTORED: 修复并简化了 pane 状态的加载与初始化逻辑，确保布局持久化能正确工作。
     - NEW: "新增"按钮现在会弹出一个菜单供用户选择指标类型，而不是直接添加 MACD。
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
    <!-- NEW: "新增"按钮容器，添加了 ref 并改为相对定位 -->
    <div class="add-wrap" ref="addWrapRef">
      <!-- NEW: 新增指标的弹出菜单 -->
      <ul v-if="isAddMenuOpen" class="add-menu">
        <li
          v-for="opt in indicatorOptions"
          :key="opt.key"
          @click="addPane(opt.key)"
        >
          {{ opt.label }}
        </li>
      </ul>
      <button
        class="btn-add"
        @click="toggleAddMenu"
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
import { reactive, watch, onMounted, onBeforeUnmount, ref } from "vue";
import IndicatorPanel from "./tech/IndicatorPanel.vue";
import { useUserSettings } from "@/composables/useUserSettings";
import { useViewRenderHub } from "@/composables/useViewRenderHub";

const panes = reactive([]);

const settings = useUserSettings();
const renderHub = useViewRenderHub();

const draggingId = ref(null);
const dragOverIndex = ref(-1);

// NEW: 新增状态，用于控制添加菜单的显示
const isAddMenuOpen = ref(false);
const addWrapRef = ref(null);

// NEW: 定义可添加的指标选项
const indicatorOptions = [
  { key: "VOL", label: "成交量" },
  { key: "AMOUNT", label: "成交额" },
  { key: "MACD", label: "MACD" },
  { key: "KDJ", label: "KDJ" },
  { key: "RSI", label: "RSI" },
  { key: "BOLL", label: "BOLL" },
];

onMounted(() => {
  let panesToLoad = [];
  const savedPanes = settings.preferences.indicatorPanes;

  if (Array.isArray(savedPanes) && savedPanes.length > 0) {
    panesToLoad = savedPanes.map((p, idx) => ({
      id: Date.now() + idx + Math.random(),
      kind: String(p.kind || "MACD").toUpperCase(),
    }));
  } else {
    panesToLoad = [
      { id: Date.now() + Math.random(), kind: "VOL" },
      { id: Date.now() + Math.random() + 1, kind: "MACD" },
    ];
  }
  
  panes.splice(0, panes.length, ...panesToLoad);
  
  renderHub.setIndicatorPanes(panes);

  // NEW: 添加全局点击监听，用于关闭菜单
  document.addEventListener("click", handleClickOutside);
});

onBeforeUnmount(() => {
  // NEW: 组件卸载时移除监听
  document.removeEventListener("click", handleClickOutside);
});

watch(
  () => panes,
  (newPanes) => {
    try {
      const kindsToSave = newPanes.map((p) => ({ kind: String(p.kind || "MACD") }));
      settings.setIndicatorPanes(kindsToSave);
      renderHub.setIndicatorPanes(newPanes);
    } catch {}
  },
  { deep: true }
);

// NEW: 修改 addPane 函数，使其接受一个指标类型作为参数
function addPane(kind) {
  panes.push({ id: Date.now() + Math.random(), kind: String(kind || "MACD").toUpperCase() });
  isAddMenuOpen.value = false; // 添加后关闭菜单
}
function removePane(idx) {
  if (idx < 0 || idx >= panes.length) return;
  panes.splice(idx, 1);
}

// NEW: 切换添加菜单的显示状态
function toggleAddMenu() {
  isAddMenuOpen.value = !isAddMenuOpen.value;
}

// NEW: 处理外部点击事件，如果点击位置不在菜单或按钮内，则关闭菜单
function handleClickOutside(event) {
  if (addWrapRef.value && !addWrapRef.value.contains(event.target)) {
    isAddMenuOpen.value = false;
  }
}

// 拖拽排序实现（保持不变）
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
      onDragEnd();
      return;
    }
    const moving = panes.splice(fromIdx, 1)[0];
    const insertAt = fromIdx < i ? i - 1 : i;
    panes.splice(insertAt, 0, moving);
  } finally {
    onDragEnd();
  }
}
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
  position: relative; /* NEW: 设置为相对定位，作为菜单的定位锚点 */
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 8px 0 0 0;
}

/* NEW: 新增指标菜单的样式 */
.add-menu {
  position: absolute;
  bottom: 100%; /* 显示在按钮上方 */
  left: 50%;
  transform: translateX(-50%);
  margin: 0 0 8px 0;
  padding: 6px 0;
  background-color: #1b1b1b;
  border: 1px solid #333;
  border-radius: 6px;
  list-style: none;
  z-index: 10;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  min-width: 120px;
}
.add-menu li {
  padding: 8px 16px;
  color: #ddd;
  cursor: pointer;
  white-space: nowrap;
  font-size: 14px;
}
.add-menu li:hover {
  background-color: #2b4b7e;
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
