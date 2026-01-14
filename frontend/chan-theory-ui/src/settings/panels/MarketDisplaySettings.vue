<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\panels\MarketDisplaySettings.vue -->
<!-- ==============================
说明：行情设置面板（新版：UI-only, 数据驱动渲染）
本轮修复：
  - 均线总控 controller 改为稳定实例（禁止 computed 重建导致 snapshot 被重置）
  - keys 使用 DEFAULT_MA_CONFIGS 的稳定键集合
  - 三态规则：snapshot -> all -> none -> snapshot；退化两态仅当 snapshot 本身退化
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
import {
  DEFAULT_KLINE_STYLE,
  DEFAULT_MA_CONFIGS,
  LINE_STYLES,
  DISPLAY_ORDER_OPTIONS,
  UI_LIMITS,
} from "@/constants";
import NumberSpinner from "@/components/ui/NumberSpinner.vue";
import { createBooleanGroupTriController } from "@/composables/useTriToggle";
import {
  useSettingsRenderer,
  makeNativeSelect,
  makeColorInput,
  makeNumberSpinner,
} from "@/settings/common/useSettingsRenderer";

const klineDraft = inject("klineDraft");
const maDraft = inject("maDraft");

const klineResetter = inject("klineResetter");
const maResetter = inject("maResetter");

// === 关键修复：keys 固定 + controller 单例（不可 computed 重建） ===
const MA_KEYS = Object.keys(DEFAULT_MA_CONFIGS);

function getMaEnabled(k) {
  const key = String(k || "");
  return !!maDraft?.[key]?.enabled;
}

function setMaEnabled(k, v) {
  const key = String(k || "");
  if (!key || !maDraft?.[key]) return;
  const conf = maDraft[key] || {};
  maDraft[key] = { ...conf, enabled: !!v };
}

const maTri = createBooleanGroupTriController({
  scopeKey: "maMaster",
  keys: MA_KEYS,
  get: getMaEnabled,
  set: setMaEnabled,
});

