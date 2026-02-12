<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\App.vue -->
<!-- ============================== -->
<!-- V11.0 - REFACTOR: 启动阶段任务链路拉直（SymbolIndex/TradeCalendar）
     - 交易日历：改为 useTradeCalendar().ensureReady()（唯一工作路径）
     - 标的索引：改为 useSymbolIndex().ensureIndexReady({mode:'startup'})（唯一工作路径）
     - 删除启动阶段重复的 ensureIndexFresh/declareSymbolIndex 双段绕路编排
-->
<template>
  <div v-if="!backendReady" class="loading-screen">
    <div class="spinner"></div>
    <div class="text">正在连接后端服务...</div>
  </div>

  <div v-else class="app-container">
    <TopTitle />
    <SymbolPanel />
    <MainChartPanel />
    <TechPanels />

    <ModalDialog
      v-if="activeDialog"
      :show="true"
      :title="activeDialog.title"
      :tabs="activeDialog.tabs"
      :activeTab="activeDialog.activeTab"
      :footerActions="activeDialog.footerActions"
      @close="handleModalClose"
      @tab-change="handleTabChange"
      @action="handleFooterAction"
    >
      <template #body>
        <component
          :is="activeDialog.contentComponent"
          v-bind="activeDialog.props || {}"
          ref="dialogBodyRef"
        />
      </template>

      <template #footer-left>
        <component 
          v-if="footerLeftComp" 
          :is="footerLeftComp" 
          v-bind="footerLeftProps"
        />
      </template>
    </ModalDialog>
  </div>
</template>

<script setup>
import { ref, computed, provide, onMounted, inject, onBeforeUnmount, watch } from "vue";
import { useMarketView } from "./composables/useMarketView";
import { useViewCommandHub } from "./composables/useViewCommandHub";
import { useViewRenderHub } from "./composables/viewRenderHub";
import { useDialogManager } from "./composables/useDialogManager";
import { useExportController } from "./composables/useExportController";
import { useEventStream } from "@/composables/useEventStream";
import { useWatchlist } from "./composables/useWatchlist";
import { waitBackendAlive } from "./utils/backendReady";

import {
  registerGlobalHandlers,
  registerModalSettingsHandlers,
  unregisterAllHandlers,
} from "@/interaction/handlers/global";
import { pushDialogScope, popDialogScope } from "@/interaction/handlers/scopes";

import TopTitle from "./components/features/TopTitle.vue";
import SymbolPanel from "./components/features/SymbolPanel.vue";
import MainChartPanel from "./components/features/MainChartPanel.vue";
import TechPanels from "./components/features/TechPanels.vue";
import ModalDialog from "./components/ui/ModalDialog.vue";
import { useTradeCalendar } from "@/composables/useTradeCalendar";
import { useSymbolIndex } from "@/composables/useSymbolIndex";

const backendReady = ref(false);

const hub = useViewCommandHub();
const vm = useMarketView({ autoStart: false });
const renderHub = useViewRenderHub();
const dialogManager = useDialogManager();
const hotkeys = inject("hotkeys");
const exportCtl = useExportController({
  isBusy: () => vm.loading.value,
});
renderHub.setMarketView(vm);

provide("marketView", vm);
provide("viewCommandHub", hub);
provide("renderHub", renderHub);
provide("dialogManager", dialogManager);
provide("exportController", exportCtl);

const activeDialog = computed(() => dialogManager.activeDialog.value);
const dialogBodyRef = ref(null);

const footerLeftComp = computed(() => {
  const body = dialogBodyRef.value;
  const comp = body && typeof body === "object" ? body.dialogFooterLeft : null;
  return comp || null;
});

const footerLeftProps = computed(() => {
  const body = dialogBodyRef.value;
  const props = body && typeof body === "object" ? body.dialogFooterLeftProps : null;

  if (props && typeof props === "object" && "value" in props) {
    return props.value || {};
  }

  return props && typeof props === "object" ? props : {};
});

function nowTs() {
  return new Date().toISOString();
}

function handleModalClose() {
  try {
    const onClose = activeDialog.value?.onClose;
    if (typeof onClose === "function") {
      onClose();
    }
    dialogManager.close();
  } catch (e) {
    console.error("Modal close error:", e);
  }
}

function handleTabChange(key) {
  try {
    dialogManager.setActiveTab(key);
  } catch (e) {
    console.error("Tab change error:", e);
  }
}

