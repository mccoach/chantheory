<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\panels\AtrStopSettingsPanel.vue -->
<!-- ==============================
说明：ATR_stop 设置面板（最终线专用 + 止损标记）
本轮改动：
  - 止损标记行回归通用渲染器（统一渲染方式）
  - select 统一改为 options children 渲染（不再使用 innerHTML 拼接）
  - 控件 getProps 样板代码用工厂函数标准化复用（但保留嵌套对象写回的显式逻辑）
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
import {
  DEFAULT_ATR_STOP_SETTINGS,
  ATR_BREACH_DEFAULTS,
  UI_LIMITS,
  LINE_STYLES,
  MARKER_SHAPE_OPTIONS,
  FILL_OPTIONS,
} from "@/constants";
import {
  useSettingsRenderer,
  makeNativeSelect,
  makeColorInput,
  makeNumberSpinner,
} from "@/settings/common/useSettingsRenderer";

const atrStopDraft = inject("atrStopDraft");
const atrStopResetter = inject("atrStopResetter", null);

const atrBreachDraft = inject("atrBreachDraft");
const atrBreachResetter = inject("atrBreachResetter", null);

const rows = computed(() => {
  const s = atrStopDraft || DEFAULT_ATR_STOP_SETTINGS;
  const b = atrBreachDraft || ATR_BREACH_DEFAULTS;
  const out = [];

  out.push({
    key: "atr-fixed-long",
    name: "倍数止损-多",
    items: [
      { key: "fixedLongWidth", label: "线宽" },
      { key: "fixedLongColor", label: "颜色" },
      { key: "fixedLongStyle", label: "线型" },
      { key: "fixedLongAtrPeriod", label: "MA周期" },
    ],
    check: { type: "single", checked: !!s.fixed?.long?.enabled },
    reset: { visible: true, title: "恢复默认" },
  });

  out.push({
    key: "atr-fixed-short",
    name: "倍数止损-空",
    items: [
      { key: "fixedShortWidth", label: "线宽" },
      { key: "fixedShortColor", label: "颜色" },
      { key: "fixedShortStyle", label: "线型" },
      { key: "fixedShortAtrPeriod", label: "MA周期" },
    ],
    check: { type: "single", checked: !!s.fixed?.short?.enabled },
    reset: { visible: true, title: "恢复默认" },
  });

  out.push({
    key: "atr-chan-long",
    name: "波动止损-多",
    items: [
      { key: "chanLongWidth", label: "线宽" },
      { key: "chanLongColor", label: "颜色" },
      { key: "chanLongStyle", label: "线型" },
      { key: "chanLongAtrPeriod", label: "MA周期" },
      { key: "chanLongLookback", label: "回顾周期" },
    ],
    check: { type: "single", checked: !!s.chandelier?.long?.enabled },
    reset: { visible: true, title: "恢复默认" },
  });

  out.push({
    key: "atr-chan-short",
    name: "波动止损-空",
    items: [
      { key: "chanShortWidth", label: "线宽" },
      { key: "chanShortColor", label: "颜色" },
      { key: "chanShortStyle", label: "线型" },
      { key: "chanShortAtrPeriod", label: "MA周期" },
      { key: "chanShortLookback", label: "回顾周期" },
    ],
    check: { type: "single", checked: !!s.chandelier?.short?.enabled },
    reset: { visible: true, title: "恢复默认" },
  });

  out.push({
    key: "atr-breach-marker",
    name: "止损标记",
    items: [
      { key: "atrBreachShape", label: "符号" },
      { key: "atrBreachFill", label: "填充" },
      { key: "atrBreachMarkerPercent", label: "标记宽%" },
    ],
    check: { type: "single", checked: !!b.enabled },
    reset: { visible: true, title: "恢复默认" },
  });

  return out;
});

function onRowToggle(row) {
  const key = String(row.key || "");

  if (key === "atr-fixed-long") {
    atrStopDraft.fixed = {
      ...(atrStopDraft.fixed || {}),
      long: {
        ...(atrStopDraft.fixed?.long || {}),
        enabled: !(atrStopDraft.fixed?.long?.enabled ?? DEFAULT_ATR_STOP_SETTINGS.fixed.long.enabled),
      },
    };
    return;
  }

  if (key === "atr-fixed-short") {
    atrStopDraft.fixed = {
      ...(atrStopDraft.fixed || {}),
      short: {
        ...(atrStopDraft.fixed?.short || {}),
        enabled: !(atrStopDraft.fixed?.short?.enabled ?? DEFAULT_ATR_STOP_SETTINGS.fixed.short.enabled),
      },
    };
    return;
  }

  if (key === "atr-chan-long") {
    atrStopDraft.chandelier = {
      ...(atrStopDraft.chandelier || {}),
      long: {
        ...(atrStopDraft.chandelier?.long || {}),
        enabled: !(atrStopDraft.chandelier?.long?.enabled ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.long.enabled),
      },
    };
    return;
  }

  if (key === "atr-chan-short") {
    atrStopDraft.chandelier = {
      ...(atrStopDraft.chandelier || {}),
      short: {
        ...(atrStopDraft.chandelier?.short || {}),
        enabled: !(atrStopDraft.chandelier?.short?.enabled ?? DEFAULT_ATR_STOP_SETTINGS.chandelier.short.enabled),
      },
    };
    return;
  }

  if (key === "atr-breach-marker") {
    atrBreachDraft.enabled = !(atrBreachDraft.enabled ?? ATR_BREACH_DEFAULTS.enabled);
  }
}

