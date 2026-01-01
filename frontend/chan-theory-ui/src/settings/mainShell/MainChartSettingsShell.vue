<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\mainShell\MainChartSettingsShell.vue -->
<!-- ==============================
说明：主窗设置壳（新版：数据驱动）
本轮改动：
  - 彻底删除设置窗内“复权(adjust)”链路（adjustDraft/adjustManager），避免双通道与死代码；
  - 复权仅保留页面按钮链路（MainChartPanel 三联按钮）；
  - 保存行为仅触发 Refresh，复权变更由页面按钮触发 useMarketView.watch(adjust) 原链路完成。
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
import { inject, ref, watch, provide } from "vue";
import MarketDisplaySettings from "@/settings/panels/MarketDisplaySettings.vue";
import ChanTheorySettings from "@/settings/panels/ChanTheorySettings.vue";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
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
} from "@/constants";
import { createSettingsResetter } from "@/settings/common/useSettingsResetter";

const props = defineProps({
  initialActiveTab: { type: String, default: "chan" },
});

const hub = useViewCommandHub();
inject("marketView"); // 保持注入顺序与结构（本轮不使用 vm）
useUserSettings(); // 保持现有结构（本轮不直接使用 settings）

const currentTabKey = ref(props.initialActiveTab || "chan");

// == 为每个设置项创建独立的、通用的管理器 ==
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

// NEW: chanDefaultConfig 增加 upDownMarkerPercent（涨跌标记宽%），并保留原结构
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
      // 确保新增字段也能正确兜底（例如老版本 localStorage 中没有 upDownMarkerPercent）
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

// NEW: 创建并提供统一重置器供子面板使用（只改草稿，不保存、不刷新）
const klineResetter = createSettingsResetter({ draft: klineManager.draft, defaults: DEFAULT_KLINE_STYLE });
const maResetter = createSettingsResetter({ draft: maManager.draft, defaults: DEFAULT_MA_CONFIGS });
const chanResetter = createSettingsResetter({ draft: chanManager.draft, defaults: chanDefaultConfig });
const fractalResetter = createSettingsResetter({ draft: fractalManager.draft, defaults: FRACTAL_DEFAULTS });
provide("klineResetter", klineResetter);
provide("maResetter", maResetter);
provide("chanResetter", chanResetter);
provide("fractalResetter", fractalResetter);

// === 暴露给 App.vue 的核心方法 ===
const save = () => {
  klineManager.save();
  maManager.save();
  chanManager.save();
  fractalManager.save();

  // 保存后触发重新渲染
  hub.execute("Refresh", {});
};

const resetAll = () => {
  klineResetter.resetAll();
  maResetter.resetAll();
  chanResetter.resetAll();
  fractalResetter.resetAll();
};

defineExpose({ save, resetAll });

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