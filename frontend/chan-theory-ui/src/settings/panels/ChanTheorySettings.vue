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
import { computed, defineComponent, h, inject } from "vue";
import SettingsGrid from "@/components/ui/SettingsGrid.vue";
import UiNumberBox from "@/components/ui/UiNumberBox.vue";
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

// 构建行
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

// 行重置
function onRowReset(row) {
  const key = String(row.key || "");
  const cf = chanDraft;
  const ff = fractalDraft;

  if (key === "chan-updown") {
    const { pen, segment, penPivot, ...rest } = cf;
    Object.assign(rest, JSON.parse(JSON.stringify(CHAN_DEFAULTS)));
    Object.assign(cf, rest);
    return;
  }
  if (key === "fr-global") {
    Object.assign(ff, JSON.parse(JSON.stringify(FRACTAL_DEFAULTS)));
    frTri.updateSnapshot();
    return;
  }

  if (key.startsWith("fr-kind-")) {
    const kind = key.slice("fr-kind-".length);
    if (kind === "confirm") {
      ff.confirmStyle = JSON.parse(
        JSON.stringify(FRACTAL_DEFAULTS.confirmStyle)
      );
      frTri.updateSnapshot();
      return;
    }
    const def = JSON.parse(
      JSON.stringify(FRACTAL_DEFAULTS.styleByStrength[kind])
    );
    const s = ff.styleByStrength || {};
    s[kind] = def;
    ff.styleByStrength = s;
    const ss = ff.showStrength || {};
    ff.showStrength = { ...ss, [kind]: true };
    frTri.updateSnapshot();
    return;
  }
  if (key === "pen") {
    cf.pen = JSON.parse(JSON.stringify(PENS_DEFAULTS));
    return;
  }
  if (key === "segment") {
    cf.segment = JSON.parse(JSON.stringify(SEGMENT_DEFAULTS));
    return;
  }
  if (key === "penPivot") {
    cf.penPivot = JSON.parse(JSON.stringify(CHAN_PEN_PIVOT_DEFAULTS));
    return;
  }
}

