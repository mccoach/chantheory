<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\indicatorShell\IndicatorSettingsShell.vue -->
<!-- ==============================
说明：指标设置壳（数据驱动）
- 职责：
  * 作为所有指标设置的统一内容根组件。
  * 使用 useSettingsManager 为 `volSettings` 创建状态管理器。
  * 通过 `provide` 将 `volDraft` 草稿对象提供给子面板。
  * 根据 activeTab 动态渲染 `VolumeSettingsPanel` 或其他指标的占位面板。
  * 通过 `defineExpose` 暴露 `save` 和 `resetAll` 方法供 App.vue 调用。
============================== -->
<template>
  <div class="shell-wrap">
    <!-- 根据当前激活的 tab 动态渲染对应的设置面板 -->
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
    <!-- 默认或未知 tab 的降级处理 -->
    <div v-else>
      <IndicatorPlaceholderPanel :label="currentTabKey" />
    </div>
  </div>
</template>

<script setup>
import { inject, ref, watch, provide, defineExpose } from "vue";
import VolumeSettingsPanel from "@/settings/panels/VolumeSettingsPanel.vue";
import MacdSettingsPanel from "@/settings/panels/MacdSettingsPanel.vue";
import KdjSettingsPanel from "@/settings/panels/KdjSettingsPanel.vue";
import RsiSettingsPanel from "@/settings/panels/RsiSettingsPanel.vue";
import BollSettingsPanel from "@/settings/panels/BollSettingsPanel.vue";
import IndicatorPlaceholderPanel from "@/settings/panels/IndicatorPlaceholderPanel.vue";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useSettingsManager } from "@/composables/useSettingsManager";
import { DEFAULT_VOL_SETTINGS } from "@/constants";

const props = defineProps({
  initialKind: { type: String, default: "VOL" },
});

const hub = useViewCommandHub();
const dialogManager = inject("dialogManager", null);

// 如果初始 kind 是 AMOUNT，映射到 VOL tab
const getInitialTab = (kind) => (String(kind).toUpperCase() === 'AMOUNT' ? 'VOL' : String(kind).toUpperCase());
const currentTabKey = ref(getInitialTab(props.initialKind));

// 为成交量/成交额设置创建通用管理器
const volManager = useSettingsManager({
  settingsKey: "volSettings",
  defaultConfig: DEFAULT_VOL_SETTINGS,
});
provide("volDraft", volManager.draft);

// 暴露 save 和 resetAll 方法
const save = () => {
  // 目前只有量窗有可保存的设置
  volManager.save();
  // 保存后触发一次刷新
  hub.execute("Refresh", {});
};

const resetAll = () => {
  // 目前只有量窗有可重置的设置
  volManager.reset();
  // 重置后触发一次刷新
  hub.execute("Refresh", {});
};

defineExpose({ save, resetAll });

// 监听外壳（ModalDialog）的 tab 切换
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