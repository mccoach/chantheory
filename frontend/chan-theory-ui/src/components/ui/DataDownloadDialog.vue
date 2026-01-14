<!-- src/components/ui/DataDownloadDialog.vue -->
<!-- ==============================
盘后下载弹窗（瘦身版）
- UI：标的列表 + 快速筛选 + 下载参数
- 业务：bulk 入队 / SSE 跟踪 / 失败重试 / CSV 导出 —— 全部下沉到 src/composables/afterHoursBulk（全局单例）

本轮改动（方案D）：
  - 删除 h() 渲染函数（defineComponent + 60行内联样式）
  - 新增 dialogFooterLeftProps（显式 props 对象）
  - 引入 DownloadFooterLeft 组件（纯展示，通过 props 驱动）
  - 保留 elapsedTime ticker（数据源）
============================== -->
<template>
  <div class="dd-wrap">
    <div class="cols">
      <div class="col table-col">
        <SymbolUniverseTable
          title="标的列表"
          :rows="tableRows"
          :isSelected="isSelected"
          :isStarred="isStarred"
          :sortKey="sortKeyForTable"
          :sortDir="sortDirForTable"
          :rowHeightPx="ROW_H"
          :approxVisibleRows="APPROX_ROWS"
          @sort="onSort"
          @toggle-select="onToggleSelect"
          @toggle-star="onToggleStar"
        />
      </div>

      <div class="col selectors-col">
        <div class="col-head">
          <div class="col-title">快速筛选</div>
        </div>

        <div class="selectors">
          <div v-for="g in selectorGroups" :key="g.groupKey" class="group">
            <div class="group-title">{{ groupTitle(g.groupKey) }}</div>

            <div v-for="it in g.items" :key="it.scopeKey" class="sel-row">
              <div class="sel-left">
                <span class="std-check">
                  <input
                    type="checkbox"
                    v-tri-state="{
                      checked: !!it.checked,
                      indeterminate: !!it.indeterminate
                    }"
                    @change="onCycleScope(it)"
                  />
                </span>
                <span class="sel-label" :title="it.label">{{ it.label }}</span>
              </div>

              <div class="sel-right">
                <span class="sel-count">{{ it.selectedCount }} / {{ it.totalCount }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="col params-col">
        <div class="col-head">
          <div class="col-title">下载参数</div>
        </div>

        <div class="params">
          <div class="block">
            <div class="block-title">频率（freq）</div>

            <div class="two-col">
              <div class="colbox">
                <div class="mini-title">日线</div>
                <label v-for="f in dayFreqs" :key="f" class="chip">
                  <input type="checkbox" :checked="selectedFreqs.has(f)" @change="toggleFreq(f)" />
                  <span>{{ freqLabel(f) }}</span>
                </label>
              </div>

              <div class="colbox">
                <div class="mini-title">分时</div>
                <label v-for="f in minuteFreqs" :key="f" class="chip">
                  <input type="checkbox" :checked="selectedFreqs.has(f)" @change="toggleFreq(f)" />
                  <span>{{ freqLabel(f) }}</span>
                </label>
              </div>
            </div>
          </div>

          <div class="block">
            <div class="block-title">复权（adjust）</div>

            <div class="two-col">
              <div class="colbox">
                <label class="chip">
                  <input
                    type="checkbox"
                    :checked="selectedAdjusts.has('none')"
                    @change="toggleAdjust('none')"
                  />
                  <span>none</span>
                </label>
              </div>

              <div class="colbox">
                <label class="chip">
                  <input
                    type="checkbox"
                    :checked="selectedAdjusts.has('qfq')"
                    @change="toggleAdjust('qfq')"
                  />
                  <span>qfq</span>
                </label>
                <label class="chip">
                  <input
                    type="checkbox"
                    :checked="selectedAdjusts.has('hfq')"
                    @change="toggleAdjust('hfq')"
                  />
                  <span>hfq</span>
                </label>
              </div>
            </div>

            <div class="hint-line">
              stock 标的固定拉取：复权因子 + 不复权K线；复权选项仅影响非 stock 标的。
              （若频率未选择，则不生成任何任务）
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from "vue";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useWatchlist } from "@/composables/useWatchlist";
import { useUniverseBuilder } from "@/composables/useUniverseBuilder";
import { createTriStateController } from "@/composables/useTriToggle";
import { formatYmdInt } from "@/utils/timeFormat";
import SymbolUniverseTable from "@/components/ui/SymbolUniverseTable.vue";
import DownloadFooterLeft from "./DownloadFooterLeft.vue";

