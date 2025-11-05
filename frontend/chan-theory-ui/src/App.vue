<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\App.vue -->
<!-- (REFACTORED)
  - 新增 SyncStatusPanel 组件，用于显示后台同步状态。
-->
<template>
  <div class="page-wrap">
    <TopTitle />
    <SymbolPanel />
    <SyncStatusPanel /> <!-- (NEW) 新增同步状态面板 -->
    <MainChartPanel />
    <TechPanels />

    <ModalDialog
      :show="!!dialogManager.activeDialog.value"
      :title="dialogManager.activeDialog.value?.title"
      :tabs="dialogManager.activeDialog.value?.tabs"
      :activeTab="dialogManager.activeDialog.value?.activeTab"
      @tab-change="(k) => dialogManager.setActiveTab(k)"
      @close="handleModalClose"
      @save="handleModalSave"
      @reset-all="handleModalResetAll"
    >
      <template #body>
        <component
          v-if="dialogManager.activeDialog.value?.contentComponent"
          :is="dialogManager.activeDialog.value.contentComponent"
          v-bind="dialogManager.activeDialog.value.props"
          :activeTab="dialogManager.activeDialog.value.activeTab"
          ref="dialogBodyRef"
        />
      </template>

      <template #footer-left>
        <component
          v-if="dialogManager.activeDialog.value?.footerLeftComponent"
          :is="dialogManager.activeDialog.value.footerLeftComponent"
          v-bind="dialogManager.activeDialog.value.props"
        />
      </template>
    </ModalDialog>

    <div class="meta">
      meta: {{ vm.meta && vm.meta.value ? JSON.stringify(vm.meta.value) : "" }}
    </div>
    <div v-if="vm.error" class="error">错误：{{ vm.error }}</div>
    <div v-if="vm.loading" class="loading">加载中...</div>
  </div>
</template>

<script setup>
import { onMounted, provide, ref, inject, watch } from "vue";
import TopTitle from "./components/features/TopTitle.vue";
import SymbolPanel from "./components/features/SymbolPanel.vue";
import SyncStatusPanel from "./components/features/SyncStatusPanel.vue"; // (NEW) 导入
import MainChartPanel from "./components/features/MainChartPanel.vue";
import TechPanels from "./components/features/TechPanels.vue";
import ModalDialog from "@/components/ui/ModalDialog.vue";

import { useUserSettings } from "./composables/useUserSettings";
import { useMarketView } from "./composables/useMarketView";
import { useDialogManager } from "./composables/useDialogManager";
import { waitBackendAlive } from "./utils/backendReady";
import { useEventStream } from '@/composables/useEventStream';
import { ensureIndexFresh } from "./composables/useSymbolIndex";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import { useViewCommandHub } from "@/composables/useViewCommandHub";

const settings = useUserSettings();
provide("userSettings", settings);
const vm = useMarketView({ autoStart: false });
provide("marketView", vm);

const renderHub = useViewRenderHub();
renderHub.setMarketView(vm);
provide("renderHub", renderHub);

const hub = useViewCommandHub();
provide("viewCommandHub", hub);

const dialogManager = useDialogManager();
provide("dialogManager", dialogManager);

const dialogBodyRef = ref(null);
const hotkeys = inject("hotkeys", null);
if (hotkeys) {
  hotkeys.registerHandlers("global", {
    refresh() { vm.reload(true); },
    openHotkeySettings() {
      import("@/components/ui/HotkeySettingsDialog.vue").then((mod) => {
        dialogManager.open({ title: "快捷键设置", contentComponent: mod.default });
      });
    },
    cursorLeft() { try { renderHub.moveCursorByStep(-1); } catch {} },
    cursorRight() { try { renderHub.moveCursorByStep(+1); } catch {} },
  });
  hotkeys.registerHandlers("modal:settings", {
    closeSettings() { handleModalClose(); },
    saveSettings() { handleModalSave(); },
  });
}

const backendReady = ref(false);
provide("backendReady", backendReady);

let modalScopePushed = false;
watch(
  () => dialogManager.activeDialog.value,
  (dlg) => {
    if (!hotkeys) return;
    if (dlg && !modalScopePushed) {
      hotkeys.pushScope("modal:settings");
      modalScopePushed = true;
    } else if (!dlg && modalScopePushed) {
      hotkeys.popScope("modal:settings");
      modalScopePushed = false;
    }
  }
);

function handleModalSave() {
  const body = dialogBodyRef.value;
  if (body && typeof body.save === "function") {
    try { body.save(); } catch (e) { console.error("handleModalSave direct call error:", e); }
  } else { console.warn("handleModalSave: 'save' method not found on dialog body component."); }
  try { dialogManager.close(); } catch {}
}

function handleModalClose() {
  const dlg = dialogManager.activeDialog.value;
  if (dlg && typeof dlg.onClose === "function") {
    try { dlg.onClose(); } catch (e) { console.error(e); }
  } else {
    dialogManager.close();
  }
}

function handleModalResetAll() {
  const body = dialogBodyRef.value;
  if (body && typeof body.resetAll === "function") {
    try { body.resetAll(); } catch (e) { console.error("handleModalResetAll direct call error:", e); }
  } else { console.warn("handleModalResetAll: 'resetAll' method not found on dialog body component."); }
}

onMounted(async () => {
  const alive = await waitBackendAlive({ timeoutMs: 10000, intervalMs: 600 });
  backendReady.value = !!alive;
  if (backendReady.value) {
    console.log('[App] 建立 SSE 连接...');
    const { connect: connectEventStream } = useEventStream();
    connectEventStream();
    await ensureIndexFresh(false);
    vm.reload({ force: true });
    ensureIndexFresh(true);
  } else {
    console.warn("Backend not alive within timeout; some features may be disabled.");
  }
});
</script>

<style scoped>
.page-wrap {
  padding: 12px;
}
.meta {
  margin-top: 6px;
  font-size: 12px;
  color: #888;
  word-break: break-all;
}
.error {
  color: #c0392b;
  margin-top: 8px;
}
.loading {
  margin-top: 8px;
}
</style>
