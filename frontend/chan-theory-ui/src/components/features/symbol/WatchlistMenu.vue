<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\symbol\WatchlistMenu.vue -->
<!-- ==============================
说明：自选池下拉菜单
V5.0 - BREAKING: watchlist 终态对齐双主键
- 底层 useWatchlist 已彻底升级为 (symbol, market) 双主键
- 本组件继续保持 UI 层身份语义一致
- 不再存在 symbol-only 残留调用
============================== -->
<template>
  <div class="watchlist-wrapper">
    <button
      ref="favBtnRef"
      class="fav-menu-btn"
      title="自选"
      aria-label="自选"
      @click="toggleFavoritesMenu"
    >
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path
          d="M12 2 L14.9 8.1 L21.5 9.2 L16.8 13.7 L18.1 20.2 L12 16.9 L5.9 20.2 L7.2 13.7 L2.5 9.2 L9.1 8.1 Z"
          fill="#f1c40f"
          stroke="#f39c12"
          stroke-width="1"
        />
      </svg>
      <svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true">
        <path d="M7 9l5 6 5-6z" fill="#ccc" />
      </svg>
    </button>

    <DropdownContainer :show="isOpen" ref="favoritesWrapRef">
      <SymbolListItem
        v-for="(it, i) in favoritesDisplay"
        :key="itemKey(it, i)"
        :symbol="it.symbol"
        :name="it.name || ''"
        :market="it.market || ''"
        :type="it.type || ''"
        :is-starred="isFavStarOn(it)"
        star-title="从自选中移除/撤销移除（关闭菜单后生效）"
        @select="onSelect"
        @toggle-star="toggleFavStage"
      />
      <div v-if="!favoritesDisplay.length" class="no-data">暂无自选标的</div>
    </DropdownContainer>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useWatchlist } from "@/composables/useWatchlist";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import DropdownContainer from "./DropdownContainer.vue";
import SymbolListItem from "./SymbolListItem.vue";

const emit = defineEmits(["selectSymbol", "opened", "closed"]);
defineExpose({ close });

const wl = useWatchlist();
const { findBySymbol } = useSymbolIndex();

const favBtnRef = ref(null);
const favoritesWrapRef = ref(null);

const isOpen = ref(false);
const favInitialSet = ref(new Set());
const favStagedSet = ref(new Set());

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function makeIdentityKey(symbol, market) {
  return `${asStr(market).toUpperCase()}:${asStr(symbol)}`;
}

function itemKey(item, i) {
  return `${makeIdentityKey(item?.symbol, item?.market)}_${i}`;
}

const favoritesDisplay = computed(() => {
  const initial = Array.from(favInitialSet.value);
  return initial
    .map((k) => {
      const [market, symbol] = String(k || "").split(":");
      if (!market || !symbol) return null;
      return (
        findBySymbol(symbol, market) || {
          symbol,
          market,
          name: "",
          type: "",
        }
      );
    })
    .filter(Boolean)
    .sort((a, b) => {
      const ka = makeIdentityKey(a.symbol, a.market);
      const kb = makeIdentityKey(b.symbol, b.market);
      return ka.localeCompare(kb);
    });
});

function isFavStarOn(item) {
  const key = makeIdentityKey(item?.symbol, item?.market);
  return favStagedSet.value.has(key);
}

function toggleFavStage(item) {
  const key = makeIdentityKey(item?.symbol, item?.market);
  if (!key || key === ":") return;
  const next = new Set(favStagedSet.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  favStagedSet.value = next;
}

function open() {
  const nowArr = Array.isArray(wl.items.value) ? wl.items.value : [];
  const itemsSet = new Set(
    nowArr
      .map((x) => makeIdentityKey(x?.symbol, x?.market))
      .filter((k) => k && k !== ":")
  );

  favInitialSet.value = itemsSet;
  favStagedSet.value = new Set(favInitialSet.value);
  isOpen.value = true;
  emit("opened");
}

async function close(apply = true) {
  if (!isOpen.value) return;
  if (apply) {
    await applyFavoritesDiff();
  }
  isOpen.value = false;
  emit("closed");
}

function toggleFavoritesMenu() {
  if (isOpen.value) {
    close(true);
  } else {
    open();
  }
}

async function applyFavoritesDiff() {
  const toRemove = [];
  const toAdd = [];

  for (const s of favInitialSet.value) {
    if (!favStagedSet.value.has(s)) toRemove.push(s);
  }
  for (const s of favStagedSet.value) {
    if (!favInitialSet.value.has(s)) toAdd.push(s);
  }

  if (toAdd.length > 0 || toRemove.length > 0) {
    const addJobs = toAdd.map((key) => {
      const [market, symbol] = key.split(":");
      return wl.addOne({ symbol, market }).catch(() => {});
    });
    const rmJobs = toRemove.map((key) => {
      const [market, symbol] = key.split(":");
      return wl.removeOne({ symbol, market }).catch(() => {});
    });
    await Promise.all([...addJobs, ...rmJobs]);
  }
}

function onSelect(item) {
  emit("selectSymbol", item);
  close(true);
}
</script>

<style scoped>
.watchlist-wrapper {
  position: relative;
  display: inline-block;
}
.fav-menu-btn {
  height: 36px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #1a1a1a;
  border: 1px solid #444;
  border-radius: 6px;
  color: #ddd;
  padding: 0 8px;
  cursor: pointer;
}
.fav-menu-btn:hover {
  border-color: #5b7fb3;
}
.no-data {
  color: #888;
  padding: 10px;
  text-align: center;
}
</style>
