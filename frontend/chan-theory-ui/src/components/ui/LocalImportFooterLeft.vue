<!-- src/components/ui/LocalImportFooterLeft.vue -->
<!-- ==============================
盘后数据导入弹窗底栏左侧信息区
职责：
  - 只展示 local import 主批次状态与少量辅助动作
  - 不做业务推导
  - retry/cancel 可用性只认后端字段
============================== -->
<template>
  <div class="footer-wrap">
    <div class="footer-inline">
      <div class="col col-progress">
        <div class="bar">
          <div class="fill" :style="{ width: progressPercent + '%' }"></div>
          <div class="bar-text">
            {{ progressDone }} / {{ progressTotal }}（{{ progressText }}）
          </div>
        </div>

        <div class="subline">
          <span class="tag" :class="stateTagClass">{{ batchStateText }}</span>
          <span v-if="batchId" class="id" :title="batchId">{{ batchId }}</span>
          <span v-if="uiMessage" class="msg" :title="uiMessage">{{ uiMessage }}</span>
        </div>
      </div>

      <div class="col col-result">
        <div class="col-label">成/败/取</div>
        <div class="col-value">
          <span class="success">{{ progressSuccess }}</span>
          <span class="sep">/</span>
          <span class="danger">{{ progressFailed }}</span>
          <span class="sep">/</span>
          <span class="neutral">{{ progressCancelled }}</span>
        </div>
      </div>

      <div class="ops">
        <button
          class="op-btn"
          type="button"
          @click="onRefreshStatus"
          :disabled="!!busy"
          title="刷新当前导入状态"
        >
          刷新状态
        </button>

        <button
          class="op-btn"
          type="button"
          @click="onRefreshTasks"
          :disabled="!!busy || !batchId"
          title="刷新当前任务表"
        >
          刷新任务
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  batchId: { type: String, default: "" },
  batchState: { type: String, default: "" },
  progressTotal: { type: Number, default: 0 },
  progressDone: { type: Number, default: 0 },
  progressSuccess: { type: Number, default: 0 },
  progressFailed: { type: Number, default: 0 },
  progressCancelled: { type: Number, default: 0 },
  uiMessage: { type: String, default: "" },
  busy: { type: Boolean, default: false },

  onRefreshStatus: { type: Function, default: null },
  onRefreshTasks: { type: Function, default: null },
});

const progressPercent = computed(() => {
  const total = Math.max(0, Number(props.progressTotal || 0));
  const done = Math.max(0, Number(props.progressDone || 0));
  if (!total) return 0;
  return Math.max(0, Math.min(100, (done / total) * 100));
});

const progressText = computed(() => {
  const total = Math.max(0, Number(props.progressTotal || 0));
  if (!total) return "0.0%";
  return progressPercent.value.toFixed(1) + "%";
});

const batchStateText = computed(() => {
  return String(props.batchState || "").trim() || "NO-BATCH";
});

const stateTagClass = computed(() => {
  const s = String(props.batchState || "").trim();
  if (s === "running") return "tag-running";
  if (s === "queued") return "tag-queued";
  if (s === "paused") return "tag-paused";
  if (s === "failed") return "tag-failed";
  if (s === "success") return "tag-success";
  if (s === "cancelled") return "tag-cancelled";
  return "tag-idle";
});
</script>

<style scoped>
.footer-wrap {
  width: 100%;
  min-width: 0;
}

.footer-inline {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.col {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  flex-shrink: 0;
}

.col-label {
  font-size: 10px;
  color: #888;
  user-select: none;
  white-space: nowrap;
}

.col-value {
  font-size: 13px;
  font-weight: 600;
  user-select: none;
  white-space: nowrap;
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.col-progress {
  flex: 1;
  min-width: 0;
  align-items: stretch;
}

.bar {
  position: relative;
  height: 20px;
  width: 100%;
  background: linear-gradient(180deg, #1a1a1a 0%, #242424 100%);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.fill {
  height: 100%;
  background: linear-gradient(90deg, #2b4b7e 0%, #4a6fa5 50%, #5b7fb3 100%);
  transition: width 0.3s ease;
}

.bar-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #e6e6e6;
  font-weight: 600;
  user-select: none;
  pointer-events: none;
}

.subline {
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex-wrap: wrap;
}

.tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: #bbb;
  user-select: none;
  white-space: nowrap;
}

.tag-running {
  background: rgba(46, 204, 113, 0.12);
  border-color: rgba(46, 204, 113, 0.25);
  color: #7ee2b8;
}

.tag-queued {
  background: rgba(155, 183, 230, 0.10);
  border-color: rgba(155, 183, 230, 0.22);
  color: #9db7e6;
}

.tag-paused {
  background: rgba(230, 179, 92, 0.12);
  border-color: rgba(230, 179, 92, 0.25);
  color: #e6b35c;
}

.tag-failed,
.tag-success,
.tag-cancelled,
.tag-idle {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  color: #bbb;
}

.id {
  font-size: 11px;
  color: #9a9a9a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.msg {
  font-size: 11px;
  color: #aaa;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 420px;
}

.col-result {
  min-width: 70px;
}

.col-value .success {
  color: #47a69b;
}

.col-value .danger {
  color: #d97575;
}

.col-value .sep {
  color: #555;
  font-size: 11px;
}

.col-value .neutral {
  color: #aaa;
}

.ops {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.op-btn {
  height: 26px;
  padding: 0 8px;
  background: #2a2a2a;
  color: #ddd;
  border: 1px solid #444;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.op-btn:hover:not(:disabled) {
  border-color: #5b7fb3;
}

.op-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
