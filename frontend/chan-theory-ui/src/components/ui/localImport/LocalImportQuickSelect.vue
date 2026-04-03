<!-- src/components/ui/localImport/LocalImportQuickSelect.vue -->
<template>
  <div class="quick-body">
    <div class="quick-grid">
      <div class="quick-col-left">
        <div class="group">
          <div class="group-title">全选</div>
          <div class="group-items">
            <label class="quick-item">
              <span class="std-check">
                <input
                  type="checkbox"
                  v-tri-state="scopeUiMap[allScopeKey] || emptyUi"
                  @change="$emit('toggle-scope', allScopeKey)"
                />
              </span>
              <span class="txt">全选</span>
              <span class="count">{{ scopeCountText(allScopeKey) }}</span>
            </label>
          </div>
        </div>

        <div class="group">
          <div class="group-title">市场</div>
          <div class="group-items">
            <label
              v-for="item in marketScopeItems"
              :key="item.scopeKey"
              class="quick-item"
            >
              <span class="std-check">
                <input
                  type="checkbox"
                  v-tri-state="scopeUiMap[item.scopeKey] || emptyUi"
                  @change="$emit('toggle-scope', item.scopeKey)"
                />
              </span>
              <span class="txt">{{ item.label }}</span>
              <span class="count">{{ scopeCountText(item.scopeKey) }}</span>
            </label>
          </div>
        </div>

        <div class="group">
          <div class="group-title">类别</div>
          <div class="group-items">
            <label
              v-for="item in classScopeItems"
              :key="item.scopeKey"
              class="quick-item"
            >
              <span class="std-check">
                <input
                  type="checkbox"
                  v-tri-state="scopeUiMap[item.scopeKey] || emptyUi"
                  @change="$emit('toggle-scope', item.scopeKey)"
                />
              </span>
              <span class="txt">{{ item.label }}</span>
              <span class="count">{{ scopeCountText(item.scopeKey) }}</span>
            </label>
          </div>
        </div>

        <div class="group">
          <div class="group-title">周期</div>
          <div class="group-items">
            <label
              v-for="item in freqScopeItems"
              :key="item.scopeKey"
              class="quick-item"
            >
              <span class="std-check">
                <input
                  type="checkbox"
                  v-tri-state="scopeUiMap[item.scopeKey] || emptyUi"
                  @change="$emit('toggle-scope', item.scopeKey)"
                />
              </span>
              <span class="txt">{{ item.label }}</span>
              <span class="count">{{ scopeCountText(item.scopeKey) }}</span>
            </label>
          </div>
        </div>
      </div>

      <div class="quick-col-right">
        <div class="group">
          <div class="group-title">股票类型</div>
          <div class="group-items">
            <label
              v-for="item in stockTypeScopeItems"
              :key="item.scopeKey"
              class="quick-item"
            >
              <span class="std-check">
                <input
                  type="checkbox"
                  v-tri-state="scopeUiMap[item.scopeKey] || emptyUi"
                  @change="$emit('toggle-scope', item.scopeKey)"
                />
              </span>
              <span class="txt">{{ item.label }}</span>
              <span class="count">{{ scopeCountText(item.scopeKey) }}</span>
            </label>
          </div>
        </div>

        <div class="group">
          <div class="group-title">指数类型</div>
          <div class="group-items">
            <label
              v-for="item in indexTypeScopeItems"
              :key="item.scopeKey"
              class="quick-item"
            >
              <span class="std-check">
                <input
                  type="checkbox"
                  v-tri-state="scopeUiMap[item.scopeKey] || emptyUi"
                  @change="$emit('toggle-scope', item.scopeKey)"
                />
              </span>
              <span class="txt">{{ item.label }}</span>
              <span class="count">{{ scopeCountText(item.scopeKey) }}</span>
            </label>
          </div>
        </div>

        <div class="group">
          <div class="group-title">基金类型</div>
          <div class="group-items">
            <label
              v-for="item in fundTypeScopeItems"
              :key="item.scopeKey"
              class="quick-item"
            >
              <span class="std-check">
                <input
                  type="checkbox"
                  v-tri-state="scopeUiMap[item.scopeKey] || emptyUi"
                  @change="$emit('toggle-scope', item.scopeKey)"
                />
              </span>
              <span class="txt">{{ item.label }}</span>
              <span class="count">{{ scopeCountText(item.scopeKey) }}</span>
            </label>
          </div>
        </div>
      </div>
    </div>

    <div v-if="uiMessage" class="ui-msg">
      {{ uiMessage }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  allScopeKey: { type: String, required: true },
  emptyUi: { type: Object, required: true },
  scopeUiMap: { type: Object, required: true },
  marketScopeItems: { type: Array, default: () => [] },
  classScopeItems: { type: Array, default: () => [] },
  freqScopeItems: { type: Array, default: () => [] },
  stockTypeScopeItems: { type: Array, default: () => [] },
  indexTypeScopeItems: { type: Array, default: () => [] },
  fundTypeScopeItems: { type: Array, default: () => [] },
  scopeCountText: { type: Function, required: true },
  uiMessage: { type: String, default: "" },
});

defineEmits(["toggle-scope"]);
</script>

<style scoped>
.quick-body {
  padding: 10px 12px;
  overflow: auto;
  min-height: 0;
  flex: 1;
}

.quick-grid {
  display: grid;
  grid-template-columns: 135px 160px;
  gap: 8px;
  align-items: start;
}

.quick-col-left,
.quick-col-right {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-title {
  font-size: 12px;
  color: #bbb;
  font-weight: 700;
  text-align: left;
}

.group-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quick-item {
  display: grid;
  grid-template-columns: 16px 1fr auto;
  align-items: center;
  column-gap: 8px;
  min-height: 22px;
  color: #ddd;
  user-select: none;
}

.quick-item .txt {
  text-align: left;
  font-size: 12px;
  line-height: 1.4;
}

.quick-item .count {
  color: #888;
  font-size: 11px;
  white-space: nowrap;
}

.ui-msg {
  margin-top: 12px;
  color: #bbb;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  text-align: left;
}
</style>
