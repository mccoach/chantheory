<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\panels\ChanTheorySettings.vue -->
<!-- ==============================
说明：缠论设置面板（新版：UI-only）
- 职责：仅负责渲染缠论相关的设置UI，不再管理状态。
- 数据流：通过 `inject` 获取来自外壳的响应式草稿对象 (chanDraft, fractalDraft)，并直接绑定。
- 逻辑：分型总控的三态切换逻辑 (useTriMasterToggle) 依然保留在此，因为它与 UI 渲染紧密相关。
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
  CHAN_DEFAULTS,
  FRACTAL_DEFAULTS,
  LINE_STYLES,
  ANCHOR_POLICY_OPTIONS,
  MIN_COND_OPTIONS,
  CHAN_PEN_PIVOT_DEFAULTS,
  SEGMENT_DEFAULTS,
  PENS_DEFAULTS,
  UI_LIMITS,
  MARKER_SHAPE_OPTIONS,
  FILL_OPTIONS,
} from "@/constants";
import { useTriMasterToggle } from "@/settings/common/useTriMasterToggle";
import { useSettingsRenderer } from "@/settings/common/useSettingsRenderer";

// 通过 inject 获取共享的草稿状态
const chanDraft = inject("chanDraft");
const fractalDraft = inject("fractalDraft");

// 分型总控（强/标/弱/确认）
const frTri = useTriMasterToggle({
  items: ["strong", "standard", "weak"]
    .map((lvl) => ({
      get: () => !!fractalDraft?.styleByStrength?.[lvl]?.enabled,
      set: (v) => {
        const s = fractalDraft.styleByStrength || {};
        const conf = s[lvl] || {};
        s[lvl] = { ...conf, enabled: !!v };
        fractalDraft.styleByStrength = s;
        const ss = fractalDraft.showStrength || {};
        fractalDraft.showStrength = { ...ss, [lvl]: !!v };
      },
    }))
    .concat([
      {
        get: () => !!fractalDraft?.confirmStyle?.enabled,
        set: (v) => {
          const cs = fractalDraft.confirmStyle || {};
          fractalDraft.confirmStyle = { ...cs, enabled: !!v };
        },
      },
    ]),
});

// 构建行定义
const rows = computed(() => {
  const cf = chanDraft || {};
  const ff = fractalDraft || {};
  const out = [];

  // 涨跌标记
  out.push({
    key: "chan-updown",
    name: "涨跌标记",
    items: [
      { key: "upShape", label: "上涨符号" },
      { key: "upColor", label: "上涨颜色" },
      { key: "downShape", label: "下跌符号" },
      { key: "downColor", label: "下跌颜色" },
      { key: "anchorPolicy", label: "承载点" },
    ],
    check: { type: "single", checked: !!cf.showUpDownMarkers },
    reset: { visible: true, title: "恢复默认" },
  });

  // 分型总控（显著度参数 + 总控复选）
  out.push({
    key: "fr-global",
    name: "分型判定",
    items: [
      { key: "fr-minTick", label: "最小tick" },
      { key: "fr-minPct", label: "最小幅度%" },
      { key: "fr-minCond", label: "判断条件" },
    ],
    check: {
      type: "tri",
      checked: !!frTri.masterUi.checked.value,
      indeterminate: !!frTri.masterUi.indeterminate.value,
    },
    reset: { visible: true, title: "恢复默认" },
  });

  // 强/标准/弱/确认
  const kindList = [
    { k: "strong", label: "强分型" },
    { k: "standard", label: "标准分型" },
    { k: "weak", label: "弱分型" },
    { k: "confirm", label: "确认分型" },
  ];
  kindList.forEach(({ k, label }) => {
    const enabled =
      k === "confirm"
        ? !!ff.confirmStyle?.enabled
        : !!ff.styleByStrength?.[k]?.enabled;

    out.push({
      key: `fr-kind-${k}`,
      name: label,
      items: [
        { key: `fr-botShape-${k}`, label: "底分符号" },
        { key: `fr-botColor-${k}`, label: "底分颜色" },
        { key: `fr-topShape-${k}`, label: "顶分符号" },
        { key: `fr-topColor-${k}`, label: "顶分颜色" },
        { key: `fr-fill-${k}`, label: "填充" },
      ],
      check: { type: "single", checked: enabled },
      reset: { visible: true, title: "恢复默认" },
    });
  });

  // 简笔
  out.push({
    key: "pen",
    name: "简笔",
    items: [
      { key: "pen-lineWidth", label: "线宽" },
      { key: "pen-color", label: "颜色" },
      { key: "pen-confirmedStyle", label: "确认线型" },
      { key: "pen-provisionalStyle", label: "预备线型" },
    ],
    check: {
      type: "single",
      checked: !!(cf.pen?.enabled ?? PENS_DEFAULTS.enabled),
    },
    reset: { visible: true, title: "恢复默认" },
  });

  // 线段
  out.push({
    key: "segment",
    name: "线段",
    items: [
      { key: "seg-lineWidth", label: "线宽" },
      { key: "seg-color", label: "颜色" },
      { key: "seg-lineStyle", label: "线型" },
    ],
    check: {
      type: "single",
      checked: !!(cf.segment?.enabled ?? SEGMENT_DEFAULTS.enabled),
    },
    reset: { visible: true, title: "恢复默认" },
  });

  // 笔中枢
  out.push({
    key: "penPivot",
    name: "笔中枢",
    items: [
      { key: "pv-lineWidth", label: "线宽" },
      { key: "pv-lineStyle", label: "线型" },
      { key: "pv-upColor", label: "上涨颜色" },
      { key: "pv-downColor", label: "下跌颜色" },
      { key: "pv-alpha", label: "透明度%" },
    ],
    check: {
      type: "single",
      checked: !!(cf.penPivot?.enabled ?? CHAN_PEN_PIVOT_DEFAULTS.enabled),
    },
    reset: { visible: true, title: "恢复默认" },
  });

  return out;
});