const rows = computed(() => {
  const k = klineDraft || DEFAULT_KLINE_STYLE;
  const maMap = maDraft || {};
  const out = [];

  out.push({
    key: "k-original",
    name: "原始K线",
    items: [
      { key: "barPercent", label: "柱宽%" },
      { key: "upColor", label: "阳线颜色" },
      { key: "upFade", label: "阳线淡显" },
      { key: "downColor", label: "阴线颜色" },
      { key: "downFade", label: "阴线淡显" },
    ],
    check: { type: "single", checked: !!k.originalEnabled },
    reset: { visible: true, title: "恢复默认" },
  });

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

  const ui = maTri.getUi();

  out.push({
    key: "ma-global",
    name: "均线总控",
    items: [],
    check: {
      type: "tri",
      checked: !!ui.checked,
      indeterminate: !!ui.indeterminate,
    },
    reset: { visible: false },
  });

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

function onRowToggle(row) {
  const key = String(row.key || "");

  if (key === "ma-global") {
    maTri.cycle();
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
      maTri.syncSnapshotFromCurrent(); // external change -> 更新 snapshot（规则2）
    }
  }
}

function onRowReset(row) {
  const key = String(row.key || "");
  if (key === "k-original") {
    klineResetter?.resetPath("barPercent");
    klineResetter?.resetPath("upColor");
    klineResetter?.resetPath("downColor");
    klineResetter?.resetPath("originalFadeUpPercent");
    klineResetter?.resetPath("originalFadeDownPercent");
    klineResetter?.resetPath("originalEnabled");
    return;
  }
  if (key === "k-merged") {
    klineResetter?.resetPath("mergedK");
    klineResetter?.resetPath("mergedEnabled");
    return;
  }
  if (key.startsWith("ma-")) {
    const mk = key.slice(3);
    maResetter?.resetPath(mk);
    maTri.syncSnapshotFromCurrent();
  }
}

const { renderControl } = useSettingsRenderer({
  barPercent: makeNumberSpinner({
    component: NumberSpinner,
    get: () => klineDraft.barPercent,
    set: (_, v) => (klineDraft.barPercent = v),
    min: UI_LIMITS.barWidthPercent.min,
    max: UI_LIMITS.barWidthPercent.max,
    step: UI_LIMITS.barWidthPercent.step,
    integer: true,
  }),

  upColor: makeColorInput({
    get: () => klineDraft.upColor,
    set: (_, v) => (klineDraft.upColor = v),
  }),

  downColor: makeColorInput({
    get: () => klineDraft.downColor,
    set: (_, v) => (klineDraft.downColor = v),
  }),

  upFade: makeNumberSpinner({
    component: NumberSpinner,
    get: () => klineDraft.originalFadeUpPercent,
    set: (_, v) => (klineDraft.originalFadeUpPercent = v),
    min: UI_LIMITS.percentage.min,
    max: UI_LIMITS.percentage.max,
    step: UI_LIMITS.percentage.step,
    integer: true,
  }),

  downFade: makeNumberSpinner({
    component: NumberSpinner,
    get: () => klineDraft.originalFadeDownPercent,
    set: (_, v) => (klineDraft.originalFadeDownPercent = v),
    min: UI_LIMITS.percentage.min,
    max: UI_LIMITS.percentage.max,
    step: UI_LIMITS.percentage.step,
    integer: true,
  }),

  outlineWidth: makeNumberSpinner({
    component: NumberSpinner,
    get: () => klineDraft.mergedK.outlineWidth,
    set: (_, v) => (klineDraft.mergedK.outlineWidth = v),
    min: UI_LIMITS.outlineWidth.min,
    max: UI_LIMITS.outlineWidth.max,
    step: UI_LIMITS.outlineWidth.step,
    fracDigits: 1,
  }),

  mUpColor: makeColorInput({
    get: () => klineDraft.mergedK.upColor,
    set: (_, v) => (klineDraft.mergedK.upColor = v),
  }),

  mDownColor: makeColorInput({
    get: () => klineDraft.mergedK.downColor,
    set: (_, v) => (klineDraft.mergedK.downColor = v),
  }),

  fillFade: makeNumberSpinner({
    component: NumberSpinner,
    get: () => klineDraft.mergedK.fillFadePercent,
    set: (_, v) => (klineDraft.mergedK.fillFadePercent = v),
    min: UI_LIMITS.percentage.min,
    max: UI_LIMITS.percentage.max,
    step: UI_LIMITS.percentage.step,
    integer: true,
  }),

  displayOrder: makeNativeSelect({
    options: DISPLAY_ORDER_OPTIONS,
    get: () => klineDraft.mergedK.displayOrder,
    set: (_, v) => (klineDraft.mergedK.displayOrder = v),
  }),

  "ma-width": makeNumberSpinner({
    component: NumberSpinner,
    get: (item) => maDraft[item.maKey].width,
    set: (item, v) => (maDraft[item.maKey].width = v),
    min: UI_LIMITS.lineWidth.min,
    max: UI_LIMITS.lineWidth.max,
    step: UI_LIMITS.lineWidth.step,
    fracDigits: 1,
  }),

  "ma-color": makeColorInput({
    get: (item) => maDraft[item.maKey].color,
    set: (item, v) => (maDraft[item.maKey].color = v),
  }),

  "ma-style": makeNativeSelect({
    options: LINE_STYLES,
    get: (item) => maDraft[item.maKey].style,
    set: (item, v) => (maDraft[item.maKey].style = v),
  }),

  "ma-period": makeNumberSpinner({
    component: NumberSpinner,
    get: (item) => maDraft[item.maKey].period,
    set: (item, v) => (maDraft[item.maKey].period = v),
    min: UI_LIMITS.positiveInteger.min,
    step: UI_LIMITS.positiveInteger.step,
    integer: true,
  }),
});
</script>
