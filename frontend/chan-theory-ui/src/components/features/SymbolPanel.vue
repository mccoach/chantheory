<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\SymbolPanel.vue -->
<!-- ============================== -->
<!-- V16.0 - BREAKING: 当前标的身份模型升级为双主键（symbol + market）严格化
     变更：
     - 搜索候选 / 历史 / 自选点击，统一传完整 identity
     - vm.setSymbolIdentity({symbol, market}) 成为唯一切换入口
     - 当前标的的持久化历史也升级为 symbol + market
     - UI 层 identity 统一走 normalizeIdentity / identityKey

     Local Import：
     - 原“盘后远程下载”入口正式切换为“盘后数据导入”
     - 打开新 LocalImportDialog.vue
     - 旧远程下载主链路彻底退出引用

     本轮改动（启动重复去重）：
     - 删除 mounted 中对 wl.refresh() 的主动调用
     - watchlist 启动加载唯一链路保留在 useAppStartup -> wl.smartLoad()
-->
<template>
  <div class="symbol-row">
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

    <div class="col-middle">
      <div class="info-line-1" :title="middleTitle">
        <span class="sym-name">{{ middleName }}</span>
        <span class="sym-code">（{{ middleCode }}）</span>

        <span v-if="middleMarket" class="sym-meta-chip">|</span>
        <span v-if="middleMarket" class="sym-meta-chip">
          市场：{{ middleMarket }}
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
          上市日期：{{ middleListingDate }}
        </span>
        <span v-if="profileInfo.updatedAt" class="sym-meta-chip">|</span>
        <span v-if="profileInfo.updatedAt" class="sym-meta-chip">
          档案更新：{{ formatUpdatedAt(profileInfo.updatedAt) }}
        </span>
      </div>

      <div class="info-line-2" v-if="hasProfileInfo">
        <span v-if="profileInfo.floatShares" class="info-item">
          流通股：{{ profileInfo.floatShares }}万股（份）
        </span>
        <span v-if="profileInfo.floatValue" class="info-item">|</span>
        <span v-if="profileInfo.floatValue" class="info-item">
          流通市值：{{ profileInfo.floatValue }}亿元
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

    <div class="col-right">
      <SymbolActions :loading="vm.loading.value" />

      <div class="seg seg-download-refresh">
        <button
          class="seg-btn"
          title="盘后数据导入"
          @click="openLocalImportDialog"
          :disabled="vm.loading.value"
        >
          盘后导入
        </button>
        <button
          class="seg-btn"
          title="刷新"
          @click="onRefreshClick"
          :disabled="vm.loading.value"
        >
          行情刷新
        </button>
      </div>
    </div>
  </div>

  <div v-if="error" class="err">错误：{{ error }}</div>
</template>

<script setup>
import { inject, ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useWatchlist } from "@/composables/useWatchlist";
import { useProfileSnapshot } from "@/composables/useProfileSnapshot";

import SymbolSearch from "./symbol/SymbolSearch.vue";
import WatchlistMenu from "./symbol/WatchlistMenu.vue";
import SymbolActions from "./symbol/SymbolActions.vue";

import { formatDateTime, formatYmdInt } from "@/utils/timeFormat";
import { parseTimeValue } from "@/utils/timeParse";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function asMarket(x) {
  return asStr(x).toUpperCase();
}

function normalizeIdentity(input = {}) {
  return {
    symbol: asStr(input.symbol),
    market: asMarket(input.market),
  };
}

function identityKey(symbol, market) {
  return `${asMarket(market)}:${asStr(symbol)}`;
}

const vm = inject("marketView");
const hotkeys = inject("hotkeys", null);
const settings = useUserSettings();
const symbolIndex = useSymbolIndex();
const profileSnapshot = useProfileSnapshot();
const wl = useWatchlist();
const dialogManager = inject("dialogManager", null);
const hub = inject("viewCommandHub");

const { ready, search, findBySymbol, ensureIndexReady } = symbolIndex;

