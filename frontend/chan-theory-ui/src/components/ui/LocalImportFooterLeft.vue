<!-- src/components/ui/LocalImportFooterLeft.vue -->
<!-- ==============================
盘后数据导入弹窗底栏左侧信息区
职责：
  - 只展示 local import 主批次状态与结果
  - 展示“当前批次运行时间”
  - 不做业务推导，不做批次切换决策
  - 运行时间按当前批次独立计时：
      * 新 batchId 出现时归零重新开始
      * 终态后停止计时
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

      <div class="col col-runtime">
        <div class="col-label">运行时间</div>
        <div class="col-value mono">{{ runtimeText }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onBeforeUnmount } from "vue";

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

  startedAt: { type: String, default: "" },
  finishedAt: { type: String, default: "" },
});

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function parseMs(x) {
  const s = asStr(x);
  if (!s) return null;
  const ms = new Date(s).getTime();
  return Number.isFinite(ms) ? ms : null;
}

function isTerminalState(state) {
  const s = asStr(state);
  return s === "success" || s === "failed" || s === "cancelled";
}

function pad2(n) {
  return String(Math.max(0, Math.floor(Number(n || 0)))).padStart(2, "0");
}

function formatDuration(ms) {
  const totalSec = Math.max(0, Math.floor(Number(ms || 0) / 1000));
  const hh = Math.floor(totalSec / 3600);
  const mm = Math.floor((totalSec % 3600) / 60);
  const ss = totalSec % 60;
  return `${pad2(hh)}:${pad2(mm)}:${pad2(ss)}`;
}

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
  return asStr(props.batchState) || "NO-BATCH";
});

const stateTagClass = computed(() => {
  const s = asStr(props.batchState);
  if (s === "running") return "tag-running";
  if (s === "queued") return "tag-queued";
  if (s === "paused") return "tag-paused";
  if (s === "failed") return "tag-failed";
  if (s === "success") return "tag-success";
  if (s === "cancelled") return "tag-cancelled";
  return "tag-idle";
});

const nowMs = ref(Date.now());
let timerId = null;

function stopTimer() {
  if (timerId != null) {
    clearInterval(timerId);
    timerId = null;
  }
}

function ensureTimerRunning() {
  if (timerId != null) return;
  timerId = setInterval(() => {
    nowMs.value = Date.now();
  }, 1000);
}

watch(
  () => [asStr(props.batchId), asStr(props.batchState)],
  ([batchId, batchState]) => {
    if (!batchId) {
      stopTimer();
      return;
    }

    if (isTerminalState(batchState)) {
      stopTimer();
      return;
    }

    ensureTimerRunning();
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  stopTimer();
});

const runtimeMs = computed(() => {
  const batchId = asStr(props.batchId);
  if (!batchId) return 0;

  const started = parseMs(props.startedAt);
  if (started == null) return 0;

  const finished = parseMs(props.finishedAt);
  const state = asStr(props.batchState);

  if (finished != null && isTerminalState(state)) {
    return Math.max(0, finished - started);
  }

  return Math.max(0, nowMs.value - started);
});

const runtimeText = computed(() => {
  if (!asStr(props.batchId)) return "00:00:00";
  return formatDuration(runtimeMs.value);
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

.col-runtime {
  min-width: 88px;
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

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
