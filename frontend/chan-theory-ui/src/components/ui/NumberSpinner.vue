<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\ui\NumberSpinner.vue -->
<!--
V3.6 - FIX: allowNullCommit 空值 Enter 提交时避免焦点争抢
根因：
  - Enter 提交成功后会触发全局 hotkeys 跳到下一格；
  - allowNullCommit 分支里原先 nextTick 强制 focus 自身，导致与下一格争抢焦点。
修复：
  - 移除 allowNullCommit 分支中的 nextTick focus，自身不再抢回焦点。
-->
<template>
  <div
    class="numspin"
    :class="{ compact, disabled }"
    @wheel.prevent="onWheel"
    data-ct-numspin="1"
    :data-editing="isEditing ? '1' : '0'"
  >
    <input
      ref="inp"
      type="text"
      class="numspin-input"
      :value="displayText"
      :disabled="disabled"
      inputmode="numeric"
      :pattern="integer ? '^-?\\d*$' : '^-?\\d*(?:\\.\\d*)?$'"
      v-select-all
      @focus="onFocus"
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
import { computed, ref, watch } from "vue";
import { clampNumber } from "@/utils/numberUtils";

const props = defineProps({
  modelValue: { type: [Number, String], required: true },
  min: { type: Number, default: Number.NEGATIVE_INFINITY },
  max: { type: Number, default: Number.POSITIVE_INFINITY },
  step: { type: Number, default: 1 },
  disabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  integer: { type: Boolean, default: false },
  fracDigits: { type: Number, default: -1 }, // -1=不控制；>=0 固定位数（提交时生效）
  padDigits: { type: Number, default: 0 },   // 0=不控制；>0 整数位左补零（展示态生效）

  // 是否允许把“清空”作为一次有效提交（提交 null）
  allowNullCommit: { type: Boolean, default: false },

  // 清空提交后回填（返回 number|string|null）
  nullCommitFill: { type: [Function, Number, String, null], default: null },
});

const emit = defineEmits(["update:modelValue", "blur", "commit"]);
const inp = ref(null);

const isEditing = ref(false);
const editText = ref("");
const focusSnapshot = ref(null);

function roundTo(n, d) {
  if (!Number.isFinite(n)) return n;
  if (!Number.isFinite(d) || d < 0) return n;
  const f = Math.pow(10, d);
  return Math.round((n + Number.EPSILON) * f) / f;
}

function formatDisplay(val) {
  let n = Number(val);
  if (!Number.isFinite(n)) return String(val ?? "");

  const dEff = props.integer ? 0 : (props.fracDigits >= 0 ? props.fracDigits : -1);
  if (dEff >= 0) n = roundTo(n, dEff);

  let s = dEff >= 0 ? n.toFixed(dEff) : String(n);

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

  if (!/^\d*$/.test(intPart) || (fracPart && !/^\d*$/.test(fracPart))) {
    return sign + s;
  }

  const padded = intPart.length >= digits ? intPart : "0".repeat(digits - intPart.length) + intPart;
  return sign + (dotIdx >= 0 ? `${padded}.${fracPart}` : padded);
}

function normalizeAndClampFromText(text) {
  const t = String(text ?? "").trim();
  if (t === "" || t === "-" || t === "." || t === "-.") return null;

  const n0 = Number(t);
  if (!Number.isFinite(n0)) return null;

  const dEff = props.integer ? 0 : (props.fracDigits >= 0 ? props.fracDigits : -1);

  let n = dEff >= 0 ? roundTo(n0, dEff) : n0;
  n = clampNumber(n, { min: props.min, max: props.max, integer: props.integer });
  n = dEff >= 0 ? roundTo(n, dEff) : n;

  return n;
}

watch(
  () => props.modelValue,
  (v) => {
    if (isEditing.value) return;
    editText.value = formatDisplay(v);
  },
  { immediate: true }
);

const displayText = computed(() => {
  return isEditing.value ? editText.value : formatDisplay(props.modelValue);
});

