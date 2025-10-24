<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\MainChartPanel.vue -->
<!-- ============================== -->
<!-- 说明：主图组件（接入“上游统一渲染中枢 useViewRenderHub” · 一次订阅一次渲染）
     - REFACTORED: 移除所有本地的 option 构建逻辑，简化为纯粹的 option 消费者。
     - doSinglePassRender 函数现在只从快照中获取预先构建好的 option 并 setOption。
-->
<template>
  <!-- 顶部两行两列布局 -->
  <div class="controls controls-grid-2x2">
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
      <!-- 日族：YYYY-MM-DD × 起/止（共 6 个数字输入框） -->
      <template v-if="!isMinuteFreq">
        <div class="inline-group">
          <span class="label">起：</span>
          <!-- 年：四位；滚轮仅改值并阻止页面滚动 -->
          <input
            class="date-cell year"
            type="number"
            v-select-all
            v-model="startFields.Y"
            min="1900"
            max="2100"
            @wheel.prevent="onWheelAdjust('start', 'Y', $event, 1900, 2100)"
          />
          <span class="sep">-</span>
          <!-- 月：两位；滚轮阻拦；输入保持两位 -->
          <input
            class="date-cell short"
            type="number"
            v-select-all
            v-model="startFields.M"
            min="1"
            max="12"
            @wheel.prevent="onWheelAdjust('start', 'M', $event, 1, 12)"
            @input="onTwoDigitInput('start', 'M', $event, 1, 12)"
          />
          <span class="sep">-</span>
          <!-- 日：两位；滚轮阻拦；输入保持两位 -->
          <input
            class="date-cell short"
            type="number"
            v-select-all
            v-model="startFields.D"
            min="1"
            max="31"
            @wheel.prevent="onWheelAdjust('start', 'D', $event, 1, 31)"
            @input="onTwoDigitInput('start', 'D', $event, 1, 31)"
          />
        </div>
        <div class="inline-group">
          <span class="label">止：</span>
          <!-- 年：四位；滚轮仅改值并阻止页面滚动 -->
          <input
            class="date-cell year"
            type="number"
            v-select-all
            v-model="endFields.Y"
            min="1900"
            max="2100"
            @wheel.prevent="onWheelAdjust('end', 'Y', $event, 1900, 2100)"
          />
          <span class="sep">-</span>
          <!-- 月：两位数字宽度 -->
          <input
            class="date-cell short"
            type="number"
            v-select-all
            v-model="endFields.M"
            min="1"
            max="12"
            @wheel.prevent="onWheelAdjust('end', 'M', $event, 1, 12)"
            @input="onTwoDigitInput('end', 'M', $event, 1, 12)"
          />
          <span class="sep">-</span>
          <!-- 日：两位数字宽度（失焦应用） -->
          <input
            class="date-cell short"
            type="number"
            v-select-all
            v-model="endFields.D"
            min="1"
            max="31"
            @wheel.prevent="onWheelAdjust('end', 'D', $event, 1, 31)"
            @input="onTwoDigitInput('end', 'D', $event, 1, 31)"
            @blur="applyInlineRangeDaily"
            title="日期失焦立即应用"
          />
        </div>
      </template>

      <!-- 分钟族：YYYY-MM-DD HH:MM × 起/止（共 10 个数字输入框） -->
      <template v-else>
        <div class="inline-group">
          <span class="label">起：</span>
          <!-- 年：四位数字宽度 -->
          <input
            class="date-cell year"
            type="number"
            v-select-all
            v-model="startFields.Y"
            min="1900"
            max="2100"
            @wheel.prevent="onWheelAdjust('start', 'Y', $event, 1900, 2100)"
          />
          <span class="sep">-</span>
          <!-- 月：两位数字宽度 -->
          <input
            class="date-cell short"
            type="number"
            v-select-all
            v-model="startFields.M"
            min="1"
            max="12"
            @wheel.prevent="onWheelAdjust('start', 'M', $event, 1, 12)"
            @input="onTwoDigitInput('start', 'M', $event, 1, 12)"
          />
          <span class="sep">-</span>
          <!-- 日：两位数字宽度 -->
          <input
            class="date-cell short"
            type="number"
            v-select-all
            v-model="startFields.D"
            min="1"
            max="31"
            @wheel.prevent="onWheelAdjust('start', 'D', $event, 1, 31)"
            @input="onTwoDigitInput('start', 'D', $event, 1, 31)"
          />
          <span class="sep space"> </span>
          <!-- 时：两位数字宽度 -->
          <input
            class="time-cell short"
            type="number"
            v-select-all
            v-model="startFields.h"
            min="0"
            max="23"
            @wheel.prevent="onWheelAdjust('start', 'h', $event, 0, 23)"
            @input="onTwoDigitInput('start', 'h', $event, 0, 23)"
          />
          <span class="sep">:</span>
          <!-- 分：两位数字宽度 -->
          <input
            class="time-cell short"
            type="number"
            v-select-all
            v-model="startFields.m"
            min="0"
            max="59"
            @wheel.prevent="onWheelAdjust('start', 'm', $event, 0, 59)"
            @input="onTwoDigitInput('start', 'm', $event, 0, 59)"
          />
        </div>
        <div class="inline-group">
          <span class="label">止：</span>
          <!-- 年：四位数字宽度 -->
          <input
            class="date-cell year"
            type="number"
            v-select-all
            v-model="endFields.Y"
            min="1900"
            max="2100"
            @wheel.prevent="onWheelAdjust('end', 'Y', $event, 1900, 2100)"
          />
          <span class="sep">-</span>
          <!-- 月：两位数字宽度 -->
          <input
            class="date-cell short"
            type="number"
            v-select-all
            v-model="endFields.M"
            min="1"
            max="12"
            @wheel.prevent="onWheelAdjust('end', 'M', $event, 1, 12)"
            @input="onTwoDigitInput('end', 'M', $event, 1, 12)"
          />
          <span class="sep">-</span>
          <!-- 日：两位数字宽度 -->
          <input
            class="date-cell short"
            type="number"
            v-select-all
            v-model="endFields.D"
            min="1"
            max="31"
            @wheel.prevent="onWheelAdjust('end', 'D', $event, 1, 31)"
            @input="onTwoDigitInput('end', 'D', $event, 1, 31)"
          />
          <span class="sep space"> </span>
          <!-- 时：两位数字宽度 -->
          <input
            class="time-cell short"
            type="number"
            v-select-all
            v-model="endFields.h"
            min="0"
            max="23"
            @wheel.prevent="onWheelAdjust('end', 'h', $event, 0, 23)"
            @input="onTwoDigitInput('end', 'h', $event, 0, 23)"
          />
          <span class="sep">:</span>
          <!-- 分：两位数字宽度（失焦应用） -->
          <input
            class="time-cell short"
            type="number"
            v-select-all
            v-model="endFields.m"
            min="0"
            max="59"
            @wheel.prevent="onWheelAdjust('end', 'm', $event, 0, 59)"
            @input="onTwoDigitInput('end', 'm', $event, 0, 59)"
            @blur="applyInlineRangeMinute"
            title="分钟失焦立即应用"
          />
        </div>
      </template>
    </div>

    <!-- 第二行右：Bars 原位输入（失焦应用；滚轮阻拦且仅改数值） -->
    <div class="row2 col-right">
      <div class="bars-inline">
        <span class="label">Bars：</span>
        <input
          class="bars-input"
          type="number"
          v-select-all
          v-model="barsStr"
          min="1"
          :max="Math.max(1, vm.meta.value?.all_rows || 1)"
          @blur="applyBarsInline"
          @wheel.prevent="onBarsWheel"
          :placeholder="String(topBarsCount)"
          title="失焦应用，可见根数"
        />
      </div>
    </div>
  </div>

  <!-- 主图画布容器 -->
  <div
    ref="wrap"
    class="chart"
    tabindex="0"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
    @dblclick="openSettingsDialog"
  >
    <div class="top-info">
      <div class="title">{{ displayTitle }}</div>
      <div class="right-box">
        <div class="status">
          <span v-if="vm.loading.value" class="badge busy">更新中…</span>
          <span v-else-if="showRefreshed.value" class="badge done"
            >已刷新 {{ refreshedAtHHMMSS.value }}</span
          >
        </div>
      </div>
    </div>
    <div ref="host" class="canvas-host"></div>
    <div
      class="bottom-strip"
      title="上下拖拽调整窗体高度"
      @mousedown="onResizeHandleDown('bottom', $event)"
    ></div>
  </div>
