<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\SymbolPanel.vue -->
<!--
说明：标的输入与时间范围控制（热键全面适配版 · 逐行注释）
主要改动（让快捷键在该模块生效）：
- 注入 hotkeys；在输入框 focus/blur 时 pushScope/popScope("panel:symbol")，使该作用域键位映射有效。
- 注册 panel:symbol 的命令处理器：
  * dropdownNext / dropdownPrev / dropdownConfirm / dropdownClose 分别映射到现有方法，完全等效键盘操作。
- 监听全局事件 'chan:toggle-export-menu'，配合 App.vue 的 global.toggleExportMenu 实现 Alt+E 切换导出菜单。
- 为输入框增加 ref，便于 focus/blur 精准绑定；保留原有 onKeydown/输入行为，服务层优先捕获执行，二者不冲突。
-->
<template>
  <!-- 顶部标的/区间控制条 -->
  <div class="symbol-panel">
    <!-- 标的输入（联想下拉） -->
    <div class="symbol-wrap" ref="symbolWrapRef">
      <input
        ref="symbolInputRef"
        class="symbol-input"
        v-model="inputText"
        :placeholder="placeholder"
        v-select-all
        @focus="onFocus"
        @input="onInput"
        @keydown="onKeydown"
        @blur="onBlur"
        :class="{ invalid: invalidHint }"
      />
      <!-- 下拉建议列表 -->
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
      <!-- 无效提示 -->
      <div v-if="invalidHint" class="hint">{{ invalidHint }}</div>
    </div>

    <!-- 快捷区间 + 右侧操作（高级/刷新/导出） -->
    <div class="range-wrap">
      <!-- 快捷区间“连体按钮” -->
      <div class="seg seg-presets">
        <button
          v-for="p in presets"
          :key="p"
          class="seg-btn"
          :class="{ active: vm.rng.value.preset === p }"
          @click="onClickPreset(p)"
          :title="`快捷区间：${p}`"
        >
          {{ p }}
        </button>
      </div>

      <!-- 右侧操作：起止 | 高级 | 刷新 | 导出 -->
      <div class="right-actions">
        <!-- 当前起止时间 -->
        <div class="range-tip">
          起止：
          <span class="date">{{ vm.start.value || "-" }}</span>
          →
          <span class="date">{{ vm.end.value || "-" }}</span>
        </div>
        <!-- 高级 -->
        <button class="btn" @click="advancedOpen = !advancedOpen">
          {{ advancedOpen ? "关闭高级" : "高级" }}
        </button>
        <!-- 刷新 -->
        <button class="btn" @click="vm.reload()" :disabled="vm.loading.value">
          刷新
        </button>
        <!-- 导出（分体式按钮；菜单下拉） -->
        <div class="export-wrap" ref="exportWrapRef">
          <button
            class="btn"
            :disabled="disabledExport"
            @click="toggleExportMenu"
          >
            导出
          </button>
          <div v-if="exportOpen" class="menu">
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

    <!-- 高级面板 -->
    <div v-if="advancedOpen" class="advanced-panel">
      <div class="adv-row">
        <div class="label">手动日期</div>
        <input
          type="date"
          class="date-input"
          v-model="advStart"
          v-select-all
          :title="'开始日期（YYYY-MM-DD）'"
        />
        <span class="sep">至</span>
        <input
          type="date"
          class="date-input"
          v-model="advEnd"
          v-select-all
          :title="'结束日期（YYYY-MM-DD）'"
        />
        <button
          class="btn"
          @click="applyManualRange"
          :disabled="!canApplyManual"
        >
          应用
        </button>
      </div>
      <div class="adv-row">
        <div class="label">最近 N 根</div>
        <input
          class="bars-input"
          v-model="barsStr"
          placeholder="如 300（近似按天/周/月换算）"
        />
        <button class="btn" @click="applyBarsRange" :disabled="!canApplyBars">
          应用
        </button>
        <div class="hint">
          说明：按频率近似换算为日期窗口；严格对齐交易日可后续引入交易日历。
        </div>
      </div>
      <div class="adv-row">
        <div class="label">可见窗口</div>
        <div class="visible">
          <span class="date">{{ vm.rng.value.visible.startStr || "-" }}</span>
          →
          <span class="date">{{ vm.rng.value.visible.endStr || "-" }}</span>
          <button
            class="btn"
            @click="applyVisible"
            :disabled="!vm.rng.value.visible.startStr"
          >
            应用为数据窗口
          </button>
        </div>
      </div>
    </div>

    <!-- 错误显示 -->
    <div v-if="error" class="err">错误：{{ error }}</div>
  </div>
</template>

