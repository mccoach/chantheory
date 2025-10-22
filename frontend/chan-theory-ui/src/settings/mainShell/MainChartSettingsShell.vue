<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\mainShell\MainChartSettingsShell.vue -->
<!-- ==============================
说明：主窗设置壳（新版：数据驱动）
- 职责：
  * 使用通用的 `useSettingsManager` 为每个设置项（K线、MA、缠论等）创建独立的管理器。
  * 通过 `provide` 将各管理器的 `draft` 对象提供给子组件。
  * 通过 `defineExpose` 暴露 `save` 和 `resetAll` 方法，供 App.vue 直接调用。
- 优点：逻辑内聚，无UI闪烁，易于扩展。
============================== -->
<template>
  <div class="shell-wrap">
    <!-- 标签页由 ModalDialog 外壳呈现；这里根据 currentTabKey 切换内容 -->
    <div v-if="currentTabKey === 'display'">
      <MarketDisplaySettings />
    </div>
    <div v-else-if="currentTabKey === 'chan'">
      <ChanTheorySettings />
    </div>
  </div>
</template>

<script setup>
import { inject, ref, watch, provide, defineExpose } from "vue";
import MarketDisplaySettings from "@/settings/panels/MarketDisplaySettings.vue";
import ChanTheorySettings from "@/settings/panels/ChanTheorySettings.vue";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useMarketView } from "@/composables/useMarketView"; // 修正：这是一个composables
import { useUserSettings } from "@/composables/useUserSettings";
import { useSettingsManager } from "@/composables/useSettingsManager";
import {
  DEFAULT_KLINE_STYLE,
  DEFAULT_MA_CONFIGS,
  CHAN_DEFAULTS,
  FRACTAL_DEFAULTS,
  DEFAULT_APP_PREFERENCES,
  PENS_DEFAULTS,
  SEGMENT_DEFAULTS,
  CHAN_PEN_PIVOT_DEFAULTS,
} from "@/constants";

const props = defineProps({
  initialActiveTab: { type: String, default: "chan" },
});

const hub = useViewCommandHub();
const vm = inject("marketView");
const settings = useUserSettings();

const currentTabKey = ref(props.initialActiveTab || "chan");

// == 为每个设置项创建独立的、通用的管理器 ==

// 1. K线样式管理器
const klineManager = useSettingsManager({
  settingsKey: "klineStyle",
  defaultConfig: DEFAULT_KLINE_STYLE,
});
provide("klineDraft", klineManager.draft);

// 2. MA配置管理器
const maManager = useSettingsManager({
  settingsKey: "maConfigs",
  defaultConfig: DEFAULT_MA_CONFIGS,
});
provide("maDraft", maManager.draft);

// 3. 缠论设置管理器
const chanDefaultConfig = {
  ...CHAN_DEFAULTS,
  pen: PENS_DEFAULTS,
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
      pen: { ...PENS_DEFAULTS, ...(localConfig.pen || {}) },
      segment: { ...SEGMENT_DEFAULTS, ...(localConfig.segment || {}) },
      penPivot: { ...CHAN_PEN_PIVOT_DEFAULTS, ...(localConfig.penPivot || {}) },
    };
  },
});
provide("chanDraft", chanManager.draft);

// 4. 分型设置管理器
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

// 5. 复权设置管理器
const adjustManager = (() => {
  const draft = ref(settings.adjust.value || DEFAULT_APP_PREFERENCES.adjust);
  const snapshot = ref(draft.value);
  const save = () => {
    settings.setAdjust(draft.value);
    const changed = snapshot.value !== draft.value;
    snapshot.value = draft.value;
    return changed;
  };
  const reset = () => {
    draft.value = DEFAULT_APP_PREFERENCES.adjust;
  };
  return { draft, save, reset };
})();
provide("adjustDraft", adjustManager.draft);


// === 暴露给 App.vue 的核心方法 ===
const save = () => {
  klineManager.save();
  maManager.save();
  chanManager.save();
  fractalManager.save();
  const adjustChanged = adjustManager.save();

  if (adjustChanged) {
    vm.reload({ force: true });
  } else {
    hub.execute("Refresh", {});
  }
};

const resetAll = () => {
  klineManager.reset();
  maManager.reset();
  chanManager.reset();
  fractalManager.reset();
  adjustManager.reset();
  hub.execute("Refresh", {});
};

defineExpose({ save, resetAll });


// 监听外壳当前 tab
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