</template>

<script setup>
import { inject, ref, reactive, computed, watch, onMounted, onBeforeUnmount } from "vue";
import { useUserSettings } from "@/composables/useUserSettings";
import { openMainChartSettings } from "@/settings/mainShell";
import { useChartPanel } from "@/composables/useChartPanel";
import { pad2 } from "@/utils/timeFormat";
import { WINDOW_PRESETS } from "@/constants";

// --- Injected Services ---
const vm = inject("marketView");
const renderHub = inject("renderHub");
const hub = inject("viewCommandHub");
const dialogManager = inject("dialogManager");
const settings = useUserSettings();

// --- NEW: Use the common chart panel logic ---
const {
  wrapRef: wrap,
  hostRef: host,
  chart,
  displayTitle,
  onResizeHandleDown,
  onMouseEnter,
  onMouseLeave,
} = useChartPanel({
  panelKey: ref("main"),
  vm: vm,
  hub: hub,
  renderHub: renderHub,
  onChartReady: (instance) => {
    // 主图特有的初始化逻辑
    try {
        renderHub.registerChart('main', instance);
        host.value?.addEventListener('mouseenter', () => {
            renderHub.setActivePanel('main');
        });
        
        // FIX: 订阅渲染中枢
        const unsubId = renderHub.onRender((snapshot) => {
          try {
            if (instance && snapshot.main?.option) {
              // 使用 notMerge: true 保证每次都是全量替换，避免旧状态干扰
              instance.setOption(snapshot.main.option, { notMerge: true, silent: true });
            }
          } catch (e) {
            console.error("MainChartPanel onRender error:", e);
          }
        });
        onBeforeUnmount(() => renderHub.offRender(unsubId)); // FIX: 卸载时取消订阅
    } catch {}
  }
});

