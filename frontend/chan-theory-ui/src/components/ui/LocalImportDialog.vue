<!-- src/components/ui/LocalImportDialog.vue -->
<!-- ==============================
盘后数据导入弹窗（Local Import）

本轮目标：
- 候选列表只来自 /api/local-import/candidates
- 主状态只来自 /api/local-import/status 和 SSE local_import.status
- 任务表只按 display_batch.batch_id 加载
- 入口语义正式切换为“盘后数据导入”
- 保留原三栏布局骨架风格，但内部数据流全部切换为 import 模型

本轮修正（双主键彻底落实）：
- 候选表选择集严格使用 market:symbol|freq
- 表格 row key 严格使用 market:symbol|freq
- SymbolUniverseTable 的选择事件改为传整行 row，不再传单 symbol
- 候选查找 / toggle / 选中判断全部消灭单主键
============================== -->
<template>
  <div class="li-wrap">
    <div class="cols">
      <div class="col table-col">
        <SymbolUniverseTable
          title="导入候选"
          :rows="tableRows"
          :isSelected="isSelected"
          :isStarred="isStarred"
          :sortKey="sortKeyForTable"
          :sortDir="sortDirForTable"
          :rowHeightPx="ROW_H"
          :approxVisibleRows="APPROX_ROWS"
          :rowKeyBuilder="buildRowKey"
          @sort="onSort"
          @toggle-select="onToggleSelect"
          @toggle-star="onToggleStarNoop"
        />
      </div>

      <div class="col status-col">
        <div class="col-head">
          <div class="col-title">当前批次</div>
        </div>

        <div class="status-body">
          <div v-if="displayBatch" class="batch-card">
            <div class="line"><span class="k">批次ID：</span><span class="v mono">{{ displayBatch.batch_id }}</span></div>
            <div class="line"><span class="k">状态：</span><span class="v">{{ displayBatch.state }}</span></div>
            <div class="line"><span class="k">创建时间：</span><span class="v">{{ displayBatch.created_at || "-" }}</span></div>
            <div class="line"><span class="k">开始时间：</span><span class="v">{{ displayBatch.started_at || "-" }}</span></div>
            <div class="line"><span class="k">结束时间：</span><span class="v">{{ displayBatch.finished_at || "-" }}</span></div>
            <div class="line"><span class="k">总任务：</span><span class="v">{{ displayBatch.progress_total }}</span></div>
            <div class="line"><span class="k">已完成：</span><span class="v">{{ displayBatch.progress_done }}</span></div>
            <div class="line"><span class="k">成功：</span><span class="v success">{{ displayBatch.progress_success }}</span></div>
            <div class="line"><span class="k">失败：</span><span class="v danger">{{ displayBatch.progress_failed }}</span></div>
            <div class="line"><span class="k">取消：</span><span class="v neutral">{{ displayBatch.progress_cancelled }}</span></div>
            <div class="line"><span class="k">可取消：</span><span class="v">{{ displayBatch.cancelable ? "是" : "否" }}</span></div>
            <div class="line"><span class="k">可重试：</span><span class="v">{{ displayBatch.retryable ? "是" : "否" }}</span></div>
          </div>

          <div v-else class="empty-card">
            当前无可展示批次
          </div>

          <div class="queued-box">
            <div class="mini-title">排队批次</div>

            <div v-if="queuedBatches.length === 0" class="empty-mini">
              当前无排队批次
            </div>

            <div v-else class="queued-list">
              <div
                v-for="qb in queuedBatches"
                :key="qb.batch_id"
                class="queued-item"
              >
                <div class="q1">#{{ qb.queue_position }} {{ qb.batch_id }}</div>
                <div class="q2">{{ qb.created_at || "-" }}</div>
                <div class="q3">任务数：{{ qb.item_count }}</div>
              </div>
            </div>
          </div>

          <div v-if="uiMessage" class="ui-msg">
            {{ uiMessage }}
          </div>
        </div>
      </div>

      <div class="col tasks-col">
        <div class="col-head">
          <div class="col-title">任务列表</div>
        </div>

        <div class="tasks-body">
          <div class="tasks-head" v-if="tasksBatchId">
            当前批次：<span class="mono">{{ tasksBatchId }}</span>
          </div>

          <div v-if="!tasks.length" class="empty-card">
            当前无任务列表
          </div>

          <div v-else class="task-list">
            <div
              v-for="task in tasks"
              :key="taskKey(task)"
              class="task-item"
            >
              <div class="t-main">
                <span class="mono">{{ task.market }}:{{ task.symbol }}</span>
                <span class="freq">{{ task.freq }}</span>
                <span class="name">{{ task.name }}</span>
              </div>
              <div class="t-sub">
                <span>{{ task.class }}</span>
                <span>|</span>
                <span>{{ task.type }}</span>
                <span>|</span>
                <span :class="taskStateClass(task.state)">{{ task.state }}</span>
                <span>|</span>
                <span>attempts={{ task.attempts }}</span>
              </div>
              <div class="t-err" v-if="task.error_code || task.error_message">
                {{ task.error_code || "-" }} {{ task.error_message || "" }}
              </div>
              <div class="t-time">
                {{ task.updated_at || "-" }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="hint-line">
      当前阶段仅支持通达信本地 <span class="mono">.day</span> 文件导入，
      固定导入为 <span class="mono">freq=1d</span>、
      <span class="mono">adjust=none</span>。
      选择的是导入任务，不是文件路径；文件候选完全以后端扫描结果为准。
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from "vue";
import SymbolUniverseTable from "@/components/ui/SymbolUniverseTable.vue";
import LocalImportFooterLeft from "@/components/ui/LocalImportFooterLeft.vue";
import { useLocalImportController } from "@/composables/localImport";

const ROW_H = 28;
const APPROX_ROWS = 17;

const ctl = useLocalImportController();

const selectedSet = ref(new Set());
const sortState = ref({ key: "symbol", dir: "asc" });

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function selectionKey(item) {
  const it = item && typeof item === "object" ? item : {};
  return `${asStr(it.market).toUpperCase()}:${asStr(it.symbol)}|${asStr(it.freq)}`;
}

onMounted(async () => {
  await ctl.initialize();
});

onBeforeUnmount(() => {
  ctl.dispose?.();
});

const candidates = computed(() => ctl.state.candidates.value || []);
const displayBatch = computed(() => ctl.state.displayBatch.value || null);
const queuedBatches = computed(() => ctl.state.queuedBatches.value || []);
const uiMessage = computed(() => ctl.state.uiMessage.value || "");
const tasksBatchId = computed(() => ctl.state.tasksBatchId.value || "");
const tasks = computed(() => ctl.state.tasks.value || []);

const sortedCandidates = computed(() => {
  const list = Array.isArray(candidates.value) ? candidates.value.slice() : [];
  const { key, dir } = sortState.value || {};
  const d = dir === "desc" ? -1 : 1;
  const sortKey = asStr(key) || "symbol";

  list.sort((a, b) => {
    const va = String(a?.[sortKey] ?? "");
    const vb = String(b?.[sortKey] ?? "");
    if (va === vb) {
      const ka = selectionKey(a);
      const kb = selectionKey(b);
      return ka.localeCompare(kb);
    }
    return va.localeCompare(vb) * d;
  });

  return list;
});

const tableRows = computed(() => {
  return sortedCandidates.value.map((it) => ({
    symbol: it.symbol,
    name: it.name,
    market: it.market,
    class: it.class,
    type: it.type,
    listingDate: null,
    listingDateText: it.freq,
    updatedAt: "",
    _freq: it.freq,
    _rowKey: selectionKey(it),
  }));
});

const sortKeyForTable = computed(() => {
  const k = asStr(sortState.value?.key || "symbol");
  return k;
});

const sortDirForTable = computed(() => {
  return asStr(sortState.value?.dir || "asc");
});

function onSort(key) {
  const k = asStr(key || "symbol");
  const cur = sortState.value || { key: "symbol", dir: "asc" };
  const dir = cur.key === k ? (cur.dir === "asc" ? "desc" : "asc") : "asc";
  sortState.value = { key: k, dir };
}

function buildRowKey(row) {
  return asStr(row?._rowKey);
}

function isSelected(row) {
  const key = selectionKey({
    market: row?.market,
    symbol: row?.symbol,
    freq: row?._freq || row?.freq || row?.listingDateText,
  });
  return selectedSet.value.has(key);
}

// 当前不在导入候选表里处理 watchlist，自选星标仅占位为 false
function isStarred(_row) {
  return false;
}

function onToggleSelect(row) {
  const key = selectionKey({
    market: row?.market,
    symbol: row?.symbol,
    freq: row?._freq || row?.freq || row?.listingDateText,
  });

  if (!key) return;

  const next = new Set(selectedSet.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  selectedSet.value = next;
}

function onToggleStarNoop() {
  // Local Import 候选不走 watchlist 语义，本轮故意留空
}

function selectedItems() {
  const out = [];
  for (const row of sortedCandidates.value) {
    const key = selectionKey(row);
    if (selectedSet.value.has(key)) {
      out.push({
        market: row.market,
        symbol: row.symbol,
        freq: row.freq,
      });
    }
  }
  return out;
}

function taskKey(task) {
  return `${asStr(task.market).toUpperCase()}:${asStr(task.symbol)}|${asStr(task.freq)}`;
}

function taskStateClass(state) {
  const s = asStr(state);
  if (s === "success") return "ok";
  if (s === "failed") return "bad";
  if (s === "cancelled") return "muted";
  if (s === "running") return "run";
  if (s === "queued") return "queue";
  return "";
}

async function handleStartImport() {
  const items = selectedItems();
  if (!items.length) {
    alert("请先勾选要导入的候选项");
    return;
  }

  const r = await ctl.startImport({ items });
  if (!r.ok) {
    alert(r.message || "启动导入失败");
  }
}

async function handleCancelImport() {
  if (!ctl.cancelable.value) {
    alert("当前批次不可取消");
    return;
  }

  const r = await ctl.cancelImport();
  if (!r.ok) {
    alert(r.message || "取消导入失败");
  }
}

async function handleRetryImport() {
  if (!ctl.retryable.value) {
    alert("当前批次不可重试");
    return;
  }

  const r = await ctl.retryImport();
  if (!r.ok) {
    alert(r.message || "重试失败任务失败");
  }
}

async function refreshStatus() {
  const r = await ctl.loadStatus({ syncTasks: true });
  if (!r.ok) {
    alert(r.message || "刷新状态失败");
  }
}

async function refreshTasks() {
  const bid = asStr(tasksBatchId.value || displayBatch.value?.batch_id);
  if (!bid) return;

  const r = await ctl.loadTasks({ batch_id: bid });
  if (!r.ok) {
    alert(r.message || "刷新任务失败");
  }
}

const dialogFooterLeftProps = computed(() => ({
  batchId: displayBatch.value?.batch_id || "",
  batchState: displayBatch.value?.state || "",
  progressTotal: Number(displayBatch.value?.progress_total || 0),
  progressDone: Number(displayBatch.value?.progress_done || 0),
  progressSuccess: Number(displayBatch.value?.progress_success || 0),
  progressFailed: Number(displayBatch.value?.progress_failed || 0),
  progressCancelled: Number(displayBatch.value?.progress_cancelled || 0),
  uiMessage: uiMessage.value || "",
  busy:
    ctl.state.loadingStatus.value ||
    ctl.state.loadingTasks.value ||
    ctl.state.submittingStart.value ||
    ctl.state.submittingCancel.value ||
    ctl.state.submittingRetry.value,
  onRefreshStatus: refreshStatus,
  onRefreshTasks: refreshTasks,
}));

const dialogActions = {
  start_import: async () => {
    await handleStartImport();
  },
  cancel_import: async () => {
    await handleCancelImport();
  },
  retry_import: async () => {
    await handleRetryImport();
  },
};

defineExpose({
  dialogActions,
  dialogFooterLeft: LocalImportFooterLeft,
  dialogFooterLeftProps,
});
</script>

<style scoped>
.li-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px 0;
}

.cols {
  display: grid;
  grid-template-columns: 2fr 1fr 1.2fr;
  gap: 6px;
  align-items: start;
}

.col {
  border: 1px solid #333;
  border-radius: 8px;
  background: #141414;
  display: flex;
  flex-direction: column;
  min-height: 545px;
}

.table-col {
  width: 640px;
  min-width: 640px;
}

.status-col .status-body,
.tasks-col .tasks-body {
  padding: 10px 12px;
  overflow: auto;
  min-height: 0;
  flex: 1;
  min-width: 180px;
}

.col-head {
  padding: 8px 10px;
  border-bottom: 1px solid #2a2a2a;
}

.col-title {
  font-size: 13px;
  font-weight: 700;
  color: #ddd;
}

.batch-card,
.empty-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  padding: 10px;
}

