<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\SymbolPanel.vue -->
<template>
  <div class="symbol-row">
    <!-- 左列：标的输入框 + 自选菜单按钮 -->
    <div class="col-left">
      <div class="input-group">
        <input
          ref="symbolInputRef"
          class="symbol-input compact"
          v-model="inputText"
          :placeholder="placeholder"
          v-select-all
          @focus="onFocus"
          @input="onInput"
          @keydown="onKeydown"
          @blur="onBlur"
          :class="{ invalid: invalidHint }"
        />

        <!-- 自选菜单按钮（星+下三角） -->
        <button
          ref="favBtnRef"
          class="fav-menu-btn"
          title="自选"
          aria-label="自选"
          @click="toggleFavoritesMenu"
        >
          <!-- 星形图标 + 下三角 -->
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
      </div>

      <!-- 联想下拉（与 favorites/历史 互斥） -->
      <div
        v-if="showSuggest && !favoritesOpen && !showHistory"
        class="dropdown"
        ref="suggestWrapRef"
        @wheel.passive
      >
        <div
          v-for="(item, i) in suggestions"
          :key="item.symbol + '_' + i"
          class="suggest-item"
          :class="{ active: i === activeIndex }"
          @mousedown.prevent="selectItemByRow(item, $event)"
        >
          <div class="left">
            <span class="code">{{ item.symbol }}</span>
            <span class="name">{{ item.name }}</span>
          </div>
          <div class="right">
            <!-- 市场/类型合并在一列上下两行，居中 -->
            <div class="meta-vert">
              <span class="meta market">{{ item.market }}</span>
              <span class="meta type">{{ item.type }}</span>
            </div>
            <!-- 联想下拉的星标：即时落地（点击即 add/remove + refresh），放在市场列右边 -->
            <button
              class="star-btn"
              :class="{ active: isStarOn(item.symbol) }"
              title="加入/移除自选"
              aria-label="加入/移除自选"
              @mousedown.stop.prevent="toggleStarImmediate(item)"
            >
              <!-- 简洁 SVG 五角星 -->
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                aria-hidden="true"
              >
                <path
                  class="star"
                  d="M12 2 L14.9 8.1 L21.5 9.2 L16.8 13.7 L18.1 20.2 L12 16.9 L5.9 20.2 L7.2 13.7 L2.5 9.2 L9.1 8.1 Z"
                />
              </svg>
            </button>
          </div>
        </div>
        <div v-if="!suggestions.length" class="no-data">无匹配项</div>
      </div>

      <!-- 历史下拉（输入为空时自动显示，最大50项，时间倒序） -->
      <div
        v-if="showHistory && !favoritesOpen"
        class="dropdown"
        ref="historyWrapRef"
        @wheel.passive
      >
        <div
          v-for="(h, i) in historyDisplay"
          :key="h.symbol + '_' + i"
          class="suggest-item"
          @mousedown.prevent="selectHistoryByRow(h)"
        >
          <div class="left">
            <span class="code">{{ h.symbol }}</span>
            <span class="name">{{ findBySymbol(h.symbol)?.name || "" }}</span>
          </div>
          <div class="right">
            <div class="meta-vert">
              <span class="meta market">{{
                findBySymbol(h.symbol)?.market || ""
              }}</span>
              <span class="meta type">{{
                findBySymbol(h.symbol)?.type || ""
              }}</span>
            </div>
            <!-- 历史下拉的星标（即时落地，与联想一致） -->
            <button
              class="star-btn"
              :class="{ active: isStarOn(h.symbol) }"
              title="加入/移除自选"
              aria-label="加入/移除自选"
              @mousedown.stop.prevent="
                toggleStarImmediate({ symbol: h.symbol })
              "
            >
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                aria-hidden="true"
              >
                <path
                  class="star"
                  d="M12 2 L14.9 8.1 L21.5 9.2 L16.8 13.7 L18.1 20.2 L12 16.9 L5.9 20.2 L7.2 13.7 L2.5 9.2 L9.1 8.1 Z"
                />
              </svg>
            </button>
          </div>
        </div>
        <div v-if="!historyDisplay.length" class="no-data">暂无历史记录</div>
      </div>

      <!-- 自选下拉（favorites）：星标仅改 staged，关闭时统一落地 -->
      <div
        v-if="favoritesOpen"
        class="dropdown"
        ref="favoritesWrapRef"
        @wheel.passive
      >
        <div
          v-for="(sym, i) in favoritesDisplay"
          :key="sym + '_' + i"
          class="suggest-item"
          @mousedown.prevent="selectFavByRow(sym)"
        >
          <div class="left">
            <span class="code">{{ sym }}</span>
            <span class="name">{{ findBySymbol(sym)?.name || "" }}</span>
          </div>
          <div class="right">
            <!-- 市场/类型合并在一列上下两行，居中 -->
            <div class="meta-vert">
              <span class="meta market">{{
                findBySymbol(sym)?.market || ""
              }}</span>
              <span class="meta type">{{ findBySymbol(sym)?.type || "" }}</span>
            </div>
            <!-- favorites 下拉的星标：放在市场列右边（仅改 staged，关闭菜单后生效） -->
            <button
              class="star-btn"
              :class="{ active: isFavStarOn(sym) }"
              title="从自选中移除/撤销移除（关闭菜单后生效）"
              aria-label="从自选中移除/撤销移除"
              @mousedown.stop.prevent="toggleFavStage(sym)"
            >
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                aria-hidden="true"
              >
                <path
                  class="star"
                  d="M12 2 L14.9 8.1 L21.5 9.2 L16.8 13.7 L18.1 20.2 L12 16.9 L5.9 20.2 L7.2 13.7 L2.5 9.2 L9.1 8.1 Z"
                />
              </svg>
            </button>
          </div>
        </div>
        <div v-if="!favoritesDisplay.length" class="no-data">暂无自选标的</div>
      </div>

      <div v-if="invalidHint" class="hint">{{ invalidHint }}</div>
    </div>

    <!-- 中列：标的信息 -->
    <div class="col-middle" :title="middleTitle">
      <span class="sym-name">{{ middleName }}</span>
      <span class="sym-code">（{{ middleCode }}）</span>
    </div>

    <!-- 右列：刷新/导出 两个连体按钮 -->
    <div class="col-right">
      <div class="seg">
        <button
          class="seg-btn"
          title="刷新"
          @click="onRefreshClick"
          :disabled="vm.loading.value"
        >
          刷新
        </button>
        <button
          class="seg-btn"
          title="导出"
          @click="toggleExportMenu"
          :disabled="disabledExport"
        >
          导出
        </button>
      </div>

      <!-- 导出菜单（保持原有能力） -->
      <div class="export-wrap" ref="exportWrapRef" v-if="exportOpen">
        <div class="menu">
          <div
            class="item"
            :class="{ disabled: disabledExport }"
            @click="doExport('main', 'png')"
          >
            导出 PNG
          </div>
          <div
            class="item"
            :class="{ disabled: disabledExport }"
            @click="doExport('main', 'jpg')"
          >
            导出 JPG
          </div>
          <div
            class="item"
            :class="{ disabled: disabledExport }"
            @click="doExport('main', 'svg')"
          >
            导出 SVG
          </div>
          <div
            class="item"
            :class="{ disabled: disabledExport }"
            @click="doExport('main', 'html')"
          >
            导出 HTML
          </div>
        </div>
      </div>
    </div>
  </div>

  <div v-if="error" class="err">错误：{{ error }}</div>
