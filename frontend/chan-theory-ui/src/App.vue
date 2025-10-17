<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\App.vue -->
<!-- 说明：删除旧自选面板 WatchlistPanel 的引入与渲染；其余保持不变 -->
<template>
  <div class="page-wrap">
    <TopTitle />
    <SymbolPanel />
    <MainChartPanel />
    <TechPanels />
    <!-- <StorageManager v-if="backendReady" /> -->

    <!-- 全局唯一设置弹窗外壳：新增 tabs/activeTab 透传与 tab-change 处理 -->
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
          :ref="dialogBodyRef"
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
import MainChartPanel from "./components/features/MainChartPanel.vue";
import TechPanels from "./components/features/TechPanels.vue";
// import StorageManager from "@/components/features/StorageManager.vue";
import ModalDialog from "@/components/ui/ModalDialog.vue";

import { useUserSettings } from "./composables/useUserSettings";
import { useMarketView } from "./composables/useMarketView";
import { useExportController } from "./composables/useExportController";
import { useDialogManager } from "./composables/useDialogManager";
import { buildExportFilename } from "./utils/download";
import { waitBackendAlive } from "./utils/backendReady";
import { ensureIndexFresh } from "./composables/useSymbolIndex";
// NEW: 统一渲染中枢
import { useViewRenderHub } from "@/composables/useViewRenderHub";
// NEW: 显示状态中枢（供设置保存/重置后“刷新”）
import { useViewCommandHub } from "@/composables/useViewCommandHub";

const settings = useUserSettings();
const vm = useMarketView({ autoStart: false }); // 关键变更：延迟首刷
provide("marketView", vm);

// 初始化并提供渲染中枢（上游唯一源头）
const renderHub = useViewRenderHub();
renderHub.setMarketView(vm);
provide("renderHub", renderHub);

// NEW: 中枢（供设置保存/重置时调用 Refresh）
const hub = useViewCommandHub();

const dialogManager = useDialogManager();
provide("dialogManager", dialogManager);

const dialogBodyRef = ref(null);

const hotkeys = inject("hotkeys", null);
if (hotkeys) {
  hotkeys.registerHandlers("global", {
    refresh() {
      vm.reload(true);
    },
    toggleExportMenu() {
      try {
        window.dispatchEvent(new CustomEvent("chan:toggle-export-menu"));
      } catch {}
    },
    openHotkeySettings() {
      import("@/components/ui/HotkeySettingsDialog.vue").then((mod) => {
        dialogManager.open({
          title: "快捷键设置",
          contentComponent: mod.default,
          onSave: () => {
            handleModalClose();
          },
          onClose: () => handleModalClose(),
        });
      });
    },
    // NEW: 全局左右键 → 由渲染中枢作用于“激活窗体”
    cursorLeft() { try { renderHub.moveCursorByStep(-1); } catch {} },
    cursorRight() { try { renderHub.moveCursorByStep(+1); } catch {} },
  });

  hotkeys.registerHandlers("modal:settings", {
    closeSettings() { handleModalClose(); },
    saveSettings() { handleModalSave(); },
  });
}

const exportController = useExportController({
  isBusy: () => vm.loading.value,
  filenameBuilder: (fmt) =>
    buildExportFilename(vm.code.value, vm.freq.value, fmt),
});
provide("exportController", exportController);

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
  const dlg = dialogManager.activeDialog.value;
  if (dlg && typeof dlg.onSave === "function") {
    try {
      dlg.onSave();
    } catch (e) {
      console.error(e);
    }
  }
}
function handleModalClose() {
  const dlg = dialogManager.activeDialog.value;
  if (dlg && typeof dlg.onClose === "function") {
    try {
      dlg.onClose();
    } catch (e) {
      console.error(e);
    }
  } else {
    dialogManager.close();
  }
}
function handleModalResetAll() {
  const dlg = dialogManager.activeDialog.value;
  try {
    // 优先：内容组件自带重置回调（内容组件内部负责“写入持久化 + 决定是否需要 reload”）
    if (dlg && typeof dlg.onResetAll === "function") {
      dlg.onResetAll();
      // —— 仅做前端刷新，不触发后端 —— //
      try { if (hub && typeof hub.execute === "function") hub.execute("Refresh", {}); } catch {}
      return;
    }
    // 次选：内容组件若暴露 resetAll()
    const body = dialogBodyRef.value;
    if (body && typeof body.resetAll === "function") {
      body.resetAll();
      try { if (hub && typeof hub.execute === "function") hub.execute("Refresh", {}); } catch {}
      return;
    }
    console.warn("当前设置窗未提供 onResetAll 或 resetAll，忽略重置命令。");
  } catch (e) {
    console.error("handleModalResetAll error:", e);
  }
}

// —— openSettingsDialog 内对“保存并应用”与“重置”的实现位于 MainChartPanel.vue —— //
// 这里不再做任何 reload；由内容组件决定“是否需要后端请求”（例如 adjust ���化）并自行调用 vm.reload。
onMounted(async () => {
  const alive = await waitBackendAlive({ timeoutMs: 10000, intervalMs: 600 });
  backendReady.value = !!alive;
  if (backendReady.value) {
    await ensureIndexFresh(false);
    vm.reload({ force: true }); // 探活成功后首刷
    ensureIndexFresh(true);
  } else {
    console.warn("Backend not alive within timeout; panels gated by v-if");
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
