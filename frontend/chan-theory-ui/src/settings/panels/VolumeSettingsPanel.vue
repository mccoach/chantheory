<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\panels\VolumeSettingsPanel.vue -->
<!-- ==============================
说明：量窗设置面板（UI-only）
- 职责：仅渲染成交量/成交额的设置UI。
- 数据流：通过 inject('volDraft') 获取响应式草稿，并直接绑定。
- 逻辑：MAVOL总控的三态切换逻辑 (useTriMasterToggle) 保留在此。
- 渲染：使用新的通用渲染器 useSettingsRenderer 简化控件创建。
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
  DEFAULT_VOL_SETTINGS,
  UI_LIMITS,
  MARKER_SHAPE_OPTIONS,
  LINE_STYLES,
} from "@/constants";
import { useTriMasterToggle } from "@/settings/common/useTriMasterToggle";
import { useSettingsRenderer } from "@/settings/common/useSettingsRenderer";

// 通过 inject 获取共享的草稿状态
const volDraft = inject("volDraft");

// MAVOL总控 (三态切换逻辑)
const mavolTri = useTriMasterToggle({
  items: Object.keys(volDraft.mavolStyles || {}).map((mk) => ({
    get: () => !!volDraft.mavolStyles?.[mk]?.enabled,
    set: (v) => {
      const conf = volDraft.mavolStyles[mk] || {};
      volDraft.mavolStyles[mk] = { ...conf, enabled: !!v };
    },
  })),
});

// 构建行定义
const rows = computed(() => {
  const vd = volDraft;
  const out = [];

  out.push({
    key: "vol-bar",
    name: "量额柱",
    items: [
      { key: "barPercent", label: "柱宽%" },
      { key: "upColor", label: "阳线颜色" },
      { key: "downColor", label: "阴线颜色" },
    ],
    check: { visible: false },
    reset: { visible: true, title: "恢复默认" },
  });

  out.push({
    key: "mavol-global",
    name: "均线总控",
    items: [],
    check: {
      type: "tri",
      checked: mavolTri.masterUi.checked.value,
      indeterminate: mavolTri.masterUi.indeterminate.value,
    },
    reset: { visible: false },
  });

  Object.entries(vd.mavolStyles || {}).forEach(([mk, conf]) => {
    out.push({
      key: `mavol-${mk}`,
      name: `MAVOL${conf.period}`,
      items: [
        { key: `mavol-width-${mk}`, label: "线宽" },
        { key: `mavol-color-${mk}`, label: "颜色" },
        { key: `mavol-style-${mk}`, label: "线型" },
        { key: `mavol-period-${mk}`, label: "周期" },
      ],
      check: { type: "single", checked: !!conf.enabled },
      reset: { visible: true, title: "恢复默认" },
    });
  });

  out.push({
    key: "marker-pump",
    name: "放量标记",
    items: [
      { key: "pump-shape", label: "形状" },
      { key: "pump-color", label: "颜色" },
      { key: "pump-threshold", label: "阈值" },
    ],
    check: { type: "single", checked: !!vd.markerPump.enabled },
    reset: { visible: true, title: "恢复默认" },
  });

  out.push({
    key: "marker-dump",
    name: "缩量标记",
    items: [
      { key: "dump-shape", label: "形状" },
      { key: "dump-color", label: "颜色" },
      { key: "dump-threshold", label: "阈值" },
    ],
    check: { type: "single", checked: !!vd.markerDump.enabled },
    reset: { visible: true, title: "恢复默认" },
  });

  return out;
});

// 行级事件处理器
function onRowToggle(row) {
  const key = String(row.key || "");
  const vd = volDraft;
  if (key === "mavol-global") {
    mavolTri.cycleOnce();
    return;
  }
  if (key.startsWith("mavol-")) {
    const mk = key.slice("mavol-".length);
    const conf = vd.mavolStyles[mk];
    if (conf) {
      conf.enabled = !conf.enabled;
      mavolTri.updateSnapshot();
    }
    return;
  }
  if (key === "marker-pump") vd.markerPump.enabled = !vd.markerPump.enabled;
  if (key === "marker-dump") vd.markerDump.enabled = !vd.markerDump.enabled;
}