</template>

<script setup>
import { inject, ref, computed, onMounted, onBeforeUnmount } from "vue";
import { vSelectAll } from "@/utils/inputBehaviors";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useWatchlist } from "@/composables/useWatchlist";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import * as historyApi from "@/services/historyService"; // NEW: 历史入库服务

defineOptions({ directives: { selectAll: vSelectAll } });

const vm = inject("marketView");
const hotkeys = inject("hotkeys", null);
const exportController = inject("exportController");
const settings = useUserSettings();
const { ready, search, findBySymbol } = useSymbolIndex();
const hub = useViewCommandHub();
const wl = useWatchlist();

const placeholder = "输入代码/拼音首字母（例：600519 或 gzymt）";
const inputText = ref(settings.lastSymbol.value || vm.code.value || "");
const symbolInputRef = ref(null);
const focused = ref(false);
const activeIndex = ref(-1);
const suggestions = ref([]);
const invalidHint = ref("");
const exportWrapRef = ref(null);
const exportOpen = ref(false);
const error = ref("");

// 外部点击收起元素引用
const suggestWrapRef = ref(null);
const historyWrapRef = ref(null);
const favoritesWrapRef = ref(null);
const favBtnRef = ref(null);

// 首次载入取一次自选
onMounted(() => {
  wl.refresh().catch(() => {});
});

const inWatchlistSet = computed(() => {
  const arr = Array.isArray(wl.items.value) ? wl.items.value : [];
  return new Set(arr);
});

