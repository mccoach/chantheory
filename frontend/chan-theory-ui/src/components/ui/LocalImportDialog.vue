<!-- src/components/ui/LocalImportDialog.vue -->
<template>
  <div class="li-wrap">
    <div class="cols">
      <div class="col table-col">
        <div class="table-head-inline">
          <div class="table-head-left-group">
            <div class="table-head-left">导入候选</div>

            <div
              class="path-inline"
              :title="importRootDirDisplayTitle"
            >
              <span class="path-label">盘后数据源文件根目录：</span>
              <span class="path-value">
                {{ importRootDirDisplayText }}
              </span>
            </div>

            <button
              class="mini-btn"
              type="button"
              :disabled="settingDirBusy"
              @click="handleSetImportRootDir"
              title="设置盘后数据源文件根目录"
            >
              {{ settingDirBusy ? "设置中..." : "设置目录" }}
            </button>

            <div
              v-if="dirFeedbackText"
              class="dir-feedback"
              :class="{ err: dirFeedbackIsError }"
              :title="dirFeedbackText"
            >
              {{ dirFeedbackText }}
            </div>
          </div>

          <div class="table-head-right">
            <button
              class="mini-btn"
              type="button"
              :disabled="ctl.state.refreshingCandidates.value || settingDirBusy"
              @click="handleRefreshCandidates"
              :title="ctl.state.refreshingCandidates.value ? '正在刷新候选...' : '重新扫描本地文件并刷新候选'"
            >
              {{ ctl.state.refreshingCandidates.value ? "刷新中..." : "刷新候选" }}
            </button>
          </div>
        </div>

        <div v-if="!ctl.state.candidatesReady.value" class="not-ready-box">
          {{ candidatesDisplayMessage }}
        </div>

        <SymbolUniverseTable
          v-else
          title=""
          :rows="tableRows"
          :columns="tableColumns"
          :isSelected="isSelected"
          :isStarred="isStarred"
          :sortKey="sortState.key"
          :sortDir="sortState.dir"
          :rowHeightPx="ROW_H"
          :approxVisibleRows="APPROX_ROWS"
          :rowKeyBuilder="buildRowKey"
          @sort="onSort"
          @toggle-select="onToggleSelect"
          @toggle-star="onToggleStarNoop"
        />
      </div>

      <div class="col quick-col">
        <div class="col-head">
          <div class="col-title">快速选择</div>
        </div>

        <LocalImportQuickSelect
          :allScopeKey="ALL_SCOPE_KEY"
          :emptyUi="EMPTY_UI"
          :scopeUiMap="scopeUiMap"
          :marketScopeItems="marketScopeItems"
          :classScopeItems="classScopeItems"
          :freqScopeItems="freqScopeItems"
          :stockTypeScopeItems="stockTypeScopeItems"
          :indexTypeScopeItems="indexTypeScopeItems"
          :fundTypeScopeItems="fundTypeScopeItems"
          :scopeCountText="scopeCountText"
          :uiMessage="uiMessage"
          @toggle-scope="onScopeToggle"
        />
      </div>
    </div>

    <div class="hint-line">
      当前支持通达信本地
      <span class="mono">.day</span>、
      <span class="mono">.lc1</span>、
      <span class="mono">.lc5</span>
      文件导入，对应周期分别为
      <span class="mono">1d</span>、
      <span class="mono">1m</span>、
      <span class="mono">5m</span>；
      固定导入为 <span class="mono">adjust=none</span>。
      选择的是导入任务项，不是文件路径；同一标的不同周期会分别占用独立导入项，文件候选完全以后端当前唯一候选结果为准。
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onBeforeUnmount, inject, watch } from "vue";
import SymbolUniverseTable from "@/components/ui/SymbolUniverseTable.vue";
import LocalImportFooterLeft from "@/components/ui/LocalImportFooterLeft.vue";
import LocalImportQuickSelect from "@/components/ui/localImport/LocalImportQuickSelect.vue";
import { useLocalImportController } from "@/composables/localImport";
import { useLocalImportSelection } from "@/composables/localImport/useLocalImportSelection";

const ROW_H = 28;
const APPROX_ROWS = 17;

const ctl = useLocalImportController();
const dialogManager = inject("dialogManager", null);

