<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\ui\SettingsGrid.vue -->
<!--
说明：标准化设置网格（UI-only）
- 使用模板与自定义指令设置 indeterminate；
- 仅提供 UI 外观与事件，不承载三态算法/持久化/重置逻辑；
- 槽位 control 由上层渲染具体控件；
- 复用现有 .std-* 样式，与 ModalDialog/App 的 :deep 定义无缝对接。
-->

<template>
  <div class="settings-grid">
    <div
      v-for="(row, ri) in rows"
      :key="row.key ?? ri"
      class="std-row"
    >
      <!-- 列1：行名 -->
      <div class="std-name">{{ row.name }}</div>

      <!-- 列2~(1+itemsPerRow)：统一“标签+输入”网格；不足自动补齐空列对齐 -->
      <template v-for="(item, ji) in normalizedItems(row)" :key="ji">
        <div class="std-item" v-if="item">
          <div class="std-item-label">{{ item.label || '' }}</div>
          <div class="std-item-input">
            <!-- 控制槽位：上层根据 item.key 自行渲染具体控件 -->
            <slot
              name="control"
              :row="row"
              :item="item"
              :rowIndex="ri"
              :itemIndex="ji"
            />
          </div>
        </div>
        <div v-else class="std-item" />
      </template>

      <!-- 倒数第2列：复选框（单/三态） -->
      <div class="std-check">
        <template v-if="row.check && (row.check.visible ?? true)">
          <!-- 三态复选 -->
          <input
            v-if="row.check.type === 'tri'"
            type="checkbox"
            :checked="!!row.check.checked"
            :disabled="!!row.check.disabled"
            v-set-indeterminate="!!row.check.indeterminate"
            @change="$emit('row-toggle', row)"
          />
          <!-- 单态复选 -->
          <input
            v-else
            type="checkbox"
            :checked="!!row.check.checked"
            :disabled="!!row.check.disabled"
            @change="$emit('row-toggle', row)"
          />
        </template>
      </div>

      <!-- 倒数第1列：恢复默认按钮 -->
      <div class="std-reset">
        <button
          v-if="row.reset && (row.reset.visible ?? true)"
          class="btn icon"
          type="button"
          :title="row.reset.title || '恢复默认'"
          @click="$emit('row-reset', row)"
        ></button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from "vue";

/**
 * props.rows 结构定义（UI-only）：
 * - key: string（可选，用作 v-for key）
 * - name: string（行名）
 * - items: Array<{ key:string, label:string, [any]... }>（长度 <= itemsPerRow）
 * - check?: { type:'single'|'tri', checked:boolean, indeterminate?:boolean, disabled?:boolean, visible?:boolean }
 * - reset?: { visible?:boolean, title?:string }
 */
const props = defineProps({
  rows: {
    type: Array,
    default: () => [],
  },
  itemsPerRow: {
    type: Number,
    default: 5, // 与现有标准网格保持一致：5列“标签+输入”
  },
});
defineEmits(["row-toggle", "row-reset"]);

// 归一化 items：长度不足补 null，模板中占位空列对齐
function normalizedItems(row) {
  const raw = Array.isArray(row.items) ? row.items.slice(0, props.itemsPerRow) : [];
  const pad = Math.max(0, props.itemsPerRow - raw.length);
  return [...raw, ...new Array(pad).fill(null)];
}

// 自定义指令：设置 indeterminate 状态（适用于三态复选框）
// 在 <script setup> 下，命名为 vSetIndeterminate，可在模板中直接使用 v-set-indeterminate
const vSetIndeterminate = {
  mounted(el, binding) {
    try { el.indeterminate = !!binding.value; } catch {}
  },
  updated(el, binding) {
    try { el.indeterminate = !!binding.value; } catch {}
  },
};
</script>

<style scoped>
/* 容器本身不强加额外样式，遵循现有 ModalDialog/App 中的 :deep(.std-*) 规则 */
.settings-grid {
  display: flex;
  flex-direction: column;
  gap: 0; /* 行距由外层控制 */
}

/* 复用外部 .btn.icon 的视觉（ModalDialog 已包含 ::before 的蒙版图标） */
.btn.icon {
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
.btn.icon:hover {
  border-color: #5b7fb3;
  background: #2f3d55;
}
</style>