import { useAfterHoursBulkController } from "@/composables/afterHoursBulk";

const ROW_H = 28;
const APPROX_ROWS = 17;

const dayFreqs = ["1d", "1w", "1M"];
const minuteFreqs = ["1m", "5m", "15m", "30m", "60m"];

function freqLabel(f) {
  const m = {
    "1d": "日",
    "1w": "周",
    "1M": "月",
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "60m": "60m",
  };
  return m[f] ?? String(f || "");
}

const bulkCtl = useAfterHoursBulkController();

const { listAll } = useSymbolIndex();
const wl = useWatchlist();
const allItems = ref([]);

onMounted(() => {
  try {
    allItems.value = listAll({ clone: true });
  } catch {
    allItems.value = [];
  }
});

const totalUniverseCount = computed(() => {
  const arr = Array.isArray(allItems.value) ? allItems.value : [];
  return arr.length;
});

const watchSet = computed(() => {
  const arr = Array.isArray(wl.items.value) ? wl.items.value : [];
  return new Set(arr.map((x) => String(x?.symbol || "").trim()).filter(Boolean));
});

const watchKeyStable = computed(() => Array.from(watchSet.value).sort().join("|"));

const {
  sortedItems,
  selectedSet,
  toggleSymbolSelected,
  selectorGroups,
  sortState,
  setSort,
  selectedFreqs,
  toggleFreq,
  selectedAdjusts,
  toggleAdjust,
  counts,
  selectedRowsForExport,

  applyScopeAll,
  applyScopeNone,
  applyScopeSnapshot,
  triSyncSnapshotsOnExternalChange,
  triSetSnapshotForScope,
  triGetSnapshotForScope,
} = useUniverseBuilder({
  itemsRef: allItems,
  watchlistSetRef: watchSet,
});

const scopesList = computed(() => {
  const out = [];
  for (const g of selectorGroups.value || []) {
    for (const it of g.items || []) {
      out.push({ scopeKey: it.scopeKey, universeSet: it.universeSet });
    }
  }
  return out;
});

const tri = createTriStateController({
  getUi: (_scopeKey, universeSet) => {
    const U = universeSet instanceof Set ? universeSet : new Set();
    let sel = 0;
    const S = selectedSet.value;

    const [small, large] = S.size <= U.size ? [S, U] : [U, S];
    for (const x of small) if (large.has(x)) sel += 1;

    const total = U.size;

    return {
      checked: total > 0 && sel === total,
      indeterminate: total > 0 && sel > 0 && sel < total,
      selectedCount: sel,
      totalCount: total,
    };
  },

  applyAll: (scopeKey, universeSet) => {
    triSetSnapshotForScope(scopeKey, universeSet);
    applyScopeAll(scopeKey, universeSet);
  },

  applyNone: (scopeKey, universeSet) => {
    triSetSnapshotForScope(scopeKey, universeSet);
    applyScopeNone(scopeKey, universeSet);
  },

  applySnapshot: (scopeKey, universeSet) => {
    applyScopeSnapshot(scopeKey, universeSet, triGetSnapshotForScope(scopeKey));
  },

  buildSnapshot: (scopeKey, universeSet) => {
    const U = universeSet instanceof Set ? universeSet : new Set();
    const S = selectedSet.value;

    const snap = new Set();
    const [small, large] = S.size <= U.size ? [S, U] : [U, S];
    for (const x of small) if (large.has(x)) snap.add(x);

    return snap;
  },
});

watch(
  watchKeyStable,
  () => {
    tri.syncSnapshotsOnExternalChange(null, scopesList.value);
    triSyncSnapshotsOnExternalChange(null, scopesList.value);
  },
  { flush: "post" }
);

