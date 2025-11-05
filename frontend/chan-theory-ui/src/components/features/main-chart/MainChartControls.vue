<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\main-chart\MainChartControls.vue -->
<!-- ============================== -->
<!-- 说明：主图控制栏 (新提取的组件)
     - REFACTORED: 从 MainChartPanel.vue 中分离，负责所有顶部控制UI与交互。
     - OPTIMIZED: 使用 NumberSpinner 组件替代了所有原生 <input type="number"> 及其手写的滚轮/格式化/补零逻辑。
-->
<template>
  <!-- 顶部两行两列布局 -->
  <div class="controls-grid-2x2">
    <!-- 第一行左：频率按钮（切频会触发后端 reload） -->
    <div class="row1 col-left">
      <div class="seg">
        <button
          class="seg-btn"
          :class="{ active: isActiveK('1d') }"
          @click="activateK('1d')"
          title="日K线"
        >
          日
        </button>
        <button
          class="seg-btn"
          :class="{ active: isActiveK('1w') }"
          @click="activateK('1w')"
          title="周K线"
        >
          周
        </button>
        <button
          class="seg-btn"
          :class="{ active: isActiveK('1M') }"
          @click="activateK('1M')"
          title="月K线"
        >
          月
        </button>
        <button
          class="seg-btn"
          :class="{ active: isActiveK('1m') }"
          @click="activateK('1m')"
          title="1分钟"
        >
          1分
        </button>
        <button
          class="seg-btn"
          :class="{ active: isActiveK('5m') }"
          @click="activateK('5m')"
          title="5分钟"
        >
          5分
        </button>
        <button
          class="seg-btn"
          :class="{ active: isActiveK('15m') }"
          @click="activateK('15m')"
          title="15分钟"
        >
          15分
        </button>
        <button
          class="seg-btn"
          :class="{ active: isActiveK('30m') }"
          @click="activateK('30m')"
          title="30分钟"
        >
          30分
        </button>
        <button
          class="seg-btn"
          :class="{ active: isActiveK('60m') }"
          @click="activateK('60m')"
          title="60分钟"
        >
          60分
        </button>
      </div>
    </div>

    <!-- 第一行右：窗宽预设按钮（靠右） -->
    <div class="row1 col-right">
      <div class="seg">
        <button
          v-for="p in presets"
          :key="p"
          class="seg-btn"
          :class="{ active: activePresetKey === p }"
          @click="onClickPreset(p)"
          :title="`快捷区间：${p}`"
        >
          {{ p }}
        </button>
      </div>
    </div>

    <!-- 第二行左：起止“原位输入”（按频率显示日/分钟族） -->
    <div class="row2 col-left time-inline">
      <!-- 日族 -->
      <template v-if="!isMinuteFreq">
        <div class="inline-group">
          <span class="label">起：</span>
          <NumberSpinner class="date-cell year" :model-value="startFields.Y" @update:modelValue="v => startFields.Y = v" :min="1900" :max="2100" :integer="true" />
          <span class="sep">-</span>
          <NumberSpinner class="date-cell short" :model-value="startFields.M" @update:modelValue="v => startFields.M = v" :min="1" :max="12" :integer="true" :pad-digits="2" />
          <span class="sep">-</span>
          <NumberSpinner class="date-cell short" :model-value="startFields.D" @update:modelValue="v => startFields.D = v" :min="1" :max="31" :integer="true" :pad-digits="2" />
        </div>
        <div class="inline-group">
          <span class="label">止：</span>
          <NumberSpinner class="date-cell year" :model-value="endFields.Y" @update:modelValue="v => endFields.Y = v" :min="1900" :max="2100" :integer="true" />
          <span class="sep">-</span>
          <NumberSpinner class="date-cell short" :model-value="endFields.M" @update:modelValue="v => endFields.M = v" :min="1" :max="12" :integer="true" :pad-digits="2" />
          <span class="sep">-</span>
          <NumberSpinner class="date-cell short" :model-value="endFields.D" @update:modelValue="v => endFields.D = v" :min="1" :max="31" :integer="true" :pad-digits="2" @blur="applyInlineRangeDaily" title="日期失焦立即应用" />
        </div>
      </template>

      <!-- 分钟族 -->
      <template v-else>
        <div class="inline-group">
          <span class="label">起：</span>
          <NumberSpinner class="date-cell year" :model-value="startFields.Y" @update:modelValue="v => startFields.Y = v" :min="1900" :max="2100" :integer="true" />
          <span class="sep">-</span>
          <NumberSpinner class="date-cell short" :model-value="startFields.M" @update:modelValue="v => startFields.M = v" :min="1" :max="12" :integer="true" :pad-digits="2" />
          <span class="sep">-</span>
          <NumberSpinner class="date-cell short" :model-value="startFields.D" @update:modelValue="v => startFields.D = v" :min="1" :max="31" :integer="true" :pad-digits="2" />
          <span class="sep space"></span>
          <NumberSpinner class="time-cell short" :model-value="startFields.h" @update:modelValue="v => startFields.h = v" :min="0" :max="23" :integer="true" :pad-digits="2" />
          <span class="sep">:</span>
          <NumberSpinner class="time-cell short" :model-value="startFields.m" @update:modelValue="v => startFields.m = v" :min="0" :max="59" :integer="true" :pad-digits="2" />
        </div>
        <div class="inline-group">
          <span class="label">止：</span>
          <NumberSpinner class="date-cell year" :model-value="endFields.Y" @update:modelValue="v => endFields.Y = v" :min="1900" :max="2100" :integer="true" />
          <span class="sep">-</span>
          <NumberSpinner class="date-cell short" :model-value="endFields.M" @update:modelValue="v => endFields.M = v" :min="1" :max="12" :integer="true" :pad-digits="2" />
          <span class="sep">-</span>
          <NumberSpinner class="date-cell short" :model-value="endFields.D" @update:modelValue="v => endFields.D = v" :min="1" :max="31" :integer="true" :pad-digits="2" />
          <span class="sep space"></span>
          <NumberSpinner class="time-cell short" :model-value="endFields.h" @update:modelValue="v => endFields.h = v" :min="0" :max="23" :integer="true" :pad-digits="2" />
          <span class="sep">:</span>
          <NumberSpinner class="time-cell short" :model-value="endFields.m" @update:modelValue="v => endFields.m = v" :min="0" :max="59" :integer="true" :pad-digits="2" @blur="applyInlineRangeMinute" title="分钟失焦立即应用" />
        </div>
      </template>
    </div>

    <!-- 第二行右：Bars 原位输入 -->
    <div class="row2 col-right">
      <div class="bars-inline">
        <span class="label">Bars：</span>
        <NumberSpinner
            class="bars-input"
            v-model="barsStr"
            :min="1"
            :max="Math.max(1, vm.meta.value?.all_rows || 1)"
            :integer="true"
            @blur="applyBarsInline"
            :placeholder="String(topBarsCount)"
            title="失焦应用，可见根数"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, ref, reactive, computed, watch, onMounted, onBeforeUnmount } from "vue";
