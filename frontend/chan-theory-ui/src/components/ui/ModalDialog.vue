<!-- src/components/ui/ModalDialog.vue -->
<!-- 通用弹窗外壳：统一遮罩/布局/样式/快捷键

     V3.4 - footer-left 插槽（布局能力）
     - 壳只提供"底栏左侧区域"的布局容器；业务内容由 slot 提供。
     - 为保证布局稳定（不跳动），footer-left 容器始终存在；slot 无内容时显示为空。
-->
<template>
  <div v-if="show" class="modal-mask" @click.self="close">
    <div class="modal-dialog" role="dialog" aria-modal="true">
      <div class="head">
        <div class="title">{{ title }}</div>
        <div class="head-right">
          <div v-if="tabs && tabs.length" class="tabs-group">
            <button
              v-for="t in tabs"
              :key="t.key"
              class="tab-btn"
              :class="{ active: t.key === activeTab }"
              @click="$emit('tab-change', t.key)"
              type="button"
            >
              {{ t.label }}
            </button>
          </div>
          <button class="x" @click="close" aria-label="关闭" type="button">
            ×
          </button>
        </div>
      </div>

      <div class="body">
        <slot name="body"></slot>
      </div>

      <div v-if="hasFooter" class="foot">
        <!-- 左侧：业务自定义 footer-left（容器始终存在，保证结构稳定） -->
        <div class="foot-left">
          <slot name="footer-left"></slot>
        </div>

        <!-- 右侧：统一 footerActions -->
        <div v-if="footerActions && footerActions.length" class="actions">
          <button
            v-for="act in footerActions"
            :key="act.key || act.label"
            class="btn"
            :class="btnClass(act)"
            type="button"
            :disabled="!!act.disabled"
            :title="act.title || ''"
            @click="emitAction(act)"
          >
            {{ act.label }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  show: { type: Boolean, required: true },
  title: { type: String, default: "设置" },
  tabs: { type: Array, default: () => [] },
  activeTab: { type: String, default: "" },
  footerActions: { type: Array, default: () => [] },
});

const emit = defineEmits(["close", "tab-change", "action"]);

function close() {
  emit("close");
}

function hasMeaningfulFooter(arr) {
  const a = Array.isArray(arr) ? arr : [];
  return a.length > 0;
}

const hasFooter = hasMeaningfulFooter(props.footerActions);

function btnClass(act) {
  const v = String(act?.variant || "").toLowerCase();
  if (v === "ok" || v === "primary") return "ok";
  if (v === "danger") return "danger";
  return "";
}

function emitAction(act) {
  emit("action", act);
}
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  backdrop-filter: blur(1px);
}

.modal-dialog {
  width: 1080px;
  background: #1b1b1b;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 24px #141414;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid #333;
  flex-shrink: 0;
}

.head .title {
  font-weight: 600;
}

.head .head-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.tabs-group {
  display: inline-flex;
  align-items: center;
  border: 1px solid #444;
  border-radius: 8px;
  overflow: hidden;
  background: #1a1a1a;
}

.tab-btn {
  background: transparent;
  color: #ddd;
  border: none;
  padding: 6px 12px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  line-height: 1;
  height: 26px;
  border-radius: 0;
  box-shadow: none;
}

.tab-btn + .tab-btn {
  border-left: 1px solid #444;
}

.tab-btn.active {
  background: #2b4b7e;
  color: #fff;
}

.x {
  background: #333;
  border: 1px solid #444;
  border-radius: 4px;
  color: #ddd;
  padding: 2px 8px;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

.body {
  padding: 0px 30px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid #333;
  flex-shrink: 0;
}

.foot-left {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
}

/* 关键修复：按钮区强制贴右 */
.actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}

.btn {
  background: #2a2a2a;
  color: #ddd;
  border: 1px solid #444;
  border-radius: 4px;
  padding: 6px 10px;
  cursor: pointer;
}

.btn.ok {
  background: #2b4b7e;
  border-color: #444444;
  color: #fff;
}

.btn.danger {
  background: #5a2323;
  border-color: #744;
  color: #fff;
}

/* ==============================
   统一 hover 高亮（不改背景色）
   - tabs：用 inset box-shadow（避免裁剪）
   - footer btn / x：用 outline（简单清晰）
   ============================== */