function onRowReset(row) {
  const key = String(row.key || "");
  const vd = volDraft;
  if (key === "vol-bar") {
    vd.volBar = { ...DEFAULT_VOL_SETTINGS.volBar };
    return;
  }
  if (key.startsWith("mavol-")) {
    const mk = key.slice("mavol-".length);
    if (DEFAULT_VOL_SETTINGS.mavolStyles[mk]) {
      vd.mavolStyles[mk] = { ...DEFAULT_VOL_SETTINGS.mavolStyles[mk] };
      mavolTri.updateSnapshot();
    }
    return;
  }
  if (key === "marker-pump")
    vd.markerPump = { ...DEFAULT_VOL_SETTINGS.markerPump };
  if (key === "marker-dump")
    vd.markerDump = { ...DEFAULT_VOL_SETTINGS.markerDump };
}

// 使用通用渲染器
const { renderControl } = useSettingsRenderer({
  barPercent: {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: volDraft.volBar.barPercent,
      min: UI_LIMITS.barWidthPercent.min,
      max: UI_LIMITS.barWidthPercent.max,
      step: UI_LIMITS.barWidthPercent.step,
      integer: true,
      "onUpdate:modelValue": (v) => (volDraft.volBar.barPercent = v),
    }),
  },
  upColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: volDraft.volBar.upColor,
      onInput: (e) => (volDraft.volBar.upColor = e.target.value),
    }),
  },
  downColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: volDraft.volBar.downColor,
      onInput: (e) => (volDraft.volBar.downColor = e.target.value),
    }),
  },
  ...Object.fromEntries(
    Object.keys(DEFAULT_VOL_SETTINGS.mavolStyles).flatMap((mk) => [
      [
        `mavol-width-${mk}`,
        {
          component: NumberSpinner,
          getProps: () => ({
            modelValue: volDraft.mavolStyles[mk].width,
            min: UI_LIMITS.lineWidth.min,
            max: UI_LIMITS.lineWidth.max,
            step: UI_LIMITS.lineWidth.step,
            "frac-digits": 1,
            "onUpdate:modelValue": (v) => (volDraft.mavolStyles[mk].width = v),
          }),
        },
      ],
      [
        `mavol-color-${mk}`,
        {
          component: "input",
          getProps: () => ({
            class: "input color",
            type: "color",
            value: volDraft.mavolStyles[mk].color,
            onInput: (e) => (volDraft.mavolStyles[mk].color = e.target.value),
          }),
        },
      ],
      [
        `mavol-style-${mk}`,
        {
          component: "select",
          getProps: () => ({
            class: "input",
            value: volDraft.mavolStyles[mk].style,
            onChange: (e) => (volDraft.mavolStyles[mk].style = e.target.value),
            innerHTML: LINE_STYLES.map(
              (o) => `<option value="${o.v}">${o.label}</option>`
            ).join(""),
          }),
        },
      ],
      [
        `mavol-period-${mk}`,
        {
          component: NumberSpinner,
          getProps: () => ({
            modelValue: volDraft.mavolStyles[mk].period,
            min: UI_LIMITS.positiveInteger.min,
            step: UI_LIMITS.positiveInteger.step,
            integer: true,
            "onUpdate:modelValue": (v) => (volDraft.mavolStyles[mk].period = v),
          }),
        },
      ],
    ])
  ),
  "pump-shape": {
    component: "select",
    getProps: () => ({
      class: "input",
      value: volDraft.markerPump.shape,
      onChange: (e) => (volDraft.markerPump.shape = e.target.value),
      innerHTML: MARKER_SHAPE_OPTIONS.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  "pump-color": {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: volDraft.markerPump.color,
      onInput: (e) => (volDraft.markerPump.color = e.target.value),
    }),
  },
  "pump-threshold": {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: volDraft.markerPump.threshold,
      min: UI_LIMITS.nonNegativeFloat.min,
      step: UI_LIMITS.nonNegativeFloat.step,
      "frac-digits": 1,
      "onUpdate:modelValue": (v) => (volDraft.markerPump.threshold = v),
    }),
  },
  "dump-shape": {
    component: "select",
    getProps: () => ({
      class: "input",
      value: volDraft.markerDump.shape,
      onChange: (e) => (volDraft.markerDump.shape = e.target.value),
      innerHTML: MARKER_SHAPE_OPTIONS.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  "dump-color": {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: volDraft.markerDump.color,
      onInput: (e) => (volDraft.markerDump.color = e.target.value),
    }),
  },
  "dump-threshold": {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: volDraft.markerDump.threshold,
      min: UI_LIMITS.nonNegativeFloat.min,
      step: UI_LIMITS.nonNegativeFloat.step,
      "frac-digits": 1,
      "onUpdate:modelValue": (v) => (volDraft.markerDump.threshold = v),
    }),
  },
});
</script>