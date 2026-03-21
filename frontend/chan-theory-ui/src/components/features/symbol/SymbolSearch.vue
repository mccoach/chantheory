<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\symbol\SymbolSearch.vue -->
<!-- 说明：封装输入框、联想建议和历史记录的展示。 -->
<!-- V4.0 - BREAKING: 双主键语义封口
     - 选中语义继续使用完整 item（symbol + market）
     - 内部统一使用 identityKey，禁止散落 symbol-only key 拼接
-->
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
        :key="itemKey(item, i)"
        :symbol="item.symbol"
        :name="item.name"
        :market="item.market"
        :type="item.type"
        :active="i === activeIndex"
        :is-starred="watchlist.has(identityKey(item.symbol, item.market))"
        @select="onSelect"
        @toggle-star="onToggleStar"
      />
      <div v-if="!suggestions.length" class="no-data">无匹配项</div>
    </DropdownContainer>

    <DropdownContainer :show="showHistory" ref="historyWrapRef">
      <SymbolListItem
        v-for="(h, i) in historyResolved"
        :key="itemKey(h, i)"
        :symbol="h.symbol"
        :name="h.name || ''"
        :market="h.market || ''"
        :type="h.type || ''"
        :active="i === activeIndex"
        :is-starred="watchlist.has(identityKey(h.symbol, h.market))"
        @select="onSelect"
        @toggle-star="onToggleStar"
      />
      <div v-if="!historyResolved.length" class="no-data">暂无历史记录</div>
    </DropdownContainer>

    <div v-if="invalidHint" class="hint">{{ invalidHint }}</div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from "vue";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import DropdownContainer from "./DropdownContainer.vue";
import SymbolListItem from "./SymbolListItem.vue";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function identityKey(symbol, market) {
  return `${asStr(market).toUpperCase()}:${asStr(symbol)}`;
}

function itemKey(item, i) {
  return `${identityKey(item?.symbol, item?.market)}_${i}`;
}

const props = defineProps({
  modelValue: { type: String, default: "" },
  placeholder: { type: String, default: "" },
  invalidHint: { type: String, default: "" },
  suggestions: { type: Array, default: () => [] },
  history: { type: Array, default: () => [] },
  watchlist: { type: Set, default: () => new Set() },
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

const historyResolved = computed(() => {
  const arr = Array.isArray(props.history) ? props.history : [];
  return arr
    .map((h) => {
      const sym = asStr(h?.symbol);
      const mk = asStr(h?.market).toUpperCase();
      if (!sym || !mk) return null;

      return (
        findBySymbol(sym, mk) || {
          symbol: sym,
          market: mk,
          name: "",
          type: "",
        }
      );
    })
    .filter(Boolean);
});

const currentActiveList = computed(() => {
  if (props.showSuggestions) {
    return Array.isArray(props.suggestions) ? props.suggestions : [];
  }
  if (props.showHistory) {
    return historyResolved.value;
  }
  return [];
});

watch(currentActiveList, (newList) => {
  activeIndex.value = newList.length > 0 ? 0 : -1;
});

function onInput(event) {
  emit("update:modelValue", event.target.value);
}

function onSelect(item) {
  emit("selectSymbol", item);
}

function onToggleStar(item) {
  emit("toggleStar", item);
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
      onSelect(list[activeIndex.value]);
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