function handleFooterAction(action) {
  try {
    const act = action && typeof action === "object" ? action : {};
    const key = String(act.key || "").trim();
    if (!key) return;

    if (key === "close") {
      handleModalClose();
      return;
    }

    const body = dialogBodyRef.value;

    const actionMap = body && typeof body === "object" ? body.dialogActions : null;
    const fn = actionMap && typeof actionMap === "object" ? actionMap[key] : null;

    if (typeof fn !== "function") {
      if (import.meta.env.DEV) {
        const title = String(activeDialog.value?.title || "");
        console.warn(
          `[DialogActionContract] missing handler: key='${key}' title='${title}'`
        );
      }
      return;
    }

    fn({
      action: act,
      actionKey: key,
      dialogManager,
      dialogBodyRef: body,
      close: handleModalClose,
    });
  } catch (e) {
    console.error("Footer action error:", e);
  }
}

watch(activeDialog, (newDialog, oldDialog) => {
  if (newDialog && !oldDialog) {
    pushDialogScope({
      hotkeys,
      scope: "modal:settings",
    });
  }
  if (!newDialog && oldDialog) {
    popDialogScope({
      hotkeys,
      scope: "modal:settings",
    });
  }
});

onMounted(async () => {
  registerGlobalHandlers({
    hotkeys,
    dialogManager,
    vm,
    renderHub,
  });

  registerModalSettingsHandlers({
    hotkeys,
    onClose: handleModalClose,
    onSave: () => {
      try {
        const acts = activeDialog.value?.footerActions || [];
        const saveAct = Array.isArray(acts) ? acts.find((a) => String(a?.key || "") === "save") : null;
        if (saveAct) {
          handleFooterAction(saveAct);
        }
      } catch (e) {
        console.error("Hotkey saveSettings error:", e);
      }
    },
  });

  const alive = await waitBackendAlive({ intervalMs: 200 });
  backendReady.value = !!alive;

  if (!backendReady.value) {
    return;
  }

  console.log(`${nowTs()} [App] backend-ready, start-app`);

  // 建立 SSE 连接（单例）
  const { connect, connected } = useEventStream();
  connect();

  console.log(`${nowTs()} [App] waiting-sse-connection`);
  let retries = 0;
  while (!connected.value && retries < 50) {
    await new Promise((r) => setTimeout(r, 100));
    retries++;
  }

  if (!connected.value) {
    console.error(`${nowTs()} [App] sse-timeout`);
    alert("无法建立实时连接，请刷新页面");
    return;
  }

  console.log(`${nowTs()} [App] sse-connected`);

  // ===== 启动被动任务指令集（拉直版）=====

  // 1) 交易日历：唯一入口 ensureReady（declare+wait+load snapshot）
  try {
    const tc = useTradeCalendar();
    const r = await tc.ensureReady({ force_fetch: false, timeoutMs: 60000 });
    if (r?.ok) console.log(`${nowTs()} [App] trade_calendar-ready`);
    else console.warn(`${nowTs()} [App] trade_calendar-not-ready`);
  } catch (e) {
    console.error(`${nowTs()} [App] trade_calendar-init-failed`, e);
  }

  // 2) 当前标的行情（K+因子+档案）
  await vm.reload({ force_refresh: false, with_profile: true });

  // 3) 标的索引：唯一入口 ensureIndexReady(mode=startup)
  try {
    const si = useSymbolIndex();
    const r = await si.ensureIndexReady({ mode: "startup" });
    if (r?.ok) console.log(`${nowTs()} [App] symbol_index-ready`);
    else console.warn(`${nowTs()} [App] symbol_index-not-ready`);
  } catch (e) {
    console.error(`${nowTs()} [App] symbol_index-init-failed`, e);
  }

  // 4) 自选列表（全量快照）
  const wl = useWatchlist();
  await wl.smartLoad();

  console.log(`${nowTs()} [App] app-started`);
});

onBeforeUnmount(() => {
  unregisterAllHandlers({ hotkeys });
});

if (import.meta.env.DEV) {
  window.__DEBUG__ = { vm, candles: vm.candles, meta: vm.meta, hotkeys };
}
</script>

<style scoped>
.loading-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #111;
  color: #ddd;
}
.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #333;
  border-top-color: #2b4b7e;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.text {
  margin-top: 16px;
  font-size: 14px;
  color: #bbb;
}
.app-container {
  padding: 20px;
  max-width: 1920px;
  margin: 0 auto;
}
</style>
