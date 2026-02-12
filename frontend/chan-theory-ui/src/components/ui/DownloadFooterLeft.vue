<!-- src/components/ui/DownloadFooterLeft.vue -->
<!-- ==============================
说明：盘后下载弹窗底栏左侧信息区（展示 + 少量运行辅助按钮）

本轮调整（按你的要求“极简 + 不重复”）：
- 移除：解除绑定 / 刷新状态 / 取消（终止下载）按钮
  原因：自动 SSE + watchdog + 退避轮询 已经覆盖“刷新/纠偏”；解除绑定属于反直觉操作。
- 保留并新增：左半区只放“运行辅助”：
  1) 状态明细（打开二次弹窗：排队批次/失败任务 + 导出）
  2) 续传（仅 paused）
  3) 重试失败（仅 failed）
- “终止下载”将由右半区主按钮区承载（通过 dialogActions.terminate_download）
============================== -->
<template>
  <div class="footer-wrap">
    <div class="footer-inline">
      <!-- 列1：已选标的 -->
      <div class="col col-selected">
        <div class="col-label">已选标的</div>
        <div class="col-value neutral">{{ selectedCount }} / {{ totalCount }}</div>
      </div>

      <!-- 列2：进度条 -->
      <div class="col col-progress">
        <div class="bar">
          <div class="fill" :style="{ width: progressPercent + '%' }"></div>
          <div class="bar-text">{{ done }} / {{ totalJobs }}（{{ progressText }}）</div>
        </div>

        <div class="subline">
          <span class="tag" :class="stateTagClass">{{ stateTagText }}</span>
          <span v-if="reconnecting" class="tag tag-warn">RECONNECTING</span>

          <span v-if="batchId" class="id" :title="batchId">
            {{ batchId }}
          </span>
        </div>
      </div>

      <!-- 列3：成功/失败/取消（压缩展示） -->
      <div class="col col-result">
        <div class="col-label">成/败/取</div>
        <div class="col-value">
          <span class="success">{{ succeeded }}</span>
          <span class="sep">/</span>
          <span class="danger">{{ failed }}</span>
          <span class="sep">/</span>
          <span class="neutral">{{ cancelled }}</span>
        </div>
      </div>

      <!-- 列4：持续时间 -->
      <div class="col col-time">
        <div class="col-label">时间</div>
        <div class="col-value time">{{ elapsed }}</div>
      </div>

      <!-- 按钮区：紧凑横排（左半区运行辅助） -->
      <div class="ops">
        <button
          class="op-btn"
          type="button"
          @click="onOpenDetails"
          :disabled="!!busy"
          title="查看排队批次/失败任务明细，并支持导出"
        >
          状态明细
        </button>

        <button
          class="op-btn"
          type="button"
          @click="onResume"
          :disabled="!!busy || batchState !== 'paused' || !batchId"
          title="仅 paused 允许续传"
        >
          续传
        </button>

        <button
          class="op-btn"
          type="button"
          @click="onRetryFailed"
          :disabled="!!busy || batchState !== 'failed' || !batchId"
          title="仅 failed 批次允许重试失败任务"
        >
          重试失败
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  selectedCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
  totalJobs: { type: Number, default: 0 },
  done: { type: Number, default: 0 },
  succeeded: { type: Number, default: 0 },
  failed: { type: Number, default: 0 },
  cancelled: { type: Number, default: 0 },
  elapsed: { type: String, default: "00:00:00" },

  // batch 状态（来自 batch_snapshot.state）
  batchState: { type: String, default: "" },
  batchId: { type: String, default: "" },

  // 连接状态（仅 UI）
  reconnecting: { type: Boolean, default: false },

  // 按钮忙状态（避免重复点击）
  busy: { type: Boolean, default: false },

  // 操作回调（由父组件实现）
  onOpenDetails: { type: Function, default: null },
  onResume: { type: Function, default: null },
  onRetryFailed: { type: Function, default: null },
});

const progressPercent = computed(() => {
  const total = Math.max(0, props.totalJobs);
  if (total === 0) return 0;
  const done = Math.max(0, props.done);
  return Math.max(0, Math.min(100, (done / total) * 100));
});

const progressText = computed(() => {
  const total = Math.max(0, props.totalJobs);
  if (total === 0) return "0.0%";
  return progressPercent.value.toFixed(1) + "%";
});

const stateTagText = computed(() => {
  const s = String(props.batchState || "").trim();
  return s || "NO-BATCH";
});

const stateTagClass = computed(() => {
  const s = String(props.batchState || "").trim();
  if (s === "running") return "tag-running";
  if (s === "paused") return "tag-paused";
  if (s === "stopping") return "tag-stopping";
  if (s === "queued") return "tag-queued";
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

/* 通用列样式（除进度条外） */
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

/* 列1：已选标的 */
.col-selected {
  min-width: 90px;
}

.col-value.neutral {
  color: #aaa;
}

/* 列2：进度条 */
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

.tag-paused {
  background: rgba(230, 179, 92, 0.12);
  border-color: rgba(230, 179, 92, 0.25);
  color: #e6b35c;
}

.tag-stopping {
  background: rgba(91, 127, 179, 0.12);
  border-color: rgba(91, 127, 179, 0.25);
  color: #9db7e6;
}

.tag-queued {
  background: rgba(155, 183, 230, 0.10);
  border-color: rgba(155, 183, 230, 0.22);
  color: #9db7e6;
}

.tag-failed,
.tag-success,
.tag-cancelled,
.tag-idle {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  color: #bbb;
}

.tag-warn {
  background: rgba(230, 179, 92, 0.10);
  border-color: rgba(230, 179, 92, 0.22);
  color: #e6b35c;
}

.id {
  font-size: 11px;
  color: #9a9a9a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 列3：结果（压缩宽度） */
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

/* 列4：时间 */
.col-time {
  min-width: 75px;
}

.col-value.time {
  color: #d4a574;
  font-variant-numeric: tabular-nums;
}

/* 按钮区：紧凑横排 */
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
