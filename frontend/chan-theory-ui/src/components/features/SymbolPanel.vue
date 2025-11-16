<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\SymbolPanel.vue -->
<!-- ============================== -->
<!-- V7.0 - 显示档案信息 -->
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
      <!-- 第1行：名称和代码 -->
      <div class="info-line-1" :title="middleTitle">
        <span class="sym-name">{{ middleName }}</span>
        <span class="sym-code">（{{ middleCode }}）</span>
      </div>

      <!-- 第2行：档案信息（单行）-->
      <div class="info-line-2" v-if="hasProfileInfo">
        <span v-if="profileInfo.totalShares" class="info-item">
          总股本：{{ formatShares(profileInfo.totalShares) }}
        </span>
        <span v-if="profileInfo.floatShares" class="info-item">
          流通：{{ formatShares(profileInfo.floatShares) }}
        </span>
        <span v-if="profileInfo.listingDate" class="info-item">
          上市：{{ formatDate(profileInfo.listingDate) }}
        </span>
        <span v-if="profileInfo.industry" class="info-item">
          行业：{{ profileInfo.industry }}
        </span>
        <span v-if="profileInfo.region" class="info-item">
          地区：{{ profileInfo.region }}
        </span>
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
import { inject, ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useWatchlist } from "@/composables/useWatchlist";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useEventStream } from "@/composables/useEventStream";
import { api } from "@/api/client";

import SymbolSearch from "./symbol/SymbolSearch.vue";
import WatchlistMenu from "./symbol/WatchlistMenu.vue";
import SymbolActions from "./symbol/SymbolActions.vue";

const vm = inject("marketView");
const hotkeys = inject("hotkeys", null);
const settings = useUserSettings();
const { ready, search, findBySymbol } = useSymbolIndex();
const hub = useViewCommandHub();
const wl = useWatchlist();
const eventStream = useEventStream();

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
  vm.code.value = sym;
  settings.setLastSymbol(sym);
  settings.addSymbolHistoryEntry(sym);

  invalidHint.value = "";
  suggestions.value = [];
  isInputFocused.value = false;

  vm.reload({ force_refresh: false });
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
  vm.reload?.({ force_refresh: true });
}

async function forceRefreshSymbols() {
  if (refreshing.value) return;

  refreshing.value = true;

  try {
    console.log("[SymbolPanel] 🔄 强制刷新标的列表...");

    const { data } = await api.post("/api/symbols/refresh-force", null, {
      timeout: 60000,
    });

    console.log("[SymbolPanel] ✅ 强制刷新触发成功", data);

    await new Promise((r) => setTimeout(r, 800));
  } catch (e) {
    console.error("[SymbolPanel] ❌ 强制刷新失败", e);
    alert(`标的列表刷新失败：${e.message || "网络错误"}`);
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

  eventStream.subscribe("symbol_index_ready", () => {
    if (refreshing.value) {
      refreshing.value = false;
    }
  });
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

// ===== 中间栏信息（基础）=====
const middleCode = computed(() => (vm.code?.value || "").trim());

const middleName = computed(() => {
  const sym = middleCode.value;
  const entry = findBySymbol(sym);
  return entry?.name || "";
});

const middleTitle = computed(() =>
  middleName.value
    ? `${middleName.value}（${middleCode.value}）`
    : middleCode.value || ""
);

// ===== 新增：档案信息 =====
const profileInfo = computed(() => {
  const sym = middleCode.value;
  const entry = findBySymbol(sym);

  if (!entry) {
    return {
      totalShares: null,
      floatShares: null,
      listingDate: null,
      industry: null,
      region: null,
      concepts: [],
    };
  }

  return {
    totalShares: entry.totalShares,
    floatShares: entry.floatShares,
    listingDate: entry.listingDate,
    industry: entry.industry,
    region: entry.region,
    concepts: entry.concepts || [],
  };
});

// ===== 新增：判断是否显示档案行 =====
const hasProfileInfo = computed(() => {
  return !!(
    profileInfo.value.totalShares ||
    profileInfo.value.floatShares ||
    profileInfo.value.listingDate ||
    profileInfo.value.industry ||
    profileInfo.value.region ||
    profileInfo.value.concepts.length > 0
  );
});

// ===== 格式化工具 =====
function formatShares(shares) {
  if (!shares) return "-";

  const num = Number(shares);

  if (!Number.isFinite(num) || num <= 0) return "-";

  if (num >= 1e8) {
    return `${(num / 1e8).toFixed(2)}亿`;
  } else if (num >= 1e4) {
    return `${(num / 1e4).toFixed(2)}万`;
  } else {
    return `${num.toFixed(0)}`;
  }
}

function formatDate(dateInt) {
  if (!dateInt) return "-";

  const str = String(dateInt);
  if (str.length !== 8) return "-";

  return `${str.slice(0, 4)}-${str.slice(4, 6)}-${str.slice(6, 8)}`;
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

/* ===== 核心修改：中间栏改为多行布局 ===== */
.col-middle {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
  user-select: none;
  overflow: hidden;
}

/* 第1行：名称和代码（保持原样式）*/
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

/* 第2行：股本信息/行业/地区/概念 */
.info-line-2 {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;  /* ← 新增：超长时省略 */
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