const placeholder = "输入代码/拼音首字母（例：000001 + 市场区分）";
const inputText = ref(settings.preferences.lastSymbol || vm.code.value || "");
const isInputFocused = ref(false);
const isWatchlistOpen = ref(false);
const suggestions = ref([]);
const invalidHint = ref("");
const error = ref("");

const refreshing = ref(false);

const searchRef = ref(null);
const watchlistRef = ref(null);

const lastRenderedIdentity = ref(identityKey(vm.code.value, vm.market.value));

watch(
  [() => vm.code.value, () => vm.market.value],
  ([newCode, newMarket]) => {
    lastRenderedIdentity.value = identityKey(newCode, newMarket);
  }
);

async function selectItem(item) {
  const identity = normalizeIdentity(item);
  if (!identity.symbol || !identity.market) return;

  const nextIdentity = identityKey(identity.symbol, identity.market);
  if (nextIdentity === lastRenderedIdentity.value) {
    console.log(`[SymbolPanel] 🔄 标的未变化（${nextIdentity}），跳过重载`);
    inputText.value = identity.symbol;
    invalidHint.value = "";
    suggestions.value = [];
    isInputFocused.value = false;
    return;
  }

  console.log(`[SymbolPanel] 🔄 标的变化: ${lastRenderedIdentity.value} → ${nextIdentity}`);

  inputText.value = identity.symbol;

  settings.setLastSymbolIdentity({
    symbol: identity.symbol,
    market: identity.market,
  });
  settings.addSymbolHistoryEntry({
    symbol: identity.symbol,
    market: identity.market,
  });

  vm.setSymbolIdentity({
    symbol: identity.symbol,
    market: identity.market,
  });

  invalidHint.value = "";
  suggestions.value = [];
  isInputFocused.value = false;
}

function tryCommitByInput() {
  const t = asStr(inputText.value);
  if (!t) {
    invalidHint.value = "请输入标的代码或拼音首字母";
    return;
  }

  let entry = null;

  const arr = search(t, 20);
  if (arr.length === 1) {
    entry = arr[0];
  }

  if (entry) {
    selectItem(entry);
  } else {
    invalidHint.value = "存在重码或无效标的，请从候选中明确选择";
  }
}