const tableRows = computed(() => {
  const arr = Array.isArray(sortedItems.value) ? sortedItems.value : [];
  return arr.map((it) => {
    const symbol = String(it?.symbol || "").trim();
    const name = String(it?.name || "");
    const market = String(it?.market || "");
    const cls = String(it?.class || "");
    const type = String(it?.type || "");

    const listingDate = it?.listingDate ?? it?.listing_date ?? null;
    const updatedAt = String(it?.updatedAt ?? it?.updated_at ?? "");

    const listingDateText = listingDate ? formatYmdInt(listingDate) : "";

    return {
      symbol,
      name,
      market,
      class: cls,
      type,
      listingDate,
      listingDateText,
      updatedAt,
    };
  });
});

const sortKeyForTable = computed(() => String(sortState.value?.key || "symbol"));
const sortDirForTable = computed(() => String(sortState.value?.dir || "asc"));

function onSort(key) {
  setSort(key);
}

function isSelected(symbol) {
  return selectedSet.value.has(String(symbol || "").trim());
}

function isStarred(symbol) {
  return watchSet.value.has(String(symbol || "").trim());
}

function onToggleSelect(symbol) {
  toggleSymbolSelected(symbol);
  tri.syncSnapshotsOnExternalChange(null, scopesList.value);
  triSyncSnapshotsOnExternalChange(null, scopesList.value);
}

async function onToggleStar(symbol) {
  try {
    const sym = String(symbol || "").trim();
    if (!sym) return;

    if (watchSet.value.has(sym)) await wl.removeOne(sym);
    else await wl.addOne(sym);
  } catch {}
}

function onCycleScope(it) {
  try {
    tri.cycle(it.scopeKey, it.universeSet);
  } catch {}
}

function groupTitle(k) {
  const key = String(k || "");
  if (key === "watchlist") return "自选（watchlist）";
  if (key === "market") return "市场（market）";
  if (key === "board") return "板块（board）";
  if (key === "class") return "类别（class）";
  if (key === "type") return "类型（type）";
  return key;
}

// ===== 任务队列生成（保留你原先规则，不改）=====
const FREQ_ORDER = ["1d", "1w", "1M", "60m", "30m", "15m", "5m", "1m"];
const ADJUST_ORDER = ["none", "qfq", "hfq"];

function isStockItem(it) {
  return String(it?.class || "").toLowerCase() === "stock";
}

function selectedItemsInDisplayOrder() {
  const out = [];
  const arr = Array.isArray(sortedItems.value) ? sortedItems.value : [];
  const S = selectedSet.value;

  for (const it of arr) {
    const sym = String(it?.symbol || "").trim();
    if (!sym) continue;
    if (S.has(sym)) out.push(it);
  }
  return out;
}

const orderedFreqs = computed(() => {
  const sel = selectedFreqs.value instanceof Set ? selectedFreqs.value : new Set();
  return FREQ_ORDER.filter((f) => sel.has(f));
});

const orderedAdjusts = computed(() => {
  const sel = selectedAdjusts.value instanceof Set ? selectedAdjusts.value : new Set();
  return ADJUST_ORDER.filter((a) => sel.has(a));
});

const downloadQueue = computed(() => {
  const items = selectedItemsInDisplayOrder();
  const freqs = orderedFreqs.value;
  const adjs = orderedAdjusts.value;

  if (!freqs.length) return [];

  const queue = [];

  for (const it of items) {
    const symbol = String(it?.symbol || "").trim();
    if (!symbol) continue;

    const stock = isStockItem(it);

    if (stock) {
      queue.push({
        type: "current_factors",
        symbol,
        force_fetch: true,
      });

      for (const f of freqs) {
        queue.push({
          type: "current_kline",
          symbol,
          freq: f,
          adjust: "none",
          force_fetch: true,
        });
      }
    } else {
      for (const f of freqs) {
        for (const a of adjs) {
          queue.push({
            type: "current_kline",
            symbol,
            freq: f,
            adjust: a,
            force_fetch: true,
          });
        }
      }
    }
  }

  return queue;
});

const jobsTotal = computed(() => downloadQueue.value.length);

