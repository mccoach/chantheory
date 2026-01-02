<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\main-chart\MainChartPanel.vue -->
<!-- ============================== -->
<!-- 本轮改动：主图分型+涨跌 markerWidth 由通用 WidthController 管理
     - 每次 renderHub 下发主图 option 并 setOption(notMerge:true) 后，显式调用 scheduleWidthUpdate()
       作为“option 已落地”的强时序信号，消除竞态。 -->
<template>
  <MainChartControls />

  <div ref="wrap" class="chart" tabindex="0" @mouseenter="onMouseEnter" @mouseleave="onMouseLeave"
    @dblclick="openSettingsDialog">
    <div class="top-info">
      <div class="title">{{ displayTitle }}</div>
      <div class="right-box">
        <div class="status">
          <span v-if="vm.loading.value" class="badge busy">更新中…</span>

          <transition name="hintfade">
            <span
              v-if="!vm.loading.value && refreshStatus.showRefreshed.value && vm.meta.value?.completeness === 'complete'"
              class="badge done">
              已刷新 {{ refreshStatus.refreshedAtHHMMSS.value }}
            </span>
          </transition>

          <span v-if="!vm.loading.value && vm.meta.value?.completeness === 'incomplete'" class="badge warn"
            title="近端数据更新失败，当前为历史缓存">
            数据不完整 {{ refreshStatus.refreshedAtHHMMSS.value }}
          </span>
        </div>

        <div class="adj-seg" title="复权方式">
          <button class="adj-btn" :class="{ active: isAdjust('qfq') }" @click="setAdjust('qfq')">
            前
          </button>
          <button class="adj-btn" :class="{ active: isAdjust('none') }" @click="setAdjust('none')">
            无
          </button>
          <button class="adj-btn" :class="{ active: isAdjust('hfq') }" @click="setAdjust('hfq')">
            后
          </button>
        </div>

        <button class="btn-settings" @click="openSettingsDialog" title="主图设置" aria-label="主图设置"
          v-html="SETTINGS_ICON_SVG"></button>
      </div>
    </div>

    <div ref="host" class="canvas-host"></div>

    <div
      class="bottom-strip"
      title="上下拖拽调整窗体高度（双击恢复默认）"
      @mousedown="onResizeHandleDown('bottom', $event)"
      @dblclick.stop.prevent="resetHeightToDefault"
    ></div>
  </div>
</template>

<script setup>
import { inject, ref, onBeforeUnmount, computed } from "vue";
import { openMainChartSettings } from "@/settings/mainShell";
import { useChartPanel } from "@/composables/useChartPanel";
import { useRefreshStatus } from "@/composables/useRefreshStatus";
import { useUserSettings } from "@/composables/useUserSettings";
import MainChartControls from "./main-chart/MainChartControls.vue";
import { SETTINGS_ICON_SVG } from "@/constants/icons";

const vm = inject("marketView");
const renderHub = inject("renderHub");
const hub = inject("viewCommandHub");
const dialogManager = inject("dialogManager");

const refreshStatus = useRefreshStatus(vm.loading, vm.error);
const settings = useUserSettings();

const {
  wrapRef: wrap,
  hostRef: host,
  displayTitle,
  onResizeHandleDown,
  resetHeightToDefault,
  onMouseEnter,
  onMouseLeave,
  scheduleWidthUpdate,
} = useChartPanel({
  panelKey: ref("main"),
  vm: vm,
  hub: hub,
  renderHub: renderHub,
  onChartReady: (instance) => {
    try {
      renderHub.registerChart("main", instance);

      // DEV ONLY: 暴露主图实例到 window，便于控制台导出中间数据
      if (import.meta.env.DEV) {
        try {
          window.__CHARTS__ = window.__CHARTS__ || {};
          window.__CHARTS__.main = instance;
        } catch { }
      }

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

            // 关键时序信号：option 已落地，再更新 widthState 并触发最小重绘
            scheduleWidthUpdate?.();
          }
        } catch (e) {
          console.error("MainChartPanel onRender error:", e);
        }
      });

      onBeforeUnmount(() => renderHub.offRender(unsubId));
    } catch { }
  },
});

const currentAdjust = computed(() => String(vm.adjust?.value || "none"));

function isAdjust(kind) {
  const k = kind === "qfq" || kind === "hfq" ? kind : "none";
  return currentAdjust.value === k;
}

function setAdjust(kind) {
  const k = kind === "qfq" || kind === "hfq" ? kind : "none";
  try {
    settings.setAdjust(k);
  } catch (e) {
    console.error("setAdjust failed:", e);
  }
}

function openSettingsDialog() {
  try {
    openMainChartSettings(dialogManager, { activeTab: "chan" });
  } catch (e) { }
}

onBeforeUnmount(() => {
  renderHub.unregisterChart("main");
});
</script>

<style scoped>
/* 样式保持原样，仅 title 文案已在模板更新 */
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

.badge.warn {
  background: rgba(231, 76, 60, 0.15);
  border: 1px solid rgba(231, 76, 60, 0.4);
  color: #e74c3c;
  cursor: help;
}

.hintfade-leave-active {
  transition: opacity 1000ms ease;
}

.hintfade-enter-from,
.hintfade-leave-to {
  opacity: 0;
}

.adj-seg {
  display: inline-flex;
  align-items: center;
  border: 1px solid #444;
  border-radius: 10px;
  overflow: hidden;
  background: #1a1a1a;
  height: 24px;
}

.adj-btn {
  background: transparent;
  color: #ccc;
  border: none;
  padding: 2px 8px;
  cursor: pointer;
  user-select: none;
  font-size: 12px;
  line-height: 20px;
  height: 24px;
}

.adj-btn+.adj-btn {
  border-left: 1px solid #444;
}

.adj-btn.active {
  background: #2b4b7e;
  color: #fff;
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