.empty-card {
  color: #999;
  font-size: 12px;
  text-align: center;
}

.line {
  display: flex;
  gap: 6px;
  align-items: flex-start;
  font-size: 12px;
  color: #ddd;
  line-height: 1.6;
}

.k {
  color: #999;
  min-width: 70px;
  flex-shrink: 0;
}

.v {
  color: #ddd;
  word-break: break-all;
}

.v.success {
  color: #47a69b;
}

.v.danger {
  color: #d97575;
}

.v.neutral {
  color: #aaa;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.queued-box {
  margin-top: 12px;
}

.mini-title {
  font-size: 12px;
  color: #bbb;
  font-weight: 700;
  margin-bottom: 8px;
  text-align: left;
}

.empty-mini {
  color: #999;
  font-size: 12px;
}

.queued-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.queued-item {
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.02);
}

.q1 {
  font-size: 12px;
  color: #ddd;
}

.q2,
.q3 {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.ui-msg {
  margin-top: 12px;
  color: #bbb;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.tasks-head {
  font-size: 12px;
  color: #bbb;
  margin-bottom: 8px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-item {
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 6px;
  padding: 8px;
  background: rgba(255,255,255,0.02);
}

.t-main {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #ddd;
  font-size: 12px;
  flex-wrap: wrap;
}

.freq {
  color: #9db7e6;
}

.name {
  color: #bbb;
}

.t-sub {
  margin-top: 4px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 11px;
  color: #999;
}

.t-err {
  margin-top: 4px;
  font-size: 11px;
  color: #d97575;
  word-break: break-word;
}

.t-time {
  margin-top: 4px;
  font-size: 11px;
  color: #888;
}

.ok {
  color: #47a69b;
}

.bad {
  color: #d97575;
}

.muted {
  color: #aaa;
}

.run {
  color: #7ee2b8;
}

.queue {
  color: #9db7e6;
}

.hint-line {
  color: #999;
  font-size: 12px;
  text-align: left;
  line-height: 1.6;
}
</style>
