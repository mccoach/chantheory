<!-- src/components/ui/DataDownloadDialog.vue -->
<!-- ==============================
盘后下载弹窗（契约 v2.1.2-FINAL+ 对齐版）

按你的要求重构（极简/去冗余/压缩高度）：
1) 移除右侧“运行控制”竖排区块；运行辅助按钮全部放到底栏左半区（DownloadFooterLeft）
2) 排队明细/失败明细改为二次弹窗（组件内轻量浮层），使用 Tabs（压缩高度）
3) 移除“解除绑定/刷新状态/重新开始”常驻按钮
4) “终止下载”动作提供为 dialogActions.terminate_download，供外层放到底栏右半区主按钮区
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

          <!-- 三选一提示（仅在用户点击“数据下载”且存在 active 时出现） -->
          <div v-if="submitChooserVisible" class="block chooser">
            <div class="chooser-title">检测到当前存在活动批次，请选择提交策略：</div>

            <div class="chooser-body">
              <label class="radio">
                <input type="radio" value="enqueue" v-model="submitPolicy" />
                <span>enqueue（默认）：新批次排队，不影响当前运行</span>
              </label>

              <label class="radio">
                <input type="radio" value="replace" v-model="submitPolicy" />
                <span>replace：将当前批次置为 stopping，新批次通常 queued</span>
              </label>

              <label class="radio">
                <input type="radio" value="abort" v-model="submitPolicy" />
                <span>abort：不提交（取消本次操作）</span>
              </label>
            </div>

            <div class="chooser-actions">
              <button class="ctl-btn" type="button" @click="confirmSubmitPolicy" :disabled="uiBusy">
                确认
              </button>
              <button class="ctl-btn" type="button" @click="cancelSubmitPolicy" :disabled="uiBusy">
                取消
              </button>
            </div>

            <div v-if="lastSubmitInfo" class="hint-line">
              {{ lastSubmitInfo }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 二次弹窗：状态明细（Tabs：排队批次 / 失败任务） -->
    <div v-if="detailsVisible" class="overlay">
      <div class="overlay-mask" @click="closeDetails"></div>

      <div class="overlay-card" role="dialog" aria-modal="true">
        <div class="ov-head">
          <div class="ov-title">状态明细</div>
          <button class="ov-close" type="button" @click="closeDetails" :disabled="detailsBusy">×</button>
        </div>

        <div class="ov-tabs">
          <button
            class="tab"
            :class="{ active: detailsTab === 'queue' }"
            type="button"
            @click="detailsTab = 'queue'"
            :disabled="detailsBusy"
          >
            排队批次（{{ queuedList.length }}）
          </button>

          <button
            class="tab"
            :class="{ active: detailsTab === 'fail' }"
            type="button"
            @click="detailsTab = 'fail'"
            :disabled="detailsBusy"
          >
            失败任务（{{ failuresTotal }}）
          </button>
        </div>

        <div class="ov-body">
          <!-- TAB: queued_batches -->
          <div v-if="detailsTab === 'queue'" class="pane">
            <div class="pane-head">
              <div class="pane-hint">来源：/bulk/status/active（后端 FIFO 真相源）</div>
              <button class="mini-btn" type="button" @click="refreshActive" :disabled="detailsBusy">
                刷新
              </button>
            </div>

            <div v-if="queuedList.length === 0" class="empty">
              当前无排队批次。
            </div>

            <div v-else class="grid">
              <div class="grid-head">
                <div class="c pos">#</div>
                <div class="c id">batch_id</div>
                <div class="c time">started_at</div>
                <div class="c prog">进度</div>
              </div>

              <div v-for="qb in queuedList" :key="qb.batch_id" class="grid-row">
                <div class="c pos">#{{ qb.queue_position }}</div>
                <div class="c id" :title="qb.batch_id">{{ qb.batch_id }}</div>
                <div class="c time" :title="qb.started_at || ''">{{ qb.started_at || "-" }}</div>
                <div class="c prog">{{ qb.progress?.done ?? 0 }} / {{ qb.progress?.total ?? 0 }}</div>
              </div>
            </div>
          </div>

          <!-- TAB: failures -->
          <div v-else class="pane">
            <div class="pane-head">
              <div class="pane-hint">接口：/bulk/failures（仅诊断/导出，不参与进度真相源）</div>

              <button class="mini-btn" type="button" @click="refreshFailures" :disabled="detailsBusy">
                刷新
              </button>

              <button
                class="mini-btn"
                type="button"
                @click="exportFailuresPage"
                :disabled="detailsBusy || failuresItems.length === 0"
                title="导出当前页"
              >
                导出本页
              </button>

              <button
                class="mini-btn"
                type="button"
                @click="exportFailuresAll"
                :disabled="detailsBusy || !hasAnyBatchId"
                title="自动分页拉取全部失败任务并导出"
              >
                导出全部
              </button>
            </div>

            <div class="meta">
              <span>batch: {{ failuresBatchId || "-" }}</span>
              <span>total_failed: {{ failuresTotal }}</span>
              <span>offset: {{ failuresOffset }}</span>
              <span>limit: {{ failuresLimit }}</span>
            </div>

            <div v-if="failuresError" class="warn">
              {{ failuresError }}
            </div>

            <div v-if="failuresItems.length === 0" class="empty">
              当前页无失败条目。
            </div>

            <div v-else class="grid fail-grid">
              <div class="grid-head">
                <div class="c key">client_task_key</div>
                <div class="c sym">symbol</div>
                <div class="c tf">type</div>
                <div class="c fa">freq/adjust</div>
                <div class="c att">attempts</div>
                <div class="c code">error_code</div>
                <div class="c msg">error_message</div>
                <div class="c time">updated_at</div>
              </div>

              <div v-for="it in failuresItems" :key="it.client_task_key" class="grid-row">
                <div class="c key" :title="it.client_task_key">{{ it.client_task_key }}</div>
                <div class="c sym" :title="it.symbol">{{ it.symbol }}</div>
                <div class="c tf" :title="it.type">{{ it.type }}</div>
                <div class="c fa">{{ it.freq ?? "-" }}/{{ it.adjust ?? "-" }}</div>
                <div class="c att">{{ it.attempts ?? 0 }}</div>
                <div class="c code" :title="it.last_error_code || ''">{{ it.last_error_code || "-" }}</div>
                <div class="c msg" :title="it.last_error_message || ''">{{ it.last_error_message || "-" }}</div>
                <div class="c time" :title="it.updated_at || ''">{{ it.updated_at || "-" }}</div>
              </div>
            </div>

            <div class="pager">
              <button class="mini-btn" type="button" @click="prevFailuresPage" :disabled="detailsBusy || failuresOffset <= 0">
                上一页
              </button>
              <button class="mini-btn" type="button" @click="nextFailuresPage" :disabled="detailsBusy || !canNextFailures">
                下一页
              </button>
            </div>
          </div>
        </div>

        <div class="ov-foot">
          <button class="ctl-btn" type="button" @click="closeDetails" :disabled="detailsBusy">关闭</button>
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
import { buildTimestampForFilename, toCsvText, downloadTextFile } from "@/utils/csvExport";

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

const uiBusy = ref(false);

// 三选一（默认 enqueue）
const submitChooserVisible = ref(false);
const submitPolicy = ref("enqueue");
const lastSubmitInfo = ref("");
const _pendingSubmit = ref(null);

// 二次弹窗：状态明细
const detailsVisible = ref(false);
const detailsTab = ref("queue"); // 'queue' | 'fail'
const detailsBusy = ref(false);

// failures 分页与导出状态（仅在明细弹窗里用）
const failuresBusy = ref(false);
const failuresOffset = ref(0);
const failuresLimit = ref(200);
const failuresError = ref("");

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function safeInt(n, d = 0) {
  const x = Number(n);
  return Number.isFinite(x) ? Math.floor(x) : d;
}

onMounted(async () => {
  try {
    allItems.value = listAll({ clone: true });
  } catch {
    allItems.value = [];
  }

  try {
    await bulkCtl.restoreFromActive();
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

const scopesList = computed(() => {
  const out = [];
  for (const g of selectorGroups.value || []) {
    for (const it of g.items || []) {
      out.push({ scopeKey: it.scopeKey, universeSet: it.universeSet });
    }
  }
  return out;
});

// 三态总控
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

  applyAll: (_scopeKey, universeSet) => applyScopeAll(_scopeKey, universeSet),
  applyNone: (_scopeKey, universeSet) => applyScopeNone(_scopeKey, universeSet),

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

function syncTriSnapshotsFromExternalChange(sourceScopeKey = null) {
  try {
    tri.syncSnapshotsOnExternalChange(sourceScopeKey, scopesList.value);
  } catch {}
}

watch(
  watchKeyStable,
  () => syncTriSnapshotsFromExternalChange(null),
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

// ===== 任务队列生成（保持原规则）=====
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
      // CHANGED: 取消强制 force_fetch（不传该字段）
      queue.push({ type: "current_factors", symbol });

      for (const f of freqs) {
        // CHANGED: 取消强制 force_fetch（不传该字段）
        queue.push({ type: "current_kline", symbol, freq: f, adjust: "none" });
      }
    } else {
      for (const f of freqs) {
        for (const a of adjs) {
          // CHANGED: 取消强制 force_fetch（不传该字段）
          queue.push({ type: "current_kline", symbol, freq: f, adjust: a });
        }
      }
    }
  }

  return queue;
});

const jobsTotal = computed(() => downloadQueue.value.length);

// ===== active/queued 快照辅助 =====
const activeBatch = computed(() => bulkCtl.state.activeBatch.value);
const activeBatchId = computed(() => String(activeBatch.value?.batch_id || ""));
const activeState = computed(() => String(activeBatch.value?.state || ""));
const isTerminalActive = computed(() => {
  const s = activeState.value;
  return s === "failed" || s === "success" || s === "cancelled";
});

const queuedList = computed(() => {
  const arr = Array.isArray(bulkCtl.state.queuedBatches.value) ? bulkCtl.state.queuedBatches.value : [];
  return arr;
});

const hasAnyBatchId = computed(() => {
  const b = bulkCtl.state.activeBatch.value;
  const bid =
    asStr(b?.batch_id) ||
    asStr(bulkCtl.state.lastBatchId?.value) ||
    asStr(localStorage.getItem("chan_after_hours_last_batch_id_v1"));
  return !!bid;
});

// ===== elapsed：纯展示（累加计时版）=====
const elapsedMs = ref(0);
const elapsedTime = computed(() => formatElapsed(elapsedMs.value));

let _ticker = null;
let _lastTickAtMs = 0;

function formatElapsed(ms) {
  const totalSec = Math.floor(Math.max(0, Number(ms || 0)) / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

function shouldTickByState(st) {
  const s = String(st || "");
  return s === "running" || s === "stopping";
}

function stopTicker() {
  if (_ticker) clearInterval(_ticker);
  _ticker = null;
  _lastTickAtMs = 0;
}

function startTicker() {
  if (_ticker) return;

  _lastTickAtMs = Date.now();
  _ticker = setInterval(() => {
    const now = Date.now();
    const delta = now - _lastTickAtMs;
    _lastTickAtMs = now;

    if (delta > 0 && delta < 60_000) {
      elapsedMs.value += delta;
    }
  }, 200);
}

// 新任务归零：以 batch_id 作为唯一判定（最稳、最简）
watch(
  () => activeBatchId.value,
  (newId, oldId) => {
    const n = String(newId || "");
    const o = String(oldId || "");

    if (n && n !== o) {
      elapsedMs.value = 0;
      stopTicker();
    }
  }
);

// 按状态启停：暂停/终态冻结；running/stopping 累加
watch(
  () => activeState.value,
  (st) => {
    if (shouldTickByState(st)) startTicker();
    else stopTicker();
  },
  { immediate: true }
);

onBeforeUnmount(() => stopTicker());

// ===== footer-left props（左半区：状态明细/续传/重试失败）=====
const dialogFooterLeftProps = computed(() => {
  const b = activeBatch.value;
  const p = bulkCtl.progress.value;

  const selectedSymbols = Math.max(0, Number(b?.selected_symbols || counts.value.nTotal || 0));
  const planned = Math.max(0, Number(b?.planned_total_tasks || jobsTotal.value || 0));

  const totalJobs = Math.max(0, Number(p.total || 0));
  const done = Math.max(0, Number(p.done || 0));
  const succeeded = Math.max(0, Number(p.success || 0));
  const failed = Math.max(0, Number(p.failed || 0));
  const cancelled = Math.max(0, Number(p.cancelled || 0));

  const batchId = String(b?.batch_id || "");

  return {
    selectedCount: selectedSymbols,
    totalCount: totalUniverseCount.value,
    totalJobs: totalJobs > 0 ? totalJobs : planned,
    done,
    succeeded,
    failed,
    cancelled,
    elapsed: elapsedTime.value,

    batchState: activeState.value,
    batchId,

    reconnecting: !!bulkCtl.state.ui.value?.reconnecting,
    busy: uiBusy.value,

    onOpenDetails: () => openDetails(),
    onResume: () => doResume(),
    onRetryFailed: () => doRetryFailed(),
  };
});

// ===== 运行辅助动作（不再提供“刷新/解除绑定”常驻按钮）=====
function openDetails() {
  detailsTab.value = "queue";
  detailsVisible.value = true;

  // 打开即刷新一次 failures 的第一页（让用户一进来就能看到数据）
  // 失败明细接口具备“不存在/隔离 -> 空列表”语义，不会泄露
  refreshFailures();
}

function closeDetails() {
  if (detailsBusy.value) return;
  detailsVisible.value = false;
}

async function refreshActive() {
  detailsBusy.value = true;
  try {
    await bulkCtl.restoreFromActive();
  } finally {
    detailsBusy.value = false;
  }
}

async function doResume() {
  const bid = activeBatchId.value;
  if (!bid) return;
  if (activeState.value !== "paused") return;

  uiBusy.value = true;
  try {
    const r = await bulkCtl.resume({ batch_id: bid });
    if (!r.ok && r.message) alert(r.message);
  } finally {
    uiBusy.value = false;
  }
}

async function doRetryFailed() {
  const bid = activeBatchId.value;
  if (!bid) return;
  if (activeState.value !== "failed") return;

  uiBusy.value = true;
  try {
    const r = await bulkCtl.retryFailed({ batch_id: bid });
    if (!r.ok && r.message) alert(r.message);
  } finally {
    uiBusy.value = false;
  }
}

// ===== 三选一提交（数据下载）=====
async function startBulkWithPolicy(policy) {
  const res = await bulkCtl.startFromQueue(downloadQueue.value, {
    when_active_exists: policy,
    // CHANGED: 不再传 force_fetch（避免“强制字段”残留，交给后端默认策略）
    priority: null,
    selected_symbols: counts.value.nTotal,
  });

  if (!res.ok) {
    if (res.message) alert(res.message);
    lastSubmitInfo.value = res.message || "提交失败";
    return;
  }

  const nb = res.batch;
  const ab = res.active_batch;

  const nbId = nb?.batch_id ? String(nb.batch_id) : "";
  const nbState = nb?.state ? String(nb.state) : "";
  const qp = res.queue_position != null ? String(res.queue_position) : "";

  const abId = ab?.batch_id ? String(ab.batch_id) : "";
  const abState = ab?.state ? String(ab.state) : "";

  let msg = "提交成功。";
  if (abId) msg += ` active_batch=${abId}(${abState})`;
  if (nbId) msg += ` new_batch=${nbId}(${nbState})`;
  if (nbState === "queued" && qp) msg += ` queue_position=${qp}`;

  lastSubmitInfo.value = msg;
}

function openSubmitChooser(pendingFn) {
  _pendingSubmit.value = pendingFn;
  submitPolicy.value = "enqueue";
  submitChooserVisible.value = true;
  lastSubmitInfo.value = "";
}

function cancelSubmitPolicy() {
  submitChooserVisible.value = false;
  _pendingSubmit.value = null;
}

async function confirmSubmitPolicy() {
  if (uiBusy.value) return;

  const pol = String(submitPolicy.value || "enqueue");

  if (pol === "abort") {
    submitChooserVisible.value = false;
    _pendingSubmit.value = null;
    lastSubmitInfo.value = "已取消提交（abort）。";
    return;
  }

  submitChooserVisible.value = false;

  const fn = _pendingSubmit.value;
  _pendingSubmit.value = null;

  if (typeof fn === "function") {
    await fn(pol);
  }
}

async function startBulkEntry() {
  if (uiBusy.value) return;

  if (jobsTotal.value <= 0) {
    alert("当前没有可执行的下载任务（请先选择标的并勾选频率/复权）");
    return;
  }

  const st = activeState.value;
  if (st === "running" || st === "paused" || st === "stopping") {
    openSubmitChooser(async (pol) => {
      uiBusy.value = true;
      try {
        await startBulkWithPolicy(pol);
      } finally {
        uiBusy.value = false;
      }
    });
    return;
  }

  uiBusy.value = true;
  try {
    await startBulkWithPolicy("enqueue");
  } finally {
    uiBusy.value = false;
  }
}

// ===== 终止下载（cancel）作为右半区主按钮动作 =====
async function terminateDownload() {
  const bid = activeBatchId.value;
  if (!bid) {
    alert("当前没有可终止的批次");
    return;
  }

  if (isTerminalActive.value) {
    alert("当前批次已结束，无需终止");
    return;
  }

  uiBusy.value = true;
  try {
    const r = await bulkCtl.cancel({ batch_id: bid });
    if (!r.ok && r.message) alert(r.message);
  } finally {
    uiBusy.value = false;
  }
}

// ===== 导出列表（标的清单）=====
function exportList() {
  const res = bulkCtl.exportList({ rows: selectedRowsForExport.value || [], isStarredSet: watchSet.value });
  if (!res.ok) alert(res.message);
}

// ===== failures：读取 controller state + 分页/导出 =====
const failuresState = computed(() => bulkCtl.state.failures.value || {});
const failuresItems = computed(() => {
  const items = failuresState.value?.items;
  return Array.isArray(items) ? items : [];
});
const failuresTotal = computed(() => safeInt(failuresState.value?.total_failed, 0));
const failuresBatchId = computed(() => asStr(failuresState.value?.batch_id));
const canNextFailures = computed(() => {
  const total = failuresTotal.value;
  const off = safeInt(failuresOffset.value, 0);
  const lim = safeInt(failuresLimit.value, 200);
  return off + lim < total;
});

async function loadFailuresPage({ offset, limit }) {
  failuresError.value = "";
  failuresBusy.value = true;
  detailsBusy.value = true;
  try {
    const r = await bulkCtl.loadFailures({ offset, limit });
    if (!r.ok) failuresError.value = r.message || "加载失败明细失败";
  } catch (e) {
    failuresError.value = e?.message || "加载失败明细失败";
  } finally {
    failuresBusy.value = false;
    detailsBusy.value = false;
  }
}

async function refreshFailures() {
  failuresOffset.value = 0;
  await loadFailuresPage({ offset: failuresOffset.value, limit: failuresLimit.value });
}

async function prevFailuresPage() {
  const lim = safeInt(failuresLimit.value, 200);
  failuresOffset.value = Math.max(0, safeInt(failuresOffset.value, 0) - lim);
  await loadFailuresPage({ offset: failuresOffset.value, limit: lim });
}

async function nextFailuresPage() {
  if (!canNextFailures.value) return;
  const lim = safeInt(failuresLimit.value, 200);
  failuresOffset.value = safeInt(failuresOffset.value, 0) + lim;
  await loadFailuresPage({ offset: failuresOffset.value, limit: lim });
}

function buildFailuresCsvRows(items) {
  const arr = Array.isArray(items) ? items : [];
  return arr.map((it) => [
    asStr(it?.client_task_key),
    asStr(it?.type),
    asStr(it?.scope),
    asStr(it?.symbol),
    it?.freq == null ? "" : asStr(it?.freq),
    it?.adjust == null ? "" : asStr(it?.adjust),
    String(it?.attempts ?? 0),
    asStr(it?.last_error_code),
    asStr(it?.last_error_message),
    asStr(it?.updated_at),
  ]);
}

function exportFailuresPage() {
  const items = failuresItems.value;
  if (!items.length) return;

  const bid = failuresBatchId.value || activeBatchId.value || "UNKNOWN_BATCH";
  const stamp = buildTimestampForFilename(new Date());

  const header = [
    "client_task_key",
    "type",
    "scope",
    "symbol",
    "freq",
    "adjust",
    "attempts",
    "last_error_code",
    "last_error_message",
    "updated_at",
  ];

  const csv = toCsvText({ header, rows: buildFailuresCsvRows(items) });

  downloadTextFile({
    filename: `after_hours_failures_${bid}_page_${failuresOffset.value}_${stamp}.csv`,
    text: csv,
  });
}

async function exportFailuresAll() {
  if (failuresBusy.value) return;

  failuresError.value = "";
  failuresBusy.value = true;
  detailsBusy.value = true;

  try {
    const maxLimit = 1000;
    const lim = Math.min(maxLimit, Math.max(1, safeInt(failuresLimit.value, 200)));

    await loadFailuresPage({ offset: 0, limit: lim });

    const total = failuresTotal.value;
    const bid = failuresBatchId.value || activeBatchId.value || "UNKNOWN_BATCH";

    const all = [];
    all.push(...failuresItems.value);

    let off = lim;
    while (off < total) {
      await loadFailuresPage({ offset: off, limit: lim });
      const page = failuresItems.value;
      if (!page.length) break;
      all.push(...page);
      off += lim;
    }

    // 导出完成后，把 UI 页码恢复到当前 offset
    const userOff = Math.max(0, safeInt(failuresOffset.value, 0));
    await loadFailuresPage({ offset: userOff, limit: lim });

    const stamp = buildTimestampForFilename(new Date());

    const header = [
      "client_task_key",
      "type",
      "scope",
      "symbol",
      "freq",
      "adjust",
      "attempts",
      "last_error_code",
      "last_error_message",
      "updated_at",
    ];

    const csv = toCsvText({ header, rows: buildFailuresCsvRows(all) });

    downloadTextFile({
      filename: `after_hours_failures_${bid}_ALL_${stamp}.csv`,
      text: csv,
    });
  } catch (e) {
    failuresError.value = e?.message || "导出全部失败清单失败";
  } finally {
    failuresBusy.value = false;
    detailsBusy.value = false;
  }
}

// ==============================
// Dialog Action Contract（纯 key）
// ==============================
const dialogActions = {
  export_list: () => exportList(),

  download_data: () => {
    startBulkEntry();
  },

  // NEW: 供外层 footerActions 放到右半区按钮组（你要求“终止下载”与主按钮并排）
  terminate_download: () => {
    terminateDownload();
  },
};

defineExpose({
  dialogActions,
  dialogFooterLeft: DownloadFooterLeft,
  dialogFooterLeftProps,
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

.chooser {
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}

.chooser-title {
  font-size: 12px;
  color: #ddd;
  font-weight: 700;
  text-align: left;
  margin-bottom: 8px;
}

.chooser-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.radio {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #ccc;
}

.chooser-actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}

.ctl-btn {
  height: 28px;
  padding: 0 10px;
  background: #2a2a2a;
  color: #ddd;
  border: 1px solid #444;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.ctl-btn:hover:not(:disabled) {
  border-color: #5b7fb3;
}

.ctl-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* ===== 二次弹窗（轻量 overlay） ===== */
.overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
}

.overlay-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
}

.overlay-card {
  position: absolute;
  left: 50%;
  top: 50%;
  width: min(1200px, calc(100vw - 60px));
  height: min(620px, calc(100vh - 80px));
  transform: translate(-50%, -50%);
  background: #141414;
  border: 1px solid #333;
  border-radius: 10px;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ov-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.ov-title {
  font-size: 13px;
  font-weight: 800;
  color: #ddd;
}

.ov-close {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #2a2a2a;
  border: 1px solid #444;
  color: #ddd;
  cursor: pointer;
  padding: 0;
}

.ov-tabs {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.tab {
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid #444;
  background: #222;
  color: #ccc;
  cursor: pointer;
  font-size: 12px;
}

.tab.active {
  background: #2b4b7e;
  border-color: #4a6fa5;
  color: #fff;
}

.ov-body {
  flex: 1;
  min-height: 0;
  padding: 10px 12px;
  overflow: auto;
}

.ov-foot {
  padding: 10px 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.pane-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.pane-hint {
  font-size: 12px;
  color: #999;
}

.mini-btn {
  height: 26px;
  padding: 0 8px;
  background: #2a2a2a;
  color: #ddd;
  border: 1px solid #444;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.mini-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.meta {
  margin: 6px 0 8px;
  font-size: 12px;
  color: #999;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.warn {
  margin: 6px 0;
  font-size: 12px;
  color: #e6b35c;
}

.empty {
  padding: 10px 0;
  color: #999;
  font-size: 12px;
}

.grid {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  overflow: hidden;
}

.grid-head,
.grid-row {
  display: grid;
  grid-template-columns: 60px 1fr 170px 110px;
  gap: 8px;
  align-items: center;
  padding: 6px 8px;
}

.grid-head {
  background: rgba(255, 255, 255, 0.04);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 11px;
  color: #aaa;
  font-weight: 800;
}

.grid-row {
  font-size: 12px;
  color: #ddd;
}

.grid-row:nth-child(even) {
  background: rgba(255, 255, 255, 0.02);
}

.c {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.c.pos {
  color: #9db7e6;
  font-weight: 800;
}

.c.prog {
  text-align: right;
  color: #bbb;
}

.fail-grid .grid-head,
.fail-grid .grid-row {
  grid-template-columns: 240px 70px 90px 90px 60px 120px 1fr 160px;
}

.pager {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}
</style>