<script setup>
// Vue
import { inject, ref, computed, onMounted, onBeforeUnmount } from "vue"; // 注入/响应式/生命周期
// 注入市场视图与导出控制器
const vm = inject("marketView"); // 市场视图
const exportController = inject("exportController"); // 导出控制器
// 用户设置（持久化保存 lastSymbol/lastStart/lastEnd 等）
import { useUserSettings } from "@/composables/useUserSettings"; // 用户设置
const settings = useUserSettings(); // 实例
// 输入行为：聚焦全选
import { vSelectAll } from "@/utils/inputBehaviors"; // 指令
defineExpose(); // 暴露（无需额外成员）
defineOptions({ directives: { selectAll: vSelectAll } }); // 注册指令
// 热键服务
const hotkeys = inject("hotkeys", null); // 注入热键服务

// 标的索引与搜索
import { useSymbolIndex } from "@/composables/useSymbolIndex"; // 符号索引
const { ready, search, findBySymbol } = useSymbolIndex(); // API

// 占位与内部状态
const placeholder = "输入代码/拼音首字母（例：600519 或 gzymt）"; // 占位
const inputText = ref(settings.lastSymbol.value || vm.code.value || ""); // 输入文本
const symbolWrapRef = ref(null); // 输入容器 ref
const symbolInputRef = ref(null); // 新增：输入框 ref
const focused = ref(false); // 是否聚焦
const activeIndex = ref(-1); // 下拉高亮索引
const suggestions = ref([]); // 建议数组
const invalidHint = ref(""); // 无效提示

// 快捷区间列表（随 freq 动态）
const presets = computed(() => vm.getPresetsForCurrentFreq()); // 快捷预设

// 高级面板状态与输入
const advancedOpen = ref(false); // 高级开关
const advStart = ref(vm.start.value || ""); // 高级开始
const advEnd = ref(vm.end.value || ""); // 高级结束
const barsStr = ref(""); // 近 N 根

// 可应用判断
const canApplyManual = computed(() => true); // 手动恒可用
const canApplyBars = computed(() => /^\d+$/.test((barsStr.value || "").trim())); // N 为数字

// 右上导出相关
const exportWrapRef = ref(null); // 导出菜单容器
const exportOpen = ref(false); // 导出菜单开关
const disabledExport = computed(
  () => !!(vm.loading?.value || exportController?.exporting?.value)
); // 禁用逻辑
function toggleExportMenu() {
  // 切换导出菜单
  if (disabledExport.value) return; // 忙碌时不切换
  exportOpen.value = !exportOpen.value; // 翻转开关
}
async function doExport(targetId, format) {
  // 执行导出
  if (disabledExport.value) return; // 忙碌时返回
  const res = await exportController.export({ targetId, format }); // 调用控制器
  exportOpen.value = false; // 关闭菜单
  if (!res.ok) console.error("导出失败：", res.error); // 错误输出
}
function onDocClick(e) {
  // 文档点击关闭菜单
  if (
    exportOpen.value &&
    exportWrapRef.value &&
    !exportWrapRef.value.contains(e.target)
  ) {
    exportOpen.value = false; // 点击外部关闭
  }
}