// 历史：输入为空时自动弹出（UI 仍读取本地持久化列表，以保持“本地-first”的体验）
const showHistory = computed(
  () =>
    focused.value && !favoritesOpen.value && inputText.value.trim().length === 0
);

// 若你只想在“有历史时”才显示下拉，请改为：
// const showHistory = computed(() =>
//   focused.value &&
//   !favoritesOpen.value &&
//   inputText.value.trim().length === 0 &&
//   historyDisplay.value.length > 0  // 注意 .value
// );

const historyList = computed(() => settings.getSymbolHistoryList()); // [{symbol, ts}] 时间倒序
const historyDisplay = computed(() => {
  const arr = Array.isArray(historyList.value) ? historyList.value : [];
  return arr.slice(0, 50);
});

// 联想下拉可见：输入有内容，未打开 favorites/历史
const showSuggest = computed(
  () =>
    focused.value &&
    !favoritesOpen.value &&
    inputText.value?.trim().length > 0 &&
    suggestions.value.length > 0
);

// favorites（自选）下拉：打开/关闭与会话态（使用 ref(Set) 触发响应式）
const favoritesOpen = ref(false);
const favInitialSet = ref(new Set());
const favStagedSet = ref(new Set());

const favoritesDisplay = computed(() => {
  return Array.from(favInitialSet.value).sort((a, b) => a.localeCompare(b));
});
function isFavStarOn(sym) {
  return favStagedSet.value.has(String(sym || "").trim());
}
function toggleFavStage(sym) {
  const s = String(sym || "").trim();
  if (!s) return;
  const next = new Set(favStagedSet.value);
  if (next.has(s)) next.delete(s);
  else next.add(s);
  favStagedSet.value = next; // 新建 Set 再赋值，触发响应式更新
}
function openFavorites() {
  // 互斥：关闭联想
  focused.value = false;
  activeIndex.value = -1;
  suggestions.value = [];
  // 会话初始与影子集合（ref(Set)）
  const now = Array.isArray(wl.items.value) ? wl.items.value : [];
  favInitialSet.value = new Set(now.map((x) => String(x || "").trim()));
  favStagedSet.value = new Set(favInitialSet.value);
  favoritesOpen.value = true;
}
async function applyFavoritesDiff() {
  // 计算差异
  const toRemove = [];
  const toAdd = [];
  for (const s of favInitialSet.value)
    if (!favStagedSet.value.has(s)) toRemove.push(s);
  for (const s of favStagedSet.value)
    if (!favInitialSet.value.has(s)) toAdd.push(s);

  // 并发执行
  const addJobs = toAdd.map((s) => wl.addOne(s).catch(() => {}));
  const rmJobs = toRemove.map((s) => wl.removeOne(s).catch(() => {}));
  await Promise.all([...addJobs, ...rmJobs]);

  // 与后端对齐（关键：await，确保“关闭就生效、再打开立即最新”）
  await wl.refresh().catch(() => {});
}
async function closeFavorites(apply = true) {
  if (!favoritesOpen.value) return;
  if (apply) {
    await applyFavoritesDiff();
  }
  favoritesOpen.value = false;
}
function toggleFavoritesMenu() {
  if (favoritesOpen.value) closeFavorites(true);
  else openFavorites();
}

// 联想/历史：星标即时落地
function isStarOn(symbol) {
  return inWatchlistSet.value.has(String(symbol || "").trim());
}
async function toggleStarImmediate(item) {
  try {
    const sym = String(item?.symbol || "").trim();
    if (!sym) return;
    const on = isStarOn(sym);
    if (on) await wl.removeOne(sym);
    else await wl.addOne(sym);
    await wl.refresh(); // 保证 favorites 下次打开立即最新
  } catch {}
}

// 联想下拉交互
function onFocus() {
  focused.value = true;
  invalidHint.value = "";
  if (inputText.value?.trim()) updateSuggestions();
  if (hotkeys) hotkeys.pushScope("panel:symbol");
}
function onInput() {
  invalidHint.value = "";
  updateSuggestions();
}

// 按回车仅失焦；提交逻辑统一在 onBlur 中执行
function onKeydown(e) {
  // 1. 优先处理回车键
  if (e.key === "Enter") {
    e.preventDefault();
    symbolInputRef.value?.blur(); // 只失焦，避免二次提交
    return;
  }
  if (!showSuggest.value) return;
  if (e.key === "ArrowDown") {
    e.preventDefault();
    if (!suggestions.value.length) return;
    activeIndex.value =
      (activeIndex.value + 1 + suggestions.value.length) %
      suggestions.value.length;
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (!suggestions.value.length) return;
    activeIndex.value =
      (activeIndex.value - 1 + suggestions.value.length) %
      suggestions.value.length;
  } else if (e.key === "Escape") {
    focused.value = false;
  }
}

