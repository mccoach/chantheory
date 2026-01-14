<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\mainShell\MainChartSettingsShell.vue -->
<!-- ==============================
V2.0 - 阶段2：设置保存归口 RenderHub（快照比对 + FULL/PATCH 决策）
- baseline：打开时保存各草稿快照（kline/ma/chan/fractal/atrStop/atrBreach）
- 保存：baseline vs current 计算 changedPaths
- 分类：命中任意 FULL 规则 => FULL；否则 => PATCH（但若存在未知路径 => FULL）
- 执行：调用 renderHub.requestRender({intent:'settings_apply', mode, patchPlan})
说明：
  - 仅对“用户暴露交互”的设置项做分类
  - 结构性/算法性/系列增删类变更一律归 FULL（确定性规则范式）

V3.1 - Dialog Action Contract（纯 key · 去冗版）
- 彻底去冗：只暴露 defineExpose({ dialogActions })
- footerActions 的执行不再依赖任何“固定方法名”（save/resetAll 等）
============================== -->
<template>
  <div class="shell-wrap">
    <div v-if="currentTabKey === 'display'">
      <MarketDisplaySettings />
    </div>
    <div v-else-if="currentTabKey === 'chan'">
      <ChanTheorySettings />
    </div>
    <div v-else-if="currentTabKey === 'atr'">
      <AtrStopSettingsPanel />
    </div>
  </div>
</template>

<script setup>
import { inject, ref, watch, provide, onMounted } from "vue";
import MarketDisplaySettings from "@/settings/panels/MarketDisplaySettings.vue";
import ChanTheorySettings from "@/settings/panels/ChanTheorySettings.vue";
import AtrStopSettingsPanel from "@/settings/panels/AtrStopSettingsPanel.vue";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/viewRenderHub";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSettingsManager } from "@/composables/useSettingsManager";
import {
  DEFAULT_KLINE_STYLE,
  DEFAULT_MA_CONFIGS,
  CHAN_DEFAULTS,
  FRACTAL_DEFAULTS,
  PENS_DEFAULTS,
  META_SEGMENT_DEFAULTS,
  SEGMENT_DEFAULTS,
  CHAN_PEN_PIVOT_DEFAULTS,
  DEFAULT_ATR_STOP_SETTINGS,
  ATR_BREACH_DEFAULTS,
} from "@/constants";
import { createSettingsResetter } from "@/settings/common/useSettingsResetter";
import {
  createBaselineKeeper,
  diffPaths,
  classifyPaths,
  buildPatchPlan,
} from "@/settings/common/settingsChangeClassifier";

const props = defineProps({
  initialActiveTab: { type: String, default: "chan" },
});

const hub = useViewCommandHub();
const renderHub = useViewRenderHub();

inject("marketView");
useUserSettings();

const currentTabKey = ref(props.initialActiveTab || "chan");

// == managers ==
const klineManager = useSettingsManager({
  settingsKey: "klineStyle",
  defaultConfig: DEFAULT_KLINE_STYLE,
});
provide("klineDraft", klineManager.draft);

const maManager = useSettingsManager({
  settingsKey: "maConfigs",
  defaultConfig: DEFAULT_MA_CONFIGS,
});
provide("maDraft", maManager.draft);

const chanDefaultConfig = {
  ...CHAN_DEFAULTS,
  pen: PENS_DEFAULTS,
  metaSegment: META_SEGMENT_DEFAULTS,
  segment: SEGMENT_DEFAULTS,
  penPivot: CHAN_PEN_PIVOT_DEFAULTS,
};
const chanManager = useSettingsManager({
  settingsKey: "chanSettings",
  defaultConfig: chanDefaultConfig,
  mergeFn: (localConfig = {}) => {
    return {
      ...chanDefaultConfig,
      ...localConfig,
      upDownMarkerPercent:
        localConfig.upDownMarkerPercent ?? chanDefaultConfig.upDownMarkerPercent,
      pen: { ...PENS_DEFAULTS, ...(localConfig.pen || {}) },
      metaSegment: { ...META_SEGMENT_DEFAULTS, ...(localConfig.metaSegment || {}) },
      segment: { ...SEGMENT_DEFAULTS, ...(localConfig.segment || {}) },
      penPivot: { ...CHAN_PEN_PIVOT_DEFAULTS, ...(localConfig.penPivot || {}) },
    };
  },
});
provide("chanDraft", chanManager.draft);

