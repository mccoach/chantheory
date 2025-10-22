<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\ui\UiTextBox.vue -->
<template>
  <input
    ref="inp"
    type="text"
    class="ui-textbox"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    v-select-all
    @focus="onFocus"
    @input="onInput"
  />
</template>

<script setup>
import { ref } from "vue";
import { vSelectAll } from "@/utils/inputBehaviors";

const props = defineProps({
  modelValue: { type: [String, Number], default: "" },
  placeholder: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue"]);

const inp = ref(null);

function onInput(e) {
  if (props.disabled) return;
  emit("update:modelValue", e.target.value ?? "");
}
function onFocus() {
  // 保险：指令已选中，这里保留一次兜底选中
  try { setTimeout(() => inp.value && inp.value.select(), 0); } catch {}
}
</script>

<style scoped>
.ui-textbox {
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 4px 6px;
  width: 100%;
  outline: none;
}
.ui-textbox:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