// --- Component-Specific Logic (UI Controls) ---
const presets = computed(() => WINDOW_PRESETS.slice());
const isActiveK = (f) => vm.chartType.value === "kline" && vm.freq.value === f;
function activateK(f) {
  vm.setFreq(f);
}

const showRefreshed = ref(false);
const refreshedAt = ref(null);
const refreshedAtHHMMSS = computed(() => {
  if (!refreshedAt.value) return "";
  const d = refreshedAt.value;
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
});

watch(() => vm.meta.value, () => {
    refreshedAt.value = new Date();
    showRefreshed.value = true;
    setTimeout(() => { showRefreshed.value = false; }, 2000);
    fillInlineFieldsFromEffective(); // 元信息更新后，同步一次“原位输入”的显示
  },
  { deep: true }
);

function openSettingsDialog() {
  try {
    openMainChartSettings(dialogManager, { activeTab: "chan" });
  } catch (e) {}
}

function onClickPreset(preset) {
  try {
    const pkey = String(preset || "ALL");
    const st = hub.getState();
    hub.execute("ChangeWidthPreset", { presetKey: pkey, allRows: st.allRows });
  } catch {}
}

// --- Inline Inputs Logic ---
const activePresetKey = ref(hub.getState().presetKey || "ALL");
hub.onChange((st) => {
  activePresetKey.value = st.presetKey || "ALL";
});

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
  // 订阅 hub 变化以更新输入框
  const subId = hub.onChange(syncFromHub);
  onBeforeUnmount(() => hub.offChange(subId));
});

