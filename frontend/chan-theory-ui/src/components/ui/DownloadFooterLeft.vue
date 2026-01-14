<!-- src/components/ui/DownloadFooterLeft.vue -->
<!-- ==============================
说明：盘后下载弹窗底栏左侧信息区（纯展示组件）
职责：
  - 展示已选标的、任务进度、成功/失败数、持续时间
  - 展示实时进度条（从左向右填充）
设计：
  - 一行四列布局（已选 | 进度条 | 成功失败 | 时间）
  - 配色与窗体色系融合（低调克制，渐变质感）
============================== -->
<template>
  <div class="footer-inline">
    <!-- 列1：已选标的 -->
    <div class="col col-selected">
      <div class="col-label">已选标的</div>
      <div class="col-value neutral">{{ selectedCount }} / {{ totalCount }}</div>
    </div>

    <!-- 列2：进度条（占据主要空间）-->
    <div class="col col-progress">
      <div class="bar">
        <div class="fill" :style="{ width: progressPercent + '%' }"></div>
        <div class="bar-text">{{ done }} / {{ totalJobs }} （{{ progressText }}）</div>
      </div>
    </div>

    <!-- 列3：成功 + 失败 -->
    <div class="col col-result">
      <div class="col-label">成功 · 失败</div>
      <div class="col-value">
        <span class="success">{{ succeeded }}</span>
        <span class="sep">·</span>
        <span class="danger">{{ failed }}</span>
      </div>
    </div>

    <!-- 列4：持续时间 -->
    <div class="col col-time">
      <div class="col-label">持续时间</div>
      <div class="col-value time">{{ elapsed }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  selectedCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
  totalJobs: { type: Number, default: 0 },
  done: { type: Number, default: 0 },
  succeeded: { type: Number, default: 0 },
  failed: { type: Number, default: 0 },
  elapsed: { type: String, default: '00:00:00' },
});

const progressPercent = computed(() => {
  const total = Math.max(0, props.totalJobs);
  if (total === 0) return 0;
  const done = Math.max(0, props.done);
  const pct = (done / total) * 100;
  return Math.max(0, Math.min(100, pct));
});

const progressText = computed(() => {
  const total = Math.max(0, props.totalJobs);
  if (total === 0) return '0.0%';
  const pct = progressPercent.value;
  return pct.toFixed(1) + '%';
});
</script>

<style scoped>
/* ==============================
   一行四列布局（已选 | 进度条 | 成功失败 | 时间）
   ============================== */

.footer-inline {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

/* 通用列样式（除进度条外） */
.col {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  flex-shrink: 0;
}

.col-label {
  font-size: 10px;
  color: #888;
  user-select: none;
  white-space: nowrap;
}

.col-value {
  font-size: 13px;
  font-weight: 600;
  user-select: none;
  white-space: nowrap;
  display: flex;
  align-items: baseline;
  gap: 4px;
}

/* 列1：已选标的（固定宽度） */
.col-selected {
  min-width: 90px;
}

.col-value.neutral {
  color: #aaa;
}

/* 列2：进度条（占据剩余空间） */
.col-progress {
  flex: 1;
  min-width: 0;
}

.bar {
  position: relative;
  height: 20px;
  width: 100%;
  background: linear-gradient(180deg, #1a1a1a 0%, #242424 100%);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.3);
}

.fill {
  height: 100%;
  background: linear-gradient(90deg, #2b4b7e 0%, #4a6fa5 50%, #5b7fb3 100%);
  transition: width 0.3s ease;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.1);
}

.bar-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #e6e6e6;
  font-weight: 600;
  user-select: none;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
  pointer-events: none;
}

/* 列3：成功 + 失败（固定宽度） */
.col-result {
  min-width: 80px;
}

.col-value .success {
  color: #47a69b;
}

.col-value .danger {
  color: #d97575;
}

.col-value .sep {
  color: #555;
  font-size: 11px;
}

/* 列4：持续时间（固定宽度） */
.col-time {
  min-width: 75px;
}

.col-value.time {
  color: #d4a574;
  font-variant-numeric: tabular-nums;
}
</style>
