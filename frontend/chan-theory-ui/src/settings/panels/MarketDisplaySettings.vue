<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\panels\MarketDisplaySettings.vue -->
<!-- ==============================
说明：行情设置面板（新版：UI-only, 数据驱动渲染）
- 职责：仅负责渲染行情相关的设置UI。
- 数据流：通过 `inject` 获取响应式草稿对象。
- 渲染：使用新的通用渲染器 `useSettingsRenderer` 替代手写的 `renderControl`。
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
import { computed, h, inject } from "vue";
import SettingsGrid from "@/components/ui/SettingsGrid.vue";
import {
  DEFAULT_KLINE_STYLE,
  DEFAULT_MA_CONFIGS,
  DEFAULT_APP_PREFERENCES,
  LINE_STYLES,
  ADJUST_OPTIONS,
  DISPLAY_ORDER_OPTIONS,
  UI_LIMITS,
} from "@/constants";
import { useTriMasterToggle } from "@/settings/common/useTriMasterToggle";
import UiNumberBox from "@/components/ui/UiNumberBox.vue";
import { useSettingsRenderer } from "@/settings/common/useSettingsRenderer";

// 通过 inject 获取共享的草稿状态
const klineDraft = inject("klineDraft");
const maDraft = inject("maDraft");
const adjustDraft = inject("adjustDraft");

function getMAKeys() {
  return Object.keys(maDraft || {});
}

// MA 总控：动态两态/三态
const maTri = useTriMasterToggle({
  items: getMAKeys().map((mk) => ({
    get: () => !!maDraft?.[mk]?.enabled,
    set: (v) => {
      const conf = maDraft[mk] || {};
      maDraft[mk] = { ...conf, enabled: !!v };
    },
  })),
});

// 构建行
const rows = computed(() => {
  const k = klineDraft || DEFAULT_KLINE_STYLE;
  const maMap = maDraft || {};
  const out = [];

  // 原始K线
  out.push({
    key: "k-original",
    name: "原始K线",
    items: [
      { key: "adjust", label: "复权" },
      { key: "upColor", label: "阳线颜色" },
      { key: "upFade", label: "阳线淡显" },
      { key: "downColor", label: "阴线颜色" },
      { key: "downFade", label: "阴线淡显" },
    ],
    check: { type: "single", checked: !!k.originalEnabled },
    reset: { visible: true, title: "恢复默认" },
  });

  // 合并K线
  out.push({
    key: "k-merged",
    name: "合并K线",
    items: [
      { key: "outlineWidth", label: "轮廓线宽" },
      { key: "mUpColor", label: "上涨颜色" },
      { key: "mDownColor", label: "下跌颜色" },
      { key: "fillFade", label: "填充淡显" },
      { key: "displayOrder", label: "显示层级" },
    ],
    check: { type: "single", checked: !!k.mergedEnabled },
    reset: { visible: true, title: "恢复默认" },
  });

  // MA 总控（三态）
  out.push({
    key: "ma-global",
    name: "均线总控",
    items: [],
    check: {
      type: "tri",
      checked: !!maTri.masterUi.checked.value,
      indeterminate: !!maTri.masterUi.indeterminate.value,
    },
    reset: { visible: false },
  });

  // 各 MA 行（按 DEFAULT_MA_CONFIGS 键序构建）
  Object.keys(DEFAULT_MA_CONFIGS).forEach((mk) => {
    const conf = maMap[mk] || DEFAULT_MA_CONFIGS[mk];
    out.push({
      key: `ma-${mk}`,
      name: `MA${conf.period}`,
      items: [
        { key: "ma-width", label: "线宽", maKey: mk },
        { key: "ma-color", label: "颜色", maKey: mk },
        { key: "ma-style", label: "线型", maKey: mk },
        { key: "ma-period", label: "周期", maKey: mk },
      ],
      check: { type: "single", checked: !!conf.enabled },
      reset: { visible: true, title: "恢复默认" },
    });
  });

  return out;
});

// 行级切换
function onRowToggle(row) {
  const key = String(row.key || "");
  if (key === "ma-global") {
    maTri.cycleOnce();
    return;
  }
  if (key === "k-original") {
    klineDraft.originalEnabled = !klineDraft.originalEnabled;
    return;
  }
  if (key === "k-merged") {
    klineDraft.mergedEnabled = !klineDraft.mergedEnabled;
    return;
  }
  if (key.startsWith("ma-")) {
    const mk = key.slice(3);
    const conf = maDraft[mk];
    if (conf) {
      conf.enabled = !conf.enabled;
      maTri.updateSnapshot();
    }
  }
}

