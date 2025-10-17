<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\ui\NumberSpinner.vue -->
<template>
  <div
    class="numspin"
    :class="{ compact, disabled }"
    @wheel.passive.prevent="onWheel"
  >
    <input
      ref="inp"
      type="number"
      class="numspin-input"
      :min="min"
      :max="max"
      :step="step"
      :value="displayValue"
      :disabled="disabled"
      v-select-all
      @focus="onFocus"
      @input="onInput"
      @keydown="onKeydown"
      @blur="onBlur"
    />
    <div class="numspin-arrows">
      <div class="arrow up" @click="stepBy(+step)" :class="{ disabled }"></div>
      <div
        class="arrow down"
        @click="stepBy(-step)"
        :class="{ disabled }"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { clampNumber } from "@/utils/numberUtils";

const props = defineProps({
  modelValue: { type: [Number, String], required: true },
  min: { type: Number, default: Number.NEGATIVE_INFINITY },
  max: { type: Number, default: Number.POSITIVE_INFINITY },
  step: { type: Number, default: 1 },
  disabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "blur"]);
const inp = ref(null);
const displayValue = computed(() => String(props.modelValue ?? ""));

function onInput(e) {
  if (props.disabled) return;
  const next = clampNumber(e.target.value, { min: props.min, max: props.max, integer: true });
  emit("update:modelValue", next);
}
function onKeydown(e) {
  if (props.disabled) return;
  if (e.key === "ArrowUp") {
    e.preventDefault();
    stepBy(+props.step);
  } else if (e.key === "ArrowDown") {
    e.preventDefault();
    stepBy(-props.step);
  }
}
function onWheel(e) {
  if (props.disabled) return;
  const delta = e.deltaY < 0 ? +props.step : -props.step;
  stepBy(delta);
}
function stepBy(delta) {
  if (props.disabled) return;
  const curr = clampNumber(props.modelValue, { min: props.min, max: props.max, integer: true });
  const next = clampNumber(curr + delta, { min: props.min, max: props.max, integer: true });
  if (next !== curr) emit("update:modelValue", next);
}
function onBlur() {
  if (props.disabled) return;
  const curr = clampNumber(props.modelValue, { min: props.min, max: props.max, integer: true });
  emit("update:modelValue", curr);
  emit("blur");
}
function onFocus() {
  // 有指令兜底，这里保留一次保险选中
  try {
    setTimeout(() => inp.value && inp.value.select(), 0);
  } catch {}
}
</script>

<style scoped>
/* 保持之前样式，无改动（略） */
.numspin {
  display: inline-flex;
  align-items: center;
  background: #0f0f0f;
  border: 1px solid #333;
  border-radius: 4px;
  overflow: hidden;
}
.numspin.compact {
  background: transparent;
  border: none;
}
.numspin.disabled {
  opacity: 0.5;
  pointer-events: none;
}
.numspin-input {
  width: 68px;
  background: transparent;
  color: #ddd;
  border: none;
  padding: 0 6px;
  outline: none;
  text-align: center;
  appearance: textfield;
}
.numspin-input::-webkit-outer-spin-button,
.numspin-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.numspin-arrows {
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-left: 1px solid #333;
  padding: 0 6px;
}
.numspin.compact .numspin-arrows {
  border-left: 1px solid #444;
}
.arrow {
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  cursor: pointer;
  margin: 3px 0;
}
.arrow.up {
  border-bottom: 6px solid #bbb;
}
.arrow.down {
  border-top: 6px solid #bbb;
}
.arrow.disabled {
  opacity: 0.5;
  pointer-events: none;
}
</style>