function onFocus() {
  if (props.disabled) return;

  isEditing.value = true;
  focusSnapshot.value = props.modelValue;
  editText.value = formatDisplay(props.modelValue);
}

function onInput(e) {
  if (props.disabled) return;
  isEditing.value = true;
  editText.value = String(e?.target?.value ?? "");
}

function emitCommit(value, source) {
  emit("commit", { value, source: String(source || "unknown") });
}

function resolveNullFillValue() {
  try {
    if (typeof props.nullCommitFill === "function") {
      return props.nullCommitFill();
    }
    return props.nullCommitFill;
  } catch {
    return null;
  }
}

function requestFocusMove(dir) {
  try {
    const d = Number(dir);
    if (!Number.isFinite(d) || d === 0) return;

    window.dispatchEvent(
      new CustomEvent("chan:numspin-focus-next", {
        detail: { dir: d },
      })
    );
  } catch {}
}

function commitIfPossible(source) {
  const raw = String(editText.value ?? "");
  const t = raw.trim();

  if (props.allowNullCommit === true && t === "") {
    emit("update:modelValue", null);
    emitCommit(null, source);

    const fill = resolveNullFillValue();
    if (fill != null && fill !== "") {
      editText.value = formatDisplay(fill);
      const nFill = Number(fill);
      if (Number.isFinite(nFill)) {
        emit("update:modelValue", nFill);
      }
    } else {
      editText.value = "";
    }

    // FIX: 不再 nextTick 强制 focus 自身，避免与“跳下一格”争抢焦点
    return true;
  }

  const n = normalizeAndClampFromText(editText.value);
  if (n == null) return false;

  emit("update:modelValue", n);
  editText.value = formatDisplay(n);
  emitCommit(n, source);

  return true;
}

function cancelToSnapshot() {
  emit("update:modelValue", focusSnapshot.value);
  editText.value = formatDisplay(focusSnapshot.value);
}

function onKeydown(e) {
  if (props.disabled) return;

  if (e.key === "ArrowUp") {
    e.preventDefault();
    stepBy(+props.step);
    return;
  }
  if (e.key === "ArrowDown") {
    e.preventDefault();
    stepBy(-props.step);
    return;
  }

  if (e.key === "Escape") {
    e.preventDefault();
    e.stopPropagation();
    cancelToSnapshot();
    try { inp.value?.focus?.(); } catch {}
    return;
  }

  if (e.key === "Enter") {
    e.preventDefault();
    e.stopPropagation();

    const ok = commitIfPossible("enter");
    if (ok) {
      requestFocusMove(e.shiftKey ? -1 : +1);
    }
    return;
  }
}

function onWheel(e) {
  if (props.disabled) return;
  const delta = e.deltaY < 0 ? +props.step : -props.step;
  stepBy(delta);
}

function stepBy(delta) {
  if (props.disabled) return;

  const baseFromText = normalizeAndClampFromText(editText.value);
  const baseFromModel = Number(props.modelValue);
  const curr =
    baseFromText != null
      ? baseFromText
      : (Number.isFinite(baseFromModel) ? baseFromModel : 0);

  const dEff = props.integer ? 0 : (props.fracDigits >= 0 ? props.fracDigits : -1);

  let next = curr + Number(delta || 0);
  if (dEff >= 0) next = roundTo(next, dEff);

  next = clampNumber(next, { min: props.min, max: props.max, integer: props.integer });
  if (dEff >= 0) next = roundTo(next, dEff);

  emit("update:modelValue", next);

  if (isEditing.value) {
    editText.value = formatDisplay(next);
  }
}

function onBlur() {
  if (props.disabled) return;

  const ok = commitIfPossible("blur");
  if (!ok) {
    editText.value = formatDisplay(props.modelValue);
  }

  isEditing.value = false;
  focusSnapshot.value = null;

  emit("blur");
}
</script>

<style scoped>
.numspin {
  display: inline-flex;
  align-items: center;
  width: 100%;
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
  flex-grow: 1;
  width: 100%;
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
  position: absolute;
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid #aaa;
}
</style>
