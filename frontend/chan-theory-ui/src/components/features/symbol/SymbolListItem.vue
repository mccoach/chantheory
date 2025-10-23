<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\symbol\SymbolListItem.vue -->
<!-- 说明：可复用的列表项组件，用于联想、历史和自选。 -->
<!-- FINAL FIX: 彻底移除内部所有状态获取逻辑，使其成为一个完全由 props 驱动的纯展示型（Dumb）组件。-->
<template>
  <div
    class="suggest-item"
    :class="{ active: active }"
    @mousedown.prevent="$emit('select', symbol)"
  >
    <div class="left">
      <span class="code">{{ symbol }}</span>
      <span class="name">{{ name }}</span>
    </div>
    <div class="right">
      <div class="meta-vert">
        <span class="meta market">{{ market }}</span>
        <span class="meta type">{{ type }}</span>
      </div>
      <button
        class="star-btn"
        :class="{ active: isStarred }"
        :title="starTitle"
        :aria-label="starTitle"
        @mousedown.stop.prevent="$emit('toggleStar', symbol)"
      >
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <path
            class="star"
            d="M12 2 L14.9 8.1 L21.5 9.2 L16.8 13.7 L18.1 20.2 L12 16.9 L5.9 20.2 L7.2 13.7 L2.5 9.2 L9.1 8.1 Z"
          />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
// 这个组件现在是纯粹的展示组件，不包含任何业务逻辑。
defineProps({
  symbol: { type: String, required: true },
  name: { type: String, default: "" },
  market: { type: String, default: "" },
  type: { type: String, default: "" },
  isStarred: { type: Boolean, default: false }, // 星标状态完全由父组件决定
  starTitle: { type: String, default: "加入/移除自选" },
  active: { type: Boolean, default: false },
});
defineEmits(["select", "toggleStar"]);
</script>

<style scoped>
/* 统一列宽 */
:where(.suggest-item) {
  --col-code: 80px;
  --col-name: 1fr;
  --col-meta: 30px;
  --col-star: 18px;
}

.suggest-item {
  display: grid;
  grid-template-columns:
    var(--col-code)
    var(--col-name)
    var(--col-meta)
    var(--col-star);
  align-items: center;
  justify-content: start;
  column-gap: 8px;
  padding: 6px 10px;
  cursor: pointer;
  color: #ddd;
  white-space: nowrap;
}
.suggest-item:hover,
.suggest-item.active {
  background: #2a2a2a;
}

.suggest-item .left,
.suggest-item .right {
  display: contents;
}

.suggest-item .left .code {
  grid-column: 1;
  font-weight: 600;
  margin-right: 8px;
}
.suggest-item .left .name {
  grid-column: 2;
  color: #ccc;
  text-align: left;
  justify-self: start;
}

.suggest-item .right .meta-vert {
  grid-column: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
}
.suggest-item .right .meta-vert .meta {
  color: #999;
  font-size: 12px;
  line-height: 1.1;
}

.suggest-item .right .star-btn {
  grid-column: 4;
  justify-self: center;
}

.star-btn {
  width: 18px;
  height: 18px;
  padding: 0;
  margin: 0;
  background: transparent;
  border: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.star-btn .star {
  fill: transparent;
  stroke: #bbb;
  stroke-width: 1.2;
  transition: fill 120ms ease, stroke 120ms ease;
}
.star-btn:hover .star {
  stroke: #e0e0e0;
}
.star-btn.active .star {
  fill: #f1c40f;
  stroke: #f39c12;
}
</style>