.tab-btn:hover:not(:disabled),
.tab-btn:focus-visible {
  box-shadow: inset 0 0 0 2px #5b7fb3;
}

.btn,
.x {
  outline: none;
}

.btn:hover:not(:disabled),
.x:hover:not(:disabled) {
  outline: 2px solid #5b7fb3;
  outline-offset: 1px;
}

.btn:focus-visible,
.x:focus-visible {
  outline: 2px solid #5b7fb3;
  outline-offset: 1px;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ============================= */
/* std-* 样式保持原样（未调序） */
/* ============================= */

:deep(.std-row) {
  display: grid;
  grid-template-columns: 100px repeat(6, 135px) 30px 30px;
  align-items: center;
  justify-items: center;
  column-gap: 8px;
  min-height: 36px;
}

:deep(.std-name) {
  justify-self: start;
  font-weight: 600;
}

:deep(.std-item) {
  display: flex;
  align-items: center;
  gap: 0;
}

:deep(.std-item-label) {
  width: 75px;
  text-align: right;
  color: #bbb;
  font-size: 12px;
  padding-right: 4px;
  box-sizing: border-box;
}

:deep(.std-item-input) {
  width: 60px;
  display: flex;
  align-items: center;
}
:deep(.std-item-input > input),
:deep(.std-item-input > select) {
  width: 100%;
  box-sizing: border-box;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 4px 6px;
}

:deep(.std-item-input .numspin) {
  display: inline-flex;
  align-items: center;
  width: 100%;
  height: 28px;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 4px;
  box-sizing: border-box;
}
:deep(.std-item-input .numspin.disabled) {
  opacity: 0.6;
  cursor: not-allowed;
}
:deep(.std-item-input .numspin .numspin-input) {
  flex-grow: 1;
  width: 1px;
  height: 100%;
  background: transparent;
  color: #ddd;
  border: none;
  outline: none;
  padding: 0px 0px 0px 10px;
  box-sizing: border-box;
  text-align: left;
}
:deep(.std-item-input .numspin .numspin-arrows) {
  display: flex;
  flex-direction: column;
  width: 18px;
  height: 100%;
  flex-shrink: 0;
  opacity: 0;
  visibility: hidden;
  transition: opacity 120ms ease;
}
:deep(.std-item-input .numspin:hover .numspin-arrows) {
  opacity: 1;
  visibility: visible;
}
:deep(.std-item-input .numspin .arrow) {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  position: relative;
}
:deep(.std-item-input .numspin .arrow.disabled) {
  cursor: not-allowed;
  opacity: 0.5;
}
:deep(.std-item-input .numspin .arrow:hover) {
  background-color: #333;
}
:deep(.std-item-input .numspin .arrow.up::before) {
  content: "";
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-bottom: 5px solid #aaa;
}
:deep(.std-item-input .numspin .arrow.down::before) {
  content: "";
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid #aaa;
}

:deep(.std-reset) {
  width: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.std-reset > .btn.icon) {
  position: relative;
  width: 26px;
  height: 26px;
  padding: 0;
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
:deep(.std-reset > .btn.icon:hover) {
  border-color: #5b7fb3;
  background: #2f3d55;
}

:deep(.std-reset > .btn.icon)::before {
  content: "";
  width: var(--reset-icon-size, 18px);
  height: var(--reset-icon-size, 18px);
  background-color: var(--reset-icon-color, #cfcfcf);
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
  -webkit-mask-image: url('data:image/svg+xml;utf8,<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="%23000" d="M12 5V2l-4 4 4 4V7c2.76 0 5 2.24 5 5a5 5 0 1 1-8.66-3.54l-1.42-1.42A7 7 0 1 0 19 12c0-3.87-3.13-7-7-7z"/></svg>');
  mask-image: url('data:image/svg+xml;utf8,<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="%23000" d="M12 5V2l-4 4 4 4V7c2.76 0 5 2.24 5 5a5 5 0 1 1-8.66-3.54l-1.42-1.42A7 7 0 1 0 19 12c0-3.87-3.13-7-7-7z"/></svg>');
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center;
  mask-position: center;
  -webkit-mask-size: contain;
  mask-size: contain;
}

:deep(.std-reset > .btn.icon > svg),
:deep(.std-reset > .btn.icon > span) {
  pointer-events: none;
}
</style>
