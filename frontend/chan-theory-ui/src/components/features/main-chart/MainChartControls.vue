<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\main-chart\MainChartControls.vue -->
<!-- ============================== -->
<!-- V5.0 - 固定显示全部窗宽预设 -->
<template>
  <div class="controls-grid-2x2">
    <!-- 第一行左：频率按钮 -->
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

    <!-- 第一行右：窗宽预设按钮（固定显示全部）-->
    <div class="row1 col-right">
      <div class="seg">
        <button
          v-for="p in FIXED_PRESETS"
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

    <!-- 第二行左：起止时间输入 -->
    <div class="row2 col-left time-inline">
      <!-- 日族 -->
      <template v-if="!isMinute.value">
        <div class="inline-group">
          <span class="label">起：</span>
          <NumberSpinner
            class="date-cell year"
            :model-value="startFields.Y"
            @update:modelValue="(v) => (startFields.Y = v)"
            :min="1900"
            :max="2100"
            :integer="true"
          />
          <span class="sep">-</span>
          <NumberSpinner
            class="date-cell short"
            :model-value="startFields.M"
            @update:modelValue="(v) => (startFields.M = v)"
            :min="1"
            :max="12"
            :integer="true"
            :pad-digits="2"
          />
          <span class="sep">-</span>
          <NumberSpinner
            class="date-cell short"
            :model-value="startFields.D"
            @update:modelValue="(v) => (startFields.D = v)"
            :min="1"
            :max="31"
            :integer="true"
            :pad-digits="2"
          />
        </div>
        <div class="inline-group">
          <span class="label">止：</span>
          <NumberSpinner
            class="date-cell year"
            :model-value="endFields.Y"
            @update:modelValue="(v) => (endFields.Y = v)"
            :min="1900"
            :max="2100"
            :integer="true"
          />
          <span class="sep">-</span>
          <NumberSpinner
            class="date-cell short"
            :model-value="endFields.M"
            @update:modelValue="(v) => (endFields.M = v)"
            :min="1"
            :max="12"
            :integer="true"
            :pad-digits="2"
          />
          <span class="sep">-</span>
          <NumberSpinner
            class="date-cell short"
            :model-value="endFields.D"
            @update:modelValue="(v) => (endFields.D = v)"
            :min="1"
            :max="31"
            :integer="true"
            :pad-digits="2"
            @blur="applyInlineRangeDaily"
            title="日期失焦立即应用"
          />
        </div>
      </template>

      <!-- 分钟族 -->
      <template v-else>
        <div class="inline-group">
          <span class="label">起：</span>
          <NumberSpinner
            class="date-cell year"
            :model-value="startFields.Y"
            @update:modelValue="(v) => (startFields.Y = v)"
            :min="1900"
            :max="2100"
            :integer="true"
          />
          <span class="sep">-</span>
          <NumberSpinner
            class="date-cell short"
            :model-value="startFields.M"
            @update:modelValue="(v) => (startFields.M = v)"
            :min="1"
            :max="12"
            :integer="true"
            :pad-digits="2"
          />
          <span class="sep">-</span>
          <NumberSpinner
            class="date-cell short"
            :model-value="startFields.D"
            @update:modelValue="(v) => (startFields.D = v)"
            :min="1"
            :max="31"
            :integer="true"
            :pad-digits="2"
          />
          <span class="sep space"></span>
          <NumberSpinner
            class="time-cell short"
            :model-value="startFields.h"
            @update:modelValue="(v) => (startFields.h = v)"
            :min="0"
            :max="23"
            :integer="true"
            :pad-digits="2"
          />
          <span class="sep">:</span>
          <NumberSpinner
            class="time-cell short"
            :model-value="startFields.m"
            @update:modelValue="(v) => (startFields.m = v)"
            :min="0"
            :max="59"
            :integer="true"
            :pad-digits="2"
          />
        </div>
        <div class="inline-group">
          <span class="label">止：</span>
          <NumberSpinner
            class="date-cell year"
            :model-value="endFields.Y"
            @update:modelValue="(v) => (endFields.Y = v)"
            :min="1900"
            :max="2100"
            :integer="true"
          />
          <span class="sep">-</span>
          <NumberSpinner
            class="date-cell short"
            :model-value="endFields.M"
            @update:modelValue="(v) => (endFields.M = v)"
            :min="1"
            :max="12"
            :integer="true"
            :pad-digits="2"
          />
          <span class="sep">-</span>
          <NumberSpinner
            class="date-cell short"
            :model-value="endFields.D"
            @update:modelValue="(v) => (endFields.D = v)"
            :min="1"
            :max="31"
            :integer="true"
            :pad-digits="2"
          />
          <span class="sep space"></span>
          <NumberSpinner
            class="time-cell short"
            :model-value="endFields.h"
            @update:modelValue="(v) => (endFields.h = v)"
            :min="0"
            :max="23"
            :integer="true"
            :pad-digits="2"
          />
          <span class="sep">:</span>
          <NumberSpinner
            class="time-cell short"
            :model-value="endFields.m"
            @update:modelValue="(v) => (endFields.m = v)"
            :min="0"
            :max="59"
            :integer="true"
            :pad-digits="2"
            @blur="applyInlineRangeMinute"
            title="分钟失焦立即应用"
          />
        </div>
      </template>
    </div>

    <!-- 第二行右：Bars 输入 -->
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
          :placeholder="String(barsStr)"
          title="失焦应用，可见根数"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, ref, reactive, computed, onMounted, onBeforeUnmount } from "vue";