// —— 联想下拉行为 ——
// 下拉可见性
const showSuggest = computed(
  () =>
    focused.value &&
    (inputText.value?.trim().length > 0 || suggestions.value.length > 0)
); // 显示条件
// 聚焦：打开建议 + 进入 panel:symbol 作用域
function onFocus() {
  focused.value = true; // 标记聚焦
  invalidHint.value = ""; // 清提示
  if (inputText.value?.trim()) updateSuggestions(); // 有输入 → 刷新建议
  if (hotkeys) hotkeys.pushScope("panel:symbol"); // 进入作用域
}
// 输入：更新建议
function onInput() {
  invalidHint.value = ""; // 清提示
  updateSuggestions(); // 刷新建议
}
// 键盘事件（本地备用；热键服务捕获后会优先执行命令处理，避免重复，但保留容错）
function onKeydown(e) {
  if (!showSuggest.value) return; // 无下拉时忽略
  if (e.key === "ArrowDown") {
    e.preventDefault();
    if (!suggestions.value.length) return;
    activeIndex.value =
      (activeIndex.value + 1 + suggestions.value.length) %
      suggestions.value.length;
    scrollActiveIntoView();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (!suggestions.value.length) return;
    activeIndex.value =
      (activeIndex.value - 1 + suggestions.value.length) %
      suggestions.value.length;
    scrollActiveIntoView();
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (
      activeIndex.value >= 0 &&
      activeIndex.value < suggestions.value.length
    ) {
      selectItem(suggestions.value[activeIndex.value]);
    } else {
      tryCommitByInput();
    }
  } else if (e.key === "Escape") {
    focused.value = false;
  }
}
// 失焦：关闭下拉 + 尝试提交 + 退出作用域
function onBlur() {
  setTimeout(() => {
    focused.value = false; // 失焦关闭下拉
    tryCommitByInput(); // 尝试提交
    if (hotkeys) hotkeys.popScope("panel:symbol"); // 退出作用域
  }, 0);
}
// 刷新建议列表
function updateSuggestions() {
  const q = inputText.value?.trim() || ""; // 查询串
  if (!q || !ready.value) {
    // 空或未就绪
    suggestions.value = []; // 清空
    activeIndex.value = -1; // 重置索引
    return; // 返回
  }
  suggestions.value = search(q, 20); // 搜索
  activeIndex.value = suggestions.value.length ? 0 : -1; // 高亮首项或重置
}
// 滚动高亮项进入可视区域
function scrollActiveIntoView() {
  const wrap = symbolWrapRef.value; // 容器
  if (!wrap) return;
  const list = wrap.querySelector(".dropdown"); // 下拉
  if (!list) return;
  const items = list.querySelectorAll(".suggest-item"); // 项集
  if (!items || !items.length) return;
  const el = items[activeIndex.value]; // 当前项
  if (el && typeof el.scrollIntoView === "function")
    el.scrollIntoView({ block: "nearest" }); // 滚动可见
}
// 选中下拉项
function selectItem(item) {
  inputText.value = item.symbol; // 输入框赋值
  vm.code.value = item.symbol; // 触发 useMarketView.watch(code) → reload
  settings.setLastSymbol(item.symbol); // 持久化
  invalidHint.value = ""; // 清提示
  suggestions.value = []; // 清下拉
  activeIndex.value = -1; // 重置高亮
  focused.value = false; // 关闭下拉
}
// 输入提交（按回车或失焦时尝试）
function tryCommitByInput() {
  const t = (inputText.value || "").trim(); // 文本
  if (!t) {
    invalidHint.value = "请输入标的代码或拼音首字母"; // 空值提示
    return;
  }
  let entry = findBySymbol(t); // 先按代码找
  if (!entry) {
    const arr = search(t, 1); // 再按拼音/中文找
    entry = arr[0];
  }
  if (entry) selectItem(entry); // 命中 → 选中
  else invalidHint.value = "无效标的，请重试"; // 否则提示
}

// —— 快捷/高级行为（点击立即刷新） ——
// 快捷区间
async function onClickPreset(p) {
  await vm.applyPreset(p); // 应用预设 → reload
  advStart.value = vm.start.value || ""; // 同步显示
  advEnd.value = vm.end.value || "";
}
// 手动日期
async function applyManualRange() {
  await vm.applyManual(advStart.value || "", advEnd.value || "");
}
// 最近 N 根
async function applyBarsRange() {
  const n = parseInt((barsStr.value || "").trim(), 10);
  if (Number.isFinite(n) && n > 0) {
    await vm.applyBars(n);
    advStart.value = vm.start.value || "";
    advEnd.value = vm.end.value || "";
  }
}
// 应用可见窗口
async function applyVisible() {
  await vm.applyVisibleAsDataWindow();
  advStart.value = vm.start.value || "";
  advEnd.value = vm.end.value || "";
}

// 错误文本（保留）
const error = ref(""); // 错误展示

// —— 热键服务接线（panel:symbol 与全局导出菜单事件） ——
// 注册 panel:symbol 命令处理器，使下拉键位（ArrowUp/Down/Enter/Escape）在输入环境也通过热键体系生效
if (hotkeys) {
  hotkeys.registerHandlers("panel:symbol", {
    dropdownNext() {
      // 下移一项
      if (!showSuggest.value || !suggestions.value.length) return;
      activeIndex.value =
        (activeIndex.value + 1 + suggestions.value.length) %
        suggestions.value.length;
      scrollActiveIntoView();
    },
    dropdownPrev() {
      // 上移一项
      if (!showSuggest.value || !suggestions.value.length) return;
      activeIndex.value =
        (activeIndex.value - 1 + suggestions.value.length) %
        suggestions.value.length;
      scrollActiveIntoView();
    },
    dropdownConfirm() {
      // 确认当前
      if (
        showSuggest.value &&
        activeIndex.value >= 0 &&
        activeIndex.value < suggestions.value.length
      ) {
        selectItem(suggestions.value[activeIndex.value]);
      } else {
        tryCommitByInput();
      }
    },
    dropdownClose() {
      // 关闭下拉
      focused.value = false;
      exportOpen.value = false;
    },
  });
}

