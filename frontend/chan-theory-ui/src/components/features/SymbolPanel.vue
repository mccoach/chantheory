<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\SymbolPanel.vue -->
<!-- REFACTORED: 重构为协调者组件 -->
<!-- FINAL FIX: 恢复 inWatchlistSet 计算属性和对 SymbolSearch 的 :watchlist 绑定，彻底修复星标状态不同步问题。 -->
<template>
  <div class="symbol-row">
    <!-- 左列：标的输入与自选 -->
    <div class="col-left">
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
      <WatchlistMenu
        ref="watchlistRef"
        @select-symbol="selectItem"
        @opened="onWatchlistOpen"
        @closed="onWatchlistClose"
      />
    </div>

    <!-- 中列：标的信息 -->
    <div class="col-middle" :title="middleTitle">
      <span class="sym-name">{{ middleName }}</span>
      <span class="sym-code">（{{ middleCode }}）</span>
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
import * as historyApi from "@/services/historyService";

// 导入新的子组件
import SymbolSearch from "./symbol/SymbolSearch.vue";
import WatchlistMenu from "./symbol/WatchlistMenu.vue";
import SymbolActions from "./symbol/SymbolActions.vue";

const vm = inject("marketView");
const hotkeys = inject("hotkeys", null);
const settings = useUserSettings();
const { ready, search, findBySymbol } = useSymbolIndex();
const hub = useViewCommandHub();
const wl = useWatchlist();

// === 状态管理 (由父组件统一协调) ===
const placeholder = "输入代码/拼音首字母（例：600519 或 gzymt）";
const inputText = ref(settings.preferences.lastSymbol || vm.code.value || "");
const isInputFocused = ref(false);
const isWatchlistOpen = ref(false);
const suggestions = ref([]);
const invalidHint = ref("");
const error = ref("");

// refs to child components
const searchRef = ref(null);
const watchlistRef = ref(null);

onMounted(() => {
  wl.refresh().catch(() => {});
  document.addEventListener("click", onDocClick);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick);
});

// === 计算属性 (决定子组件显示) ===

// NEW: 恢复 inWatchlistSet，作为响应式数据源传递给子组件
const inWatchlistSet = computed(() => new Set(Array.isArray(wl.items.value) ? wl.items.value : []));

const historyDisplay = computed(() => {
  const list = settings.getSymbolHistoryList();
  return (Array.isArray(list) ? list : []).slice(0, 50);
});

const showHistory = computed(
  () => isInputFocused.value && !isWatchlistOpen.value && inputText.value.trim().length === 0
);

const showSuggest = computed(
  () => isInputFocused.value && !isWatchlistOpen.value && inputText.value.trim().length > 0 && suggestions.value.length > 0
);

// === 事件处理器 (父组件决策) ===
function onFocus() {
  isInputFocused.value = true;
  invalidHint.value = "";
  if (inputText.value?.trim()) {
    updateSuggestions();
  }
  hotkeys?.pushScope("panel:symbol");
}

function onBlur() {
  // 延迟以允许下拉项的点击事件先生效
  setTimeout(() => {
    if (!isWatchlistOpen.value) {
      isInputFocused.value = false;
      tryCommitByInput();
      hotkeys?.popScope("panel:symbol");
    }
  }, 150);
}

watch(inputText, (newValue) => {
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
  isInputFocused.value = false; // 与自选菜单互斥
}

function onWatchlistClose() {
  isWatchlistOpen.value = false;
}

// === 核心业务逻辑 (父组件执行) ===
async function selectItem(item) {
  if (!item || !item.symbol) return;
  const sym = String(item.symbol).trim();
  inputText.value = sym;
  vm.code.value = sym;
  settings.setLastSymbol(sym);
  settings.addSymbolHistoryEntry(sym);

  try {
    await historyApi.add({ symbol: sym, freq: vm.freq.value });
  } catch (e) {
    console.warn("history add failed:", e?.message || e);
  }

  invalidHint.value = "";
  suggestions.value = [];
  isInputFocused.value = false;

  vm.reload({ force: true });
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
    // 使用 inWatchlistSet 进行判断，确保与UI状态一致
    if (inWatchlistSet.value.has(sym)) {
      await wl.removeOne(sym);
    } else {
      await wl.addOne(sym);
    }
    // `removeOne/addOne` 内部会调用 refresh，这里无需重复调用
  } catch {}
}

function onRefreshClick() {
  hub.execute("Refresh", {});
  vm.reload?.({ force: true });
}

// === 全局交互协调 ===
function onDocClick(e) {
  const target = e.target;
  // 点击外部时关闭所有
  if (searchRef.value && !searchRef.value.$el.contains(target)) {
    isInputFocused.value = false;
  }
  if (watchlistRef.value && !watchlistRef.value.$el.contains(target)) {
    watchlistRef.value.close(true); // 调用子组件的 close 方法
  }
}

// === 中间栏信息展示 (保持不变) ===
const middleCode = computed(() => (vm.code?.value || "").trim());
const middleName = computed(() => {
  const sym = middleCode.value;
  return sym ? findBySymbol(sym)?.name?.trim() || "" : "";
});
const middleTitle = computed(() =>
  middleName.value
    ? `${middleName.value}（${middleCode.value}）`
    : middleCode.value || ""
);
</script>

<style scoped>
.symbol-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  column-gap: 12px;
}
.col-left {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
}
.col-middle {
  text-align: left;
  color: #ddd;
  user-select: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sym-name {
  font-weight: 600;
}
.sym-code {
  color: #bbb;
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
</style>