// 控件渲染
function renderControl(row, item) {
  const id = String(item.key || "");
  const cf = chanDraft;
  const ff = fractalDraft;

  const makeSelect = (value, onChange, options) =>
    h(
      "select",
      { class: "input", value, onChange },
      options.map((opt) => h("option", { value: opt.v }, opt.label))
    );

  // chan-updown
  if (row.key === "chan-updown") {
    if (id === "upShape" || id === "downShape") {
      const k = id;
      return defineComponent({
        setup() {
          const val = () => cf[k] || CHAN_DEFAULTS[k];
          return () =>
            makeSelect(
              val(),
              (e) => (cf[k] = String(e.target.value)),
              MARKER_SHAPE_OPTIONS
            );
        },
      });
    }
    if (id === "upColor" || id === "downColor") {
      const k = id;
      return defineComponent({
        setup() {
          return () =>
            h("input", {
              class: "input color",
              type: "color",
              value: cf[k] || CHAN_DEFAULTS[k],
              onInput: (e) => (cf[k] = String(e.target.value)),
            });
        },
      });
    }
    if (id === "anchorPolicy") {
      return defineComponent({
        setup() {
          const val = () => cf.anchorPolicy || CHAN_DEFAULTS.anchorPolicy;
          return () =>
            makeSelect(
              val(),
              (e) => (cf.anchorPolicy = String(e.target.value || "extreme")),
              ANCHOR_POLICY_OPTIONS
            );
        },
      });
    }
  }

  // fr-global
  if (row.key === "fr-global") {
    if (id === "fr-minTick") {
      return defineComponent({
        setup() {
          return () =>
            h(UiNumberBox, {
              modelValue: ff.minTickCount ?? FRACTAL_DEFAULTS.minTickCount,
              min: UI_LIMITS.nonNegativeInteger.min,
              step: UI_LIMITS.nonNegativeInteger.step,
              compact: true,
              integer: true,
              "onUpdate:modelValue": (v) => {
                ff.minTickCount = v;
              },
            });
        },
      });
    }
    if (id === "fr-minPct") {
      return defineComponent({
        setup() {
          return () =>
            h(UiNumberBox, {
              modelValue: ff.minPct ?? FRACTAL_DEFAULTS.minPct,
              min: UI_LIMITS.percentage.min,
              max: UI_LIMITS.percentage.max,
              step: UI_LIMITS.percentage.step,
              compact: true,
              integer: true,
              "onUpdate:modelValue": (v) => {
                ff.minPct = v;
              },
            });
        },
      });
    }
    if (id === "fr-minCond") {
      return defineComponent({
        setup() {
          const val = () => String(ff.minCond || FRACTAL_DEFAULTS.minCond);
          return () =>
            makeSelect(
              val(),
              (e) => (ff.minCond = String(e.target.value || "or")),
              MIN_COND_OPTIONS
            );
        },
      });
    }
  }

  // 分型种类
  if (row.key?.startsWith("fr-kind-")) {
    const kind = row.key.slice("fr-kind-".length);
    const readConf = () =>
      (kind === "confirm" ? ff.confirmStyle : ff.styleByStrength?.[kind]) || {};
    const writeConf = (patch) => {
      if (kind === "confirm") {
        ff.confirmStyle = { ...(ff.confirmStyle || {}), ...patch };
      } else {
        const s = ff.styleByStrength || {};
        s[kind] = { ...(s[kind] || {}), ...patch };
        ff.styleByStrength = s;
      }
    };

    if (id.includes("Shape")) {
      const type = id.includes("bot") ? "bottomShape" : "topShape";
      return defineComponent({
        setup: () => () =>
          makeSelect(
            readConf()[type],
            (e) => writeConf({ [type]: String(e.target.value) }),
            MARKER_SHAPE_OPTIONS
          ),
      });
    }
    if (id.includes("Color")) {
      const type = id.includes("bot") ? "bottomColor" : "topColor";
      return defineComponent({
        setup: () => () =>
          h("input", {
            class: "input color",
            type: "color",
            value: readConf()[type],
            onInput: (e) => writeConf({ [type]: String(e.target.value) }),
          }),
      });
    }
    if (id.includes("fill")) {
      return defineComponent({
        setup: () => () =>
          makeSelect(
            readConf().fill,
            (e) => writeConf({ fill: String(e.target.value) }),
            FILL_OPTIONS
          ),
      });
    }
  }

  // pen
  if (row.key === "pen") {
    const pen = cf.pen || {};
    if (id === "pen-lineWidth") {
      return defineComponent({
        setup() {
          return () => h(UiNumberBox, {
              modelValue: pen.lineWidth ?? PENS_DEFAULTS.lineWidth,
              min: UI_LIMITS.lineWidth.min,
              max: UI_LIMITS.lineWidth.max,
              step: UI_LIMITS.lineWidth.step,
              compact: true,
              integer: false,
              "frac-digits": 1,
              "onUpdate:modelValue": (v) => {
                if (cf.pen) cf.pen.lineWidth = v;
                else cf.pen = { lineWidth: v };
              },
            });
        },
      });
    }
    if (id === "pen-color") {
      return defineComponent({
        setup() {
          return () =>
            h("input", {
              class: "input color",
              type: "color",
              value: pen.color ?? PENS_DEFAULTS.color,
              onInput: (e) => {
                if (cf.pen)
                  cf.pen.color = String(e.target.value || PENS_DEFAULTS.color);
                else
                  cf.pen = {
                    color: String(e.target.value || PENS_DEFAULTS.color),
                  };
              },
            });
        },
      });
    }
    if (id === "pen-confirmedStyle" || id === "pen-provisionalStyle") {
      const kk = id.includes("confirmed")
        ? "confirmedStyle"
        : "provisionalStyle";
      return defineComponent({
        setup() {
          const val = () => pen[kk] ?? PENS_DEFAULTS[kk];
          return () =>
            h(
              "select",
              {
                class: "input",
                value: val(),
                onChange: (e) => {
                  if (cf.pen)
                    cf.pen[kk] = String(e.target.value || PENS_DEFAULTS[kk]);
                  else
                    cf.pen = {
                      [kk]: String(e.target.value || PENS_DEFAULTS[kk]),
                    };
                },
              },
              LINE_STYLES.map((opt) => h("option", { value: opt.v }, opt.label)) // <-- 修正：正确使用 opt.v 和 opt.label
            );
        },
      });
    }
  }

  // segment
  if (row.key === "segment") {
    const sg = cf.segment || {};
    if (id === "seg-lineWidth") {
      return defineComponent({
        setup() {
          return () => h(UiNumberBox, {
              modelValue: sg.lineWidth ?? SEGMENT_DEFAULTS.lineWidth,
              min: UI_LIMITS.lineWidth.min,
              max: UI_LIMITS.lineWidth.max,
              step: UI_LIMITS.lineWidth.step,
              compact: true,
              integer: false,
              "frac-digits": 1,
              "onUpdate:modelValue": (v) => {
                if (cf.segment) cf.segment.lineWidth = v;
                else cf.segment = { lineWidth: v };
              },
            });
        },
      });
    }
    if (id === "seg-color") {
      return defineComponent({
        setup() {
          return () => h("input", {
            class: "input color",
            type: "color",
            value: sg.color ?? SEGMENT_DEFAULTS.color,
            onInput: (e) => {
              if(cf.segment) cf.segment.color = String(e.target.value || SEGMENT_DEFAULTS.color); else cf.segment = { color: String(e.target.value || SEGMENT_DEFAULTS.color) };
            },
          });
        },
      });
    }
    if (id === "seg-lineStyle") {
      return defineComponent({
        setup() {
          const val = () => sg.lineStyle ?? SEGMENT_DEFAULTS.lineStyle;
          return () =>
            h(
              "select",
              {
                class: "input",
                value: val(),
                onChange: (e) => {
                  if (cf.segment)
                    cf.segment.lineStyle = String(
                      e.target.value || SEGMENT_DEFAULTS.lineStyle
                    );
                  else
                    cf.segment = {
                      lineStyle: String(
                        e.target.value || SEGMENT_DEFAULTS.lineStyle
                      ),
                    };
                },
              },
              LINE_STYLES.map((opt) => h("option", { value: opt.v }, opt.label)) // <-- 修正：正确使用 opt.v 和 opt.label
            );
        },
      });
    }
  }

  // penPivot
  if (row.key === "penPivot") {
    const pv = cf.penPivot || {};
    if (id === "pv-lineWidth") {
      return defineComponent({
        setup() {
          const value = () => pv.lineWidth ?? CHAN_PEN_PIVOT_DEFAULTS.lineWidth;
          return () => h(UiNumberBox, {
              modelValue: value(),
              min: UI_LIMITS.lineWidth.min,
              max: UI_LIMITS.lineWidth.max,
              step: UI_LIMITS.lineWidth.step,
              compact: true,
              integer: false,
              "frac-digits": 1,
              "onUpdate:modelValue": (v) => {
                if (cf.penPivot) cf.penPivot.lineWidth = v;
                else cf.penPivot = { lineWidth: v };
              },
            });
        },
      });
    }
    if (id === "pv-lineStyle") {
      return defineComponent({
        setup() {
          const val = () => pv.lineStyle ?? CHAN_PEN_PIVOT_DEFAULTS.lineStyle;
          return () => h("select", {
              class: "input",
              value: val(),
              onChange: (e) => {
                if(cf.penPivot) cf.penPivot.lineStyle = String(e.target.value || CHAN_PEN_PIVOT_DEFAULTS.lineStyle); else cf.penPivot = { lineStyle: String(e.target.value || CHAN_PEN_PIVOT_DEFAULTS.lineStyle) };
              },
            },
            LINE_STYLES.map((opt) => h("option", { value: opt.v }, opt.label)) // <-- 修正：正确使用 opt.v 和 opt.label
          );
        },
      });
    }
    if (id === "pv-upColor" || id === "pv-downColor") {
      const kk = id.includes("upColor") ? "upColor" : "downColor";
      return defineComponent({
        setup() {
          const value = () => pv[kk] ?? CHAN_PEN_PIVOT_DEFAULTS[kk];
          return () => h("input", {
            class: "input color",
            type: "color",
            value: value(),
            onInput: (e) => {
              if (cf.penPivot) cf.penPivot[kk] = String(e.target.value || CHAN_PEN_PIVOT_DEFAULTS[kk]); else cf.penPivot = { [kk]: String(e.target.value || CHAN_PEN_PIVOT_DEFAULTS[kk]) };
            },
          });
        },
      });
    }
    if (id === "pv-alpha") {
      return defineComponent({
        setup() {
          const value = () => pv.alphaPercent ?? CHAN_PEN_PIVOT_DEFAULTS.alphaPercent;
          return () => h(UiNumberBox, {
              modelValue: value(),
              min: UI_LIMITS.percentage.min,
              max: UI_LIMITS.percentage.max,
              step: UI_LIMITS.percentage.step,
              compact: true,
              integer: true,
              "onUpdate:modelValue": (v) => {
                if (cf.penPivot) cf.penPivot.alphaPercent = v;
                else cf.penPivot = { alphaPercent: v };
              },
            });
        },
      });
    }
  }

  // 占位空控件
  return defineComponent({
    setup() {
      return () => null;
    },
  });
}
</script>