onBeforeUnmount(() => {
  window.removeEventListener("chan:preview-range", onPreviewRange);
  renderHub.unregisterChart('main');
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

function onTwoDigitInput(group, key, ev, min, max) {
  try {
    const raw = String(ev?.target?.value ?? "");
    const n = parseInt(raw.replace(/[^\d]/g, ""), 10);
    if (Number.isNaN(n)) return;
    const v = Math.max(min, Math.min(max, n));
    const pad2v = pad2(v);
    if (group === "start") startFields[key] = pad2v;
    else endFields[key] = pad2v;
  } catch {}
}

function onWheelAdjust(group, key, e, min, max) {
  try {
    const tgt = group === "start" ? startFields : endFields;
    const curr = parseInt(String(tgt[key] || "0"), 10);
    const delta = e.deltaY < 0 ? +1 : -1;
    let next = Number.isFinite(curr) ? curr + delta : delta > 0 ? min : max;
    next = Math.max(min, Math.min(max, next));
    tgt[key] = key === "Y" ? String(next) : pad2(next);
  } catch {}
}

function onBarsWheel(e) {
  const curr = parseInt(String(barsStr.value || "1"), 10);
  const delta = e.deltaY < 0 ? +1 : -1;
  let next = Number.isFinite(curr) ? curr + delta : 1;
  next = Math.max(1, next);
  barsStr.value = String(next);
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
.date-cell,
.time-cell {
  width: 56px;
  height: 28px;
  line-height: 28px;
  text-align: center;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 0 4px;
  outline: none;
}
.time-cell {
  width: 48px;
}
/* 年：四位数字宽度；月/日/时/分：两位数字宽度（显示两位由脚本 onTwoDigitInput 保障） */
.date-cell.year {
  width: 56px;
} /* 年：四位数字宽度 */
.date-cell.short {
  width: 36px;
} /* 月/日：两位数字宽度 */
.time-cell.short {
  width: 36px;
} /* 时/分：两位数字宽度 */

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
.bars-input {
  width: 64px;
  height: 28px;
  line-height: 28px;
  text-align: center;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 0 6px;
  outline: none;
}

.top-info {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 28px;
  display: flex;
  align-items: center;
  padding: 0 8px;
  gap: 10px;
  z-index: 20;
}
.top-info .title {
  font-size: 13px;
  font-weight: 600;
  color: #ddd;
  user-select: none;
}
.top-info .right-box {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  user-select: none;
}
.badge {
  display: inline-block;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  line-height: 18px;
}
.badge.busy {
  background: rgba(255, 193, 7, 0.15);
  border: 1px solid rgba(255, 193, 7, 0.35);
  color: #ffca28;
}
.badge.done {
  background: rgba(46, 204, 113, 0.15);
  border: 1px solid rgba(46, 204, 113, 0.35);
  color: #2ecc71;
}

.chart {
  position: relative;
  width: 100%;
  height: clamp(360px, 50vh, 700px);
  background: #111;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  overflow: hidden;
  outline: none;
}
.canvas-host {
  position: absolute;
  left: 0;
  right: 0;
  top: 28px;
  bottom: 18px;
}
.bottom-strip {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 8px;
  background: transparent;
}
.bottom-strip:hover {
  cursor: ns-resize;
}

/* 设置弹窗标准网格样式（与 ModalDialog.vue 保持一致） */
:deep(.std-row) {
  display: grid;
  grid-template-columns: 90px repeat(5, 140px) 30px 30px;
  align-items: center;
  justify-items: center;
  column-gap: 8px;
  min-height: 36px;
}
:deep(.std-name) {
  justify-self: start;
  font-weight: 600;
}
:deep(.std-item) {
  width: 150px;
  display: flex;
  align-items: center;
  gap: 4px;
}
:deep(.std-item-label) {
  width: 60px;
  text-align: right;
  color: #bbb;
  font-size: 12px;
}
:deep(.std-item-input) {
  width: 80px;
  display: flex;
  align-items: center;
}
:deep(.std-item-input > input),
:deep(.std-item-input > select) {
  width: 100%;
  box-sizing: border-box;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 4px 6px;
}
:deep(.std-check) {
  width: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}
:deep(.std-reset) {
  width: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>