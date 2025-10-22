<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\ui\UiNumberBox.vue -->
<template>
  <NumberSpinner
    v-select-all
    :modelValue="modelValue"
    :min="min"
    :max="max"
    :step="step"
    :disabled="disabled"
    :compact="compact"
    :integer="integer"
    :padDigits="padDigits"
    :fracDigits="fracDigits"
    @update:modelValue="(v) => emit('update:modelValue', v)"
    @blur="onBlur"
  />
</template>

<script setup>
import NumberSpinner from "@/components/ui/NumberSpinner.vue";
import { vSelectAll } from "@/utils/inputBehaviors";

const props = defineProps({
  // 统一与 NumberSpinner 的接口
  modelValue: { type: [Number, String], required: true },
  min: { type: Number, default: Number.NEGATIVE_INFINITY },
  max: { type: Number, default: Number.POSITIVE_INFINITY },
  step: { type: Number, default: 1 },
  disabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  integer: { type: Boolean, default: false },
  // 显示整数位左补零（0 不控制；>0 补零）
  padDigits: { type: Number, default: 0 },
  // 小数位数控制（-1 不控制；>=0 固定位数）
  fracDigits: { type: Number, default: -1 },
});

const emit = defineEmits(["update:modelValue", "blur"]);

function onBlur() {
  // 统一再抛出 blur，供父级按需监听
  emit("blur");
}
</script>
