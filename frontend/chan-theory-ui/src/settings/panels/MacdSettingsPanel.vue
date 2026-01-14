<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\panels\MacdSettingsPanel.vue -->
<!-- ==============================
说明：MACD 设置面板（UI-only）
本轮改动：
  - select 统一改为 options children 渲染（不再使用 innerHTML 拼接）
  - 控件 getProps 样板代码用工厂函数标准化复用
============================== -->
<template>
  <SettingsGrid
    :rows="rows"
    :itemsPerRow="6"
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
import { DEFAULT_MACD_SETTINGS, UI_LIMITS, LINE_STYLES } from "@/constants";
import {
  useSettingsRenderer,
  makeNativeSelect,
  makeColorInput,
  makeNumberSpinner,
} from "@/settings/common/useSettingsRenderer";

const macdDraft = inject("macdDraft");
const macdResetter = inject("macdResetter");

const rows = computed(() => {
  const cfg = macdDraft || DEFAULT_MACD_SETTINGS;
  const out = [];

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
    check: { type: "single", checked: !!cfg.lines?.enabled },
    reset: { visible: true, title: "恢复默认" },
  });

  out.push({
    key: "macd-hist",
    name: "柱体",
    items: [
      { key: "histBarPercent", label: "柱宽%" },
      { key: "histUpColor", label: "多方颜色" },
      { key: "histDownColor", label: "空方颜色" },
    ],
    check: { type: "single", checked: !!cfg.hist?.enabled },
    reset: { visible: true, title: "恢复默认" },
  });

  return out;
});

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

const { renderControl } = useSettingsRenderer({
  fastPeriod: makeNumberSpinner({
    component: NumberSpinner,
    get: () => macdDraft.period.fast,
    set: (_, v) => (macdDraft.period.fast = v),
    min: UI_LIMITS.positiveInteger.min,
    step: UI_LIMITS.positiveInteger.step,
    integer: true,
  }),

  slowPeriod: makeNumberSpinner({
    component: NumberSpinner,
    get: () => macdDraft.period.slow,
    set: (_, v) => (macdDraft.period.slow = v),
    min: UI_LIMITS.positiveInteger.min,
    step: UI_LIMITS.positiveInteger.step,
    integer: true,
  }),

  signalPeriod: makeNumberSpinner({
    component: NumberSpinner,
    get: () => macdDraft.period.signal,
    set: (_, v) => (macdDraft.period.signal = v),
    min: UI_LIMITS.positiveInteger.min,
    step: UI_LIMITS.positiveInteger.step,
    integer: true,
  }),

  linesWidth: makeNumberSpinner({
    component: NumberSpinner,
    get: () => macdDraft.lines.width,
    set: (_, v) => (macdDraft.lines.width = v),
    min: UI_LIMITS.lineWidth.min,
    max: UI_LIMITS.lineWidth.max,
    step: UI_LIMITS.lineWidth.step,
    fracDigits: 1,
  }),

  difColor: makeColorInput({
    get: () => macdDraft.lines.difColor,
    set: (_, v) => (macdDraft.lines.difColor = v),
  }),

  difStyle: makeNativeSelect({
    options: LINE_STYLES,
    get: () => macdDraft.lines.difStyle,
    set: (_, v) => (macdDraft.lines.difStyle = v),
  }),

  deaColor: makeColorInput({
    get: () => macdDraft.lines.deaColor,
    set: (_, v) => (macdDraft.lines.deaColor = v),
  }),

  deaStyle: makeNativeSelect({
    options: LINE_STYLES,
    get: () => macdDraft.lines.deaStyle,
    set: (_, v) => (macdDraft.lines.deaStyle = v),
  }),

  histBarPercent: makeNumberSpinner({
    component: NumberSpinner,
    get: () => macdDraft.hist.barPercent,
    set: (_, v) => (macdDraft.hist.barPercent = v),
    min: UI_LIMITS.barWidthPercent.min,
    max: UI_LIMITS.barWidthPercent.max,
    step: UI_LIMITS.barWidthPercent.step,
    integer: true,
  }),

  histUpColor: makeColorInput({
    get: () => macdDraft.hist.upColor,
    set: (_, v) => (macdDraft.hist.upColor = v),
  }),

  histDownColor: makeColorInput({
    get: () => macdDraft.hist.downColor,
    set: (_, v) => (macdDraft.hist.downColor = v),
  }),
});
</script>

<style scoped>
/* 本面板布局交由 SettingsGrid 和 ModalDialog 统一管理，无需额外样式 */
</style>
