<!-- src/App.vue -->
<!-- ============================== -->
<!-- V8.0 - 符合职责单一原则 -->
<!-- ============================== -->
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
import { ref, computed, provide, onMounted, readonly, inject, onBeforeUnmount, watch } from "vue"
import { useMarketView } from "./composables/useMarketView"
import { useViewCommandHub } from "./composables/useViewCommandHub"
import { useViewRenderHub } from "./composables/useViewRenderHub"
import { useDialogManager } from "./composables/useDialogManager"
import { useExportController } from "./composables/useExportController"
import { useEventStream } from '@/composables/useEventStream'
import { ensureIndexFresh } from "./composables/useSymbolIndex"
import { useWatchlist } from "./composables/useWatchlist"
import { waitBackendAlive } from "./utils/backendReady"

// ===== 核心修复：导入处理器注册器 =====
import { 
  registerGlobalHandlers, 
  registerModalSettingsHandlers,
  unregisterAllHandlers 
} from "@/interaction/handlers/global"
import { pushDialogScope, popDialogScope } from "@/interaction/handlers/scopes"

import TopTitle from "./components/features/TopTitle.vue"
import SymbolPanel from "./components/features/SymbolPanel.vue"
import MainChartPanel from "./components/features/MainChartPanel.vue"
import TechPanels from "./components/features/TechPanels.vue"
import ModalDialog from "./components/ui/ModalDialog.vue"

const backendReady = ref(false)

const hub = useViewCommandHub()
const vm = useMarketView({ autoStart: false })
const renderHub = useViewRenderHub()
const dialogManager = useDialogManager()
const hotkeys = inject("hotkeys")
const exportCtl = useExportController({
  isBusy: () => vm.loading.value,
})
renderHub.setMarketView(vm)

provide("marketView", vm)
provide("viewCommandHub", hub)
provide("renderHub", renderHub)
provide("dialogManager", dialogManager)
provide("exportController", exportCtl)

const activeDialog = computed(() => dialogManager.activeDialog.value)
const dialogBodyRef = ref(null)

function handleModalClose() {
  try {
    const onClose = activeDialog.value?.onClose
    if (typeof onClose === "function") {
      onClose()
    }
    dialogManager.close()
  } catch (e) {
    console.error("Modal close error:", e)
  }
}

function handleModalSave() {
  try {
    if (dialogBodyRef.value && typeof dialogBodyRef.value.save === "function") {
      dialogBodyRef.value.save()
    }
    const onSave = activeDialog.value?.onSave
    if (typeof onSave === "function") {
      onSave()
    }
    dialogManager.close()
  } catch (e) {
    console.error("Modal save error:", e)
  }
}

function handleModalResetAll() {
  try {
    if (dialogBodyRef.value && typeof dialogBodyRef.value.resetAll === "function") {
      dialogBodyRef.value.resetAll()
    }
    const onResetAll = activeDialog.value?.onResetAll
    if (typeof onResetAll === "function") {
      onResetAll()
    }
  } catch (e) {
    console.error("Modal resetAll error:", e)
  }
}

function handleTabChange(key) {
  try {
    dialogManager.setActiveTab(key)
  } catch (e) {
    console.error("Tab change error:", e)
  }
}

// ===== 核心修复：监听弹窗状态，管理作用域 =====
watch(activeDialog, (newDialog, oldDialog) => {
  // 弹窗打开
  if (newDialog && !oldDialog) {
    pushDialogScope({ 
      hotkeys, 
      scope: "modal:settings"  // ← 固定作用域（所有设置弹窗共用）
    });
  }

  // 弹窗关闭
  if (!newDialog && oldDialog) {
    popDialogScope({ 
      hotkeys, 
      scope: "modal:settings" 
    });
  }
});

onMounted(async () => {
  // ===== 核心修复：委托给专门的注册器 =====
  registerGlobalHandlers({ 
    hotkeys, 
    dialogManager, 
    vm, 
    renderHub 
  });
  
  registerModalSettingsHandlers({ 
    hotkeys, 
    onClose: handleModalClose, 
    onSave: handleModalSave 
  });

  const alive = await waitBackendAlive({ intervalMs: 200 })
  backendReady.value = !!alive
  
  if (backendReady.value) {
    console.log('[App] 🚀 后端就绪，启动应用')
    
    const { connect, connected } = useEventStream()
    connect()
    
    console.log('[App] ⏳ 等待SSE连接...')
    let retries = 0
    while (!connected.value && retries < 50) {
      await new Promise(r => setTimeout(r, 100))
      retries++
    }
    
    if (!connected.value) {
      console.error('[App] ❌ SSE连接超时')
      alert('无法建立实时连接，请刷新页面')
      return
    }
    
    console.log('[App] ✅ SSE已连接')
    
    await ensureIndexFresh(false)
    
    const wl = useWatchlist()
    await wl.smartLoad()
    
    vm.reload({ force: true })
    
    ensureIndexFresh(true)
    
    console.log('[App] ✅ 应用启动完成')
  }
})

onBeforeUnmount(() => {
  // ===== 核心修复：委托给专门的注销器 =====
  unregisterAllHandlers({ hotkeys });
});

if (import.meta.env.DEV) {
  window.__DEBUG__ = { vm, candles: vm.candles, meta: vm.meta, hotkeys };
}
</script>

<style scoped>
/* 样式保持不变 */
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
  to { transform: rotate(360deg); }
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