function onRowReset(row) {
  const key = String(row.key || "");

  if (key === "atr-fixed-long") {
    atrStopResetter?.resetPath("fixed.long");
    return;
  }
  if (key === "atr-fixed-short") {
    atrStopResetter?.resetPath("fixed.short");
    return;
  }
  if (key === "atr-chan-long") {
    atrStopResetter?.resetPath("chandelier.long");
    return;
  }
  if (key === "atr-chan-short") {
    atrStopResetter?.resetPath("chandelier.short");
    return;
  }

  if (key === "atr-breach-marker") {
    atrBreachResetter?.resetAll();
  }
}

const { renderControl } = useSettingsRenderer({
  fixedLongWidth: makeNumberSpinner({
    component: NumberSpinner,
    get: () => atrStopDraft.fixed?.long?.lineWidth,
    set: (_, v) => {
      atrStopDraft.fixed = {
        ...(atrStopDraft.fixed || {}),
        long: { ...(atrStopDraft.fixed?.long || {}), lineWidth: v },
      };
    },
    min: UI_LIMITS.lineWidth.min,
    max: UI_LIMITS.lineWidth.max,
    step: UI_LIMITS.lineWidth.step,
    fracDigits: 1,
  }),

  fixedLongColor: makeColorInput({
    get: () => atrStopDraft.fixed?.long?.color,
    set: (_, v) => {
      atrStopDraft.fixed = {
        ...(atrStopDraft.fixed || {}),
        long: { ...(atrStopDraft.fixed?.long || {}), color: v },
      };
    },
  }),

  fixedLongStyle: makeNativeSelect({
    options: LINE_STYLES,
    get: () => atrStopDraft.fixed?.long?.lineStyle,
    set: (_, v) => {
      atrStopDraft.fixed = {
        ...(atrStopDraft.fixed || {}),
        long: { ...(atrStopDraft.fixed?.long || {}), lineStyle: v },
      };
    },
  }),

  fixedLongAtrPeriod: makeNumberSpinner({
    component: NumberSpinner,
    get: () => atrStopDraft.fixed?.long?.atrPeriod,
    set: (_, v) => {
      atrStopDraft.fixed = {
        ...(atrStopDraft.fixed || {}),
        long: { ...(atrStopDraft.fixed?.long || {}), atrPeriod: v },
      };
    },
    min: UI_LIMITS.positiveInteger.min,
    step: UI_LIMITS.positiveInteger.step,
    integer: true,
  }),

  fixedShortWidth: makeNumberSpinner({
    component: NumberSpinner,
    get: () => atrStopDraft.fixed?.short?.lineWidth,
    set: (_, v) => {
      atrStopDraft.fixed = {
        ...(atrStopDraft.fixed || {}),
        short: { ...(atrStopDraft.fixed?.short || {}), lineWidth: v },
      };
    },
    min: UI_LIMITS.lineWidth.min,
    max: UI_LIMITS.lineWidth.max,
    step: UI_LIMITS.lineWidth.step,
    fracDigits: 1,
  }),

  fixedShortColor: makeColorInput({
    get: () => atrStopDraft.fixed?.short?.color,
    set: (_, v) => {
      atrStopDraft.fixed = {
        ...(atrStopDraft.fixed || {}),
        short: { ...(atrStopDraft.fixed?.short || {}), color: v },
      };
    },
  }),

  fixedShortStyle: makeNativeSelect({
    options: LINE_STYLES,
    get: () => atrStopDraft.fixed?.short?.lineStyle,
    set: (_, v) => {
      atrStopDraft.fixed = {
        ...(atrStopDraft.fixed || {}),
        short: { ...(atrStopDraft.fixed?.short || {}), lineStyle: v },
      };
    },
  }),

  fixedShortAtrPeriod: makeNumberSpinner({
    component: NumberSpinner,
    get: () => atrStopDraft.fixed?.short?.atrPeriod,
    set: (_, v) => {
      atrStopDraft.fixed = {
        ...(atrStopDraft.fixed || {}),
        short: { ...(atrStopDraft.fixed?.short || {}), atrPeriod: v },
      };
    },
    min: UI_LIMITS.positiveInteger.min,
    step: UI_LIMITS.positiveInteger.step,
    integer: true,
  }),

  chanLongWidth: makeNumberSpinner({
    component: NumberSpinner,
    get: () => atrStopDraft.chandelier?.long?.lineWidth,
    set: (_, v) => {
      atrStopDraft.chandelier = {
        ...(atrStopDraft.chandelier || {}),
        long: { ...(atrStopDraft.chandelier?.long || {}), lineWidth: v },
      };
    },
    min: UI_LIMITS.lineWidth.min,
    max: UI_LIMITS.lineWidth.max,
    step: UI_LIMITS.lineWidth.step,
    fracDigits: 1,
  }),

  chanLongColor: makeColorInput({
    get: () => atrStopDraft.chandelier?.long?.color,
    set: (_, v) => {
      atrStopDraft.chandelier = {
        ...(atrStopDraft.chandelier || {}),
        long: { ...(atrStopDraft.chandelier?.long || {}), color: v },
      };
    },
  }),

  chanLongStyle: makeNativeSelect({
    options: LINE_STYLES,
    get: () => atrStopDraft.chandelier?.long?.lineStyle,
    set: (_, v) => {
      atrStopDraft.chandelier = {
        ...(atrStopDraft.chandelier || {}),
        long: { ...(atrStopDraft.chandelier?.long || {}), lineStyle: v },
      };
    },
  }),

  chanLongAtrPeriod: makeNumberSpinner({
    component: NumberSpinner,
    get: () => atrStopDraft.chandelier?.long?.atrPeriod,
    set: (_, v) => {
      atrStopDraft.chandelier = {
        ...(atrStopDraft.chandelier || {}),
        long: { ...(atrStopDraft.chandelier?.long || {}), atrPeriod: v },
      };
    },
    min: UI_LIMITS.positiveInteger.min,
    step: UI_LIMITS.positiveInteger.step,
    integer: true,
  }),

  chanLongLookback: makeNumberSpinner({
    component: NumberSpinner,
    get: () => atrStopDraft.chandelier?.long?.lookback,
    set: (_, v) => {
      atrStopDraft.chandelier = {
        ...(atrStopDraft.chandelier || {}),
        long: { ...(atrStopDraft.chandelier?.long || {}), lookback: v },
      };
    },
    min: UI_LIMITS.positiveInteger.min,
    step: UI_LIMITS.positiveInteger.step,
    integer: true,
  }),

  chanShortWidth: makeNumberSpinner({
    component: NumberSpinner,
    get: () => atrStopDraft.chandelier?.short?.lineWidth,
    set: (_, v) => {
      atrStopDraft.chandelier = {
        ...(atrStopDraft.chandelier || {}),
        short: { ...(atrStopDraft.chandelier?.short || {}), lineWidth: v },
      };
    },
    min: UI_LIMITS.lineWidth.min,
    max: UI_LIMITS.lineWidth.max,
    step: UI_LIMITS.lineWidth.step,
    fracDigits: 1,
  }),

  chanShortColor: makeColorInput({
    get: () => atrStopDraft.chandelier?.short?.color,
    set: (_, v) => {
      atrStopDraft.chandelier = {
        ...(atrStopDraft.chandelier || {}),
        short: { ...(atrStopDraft.chandelier?.short || {}), color: v },
      };
    },
  }),

  chanShortStyle: makeNativeSelect({
    options: LINE_STYLES,
    get: () => atrStopDraft.chandelier?.short?.lineStyle,
    set: (_, v) => {
      atrStopDraft.chandelier = {
        ...(atrStopDraft.chandelier || {}),
        short: { ...(atrStopDraft.chandelier?.short || {}), lineStyle: v },
      };
    },
  }),

  chanShortAtrPeriod: makeNumberSpinner({
    component: NumberSpinner,
    get: () => atrStopDraft.chandelier?.short?.atrPeriod,
    set: (_, v) => {
      atrStopDraft.chandelier = {
        ...(atrStopDraft.chandelier || {}),
        short: { ...(atrStopDraft.chandelier?.short || {}), atrPeriod: v },
      };
    },
    min: UI_LIMITS.positiveInteger.min,
    step: UI_LIMITS.positiveInteger.step,
    integer: true,
  }),

  chanShortLookback: makeNumberSpinner({
    component: NumberSpinner,
    get: () => atrStopDraft.chandelier?.short?.lookback,
    set: (_, v) => {
      atrStopDraft.chandelier = {
        ...(atrStopDraft.chandelier || {}),
        short: { ...(atrStopDraft.chandelier?.short || {}), lookback: v },
      };
    },
    min: UI_LIMITS.positiveInteger.min,
    step: UI_LIMITS.positiveInteger.step,
    integer: true,
  }),

  atrBreachShape: makeNativeSelect({
    options: MARKER_SHAPE_OPTIONS,
    get: () => atrBreachDraft.shape,
    set: (_, v) => (atrBreachDraft.shape = v),
  }),

  atrBreachFill: makeNativeSelect({
    options: FILL_OPTIONS,
    get: () => atrBreachDraft.fill,
    set: (_, v) => (atrBreachDraft.fill = v),
  }),

  atrBreachMarkerPercent: makeNumberSpinner({
    component: NumberSpinner,
    get: () => atrBreachDraft.markerPercent,
    set: (_, v) => (atrBreachDraft.markerPercent = v),
    min: UI_LIMITS.markerWidthPercent.min,
    max: UI_LIMITS.markerWidthPercent.max,
    step: UI_LIMITS.markerWidthPercent.step,
    integer: true,
  }),
});
</script>
