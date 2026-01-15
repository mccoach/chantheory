<!-- src/components/ui/DataDownloadDialog.vue -->
<!-- ==============================
盘后下载弹窗（契约 v1.1 适配版）

核心变更（严格按 v1.1）：
1) 进度真相源在后端：UI 展示只读取 bulkCtl.state.activeBatch / bulkCtl.progress（computed）
2) 打开弹窗/页面重启可恢复：
   - 组件 mounted 时调用 bulkCtl.restoreFromLocalOrLatest()
   - latest 恢复时提示“可能非本设备发起”（契约 5.4）
3) 点击“数据下载”：
   - 生成队列后调用 bulkCtl.startFromQueue(...)，并把 selected_symbols 传给后端 batch 记录
4) 不再提供“失败重试”执行链路（v1.1 明确本期不提供 retryable/重试接口）
   - 因此：按钮语义始终为“开始下载”（若已 finished/running 则按状态禁用/提示）
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

            <!-- v1.1：latest 兜底提示 -->
            <div v-if="fromLatestHint" class="hint-line warn">
              当前进度为“找回入口（latest）”恢复，可能非本设备发起的 running 批次（系统无登录鉴权隔离）。
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

onMounted(async () => {
  try {
    allItems.value = listAll({ clone: true });
  } catch {
    allItems.value = [];
  }

  // v1.1：弹窗打开时尝试恢复（页面重启也可恢复）
  try {
    await bulkCtl.restoreFromLocalOrLatest();
  } catch {}
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
} = useUniverseBuilder({
  itemsRef: allItems,
  watchlistSetRef: watchSet,
});

// scope 列表：提供给 tri controller 做 external sync（快照更新）
const scopesList = computed(() => {
  const out = [];
  for (const g of selectorGroups.value || []) {
    for (const it of g.items || []) {
      out.push({ scopeKey: it.scopeKey, universeSet: it.universeSet });
    }
  }
  return out;
});

// ==============================
// 三态总控（唯一快照真相源）
// ==============================
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

  applyAll: (_scopeKey, universeSet) => {
    applyScopeAll(_scopeKey, universeSet);
  },

  applyNone: (_scopeKey, universeSet) => {
    applyScopeNone(_scopeKey, universeSet);
  },

  applySnapshot: (_scopeKey, universeSet) => {
    applyScopeSnapshot(_scopeKey, universeSet, tri.getSnapshot(_scopeKey));
  },

  buildSnapshot: (_scopeKey, universeSet) => {
    const U = universeSet instanceof Set ? universeSet : new Set();
    const S = selectedSet.value;

    const snap = new Set();
    const [small, large] = S.size <= U.size ? [S, U] : [U, S];
    for (const x of small) if (large.has(x)) snap.add(x);

    return snap;
  },
});

/**
 * external change：同步快照（规则2：非自发更新）
 */
function syncTriSnapshotsFromExternalChange(sourceScopeKey = null) {
  try {
    tri.syncSnapshotsOnExternalChange(sourceScopeKey, scopesList.value);
  } catch {}
}

// 1) watchlist 变化：scope universeSet 改变，属于 external change → 更新所有 scope 快照
watch(
  watchKeyStable,
  () => {
    syncTriSnapshotsFromExternalChange(null);
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
  syncTriSnapshotsFromExternalChange(null);
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
    syncTriSnapshotsFromExternalChange(it.scopeKey);
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

// ===== v1.1：elapsed 不再用前端 ticker 作为真相源（以 started_at 展示即可）=====
// 说明：契约要求真相源在后端；started_at 是展示字段，持续时间可以由前端用 started_at 自行计算。
// 这里保留轻量 ticker（纯展示），不参与进度闭环与 finished 判定。
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
    const b = bulkCtl.state.activeBatch.value;
    const startedAt = b?.started_at;
    if (!startedAt) {
      elapsedTime.value = "00:00:00";
      return;
    }
    const start = new Date(startedAt).getTime();
    if (!Number.isFinite(start)) {
      elapsedTime.value = "00:00:00";
      return;
    }
    elapsedTime.value = formatElapsed(Date.now() - start);
  }, 200);
}

function stopTicker() {
  if (_ticker) clearInterval(_ticker);
  _ticker = null;
}

watch(
  () => bulkCtl.running.value,
  (running) => {
    if (running) startTicker();
    else stopTicker();
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  stopTicker();
});

// ===== footer-left 数据准备（显式 props；按 v1.1 字段口径）=====
const dialogFooterLeftProps = computed(() => {
  const b = bulkCtl.state.activeBatch.value;
  const p = bulkCtl.progress.value;

  const selectedSymbols = Math.max(0, Number(b?.selected_symbols || counts.value.nTotal || 0));
  const planned = Math.max(0, Number(b?.planned_total_tasks || jobsTotal.value || 0));

  const totalJobs = Math.max(0, Number(p.total || 0)); // accepted_tasks
  const done = Math.max(0, Number(p.done || 0));
  const succeeded = Math.max(0, Number(p.success || 0));
  const failed = Math.max(0, Number(p.failed || 0));

  return {
    selectedCount: selectedSymbols,
    totalCount: totalUniverseCount.value,
    totalJobs: totalJobs > 0 ? totalJobs : planned, // 优先展示 accepted_tasks；若为 0 则展示 planned_total_tasks
    done,
    succeeded,
    failed,
    elapsed: elapsedTime.value,
  };
});

const fromLatestHint = computed(() => bulkCtl.state.fromLatestHint.value === true);

// ===== v1.1：启动批次 =====
async function startBulk() {
  const res = await bulkCtl.startFromQueue(downloadQueue.value, {
    force_fetch: false,
    priority: null,
    selected_symbols: counts.value.nTotal,
  });
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
    // v1.1：不支持 retryFailed；若当前 running 则不重复提交
    if (bulkCtl.running.value === true) return;

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

.hint-line.warn {
  color: #e6b35c;
}
</style>