import { WINDOW_PRESETS } from "@/constants";
import { pad2 } from "@/utils/timeFormat";
import NumberSpinner from "@/components/ui/NumberSpinner.vue";

const vm = inject("marketView");
const hub = inject("viewCommandHub");

// --- UI Controls Logic ---
const presets = computed(() => WINDOW_PRESETS.slice());
const isActiveK = (f) => vm.chartType.value === "kline" && vm.freq.value === f;
function activateK(f) {
  vm.setFreq(f);
}

function onClickPreset(preset) {
  try {
    const pkey = String(preset || "ALL");
    const st = hub.getState();
    hub.execute("ChangeWidthPreset", { presetKey: pkey, allRows: st.allRows });
  } catch {}
}

const activePresetKey = ref(hub.getState().presetKey || "ALL");
hub.onChange((st) => {
  activePresetKey.value = st.presetKey || "ALL";
});

// --- Inline Inputs Logic (Optimized with NumberSpinner) ---
const isMinuteFreq = computed(() => /m$/.test(String(vm.freq.value || "")));
const startFields = reactive({ Y: "", M: "", D: "", h: "", m: "" });
const endFields = reactive({ Y: "", M: "", D: "", h: "", m: "" });
const barsStr = ref("");

const previewStartStr = ref("");
const previewEndStr = ref("");
const previewBarsCount = ref(0);

const topBarsCount = computed(() => {
  return Number(previewBarsCount.value || vm.meta.value?.view_rows || 0);
});