const {
  ALL_SCOPE_KEY,
  EMPTY_UI,

  selectedSet,
  lastSubmittedSelectionSet,
  sortState,

  candidateRows,
  sortedCandidates,

  scopeUiMap,
  marketScopeItems,
  classScopeItems,
  freqScopeItems,
  stockTypeScopeItems,
  indexTypeScopeItems,
  fundTypeScopeItems,

  cloneSet,
  setEquals,
  scopeCountText,
  onScopeToggle,
  isSelected,
  onToggleSelect,
  selectedItems,
} = useLocalImportSelection({
  candidatesRef: computed(() => ctl.state.candidates.value || []),
});

const dirFeedbackText = ref("");
const dirFeedbackIsError = ref(false);

const settingDirBusy = computed(() => {
  return (
    ctl.state.importRootDirLoading.value ||
    ctl.state.importRootDirBrowsing.value ||
    ctl.state.importRootDirSaving.value
  );
});

const importRootDirDisplayText = computed(() => {
  if (ctl.state.importRootDirLoaded.value !== true) {
    return "读取中...";
  }

  const dir = String(ctl.state.importRootDir.value || "").trim();
  return dir || "未设置";
});

const importRootDirDisplayTitle = computed(() => {
  if (ctl.state.importRootDirLoaded.value !== true) {
    return "读取中...";
  }
  return String(ctl.state.importRootDir.value || "").trim() || "未设置";
});

const candidatesDisplayMessage = computed(() => {
  return ctl.state.candidatesDisplayMessage.value || "候选尚未就绪，请刷新后等待完成。";
});

const tableColumns = [
  { key: "check", label: "", sortable: true, min: 32, max: 90, default: 30, align: "center" },
  { key: "star", label: "自选", sortable: true, min: 40, max: 80, default: 48, align: "center" },
  { key: "symbol", label: "代码", sortable: true, min: 70, max: 140, default: 68, align: "center" },
  { key: "name", label: "名称", sortable: true, min: 120, max: 360, default: 128, align: "center" },
  { key: "market", label: "市场", sortable: true, min: 60, max: 120, default: 56, align: "center" },
  { key: "classText", label: "类别", sortable: true, min: 70, max: 160, default: 60, align: "center", field: "classText" },
  { key: "type", label: "类型", sortable: true, min: 90, max: 220, default: 110, align: "center" },
  { key: "freq", label: "周期", sortable: true, min: 70, max: 120, default: 60, align: "center", field: "freq" },
  { key: "fileTime", label: "文件时间", sortable: true, min: 150, max: 260, default: 160, align: "center", field: "fileTime", titleField: "fileTime" },
  { key: "updatedAt", label: "更新时间", sortable: true, min: 140, max: 260, default: 160, align: "center", field: "updatedAt", titleField: "updatedAt" },
];

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function setDirFeedback(text, isError = false) {
  dirFeedbackText.value = asStr(text);
  dirFeedbackIsError.value = !!isError;
}

const tableRows = computed(() => sortedCandidates.value.map((row) => ({ ...row })));
const uiMessage = computed(() => ctl.state.uiMessage.value || "");

function isStarred(_row) {
  return false;
}

function onSort(key) {
  const k = asStr(key || "symbol");
  const cur = sortState.value || { key: "symbol", dir: "asc" };
  const dir = cur.key === k ? (cur.dir === "asc" ? "desc" : "asc") : "asc";
  sortState.value = { key: k, dir };
}

function buildRowKey(row) {
  return asStr(row?._rowKey);
}

function onToggleStarNoop() {
  // 导入候选表暂保留“自选”列占位
}

async function handleSetImportRootDir() {
  if (settingDirBusy.value) return;

  setDirFeedback("");

  const browseResp = await ctl.browseSettingsDir();
  if (browseResp?.ok !== true) {
    setDirFeedback(browseResp?.message || "用户取消选择", true);
    return;
  }

  const selectedDir = asStr(browseResp?.selected_dir);
  const currentDir = asStr(ctl.state.importRootDir.value);

  if (!selectedDir) {
    setDirFeedback("后端未返回有效目录", true);
    return;
  }

  if (selectedDir === currentDir) {
    setDirFeedback("目录未改变", false);
    return;
  }

  const saveResp = await ctl.saveSettingsDir(selectedDir);
  if (saveResp?.ok !== true) {
    setDirFeedback(saveResp?.message || "目录设置失败", true);
    return;
  }

  setDirFeedback(
    saveResp?.message || "源目录已变更，原候选已失效，请重新刷新。",
    false
  );
}

