<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\panels\MarketDisplaySettings.vue -->
<!-- ==============================
说明：行情设置面板（新版：UI-only）
- 职责：仅负责渲染行情相关的设置UI，不再管理状态。
- 数据流：通过 `inject` 获取来自外壳的响应式草稿对象 (klineDraft, maDraft, adjustDraft)，并直接绑定。
- 逻辑：MA 总控的三态切换逻辑 (useTriMasterToggle) 依然保留在此，因为它与 UI 渲染紧密相关。
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
import {
  DEFAULT_KLINE_STYLE,
  DEFAULT_MA_CONFIGS,
  DEFAULT_APP_PREFERENCES,
  LINE_STYLES,
  ADJUST_OPTIONS,
  DISPLAY_ORDER_OPTIONS,
} from "@/constants";
import { useTriMasterToggle } from "@/settings/common/useTriMasterToggle";
import UiNumberBox from "@/components/ui/UiNumberBox.vue";

// 通过 inject 获取共享的草稿状态
const klineDraft = inject('klineDraft');
const maDraft = inject('maDraft');
const adjustDraft = inject('adjustDraft');


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

// 控件渲染
function renderControl(row, item) {
  const id = String(item.key || "");
  const mk = item.maKey;

  // 原始K线
  if (row.key === "k-original") {
    if (id === "adjust") {
      return defineComponent({
        setup() {
          return () =>
            h(
              "select",
              {
                class: "input",
                value: adjustDraft.value,
                onChange: (e) => (adjustDraft.value = String(e.target.value)),
              },
              ADJUST_OPTIONS.map((opt) =>
                h("option", { value: opt.v }, opt.label)
              )
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
              value: klineDraft[k],
              onInput: (e) => (klineDraft[k] = String(e.target.value)),
            });
        },
      });
    }
    if (id === "upFade" || id === "downFade") {
      const k = id === "upFade" ? "originalFadeUpPercent" : "originalFadeDownPercent";
      return defineComponent({
        setup() {
          const curr = () => Number(klineDraft[k] ?? 0);
          return () =>
            h(UiNumberBox, {
              modelValue: curr(),
              min: 0,
              max: 100,
              step: 1,
              compact: true,
              integer: true,
              'onUpdate:modelValue': (v) => {
                const nv = Math.max(0, Math.min(100, Number(v ?? 0)));
                klineDraft[k] = nv;
              },
            });
        },
      });
    }
  }

  // 合并K线
  if (row.key === "k-merged") {
    if (id === "outlineWidth") {
      return defineComponent({
        setup() {
          const curr = () => Number(klineDraft.mergedK.outlineWidth ?? DEFAULT_KLINE_STYLE.mergedK.outlineWidth);
          return () =>
            h(UiNumberBox, {
              modelValue: curr(),
              min: 0.1,
              max: 6,
              step: 0.1,
              compact: true,
              integer: false,
              'frac-digits': 1,
              'onUpdate:modelValue': (v) => {
                const def = DEFAULT_KLINE_STYLE.mergedK.outlineWidth;
                const vv = Math.max(0.1, Number(v ?? def));
                klineDraft.mergedK.outlineWidth = vv;
              },
            });
        },
      });
    }
    if (id === "mUpColor" || id === "mDownColor") {
      const kk = id === "mUpColor" ? "upColor" : "downColor";
      return defineComponent({
        setup() {
          const curr = () => klineDraft.mergedK[kk] ?? DEFAULT_KLINE_STYLE.mergedK[kk];
          return () =>
            h("input", {
              class: "input color",
              type: "color",
              value: curr(),
              onInput: (e) => (klineDraft.mergedK[kk] = String(e.target.value)),
            });
        },
      });
    }
    if (id === "fillFade") {
      return defineComponent({
        setup() {
          const curr = () => Number(klineDraft.mergedK.fillFadePercent ?? DEFAULT_KLINE_STYLE.mergedK.fillFadePercent);
          return () =>
            h(UiNumberBox, {
              modelValue: curr(),
              min: 0,
              max: 100,
              step: 1,
              compact: true,
              integer: true,
              'onUpdate:modelValue': (v) => {
                const def = DEFAULT_KLINE_STYLE.mergedK.fillFadePercent;
                const nv = Math.max(0, Math.min(100, Number(v ?? def)));
                klineDraft.mergedK.fillFadePercent = nv;
              },
            });
        },
      });
    }
    if (id === "displayOrder") {
      return defineComponent({
        setup() {
          return () =>
            h(
              "select",
              {
                class: "input",
                value: klineDraft.mergedK.displayOrder ?? DEFAULT_KLINE_STYLE.mergedK.displayOrder,
                onChange: (e) => (klineDraft.mergedK.displayOrder = String(e.target.value ?? DEFAULT_KLINE_STYLE.mergedK.displayOrder)),
              },
              DISPLAY_ORDER_OPTIONS.map((opt) =>
                h("option", { value: opt.v }, opt.label)
              )
            );
        },
      });
    }
  }

  // MA 行
  if (row.key?.startsWith("ma-")) {
    const conf = maDraft[mk] || DEFAULT_MA_CONFIGS[mk];
    if (id === "ma-width") {
      return defineComponent({
        setup() {
          const curr = () => Number(conf.width ?? DEFAULT_MA_CONFIGS[mk].width);
          return () =>
            h(UiNumberBox, {
              modelValue: curr(),
              min: 0.5,
              max: 4,
              step: 0.5,
              compact: true,
              integer: false,
              'frac-digits': 1,
              'onUpdate:modelValue': (v) => {
                const def = DEFAULT_MA_CONFIGS[mk].width;
                maDraft[mk].width = Number(v ?? def);
              },
            });
        },
      });
    }
    if (id === "ma-color") {
      return defineComponent({
        setup() {
          return () =>
            h("input", {
              class: "input color",
              type: "color",
              value: conf.color,
              onInput: (e) => (maDraft[mk].color = String(e.target.value)),
            });
        },
      });
    }
    if (id === "ma-style") {
      return defineComponent({
        setup() {
          return () =>
            h(
              "select",
              {
                class: "input",
                value: conf.style ?? DEFAULT_MA_CONFIGS[mk].style,
                onChange: (e) => (maDraft[mk].style = String(e.target.value ?? DEFAULT_MA_CONFIGS[mk].style)),
              },
              LINE_STYLES.map((s) => h("option", { value: s }, s))
            );
        },
      });
    }
    if (id === "ma-period") {
      return defineComponent({
        setup() {
          const curr = () => Number(conf.period ?? DEFAULT_MA_CONFIGS[mk].period);
          return () =>
            h(UiNumberBox, {
              modelValue: curr(),
              min: 1,
              max: Infinity,
              step: 1,
              compact: true,
              integer: true,
              'onUpdate:modelValue': (v) => {
                const def = DEFAULT_MA_CONFIGS[mk].period;
                maDraft[mk].period = Math.max(
                  1,
                  parseInt(v ?? def, 10)
                );
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
