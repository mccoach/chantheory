<!-- src/components/ui/SymbolUniverseTable.vue -->
<!-- ==============================
本轮重构目标：
- 表格仍保持“通用候选表”职责，不承载 local import 快选业务
- 列展示改为“可配置 schema”，从根因上消除旧版把 listingDateText 硬塞成 freq 的错位设计
- 默认行为保持兼容：未传 columns 时，使用原有通用列
- 新增 fileTime 列支持，供 local import 候选表显示“文件时间”
- 候选表勾选框统一接入全局 std-check 链路，和快选栏完全同构

本轮修复：
- 修复“数据区横向滚动时，标题栏/底部横向滚动条不同步”的错位问题
- 根因：原实现只处理了 hbar -> hcontent/thead 的单向同步，
        但缺少 hcontent -> hbar/thead 的反向同步链路
- 处理方式：
    1) 给 hcontent 增加 @scroll 监听
    2) 新增 syncHorizontalFromContent
    3) 继续使用 syncing 锁，避免双向同步造成递归抖动
============================== -->
<template>
  <div class="sut-wrap">
    <div class="col-head">
      <div class="col-title">{{ title }}</div>
    </div>

    <div class="table">
      <div class="thead-wrap">
        <div class="thead-h" ref="theadHRef">
          <div class="thead-inner" :style="{ width: totalWidthPx + 'px' }">
            <div
              v-for="col in normalizedColumns"
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
        </div>

        <div class="thead-spacer" :style="{ width: vScrollBarWidthPx + 'px' }"></div>
      </div>

      <div ref="vscrollRef" class="vscroll" @scroll="handleVScroll">
        <div ref="hcontentRef" class="hcontent" @scroll="handleHContentScroll">
          <div class="table-inner" :style="{ width: totalWidthPx + 'px' }">
            <div class="tbody">
              <div :style="{ height: padTop + 'px' }"></div>

              <div
                v-for="row in visibleRows"
                :key="rowKey(row)"
                class="tr"
                :class="{ selected: isSelected(row) }"
                :style="{ height: rowHeightPx + 'px' }"
              >
                <div
                  v-for="col in normalizedColumns"
                  :key="col.key"
                  class="td"
                  :class="`c-${col.key}`"
                  :style="cellStyle(col.key)"
                  :title="cellTitle(row, col)"
                >
                  <template v-if="col.key === 'check'">
                    <span class="std-check">
                      <input
                        type="checkbox"
                        :checked="isSelected(row)"
                        @change="$emit('toggle-select', row)"
                      />
                    </span>
                  </template>

                  <template v-else-if="col.key === 'star'">
                    <button
                      class="star-btn"
                      :class="{ active: isStarred(row) }"
                      :title="isStarred(row) ? '从自选移除' : '加入自选'"
                      @click="$emit('toggle-star', row)"
                    >
                      ★
                    </button>
                  </template>

                  <template v-else>
                    {{ cellValue(row, col) }}
                  </template>
                </div>
              </div>

              <div :style="{ height: padBottom + 'px' }"></div>
            </div>
          </div>
        </div>
      </div>

      <div ref="hbarRef" class="hbar" @scroll="handleHBarScroll">
        <div class="hbar-inner" :style="{ width: totalWidthPx + 'px' }"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from "vue";
import { useVirtualListFixedRow } from "@/composables/useVirtualListFixedRow";

const DEFAULT_COLUMNS = [
  { key: "check", label: "", sortable: true, min: 32, max: 90, default: 30, align: "center" },
  { key: "star", label: "自选", sortable: true, min: 40, max: 80, default: 48, align: "center" },
  { key: "symbol", label: "代码", sortable: true, min: 70, max: 140, default: 60, align: "center" },
  { key: "name", label: "名称", sortable: true, min: 120, max: 360, default: 120, align: "center" },
  { key: "market", label: "市场", sortable: true, min: 60, max: 120, default: 56, align: "center" },
  { key: "class", label: "类别", sortable: true, min: 70, max: 160, default: 56, align: "center" },
  { key: "type", label: "类型", sortable: true, min: 70, max: 180, default: 72, align: "center" },
  { key: "listingDateText", label: "上市日期", sortable: true, min: 90, max: 150, default: 90, align: "center" },
  { key: "updatedAt", label: "更新时间", sortable: true, min: 140, max: 260, default: 190, align: "center" },
];

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

  rowKeyBuilder: { type: Function, default: null },

  columns: { type: Array, default: () => [] },
});

const emit = defineEmits(["sort", "toggle-select", "toggle-star"]);

const vscrollRef = ref(null);
const hcontentRef = ref(null);
const hbarRef = ref(null);
const theadHRef = ref(null);
const vScrollBarWidthPx = ref(0);

function normalizeColumn(col) {
  const c = col && typeof col === "object" ? col : {};
  const key = String(c.key || "").trim();
  return {
    key,
    label: String(c.label ?? ""),
    sortable: c.sortable !== false,
    min: Number.isFinite(+c.min) ? +c.min : 40,
    max: Number.isFinite(+c.max) ? +c.max : 320,
    default: Number.isFinite(+c.default) ? +c.default : 80,
    align: String(c.align || "center"),
    field: c.field != null ? String(c.field) : key,
    titleField: c.titleField != null ? String(c.titleField) : null,
  };
}