// 行级切换
function onRowToggle(row) {
  const key = String(row.key || "");
  const cf = chanDraft;
  const ff = fractalDraft;

  if (key === "chan-updown") {
    cf.showUpDownMarkers = !cf.showUpDownMarkers;
    return;
  }
  if (key === "fr-global") {
    frTri.cycleOnce();
    return;
  }

  if (key.startsWith("fr-kind-")) {
    const kind = key.slice("fr-kind-".length);
    if (kind === "confirm") {
      const cs = ff.confirmStyle || {};
      ff.confirmStyle = { ...cs, enabled: !(cs.enabled ?? true) };
      frTri.updateSnapshot();
      return;
    }
    const s = ff.styleByStrength || {};
    const cur = s[kind] || {};
    s[kind] = { ...cur, enabled: !cur.enabled };
    ff.styleByStrength = s;
    const ss = ff.showStrength || {};
    ff.showStrength = { ...ss, [kind]: !!s[kind].enabled };
    frTri.updateSnapshot();
    return;
  }
  if (key === "pen") {
    const pen = cf.pen || {};
    cf.pen = { ...pen, enabled: !(pen.enabled ?? PENS_DEFAULTS.enabled) };
    return;
  }
  if (key === "segment") {
    const sg = cf.segment || {};
    cf.segment = { ...sg, enabled: !(sg.enabled ?? SEGMENT_DEFAULTS.enabled) };
    return;
  }
  if (key === "penPivot") {
    const pv = cf.penPivot || {};
    cf.penPivot = {
      ...pv,
      enabled: !(pv.enabled ?? CHAN_PEN_PIVOT_DEFAULTS.enabled),
    };
  }
}

// 行重置（统一调用 resetter；只改草稿，不保存、不刷新）
function onRowReset(row) {
  const key = String(row.key || "");
  if (key === "chan-updown") {
    // 重置涨跌标记相关字段（保留 pen/segment/penPivot）
    chanResetter?.resetPath("showUpDownMarkers");
    chanResetter?.resetPath("upShape");
    chanResetter?.resetPath("upColor");
    chanResetter?.resetPath("downShape");
    chanResetter?.resetPath("downColor");
    chanResetter?.resetPath("anchorPolicy");
    // 如需同步最小/最大/高度/偏移，亦可按需加入：
    // chanResetter?.resetPath("markerMinPx");
    // chanResetter?.resetPath("markerMaxPx");
    // chanResetter?.resetPath("markerHeightPx");
    // chanResetter?.resetPath("markerYOffsetPx");
    return;
  }
  if (key === "fr-global") {
    // 重置分型判定总控（与缠论页正确链路一致）
    fractalResetter?.resetPath("minTickCount");
    fractalResetter?.resetPath("minPct");
    fractalResetter?.resetPath("minCond");
    fractalResetter?.resetPath("showStrength");
    fractalResetter?.resetPath("confirmStyle");
    frTri.updateSnapshot();
    return;
  }

  if (key.startsWith("fr-kind-")) {
    const kind = key.slice("fr-kind-".length);
    if (kind === "confirm") {
      fractalResetter?.resetPath("confirmStyle");
      frTri.updateSnapshot();
      return;
    }
    fractalResetter?.resetPath(`styleByStrength.${kind}`);
    // 同步显隐为默认（强/标/弱默认均为 true）
    const ss = fractalDraft.showStrength || {};
    fractalDraft.showStrength = { ...ss, [kind]: true };
    frTri.updateSnapshot();
    return;
  }
  if (key === "pen") {
    chanResetter?.resetPath("pen");
    return;
  }
  if (key === "segment") {
    chanResetter?.resetPath("segment");
    return;
  }
  if (key === "penPivot") {
    chanResetter?.resetPath("penPivot");
    return;
  }
}

