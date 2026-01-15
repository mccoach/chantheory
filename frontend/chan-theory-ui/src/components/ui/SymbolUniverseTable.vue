<!-- src/components/ui/SymbolUniverseTable.vue -->
<!-- ==============================
本轮修正目标（按你的“最高原则”执行）：
- 总尺寸不变：整体表格区高度=原值不变（表头30px + 表体滚动区463px = 原 vscroll 493px），hbar 14px 不变
- 逻辑拉直：横向滚动仅允许一个入口（底部 hbar）；表头/内容区都只被动跟随 hbar.scrollLeft
- 竖向滚动仅覆盖表体：vscroll 只滚动 body，不含表头
- 表头右侧滚动条等宽占位：用一次性测量 vscroll scrollbar 宽度对齐
- 去高频/去绕弯：不在 scrollTop 时测 scrollbar 宽度；不让表头自身滚动；同步只做单向（hbar -> others）
============================== -->
<template>
  <div class="sut-wrap">
    <div class="col-head">
      <div class="col-title">{{ title }}</div>
    </div>

    <div class="table">
      <!-- 冻结表头（不在竖向滚动范围内） -->
      <div class="thead-wrap">
        <!-- 表头横向展示区：不允许用户横向滚动，只被动跟随 hbar -->
        <div class="thead-h" ref="theadHRef">
          <div class="thead-inner" :style="{ width: totalWidthPx + 'px' }">
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
        </div>

        <!-- 表头右侧滚动条占位：宽度=竖向滚动条宽度 -->
        <div class="thead-spacer" :style="{ width: vScrollBarWidthPx + 'px' }"></div>
      </div>

      <!-- 竖向滚动视口（仅表体，滚动条固定在右侧） -->
      <div ref="vscrollRef" class="vscroll" @scroll="handleVScroll">
        <!-- 内容横向滚动容器：仍隐藏其横向滚动条，但不再作为“入口”，只被动接受 hbar 同步 -->
        <div ref="hcontentRef" class="hcontent">
          <div class="table-inner" :style="{ width: totalWidthPx + 'px' }">
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

      <!-- 底部横向滚动条（固定显示在视口底部；唯一入口） -->
      <div ref="hbarRef" class="hbar" @scroll="handleHBarScroll">
        <div class="hbar-inner" :style="{ width: totalWidthPx + 'px' }"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from "vue";
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

// 表头展示容器（非滚动入口，仅用于被动设置 scrollLeft）
const theadHRef = ref(null);

// 竖向滚动条宽度（表头右侧占位）
const vScrollBarWidthPx = ref(0);

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

// ===== 虚拟滚动：表体视口高度固定（总尺寸不变约束的关键）=====
// 旧：vscroll(493) 内含表头30 => body viewport=463
// 新：表头拆出 => vscroll 仅表体，直接固定为 463
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

// ===== 竖向滚动条宽度测量（只在必要时测）=====
function updateVScrollBarWidth() {
  try {
    const el = vscrollRef.value;
    if (!el) return;
    const w = Math.max(0, Number(el.offsetWidth || 0) - Number(el.clientWidth || 0));
    vScrollBarWidthPx.value = Number.isFinite(w) ? Math.floor(w) : 0;
  } catch {}
}

// ===== 横向滚动：唯一入口 hbar；单向同步到 hcontent + thead =====
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

function handleHBarScroll() {
  syncHorizontalFromHBar();
}

// 初始化：按当前 hcontent 或 hbar 位置对齐（优先 hbar，作为唯一入口）
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

// rows 数量变化可能导致“是否出现竖向滚动条”变化：下一拍重测一次宽度
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

/* table */
.table {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

/* 表头冻结区（独立） */
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
  overflow: hidden; /* 表头不作为滚动入口 */
}

.thead-inner {
  display: flex;
  align-items: center;
  height: 30px;
}

/* 表头右侧滚动条占位 */
.thead-spacer {
  flex-shrink: 0;
  height: 30px;
  background: #141414;
}

/* 竖向滚动视口：仅表体，固定高度 463px（保持总尺寸不变） */
.vscroll {
  overflow-y: auto;
  overflow-x: hidden;
  height: 463px;
  min-height: 260px;
}

/* 内容横向滚动：隐藏自身横向滚动条（由底部 hbar 统一入口） */
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

/* 表头单元格 */
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

/* 底部横向滚动条：固定显示在视口底部（不改实现方式） */
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