watch(() => vm.meta.value, () => {
    fillInlineFieldsFromEffective(); // Meta update also triggers a sync of inline fields
  },
  { deep: true }
);

function onPreviewRange(ev) {
  try {
    const d = ev?.detail || {};
    if (String(d.code || "") !== String(vm.code.value || "") || String(d.freq || "") !== String(vm.freq.value || "")) return;
    const arr = vm.candles.value || [];
    const s = Math.max(0, Math.min(arr.length - 1, Number(d.sIdx)));
    const e = Math.max(0, Math.min(arr.length - 1, Number(d.eIdx)));
    previewStartStr.value = arr[s]?.t || "";
    previewEndStr.value = arr[e]?.t || "";
    previewBarsCount.value = Math.max(1, e - s + 1);
    fillInlineFieldsFromEffective();
  } catch {}
}

onMounted(() => {
  window.addEventListener("chan:preview-range", onPreviewRange);
  fillInlineFieldsFromEffective();
  const subId = hub.onChange(syncFromHub);
  onBeforeUnmount(() => hub.offChange(subId));
});

onBeforeUnmount(() => {
  window.removeEventListener("chan:preview-range", onPreviewRange);
});

function syncFromHub(st) {
  try {
    const arr = vm.candles.value || [];
    if (!arr.length) return;
    let eIdx = arr.length - 1;
    if (Number.isFinite(+st.rightTs)) {
      const rt = +st.rightTs;
      for (let i = arr.length - 1; i >= 0; i--) {
        const t = Date.parse(arr[i].t);
        if (Number.isFinite(t) && t <= rt) {
          eIdx = i;
          break;
        }
      }
    }
    const bars = Math.max(1, Number(st.barsCount || 1));
    let sIdx = Math.max(0, eIdx - bars + 1);
    if (sIdx === 0 && eIdx - sIdx + 1 < bars) {
      eIdx = Math.min(arr.length - 1, bars - 1);
    }
    previewStartStr.value = arr[sIdx]?.t || "";
    previewEndStr.value = arr[eIdx]?.t || "";
    previewBarsCount.value = Math.max(1, eIdx - sIdx + 1);
    fillInlineFieldsFromEffective();
    barsStr.value = String(Math.max(1, Number(st.barsCount || 1)));
  } catch {}
}

function fillInlineFieldsFromEffective() {
  try {
    const startIso = previewStartStr.value || vm.visibleRange.value.startStr || "";
    const endIso = previewEndStr.value || vm.visibleRange.value.endStr || "";
    if (!startIso || !endIso) return;
    const ds = new Date(startIso), de = new Date(endIso);
    if (Number.isNaN(ds.getTime()) || Number.isNaN(de.getTime())) return;
    startFields.Y = String(ds.getFullYear());
    startFields.M = pad2(ds.getMonth() + 1);
    startFields.D = pad2(ds.getDate());
    endFields.Y = String(de.getFullYear());
    endFields.M = pad2(de.getMonth() + 1);
    endFields.D = pad2(de.getDate());
    if (isMinuteFreq.value) {
      startFields.h = pad2(ds.getHours());
      startFields.m = pad2(ds.getMinutes());
      endFields.h = pad2(de.getHours());
      endFields.m = pad2(de.getMinutes());
    } else {
      startFields.h = ""; startFields.m = ""; endFields.h = ""; endFields.m = "";
    }
    barsStr.value = String(Math.max(1, Number(previewBarsCount.value || vm.meta.value?.view_rows || 0)));
  } catch {}
}

function applyInlineRangeDaily() {
  try {
    const ys = parseInt(startFields.Y, 10), ms = parseInt(startFields.M, 10), ds = parseInt(startFields.D, 10);
    const ye = parseInt(endFields.Y, 10), me = parseInt(endFields.M, 10), de = parseInt(endFields.D, 10);
    if (![ys, ms, ds, ye, me, de].every(Number.isFinite)) return;
    const toYMD = (y, m, d) => `${String(y).padStart(4, "0")}-${pad2(m)}-${pad2(d)}`;
    const sY = toYMD(ys, ms, ds), eY = toYMD(ye, me, de);
    const arr = vm.candles.value || [];
    if (!arr.length) return;
    let sIdx = -1, eIdx = -1;
    for (let i = 0; i < arr.length; i++) {
      const ymd = String(arr[i].t || "").slice(0, 10);
      if (sIdx < 0 && ymd >= sY) sIdx = i;
      if (ymd <= eY) eIdx = i;
    }
    if (sIdx < 0) sIdx = 0;
    if (eIdx < 0) eIdx = arr.length - 1;
    if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];
    const nextBars = Math.max(1, eIdx - sIdx + 1);
    const anchorTs = Date.parse(arr[eIdx]?.t || "");
    if (!Number.isFinite(anchorTs)) return;
    hub.execute("SetDatesManual", { nextBars, nextRightTs: anchorTs });
  } catch {}
}

