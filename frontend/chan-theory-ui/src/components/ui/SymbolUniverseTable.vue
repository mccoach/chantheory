<!-- src/components/ui/SymbolUniverseTable.vue -->
<!-- ==============================
本轮变更（按你的要求）：
1) 竖向滚动条固定在视口右侧：vscroll 为固定宽度视口，overflow-y: auto
2) 横向滚动条固定在视口底部：独立 hbar（始终可见）
3) 表格内容横向滚动仍然存在，但隐藏其自身横向滚动条（避免出现两条横向滚动条）
4) hbar 与内容区 hcontent 双向同步 scrollLeft（最小 JS）
5) 保持：表头 sticky、虚拟滚动、列宽对齐
============================== -->
<template>
  <div class="sut-wrap">
    <div class="col-head">
      <div class="col-title">{{ title }}</div>
    </div>

    <div class="table">
      <!-- 竖向滚动视口（右侧滚动条固定） -->
      <div ref="vscrollRef" class="vscroll" @scroll="handleVScroll">
        <!-- 内容横向滚动（隐藏其横向滚动条），表头/表体一起横向移动 -->
        <div ref="hcontentRef" class="hcontent" @scroll="handleHContentScroll">
          <div class="table-inner" :style="{ width: totalWidthPx + 'px' }">
            <div class="thead">
              <div
                v-for="col in columns"
                :key="col.key"
                class="th"
                :class="`c-${col.key}`"
                :style="colStyle(col)"
                :title="colTitle(col)"
                @click="onHeaderClick(col)"
              >
                <span class="th-text">{{ col.label }}</span>
                <span class="sort-ind">{{ sortMark(col) }}</span>
              </div>
            </div>

            <!-- 表体（虚拟列表）：不再自身滚动，跟随 vscroll -->
            <div class="tbody">
              <div :style="{ height: padTop + 'px' }"></div>

              <div
                v-for="row in visibleRows"
                :key="row.symbol"
                class="tr"
                :class="{ selected: isSelected(row.symbol) }"
                :style="{ height: rowHeightPx + 'px' }"
              >
                <div class="td c-check" :style="cellStyle('check')">
                  <input
                    type="checkbox"
                    :checked="isSelected(row.symbol)"
                    @change="$emit('toggle-select', row.symbol)"
                  />
                </div>

                <div class="td c-star" :style="cellStyle('star')">
                  <button
                    class="star-btn"
                    :class="{ active: isStarred(row.symbol) }"
                    :title="isStarred(row.symbol) ? '从自选移除' : '加入自选'"
                    @click="$emit('toggle-star', row.symbol)"
                  >
                    ★
                  </button>
                </div>

                <div class="td c-symbol" :style="cellStyle('symbol')">{{ row.symbol }}</div>
                <div class="td c-name" :style="cellStyle('name')" :title="row.name">{{ row.name }}</div>
                <div class="td c-market" :style="cellStyle('market')">{{ row.market }}</div>
                <div class="td c-class" :style="cellStyle('class')">{{ row.class }}</div>
                <div class="td c-type" :style="cellStyle('type')">{{ row.type }}</div>
                <div class="td c-listing" :style="cellStyle('listingDate')">{{ row.listingDateText }}</div>
                <div class="td c-updated" :style="cellStyle('updatedAt')" :title="row.updatedAt">{{ row.updatedAt }}</div>
              </div>

              <div :style="{ height: padBottom + 'px' }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部横向滚动条（固定在视口底部） -->
      <div ref="hbarRef" class="hbar" @scroll="handleHBarScroll">
        <div class="hbar-inner" :style="{ width: totalWidthPx + 'px' }"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useVirtualListFixedRow } from "@/composables/useVirtualListFixedRow";

