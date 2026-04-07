<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\SymbolPanel.vue -->
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
          @click="refreshSymbolIndexAndProfile"
          title="刷新标的列表与档案快照"
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

      <div class="seg seg-top-actions">
        <div class="seg-item" ref="foundationRootRef">
          <button
            class="seg-btn"
            title="基础数据刷新"
            @click="toggleFoundationMenu"
          >
            基础数据
          </button>

          <div v-if="foundationMenuOpen" class="foundation-menu">
            <div class="foundation-head">基础数据任务</div>

            <div class="foundation-actions">
              <button class="mini-btn" type="button" :disabled="foundationBusyAll" @click="runAllFoundation">
                刷新全部
              </button>
            </div>

            <div class="foundation-list">
              <div v-for="item in foundationItems" :key="item.key" class="foundation-item">
                <div class="foundation-main">
                  <div class="foundation-title">{{ item.label }}</div>
                  <div class="foundation-meta">
                    <span class="tag" :class="foundationTagClass(item.status)">
                      {{ foundationStatusText(item.status) }}
                    </span>
                    <span v-if="item.lastSuccessAt" class="meta">
                      成功：{{ formatUpdatedAt(item.lastSuccessAt) }}
                    </span>
                    <span v-if="item.lastFailureAt" class="meta">
                      失败：{{ formatUpdatedAt(item.lastFailureAt) }}
                    </span>
                  </div>
                  <div v-if="item.lastErrorMessage" class="foundation-error" :title="item.lastErrorMessage">
                    {{ item.lastErrorMessage }}
                  </div>
                </div>

                <div class="foundation-side">
                  <button
                    class="mini-btn"
                    type="button"
                    :disabled="item.status === 'running'"
                    @click="runOneFoundation(item.key)"
                  >
                    刷新
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <button
          class="seg-btn"
          title="盘后数据导入"
          @click="handleOpenLocalImportDialog"
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
import { inject, ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from "vue";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useWatchlist } from "@/composables/useWatchlist";
import { useFoundationDataCenter } from "@/composables/useFoundationDataCenter";
import { useCurrentSymbolData } from "@/composables/useCurrentSymbolData";
import { releaseCandlesCache } from "@/services/candlesCacheService";

import SymbolSearch from "./symbol/SymbolSearch.vue";
import WatchlistMenu from "./symbol/WatchlistMenu.vue";
import SymbolActions from "./symbol/SymbolActions.vue";

import { formatDateTime, formatYmdInt } from "@/utils/timeFormat";
import { parseTimeValue } from "@/utils/timeParse";
import { openLocalImportDialog } from "@/settings/localImport";

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
const wl = useWatchlist();
const dialogManager = inject("dialogManager", null);
const hub = inject("viewCommandHub");

const foundationData = useFoundationDataCenter();
const currentSymbolData = useCurrentSymbolData();

const { ready, search, findBySymbol, ensureLoaded } = symbolIndex;

const placeholder = "输入代码/拼音首字母（例：000001 + 市场区分）";
const inputText = ref(settings.preferences.lastSymbol || vm.code.value || "");
const isInputFocused = ref(false);
const isWatchlistOpen = ref(false);
const suggestions = ref([]);
const invalidHint = ref("");
const error = ref("");

const searchRef = ref(null);
const watchlistRef = ref(null);

const foundationMenuOpen = ref(false);
const foundationRootRef = ref(null);

const refreshing = ref(false);

const foundationItems = computed(() => [
  {
    key: "symbol_index",
    label: "标的列表",
    ...foundationData.state.symbol_index,
  },
  {
    key: "profile_snapshot",
    label: "档案快照",
    ...foundationData.state.profile_snapshot,
  },
  {
    key: "trade_calendar",
    label: "交易日历",
    ...foundationData.state.trade_calendar,
  },
  {
    key: "factor_events_snapshot",
    label: "复权事件快照",
    ...foundationData.state.factor_events_snapshot,
  },
]);

const foundationBusyAll = computed(() =>
  foundationItems.value.some((x) => x.status === "running")
);

const lastRenderedIdentity = ref(identityKey(vm.code.value, vm.market.value));

watch(
  [() => vm.code.value, () => vm.market.value],
  ([newCode, newMarket]) => {
    lastRenderedIdentity.value = identityKey(newCode, newMarket);
  }
);

async function tryReleaseCurrentCache() {
  try {
    const code = asStr(vm.code.value);
    const market = asMarket(vm.market.value);
    const freq = asStr(vm.freq.value);
    if (!code || !market || !freq) return;

    await releaseCandlesCache({ market, code, freq });
  } catch (e) {
    console.warn("[SymbolPanel] release current cache failed:", e);
  }
}

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

  await tryReleaseCurrentCache();

  inputText.value = identity.symbol;

  settings.setLastSymbolIdentity({
    symbol: identity.symbol,
    market: identity.market,
  });
  settings.addSymbolHistoryEntry({
    symbol: identity.symbol,
    market: identity.market,
  });

  try {
    await currentSymbolData.prepare({
      symbol: identity.symbol,
      market: identity.market,
      freq: vm.freq.value,
      adjust: vm.adjust.value,
    });

    vm.setSymbolIdentity({
      symbol: identity.symbol,
      market: identity.market,
    });

    await vm.reload({ with_profile: true });
  } catch (e) {
    console.error("[SymbolPanel] selectItem failed:", e);
  }

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
  vm.reload?.({ with_profile: true });
}

