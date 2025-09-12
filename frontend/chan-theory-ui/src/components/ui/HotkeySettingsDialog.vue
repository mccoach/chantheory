<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\ui\HotkeySettingsDialog.vue -->
<!--
说明（集中式设置弹窗用“内容组件”版本 · 逐行注释）：
- 本组件仅负责“快捷键设置面板的内容”，不再包含遮罩/弹窗外壳；外壳由全局 ModalDialog 统一渲染。
- 与 App.vue 的配合：
  * App.vue 通过 dialogManager.open 打开本组件作为内容；
  * ModalDialog 的“保存/关闭”按钮会触发 App.vue 的 handleModalSave/handleModalClose；
  * 为避免 App.vue 必须显式调用 save()，本组件在卸载 onBeforeUnmount 时也会执行 save()，确保用户修改不会丢失。
- 交互：
  * 点击输入框后按新的组合键可改绑（组合键采集规则与 core.js 一致：Ctrl/Meta/Alt/Shift + 键位码）。
  * Esc 取消当前输入框的采集；Enter 确认当前输入框采集的组合键。
- 数据流：
  * 默认绑定来自 HotkeyService（默认映射 + 用户覆盖合并后的“命令→组合”映射）。
  * 保存：将草稿转换为 “组合→命令（按 scope 分类）” 的 overrides 写入用户设置与 HotkeyService。
- 重要：
  * 这是“内容组件”，外壳按钮（保存/关闭）在 ModalDialog 中；本组件暴露 save() 以便 App.vue 在按下“保存并应用”时调用（defineExpose）。
  * 同时在 onBeforeUnmount 自动执行一次 save()（简化使用场景，避免外层未调用 save 导致修改丢失）。
-->

<template>
  <!-- 外层包裹，仅负责排版（非遮罩/非弹窗） -->
  <div class="settings-content">
    <!-- 顶部说明 -->
    <div class="desc">
      提示：点击某项的快捷键框，然后按下新的组合键以修改。Esc 取消当前采集，Ctrl/Cmd+Enter 确认保存。
    </div>

    <!-- 遍历作用域（global / panel:symbol / panel:mainChart / modal:settings / ...） -->
    <div v-for="scope in scopes" :key="scope" class="scope">
      <!-- 作用域标题 -->
      <div class="scope-title">{{ scope }}</div>
      <!-- 遍历作用域下的命令（显示为：命令中文名称 + 输入框） -->
      <div
        class="row"
        v-for="(label, cmd) in labelsForScope(scope)"
        :key="scope + '-' + cmd"
      >
        <!-- 命令中文名称 -->
        <div class="cmd">{{ label }}</div>
        <!-- 组合键输入框（只读，靠键盘事件采集） -->
        <input
          class="combo"
          :value="draftBindings[scope]?.[cmd] || ''"    <!-- 显示当前草稿中的“命令→组合” -->
          readonly                                      <!-- 只读：避免软键盘输入干扰 -->
          @focus="startCapture(scope, cmd, $event)"     <!-- 聚焦开始采集（选中） -->
          @keydown.prevent="captureKey(scope, cmd, $event)" <!-- 捕获按键组合（阻止默认） -->
          @blur="stopCapture(scope, cmd, false)"        <!-- 失焦：若无 keep 则恢复为原值 -->
        />
      </div>
    </div>
  </div>
</template>

<script setup>
// ==============================
// 脚本 · 逐行注释
// ==============================

import { inject, reactive, ref, onMounted, onBeforeUnmount } from "vue"; // Vue 组合式 API
import { defaultKeymap, commandLabels } from "@/interaction/hotkeys/presets"; // 默认键位映射 + 命令中文名
import { useUserSettings } from "@/composables/useUserSettings";             // 用户设置（Local-first）

// 注入全局 HotkeyService（在 main.js 的快捷键插件中提供）
const hotkeys = inject("hotkeys");               // 全局热键服务（含 getBindings/setUserOverrides 等）
const settings = useUserSettings();              // 用户设置（持久化 hotkeyOverrides）

// 草稿：命令→组合（按 scope 分类），形如：{ global: { confirm: "Ctrl+Enter", ... }, ... }
const draftBindings = reactive({});              // 使用 reactive 方便表单联动更新

// 要展示的作用域列表（来自默认映射的键集合）
const scopes = Object.keys(defaultKeymap);       // 如 ["global","panel:symbol","panel:mainChart","modal:settings",...]

/**
 * 初始化草稿：从 HotkeyService 合并映射中获取“命令→组合”，写入 draftBindings。
 * - HotkeyService.getBindings(scope) 返回“命令→组合”的合并视图（默认 + 用户覆盖）。
 */
function initDraft() {
  scopes.forEach((s) => {
    draftBindings[s] = draftBindings[s] || {};                     // 确保 scope 键存在
    const mergedCmdToCombo = hotkeys.getBindings(s);               // 读取合并后的命令→组合
    Object.keys(mergedCmdToCombo).forEach((cmd) => {
      draftBindings[s][cmd] = mergedCmdToCombo[cmd];               // 写入草稿
    });
  });
}

/**
 * 将某个作用域的命令映射为“命令中文名称”（用于行左侧展示）
 * - 依赖 commandLabels（中文名映射），若缺失则回退为命令键名。
 */