const props = defineProps({
  title: { type: String, default: "标的列表" },
  rows: { type: Array, default: () => [] },

  isSelected: { type: Function, required: true },
  isStarred: { type: Function, required: true },

  sortKey: { type: String, default: "symbol" },
  sortDir: { type: String, default: "asc" },

  rowHeightPx: { type: Number, default: 28 },
  approxVisibleRows: { type: Number, default: 20 },

  initialColWidths: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["sort", "toggle-select", "toggle-star"]);

const vscrollRef = ref(null);
const hcontentRef = ref(null);
const hbarRef = ref(null);

// 列宽固定策略（不允许改列宽）
const columns = ref([
  { key: "check", label: "", sortable: true, min: 32, max: 90, default: 30, align: "center" },
  { key: "star", label: "自选", sortable: true, min: 40, max: 80, default: 48, align: "center" },
  { key: "symbol", label: "代码", sortable: true, min: 70, max: 140, default: 60, align: "center" },
  { key: "name", label: "名称", sortable: true, min: 120, max: 360, default: 120, align: "center" },
  { key: "market", label: "市场", sortable: true, min: 60, max: 120, default: 56, align: "center" },
  { key: "class", label: "类别", sortable: true, min: 70, max: 160, default: 56, align: "center" },
  { key: "type", label: "类型", sortable: true, min: 70, max: 160, default: 56, align: "center" },
  { key: "listingDate", label: "上市日期", sortable: true, min: 90, max: 150, default: 90, align: "center" },
  { key: "updatedAt", label: "更新时间", sortable: true, min: 140, max: 260, default: 190, align: "center" },
]);

function clamp(n, min, max) {
  const x = Math.floor(Number(n));
  if (!Number.isFinite(x)) return min;
  return Math.max(min, Math.min(max, x));
}

const colWidths = ref({});

function initColWidths() {
  const init = props.initialColWidths && typeof props.initialColWidths === "object" ? props.initialColWidths : {};
  const out = {};
  for (const c of columns.value) {
    const v = Number(init[c.key]);
    out[c.key] = Number.isFinite(v) ? clamp(v, c.min, c.max) : c.default;
  }
  colWidths.value = out;
}

initColWidths();

watch(
  () => props.initialColWidths,
  () => {
    initColWidths();
  },
  { deep: true }
);

function colStyle(col) {
  const w = colWidths.value[col.key] || col.default;
  return { width: `${w}px` };
}

function cellStyle(key) {
  const w = colWidths.value[key];
  return w ? { width: `${w}px` } : {};
}

const totalWidthPx = computed(() => {
  const cols = columns.value || [];
  let sum = 0;
  for (const c of cols) {
    const w = Number(colWidths.value?.[c.key] ?? c.default ?? 0);
    if (Number.isFinite(w) && w > 0) sum += w;
  }
  return Math.max(1, Math.floor(sum));
});

function sortMark(col) {
  const key = col.key === "check" ? "__selected__" : col.key === "star" ? "__starred__" : col.key;
  if (String(props.sortKey) !== String(key)) return "";
  return props.sortDir === "desc" ? "▼" : "▲";
}

function colTitle(col) {
  return col.sortable === false ? "" : "点击排序";
}

function onHeaderClick(col) {
  if (col.sortable === false) return;
  const key = col.key === "check" ? "__selected__" : col.key === "star" ? "__starred__" : col.key;
  emit("sort", key);
}

// ===== 虚拟滚动：使用 vscroll 的可视高度 - 表头高度 =====
const viewportHeight = ref(420);

// 表头高度（与 CSS 同步；不做动态测量，保持简单、确定）
const THEAD_H = 30;
const HBAR_H = 14;

function updateViewportHeight() {
  try {
    const h = vscrollRef.value?.clientHeight;
    if (Number.isFinite(+h) && +h > 0) {
      viewportHeight.value = Math.max(0, Math.floor(+h) - THEAD_H);
    }
  } catch {}
}

onMounted(() => {
  updateViewportHeight();
  window.addEventListener("resize", updateViewportHeight);
  // 初次对齐横向滚动位置
  syncHBarFromContent();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", updateViewportHeight);
});

const totalCountRef = computed(() => (Array.isArray(props.rows) ? props.rows.length : 0));

const { startIndex, endIndex, padTop, padBottom, onScroll } = useVirtualListFixedRow({
  totalCountRef,
  rowHeight: props.rowHeightPx,
  viewportHeightRef: viewportHeight,
  overscan: 8,
});

function handleVScroll(e) {
  onScroll(e);
}

// ===== 横向滚动同步（最小实现）=====
let syncing = false;

function syncHBarFromContent() {
  if (syncing) return;
  try {
    syncing = true;
    const left = hcontentRef.value?.scrollLeft || 0;
    if (hbarRef.value) hbarRef.value.scrollLeft = left;
  } finally {
    syncing = false;
  }
}

function syncContentFromHBar() {
  if (syncing) return;
  try {
    syncing = true;
    const left = hbarRef.value?.scrollLeft || 0;
    if (hcontentRef.value) hcontentRef.value.scrollLeft = left;
  } finally {
    syncing = false;
  }
}

function handleHContentScroll() {
  syncHBarFromContent();
}

function handleHBarScroll() {
  syncContentFromHBar();
}

const visibleRows = computed(() => {
  const a = Array.isArray(props.rows) ? props.rows : [];
  const s = startIndex.value;
  const e = endIndex.value;
  if (!a.length || e < s) return [];
  return a.slice(s, e + 1);
});
</script>

<style scoped>
.sut-wrap {
  display: flex;
  flex-direction: column;
  min-height: 0;
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

/* table */
.table {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

/* 竖向滚动视口：右侧滚动条固定在视口边缘 */
.vscroll {
  overflow-y: auto;
  overflow-x: hidden;
  height: 493px;
  min-height: 260px;
}

/* 内容横向滚动：隐藏其横向滚动条（横向滚动条由 hbar 统一显示） */
.hcontent {
  overflow-x: auto;
  overflow-y: hidden;
  min-height: 0;

  scrollbar-width: none;          /* Firefox */
  -ms-overflow-style: none;       /* IE/旧 Edge */
}
.hcontent::-webkit-scrollbar {
  display: none;                  /* Chrome/Safari */
}

/* 内层承载列布局（超宽时通过 hscroll 横向滚动） */
.table-inner {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* header（冻结） */
.thead {
  display: flex;
  align-items: center;
  border-bottom: 1px solid #2a2a2a;
  background: #141414;
  flex-shrink: 0;

  /* NEW: 冻结表头 */
  position: sticky;
  top: 0;
  z-index: 3;
}

.th {
  position: relative;
  height: 30px;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  padding: 0 8px;
  font-size: 12px;
  color: #bbb;
  user-select: none;
  cursor: pointer;
  border-right: 1px solid rgba(255, 255, 255, 0.04);
  box-sizing: border-box;
  overflow: hidden;
}

.th-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sort-ind {
  margin-left: 6px;
  color: #777;
  font-size: 11px;
  flex-shrink: 0;
}

/* body：不再滚动（滚动由 vscroll 统一承载） */
.tbody {
  overflow: hidden;
}

.tr {
  display: flex;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.tr:hover {
  background: rgba(43, 75, 126, 0.12);
}

.tr.selected {
  background: rgba(43, 75, 126, 0.18);
}

.td {
  padding: 0 8px;
  font-size: 12px;
  color: #ddd;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-right: 1px solid rgba(255, 255, 255, 0.02);
  box-sizing: border-box;
  height: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.c-check,
.c-star {
  justify-content: center;
}

.star-btn {
  width: 22px;
  height: 22px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: #888;
  cursor: pointer;
  font-size: 14px;
  line-height: 22px;
}

.star-btn:hover {
  border-color: #444;
  color: #bbb;
}

.star-btn.active {
  color: #f1c40f;
  border-color: rgba(241, 196, 15, 0.35);
  background: rgba(241, 196, 15, 0.08);
}

/* 底部横向滚动条：固定显示在视口底部 */
.hbar {
  height: 14px;
  overflow-x: auto;
  overflow-y: hidden;
  background: transparent;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}
.hbar-inner {
  height: 1px; /* 只为撑出横向滚动宽度 */
}
</style>