// 使用通用渲染器
const { renderControl } = useSettingsRenderer({
  upShape: {
    component: "select",
    getProps: () => ({
      class: "input",
      value: chanDraft.upShape,
      onChange: (e) => (chanDraft.upShape = e.target.value),
      innerHTML: MARKER_SHAPE_OPTIONS.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  upColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: chanDraft.upColor,
      onInput: (e) => (chanDraft.upColor = e.target.value),
    }),
  },
  downShape: {
    component: "select",
    getProps: () => ({
      class: "input",
      value: chanDraft.downShape,
      onChange: (e) => (chanDraft.downShape = e.target.value),
      innerHTML: MARKER_SHAPE_OPTIONS.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  downColor: {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: chanDraft.downColor,
      onInput: (e) => (chanDraft.downColor = e.target.value),
    }),
  },
  anchorPolicy: {
    component: "select",
    getProps: () => ({
      class: "input",
      value: chanDraft.anchorPolicy,
      onChange: (e) => (chanDraft.anchorPolicy = e.target.value),
      innerHTML: ANCHOR_POLICY_OPTIONS.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  "fr-minTick": {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: fractalDraft.minTickCount,
      min: UI_LIMITS.nonNegativeInteger.min,
      step: UI_LIMITS.nonNegativeInteger.step,
      integer: true,
      "onUpdate:modelValue": (v) => (fractalDraft.minTickCount = v),
    }),
  },
  "fr-minPct": {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: fractalDraft.minPct,
      min: UI_LIMITS.percentage.min,
      max: UI_LIMITS.percentage.max,
      step: UI_LIMITS.percentage.step,
      integer: true,
      "onUpdate:modelValue": (v) => (fractalDraft.minPct = v),
    }),
  },
  "fr-minCond": {
    component: "select",
    getProps: () => ({
      class: "input",
      value: fractalDraft.minCond,
      onChange: (e) => (fractalDraft.minCond = e.target.value),
      innerHTML: MIN_COND_OPTIONS.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  ...Object.fromEntries(
    ["strong", "standard", "weak", "confirm"].flatMap((k) => {
      const readConf = () =>
        (k === "confirm"
          ? fractalDraft.confirmStyle
          : fractalDraft.styleByStrength[k]) || {};
      const writeConf = (patch) => {
        if (k === "confirm")
          fractalDraft.confirmStyle = {
            ...fractalDraft.confirmStyle,
            ...patch,
          };
        else
          fractalDraft.styleByStrength[k] = {
            ...fractalDraft.styleByStrength[k],
            ...patch,
          };
      };
      return [
        [
          `fr-botShape-${k}`,
          {
            component: "select",
            getProps: () => ({
              class: "input",
              value: readConf().bottomShape,
              onChange: (e) => writeConf({ bottomShape: e.target.value }),
              innerHTML: MARKER_SHAPE_OPTIONS.map(
                (o) => `<option value="${o.v}">${o.label}</option>`
              ).join(""),
            }),
          },
        ],
        [
          `fr-botColor-${k}`,
          {
            component: "input",
            getProps: () => ({
              class: "input color",
              type: "color",
              value: readConf().bottomColor,
              onInput: (e) => writeConf({ bottomColor: e.target.value }),
            }),
          },
        ],
        [
          `fr-topShape-${k}`,
          {
            component: "select",
            getProps: () => ({
              class: "input",
              value: readConf().topShape,
              onChange: (e) => writeConf({ topShape: e.target.value }),
              innerHTML: MARKER_SHAPE_OPTIONS.map(
                (o) => `<option value="${o.v}">${o.label}</option>`
              ).join(""),
            }),
          },
        ],
        [
          `fr-topColor-${k}`,
          {
            component: "input",
            getProps: () => ({
              class: "input color",
              type: "color",
              value: readConf().topColor,
              onInput: (e) => writeConf({ topColor: e.target.value }),
            }),
          },
        ],
        [
          `fr-fill-${k}`,
          {
            component: "select",
            getProps: () => ({
              class: "input",
              value: readConf().fill,
              onChange: (e) => writeConf({ fill: e.target.value }),
              innerHTML: FILL_OPTIONS.map(
                (o) => `<option value="${o.v}">${o.label}</option>`
              ).join(""),
            }),
          },
        ],
      ];
    })
  ),
  "pen-lineWidth": {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: chanDraft.pen.lineWidth,
      min: UI_LIMITS.lineWidth.min,
      max: UI_LIMITS.lineWidth.max,
      step: UI_LIMITS.lineWidth.step,
      "frac-digits": 1,
      "onUpdate:modelValue": (v) => (chanDraft.pen.lineWidth = v),
    }),
  },
  "pen-color": {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: chanDraft.pen.color,
      onInput: (e) => (chanDraft.pen.color = e.target.value),
    }),
  },
  "pen-confirmedStyle": {
    component: "select",
    getProps: () => ({
      class: "input",
      value: chanDraft.pen.confirmedStyle,
      onChange: (e) => (chanDraft.pen.confirmedStyle = e.target.value),
      innerHTML: LINE_STYLES.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  "pen-provisionalStyle": {
    component: "select",
    getProps: () => ({
      class: "input",
      value: chanDraft.pen.provisionalStyle,
      onChange: (e) => (chanDraft.pen.provisionalStyle = e.target.value),
      innerHTML: LINE_STYLES.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  "seg-lineWidth": {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: chanDraft.segment.lineWidth,
      min: UI_LIMITS.lineWidth.min,
      max: UI_LIMITS.lineWidth.max,
      step: UI_LIMITS.lineWidth.step,
      "frac-digits": 1,
      "onUpdate:modelValue": (v) => (chanDraft.segment.lineWidth = v),
    }),
  },
  "seg-color": {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: chanDraft.segment.color,
      onInput: (e) => (chanDraft.segment.color = e.target.value),
    }),
  },
  "seg-lineStyle": {
    component: "select",
    getProps: () => ({
      class: "input",
      value: chanDraft.segment.lineStyle,
      onChange: (e) => (chanDraft.segment.lineStyle = e.target.value),
      innerHTML: LINE_STYLES.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  "pv-lineWidth": {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: chanDraft.penPivot.lineWidth,
      min: UI_LIMITS.lineWidth.min,
      max: UI_LIMITS.lineWidth.max,
      step: UI_LIMITS.lineWidth.step,
      "frac-digits": 1,
      "onUpdate:modelValue": (v) => (chanDraft.penPivot.lineWidth = v),
    }),
  },
  "pv-lineStyle": {
    component: "select",
    getProps: () => ({
      class: "input",
      value: chanDraft.penPivot.lineStyle,
      onChange: (e) => (chanDraft.penPivot.lineStyle = e.target.value),
      innerHTML: LINE_STYLES.map(
        (o) => `<option value="${o.v}">${o.label}</option>`
      ).join(""),
    }),
  },
  "pv-upColor": {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: chanDraft.penPivot.upColor,
      onInput: (e) => (chanDraft.penPivot.upColor = e.target.value),
    }),
  },
  "pv-downColor": {
    component: "input",
    getProps: () => ({
      class: "input color",
      type: "color",
      value: chanDraft.penPivot.downColor,
      onInput: (e) => (chanDraft.penPivot.downColor = e.target.value),
    }),
  },
  "pv-alpha": {
    component: NumberSpinner,
    getProps: () => ({
      modelValue: chanDraft.penPivot.alphaPercent,
      min: UI_LIMITS.percentage.min,
      max: UI_LIMITS.percentage.max,
      step: UI_LIMITS.percentage.step,
      integer: true,
      "onUpdate:modelValue": (v) => (chanDraft.penPivot.alphaPercent = v),
    }),
  },
});
</script>
