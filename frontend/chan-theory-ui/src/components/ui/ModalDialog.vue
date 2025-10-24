<!-- src/components/ui/ModalDialog.vue -->
<!-- 通用设置弹窗外壳：统一遮罩/布局/样式/快捷键
     修复：
     1) 重置按钮图形定位问题：为 .std-reset > .btn.icon 增加 position: relative，使 ::before 绝对定位相对按钮本身；
        同时为 ::before 增加 pointer-events: none，避免覆盖点击区域。
     2) 其他保持原样。 -->
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

      <div class="foot">
        <div style="flex: 1"></div>
        <button class="btn" @click="resetAll" type="button">
          全部恢复默认
        </button>
        <button class="btn ok" @click="save" type="button">保存并关闭</button>
        <button class="btn" @click="close" type="button">取消</button>
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
});
const emit = defineEmits(["close", "save", "tab-change", "reset-all"]); // NEW: 声明 reset-all
function close() {
  emit("close");
}
function save() {
  emit("save");
}
function resetAll() {
  emit("reset-all");
}
</script>

<style scoped>
/* 基础弹窗外观 */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}
.modal-dialog {
  width: 960px;
  background: #1b1b1b;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
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
}
.tab-btn + .tab-btn {
  border-left: 1px solid #444;
}
.tab-btn.active {
  background: #2b4b7e;
  color: #fff;
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
  border-color: #3c5f91;
  color: #fff;
}

/* ============================= */
/* 统一设置行的唯一有效样式（集中在 ModalDialog）
   说明：
   - 不再在其他组件重复定义 .std-* 或数字框样式，避免冲突；
   - 列宽严格遵循：第1列 90px；第2~6列每列 140px（标签60 + 输入80）；倒数2列各30px；
   - 数字输入（含上下箭头）整体宽度固定 80px（在 .std-item-input 内实现）。 */
/* ============================= */

/* 每行栅格（90）+ 5*(140) +（30）+（30） */
:deep(.std-row) {
  display: grid;
  grid-template-columns: 90px repeat(5, 140px) 30px 30px;
  align-items: center;
  justify-items: center;
  column-gap: 8px;
  min-height: 36px;
}

/* 第1列：行名 */
:deep(.std-name) {
  justify-self: start;
  font-weight: 600;
}

/* 第2~6列：每列 140px，由标签 60 + 输入 80 构成；不要在子项再规定宽度 */
:deep(.std-item) {
  display: flex;
  align-items: center;
  gap: 0; /* 关键：60 + 80 = 140，gap 必须为 0 */
}

/* 标签固定 60px */
:deep(.std-item-label) {
  width: 70px;
  text-align: right;
  color: #bbb;
  font-size: 12px;
  padding-right: 4px;
  box-sizing: border-box;
}