// ===== 持续时间计算（实时更新）=====
const elapsedTime = ref("00:00:00");
let _ticker = null;

function formatElapsed(ms) {
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

function startTicker() {
  stopTicker();
  _ticker = setInterval(() => {
    const p = bulkCtl.state.progress.value || {};
    const startedAt = p.started_at;
    if (!startedAt) {
      elapsedTime.value = "00:00:00";
      return;
    }
    const start = new Date(startedAt).getTime();
    const now = Date.now();
    elapsedTime.value = formatElapsed(now - start);
  }, 200);
}

function stopTicker() {
  if (_ticker) clearInterval(_ticker);
  _ticker = null;
}

watch(
  () => bulkCtl.state.running.value,
  (running) => {
    if (running) startTicker();
    else stopTicker();
  }
);

onBeforeUnmount(() => {
  stopTicker();
});

// ===== footer-left 数据准备（显式 props）=====
const dialogFooterLeftProps = computed(() => {
  const p = bulkCtl.state.progress.value || {};
  const done = Math.max(0, Number(p.done || 0));
  const total = Math.max(0, Number(jobsTotal.value || 0));
  const succeeded = Math.max(0, done - Number(p.failed || 0));
  const failed = Math.max(0, Number(p.failed || 0));

  return {
    selectedCount: counts.value.nTotal,
    totalCount: totalUniverseCount.value,
    totalJobs: total,
    done,
    succeeded,
    failed,
    elapsed: elapsedTime.value,
  };
});

async function startBulk() {
  const res = await bulkCtl.startFromQueue(downloadQueue.value, { force_fetch: false, priority: null });
  if (!res.ok) alert(res.message);
}

async function retryFailed() {
  const res = await bulkCtl.retryFailed({ force_fetch: false, priority: null });
  if (!res.ok) alert(res.message);
}

function exportList() {
  const res = bulkCtl.exportList({ rows: selectedRowsForExport.value || [], isStarredSet: watchSet.value });
  if (!res.ok) alert(res.message);
}

// ==============================
// Dialog Action Contract（纯 key）
// ==============================
const dialogActions = {
  export_list: () => exportList(),

  download_data: () => {
    if (bulkCtl.state.running.value === true) return;

    if (bulkCtl.canRetryFailed.value) {
      retryFailed();
      return;
    }

    if (jobsTotal.value <= 0) {
      alert("当前没有可执行的下载任务（请先选择标的并勾选频率/复权）");
      return;
    }

    startBulk();
  },
};

// ===== 新契约：暴露组件 + props（App.vue 会 v-bind 透传）=====
defineExpose({ 
  dialogActions, 
  dialogFooterLeft: DownloadFooterLeft,
  dialogFooterLeftProps
});
</script>

<style scoped>
.dd-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px 0;
}

.cols {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
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

.selectors-col .selectors {
  padding: 10px 12px;
  overflow: auto;
  min-height: 0;
  flex: 1;
  min-width: 150px;
}

.params-col .params {
  padding: 10px 12px;
  overflow: auto;
  min-height: 0;
  flex: 1;
  min-width: 150px;
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

.group + .group {
  margin-top: 12px;
}

.group-title {
  font-size: 12px;
  color: #bbb;
  font-weight: 700;
  margin-bottom: 8px;
  text-align: left;
}

.sel-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 1px 4px;
  border-radius: 6px;
}

.sel-row:hover {
  background: rgba(255, 255, 255, 0.04);
}

.sel-left {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.sel-label {
  font-size: 12px;
  color: #ddd;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}

.sel-right {
  font-size: 12px;
  color: #999;
  white-space: nowrap;
}

.block + .block {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.block-title {
  font-size: 12px;
  color: #bbb;
  font-weight: 700;
  margin-bottom: 8px;
  text-align: left;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
}

.colbox {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mini-title {
  font-size: 12px;
  color: #999;
  font-weight: 600;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border: 0px solid #444;
  border-radius: 999px;
  background: transparent;
  font-size: 12px;
  color: #ddd;
  user-select: none;
  width: fit-content;
}

.hint-line {
  margin-top: 8px;
  color: #999;
  font-size: 12px;
  text-align: left;
}
</style>