async function toggleStarImmediate(item) {
  try {
    const identity = normalizeIdentity(item);
    if (!identity.symbol || !identity.market) return;

    const key = identityKey(identity.symbol, identity.market);
    if (inWatchlistSet.value.has(key)) {
      await wl.removeOne({
        symbol: identity.symbol,
        market: identity.market,
      });
    } else {
      await wl.addOne({
        symbol: identity.symbol,
        market: identity.market,
      });
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
    console.log("[SymbolPanel] 🔄 强制刷新标的列表 + 档案快照...");

    const [indexRes, profileRes] = await Promise.all([
      ensureIndexReady({ mode: "force", timeoutMs: 60000 }),
      profileSnapshot.ensureReady({ timeoutMs: 60000 }),
    ]);

    if (!indexRes?.ok) {
      throw new Error(indexRes?.message || "标的列表刷新失败");
    }
    if (!profileRes?.ok) {
      throw new Error(profileRes?.message || "档案快照刷新失败");
    }

    if (vm.code?.value && vm.market?.value) {
      await vm.reload?.({ force_refresh: false, with_profile: true });
    }

    console.log("[SymbolPanel] ✅ 标的列表 + 档案快照刷新完成");
  } catch (e) {
    console.error("[SymbolPanel] ❌ 强制刷新失败", e);
    alert(`刷新失败：${e.message || "网络错误"}`);
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
    arr
      .map((it) => identityKey(it?.symbol, it?.market))
      .filter((x) => x && x !== ":")
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
    asStr(inputText.value).length === 0
);

const showSuggest = computed(
  () =>
    isInputFocused.value &&
    !isWatchlistOpen.value &&
    asStr(inputText.value).length > 0 &&
    suggestions.value.length > 0
);

function onFocus() {
  isInputFocused.value = true;
  invalidHint.value = "";
  if (asStr(inputText.value)) {
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
  const q = asStr(inputText.value);
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

const middleCode = computed(() => asStr(vm.code?.value));
const middleMarket = computed(() => asMarket(vm.market?.value));

const symbolEntry = computed(() => {
  const symbol = middleCode.value;
  const market = middleMarket.value;
  if (!symbol || !market) return null;
  return findBySymbol(symbol, market);
});

const middleName = computed(() => symbolEntry.value?.name || "");
const middleClass = computed(() => symbolEntry.value?.class || "");
const middleType = computed(() => symbolEntry.value?.type || "");
const middleListingDate = computed(() =>
  formatListingDate(symbolEntry.value?.listingDate)
);

const middleTitle = computed(() =>
  middleName.value
    ? `${middleName.value}（${middleMarket.value}:${middleCode.value}）`
    : `${middleMarket.value}:${middleCode.value}` || ""
);

const profileInfo = computed(() => {
  const pf = vm.profile?.value || null;

  if (!pf) {
    return {
      floatShares: null,
      floatValue: null,
      industry: null,
      region: null,
      concepts: [],
      updatedAt: null,
    };
  }

  return {
    floatShares: pf.float_shares ?? null,
    floatValue: pf.float_value ?? null,
    industry: pf.industry ?? null,
    region: pf.region ?? null,
    concepts: Array.isArray(pf.concepts) ? pf.concepts : [],
    updatedAt: pf.updated_at ?? null,
  };
});

const hasProfileInfo = computed(() => {
  const p = profileInfo.value;
  return !!(
    p.floatShares ||
    p.floatValue ||
    p.industry ||
    p.region ||
    p.concepts.length > 0 ||
    p.updatedAt
  );
});

function formatUpdatedAt(str) {
  if (!str) return "-";
  const dt = parseTimeValue(str);
  if (!dt) return "-";
  return formatDateTime(dt, true);
}

function formatListingDate(intVal) {
  if (!intVal) return "";
  const n = Number(intVal);
  if (!Number.isFinite(n)) return "";
  return formatYmdInt(n);
}

async function openLocalImportDialog() {
  try {
    if (!dialogManager || typeof dialogManager.open !== "function") return;

    const mod = await import("@/components/ui/LocalImportDialog.vue");

    dialogManager.open({
      title: "盘后数据导入",
      contentComponent: mod.default,
      props: {},
      footerActions: [
        {
          key: "start_import",
          label: "开始导入",
          variant: "ok",
          disabled: false,
        },
        {
          key: "cancel_import",
          label: "取消当前导入",
          disabled: false,
        },
        {
          key: "retry_import",
          label: "重试失败任务",
          disabled: false,
        },
        {
          key: "close",
          label: "关闭",
        },
      ],
    });
  } catch (e) {
    console.error("[SymbolPanel] openLocalImportDialog failed:", e);
  }
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

.col-middle {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
  user-select: none;
  overflow: hidden;
}

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

.sym-meta-chip {
  font-size: 11px;
  color: #999;
  margin-left: 8px;
  white-space: nowrap;
}

.sym-meta-chip + .sym-meta-chip {
  margin-left: 6px;
}

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

.seg-download-refresh {
  height: 36px;
}

.seg {
  display: inline-flex;
  align-items: center;
  border: 1px solid #444;
  border-radius: 10px;
  overflow: hidden;
  background: #1a1a1a;
  height: 36px;
}

.seg-btn {
  background: transparent;
  color: #ddd;
  border: none;
  padding: 8px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 14px;
  line-height: 20px;
  width: 90px;
  height: 36px;
  border-radius: 0;
}

.seg-btn + .seg-btn {
  border-left: 1px solid #444;
}

.seg-btn:hover:not(:disabled) {
  background: #2b4b7e;
  color: #fff;
}

.seg-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
