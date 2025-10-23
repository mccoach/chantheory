<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\symbol\WatchlistMenu.vue -->
<!-- 说明：封装自选池的按钮和下拉菜单，包含“暂存式编辑”的完整逻辑。 -->
<!-- FIX: 增加对 wl.items 的 watch，确保在菜单打开时能响应外部对自选池的修改，实现实时同步。 -->
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
        v-for="(sym, i) in favoritesDisplay"
        :key="sym + '_' + i"
        :symbol="sym"
        :name="findBySymbol(sym)?.name || ''"
        :market="findBySymbol(sym)?.market || ''"
        :type="findBySymbol(sym)?.type || ''"
        :is-starred="isFavStarOn(sym)"
        star-title="从自选中移除/撤销移除（关闭菜单后生效）"
        @select="onSelect"
        @toggle-star="toggleFavStage"
      />
      <div v-if="!favoritesDisplay.length" class="no-data">暂无自选标的</div>
    </DropdownContainer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue"; // NEW: 引入 watch
import { useWatchlist } from "@/composables/useWatchlist";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import DropdownContainer from "./DropdownContainer.vue";
import SymbolListItem from "./SymbolListItem.vue";

const emit = defineEmits(["selectSymbol", "opened", "closed"]); // MODIFIED: 增加 opened/closed 事件
defineExpose({ close });

const wl = useWatchlist();
const { findBySymbol } = useSymbolIndex();

const favBtnRef = ref(null);
const favoritesWrapRef = ref(null);

const isOpen = ref(false);
const favInitialSet = ref(new Set());
const favStagedSet = ref(new Set());

const favoritesDisplay = computed(() => {
  return Array.from(favInitialSet.value).sort((a, b) => a.localeCompare(b));
});

// NEW: 监听 useWatchlist 的 items 变化，在菜单打开时实时同步
watch(
  () => wl.items.value,
  (newItems) => {
    // 只有当菜单是打开状态时，才进行同步
    if (isOpen.value) {
      const itemsSet = new Set((newItems || []).map(s => String(s || "").trim()));
      // 使用最新的数据重置内部的初始状态和暂存状态
      favInitialSet.value = itemsSet;
      favStagedSet.value = new Set(itemsSet);
    }
  },
  { deep: true } // 深度监听数组的变化
);


function isFavStarOn(sym) {
  return favStagedSet.value.has(String(sym || "").trim());
}

function toggleFavStage(sym) {
  const s = String(sym || "").trim();
  if (!s) return;
  const next = new Set(favStagedSet.value);
  if (next.has(s)) next.delete(s);
  else next.add(s);
  favStagedSet.value = next;
}

// MODIFIED: 打开菜单时，不再手动同步数据，交由 watch 统一处理
async function open() {
  // 确保在打开前获取最新列表
  await wl.refresh();
  const now = Array.isArray(wl.items.value) ? wl.items.value : [];
  favInitialSet.value = new Set(now.map((x) => String(x || "").trim()));
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
  for (const s of favInitialSet.value)
    if (!favStagedSet.value.has(s)) toRemove.push(s);
  for (const s of favStagedSet.value)
    if (!favInitialSet.value.has(s)) toAdd.push(s);

  if (toAdd.length > 0 || toRemove.length > 0) {
    const addJobs = toAdd.map((s) => wl.addOne(s).catch(() => {}));
    const rmJobs = toRemove.map((s) => wl.removeOne(s).catch(() => {}));
    await Promise.all([...addJobs, ...rmJobs]);
    await wl.refresh();
  }
}

function onSelect(symbol) {
  emit("selectSymbol", findBySymbol(symbol));
  close(true);
}

onMounted(() => {
  wl.refresh().catch(() => {});
});
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