// 失焦统一提交
function onBlur() {
  setTimeout(() => {
    if (!favoritesOpen.value) {
      focused.value = false;
      tryCommitByInput();
      if (hotkeys) hotkeys.popScope("panel:symbol");
    }
  }, 0);
}
function updateSuggestions() {
  const q = inputText.value?.trim() || "";
  if (!q || !ready.value) {
    suggestions.value = [];
    activeIndex.value = -1;
    return;
  }
  suggestions.value = search(q, 20);
  activeIndex.value = suggestions.value.length ? 0 : -1;
}
function selectItemByRow(item, _ev) {
  try {
    // 若事件目标在星标按钮内，已被 .stop 阻止，这里只处理“行的选择”
    selectItem(item);
  } catch {}
}
function selectFavByRow(sym) {
  const entry = findBySymbol(String(sym || ""));
  if (!entry) return;
  selectItem(entry);
  closeFavorites(true);
}
function selectHistoryByRow(hItem) {
  const entry = findBySymbol(String(hItem?.symbol || ""));
  if (!entry) return;
  selectItem(entry);
}

// 选中项：写入历史并刷新（本地持久化 + 后端入库）
async function selectItem(item) {
  const sym = String(item.symbol).trim();
  inputText.value = sym;
  vm.code.value = sym;
  settings.setLastSymbol(sym);
  // 本地（LocalStorage）持久化历史
  settings.addSymbolHistoryEntry(sym);
  // —— 新增：写入本地数据库（后端） —— //
  try {
    await historyApi.add({ symbol: sym, freq: vm.freq.value });
  } catch (e) {
    // 静默失败，不阻断主流程
    console.warn("history add failed:", e?.message || e);
  }

  invalidHint.value = "";
  suggestions.value = [];
  activeIndex.value = -1;
  focused.value = false;

  // 显式触发重载，不再依赖 watch。无论 code 是否变化，都强制刷新。
  vm.reload({ force: true });
}

// 失焦/输入确认时的统一提交逻辑
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

// 刷新按钮
function onRefreshClick() {
  try {
    hub.execute("Refresh", {});
  } catch {}
  vm.reload?.({ force: true });
}

// 导出菜单
const disabledExport = computed(
  () => !!(vm.loading?.value || exportController?.exporting?.value)
);
function toggleExportMenu() {
  if (disabledExport.value) return;
  exportOpen.value = !exportOpen.value;
}
async function doExport(targetId, format) {
  if (disabledExport.value) return;
  const res = await exportController.export({ targetId, format });
  exportOpen.value = false;
  if (!res.ok) console.error("导出失败：", res.error);
}

// 文档点击：关闭 favorites 与导出菜单
async function onDocClick(e) {
  const el = e?.target;
  // 关闭导出菜单
  if (
    exportOpen.value &&
    exportWrapRef.value &&
    !exportWrapRef.value.contains(el)
  ) {
    exportOpen.value = false;
  }
  // 关闭 favorites（同步等待）
  if (favoritesOpen.value) {
    const insideFav =
      (favoritesWrapRef.value && favoritesWrapRef.value.contains(el)) ||
      (favBtnRef.value && favBtnRef.value.contains(el));
    if (!insideFav) {
      await closeFavorites(true);
    }
  }
  // 关闭联想：点击在联想外部且输入不聚焦
  if (
    showSuggest.value &&
    suggestWrapRef.value &&
    !suggestWrapRef.value.contains(el) &&
    el !== symbolInputRef.value
  ) {
    focused.value = false;
  }
}
onMounted(() => {
  document.addEventListener("click", onDocClick);
  window.addEventListener("chan:toggle-export-menu", toggleExportMenu);
});
onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick);
  window.removeEventListener("chan:toggle-export-menu", toggleExportMenu);
});

// 中列标题
const middleCode = computed(() => (vm.code?.value || "").trim());
const middleName = computed(() => {
  try {
    const sym = middleCode.value;
    return sym ? findBySymbol(sym)?.name?.trim() || "" : "";
  } catch {
    return "";
  }
});
const middleTitle = computed(() =>
  middleName.value
    ? `${middleName.value}（${middleCode.value}）`
    : middleCode.value || ""
);
</script>

<style scoped>
/* 保持原样式 + 新增星标样式与下拉层级提升 */
.symbol-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  column-gap: 12px;
}
.col-left {
  position: relative;
}

