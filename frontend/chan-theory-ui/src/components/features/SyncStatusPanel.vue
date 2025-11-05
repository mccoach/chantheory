<!-- frontend/src/components/features/SyncStatusPanel.vue -->
<!-- ============================== -->
<!-- 说明：后台同步状态面板 (全新组件)
     - 显示历史数据同步的总体进度和当前任务。
     - 提供手动触发“同步”和“完整性扫描”的按钮。
-->
<template>
  <div class="sync-status-panel">
    <div class="status-text" :title="status.currentTask || '暂无任务'">
      <span class="label">后台同步:</span>
      <span class="progress-bar">
        <span
          class="progress-fill"
          :style="{ width: `${progressPercentage}%` }"
          :class="{ idle: !status.isRunning }"
        ></span>
      </span>
      <span class="progress-text">{{ progressText }}</span>
    </div>
    <div class="actions">
      <button @click="startSync" :disabled="isSyncing" class="action-btn">
        {{ isSyncing ? "同步中..." : "同步历史" }}
      </button>
      <button @click="startScan" :disabled="isScanning" class="action-btn">
        {{ isScanning ? "扫描中..." : "扫描数据" }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useSyncStatus } from "@/composables/useSyncStatus";

const { status, isSyncing, isScanning, startSync, startScan } = useSyncStatus();

const progressPercentage = computed(() => {
  if (!status.value.totalTasks || status.value.totalTasks === 0) {
    return status.value.isRunning ? 0 : 100;
  }
  const done = status.value.totalTasks - (status.value.pendingTasks || 0);
  return (done / status.value.totalTasks) * 100;
});

const progressText = computed(() => {
  if (status.value.phase === 'sleeping') return '已完成, 等待下一周期';
  if (!status.value.isRunning) return "空闲";
  const done = status.value.totalTasks - (status.value.pendingTasks || 0);
  const total = status.value.totalTasks || 0;
  return `${done} / ${total}`;
});
</script>

<style scoped>
.sync-status-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  background-color: #1a1a1a;
  border-radius: 6px;
  border: 1px solid #333;
  margin: 8px 0;
  font-size: 13px;
}

.status-text {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #bbb;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-grow: 1;
}

.label {
  font-weight: 500;
}

.progress-bar {
  width: 120px;
  height: 10px;
  background-color: #333;
  border-radius: 5px;
  overflow: hidden;
  display: inline-block;
}

.progress-fill {
  display: block;
  height: 100%;
  background-color: #2b4b7e;
  transition: width 0.3s ease-out;
  border-radius: 5px;
}

.progress-fill.idle {
  background-color: #4caf50; /* 空闲时显示绿色 */
}

.progress-text {
  min-width: 80px;
  text-align: left;
}

.actions {
  display: flex;
  gap: 8px;
  margin-left: 16px;
}

.action-btn {
  background: #2a2a2a;
  color: #ddd;
  border: 1px solid #444;
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}

.action-btn:hover:not(:disabled) {
  background: #333;
  border-color: #555;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
