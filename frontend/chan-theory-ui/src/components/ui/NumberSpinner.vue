<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\ui\NumberSpinner.vue -->
<!-- FIX: Re-added scoped styles to make the component's width configurable from the parent. -->
<template>
  <div
    class="numspin"
    :class="{ compact, disabled }"
    @wheel.prevent="onWheel"
  >
    <input
      ref="inp"
      type="text"
      class="numspin-input"
      :value="displayValue"
      :disabled="disabled"
      inputmode="numeric"
      :pattern="integer ? '^-?\\d*$' : '^-?\\d*(?:\\.\\d*)?$'"
      v-select-all
      @input="onInput"
      @keydown="onKeydown"
      @blur="onBlur"
    />
    <div class="numspin-arrows">
      <div class="arrow up" @click="stepBy(+step)" :class="{ disabled }"></div>
      <div class="arrow down" @click="stepBy(-step)" :class="{ disabled }"></div>
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
  integer: { type: Boolean, default: false },
  fracDigits: { type: Number, default: -1 }, // -1=不控制；>=0 固定位数
  padDigits: { type: Number, default: 0 },   // 0=不控制；>0 整数位左补零
});

const emit = defineEmits(["update:modelValue", "blur"]);
const inp = ref(null);

// NEW: 稳定舍入，避免 0.30000000000000004
function roundTo(n, d) {
  if (!Number.isFinite(n)) return n;
  if (!Number.isFinite(d) || d < 0) return n;
  const f = Math.pow(10, d);
  // 使用 Number.EPSILON 提升稳定性
  return Math.round((n + Number.EPSILON) * f) / f;
}

// NEW: 将任意输入字符串解析为数值并按规则裁剪
function normalizeNumber(str) {
  const t = String(str ?? "").trim();
  if (t === "" || t === "-" || t === "." || t === "-.") return null; // 编辑中间态
  const n = Number(t);
  if (!Number.isFinite(n)) return null;
  const dEff = props.integer ? 0 : (props.fracDigits >= 0 ? props.fracDigits : -1);
  const rounded = dEff >= 0 ? roundTo(n, dEff) : n;
  const clamped = clampNumber(rounded, {
    min: props.min,
    max: props.max,
    integer: props.integer,
  });
  return dEff >= 0 ? roundTo(clamped, dEff) : clamped;
}

// NEW: 显示层格式化（整数补零 + 小数固定位数）
function formatWithPadAndFrac(val) {
  // 先转为字符串（保持外部数值）
  const dEff = props.integer ? 0 : (props.fracDigits >= 0 ? props.fracDigits : -1);
  let n = Number(val);
  if (!Number.isFinite(n)) {
    const raw = String(val ?? "");
    return raw;
  }
  if (dEff >= 0) n = roundTo(n, dEff);
  let s =
    dEff >= 0
      ? n.toFixed(dEff)             // 固定小数位展示
      : String(n);

  // 前导零：仅作用整数部分
  const digits = Number.isFinite(props.padDigits) ? Math.max(0, Math.floor(props.padDigits)) : 0;
  if (digits <= 0) return s;

  let sign = "";
  if (s.startsWith("-")) {
    sign = "-";
    s = s.slice(1);
  }
  let intPart = s;
  let fracPart = "";
  const dotIdx = s.indexOf(".");
  if (dotIdx >= 0) {
    intPart = s.slice(0, dotIdx);
    fracPart = s.slice(dotIdx + 1);
  }

  // 仅在整数/小数部分都是数字时进行填充，避免用户输入阶段被干扰
  if (!/^\d*$/.test(intPart) || (fracPart && !/^\d*$/.test(fracPart))) {
    return (sign + s); // 异常时原样返回
  }
  const padded = intPart.length >= digits ? intPart : "0".repeat(digits - intPart.length) + intPart;
  return sign + (fracPart ? `${padded}.${fracPart}` : padded);
}

const displayValue = computed(() => formatWithPadAndFrac(props.modelValue));

function onInput(e) {
  if (props.disabled) return;
  const t = String(e.target.value ?? "");
  // 编辑中间态不触发修改，避免抖动
  if (t === "" || t === "-" || t === "." || t === "-.") return;
  const n = normalizeNumber(t);
  if (n == null) return;
  emit("update:modelValue", n);
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
  const base = normalizeNumber(props.modelValue);
  const curr = base == null ? 0 : base;
  const dEff = props.integer ? 0 : (props.fracDigits >= 0 ? props.fracDigits : -1);
  let next = curr + delta;
  if (dEff >= 0) next = roundTo(next, dEff);
  next = clampNumber(next, {
    min: props.min,
    max: props.max,
    integer: props.integer,
  });
  if (dEff >= 0) next = roundTo(next, dEff);
  if (next !== curr) emit("update:modelValue", next);
}
function onBlur() {
  if (props.disabled) return;
  const n = normalizeNumber(props.modelValue);
  if (n != null) emit("update:modelValue", n);
  emit("blur");
}
</script>

<style scoped>
.numspin {
  display: inline-flex;
  align-items: center;
  width: 100%; /* 组件宽度占满其容器 */
  height: 28px;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 4px;
  box-sizing: border-box;
}
.numspin.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.numspin-input {
  flex-grow: 1; /* 占据所有剩余空间 */
  width: 100%; /* 关键：输入框宽度占满 .numspin */
  height: 100%;
  background: transparent;
  color: #ddd;
  border: none;
  outline: none;
  padding: 0 6px;
  box-sizing: border-box;
  text-align: center;
}
.numspin-arrows {
  display: flex;
  flex-direction: column;
  width: 18px;
  height: 100%;
  flex-shrink: 0;
  opacity: 0;
  visibility: hidden;
  transition: opacity 120ms ease;
}
.numspin:hover .numspin-arrows {
  opacity: 1;
  visibility: visible;
}
.arrow {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  position: relative;
}
.arrow.disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.arrow:hover:not(.disabled) {
  background-color: #333;
}
.arrow.up::before {
  content: "";
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-bottom: 5px solid #aaa;
}
.arrow.down::before {
  content: "";
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid #aaa;
}
</style>
