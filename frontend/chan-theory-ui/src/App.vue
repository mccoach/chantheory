<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\App.vue -->
<!-- ============================== -->
<!-- V9.0 - 启动指令集版
     
     启动阶段被动任务顺序：
       1) 探活（/api/ping）
       2) 建立 SSE 连接（/api/events/stream）
       3) trade_calendar：POST /api/ensure-data type=trade_calendar + waitTasksDone
       4) 当前标的行情：vm.reload({force_refresh:false, with_profile:true})
       5) 标的索引：
            5.1) 先 ensureIndexFresh(false) 读取现有快照（或缓存/内置），确保搜索等功能立即可用；
            5.2) 再 POST /api/ensure-data type=symbol_index（force_fetch=false）+ waitTasksDone；
            5.3) 最后再次 ensureIndexFresh(false) 读取可能更新后的快照。
       6) 自选池：wl.smartLoad()
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
      @close="handleModalClose"
      @save="handleModalSave"
      @reset-all="handleModalResetAll"
      @tab-change="handleTabChange"
    >
      <template #body>
        <component
          :is="activeDialog.contentComponent"
          v-bind="activeDialog.props || {}"
          ref="dialogBodyRef"
        />
      </template>
    </ModalDialog>
  </div>
</template>

<script setup>
import { ref, computed, provide, onMounted, inject, onBeforeUnmount, watch } from "vue";
import { useMarketView } from "./composables/useMarketView";
import { useViewCommandHub } from "./composables/useViewCommandHub";
import { useViewRenderHub } from "./composables/useViewRenderHub";
import { useDialogManager } from "./composables/useDialogManager";
import { useExportController } from "./composables/useExportController";
import { useEventStream } from "@/composables/useEventStream";
import { ensureIndexFresh } from "./composables/useSymbolIndex";
import { useWatchlist } from "./composables/useWatchlist";
import { waitBackendAlive } from "./utils/backendReady";

import {
  declareTradeCalendar,
  declareSymbolIndex,
} from "@/services/ensureDataAPI";
import { waitTasksDone } from "@/composables/useTaskWaiter";

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

function handleModalSave() {
  try {
    if (dialogBodyRef.value && typeof dialogBodyRef.value.save === "function") {
      dialogBodyRef.value.save();
    }
    const onSave = activeDialog.value?.onSave;
    if (typeof onSave === "function") {
      onSave();
    }
    dialogManager.close();
  } catch (e) {
    console.error("Modal save error:", e);
  }
}

function handleModalResetAll() {
  try {
    if (dialogBodyRef.value && typeof dialogBodyRef.value.resetAll === "function") {
      dialogBodyRef.value.resetAll();
    }
    const onResetAll = activeDialog.value?.onResetAll;
    if (typeof onResetAll === "function") {
      onResetAll();
    }
  } catch (e) {
    console.error("Modal resetAll error:", e);
  }
}

function handleTabChange(key) {
  try {
    dialogManager.setActiveTab(key);
  } catch (e) {
    console.error("Tab change error:", e);
  }
}

// 弹窗打开/关闭时管理快捷键作用域
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
    onSave: handleModalSave,
  });

  const alive = await waitBackendAlive({ intervalMs: 200 });
  backendReady.value = !!alive;

  if (!backendReady.value) {
    return;
  }

  console.log(`${nowTs()} [App] backend-ready, start-app`);

  // 建立 SSE 连接
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

  // ===== 启动被动任务指令集 =====

  // 1) 交易日历：仅由前端声明，后端不再自发
  try {
    const t = await declareTradeCalendar({ force_fetch: false });
    const tid = t?.task_id ? String(t.task_id) : null;
    if (tid) {
      await waitTasksDone({ taskIds: [tid], timeoutMs: 60000 });
    }
    console.log(`${nowTs()} [App] trade_calendar-ready`);
  } catch (e) {
    console.error(`${nowTs()} [App] trade_calendar-init-failed`, e);
    // 日历失败不阻断 UI，但后端缺口判断可能退化
  }

  // NEW: 前端加载 trade_calendar 快照并常驻内存（若后端未提供 GET /api/trade-calendar 会失败）
  try {
    const tc = useTradeCalendar();
    await tc.ensureLoaded();
    if (tc.ready.value) {
      console.log(`${nowTs()} [App] trade_calendar-snapshot-loaded`);
    } else {
      console.warn(`${nowTs()} [App] trade_calendar-snapshot-not-ready (ensureLoaded failed)`);
    }
  } catch (e) {
    console.error(`${nowTs()} [App] trade_calendar-snapshot-load-failed`, e);
  }

  // 2) 当前标的行情（K+因子+档案）
  await vm.reload({ force_refresh: false, with_profile: true });

  // 3) 标的索引：
  //    3.1) 先读现有快照；若失败退回缓存/内置。
  await ensureIndexFresh(false);

  //    3.2) 再声明 symbol_index 任务（缺口判断），完成后再读一次快照。
  try {
    const t = await declareSymbolIndex({ force_fetch: false });
    const tid = t?.task_id ? String(t.task_id) : null;
    if (tid) {
      await waitTasksDone({ taskIds: [tid], timeoutMs: 60000 });
      await ensureIndexFresh(false);
    }
    console.log(`${nowTs()} [App] symbol_index-ready`);
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