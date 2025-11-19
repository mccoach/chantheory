<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\panels\MacdSettingsPanel.vue -->
<!-- ==============================
说明：MACD 设置面板（UI-only）
- 第1行：指标周期（快线/慢线/DEA）
- 第2行：折线（线宽 + DIF颜色 + DIF线型 + DEA颜色 + DEA线型）
- 第3行：柱体（柱宽% + 多方颜色 + 空方颜色）
============================== -->
<template>
  <SettingsGrid
    :rows="rows"
    :itemsPerRow="5"
    @row-toggle="onRowToggle"
    @row-reset="onRowReset"
  >
    <template #control="{ row, item }">
      <component :is="renderControl(row, item)" />
    </template>
  </SettingsGrid>
</template>

<script setup>
import { computed, inject } from "vue";
import SettingsGrid from "@/components/ui/SettingsGrid.vue";
import NumberSpinner from "@/components/ui/NumberSpinner.vue";
import {
  DEFAULT_MACD_SETTINGS,
  UI_LIMITS,
  LINE_STYLES,
} from "@/constants";
import { useSettingsRenderer } from "@/settings/common/useSettingsRenderer";

const macdDraft = inject("macdDraft");
const macdResetter = inject("macdResetter");

// 行定义
const rows = computed(() => {
  const cfg = macdDraft || DEFAULT_MACD_SETTINGS;
  const out = [];

  // 第1行：指标周期（快线/慢线/DEA），无勾选
  out.push({
    key: "macd-period",
    name: "指标周期",
    items: [
      { key: "fastPeriod", label: "快线周期" },
      { key: "slowPeriod", label: "慢线周期" },
      { key: "signalPeriod", label: "DEA周期" },
    ],
    check: { visible: false },
    reset: { visible: true, title: "恢复默认" },
  });

  // 第2行：折线（线宽 + DIF颜色 + DIF线型 + DEA颜色 + DEA线型），有勾选
  out.push({
    key: "macd-lines",
    name: "折线",
    items: [
      { key: "linesWidth", label: "线宽" },
      { key: "difColor", label: "DIF颜色" },
      { key: "difStyle", label: "DIF线型" },
      { key: "deaColor", label: "DEA颜色" },
      { key: "deaStyle", label: "DEA线型" },
    ],
    check: {
      type: "single",
      checked: !!cfg.lines?.enabled,
    },
    reset: { visible: true, title: "恢复默认" },
  });

  // 第3行：柱体（柱宽% + 多方颜色 + 空方颜色），有勾选
  out.push({
    key: "macd-hist",
    name: "柱体",
    items: [
      { key: "histBarPercent", label: "柱宽%" },
      { key: "histUpColor", label: "多方颜色" },
      { key: "histDownColor", label: "空方颜色" },
    ],
    check: {
      type: "single",
      checked: !!cfg.hist?.enabled,
    },
    reset: { visible: true, title: "恢复默认" },
  });

  return out;
});

// 行级勾选切换
function onRowToggle(row) {
  const key = String(row.key || "");
  const cfg = macdDraft;

  if (key === "macd-lines") {
    cfg.lines = {
      ...(cfg.lines || {}),
      enabled: !(cfg.lines?.enabled ?? DEFAULT_MACD_SETTINGS.lines.enabled),
    };
    return;
  }
  if (key === "macd-hist") {
    cfg.hist = {
      ...(cfg.hist || {}),
      enabled: !(cfg.hist?.enabled ?? DEFAULT_MACD_SETTINGS.hist.enabled),
    };
  }
}

// 行级事件：单行恢复默认（只改草稿，不保存）
function onRowReset(row) {
  const key = String(row.key || "");
  if (key === "macd-period") {
    macdResetter?.resetPath("period");
    return;
  }
  if (key === "macd-lines") {
    macdResetter?.resetPath("lines");
    return;
  }
  if (key === "macd-hist") {
    macdResetter?.resetPath("hist");
  }
}

// 通用渲染器
const { renderControl } = useSettingsRenderer({
  // 第1行：周期
  fastPeriod: {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: macdDraft.period.fast,
      min: UI_LIMITS.positiveInteger.min,
      step: UI_LIMITS.positiveInteger.step,
      integer: true,
      "onUpdate:modelValue": (v) => (macdDraft.period.fast = v),
    }),
  },
  slowPeriod: {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: macdDraft.period.slow,
      min: UI_LIMITS.positiveInteger.min,
      step: UI_LIMITS.positiveInteger.step,
      integer: true,
      "onUpdate:modelValue": (v) => (macdDraft.period.slow = v),
    }),
  },
  signalPeriod: {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: macdDraft.period.signal,
      min: UI_LIMITS.positiveInteger.min,
      step: UI_LIMITS.positiveInteger.step,
      integer: true,
      "onUpdate:modelValue": (v) => (macdDraft.period.signal = v),
    }),
  },

  // 第2行：折线
  linesWidth: {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: macdDraft.lines.width,
      min: UI_LIMITS.lineWidth.min,
      max: UI_LIMITS.lineWidth.max,
      step: UI_LIMITS.lineWidth.step,
      "frac-digits": 1,
      "onUpdate:modelValue": (v) => (macdDraft.lines.width = v),
    }),
  },
  difColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: macdDraft.lines.difColor,
      onInput: (e) => (macdDraft.lines.difColor = e.target.value),
    }),
  },
  difStyle: {
    component: "select",
    getProps: () => ({
      class: "input",
      value: macdDraft.lines.difStyle,
      onChange: (e) => (macdDraft.lines.difStyle = e.target.value),
      innerHTML: LINE_STYLES.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  deaColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: macdDraft.lines.deaColor,
      onInput: (e) => (macdDraft.lines.deaColor = e.target.value),
    }),
  },
  deaStyle: {
    component: "select",
    getProps: () => ({
      class: "input",
      value: macdDraft.lines.deaStyle,
      onChange: (e) => (macdDraft.lines.deaStyle = e.target.value),
      innerHTML: LINE_STYLES.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },

  // 第3行：柱体
  histBarPercent: {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: macdDraft.hist.barPercent,
      min: UI_LIMITS.barWidthPercent.min,
      max: UI_LIMITS.barWidthPercent.max,
      step: UI_LIMITS.barWidthPercent.step,
      integer: true,
      "onUpdate:modelValue": (v) => (macdDraft.hist.barPercent = v),
    }),
  },
  histUpColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: macdDraft.hist.upColor,
      onInput: (e) => (macdDraft.hist.upColor = e.target.value),
    }),
  },
  histDownColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: macdDraft.hist.downColor,
      onInput: (e) => (macdDraft.hist.downColor = e.target.value),
    }),
  },
});
</script>

<style scoped>
/* 本面板布局交由 SettingsGrid 和 ModalDialog 统一管理，无需额外样式 */
</style>