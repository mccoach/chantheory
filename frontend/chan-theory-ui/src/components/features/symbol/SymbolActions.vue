<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\symbol\SymbolActions.vue -->
<!-- 说明：封装“刷新”与被“短路”的“导出”按钮。 -->
<template>
  <div class="actions-group">
    <div class="seg">
      <button
        class="seg-btn"
        title="刷新"
        @click="$emit('refresh')"
        :disabled="loading"
      >
        刷新
      </button>
      <button
        class="seg-btn"
        title="导出功能暂不可用"
        @click="onExportClick"
        :disabled="loading"
      >
        导出
      </button>
    </div>
    <!-- 原导出菜单的DOM结构可保留于此，但因功能短路，暂不渲染 -->
  </div>
</template>

<script setup>
defineProps({
  loading: { type: Boolean, default: false },
});
defineEmits(["refresh"]);

// “导出”功能被短路，点击无效果
function onExportClick() {
  console.warn("导出功能已被暂时禁用。");
}
</script>

<style scoped>
.actions-group {
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
</style>
