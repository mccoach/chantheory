<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\panels\ChanTheorySettings.vue -->
<!-- ==============================
说明：缠论设置面板（新版：UI-only）
本轮改动：
  - select 统一改为 options children 渲染（不再使用 innerHTML 拼接）
  - 控件 getProps 样板代码用工厂函数标准化复用
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
  MIN_COND_OPTIONS,
  CHAN_PEN_PIVOT_DEFAULTS,
  META_SEGMENT_DEFAULTS,
  SEGMENT_DEFAULTS,
  PENS_DEFAULTS,
  UI_LIMITS,
  MARKER_SHAPE_OPTIONS,
  FILL_OPTIONS,
} from "@/constants";
import { useTriMasterToggle } from "@/settings/common/useTriMasterToggle";
import {
  useSettingsRenderer,
  makeNativeSelect,
  makeColorInput,
  makeNumberSpinner,
} from "@/settings/common/useSettingsRenderer";

const chanDraft = inject("chanDraft");
const fractalDraft = inject("fractalDraft");

const chanResetter = inject("chanResetter", null);
const fractalResetter = inject("fractalResetter", null);

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

const rows = computed(() => {
  const cf = chanDraft || {};
  const ff = fractalDraft || {};
  const out = [];

  out.push({
    key: "chan-updown",
    name: "涨跌标记",
    items: [
      { key: "upShape", label: "上涨符号" },
      { key: "upColor", label: "上涨颜色" },
      { key: "downShape", label: "下跌符号" },
      { key: "downColor", label: "下跌颜色" },
      { key: "updown-markerPercent", label: "标记宽%" },
    ],
    check: { type: "single", checked: !!cf.showUpDownMarkers },
    reset: { visible: true, title: "恢复默认" },
  });

  out.push({
    key: "fr-global",
    name: "分型总控",
    items: [
      { key: "fr-minTick", label: "最小tick" },
      { key: "fr-minPct", label: "最小幅度%" },
      { key: "fr-minCond", label: "判断条件" },
      { key: "fr-markerPercent", label: "标记宽%" },
    ],
    check: {
      type: "tri",
      checked: !!frTri.masterUi.checked.value,
      indeterminate: !!frTri.masterUi.indeterminate.value,
    },
    reset: { visible: true, title: "恢复默认" },
  });

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

  out.push({
    key: "pen",
    name: "简笔",
    items: [
      { key: "pen-lineWidth", label: "线宽" },
      { key: "pen-color", label: "颜色" },
      { key: "pen-confirmedStyle", label: "确认线型" },
      { key: "pen-provisionalStyle", label: "预备线型" },
    ],
    check: { type: "single", checked: !!(cf.pen?.enabled ?? PENS_DEFAULTS.enabled) },
    reset: { visible: true, title: "恢复默认" },
  });

  out.push({
    key: "metaSegment",
    name: "元线段",
    items: [
      { key: "mseg-lineWidth", label: "线宽" },
      { key: "mseg-color", label: "颜色" },
      { key: "mseg-lineStyle", label: "线型" },
    ],
    check: {
      type: "single",
      checked: !!(cf.metaSegment?.enabled ?? META_SEGMENT_DEFAULTS.enabled),
    },
    reset: { visible: true, title: "恢复默认" },
  });

  out.push({
    key: "segment",
    name: "线段",
    items: [
      { key: "seg-lineWidth", label: "线宽" },
      { key: "seg-color", label: "颜色" },
      { key: "seg-lineStyle", label: "线型" },
    ],
    check: { type: "single", checked: !!(cf.segment?.enabled ?? SEGMENT_DEFAULTS.enabled) },
    reset: { visible: true, title: "恢复默认" },
  });

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

  if (key === "metaSegment") {
    const ms = cf.metaSegment || {};
    cf.metaSegment = { ...ms, enabled: !(ms.enabled ?? META_SEGMENT_DEFAULTS.enabled) };
    return;
  }

  if (key === "segment") {
    const sg = cf.segment || {};
    cf.segment = { ...sg, enabled: !(sg.enabled ?? SEGMENT_DEFAULTS.enabled) };
    return;
  }

  if (key === "penPivot") {
    const pv = cf.penPivot || {};
    cf.penPivot = { ...pv, enabled: !(pv.enabled ?? CHAN_PEN_PIVOT_DEFAULTS.enabled) };
  }
}

function onRowReset(row) {
  const key = String(row.key || "");

  if (key === "chan-updown") {
    chanResetter?.resetPath("showUpDownMarkers");
    chanResetter?.resetPath("upShape");
    chanResetter?.resetPath("upColor");
    chanResetter?.resetPath("downShape");
    chanResetter?.resetPath("downColor");
    chanResetter?.resetPath("upDownMarkerPercent");
    return;
  }

  if (key === "fr-global") {
    fractalResetter?.resetPath("minTickCount");
    fractalResetter?.resetPath("minPct");
    fractalResetter?.resetPath("minCond");
    fractalResetter?.resetPath("markerPercent");
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
    const ss = fractalDraft.showStrength || {};
    fractalDraft.showStrength = { ...ss, [kind]: true };
    frTri.updateSnapshot();
    return;
  }

  if (key === "pen") {
    chanResetter?.resetPath("pen");
    return;
  }

  if (key === "metaSegment") {
    chanResetter?.resetPath("metaSegment");
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

const { renderControl } = useSettingsRenderer({
  upShape: makeNativeSelect({
    options: MARKER_SHAPE_OPTIONS,
    get: () => chanDraft.upShape,
    set: (_, v) => (chanDraft.upShape = v),
  }),

  upColor: makeColorInput({
    get: () => chanDraft.upColor,
    set: (_, v) => (chanDraft.upColor = v),
  }),

  downShape: makeNativeSelect({
    options: MARKER_SHAPE_OPTIONS,
    get: () => chanDraft.downShape,
    set: (_, v) => (chanDraft.downShape = v),
  }),

  downColor: makeColorInput({
    get: () => chanDraft.downColor,
    set: (_, v) => (chanDraft.downColor = v),
  }),

  "updown-markerPercent": makeNumberSpinner({
    component: NumberSpinner,
    get: () => chanDraft.upDownMarkerPercent,
    set: (_, v) => (chanDraft.upDownMarkerPercent = v),
    min: UI_LIMITS.markerWidthPercent.min,
    max: UI_LIMITS.markerWidthPercent.max,
    step: UI_LIMITS.markerWidthPercent.step,
    integer: true,
  }),

  "fr-minTick": makeNumberSpinner({
    component: NumberSpinner,
    get: () => fractalDraft.minTickCount,
    set: (_, v) => (fractalDraft.minTickCount = v),
    min: UI_LIMITS.nonNegativeInteger.min,
    step: UI_LIMITS.nonNegativeInteger.step,
    integer: true,
  }),

  "fr-minPct": makeNumberSpinner({
    component: NumberSpinner,
    get: () => fractalDraft.minPct,
    set: (_, v) => (fractalDraft.minPct = v),
    min: UI_LIMITS.percentage.min,
    max: UI_LIMITS.percentage.max,
    step: UI_LIMITS.percentage.step,
    integer: true,
  }),

  "fr-minCond": makeNativeSelect({
    options: MIN_COND_OPTIONS,
    get: () => fractalDraft.minCond,
    set: (_, v) => (fractalDraft.minCond = v),
  }),

  "fr-markerPercent": makeNumberSpinner({
    component: NumberSpinner,
    get: () => fractalDraft.markerPercent,
    set: (_, v) => (fractalDraft.markerPercent = v),
    min: UI_LIMITS.markerWidthPercent.min,
    max: UI_LIMITS.markerWidthPercent.max,
    step: UI_LIMITS.markerWidthPercent.step,
    integer: true,
  }),

  ...Object.fromEntries(
    ["strong", "standard", "weak", "confirm"].flatMap((k) => {
      const readConf = () =>
        (k === "confirm" ? fractalDraft.confirmStyle : fractalDraft.styleByStrength[k]) || {};
      const writeConf = (patch) => {
        if (k === "confirm") fractalDraft.confirmStyle = { ...fractalDraft.confirmStyle, ...patch };
        else
          fractalDraft.styleByStrength[k] = {
            ...fractalDraft.styleByStrength[k],
            ...patch,
          };
      };

      const getFill = () => readConf().fill;
      const setFill = (_, v) => writeConf({ fill: v });

      const getBotShape = () => readConf().bottomShape;
      const setBotShape = (_, v) => writeConf({ bottomShape: v });

      const getTopShape = () => readConf().topShape;
      const setTopShape = (_, v) => writeConf({ topShape: v });

      const getBotColor = () => readConf().bottomColor;
      const setBotColor = (_, v) => writeConf({ bottomColor: v });

      const getTopColor = () => readConf().topColor;
      const setTopColor = (_, v) => writeConf({ topColor: v });

      return [
        [
          `fr-botShape-${k}`,
          makeNativeSelect({ options: MARKER_SHAPE_OPTIONS, get: getBotShape, set: setBotShape }),
        ],
        [
          `fr-botColor-${k}`,
          makeColorInput({ get: getBotColor, set: setBotColor }),
        ],
        [
          `fr-topShape-${k}`,
          makeNativeSelect({ options: MARKER_SHAPE_OPTIONS, get: getTopShape, set: setTopShape }),
        ],
        [
          `fr-topColor-${k}`,
          makeColorInput({ get: getTopColor, set: setTopColor }),
        ],
        [
          `fr-fill-${k}`,
          makeNativeSelect({ options: FILL_OPTIONS, get: getFill, set: setFill }),
        ],
      ];
    })
  ),

  "pen-lineWidth": makeNumberSpinner({
    component: NumberSpinner,
    get: () => chanDraft.pen.lineWidth,
    set: (_, v) => (chanDraft.pen.lineWidth = v),
    min: UI_LIMITS.lineWidth.min,
    max: UI_LIMITS.lineWidth.max,
    step: UI_LIMITS.lineWidth.step,
    fracDigits: 1,
  }),

  "pen-color": makeColorInput({
    get: () => chanDraft.pen.color,
    set: (_, v) => (chanDraft.pen.color = v),
  }),

  "pen-confirmedStyle": makeNativeSelect({
    options: LINE_STYLES,
    get: () => chanDraft.pen.confirmedStyle,
    set: (_, v) => (chanDraft.pen.confirmedStyle = v),
  }),

  "pen-provisionalStyle": makeNativeSelect({
    options: LINE_STYLES,
    get: () => chanDraft.pen.provisionalStyle,
    set: (_, v) => (chanDraft.pen.provisionalStyle = v),
  }),

  "mseg-lineWidth": makeNumberSpinner({
    component: NumberSpinner,
    get: () => chanDraft.metaSegment.lineWidth,
    set: (_, v) => (chanDraft.metaSegment.lineWidth = v),
    min: UI_LIMITS.lineWidth.min,
    max: UI_LIMITS.lineWidth.max,
    step: UI_LIMITS.lineWidth.step,
    fracDigits: 1,
  }),

  "mseg-color": makeColorInput({
    get: () => chanDraft.metaSegment.color,
    set: (_, v) => (chanDraft.metaSegment.color = v),
  }),

  "mseg-lineStyle": makeNativeSelect({
    options: LINE_STYLES,
    get: () => chanDraft.metaSegment.lineStyle,
    set: (_, v) => (chanDraft.metaSegment.lineStyle = v),
  }),

  "seg-lineWidth": makeNumberSpinner({
    component: NumberSpinner,
    get: () => chanDraft.segment.lineWidth,
    set: (_, v) => (chanDraft.segment.lineWidth = v),
    min: UI_LIMITS.lineWidth.min,
    max: UI_LIMITS.lineWidth.max,
    step: UI_LIMITS.lineWidth.step,
    fracDigits: 1,
  }),

  "seg-color": makeColorInput({
    get: () => chanDraft.segment.color,
    set: (_, v) => (chanDraft.segment.color = v),
  }),

  "seg-lineStyle": makeNativeSelect({
    options: LINE_STYLES,
    get: () => chanDraft.segment.lineStyle,
    set: (_, v) => (chanDraft.segment.lineStyle = v),
  }),

  "pv-lineWidth": makeNumberSpinner({
    component: NumberSpinner,
    get: () => chanDraft.penPivot.lineWidth,
    set: (_, v) => (chanDraft.penPivot.lineWidth = v),
    min: UI_LIMITS.lineWidth.min,
    max: UI_LIMITS.lineWidth.max,
    step: UI_LIMITS.lineWidth.step,
    fracDigits: 1,
  }),

  "pv-lineStyle": makeNativeSelect({
    options: LINE_STYLES,
    get: () => chanDraft.penPivot.lineStyle,
    set: (_, v) => (chanDraft.penPivot.lineStyle = v),
  }),

  "pv-upColor": makeColorInput({
    get: () => chanDraft.penPivot.upColor,
    set: (_, v) => (chanDraft.penPivot.upColor = v),
  }),

  "pv-downColor": makeColorInput({
    get: () => chanDraft.penPivot.downColor,
    set: (_, v) => (chanDraft.penPivot.downColor = v),
  }),

  "pv-alpha": makeNumberSpinner({
    component: NumberSpinner,
    get: () => chanDraft.penPivot.alphaPercent,
    set: (_, v) => (chanDraft.penPivot.alphaPercent = v),
    min: UI_LIMITS.percentage.min,
    max: UI_LIMITS.percentage.max,
    step: UI_LIMITS.percentage.step,
    integer: true,
  }),
});
</script>
