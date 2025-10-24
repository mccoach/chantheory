<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\symbol\DropdownContainer.vue -->
<!-- 说明：下拉框的通用容器，封装了定位、样式和滚动。 -->
<template>
  <div v-if="show" class="dropdown" @wheel.passive>
    <slot></slot>
  </div>
</template>

<script setup>
defineProps({
  show: { type: Boolean, default: false },
});
</script>

<style scoped>
.dropdown {
  position: absolute;
  z-index: 1000;
  top: 38px;
  left: 0;
  right: auto;
  width: max-content;
  min-width: 100%;
  max-height: 280px;
  overflow-y: auto;
  background: #1b1b1b;
  border: 1px solid #333;
  border-radius: 6px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
  white-space: nowrap;
}
</style>