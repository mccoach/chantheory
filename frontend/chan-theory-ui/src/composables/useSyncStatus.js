// frontend/src/composables/useSyncStatus.js
// ==============================
// 说明：后台同步状态管理的 Composable (全新)
// - (FIX) 修复对 getStatus() 响应的错误解包。
// - (FIX) 简化错误处理逻辑，仅打印日志并更新状态，避免复杂的重试机制。
// ==============================

import { ref, onMounted, onUnmounted, readonly } from "vue";
import { getStatus, triggerHistorySync, triggerIntegrityScan } from "@/services/statusService";

const status = ref({
  isRunning: false,
  phase: 'idle',
  currentTaskDescription: 'N/A',
  tasks_summary: {
    total: 0,
    pending: 0,
  }
});
const isStartingSync = ref(false);
const isStartingScan = ref(false);
let pollInterval = null;

export function useSyncStatus() {
  
  async function pollStatus() {
    try {
      // (FIX) getStatus() 直接返回后端接口的 `data` 部分，结构为 { ok, data }
      const response = await getStatus();
      // (FIX) 正确地从 `response.data` 中获取状态对象，并增加健壮的空值处理
      const state = response?.data ?? {};
      
      const phase = state.phase || 'idle';
      const isRunning = phase && phase !== 'sleeping' && phase !== 'idle';
      // (FIX) 状态对象已变更，适配新的字段
      const total = state.total_tasks || 0;
      const completed = state.completed_tasks || 0;
      const pending = total > 0 ? total - completed : 0;

      status.value = {
        isRunning: isRunning,
        phase: phase,
        currentTask: state.current_task_description || 'N/A',
        totalTasks: total,
        pendingTasks: pending,
      };
    } catch (error) {
      // (FIX) 简化错误处理：仅记录日志，并将状态标记为 error，不引入复杂的重试逻辑
      console.error("Failed to poll sync status:", error);
      status.value.phase = 'error';
      status.value.isRunning = false;
    }
  }

  async function startSync() {
    if (isStartingSync.value) return;
    isStartingSync.value = true;
    try {
      await triggerHistorySync();
      // 触发后立即轮询一次以更新状态
      await pollStatus();
    } catch (error) {
      console.error("Failed to trigger history sync:", error);
    } finally {
      // 留一个短暂的loading状态给用户感知
      setTimeout(() => { isStartingSync.value = false; }, 2000);
    }
  }

  async function startScan() {
    if (isStartingScan.value) return;
    isStartingScan.value = true;
    try {
      await triggerIntegrityScan();
      // 触发后也立即轮询
      await pollStatus();
    } catch (error) {
      console.error("Failed to trigger integrity scan:", error);
    } finally {
      setTimeout(() => { isStartingScan.value = false; }, 2000);
    }
  }

  onMounted(() => {
    pollStatus(); // 立即执行一次
    pollInterval = setInterval(pollStatus, 5000); // 每5秒轮询
  });

  onUnmounted(() => {
    if (pollInterval) {
      clearInterval(pollInterval);
    }
  });

  return {
    status: readonly(status),
    isSyncing: readonly(isStartingSync),
    isScanning: readonly(isStartingScan),
    startSync,
    startScan,
  };
}
