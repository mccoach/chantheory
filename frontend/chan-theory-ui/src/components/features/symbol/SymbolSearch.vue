<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\symbol\SymbolSearch.vue -->
<!-- 说明：封装输入框、联想建议和历史记录的展示。 -->
<!-- FINAL FIX: 重新引入 watchlist prop，并用它来计算传递给 SymbolListItem 的 is-starred 状态。 -->
<template>
  <div class="search-wrapper">
    <input
      ref="inputRef"
      class="symbol-input compact"
      :value="modelValue"
      :placeholder="placeholder"
      v-select-all
      :class="{ invalid: invalidHint }"
      @focus="$emit('focus', $event)"
      @input="onInput"
      @keydown="onKeydown"
      @blur="$emit('blur', $event)"
    />

    <DropdownContainer :show="showSuggestions" ref="suggestWrapRef">
      <SymbolListItem
        v-for="(item, i) in suggestions"
        :key="item.symbol + '_' + i"
        :symbol="item.symbol"
        :name="item.name"
        :market="item.market"
        :type="item.type"
        :active="i === activeIndex"
        :is-starred="watchlist.has(item.symbol)"
        @select="onSelect"
        @toggle-star="onToggleStar"
      />
      <div v-if="!suggestions.length" class="no-data">无匹配项</div>
    </DropdownContainer>

    <DropdownContainer :show="showHistory" ref="historyWrapRef">
      <SymbolListItem
        v-for="(h, i) in history"
        :key="h.symbol + '_' + i"
        :symbol="h.symbol"
        :name="findBySymbol(h.symbol)?.name || ''"
        :market="findBySymbol(h.symbol)?.market || ''"
        :type="findBySymbol(h.symbol)?.type || ''"
        :active="i === activeIndex"
        :is-starred="watchlist.has(h.symbol)"
        @select="onSelect"
        @toggle-star="onToggleStar"
      />
      <div v-if="!history.length" class="no-data">暂无历史记录</div>
    </DropdownContainer>

    <div v-if="invalidHint" class="hint">{{ invalidHint }}</div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from "vue";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import DropdownContainer from "./DropdownContainer.vue";
import SymbolListItem from "./SymbolListItem.vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  placeholder: { type: String, default: "" },
  invalidHint: { type: String, default: "" },
  suggestions: { type: Array, default: () => [] },
  history: { type: Array, default: () => [] },
  watchlist: { type: Set, default: () => new Set() }, // NEW: 重新接收 watchlist Set
  showSuggestions: { type: Boolean, default: false },
  showHistory: { type: Boolean, default: false },
});

const emit = defineEmits([
  "update:modelValue",
  "focus",
  "blur",
  "selectSymbol",
  "toggleStar",
]);

defineExpose({
  blur: () => inputRef.value?.blur(),
  focus: () => inputRef.value?.focus(),
});

const { findBySymbol } = useSymbolIndex();
const inputRef = ref(null);
const suggestWrapRef = ref(null);
const historyWrapRef = ref(null);
const activeIndex = ref(-1);

const currentActiveList = computed(() => {
  if (props.showSuggestions) {
    return props.suggestions;
  }
  if (props.showHistory) {
    return props.history.map(h => findBySymbol(h.symbol)).filter(Boolean);
  }
  return [];
});

watch(currentActiveList, (newList) => {
  activeIndex.value = newList.length > 0 ? 0 : -1;
});

function onInput(event) {
  emit("update:modelValue", event.target.value);
}

function onSelect(symbol) {
  emit("selectSymbol", findBySymbol(symbol));
}

function onToggleStar(symbol) {
  emit("toggleStar", findBySymbol(symbol));
}

function onKeydown(e) {
  const list = currentActiveList.value;

  if (e.key === "ArrowDown") {
    e.preventDefault();
    if (!list.length) return;
    activeIndex.value = (activeIndex.value + 1) % list.length;
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (!list.length) return;
    activeIndex.value = (activeIndex.value - 1 + list.length) % list.length;
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (activeIndex.value >= 0 && activeIndex.value < list.length) {
      onSelect(list[activeIndex.value].symbol);
    } else {
      inputRef.value?.blur();
    }
  } else if (e.key === "Escape") {
    e.preventDefault();
    inputRef.value?.blur();
  }
}
</script>

<style scoped>
.search-wrapper {
  position: relative;
  display: inline-block;
}
.symbol-input {
  height: 36px;
  line-height: 36px;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 0 10px;
  outline: none;
}
.symbol-input.compact {
  width: 128px;
}
.symbol-input.invalid {
  border-color: #a94442;
}
.hint {
  position: absolute;
  top: 100%;
  left: 0;
  color: #e67e22;
  font-size: 12px;
  margin-top: 4px;
  white-space: nowrap;
}
.no-data {
  color: #888;
  padding: 10px;
  text-align: center;
}
</style>
