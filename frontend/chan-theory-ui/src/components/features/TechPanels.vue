<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\TechPanels.vue -->
<!-- “新增指标窗”按钮已是 SVG 圆形（之前版本已提供），此处保持；如需更大/更亮，可调宽高与渐变 -->
<template>
  <div class="tech-wrap">
    <VolumePanel />
    <IndicatorPanel
      v-for="(pane, i) in panes"
      :key="pane.id"
      v-model:kind="pane.kind"
      @close="removePane(i)"
    />
    <div class="add-wrap">
      <button
        class="btn-add"
        @click="addPane"
        title="新增指标窗"
        aria-label="新增指标窗"
      >
        <svg viewBox="0 0 48 48" width="36" height="36" aria-hidden="true">
          <defs>
            <radialGradient id="gcircle" cx="30%" cy="30%" r="70%">
              <stop offset="0" stop-color="#2e2e2e" />
              <stop offset="1" stop-color="#151515" />
            </radialGradient>
          </defs>
          <circle
            cx="24"
            cy="24"
            r="22"
            fill="url(#gcircle)"
            stroke="#8a8a8a"
            stroke-width="1"
          />
          <circle
            cx="24"
            cy="24"
            r="21"
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            stroke-width="1"
          />
          <path
            d="M24 14 L24 34 M14 24 L34 24"
            stroke="#e8e8e8"
            stroke-width="2.2"
            stroke-linecap="round"
          />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch, onMounted } from "vue";
import VolumePanel from "./tech/VolumePanel.vue";
import IndicatorPanel from "./tech/IndicatorPanel.vue";
import { useUserSettings } from "@/composables/useUserSettings";

// 保持原有 state 结构；初始一个窗体（若用户设置中已有持久化记录，挂载时会被覆盖为持久化内容）
const state = reactive({
  panes: [{ id: Date.now(), kind: "MACD" }],
});
const panes = state.panes;

// 新增：用户设置（Local-first）用于持久化“指标窗列表”
const settings = useUserSettings();

// 新增：挂载时从设置恢复（hydrate），仅恢复“窗体数量与类型”；id 在运行期生成
onMounted(() => {
  try {
    const saved = settings.getIndicatorPanes();
    if (Array.isArray(saved) && saved.length > 0) {
      const mapped = saved.map((x, idx) => ({
        id: Date.now() + idx + Math.random(),
        kind: String(x.kind || "MACD"),
      }));
      // 关键修复：用 splice 重置原数组内容，保持 panes 的引用不变
      panes.splice(0, panes.length, ...mapped);
    }
  } catch {}
});

// 持久化：监听 kind 序列，顺序与数量变化都会写回
watch(
  () => panes.map((p) => p.kind),
  (arr) => {
    try {
      settings.setIndicatorPanes(arr.map((k) => ({ kind: String(k || "MACD") })));
    } catch {}
  },
  { deep: true }
);

function addPane() {
  panes.push({ id: Date.now() + Math.random(), kind: "MACD" });
}
function removePane(idx) {
  if (idx < 0 || idx >= panes.length) return;
  panes.splice(idx, 1);
  // 写入由 watch 统一处理
}
</script>

<style scoped>
.tech-wrap {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin: 0;
  padding: 0;
}
.add-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 8px 0 0 0;
}
.btn-add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  width: 36px;
  height: 36px;
}
.btn-add svg circle:first-child {
  transition: stroke 120ms ease, fill 120ms ease;
}
.btn-add svg path {
  transition: stroke 120ms ease;
}
.btn-add:hover svg circle:first-child {
  stroke: #bdbdbd;
}
.btn-add:hover svg path {
  stroke: #ffffff;
}
.btn-add:active svg circle:first-child {
  stroke: #d0d0d0;
}
.btn-add:active svg path {
  stroke: #ffffff;
}
</style>