async function handleOpenLocalImportDialog() {
  try {
    await openLocalImportDialog(dialogManager);
  } catch (e) {
    console.error("[SymbolPanel] openLocalImportDialog failed:", e);
  }
}

function toggleFoundationMenu() {
  foundationMenuOpen.value = !foundationMenuOpen.value;
}

async function runAllFoundation() {
  await foundationData.runAll();
}

async function runOneFoundation(key) {
  await foundationData.runOne(key);
}

async function refreshSymbolIndexAndProfile() {
  if (refreshing.value) return;
  refreshing.value = true;

  try {
    await foundationData.runOne("symbol_index");
    await foundationData.runOne("profile_snapshot");
    await ensureLoaded();
    updateSuggestions();
  } finally {
    refreshing.value = false;
  }
}

function foundationStatusText(status) {
  const s = String(status || "");
  if (s === "running") return "同步中";
  if (s === "success") return "同步成功";
  if (s === "failed") return "同步失败";
  return "未同步";
}

function foundationTagClass(status) {
  const s = String(status || "");
  if (s === "running") return "running";
  if (s === "success") return "success";
  if (s === "failed") return "failed";
  return "idle";
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
    asStr(inputText.value).length > 0
);

async function onFocus() {
  isInputFocused.value = true;
  invalidHint.value = "";

  try {
    await ensureLoaded();
  } catch {}

  updateSuggestions();
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

watch(inputText, async () => {
  invalidHint.value = "";

  if (asStr(inputText.value)) {
    try {
      await ensureLoaded();
    } catch {}
  }

  updateSuggestions();
});

watch(
  () => ready.value,
  async () => {
    if (!asStr(inputText.value)) return;
    await nextTick();
    updateSuggestions();
  }
);

function updateSuggestions() {
  const q = asStr(inputText.value);

  if (!q) {
    suggestions.value = [];
    return;
  }

  const result = search(q, 20);
  suggestions.value = Array.isArray(result) ? result : [];
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

  if (foundationRootRef.value && !foundationRootRef.value.contains(target)) {
    foundationMenuOpen.value = false;
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
    };
  }

  return {
    floatShares: pf.float_shares ?? null,
    floatValue: pf.float_value ?? null,
    industry: pf.industry ?? null,
    region: pf.region ?? null,
    concepts: Array.isArray(pf.concepts) ? pf.concepts : [],
  };
});

const hasProfileInfo = computed(() => {
  const p = profileInfo.value;
  return !!(
    p.floatShares ||
    p.floatValue ||
    p.industry ||
    p.region ||
    p.concepts.length > 0
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

.seg-top-actions {
  height: 36px;
}

.seg {
  display: inline-flex;
  align-items: center;
  border: 1px solid #444;
  border-radius: 10px;
  overflow: visible;
  background: #1a1a1a;
  height: 36px;
}

.seg-item {
  position: relative;
  display: inline-flex;
  align-items: center;
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

.seg-item + .seg-btn,
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

.foundation-menu {
  position: absolute;
  top: 42px;
  right: 0;
  width: 420px;
  background: #1b1b1b;
  border: 1px solid #333;
  border-radius: 8px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
  padding: 10px;
  z-index: 1200;
}

.foundation-head {
  font-size: 13px;
  font-weight: 700;
  color: #ddd;
  margin-bottom: 8px;
}

.foundation-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.foundation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.foundation-item {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  padding: 8px;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.02);
}

.foundation-main {
  min-width: 0;
}

.foundation-title {
  font-size: 13px;
  color: #ddd;
  font-weight: 600;
}

.foundation-meta {
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.meta {
  color: #999;
  font-size: 12px;
}

.foundation-error {
  margin-top: 4px;
  color: #e67e22;
  font-size: 12px;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.foundation-side {
  display: flex;
  align-items: flex-start;
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

.tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: #bbb;
  user-select: none;
  white-space: nowrap;
}

.tag.running {
  background: rgba(46, 204, 113, 0.12);
  border-color: rgba(46, 204, 113, 0.25);
  color: #7ee2b8;
}

.tag.success {
  background: rgba(155, 183, 230, 0.10);
  border-color: rgba(155, 183, 230, 0.22);
  color: #9db7e6;
}

.tag.failed {
  background: rgba(230, 179, 92, 0.12);
  border-color: rgba(230, 179, 92, 0.25);
  color: #e6b35c;
}

.tag.idle {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  color: #bbb;
}
</style>
