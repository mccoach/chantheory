<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\SymbolPanel.vue -->
<!-- ============================== -->
<!-- V9.2 - 档案由 /api/profile/current 提供 + 第一行补充 symbol_index 元信息
     
     本版新增：
       - 在第1行“名称（代码）”之后，追加展示来自 symbol_index 的：
         market / board / class / type / listing_date
       - 这些元信息仅用于补充展示，数据源为 useSymbolIndex.findBySymbol。
       - 样式上采用类似第二行 info-line-2 的小号灰色文字，与名称/代码区分。
-->
<template>
  <div class="symbol-row">
    <!-- 左列：标的输入与自选 -->
    <div class="col-left">
      <div class="search-container">
        <SymbolSearch
          ref="searchRef"
          v-model="inputText"
          :placeholder="placeholder"
          :invalidHint="invalidHint"
          :suggestions="suggestions"
          :history="historyDisplay"
          :watchlist="inWatchlistSet"
          :show-suggestions="showSuggest"
          :show-history="showHistory"
          @focus="onFocus"
          @blur="onBlur"
          @select-symbol="selectItem"
          @toggle-star="toggleStarImmediate"
        />

        <button
          class="refresh-symbols-btn-inline"
          :class="{ refreshing: refreshing }"
          :disabled="refreshing"
          @click="forceRefreshSymbols"
          title="强制刷新标的列表"
        >
          {{ refreshing ? "⏳" : "🔄" }}
        </button>
      </div>

      <WatchlistMenu
        ref="watchlistRef"
        @select-symbol="selectItem"
        @opened="onWatchlistOpen"
        @closed="onWatchlistClose"
      />
    </div>

    <!-- 中列：标的信息 -->
    <div class="col-middle">
      <!-- 第1行：名称、代码 + 元信息（market / board / class / type / listing_date）-->
      <div class="info-line-1" :title="middleTitle">
        <span class="sym-name">{{ middleName }}</span>
        <span class="sym-code">（{{ middleCode }}）</span>

        <!-- NEW: 来自 symbol_index 的元信息（小号灰字） -->
        <span v-if="middleMarket" class="sym-meta-chip">|</span>
        <span v-if="middleMarket" class="sym-meta-chip">
          市场：{{ middleMarket }}
        </span>
        <span v-if="middleBoard" class="sym-meta-chip">|</span>
        <span v-if="middleBoard" class="sym-meta-chip">
          板块：{{ middleBoard }}
        </span>
        <span v-if="middleClass" class="sym-meta-chip">|</span>
        <span v-if="middleClass" class="sym-meta-chip">
          类别：{{ middleClass }}
        </span>
        <span v-if="middleType" class="sym-meta-chip">|</span>
        <span v-if="middleType" class="sym-meta-chip">
          类型：{{ middleType }}
        </span>
        <span v-if="middleListingDate" class="sym-meta-chip">|</span>
        <span v-if="middleListingDate" class="sym-meta-chip">
          上市：{{ middleListingDate }}
        </span>
        <span v-if="middleMarket" class="sym-meta-chip">|</span>
        <span v-if="profileInfo.updatedAt" class="sym-meta-chip">
          档案更新：{{ formatUpdatedAt(profileInfo.updatedAt) }}
        </span>
      </div>

      <!-- 第2行：档案信息（完全来自 vm.profile）-->
      <div class="info-line-2" v-if="hasProfileInfo">
        <span v-if="profileInfo.totalShares" class="info-item">
          总股本：{{ profileInfo.totalShares }}万股（份）
        </span>
        <span v-if="profileInfo.floatShares" class="info-item">|</span>
        <span v-if="profileInfo.floatShares" class="info-item">
          流通股：{{ profileInfo.floatShares }}万股（份）
        </span>
        <span v-if="profileInfo.totalValue" class="info-item">|</span>
        <span v-if="profileInfo.totalValue" class="info-item">
          总市值：{{ profileInfo.totalValue }}亿元
        </span>
        <span v-if="profileInfo.negoValue" class="info-item">|</span>
        <span v-if="profileInfo.negoValue" class="info-item">
          流通市值：{{ profileInfo.negoValue }}亿元
        </span>
        <span v-if="profileInfo.peStatic" class="info-item">|</span>
        <span v-if="profileInfo.peStatic" class="info-item">
          静态PE：{{ formatPe(profileInfo.peStatic) }}倍
        </span>
        <span v-if="profileInfo.industry" class="info-item">|</span>
        <span v-if="profileInfo.industry" class="info-item">
          行业：{{ profileInfo.industry }}
        </span>
        <span v-if="profileInfo.region" class="info-item">|</span>
        <span v-if="profileInfo.region" class="info-item">
          地区：{{ profileInfo.region }}
        </span>
        <span v-if="profileInfo.concepts.length > 0" class="info-item">|</span>
        <span v-if="profileInfo.concepts.length > 0" class="info-item">
          概念：{{ profileInfo.concepts.slice(0, 3).join("、")
          }}{{ profileInfo.concepts.length > 3 ? "..." : "" }}
        </span>
      </div>
    </div>

    <!-- 右列：操作按钮 -->
    <div class="col-right">
      <SymbolActions :loading="vm.loading.value" @refresh="onRefreshClick" />
    </div>
  </div>

  <div v-if="error" class="err">错误：{{ error }}</div>