import { WINDOW_PRESETS, presetToBars } from "@/constants";
import { isMinuteFreq } from "@/utils/timeCheck";
import { pad2 } from "@/utils/timeFormat";
import NumberSpinner from "@/components/ui/NumberSpinner.vue";

const vm = inject("marketView");
const hub = inject("viewCommandHub");
const renderHub = inject("renderHub");

// ===== 核心修改：固定显示全部预设（不随频率变化）=====
const FIXED_PRESETS = ['5D', '10D', '1M', '3M', '6M', '1Y', '3Y', '5Y', 'ALL'];

const isActiveK = (f) => vm.chartType.value === "kline" && vm.freq.value === f;

function activateK(f) {
  vm.setFreq(f);
}

// ===== 核心修复：使用 dispatchAction =====
function onClickPreset(preset) {
  try {
    const pkey = String(preset || "ALL");
    const st = hub.getState();
    const total = st.allRows;
    const arr = vm.candles.value || [];
    
    if (!arr.length) return;
    
    const nextBars = pkey === "ALL" 
      ? total 
      : presetToBars(vm.freq.value, pkey, total);
    
    const eIdx = arr.length - 1;
    const sIdx = Math.max(0, eIdx - nextBars + 1);
    
    const chart = renderHub.getChart('main');
    if (chart) {
      chart.dispatchAction({
        type: 'dataZoom',
        startValue: sIdx,
        endValue: eIdx
      });
    }
    
    // ===== 修复：删除 silent（允许广播）=====
    hub.execute("SyncViewState", {
      barsCount: nextBars,
      rightTs: arr[eIdx]?.ts,
    });
    
  } catch {}
}

const activePresetKey = ref("ALL");

const isMinute = computed(() => isMinuteFreq(vm.freq.value));
const startFields = reactive({ Y: "", M: "", D: "", h: "", m: "" });
const endFields = reactive({ Y: "", M: "", D: "", h: "", m: "" });
const barsStr = ref("");

function updateUIFromState(state) {
  try {
    const arr = vm.candles.value || [];
    if (!arr.length) return;

    activePresetKey.value = state.presetKey || "ALL";
    barsStr.value = String(Math.max(1, Number(state.barsCount || 1)));

    const tsArr = arr.map((d) => d.ts);

    let eIdx = arr.length - 1;
    if (Number.isFinite(state.rightTs)) {
      for (let i = arr.length - 1; i >= 0; i--) {
        if (tsArr[i] <= state.rightTs) {
          eIdx = i;
          break;
        }
      }
    }

    const sIdx = Math.max(0, eIdx - state.barsCount + 1);

    const startBar = arr[sIdx];
    const endBar = arr[eIdx];

    if (startBar && Number.isFinite(startBar.ts)) {
      const ds = new Date(startBar.ts);
      if (!isNaN(ds.getTime())) {
        startFields.Y = String(ds.getFullYear());
        startFields.M = pad2(ds.getMonth() + 1);
        startFields.D = pad2(ds.getDate());

        if (isMinute.value) {
          startFields.h = pad2(ds.getHours());
          startFields.m = pad2(ds.getMinutes());
        }
      }
    }

    if (endBar && Number.isFinite(endBar.ts)) {
      const de = new Date(endBar.ts);
      if (!isNaN(de.getTime())) {
        endFields.Y = String(de.getFullYear());
        endFields.M = pad2(de.getMonth() + 1);
        endFields.D = pad2(de.getDate());

        if (isMinute.value) {
          endFields.h = pad2(de.getHours());
          endFields.m = pad2(de.getMinutes());
        }
      }
    }
  } catch {}
}