function applyInlineRangeMinute() {
  try {
    const ys = parseInt(startFields.Y, 10), ms = parseInt(startFields.M, 10), ds = parseInt(startFields.D, 10), hs = parseInt(startFields.h, 10), mins = parseInt(startFields.m, 10);
    const ye = parseInt(endFields.Y, 10), me = parseInt(endFields.M, 10), de = parseInt(endFields.D, 10), he = parseInt(endFields.h, 10), mine = parseInt(endFields.m, 10);
    if (![ys, ms, ds, hs, mins, ye, me, de, he, mine].every(Number.isFinite)) return;
    const startDt = new Date(ys, ms - 1, ds, hs, mins, 0, 0), endDt = new Date(ye, me - 1, de, he, mine, 0, 0);
    const msStart = startDt.getTime(), msEnd = endDt.getTime();
    if (!Number.isFinite(msStart) || !Number.isFinite(msEnd)) return;
    const arr = vm.candles.value || [];
    if (!arr.length) return;
    const tsArr = arr.map((d) => Date.parse(d.t));
    let sIdx = -1, eIdx = -1;
    for (let i = 0; i < tsArr.length; i++) {
      const t = tsArr[i];
      if (!Number.isFinite(t)) continue;
      if (sIdx < 0 && t >= msStart) sIdx = i;
      if (t <= msEnd) eIdx = i;
    }
    if (sIdx < 0) sIdx = 0;
    if (eIdx < 0) eIdx = tsArr.length - 1;
    if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];
    const nextBars = Math.max(1, eIdx - sIdx + 1);
    const anchorTs = tsArr[eIdx];
    if (!Number.isFinite(anchorTs)) return;
    hub.execute("SetDatesManual", { nextBars, nextRightTs: anchorTs });
  } catch {}
}

function applyBarsInline() {
  try {
    const n = Math.max(1, parseInt(String(barsStr.value || "1"), 10));
    hub.execute("SetBarsManual", { nextBars: n });
  } catch {}
}
</script>

<style scoped>
/* 顶部两行两列布局 */
.controls-grid-2x2 {
  display: grid;
  grid-template-columns: 1fr 1fr; /* 左右两列 */
  grid-template-rows: auto auto; /* 两行 */
  gap: 6px 12px;
  margin: 8px 0 8px 0;
}
.row1.col-left {
  grid-column: 1;
  grid-row: 1;
  justify-self: start;
}
.row1.col-right {
  grid-column: 2;
  grid-row: 1;
  justify-self: end;
}
.row2.col-left {
  grid-column: 1;
  grid-row: 2;
  justify-self: start;
}
.row2.col-right {
  grid-column: 2;
  grid-row: 2;
  justify-self: end;
}

.seg {
  display: inline-flex;
  align-items: center;
  border: 1px solid #444;
  border-radius: 10px;
  overflow: hidden;
  background: #1a1a1a;
  height: 36px;
}
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
  border-radius: 0;
}
.seg-btn + .seg-btn {
  border-left: 1px solid #444;
}
.seg-btn.active {
  background: #2b4b7e;
  color: #fff;
}

.time-inline {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #ddd;
  user-select: none;
}
.inline-group {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.inline-group .label {
  color: #bbb;
  margin-right: 2px;
}
/* NumberSpinner 容器样式 */
.date-cell, .time-cell, .bars-input {
  display: inline-block;
  vertical-align: middle;
}
.date-cell.year { width: 64px; }
.date-cell.short { width: 50px; }
.time-cell.short { width: 50px; }
.bars-input { width: 64px; }

.sep {
  color: #888;
}
.sep.space {
  width: 6px;
  display: inline-block;
}

.bars-inline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #ddd;
  user-select: none;
}
.bars-inline .label {
  color: #bbb;
}
</style>