</template>

<script setup>
import {
  inject,
  ref,
  computed,
  onMounted,
  onBeforeUnmount,
  watch,
} from "vue";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useWatchlist } from "@/composables/useWatchlist";
import { useViewCommandHub } from "@/composables/useViewCommandHub";

import SymbolSearch from "./symbol/SymbolSearch.vue";
import WatchlistMenu from "./symbol/WatchlistMenu.vue";
import SymbolActions from "./symbol/SymbolActions.vue";

import { formatDateTime, formatYmdInt } from "@/utils/timeFormat";
import { parseTimeValue } from "@/utils/timeParse";

const vm = inject("marketView");
const hotkeys = inject("hotkeys", null);
const settings = useUserSettings();
const { ready, search, findBySymbol, ensureIndexFresh } = useSymbolIndex();
const hub = useViewCommandHub();
const wl = useWatchlist();

const placeholder = "输入代码/拼音首字母（例：600519 或 gzymt）";
const inputText = ref(settings.preferences.lastSymbol || vm.code.value || "");
const isInputFocused = ref(false);
const isWatchlistOpen = ref(false);
const suggestions = ref([]);
const invalidHint = ref("");
const error = ref("");

const refreshing = ref(false);

const searchRef = ref(null);
const watchlistRef = ref(null);

const lastRenderedSymbol = ref(vm.code.value || "");

watch(
  () => vm.code.value,
  (newCode) => {
    lastRenderedSymbol.value = newCode || "";
  }
);

async function selectItem(item) {
  if (!item || !item.symbol) return;
  const sym = String(item.symbol).trim();

  if (sym === lastRenderedSymbol.value) {
    console.log(`[SymbolPanel] 🔄 标的未变化（${sym}），跳过重载`);

    inputText.value = sym;
    invalidHint.value = "";
    suggestions.value = [];
    isInputFocused.value = false;

    return;
  }

  console.log(
    `[SymbolPanel] 🔄 标的变化: ${lastRenderedSymbol.value} → ${sym}`
  );

  inputText.value = sym;
  vm.code.value = sym;               // 仅改 code，任务触发交给 useMarketView.watch(code)
  settings.setLastSymbol(sym);
  settings.addSymbolHistoryEntry(sym);

  invalidHint.value = "";
  suggestions.value = [];
  isInputFocused.value = false;
}

function tryCommitByInput() {
  const t = (inputText.value || "").trim();
  if (!t) {
    invalidHint.value = "请输入标的代码或拼音首字母";
    return;
  }
  let entry = findBySymbol(t);
  if (!entry) {
    const arr = search(t, 1);
    entry = arr[0];
  }
  if (entry) {
    selectItem(entry);
  } else {
    invalidHint.value = "无效标的，请重试";
  }
}

async function toggleStarImmediate(item) {
  try {
    const sym = String(item?.symbol || "").trim();
    if (!sym) return;
    if (inWatchlistSet.value.has(sym)) {
      await wl.removeOne(sym);
    } else {
      await wl.addOne(sym);
    }
  } catch {}
}