async function handleStartImport() {
  const items = selectedItems();
  if (!items.length) {
    alert("请先勾选要导入的候选项");
    return;
  }

  const last = lastSubmittedSelectionSet.value;
  if (last instanceof Set && setEquals(selectedSet.value, last)) {
    alert("当前批次已提交过，请勿重复提交");
    return;
  }

  const r = await ctl.startImport({ items });
  if (!r.ok) {
    alert(r.message || "启动导入失败");
    return;
  }

  lastSubmittedSelectionSet.value = cloneSet(selectedSet.value);
}

async function handleCancelImport() {
  if (!ctl.cancelable.value) {
    alert("当前批次不可停止");
    return;
  }

  const r = await ctl.cancelImport();
  if (!r.ok) {
    alert(r.message || "停止导入失败");
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

async function handleRefreshCandidates() {
  const r = await ctl.refreshCandidates();
  if (!r.ok) {
    alert(r.message || "刷新候选失败");
    return;
  }

  // 若弹窗当前开着，且刷新成功使 snapshotValid=true，则立即触发一次显示
  const dialog = dialogManager?.activeDialog?.value;
  if (isLocalImportDialogOpen(dialog) && ctl.state.snapshotValid.value === true) {
    await ctl.loadCandidates();
  }
}

function isLocalImportDialogOpen(dialog) {
  const title = String(dialog?.title || "").trim();
  return title === "盘后数据导入";
}

// 唯一判定：弹窗打开 + snapshotValid
watch(
  () => ({
    open: isLocalImportDialogOpen(dialogManager?.activeDialog?.value),
    valid: ctl.state.snapshotValid.value,
  }),
  async (next, prev) => {
    const wasReady = !!(prev?.open && prev?.valid);
    const isReady = !!(next?.open && next?.valid);

    if (wasReady && !isReady) {
      ctl.clearCandidates();
      return;
    }

    if (!wasReady && isReady) {
      await ctl.loadCandidates();
    }
  },
  { immediate: true, deep: false }
);

const dialogFooterLeftProps = computed(() => ({
  batchId: ctl.state.displayBatch.value?.batch_id || "",
  batchState: ctl.state.displayBatch.value?.state || "",
  progressTotal: Number(ctl.state.displayBatch.value?.progress_total || 0),
  progressDone: Number(ctl.state.displayBatch.value?.progress_done || 0),
  progressSuccess: Number(ctl.state.displayBatch.value?.progress_success || 0),
  progressFailed: Number(ctl.state.displayBatch.value?.progress_failed || 0),
  progressCancelled: Number(ctl.state.displayBatch.value?.progress_cancelled || 0),
  uiMessage: uiMessage.value || "",
  busy:
    ctl.state.loadingStatus.value ||
    ctl.state.loadingCandidates.value ||
    ctl.state.refreshingCandidates.value ||
    ctl.state.submittingStart.value ||
    ctl.state.submittingCancel.value ||
    ctl.state.submittingRetry.value,
  startedAt: ctl.state.displayBatch.value?.started_at || "",
  finishedAt: ctl.state.displayBatch.value?.finished_at || "",
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

onBeforeUnmount(() => {
  ctl.clearCandidates();
});

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
  grid-template-columns: 760px 340px;
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
  width: 760px;
  min-width: 760px;
}

.quick-col {
  width: 340px;
  min-width: 340px;
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

.table-head-inline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid #2a2a2a;
  gap: 10px;
}

.table-head-left-group {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.table-head-left {
  font-size: 13px;
  font-weight: 700;
  color: #ddd;
  flex: 0 0 auto;
}

.table-head-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}

.path-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  max-width: 360px;
  color: #bbb;
  font-size: 12px;
  flex: 0 1 auto;
}

.path-label {
  flex: 0 0 auto;
  color: #999;
}

.path-value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #ddd;
}

.dir-feedback {
  min-width: 0;
  color: #8fd19e;
  font-size: 12px;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1 1 auto;
}

.dir-feedback.err {
  color: #e67e22;
}

.mini-btn {
  height: 26px;
  padding: 0 10px;
  background: #2a2a2a;
  color: #ddd;
  border: 1px solid #444;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  line-height: 24px;
}

.mini-btn:hover:not(:disabled) {
  border-color: #5b7fb3;
}

.mini-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.not-ready-box {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #bbb;
  font-size: 13px;
  padding: 20px;
  text-align: center;
  min-height: 463px;
}

.hint-line {
  color: #999;
  font-size: 12px;
  text-align: left;
  line-height: 1.6;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
