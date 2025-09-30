<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\SymbolPanel.vue -->
<!--
说明：
- 统一交互规则：失焦即提交。按回车仅让输入框失焦（blur），提交逻辑统一在 onBlur 中执行；
  这样避免“回车提交一次、鼠标移到图上再次失焦又提交一次”的二次更新。
- 确认选择（selectItem）：无论标的是否与当前相同，都强制 vm.reload({ force: true })，确保数据刷新。
- 刷新按钮：先通过中枢汇总 Refresh，再强制 reload。
-->

<template>
  <div class="symbol-row">
    <!-- 左列：标的输入框（窄宽） -->
    <div class="col-left">
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
      <div v-if="showSuggest" class="dropdown" @wheel.passive>
        <div
          v-for="(item, i) in suggestions"
          :key="item.symbol + '_' + i"
          class="suggest-item"
          :class="{ active: i === activeIndex }"
          @mousedown.prevent="selectItem(item)"
        >
          <div class="left">
            <span class="code">{{ item.symbol }}</span>
            <span class="name">{{ item.name }}</span>
          </div>
          <div class="right">
            <span class="meta">{{ item.market }}</span>
            <span class="meta">{{ item.type }}</span>
          </div>
        </div>
        <div v-if="!suggestions.length" class="no-data">无匹配项</div>
      </div>
      <div v-if="invalidHint" class="hint">{{ invalidHint }}</div>
    </div>

    <!-- 中列：标的信息（不加边框与背景） -->
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
// —— 新增：显示状态中枢，用于将“刷新”动作汇总 —— //
import { useViewCommandHub } from "@/composables/useViewCommandHub";

defineOptions({ directives: { selectAll: vSelectAll } });

const vm = inject("marketView");
const hotkeys = inject("hotkeys", null);
const exportController = inject("exportController");
const settings = useUserSettings();
const { ready, search, findBySymbol } = useSymbolIndex();
const hub = useViewCommandHub(); // —— 新增：中枢单例 —— //

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

// 中列：标的信息（保持原逻辑）
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

// 导出控制（保持原逻辑）
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
function onDocClick(e) {
  if (
    exportOpen.value &&
    exportWrapRef.value &&
    !exportWrapRef.value.contains(e.target)
  ) {
    exportOpen.value = false;
  }
}

// 下拉建议交互（保持原逻辑）
const showSuggest = computed(
  () =>
    focused.value &&
    (inputText.value?.trim().length > 0 || suggestions.value.length > 0)
);
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
  // 1. 优先处理回车键，不再受下拉框是否显示的影响
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

// 失焦统一提交（尝试匹配并触发刷新），逻辑简洁一致
function onBlur() {
  setTimeout(() => {
    focused.value = false;
    tryCommitByInput(); // 统一在失焦提交
    if (hotkeys) hotkeys.popScope("panel:symbol");
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

// 确认选择：无论是否变更，强制刷新
function selectItem(item) {
  inputText.value = item.symbol;
  vm.code.value = item.symbol;
  settings.setLastSymbol(item.symbol);
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

// —— 新增：刷新按钮行为 —— //
// 说明：将“刷新”作为一个动作汇总到中枢（Refresh），然后触发 vm.reload({force:true})。
// bars/rightTs 不变，符合规则 9。
function onRefreshClick() {
  try {
    hub.execute("Refresh", {});
  } catch {}
  vm.reload?.({ force: true });
}

function onToggleExportEvent() {
  toggleExportMenu();
}
onMounted(() => {
  document.addEventListener("click", onDocClick);
  window.addEventListener("chan:toggle-export-menu", onToggleExportEvent);
});
onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick);
  window.removeEventListener("chan:toggle-export-menu", onToggleExportEvent);
});
</script>

<style scoped>
/* 保持原样式 */
.symbol-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  column-gap: 12px;
}
.col-left {
  position: relative;
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
.dropdown {
  position: absolute;
  z-index: 20;
  top: 38px;
  left: 0;
  right: 0;
  max-height: 280px;
  overflow-y: auto;
  background: #1b1b1b;
  border: 1px solid #333;
  border-radius: 6px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
}
.suggest-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  cursor: pointer;
  color: #ddd;
}
.suggest-item:hover,
.suggest-item.active {
  background: #2a2a2a;
}
.suggest-item .left .code {
  font-weight: 600;
  margin-right: 8px;
}
.suggest-item .left .name {
  color: #ccc;
}
.suggest-item .right .meta {
  color: #999;
  font-size: 12px;
  margin-left: 8px;
}
.no-data {
  color: #888;
  padding: 10px;
  text-align: center;
}
.hint {
  color: #e67e22;
  font-size: 12px;
  margin-top: 4px;
}
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
  z-index: 20;
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
.err {
  margin-top: 8px;
  color: #e74c3c;
  text-align: left;
}
</style>