function onRefreshClick() {
  console.log("[SymbolPanel] 🔄 强制刷新当前标的");
  hub.execute("Refresh", {});
  vm.reload?.({ force_refresh: true, with_profile: true });
}

async function forceRefreshSymbols() {
  if (refreshing.value) return;

  refreshing.value = true;

  try {
    console.log("[SymbolPanel] 🔄 强制刷新标的列表...");

    // 使用 ensureIndexFresh(true) 触发 symbol_index 任务并读取最新快照
    await ensureIndexFresh(true);

    console.log("[SymbolPanel] ✅ 标的列表刷新完成");
  } catch (e) {
    console.error("[SymbolPanel] ❌ 强制刷新失败", e);
    alert(`标的列表刷新失败：${e.message || "网络错误"}`);
  } finally {
    refreshing.value = false;
  }
}

function registerPanelHotkeys() {
  if (!hotkeys) return;

  hotkeys.registerHandlers("panel:symbol", {
    dropdownNext: () => {},
    dropdownPrev: () => {},
    dropdownConfirm: () => {},
    dropdownClose: () => {
      isInputFocused.value = false;
      searchRef.value?.blur();
    },
  });
}

onMounted(() => {
  registerPanelHotkeys();
  wl.refresh().catch(() => {});
  document.addEventListener("click", onDocClick);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick);

  if (hotkeys) {
    try {
      hotkeys.unregisterHandlers("panel:symbol");
    } catch {}
  }
});

const inWatchlistSet = computed(() => {
  const arr = Array.isArray(wl.items.value) ? wl.items.value : [];
  return new Set(
    arr.map((it) => String((it && it.symbol) || "").trim()).filter(Boolean)
  );
});

const historyDisplay = computed(() => {
  const list = settings.getSymbolHistoryList();
  return (Array.isArray(list) ? list : []).slice(0, 50);
});

const showHistory = computed(
  () =>
    isInputFocused.value &&
    !isWatchlistOpen.value &&
    inputText.value.trim().length === 0
);

const showSuggest = computed(
  () =>
    isInputFocused.value &&
    !isWatchlistOpen.value &&
    inputText.value.trim().length > 0 &&
    suggestions.value.length > 0
);

function onFocus() {
  isInputFocused.value = true;
  invalidHint.value = "";
  if (inputText.value?.trim()) {
    updateSuggestions();
  }
  hotkeys?.pushScope("panel:symbol");
}

function onBlur() {
  setTimeout(() => {
    if (!isWatchlistOpen.value) {
      isInputFocused.value = false;
      tryCommitByInput();
      hotkeys?.popScope("panel:symbol");
    }
  }, 150);
}

watch(inputText, () => {
  invalidHint.value = "";
  updateSuggestions();
});

function updateSuggestions() {
  const q = inputText.value?.trim() || "";
  if (!q || !ready.value) {
    suggestions.value = [];
    return;
  }
  suggestions.value = search(q, 20);
}

function onWatchlistOpen() {
  isWatchlistOpen.value = true;
  isInputFocused.value = false;
}

function onWatchlistClose() {
  isWatchlistOpen.value = false;
}

function onDocClick(e) {
  const target = e.target;
  if (searchRef.value && !searchRef.value.$el.contains(target)) {
    isInputFocused.value = false;
  }
  if (watchlistRef.value && !watchlistRef.value.$el.contains(target)) {
    watchlistRef.value.close(true);
  }
}

// ===== 中间栏信息（基础：symbol_index）=====
const middleCode = computed(() => (vm.code?.value || "").trim());

const symbolEntry = computed(() => {
  const sym = middleCode.value;
  if (!sym) return null;
  return findBySymbol(sym);
});

const middleName = computed(() => symbolEntry.value?.name || "");

const middleMarket = computed(() => symbolEntry.value?.market || "");
const middleBoard = computed(() => symbolEntry.value?.board || "");
const middleClass = computed(() => symbolEntry.value?.class || "");
const middleType = computed(() => symbolEntry.value?.type || "");
const middleListingDate = computed(() =>
  formatListingDate(symbolEntry.value?.listingDate)
);

