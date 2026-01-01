<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\symbol\SymbolActions.vue -->
<!-- ============================== -->
<!-- V2.3 - 快捷键按钮独立于刷新按钮（不再包含在 seg 内），刷新按钮样式与宽度完美回归 -->
<template>
  <div class="actions-group">
    <!-- NEW: 独立图标按钮（左侧） -->
    <button
      class="icon-btn"
      title="快捷键设置"
      aria-label="快捷键设置"
      @click="openHotkeySettings"
      :disabled="loading"
      v-html="SETTINGS_ICON_SVG"
    ></button>

    <!-- 刷新按钮：保持原结构与宽度 -->
    <div class="seg">
      <button
        class="seg-btn"
        title="刷新"
        @click="$emit('refresh')"
        :disabled="loading"
      >
        刷新
      </button>
    </div>
  </div>
</template>

<script setup>
import { inject } from "vue";
import { SETTINGS_ICON_SVG } from "@/constants/icons";

defineProps({
  loading: { type: Boolean, default: false },
});
defineEmits(["refresh"]);

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

/* 刷新按钮容器（保持原样） */
.seg {
  display: inline-flex;
  align-items: center;
  border: 1px solid #444;
  border-radius: 10px;
  overflow: hidden;
  background: #1a1a1a;
  height: 36px;
}

/* 刷新按钮（保持原样：宽度 60px） */
.seg-btn {
  background: transparent;
  color: #ddd;
  border: none;
  padding: 8px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 14px;
  line-height: 20px;
  width: 60px;
  height: 36px;
  border-radius: 10px;
}

.seg-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.seg-btn:hover:not(:disabled) {
  background: #2b4b7e;
  color: #fff;
}
</style>