// 单行恢复默认
function onRowReset(row) {
  const key = String(row.key || "");
  if (key === "k-original") {
    Object.assign(klineDraft, {
      upColor: DEFAULT_KLINE_STYLE.upColor,
      downColor: DEFAULT_KLINE_STYLE.downColor,
      originalFadeUpPercent: DEFAULT_KLINE_STYLE.originalFadeUpPercent,
      originalFadeDownPercent: DEFAULT_KLINE_STYLE.originalFadeDownPercent,
      originalEnabled: DEFAULT_KLINE_STYLE.originalEnabled,
    });
    adjustDraft.value = DEFAULT_APP_PREFERENCES.adjust;
    return;
  }
  if (key === "k-merged") {
    klineDraft.mergedEnabled = DEFAULT_KLINE_STYLE.mergedEnabled;
    klineDraft.mergedK = { ...DEFAULT_KLINE_STYLE.mergedK };
    return;
  }
  if (key.startsWith("ma-")) {
    const mk = key.slice(3);
    const def = DEFAULT_MA_CONFIGS[mk];
    if (def) {
      maDraft[mk] = { ...def };
      maTri.updateSnapshot();
    }
  }
}

// 使用新的通用渲染器
const { renderControl } = useSettingsRenderer({
  adjust: {
    component: "select",
    getProps: () => ({
      class: "input",
      value: adjustDraft.value,
      onChange: (e) => (adjustDraft.value = e.target.value),
      innerHTML: ADJUST_OPTIONS.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  upColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: klineDraft.upColor,
      onInput: (e) => (klineDraft.upColor = e.target.value),
    }),
  },
  downColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: klineDraft.downColor,
      onInput: (e) => (klineDraft.downColor = e.target.value),
    }),
  },
  upFade: {
    component: UiNumberBox,
    getProps: () => ({
      modelValue: klineDraft.originalFadeUpPercent,
      min: UI_LIMITS.percentage.min,
      max: UI_LIMITS.percentage.max,
      step: UI_LIMITS.percentage.step,
      integer: true,
      "onUpdate:modelValue": (v) => (klineDraft.originalFadeUpPercent = v),
    }),
  },
  downFade: {
    component: UiNumberBox,
    getProps: () => ({
      modelValue: klineDraft.originalFadeDownPercent,
      min: UI_LIMITS.percentage.min,
      max: UI_LIMITS.percentage.max,
      step: UI_LIMITS.percentage.step,
      integer: true,
      "onUpdate:modelValue": (v) => (klineDraft.originalFadeDownPercent = v),
    }),
  },
  outlineWidth: {
    component: UiNumberBox,
    getProps: () => ({
      modelValue: klineDraft.mergedK.outlineWidth,
      min: UI_LIMITS.outlineWidth.min,
      max: UI_LIMITS.outlineWidth.max,
      step: UI_LIMITS.outlineWidth.step,
      "frac-digits": 1,
      "onUpdate:modelValue": (v) => (klineDraft.mergedK.outlineWidth = v),
    }),
  },
  mUpColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: klineDraft.mergedK.upColor,
      onInput: (e) => (klineDraft.mergedK.upColor = e.target.value),
    }),
  },
  mDownColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: klineDraft.mergedK.downColor,
      onInput: (e) => (klineDraft.mergedK.downColor = e.target.value),
    }),
  },
  fillFade: {
    component: UiNumberBox,
    getProps: () => ({
      modelValue: klineDraft.mergedK.fillFadePercent,
      min: UI_LIMITS.percentage.min,
      max: UI_LIMITS.percentage.max,
      step: UI_LIMITS.percentage.step,
      integer: true,
      "onUpdate:modelValue": (v) => (klineDraft.mergedK.fillFadePercent = v),
    }),
  },
  displayOrder: {
    component: "select",
    getProps: () => ({
      class: "input",
      value: klineDraft.mergedK.displayOrder,
      onChange: (e) => (klineDraft.mergedK.displayOrder = e.target.value),
      innerHTML: DISPLAY_ORDER_OPTIONS.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  "ma-width": {
    component: UiNumberBox,
    getProps: (item) => ({
      modelValue: maDraft[item.maKey].width,
      min: UI_LIMITS.lineWidth.min,
      max: UI_LIMITS.lineWidth.max,
      step: UI_LIMITS.lineWidth.step,
      "frac-digits": 1,
      "onUpdate:modelValue": (v) => (maDraft[item.maKey].width = v),
    }),
  },
  "ma-color": {
    component: "input",
    getProps: (item) => ({
      class: "input color",
      type: "color",
      value: maDraft[item.maKey].color,
      onInput: (e) => (maDraft[item.maKey].color = e.target.value),
    }),
  },
  "ma-style": {
    component: "select",
    getProps: (item) => ({
      class: "input",
      value: maDraft[item.maKey].style,
      onChange: (e) => (maDraft[item.maKey].style = e.target.value),
      innerHTML: LINE_STYLES.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  "ma-period": {
    component: UiNumberBox,
    getProps: (item) => ({
      modelValue: maDraft[item.maKey].period,
      min: UI_LIMITS.positiveInteger.min,
      step: UI_LIMITS.positiveInteger.step,
      integer: true,
      "onUpdate:modelValue": (v) => (maDraft[item.maKey].period = v),
    }),
  },
});
</script>
