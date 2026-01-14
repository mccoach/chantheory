<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\symbol\SymbolActions.vue -->
<!-- ============================== -->
<!-- V2.4 - 删除独立【刷新】按钮，仅保留【快捷键设置】图标按钮
     说明：
       - 刷新功能已迁移到 SymbolPanel 的【下载/刷新】组合按钮中，页面仅保留一个刷新入口；
       - 本组件职责回归为“快捷键设置入口”，避免重复按钮与职责混乱。
-->
<template>
  <div class="actions-group">
    <button
      class="icon-btn"
      title="快捷键设置"
      aria-label="快捷键设置"
      @click="openHotkeySettings"
      :disabled="loading"
      v-html="SETTINGS_ICON_SVG"
    ></button>
  </div>
</template>

<script setup>
import { inject } from "vue";
import { SETTINGS_ICON_SVG } from "@/constants/icons";

defineProps({
  loading: { type: Boolean, default: false },
});

const dialogManager = inject("dialogManager", null);

async function openHotkeySettings() {
  try {
    if (!dialogManager || typeof dialogManager.open !== "function") return;

    const mod = await import("@/components/ui/HotkeySettingsDialog.vue");
    dialogManager.open({
      title: "快捷键设置",
      contentComponent: mod.default,
    });
  } catch (e) {
    console.error("[SymbolActions] openHotkeySettings failed:", e);
  }
}
</script>

<style scoped>
.actions-group {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

/* 独立图标按钮：外观对齐现有深色系 */
.icon-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  background: transparent;
  border: none;
  cursor: pointer;

  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.icon-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
