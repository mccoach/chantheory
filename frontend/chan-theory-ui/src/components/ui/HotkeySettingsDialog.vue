<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\ui\HotkeySettingsDialog.vue -->
<template>
  <div class="settings-content">
    <div class="desc">
      提示：点击某项的快捷键框，然后按下新的组合键以修改。Esc 取消当前采集，Ctrl/Cmd+Enter 确认保存。
    </div>

    <div class="scopes-masonry">
      <div v-for="scope in scopes" :key="scope" class="scope">
        <div class="scope-title" :title="scopeTitle(scope)">
          {{ scopeTitle(scope) }}
        </div>

        <div
          class="row"
          v-for="(label, cmd) in labelsForScope(scope)"
          :key="scope + '-' + cmd"
        >
          <div class="cmd" :title="label">{{ label }}</div>

          <input
            class="combo"
            :value="draftBindings[scope]?.[cmd] || ''"
            readonly
            :title="draftBindings[scope]?.[cmd] || ''"
            @focus="startCapture(scope, cmd, $event)"
            @keydown.prevent="captureKey(scope, cmd, $event)"
            @blur="stopCapture(scope, cmd, false)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, reactive, ref, onMounted } from "vue";
import { defaultKeymap, commandLabels } from "@/interaction/hotkeys/presets";
import { useUserSettings } from "@/composables/useUserSettings";

const hotkeys = inject("hotkeys");
const settings = useUserSettings();

const draftBindings = reactive({});
const scopes = Object.keys(defaultKeymap);

const SCOPE_LABELS = {
  global: "全局",
  "panel:symbol": "标的输入面板",
  "panel:mainChart": "主图面板",
  "modal:settings": "设置弹窗",
  "modal:MAEditor": "MA 编辑器",
};

function scopeTitle(scope) {
  const k = String(scope || "");
  const cn = SCOPE_LABELS[k];
  return cn ? `${cn}（${k}）` : k;
}

function initDraft() {
  scopes.forEach((s) => {
    draftBindings[s] = draftBindings[s] || {};

    // 唯一派生：cmd -> combo
    const cmdToCombo = hotkeys.getCommandToCombo(s);

    Object.keys(cmdToCombo).forEach((cmd) => {
      draftBindings[s][cmd] = cmdToCombo[cmd];
    });
  });
}

function labelsForScope(scope) {
  const comboToCmd = hotkeys.getComboToCommand(scope);
  const out = {};
  Object.values(comboToCmd).forEach((cmd) => {
    out[cmd] = commandLabels[cmd] || cmd;
  });
  return out;
}

const capturing = ref({ scope: "", cmd: "" });

function startCapture(scope, cmd, ev) {
  capturing.value = { scope, cmd };
  ev.target.select?.();
}

function comboFromEvent(e) {
  const parts = [];
  if (e.ctrlKey) parts.push("Ctrl");
  if (e.metaKey) parts.push("Meta");
  if (e.altKey) parts.push("Alt");
  if (e.shiftKey) parts.push("Shift");
  const key = e.code || e.key;
  parts.push(key);
  return parts.join("+");
}

function captureKey(scope, cmd, e) {
  if (e.key === "Escape") {
    stopCapture(scope, cmd, false);
    return;
  }
  if (e.key === "Enter") {
    stopCapture(scope, cmd, true);
    return;
  }
  draftBindings[scope][cmd] = comboFromEvent(e);
}

function stopCapture(scope, cmd, keep) {
  if (!keep && !draftBindings[scope][cmd]) {
    const cmdToCombo = hotkeys.getCommandToCombo(scope);
    draftBindings[scope][cmd] = cmdToCombo[cmd] || "";
  }
  capturing.value = { scope: "", cmd: "" };
}

function save() {
  // 保存结构：scope -> combo -> cmd（运行时唯一真相源）
  const overrides = {};
  scopes.forEach((s) => {
    overrides[s] = overrides[s] || {};
    Object.keys(draftBindings[s] || {}).forEach((cmd) => {
      const combo = draftBindings[s][cmd];
      if (combo) overrides[s][combo] = cmd;
    });
  });
  settings.setHotkeyOverrides(overrides);
}

function resetAll() {
  try {
    // defaultKeymap 本身就是 combo->cmd
    // draftBindings 需要 cmd->combo 视图：做一次反转（仅用于 UI）
    const invert = (comboToCmd) => {
      const out = {};
      Object.keys(comboToCmd || {}).forEach((combo) => {
        const cmd = comboToCmd[combo];
        out[cmd] = combo;
      });
      return out;
    };

    scopes.forEach((s) => {
      draftBindings[s] = invert(defaultKeymap[s] || {});
    });
  } catch (e) {
    console.error("hotkey resetAll failed:", e);
  }
}

defineExpose({ save, resetAll });

onMounted(() => {
  initDraft();
});
</script>

<style scoped>
.settings-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.desc {
  color: #aaa;
  font-size: 12px;
  line-height: 1.3;
}

.scopes-masonry {
  column-count: 3;
  column-gap: 8px;
}

.scope {
  break-inside: avoid;
  -webkit-column-break-inside: avoid;
  page-break-inside: avoid;

  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 6px 8px;
  background: rgba(0, 0, 0, 0.06);

  margin: 0 0 8px 0;

  display: inline-block;
  width: 100%;
  box-sizing: border-box;
}

.scope-title {
  color: #bbb;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row {
  display: grid;
  grid-template-columns: 1fr 150px;
  gap: 8px;
  align-items: center;
  padding: 2px 0;
}

.cmd {
  min-width: 0;
  color: #ddd;
  font-size: 12px;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.combo {
  min-width: 0;
  width: 100%;
  height: 26px;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 4px 6px;
  font-size: 12px;
  line-height: 18px;
  box-sizing: border-box;
}

@media (max-width: 1180px) {
  .scopes-masonry {
    column-count: 2;
  }
}
@media (max-width: 860px) {
  .scopes-masonry {
    column-count: 1;
  }
  .row {
    grid-template-columns: 1fr 150px;
  }
}
</style>