/* 输入 + 自选按钮并排 */
.input-group {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.symbol-input {
  height: 36px;
  line-height: 36px;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 0 10px;
  outline: none;
}
.symbol-input.compact {
  width: 128px;
}
.symbol-input.invalid {
  border-color: #a94442;
}

/* 自选菜单按钮（星+下三角） */
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

/* 下拉统一样式：按内容扩展，单行不换行 */
.dropdown {
  position: absolute;
  z-index: 1000; /* 在主图之上、Modal 之下 */
  top: 38px;
  left: 0;
  right: auto;
  width: max-content;
  min-width: 100%;
  max-height: 280px;
  overflow-y: auto;
  background: #1b1b1b;
  border: 1px solid #333;
  border-radius: 6px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
  white-space: nowrap; /* 整体单行展示（不换行） */
}

/* 统一列宽（四列：code | name | meta-vert | star）——星标在市场列右边 */
:where(.dropdown) {
  --col-code: 80px; /* 代码列 */
  --col-name: 1fr; /* 名称列 */
  --col-meta: 30px; /* 市场/类型合并列（上下两行） */
  --col-star: 18px; /* 星标列（在最右） */
}

/* 每行设置为 4 列网格：code | name | meta-vert | star */
.suggest-item {
  display: grid;
  grid-template-columns:
    var(--col-code)
    var(--col-name)
    var(--col-meta)
    var(--col-star);
  align-items: center;
  justify-content: start;
  column-gap: 8px;
  padding: 6px 10px;
  cursor: pointer;
  color: #ddd;
  white-space: nowrap;
}
.suggest-item:hover,
.suggest-item.active {
  background: #2a2a2a;
}

/* 让 .left/.right 的子节点“提升”为上层 grid 的网格项 */
.suggest-item .left,
.suggest-item .right {
  display: contents; /* 关键：使内部子元素参与上层 grid 布局 */
}

/* 列放置：名称保持左对齐（第2列），市场/类型在第3列，星标移动到第4列 */
.suggest-item .left .code {
  grid-column: 1;
  font-weight: 600;
  margin-right: 8px;
}
.suggest-item .left .name {
  grid-column: 2;
  color: #ccc;
  text-align: left;
  justify-self: start;
}

/* 市场/类型合并列（上下两行，居中）在第 3 列 */
.suggest-item .right .meta-vert {
  grid-column: 3;
  display: flex;
  flex-direction: column;
  align-items: center; /* 水平居中 */
  justify-content: center; /* 垂直居中（对齐按钮行高） */
  gap: 2px;
}
.suggest-item .right .meta-vert .meta {
  color: #999;
  font-size: 12px;
  line-height: 1.1;
}

/* 星标按钮在最右（第 4 列） */
.suggest-item .right .star-btn {
  grid-column: 4;
  justify-self: center;
}

/* 空态 */
.no-data {
  color: #888;
  padding: 10px;
  text-align: center;
}

/* 提示 */
.hint {
  color: #e67e22;
  font-size: 12px;
  margin-top: 4px;
}

/* 中列信息 */
.col-middle {
  text-align: left;
  color: #ddd;
  user-select: none;
}
.sym-name {
  font-weight: 600;
}
.sym-code {
  color: #bbb;
}

/* 右列按钮保持不变 */
.col-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
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
  width: 60px;
  height: 36px;
  border-radius: 0;
}
.seg-btn + .seg-btn {
  border-left: 1px solid #444;
}
.seg-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 导出菜单 */
.export-wrap {
  position: relative;
}
.menu {
  position: absolute;
  top: 40px;
  right: 0;
  min-width: 140px;
  background: #1f1f1f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 6px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
  z-index: 1000;
  overflow: hidden;
}
.item {
  padding: 8px 12px;
  cursor: pointer;
  white-space: nowrap;
}
.item:hover {
  background: #2a2a2a;
}
.item.disabled {
  opacity: 0.5;
  pointer-events: none;
}

/* 统一星标按钮样式 */
.star-btn {
  width: 18px;
  height: 18px;
  padding: 0;
  margin: 0;
  background: transparent;
  border: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.star-btn .star {
  fill: transparent;
  stroke: #bbb;
  stroke-width: 1.2;
  transition: fill 120ms ease, stroke 120ms ease;
}
.star-btn:hover .star {
  stroke: #e0e0e0;
}
.star-btn.active .star {
  fill: #f1c40f;
  stroke: #f39c12;
}

/* 错误显示 */
.err {
  margin-top: 8px;
  color: #e74c3c;
  text-align: left;
}
</style>
