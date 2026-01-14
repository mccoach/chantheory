<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\panels\VolumeSettingsPanel.vue -->
<!-- ==============================
说明：量窗设置面板（UI-only）
本轮修复：
  - MAVOL 总控 controller 改为稳定实例（禁止 computed 重建导致 snapshot 被重置）
  - keys 使用 DEFAULT_VOL_SETTINGS.mavolStyles 的稳定键集合
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
  DEFAULT_VOL_SETTINGS,
  UI_LIMITS,
  MARKER_SHAPE_OPTIONS,
  LINE_STYLES,
} from "@/constants";
import { createBooleanGroupTriController } from "@/composables/useTriToggle";
import {
  useSettingsRenderer,
  makeNativeSelect,
  makeColorInput,
  makeNumberSpinner,
} from "@/settings/common/useSettingsRenderer";

const volDraft = inject("volDraft");
const volResetter = inject("volResetter");

// === 关键修复：keys 固定 + controller 单例（不可 computed 重建） ===
const MAVOL_KEYS = Object.keys(DEFAULT_VOL_SETTINGS.mavolStyles || {});

function getMavolEnabled(k) {
  const key = String(k || "");
  return !!volDraft?.mavolStyles?.[key]?.enabled;
}

function setMavolEnabled(k, v) {
  const key = String(k || "");
  const conf = volDraft?.mavolStyles?.[key];
  if (!conf) return;
  volDraft.mavolStyles[key] = { ...(conf || {}), enabled: !!v };
}

const mavolTri = createBooleanGroupTriController({
  scopeKey: "mavolMaster",
  keys: MAVOL_KEYS,
  get: getMavolEnabled,
  set: setMavolEnabled,
});

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

  const ui = mavolTri.getUi();

  out.push({
    key: "mavol-global",
    name: "均线总控",
    items: [],
    check: {
      type: "tri",
      checked: ui.checked,
      indeterminate: ui.indeterminate,
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
      { key: "markerPercent", label: "标记宽%" },
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

function onRowToggle(row) {
  const key = String(row.key || "");
  const vd = volDraft;

  if (key === "mavol-global") {
    mavolTri.cycle();
    return;
  }

  if (key.startsWith("mavol-")) {
    const mk = key.slice("mavol-".length);
    const conf = vd.mavolStyles[mk];
    if (conf) {
      conf.enabled = !conf.enabled;
      mavolTri.syncSnapshotFromCurrent(); // external change -> 更新 snapshot（规则2）
    }
    return;
  }

  if (key === "marker-pump") vd.markerPump.enabled = !vd.markerPump.enabled;
  if (key === "marker-dump") vd.markerDump.enabled = !vd.markerDump.enabled;
}

function onRowReset(row) {
  const key = String(row.key || "");

  if (key === "vol-bar") {
    volResetter?.resetPath("volBar");
    return;
  }

  if (key.startsWith("mavol-")) {
    const mk = key.slice("mavol-".length);
    volResetter?.resetPath(`mavolStyles.${mk}`);
    mavolTri.syncSnapshotFromCurrent();
    return;
  }

  if (key === "marker-pump") {
    volResetter?.resetPath("markerPump");
    volResetter?.resetPath("markerPercent");
    return;
  }

  if (key === "marker-dump") {
    volResetter?.resetPath("markerDump");
  }
}

const { renderControl } = useSettingsRenderer({
  barPercent: makeNumberSpinner({
    component: NumberSpinner,
    get: () => volDraft.volBar.barPercent,
    set: (_, v) => (volDraft.volBar.barPercent = v),
    min: UI_LIMITS.barWidthPercent.min,
    max: UI_LIMITS.barWidthPercent.max,
    step: UI_LIMITS.barWidthPercent.step,
    integer: true,
  }),

  upColor: makeColorInput({
    get: () => volDraft.volBar.upColor,
    set: (_, v) => (volDraft.volBar.upColor = v),
  }),

  downColor: makeColorInput({
    get: () => volDraft.volBar.downColor,
    set: (_, v) => (volDraft.volBar.downColor = v),
  }),

  markerPercent: makeNumberSpinner({
    component: NumberSpinner,
    get: () => volDraft.markerPercent,
    set: (_, v) => (volDraft.markerPercent = v),
    min: UI_LIMITS.markerWidthPercent.min,
    max: UI_LIMITS.markerWidthPercent.max,
    step: UI_LIMITS.markerWidthPercent.step,
    integer: true,
  }),

  ...Object.fromEntries(
    Object.keys(DEFAULT_VOL_SETTINGS.mavolStyles).flatMap((mk) => [
      [
        `mavol-width-${mk}`,
        makeNumberSpinner({
          component: NumberSpinner,
          get: () => volDraft.mavolStyles[mk].width,
          set: (_, v) => (volDraft.mavolStyles[mk].width = v),
          min: UI_LIMITS.lineWidth.min,
          max: UI_LIMITS.lineWidth.max,
          step: UI_LIMITS.lineWidth.step,
          fracDigits: 1,
        }),
      ],
      [
        `mavol-color-${mk}`,
        makeColorInput({
          get: () => volDraft.mavolStyles[mk].color,
          set: (_, v) => (volDraft.mavolStyles[mk].color = v),
        }),
      ],
      [
        `mavol-style-${mk}`,
        makeNativeSelect({
          options: LINE_STYLES,
          get: () => volDraft.mavolStyles[mk].style,
          set: (_, v) => (volDraft.mavolStyles[mk].style = v),
        }),
      ],
      [
        `mavol-period-${mk}`,
        makeNumberSpinner({
          component: NumberSpinner,
          get: () => volDraft.mavolStyles[mk].period,
          set: (_, v) => (volDraft.mavolStyles[mk].period = v),
          min: UI_LIMITS.positiveInteger.min,
          step: UI_LIMITS.positiveInteger.step,
          integer: true,
        }),
      ],
    ])
  ),

  "pump-shape": makeNativeSelect({
    options: MARKER_SHAPE_OPTIONS,
    get: () => volDraft.markerPump.shape,
    set: (_, v) => (volDraft.markerPump.shape = v),
  }),

  "pump-color": makeColorInput({
    get: () => volDraft.markerPump.color,
    set: (_, v) => (volDraft.markerPump.color = v),
  }),

  "pump-threshold": makeNumberSpinner({
    component: NumberSpinner,
    get: () => volDraft.markerPump.threshold,
    set: (_, v) => (volDraft.markerPump.threshold = v),
    min: UI_LIMITS.nonNegativeFloat.min,
    step: UI_LIMITS.nonNegativeFloat.step,
    fracDigits: 1,
  }),

  "dump-shape": makeNativeSelect({
    options: MARKER_SHAPE_OPTIONS,
    get: () => volDraft.markerDump.shape,
    set: (_, v) => (volDraft.markerDump.shape = v),
  }),

  "dump-color": makeColorInput({
    get: () => volDraft.markerDump.color,
    set: (_, v) => (volDraft.markerDump.color = v),
  }),

  "dump-threshold": makeNumberSpinner({
    component: NumberSpinner,
    get: () => volDraft.markerDump.threshold,
    set: (_, v) => (volDraft.markerDump.threshold = v),
    min: UI_LIMITS.nonNegativeFloat.min,
    step: UI_LIMITS.nonNegativeFloat.step,
    fracDigits: 1,
  }),
});
</script>