const fractalManager = useSettingsManager({
  settingsKey: "fractalSettings",
  defaultConfig: FRACTAL_DEFAULTS,
  mergeFn: (localConfig = {}) => {
    const merged = JSON.parse(JSON.stringify(FRACTAL_DEFAULTS));
    const loc = localConfig || {};
    Object.assign(merged, loc);
    merged.showStrength = { ...FRACTAL_DEFAULTS.showStrength, ...(loc.showStrength || {}) };
    merged.styleByStrength = {
      strong: { ...FRACTAL_DEFAULTS.styleByStrength.strong, ...(loc.styleByStrength?.strong || {}) },
      standard: { ...FRACTAL_DEFAULTS.styleByStrength.standard, ...(loc.styleByStrength?.standard || {}) },
      weak: { ...FRACTAL_DEFAULTS.styleByStrength.weak, ...(loc.styleByStrength?.weak || {}) },
    };
    merged.confirmStyle = { ...FRACTAL_DEFAULTS.confirmStyle, ...(loc.confirmStyle || {}) };
    merged.confirmStyle.enabled = (loc.confirmStyle?.enabled ?? FRACTAL_DEFAULTS.confirmStyle.enabled) === true;
    return merged;
  },
});
provide("fractalDraft", fractalManager.draft);

const atrStopManager = useSettingsManager({
  settingsKey: "atrStopSettings",
  defaultConfig: DEFAULT_ATR_STOP_SETTINGS,
});
provide("atrStopDraft", atrStopManager.draft);

const atrBreachManager = useSettingsManager({
  settingsKey: "atrBreachSettings",
  defaultConfig: ATR_BREACH_DEFAULTS,
});
provide("atrBreachDraft", atrBreachManager.draft);

// == resetters ==
const klineResetter = createSettingsResetter({ draft: klineManager.draft, defaults: DEFAULT_KLINE_STYLE });
const maResetter = createSettingsResetter({ draft: maManager.draft, defaults: DEFAULT_MA_CONFIGS });
const chanResetter = createSettingsResetter({ draft: chanManager.draft, defaults: chanDefaultConfig });
const fractalResetter = createSettingsResetter({ draft: fractalManager.draft, defaults: FRACTAL_DEFAULTS });
const atrStopResetter = createSettingsResetter({ draft: atrStopManager.draft, defaults: DEFAULT_ATR_STOP_SETTINGS });
const atrBreachResetter = createSettingsResetter({ draft: atrBreachManager.draft, defaults: ATR_BREACH_DEFAULTS });

provide("klineResetter", klineResetter);
provide("maResetter", maResetter);
provide("chanResetter", chanResetter);
provide("fractalResetter", fractalResetter);
provide("atrStopResetter", atrStopResetter);
provide("atrBreachResetter", atrBreachResetter);

// ==============================
// baseline keepers（打开时记录，用于保存时 diff）
// ==============================
const baseKline = createBaselineKeeper(klineManager.draft);
const baseMa = createBaselineKeeper(maManager.draft);
const baseChan = createBaselineKeeper(chanManager.draft);
const baseFractal = createBaselineKeeper(fractalManager.draft);
const baseAtrStop = createBaselineKeeper(atrStopManager.draft);
const baseAtrBreach = createBaselineKeeper(atrBreachManager.draft);

onMounted(() => {
  baseKline.setBaseline(klineManager.draft);
  baseMa.setBaseline(maManager.draft);
  baseChan.setBaseline(chanManager.draft);
  baseFractal.setBaseline(fractalManager.draft);
  baseAtrStop.setBaseline(atrStopManager.draft);
  baseAtrBreach.setBaseline(atrBreachManager.draft);
});