const middleTitle = computed(() =>
  middleName.value
    ? `${middleName.value}（${middleCode.value}）`
    : middleCode.value || ""
);

// ===== 档案信息（仅 vm.profile，来自 /api/profile/current）=====
const profileInfo = computed(() => {
  const pf = vm.profile?.value || null;

  if (!pf) {
    return {
      totalShares: null,
      floatShares: null,
      totalValue: null,
      negoValue: null,
      peStatic: null,
      industry: null,
      region: null,
      concepts: [],
      updatedAt: null,
    };
  }

  return {
    totalShares: pf.total_shares ?? null,
    floatShares: pf.float_shares ?? null,
    totalValue: pf.total_value ?? null,
    negoValue: pf.nego_value ?? null,
    peStatic: pf.pe_static ?? null,
    industry: pf.industry ?? null,
    region: pf.region ?? null,
    concepts: Array.isArray(pf.concepts) ? pf.concepts : [],
    updatedAt: pf.updated_at ?? null,
  };
});

// ===== 判断是否显示档案行 =====
const hasProfileInfo = computed(() => {
  const p = profileInfo.value;
  return !!(
    p.totalShares ||
    p.floatShares ||
    p.totalValue ||
    p.negoValue ||
    p.peStatic ||
    p.industry ||
    p.region ||
    p.concepts.length > 0 ||
    p.updatedAt
  );
});

// ===== 格式化工具 =====
function formatPe(pe) {
  const num = Number(pe);
  if (!Number.isFinite(num) || num <= 0) return "-";
  return num.toFixed(2);
}

function formatUpdatedAt(str) {
  if (!str) return "-";
  const dt = parseTimeValue(str);
  if (!dt) return "-";
  // 显示到分钟即可
  return formatDateTime(dt, true);
}

function formatListingDate(intVal) {
  if (!intVal) return "";
  const n = Number(intVal);
  if (!Number.isFinite(n)) return "";
  return formatYmdInt(n);
}
</script>

<style scoped>
.symbol-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  column-gap: 12px;
}
.col-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.search-container {
  position: relative;
  display: inline-block;
}

/* 中间栏：多行布局 */
.col-middle {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
  user-select: none;
  overflow: hidden;
}

/* 第1行：名称和代码 + 元信息 */
.info-line-1 {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.sym-name {
  font-weight: 600;
  font-size: 14px;
  color: #ddd;
}

.sym-code {
  font-size: 12px;
  color: #bbb;
}

/* NEW: 第一行追加元信息的样式（参考第二行的 info-item） */
.sym-meta-chip {
  font-size: 11px;
  color: #999;
  margin-left: 8px;
  white-space: nowrap;
}
.sym-meta-chip + .sym-meta-chip {
  margin-left: 6px;
}

/* 第2行：档案信息 */
.info-line-2 {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.info-item {
  white-space: nowrap;
}

.col-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.err {
  margin-top: 8px;
  color: #e74c3c;
  text-align: left;
}

.refresh-symbols-btn-inline {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);

  width: 20px;
  height: 20px;
  padding: 0;

  background: transparent;
  border: none;
  outline: none;

  font-size: 14px;
  line-height: 1;

  cursor: pointer;
  transition: all 0.2s ease;

  z-index: 10;

  display: flex;
  align-items: center;
  justify-content: center;

  color: #888;
  opacity: 0.6;
}

.refresh-symbols-btn-inline:hover:not(:disabled) {
  opacity: 1;
  color: #646cff;
  transform: translateY(-50%) scale(1.15);
}

.refresh-symbols-btn-inline:active:not(:disabled) {
  transform: translateY(-50%) scale(0.95);
}

.refresh-symbols-btn-inline:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.refresh-symbols-btn-inline.refreshing {
  animation: spin-pulse 1.5s ease-in-out infinite;
}

@keyframes spin-pulse {
  0% {
    opacity: 0.6;
    transform: translateY(-50%) rotate(0deg);
  }
  50% {
    opacity: 0.3;
    transform: translateY(-50%) rotate(180deg);
  }
  100% {
    opacity: 0.6;
    transform: translateY(-50%) rotate(360deg);
  }
}
</style>