// 监听全局事件 'chan:toggle-export-menu'（由 App.vue 的 global.toggleExportMenu 广播）
function onToggleExportEvent() {
  toggleExportMenu();
}

// 文档点击关闭导出菜单 & 监听全局菜单事件
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
/* 顶部控制条：输入 + 区间 + 右侧操作 */
.symbol-panel {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
} /* 外层布局 */

/* 标的输入区域 */
.symbol-wrap {
  position: relative;
  flex: 0 0 300px;
  min-width: 280px;
} /* 输入容器宽度与定位 */
.symbol-input {
  width: 100%;
  height: 36px;
  line-height: 36px;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 0 10px;
  outline: none;
} /* 输入框 */
.symbol-input.invalid {
  border-color: #a94442;
} /* 无效边框 */

/* 下拉建议列表 */
.dropdown {
  position: absolute;
  z-index: 20;
  top: 36px;
  left: 0;
  right: 0;
  max-height: 280px;
  overflow-y: auto;
  background: #1b1b1b;
  border: 1px solid #333;
  border-radius: 6px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
} /* 列表容器 */
.suggest-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  cursor: pointer;
  color: #ddd;
} /* 建议项 */
.suggest-item:hover,
.suggest-item.active {
  background: #2a2a2a;
} /* 悬浮/高亮 */
.suggest-item .left .code {
  font-weight: 600;
  margin-right: 8px;
} /* 代码加粗 */
.suggest-item .left .name {
  color: #ccc;
} /* 名称颜色 */
.suggest-item .right .meta {
  color: #999;
  font-size: 12px;
  margin-left: 8px;
} /* 右侧元信息 */
.no-data {
  color: #888;
  padding: 10px;
  text-align: center;
} /* 无数据时提示 */
.hint {
  color: #e67e22;
  font-size: 12px;
  margin-top: 4px;
} /* 无效提示 */

/* 区间和右侧操作区域 */
.range-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
} /* 占满剩余空间 */

/* 快捷区间“连体按钮”容器 */
.seg-presets {
  margin-left: 6px;
} /* 轻微右移分隔感 */

/* 快捷区间按钮组（连体） */
.seg {
  display: inline-flex;
  align-items: center;
  border: 1px solid #444;
  border-radius: 10px;
  overflow: hidden;
  background: #1a1a1a;
} /* 连体容器 */
.seg-btn {
  background: transparent;
  color: #ddd;
  border: none;
  padding: 8px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 14px;
  line-height: 20px;
  height: 36px;
  border-radius: 0;
} /* 按钮 */
.seg-btn + .seg-btn {
  border-left: 1px solid #444;
} /* 相邻分隔线 */
.seg-btn.active {
  background: #2b4b7e;
  color: #fff;
} /* 激活态 */

/* 右侧操作与起止展示 */
.right-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
} /* 右对齐 */
.range-tip {
  color: #bbb;
  font-size: 13px;
  user-select: none;
} /* 范围文本 */
.range-tip .date {
  color: #ddd;
} /* 日期高亮 */

/* 分体式按钮（与连体按钮一致高度/字号） */
.btn {
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 6px;
  padding: 8px 14px;
  height: 36px;
  font-size: 14px;
  color: #ddd;
  cursor: pointer;
} /* 按钮 */
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
} /* 禁用态 */

/* 导出菜单 */
.export-wrap {
  position: relative;
} /* 相对定位 */
.menu {
  position: absolute;
  top: 38px;
  right: 0;
  min-width: 140px;
  background: #1f1f1f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 6px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
  z-index: 20;
  overflow: hidden;
} /* 菜单 */
.item {
  padding: 8px 12px;
  cursor: pointer;
  white-space: nowrap;
} /* 菜单项 */
.item:hover {
  background: #2a2a2a;
} /* 悬浮高亮 */
.item.disabled {
  opacity: 0.5;
  pointer-events: none;
} /* 禁用项 */

/* 高级面板 */
.advanced-panel {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #161616;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 8px;
} /* 面板外观 */
.adv-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
} /* 行布局 */
.label {
  width: 72px;
  color: #bbb;
  font-size: 13px;
  text-align: right;
} /* 标签 */
.date-input {
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 6px 10px;
  outline: none;
} /* 日期输入 */
.bars-input {
  width: 140px;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 6px 10px;
  outline: none;
} /* 根数输入 */
.visible .date {
  color: #ddd;
} /* 可见窗口文本 */

/* 错误文本 */
.err {
  margin-top: 8px;
  color: #e74c3c;
  text-align: left;
} /* 错误提示 */
</style>