let hubUnsubscribe = null;

onMounted(() => {
  updateUIFromState(hub.getState());
  
  hubUnsubscribe = hub.onChange((state) => {
    updateUIFromState(state);
  });
});

onBeforeUnmount(() => {
  if (hubUnsubscribe) {
    hub.offChange(hubUnsubscribe);
  }
});

function applyInlineRangeDaily() {
  try {
    const ys = parseInt(startFields.Y, 10),
      ms = parseInt(startFields.M, 10),
      ds = parseInt(startFields.D, 10);
    const ye = parseInt(endFields.Y, 10),
      me = parseInt(endFields.M, 10),
      de = parseInt(endFields.D, 10);
      
    if (![ys, ms, ds, ye, me, de].every(Number.isFinite)) return;

    const toYMD = (y, m, d) =>
      `${String(y).padStart(4, "0")}-${pad2(m)}-${pad2(d)}`;
    const sY = toYMD(ys, ms, ds),
      eY = toYMD(ye, me, de);

    const arr = vm.candles.value || [];
    if (!arr.length) return;

    let sIdx = -1, eIdx = -1;
    
    for (let i = 0; i < arr.length; i++) {
      const barDate = new Date(arr[i].ts);
      const ymd = barDate.toISOString().slice(0, 10);
      
      if (sIdx < 0 && ymd >= sY) sIdx = i;
      if (ymd <= eY) eIdx = i;
    }

    if (sIdx < 0) sIdx = 0;
    if (eIdx < 0) eIdx = arr.length - 1;
    if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];

    const nextBars = Math.max(1, eIdx - sIdx + 1);
    const anchorTs = arr[eIdx]?.ts;
    
    if (!Number.isFinite(anchorTs)) return;

    const chart = renderHub.getChart('main');
    if (chart) {
      chart.dispatchAction({
        type: 'dataZoom',
        startValue: sIdx,
        endValue: eIdx
      });
    }
    
    hub.execute("SyncViewState", {
      barsCount: nextBars,
      rightTs: anchorTs,
    });
  } catch {}
}

function applyInlineRangeMinute() {
  try {
    const ys = parseInt(startFields.Y, 10),
      ms = parseInt(startFields.M, 10),
      ds = parseInt(startFields.D, 10),
      hs = parseInt(startFields.h, 10),
      mins = parseInt(startFields.m, 10);
    const ye = parseInt(endFields.Y, 10),
      me = parseInt(endFields.M, 10),
      de = parseInt(endFields.D, 10),
      he = parseInt(endFields.h, 10),
      mine = parseInt(endFields.m, 10);

    if (![ys, ms, ds, hs, mins, ye, me, de, he, mine].every(Number.isFinite))
      return;

    const startDt = new Date(ys, ms - 1, ds, hs, mins, 0, 0);
    const endDt = new Date(ye, me - 1, de, he, mine, 0, 0);
    const msStart = startDt.getTime();
    const msEnd = endDt.getTime();

    if (!Number.isFinite(msStart) || !Number.isFinite(msEnd)) return;

    const arr = vm.candles.value || [];
    if (!arr.length) return;

    const tsArr = arr.map((d) => d.ts);

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

    const chart = renderHub.getChart('main');
    if (chart) {
      chart.dispatchAction({
        type: 'dataZoom',
        startValue: sIdx,
        endValue: eIdx
      });
    }
    
    hub.execute("SyncViewState", {
      barsCount: nextBars,
      rightTs: anchorTs,
    });
  } catch {}
}

function applyBarsInline() {
  try {
    const n = Math.max(1, parseInt(String(barsStr.value || "1"), 10));
    const arr = vm.candles.value || [];
    
    if (!arr.length) return;
    
    const eIdx = arr.length - 1;
    const sIdx = Math.max(0, eIdx - n + 1);
    
    const chart = renderHub.getChart('main');
    if (chart) {
      chart.dispatchAction({
        type: 'dataZoom',
        startValue: sIdx,
        endValue: eIdx
      });
    }
    
    hub.execute("SyncViewState", {
      barsCount: n,
      rightTs: arr[eIdx]?.ts,
    });
  } catch {}
}
</script>

<style scoped>
.controls-grid-2x2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto;
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
.time-cell,
.bars-input {
  display: inline-block;
  vertical-align: middle;
}
.date-cell.year {
  width: 64px;
}
.date-cell.short {
  width: 50px;
}
.time-cell.short {
  width: 50px;
}
.bars-input {
  width: 64px;
}

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