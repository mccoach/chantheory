<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\MainChartPanel.vue -->
<!-- ============================== -->
<!-- 说明：主图组件（接入"上游统一渲染中枢 useViewRenderHub" · 一次订阅一次渲染）
     - REFACTORED:
       - 移除所有本地的 option 构建逻辑，简化为纯粹的 option 消费者。
       - 将所有顶部控制UI和逻辑提取到新的 <MainChartControls /> 组件中。
     - FIX: 确保"更新完成"提示的模板代码完整且 z-index 足够高。
     - NEW: 消费 meta.completeness 字段，显示“数据不完整”警告。
-->
<template>
  <!-- REFACTORED: 顶部控制区已提取到 MainChartControls 组件 -->
  <MainChartControls />

  <!-- 主图画布容器 -->
  <div
    ref="wrap"
    class="chart"
    tabindex="0"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
    @dblclick="openSettingsDialog"
  >
    <div class="top-info">
      <div class="title">{{ displayTitle }}</div>
      <div class="right-box">
        <div class="status">
          <span v-if="vm.loading.value" class="badge busy">更新中…</span>
          <!-- NEW: 根据 completeness 显示不同状态 -->
          <transition name="hintfade">
            <span v-if="!vm.loading.value && showRefreshed && vm.meta.value?.completeness === 'complete'" class="badge done">
              已刷新 {{ refreshedAtHHMMSS }}
            </span>
          </transition>
          <span v-if="!vm.loading.value && vm.meta.value?.completeness === 'incomplete'" class="badge warn" title="近端数据更新失败，当前为历史缓存">
            数据不完整
          </span>
        </div>
        <!-- NEW: 主图设置按钮 -->
        <button
          class="btn-settings"
          @click="openSettingsDialog"
          title="主图设置"
          aria-label="主图设置"
          v-html="SETTINGS_ICON_SVG"
        ></button>
      </div>
    </div>
    <div ref="host" class="canvas-host"></div>
    <div
      class="bottom-strip"
      title="上下拖拽调整窗体高度"
      @mousedown="onResizeHandleDown('bottom', $event)"
    ></div>
  </div>
</template>

<script setup>
import { inject, ref, computed, watch, onBeforeUnmount } from "vue";
import { openMainChartSettings } from "@/settings/mainShell";
import { useChartPanel } from "@/composables/useChartPanel";
import { pad2 } from "@/utils/timeFormat";
import MainChartControls from "./main-chart/MainChartControls.vue";
import { SETTINGS_ICON_SVG } from "@/constants/icons"; // NEW: Import SVG constant

// --- Injected Services ---
const vm = inject("marketView");
const renderHub = inject("renderHub");
const hub = inject("viewCommandHub");
const dialogManager = inject("dialogManager");

// --- Use the common chart panel logic ---
const {
  wrapRef: wrap,
  hostRef: host,
  displayTitle,
  onResizeHandleDown,
  onMouseEnter,
  onMouseLeave,
} = useChartPanel({
  panelKey: ref("main"),
  vm: vm,
  hub: hub,
  renderHub: renderHub,
  onChartReady: (instance) => {
    try {
      renderHub.registerChart("main", instance);
      host.value?.addEventListener("mouseenter", () => {
        renderHub.setActivePanel("main");
      });

      const unsubId = renderHub.onRender((snapshot) => {
        try {
          if (instance && snapshot.main?.option) {
            instance.setOption(snapshot.main.option, {
              notMerge: true,
              silent: true,
            });
          }
        } catch (e) {
          console.error("MainChartPanel onRender error:", e);
        }
      });
      onBeforeUnmount(() => renderHub.offRender(unsubId));
    } catch {}
  },
});

// --- Component-Specific Logic (Status Display) ---

const showRefreshed = ref(false);
const refreshedAt = ref(null);
const refreshedAtHHMMSS = computed(() => {
  if (!refreshedAt.value) return "";
  const d = refreshedAt.value;
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(
    d.getSeconds()
  )}`;
});

watch(
  () => vm.loading.value,
  (isLoading, wasLoading) => {
    if (wasLoading === true && isLoading === false) {
      if (!vm.error.value) {
        refreshedAt.value = new Date();
        showRefreshed.value = true;
        setTimeout(() => {
          showRefreshed.value = false;
        }, 2000);
      }
    }
  }
);

function openSettingsDialog() {
  try {
    openMainChartSettings(dialogManager, { activeTab: "chan" });
  } catch (e) {}
}

onBeforeUnmount(() => {
  renderHub.unregisterChart("main");
});
</script>

<style scoped>
/* 样式已精简，不再包含任何与 .controls-grid-2x2 相关的规则 */
.top-info {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 28px;
  display: flex;
  align-items: center;
  padding: 0 8px;
  gap: 10px;
  z-index: 100;
  pointer-events: none;
}
.top-info * {
  pointer-events: auto;
}
.top-info .title {
  font-size: 13px;
  font-weight: 600;
  color: #ddd;
  user-select: none;
}
.top-info .right-box {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  user-select: none;
}
/* NEW: 设置按钮样式 */
.btn-settings {
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
}
.badge {
  display: inline-block;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  line-height: 18px;
}
.badge.busy {
  background: rgba(255, 193, 7, 0.15);
  border: 1px solid rgba(255, 193, 7, 0.35);
  color: #ffca28;
}
.badge.done {
  background: rgba(46, 204, 113, 0.15);
  border: 1px solid rgba(46, 204, 113, 0.35);
  color: #2ecc71;
}
/* NEW: "数据不完整" 警告样式 */
.badge.warn {
  background: rgba(231, 76, 60, 0.15);
  border: 1px solid rgba(231, 76, 60, 0.4);
  color: #e74c3c;
  cursor: help;
}
/* NEW: 渐变淡出动画（已刷新提示） */
.hintfade-leave-active {
  transition: opacity 1000ms ease;
}
.hintfade-enter-from,
.hintfade-leave-to {
  opacity: 0;
}

.chart {
  position: relative;
  width: 100%;
  height: clamp(360px, 50vh, 700px);
  background: #111;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  overflow: hidden;
  outline: none;
}
.canvas-host {
  position: absolute;
  left: 0;
  right: 0;
  top: 28px;
  bottom: 18px;
}
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
</style>
