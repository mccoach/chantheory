<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\symbol\SymbolActions.vue -->
<!-- ============================== -->
<!-- V2.0 - 刷新按钮改为强制刷新 -->
<!-- ============================== -->
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
    </div>
  </div>
</template>

<script setup>
defineProps({
  loading: { type: Boolean, default: false },
});
defineEmits(["refresh"]);
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
  border-radius: 10px;
}
.seg-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.seg-btn:hover:not(:disabled) {
  background: #2b4b7e;
  color: #fff;
}
</style>