function labelsForScope(scope) {
  // 当前 scope 的命令→组合视图
  const combos = hotkeys.getBindings(scope);
  const out = {};
  Object.keys(combos).forEach((cmd) => {
    out[cmd] = commandLabels[cmd] || cmd;                          // 显示友好的中文说明
  });
  return out;
}

// 当前处于采集状态的输入框（scope/cmd），用于 Esc/Enter 控制
const capturing = ref({ scope: "", cmd: "" });

/**
 * 开始采集：输入框聚焦时触发，选择内容并记录“当前采集对象”
 */
function startCapture(scope, cmd, ev) {
  capturing.value = { scope, cmd };   // 标记当前采集的 scope/cmd
  ev.target.select?.();               // 选中全部文本，便于用户确认
}

/**
 * 将 KeyboardEvent 规范化为组合键字符串
 * - 与 hotkeys/core.js 的规范保持一致（稳定）
 * - 优先使用 e.code 区分物理键位（Digit1/KeyA等），增强稳定性
 */
function comboFromEvent(e) {
  const parts = [];
  if (e.ctrlKey) parts.push("Ctrl");              // Ctrl
  if (e.metaKey) parts.push("Meta");              // Meta（Mac Command）
  if (e.altKey) parts.push("Alt");                // Alt
  if (e.shiftKey) parts.push("Shift");            // Shift
  const key = e.code || e.key;                    // 主键使用 code（若不存在回退 key）
  parts.push(key);
  return parts.join("+");                         // 组合为 “Ctrl+Shift+Digit1” 等
}

/**
 * 采集按键：
 * - Escape：取消采集（恢复原值）
 * - Enter：确认采集（保留当前值）
 * - 其它键：生成组合键字符串写入草稿
 */
function captureKey(scope, cmd, e) {
  // Esc：取消本次采集，恢复为 HotkeyService 返回的当前绑定
  if (e.key === "Escape") {
    stopCapture(scope, cmd, false);
    return;
  }
  // Enter：确认当前值（保持草稿中的值），结束采集
  if (e.key === "Enter") {
    stopCapture(scope, cmd, true);
    return;
  }
  // 其它键：生成组合键写入草稿
  draftBindings[scope][cmd] = comboFromEvent(e);
}

/**
 * 结束采集
 * @param scope  作用域
 * @param cmd    命令
 * @param keep   true=保留当前草稿；false=恢复为 HotkeyService 的合并值
 */
function stopCapture(scope, cmd, keep) {
  if (!keep && !draftBindings[scope][cmd]) {
    // 如果用户取消且当前草稿为空，则恢复 HotkeyService 合并值
    const merged = hotkeys.getBindings(scope);
    draftBindings[scope][cmd] = merged[cmd] || "";
  }
  // 清空“当前采集”标记
  capturing.value = { scope: "", cmd: "" };
}

/**
 * 保存（暴露给外部 ModalDialog 的“保存并应用”按钮，以及 onBeforeUnmount 调用）
 * - 将“命令→组合（draftBindings）”转换为“组合→命令（overrides）”
 * - 写入到用户设置（settings.setHotkeyOverrides）与 HotkeyService（setUserOverrides）
 */
function save() {
  // 构造 overrides：{ scope: { "Ctrl+Enter": "confirm", ... }, ... }
  const overrides = {};
  scopes.forEach((s) => {
    overrides[s] = overrides[s] || {};
    Object.keys(draftBindings[s] || {}).forEach((cmd) => {
      const combo = draftBindings[s][cmd];
      if (combo) overrides[s][combo] = cmd;
    });
  });
  // 写入用户设置（本地持久化）与 HotkeyService（立即生效）
  settings.setHotkeyOverrides(overrides);
  hotkeys.setUserOverrides(overrides);
}

// 将 save 暴露给父组件（App.vue 中可通过 ref 调用 dialogBodyRef.value.save()）
defineExpose({ save });

// 挂载：初始化草稿
onMounted(() => {
  initDraft();
});

// 卸载：安全保存一次（防外层未调用 save 导致修改丢失）
onBeforeUnmount(() => {
  try { save(); } catch {} // 忽略异常，保证不阻断关闭流程
});
</script>

<style scoped>
/* 容器：仅负责本面板的排版 */
.settings-content {
  display: flex;            /* 垂直布局 */
  flex-direction: column;
  gap: 10px;                /* 行距 */
}

/* 顶部说明文案 */
.desc {
  color: #aaa;
  font-size: 12px;
}

/* 每个作用域的包裹 */
.scope {
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 8px;
}

/* 作用域标题 */
.scope-title {
  color: #bbb;
  margin-bottom: 6px;
  font-size: 13px;
}

/* 每一行（命令 + 组合键输入） */
.row {
  display: grid;
  grid-template-columns: 1fr 220px; /* 左：命令中文；右：输入框 */
  gap: 8px;
  align-items: center;
  padding: 4px 0;
}

/* 命令中文名称样式 */
.cmd {
  color: #ddd;
}

/* 组合键输入框样式（只读，但可聚焦采集） */
.combo {
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 6px 8px;
}
</style>