// ==============================
// 规则表：路径 → FULL / PATCH(facet, kind)
// ==============================
const RULES = [
  { prefix: "klineStyle", mode: "FULL" },

  {
    prefix: "maConfigs",
    mode: "FULL",
    match: (p) => /^maConfigs\.[^.]+\.period$/.test(p),
  },
  {
    prefix: "maConfigs",
    mode: "PATCH",
    facet: "display",
    kind: "style",
    match: (p) =>
      /^maConfigs\.[^.]+\.(color|width|style|enabled)$/.test(p) &&
      !/^maConfigs\.[^.]+\.period$/.test(p),
  },

  { prefix: "chanSettings", mode: "FULL" },
  { prefix: "fractalSettings", mode: "FULL" },

  {
    prefix: "atrStopSettings",
    mode: "PATCH",
    facet: "atr",
    kind: "param",
    match: (p) =>
      /^atrStopSettings\.(fixed|chandelier)\.(long|short)\.(n|atrPeriod|lookback|basePriceMode)$/.test(p),
  },
  {
    prefix: "atrStopSettings",
    mode: "PATCH",
    facet: "atr",
    kind: "style",
    match: (p) =>
      /^atrStopSettings\.(fixed|chandelier)\.(long|short)\.(color|lineWidth|lineStyle)$/.test(p),
  },
  {
    prefix: "atrStopSettings",
    mode: "FULL",
    match: (p) =>
      /^atrStopSettings\.(fixed|chandelier)\.(long|short)\.enabled$/.test(p),
  },

  {
    prefix: "atrBreachSettings",
    mode: "PATCH",
    facet: "atr",
    kind: "param",
    match: (p) => /^atrBreachSettings\.markerPercent$/.test(p),
  },
  {
    prefix: "atrBreachSettings",
    mode: "PATCH",
    facet: "atr",
    kind: "style",
    match: (p) => /^atrBreachSettings\.(shape|fill)$/.test(p),
  },
  {
    prefix: "atrBreachSettings",
    mode: "FULL",
    match: (p) => /^atrBreachSettings\.enabled$/.test(p),
  },
];

function saveImpl() {
  const changed = [];

  changed.push(...diffPaths(baseKline.getBaseline(), klineManager.draft, "klineStyle"));
  changed.push(...diffPaths(baseMa.getBaseline(), maManager.draft, "maConfigs"));
  changed.push(...diffPaths(baseChan.getBaseline(), chanManager.draft, "chanSettings"));
  changed.push(...diffPaths(baseFractal.getBaseline(), fractalManager.draft, "fractalSettings"));
  changed.push(...diffPaths(baseAtrStop.getBaseline(), atrStopManager.draft, "atrStopSettings"));
  changed.push(...diffPaths(baseAtrBreach.getBaseline(), atrBreachManager.draft, "atrBreachSettings"));

  const changedPaths = Array.from(new Set(changed.map((x) => String(x || "").trim()).filter(Boolean)));

  const cls = classifyPaths(changedPaths, RULES);
  const mustFull = cls.hasFull || cls.hasUnknown;

  klineManager.save();
  maManager.save();
  chanManager.save();
  fractalManager.save();
  atrStopManager.save();
  atrBreachManager.save();

  baseKline.setBaseline(klineManager.draft);
  baseMa.setBaseline(maManager.draft);
  baseChan.setBaseline(chanManager.draft);
  baseFractal.setBaseline(fractalManager.draft);
  baseAtrStop.setBaseline(atrStopManager.draft);
  baseAtrBreach.setBaseline(atrBreachManager.draft);

  if (mustFull) {
    renderHub.requestRender({ intent: "settings_apply", mode: "full" });
  } else {
    const patchPlan = buildPatchPlan(cls.items);
    renderHub.requestRender({ intent: "settings_apply", mode: "patch", patchPlan });
  }

  hub.execute("Refresh", {});
}

function resetAllImpl() {
  klineResetter.resetAll();
  maResetter.resetAll();
  chanResetter.resetAll();
  fractalResetter.resetAll();
  atrStopResetter.resetAll();
  atrBreachResetter.resetAll();
}

// ==============================
// Dialog Action Contract（纯 key · 唯一出口）
// ==============================
const dialogActions = {
  reset_all: () => {
    resetAllImpl();
  },

  save: ({ close }) => {
    saveImpl();
    close?.();
  },
};

defineExpose({ dialogActions });

const dialogManager = inject("dialogManager", null);
watch(
  () => dialogManager?.activeDialog?.value?.activeTab,
  (k) => {
    if (typeof k === "string" && k) currentTabKey.value = k;
  }
);
</script>

<style scoped>
.shell-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