/* 输入容器固定 80px（数字输入整体宽度=80，含箭头） */
:deep(.std-item-input) {
  width: 70px;
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

/* ===== NEW: 数字输入框悬浮箭头样式 ===== */
:deep(.std-item-input .numspin) {
  display: inline-flex;
  align-items: center;
  width: 100%; /* 占满 .std-item-input（80px） */
  height: 28px;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 4px;
  box-sizing: border-box; /* 边框计入宽度，保证总宽 80 */
  /* overflow: hidden;       /* 防止内部溢出 */
}
:deep(.std-item-input .numspin.disabled) {
  opacity: 0.6;
  cursor: not-allowed;
}
:deep(.std-item-input .numspin .numspin-input) {
  flex-grow: 1; /* 占据剩余空间 */
  width: 1px;
  height: 100%;
  background: transparent; /* 背景设为透明，以显示外层容器的背景 */
  color: #ddd;
  border: none; /* 移除原生边框，这是最关键的一步 */
  outline: none; /* 移除聚焦时的轮廓 */
  padding: 0px 0px 0px 10px;
  box-sizing: border-box;
  text-align: left; /* 文本居中 */
}
/* 箭头容器默认隐藏，悬浮时显示 */
:deep(.std-item-input .numspin .numspin-arrows) {
  display: flex;
  flex-direction: column;
  width: 18px; /* 固定宽度，避免布局跳动 */
  height: 100%;
  flex-shrink: 0;
  opacity: 0; /* 默认透明 */
  visibility: hidden; /* 默认不可见 */
  transition: opacity 120ms ease;
}
:deep(.std-item-input .numspin:hover .numspin-arrows) {
  opacity: 1; /* 悬浮时显示 */
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
/* 使用伪元素绘制箭头形状 */
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

/* 统一复选框外观 */
:deep(.std-check) {
  width: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}
:deep(.std-check input[type="checkbox"]) {
  appearance: none;
  width: 16px;
  height: 16px;
  border: 1px solid #555;
  border-radius: 3px;
  background: #0f0f0f;
  position: relative;
  cursor: pointer;
  outline: none;
}
:deep(.std-check input[type="checkbox"]:hover) {
  border-color: #aaa;
}
:deep(.std-check input[type="checkbox"]:checked) {
  background: #2b4b7e;
  border-color: #3c5f91;
}
:deep(.std-check input[type="checkbox"]:checked::after) {
  content: "";
  position: absolute;
  left: 4px;
  top: 1px;
  width: 5px;
  height: 9px;
  border: solid #fff;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

/* === 新增：部分选中（indeterminate）状态样式，呈现第三种视觉 === */
:deep(.std-check input[type="checkbox"]:indeterminate) {
  background: #7f8c8d; /* 灰色背景与选中区分 */
  border-color: #95a5a6;
}
:deep(.std-check input[type="checkbox"]:indeterminate::after) {
  content: "";
  position: absolute;
  left: 2px; /* 在方框中居中显示短横线 */
  top: 6px;
  width: 10px;
  height: 2px;
  background: #fff;
  border-radius: 1px;
}

/* 统一“重置”按钮容器 */
:deep(.std-reset) {
  width: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 修复：为按钮建立定位上下文，承载 ::before 的绝对定位 */
:deep(.std-reset > .btn.icon) {
  position: relative; /* 关键：使 ::before 以按钮为定位参考 */
  width: 26px;
  height: 26px;
  padding: 0;
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  /* overflow: hidden; /* 防止 ::before 溢出 */
}
:deep(.std-reset > .btn.icon:hover) {
  border-color: #5b7fb3;
  background: #2f3d55;
}

/* 统一“重置图标”：使用 CSS mask 在 ::before 绘制圆圈箭头 */
:deep(.std-reset > .btn.icon)::before {
  content: "";
  width: var(--reset-icon-size, 18px);
  height: var(--reset-icon-size, 18px);
  background-color: var(--reset-icon-color, #cfcfcf);
  position: absolute;
  left: 50%;
  top: 50%; /* 居中 */
  transform: translate(-50%, -50%); /* 居中 */
  pointer-events: none; /* 不拦截点击，确保按钮可点击 */
  -webkit-mask-image: url('data:image/svg+xml;utf8,<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="%23000" d="M12 5V2l-4 4 4 4V7c2.76 0 5 2.24 5 5a5 5 0 1 1-8.66-3.54l-1.42-1.42A7 7 0 1 0 19 12c0-3.87-3.13-7-7-7z"/></svg>');
  mask-image: url('data:image/svg+xml;utf8,<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="%23000" d="M12 5V2l-4 4 4 4V7c2.76 0 5 2.24 5 5a5 5 0 1 1-8.66-3.54l-1.42-1.42A7 7 0 1 0 19 12c0-3.87-3.13-7-7-7z"/></svg>');
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center;
  mask-position: center;
  -webkit-mask-size: contain;
  mask-size: contain;
}

/* 兼容：内容区 */
:deep(.std-reset > .btn.icon > svg),
:deep(.std-reset > .btn.icon > span) {
  pointer-events: none;
}
</style>