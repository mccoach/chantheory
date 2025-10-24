<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\panels\IndicatorPlaceholderPanel.vue -->
<template>
  <div class="placeholder-panel">
    {{ label }} 指标暂无更多设置项，后续版本将开放参数配置。
  </div>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    default: "当前"
  }
});
</script>

<style scoped>
.placeholder-panel {
  color: #bbb;
  font-size: 13px;
  padding: 20px;
  text-align: center;
  background: #222;
  border-radius: 6px;
}
</style>