const normalizedColumns = computed(() => {
  const raw = Array.isArray(props.columns) && props.columns.length
    ? props.columns
    : DEFAULT_COLUMNS;
  return raw
    .map(normalizeColumn)
    .filter((x) => x.key);
});

function clamp(n, min, max) {
  const x = Math.floor(Number(n));
  if (!Number.isFinite(x)) return min;
  return Math.max(min, Math.min(max, x));
}

const colWidths = ref({});

function initColWidths() {
  const init = props.initialColWidths && typeof props.initialColWidths === "object" ? props.initialColWidths : {};
  const out = {};
  for (const c of normalizedColumns.value) {
    const v = Number(init[c.key]);
    out[c.key] = Number.isFinite(v) ? clamp(v, c.min, c.max) : c.default;
  }
  colWidths.value = out;
}

watch(
  () => normalizedColumns.value,
  () => {
    initColWidths();
  },
  { immediate: true, deep: true }
);

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
  let sum = 0;
  for (const c of normalizedColumns.value) {
    const w = Number(colWidths.value?.[c.key] ?? c.default ?? 0);
    if (Number.isFinite(w) && w > 0) sum += w;
  }
  return Math.max(1, Math.floor(sum));
});

function sortKeyOfColumn(col) {
  const key = String(col?.key || "");
  if (key === "check") return "__selected__";
  if (key === "star") return "__starred__";
  return key;
}

function sortMark(col) {
  const key = sortKeyOfColumn(col);
  if (String(props.sortKey) !== String(key)) return "";
  return props.sortDir === "desc" ? "▼" : "▲";
}

function colTitle(col) {
  return col.sortable === false ? "" : "点击排序";
}

function onHeaderClick(col) {
  if (col.sortable === false) return;
  emit("sort", sortKeyOfColumn(col));
}

function rowKey(row) {
  try {
    if (typeof props.rowKeyBuilder === "function") {
      const k = String(props.rowKeyBuilder(row) || "").trim();
      if (k) return k;
    }
  } catch {}
  return String(row?.symbol || "");
}

function cellValue(row, col) {
  const field = String(col?.field || col?.key || "");
  const v = row?.[field];
  return v == null ? "" : v;
}

function cellTitle(row, col) {
  const titleField = col?.titleField ? String(col.titleField) : null;
  if (titleField) {
    const v = row?.[titleField];
    return v == null ? "" : String(v);
  }
  const v = cellValue(row, col);
  return v == null ? "" : String(v);
}

const viewportHeight = ref(463);

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

function updateVScrollBarWidth() {
  try {
    const el = vscrollRef.value;
    if (!el) return;
    const w = Math.max(0, Number(el.offsetWidth || 0) - Number(el.clientWidth || 0));
    vScrollBarWidthPx.value = Number.isFinite(w) ? Math.floor(w) : 0;
  } catch {}
}

let syncing = false;

function syncHorizontalFromHBar() {
  if (syncing) return;
  try {
    syncing = true;
    const left = hbarRef.value?.scrollLeft || 0;
    if (hcontentRef.value) hcontentRef.value.scrollLeft = left;
    if (theadHRef.value) theadHRef.value.scrollLeft = left;
  } finally {
    syncing = false;
  }
}

// NEW: 数据区横向滚动时，反向同步标题栏与底部滚动条
function syncHorizontalFromContent() {
  if (syncing) return;
  try {
    syncing = true;
    const left = hcontentRef.value?.scrollLeft || 0;
    if (hbarRef.value) hbarRef.value.scrollLeft = left;
    if (theadHRef.value) theadHRef.value.scrollLeft = left;
  } finally {
    syncing = false;
  }
}

function handleHBarScroll() {
  syncHorizontalFromHBar();
}

// NEW: 绑定到 hcontent 的横向滚动事件
function handleHContentScroll() {
  syncHorizontalFromContent();
}

function initHorizontalAlignment() {
  try {
    const left = hbarRef.value?.scrollLeft || 0;
    if (hcontentRef.value) hcontentRef.value.scrollLeft = left;
    if (theadHRef.value) theadHRef.value.scrollLeft = left;
  } catch {}
}

onMounted(() => {
  updateVScrollBarWidth();
  initHorizontalAlignment();
  window.addEventListener("resize", updateVScrollBarWidth);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", updateVScrollBarWidth);
});

watch(
  () => totalCountRef.value,
  async () => {
    await nextTick();
    updateVScrollBarWidth();
  }
);

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

.table {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.thead-wrap {
  display: flex;
  align-items: stretch;
  flex-shrink: 0;
  background: #141414;
  border-bottom: 1px solid #2a2a2a;
}

.thead-h {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.thead-inner {
  display: flex;
  align-items: center;
  height: 30px;
}

.thead-spacer {
  flex-shrink: 0;
  height: 30px;
  background: #141414;
}

.vscroll {
  overflow-y: auto;
  overflow-x: hidden;
  height: 463px;
  min-height: 260px;
}

.hcontent {
  overflow-x: auto;
  overflow-y: hidden;
  min-height: 0;

  scrollbar-width: none;
  -ms-overflow-style: none;
}
.hcontent::-webkit-scrollbar {
  display: none;
}

.table-inner {
  display: flex;
  flex-direction: column;
  min-height: 0;
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

.hbar {
  height: 14px;
  overflow-x: auto;
  overflow-y: hidden;
  background: transparent;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}
.hbar-inner {
  height: 1px;
}
</style>
