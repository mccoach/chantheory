<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\indicatorShell\IndicatorSettingsShell.vue -->
<!-- ==============================
V3.1 - Dialog Action Contract（纯 key · 去冗版）
- 彻底去冗：只暴露 defineExpose({ dialogActions })
- footerActions 的执行不再依赖任何“固定方法名”
============================== -->
<template>
  <div class="shell-wrap">
    <div v-if="currentTabKey === 'VOL'">
      <VolumeSettingsPanel />
    </div>
    <div v-else-if="currentTabKey === 'MACD'">
      <MacdSettingsPanel />
    </div>
    <div v-else-if="currentTabKey === 'KDJ'">
      <KdjSettingsPanel />
    </div>
    <div v-else-if="currentTabKey === 'RSI'">
      <RsiSettingsPanel />
    </div>
    <div v-else-if="currentTabKey === 'BOLL'">
      <BollSettingsPanel />
    </div>
    <div v-else>
      <IndicatorPlaceholderPanel :label="currentTabKey" />
    </div>
  </div>
</template>

<script setup>
import { inject, ref, watch, provide, onMounted } from "vue";
import VolumeSettingsPanel from "@/settings/panels/VolumeSettingsPanel.vue";
import MacdSettingsPanel from "@/settings/panels/MacdSettingsPanel.vue";
import KdjSettingsPanel from "@/settings/panels/KdjSettingsPanel.vue";
import RsiSettingsPanel from "@/settings/panels/RsiSettingsPanel.vue";
import BollSettingsPanel from "@/settings/panels/BollSettingsPanel.vue";
import IndicatorPlaceholderPanel from "@/settings/panels/IndicatorPlaceholderPanel.vue";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/viewRenderHub";
import { useSettingsManager } from "@/composables/useSettingsManager";
import { DEFAULT_VOL_SETTINGS, DEFAULT_MACD_SETTINGS } from "@/constants";
import { createSettingsResetter } from "@/settings/common/useSettingsResetter";
import {
  createBaselineKeeper,
  diffPaths,
  classifyPaths,
  buildPatchPlan,
} from "@/settings/common/settingsChangeClassifier";

const props = defineProps({
  initialKind: { type: String, default: "VOL" },
});

const hub = useViewCommandHub();
const renderHub = useViewRenderHub();
const dialogManager = inject("dialogManager", null);

const getInitialTab = (kind) => (String(kind).toUpperCase() === 'AMOUNT' ? 'VOL' : String(kind).toUpperCase());
const currentTabKey = ref(getInitialTab(props.initialKind));

// managers
const volManager = useSettingsManager({
  settingsKey: "volSettings",
  defaultConfig: DEFAULT_VOL_SETTINGS,
});
provide("volDraft", volManager.draft);

const volResetter = createSettingsResetter({
  draft: volManager.draft,
  defaults: DEFAULT_VOL_SETTINGS,
});
provide("volResetter", volResetter);

const macdManager = useSettingsManager({
  settingsKey: "macdSettings",
  defaultConfig: DEFAULT_MACD_SETTINGS,
});
provide("macdDraft", macdManager.draft);

const macdResetter = createSettingsResetter({
  draft: macdManager.draft,
  defaults: DEFAULT_MACD_SETTINGS,
});
provide("macdResetter", macdResetter);

// baseline
const baseVol = createBaselineKeeper(volManager.draft);
const baseMacd = createBaselineKeeper(macdManager.draft);

onMounted(() => {
  baseVol.setBaseline(volManager.draft);
  baseMacd.setBaseline(macdManager.draft);

  document.addEventListener("click", handleClickOutside);
});

function handleClickOutside(_e) {
  // 保持原有行为（此处不处理菜单，TechPanels 内处理）
}

// 规则：阶段2副图设置统一 FULL（最稳）
const RULES = [
  { prefix: "volSettings", mode: "FULL" },
  { prefix: "macdSettings", mode: "FULL" },
];

function saveImpl() {
  const changed = [];
  changed.push(...diffPaths(baseVol.getBaseline(), volManager.draft, "volSettings"));
  changed.push(...diffPaths(baseMacd.getBaseline(), macdManager.draft, "macdSettings"));

  const changedPaths = Array.from(new Set(changed.map((x) => String(x || "").trim()).filter(Boolean)));

  const cls = classifyPaths(changedPaths, RULES);
  const mustFull = cls.hasFull || cls.hasUnknown;

  volManager.save();
  macdManager.save();

  baseVol.setBaseline(volManager.draft);
  baseMacd.setBaseline(macdManager.draft);

  if (mustFull) {
    renderHub.requestRender({ intent: "settings_apply", mode: "full" });
  } else {
    const patchPlan = buildPatchPlan(cls.items);
    renderHub.requestRender({ intent: "settings_apply", mode: "patch", patchPlan });
  }

  hub.execute("Refresh", {});
}

function resetAllImpl() {
  volResetter.resetAll();
  macdResetter.resetAll();
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

watch(
  () => dialogManager?.activeDialog?.value?.activeTab,
  (k) => {
    if (typeof k === "string" && k) {
      currentTabKey.value = k;
    }
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
