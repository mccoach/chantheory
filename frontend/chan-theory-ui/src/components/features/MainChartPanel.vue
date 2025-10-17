<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\MainChartPanel.vue -->
<!-- ============================== -->
<!-- 说明：主图组件（接入“上游统一渲染中枢 useViewRenderHub” · 一次订阅一次渲染）
     本次仅适配 useChan 输出的新键；覆盖层 series 的构造保持原方法与时序，
     仅在 recomputeChan() 与 buildOverlaySeriesForOption() 内消费新键，不改变其余流程/顺序。
     NEW: 接入“笔中枢”：
       - 计算：computePenPivots()
       - 渲染：buildPenPivotAreas()
       - 设置：在“缠论标记”页的“简笔”行下方新增“笔中枢”设置行
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
import {
  inject,
  onMounted,
  onBeforeUnmount,
  ref,
  watch,
  computed,
  defineComponent,
  h,
  reactive,
} from "vue";
import * as echarts from "echarts";
import {
  buildMainChartOption,
  createFixedTooltipPositioner,
} from "@/charts/options";
import {
  DEFAULT_MA_CONFIGS,
  CHAN_DEFAULTS,
  DEFAULT_KLINE_STYLE,
  DEFAULT_APP_PREFERENCES,
  FRACTAL_DEFAULTS,
  FRACTAL_SHAPES,
  FRACTAL_FILLS,
  WINDOW_PRESETS,
  PENS_DEFAULTS,
  SEGMENT_DEFAULTS,
  CHAN_PEN_PIVOT_DEFAULTS,
} from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import {
  computeInclude,
  computeFractals,
  computePens,
  computeSegments,
  computePenPivots, // NEW: 计算笔中枢
} from "@/composables/useChan"; // 新增：computeSegments
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import {
  buildUpDownMarkers,
  buildFractalMarkers,
  buildPenLines,
  buildSegmentLines,
  buildBarrierLines, // NEW: 屏障竖线
  buildPenPivotAreas, // NEW: 渲染笔中枢
} from "@/charts/chan/layers"; // 新增：buildSegmentLines
import SettingsGrid from "@/components/ui/SettingsGrid.vue";

import {
  pad2,                 // 两位补零（用于输入框与日期拼装）
  fmtShort,             // 预览短文本（按 freq 输出）
  isMinuteFreq as isMinuteFreqFmt, // 分钟族判断
} from "@/utils/timeFormat";

/* 双跳脱调度，避免主流程期 setOption/resize */
function schedule(fn) {
  try {
    requestAnimationFrame(() => {
      setTimeout(fn, 0);
    });
  } catch {
    setTimeout(fn, 0);
  }
}
function scheduleSetOption(opt, opts) {
  schedule(() => {
    try {
      chart && chart.setOption(opt, opts);
    } catch {}
  });
}
function scheduleResize(width, height) {
  schedule(() => {
    try {
      chart && chart.resize({ width, height });
    } catch {}
  });
}

const vm = inject("marketView");
const renderHub = useViewRenderHub();
const settings = useUserSettings();
const { findBySymbol } = useSymbolIndex();
const dialogManager = inject("dialogManager");
const hub = useViewCommandHub();

/* 当前高亮预设键 */
const activePresetKey = ref(hub.getState().presetKey || "ALL");
hub.onChange((st) => {
  activePresetKey.value = st.presetKey || "ALL";
});

/* 覆盖式防抖/序号守护 */
let renderSeq = 0;
function isStale(seq) {
  return seq !== renderSeq;
}

/* 程序化 dataZoom 守护 */
let progZoomGuard = { active: false, sig: null, ts: 0 };
// 最近一次已应用范围（双保险早退，防回环）
let lastAppliedRange = { s: null, e: null };

/* 预设与高级面板 */
const presets = computed(() => WINDOW_PRESETS.slice());
const isActiveK = (f) => vm.chartType.value === "kline" && vm.freq.value === f;
function activateK(f) {
  vm.chartType.value = "kline";
  vm.setFreq(f);
}

/* 画布/实例与 Resize */
const wrap = ref(null);
const host = ref(null);
let chart = null;
let ro = null;
let unsubId = null;

// NEW: 上报悬浮状态
function onMouseEnter() {
  renderHub.setHoveredPanel("main");
  focusWrap(); // 原有 focus 逻辑
}
function onMouseLeave() {
  renderHub.setHoveredPanel(null);
}

// 下沿拖拽高度调整（保留）
let dragging = false,
  startY = 0,
  startH = 0;
function onResizeHandleDown(_pos, e) {
  dragging = true;
  startY = e.clientY;
  startH = wrap.value?.clientHeight || 0;
  window.addEventListener("mousemove", onResizeHandleMove);
  window.addEventListener("mouseup", onResizeHandleUp, { once: true });
}
function onResizeHandleMove(e) {
  if (!dragging) return;
  const next = Math.max(160, Math.min(800, startH + (e.clientY - startY)));
  if (wrap.value) {
    wrap.value.style.height = `${Math.floor(next)}px`;
    safeResize();
  }
}
function onResizeHandleUp() {
  dragging = false;
  window.removeEventListener("mousemove", onResizeHandleMove);
}
function safeResize() {
  if (!chart || !host.value) return;
  const seq = renderSeq;
  requestAnimationFrame(() => {
    if (isStale(seq)) return;
    try {
      const nextW = host.value.clientWidth;
      const nextH = host.value.clientHeight;
      // 双跳脱 resize
      scheduleResize(nextW, nextH);

      const st = hub.getState();
      const approxNextMarker = Math.max(
        1,
        Math.min(16, Math.round((nextW * 0.88) / Math.max(1, st.barsCount)))
      );
      if (approxNextMarker !== hub.markerWidthPx.value) {
        hub.execute("ResizeHost", { widthPx: nextW });
      }
    } catch {}
  });
}

/* 设置弹窗（草稿加载 + pen 合并表达式统一） */
const settingsDraft = reactive({
  kForm: { ...DEFAULT_KLINE_STYLE },
  maForm: {},
  chanForm: { ...CHAN_DEFAULTS, pen: { ...PENS_DEFAULTS }, penPivot: { ...CHAN_PEN_PIVOT_DEFAULTS } }, // NEW: 默认并入
  fractalForm: { ...FRACTAL_DEFAULTS },
  adjust: DEFAULT_APP_PREFERENCES.adjust,
});
let prevAdjust = "none";
function openSettingsDialog() {
  try {
    // 草稿加载（显示设置）
    settingsDraft.kForm = JSON.parse(
      JSON.stringify({
        ...DEFAULT_KLINE_STYLE,
        ...(settings.klineStyle.value || {}),
      })
    );

    // MA 草稿加载
    const maDefaults = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS));
    const maLocal = settings.maConfigs.value || {};
    Object.keys(maDefaults).forEach((k) => {
      const src = maLocal[k] || maDefaults[k];
      maDefaults[k] = { ...maDefaults[k], ...src };
    });
    settingsDraft.maForm = maDefaults;

    // 缠论设置草稿加载（统一合并表达式，pen 与其他项相同“默认+用户覆盖”的策略）
    settingsDraft.chanForm = JSON.parse(
      JSON.stringify({
        ...CHAN_DEFAULTS,
        ...(settings.chanSettings.value || {}),
        // 笔设置
        pen: {
          ...PENS_DEFAULTS,
          ...((settings.chanSettings.value || {}).pen || {}),
        },
        // 线段设置（默认 + 用户覆盖）
        segment: {
          ...SEGMENT_DEFAULTS,
          ...((settings.chanSettings.value || {}).segment || {}),
        },
        // 笔中枢
        penPivot: {
          ...CHAN_PEN_PIVOT_DEFAULTS,
          ...((settings.chanSettings.value || {}).penPivot || {}),
        },
      })
    );

    // 分型设置草稿加载（保持一致的“默认+用户覆盖”）
    settingsDraft.fractalForm = JSON.parse(
      JSON.stringify({
        ...FRACTAL_DEFAULTS,
        ...(settings.fractalSettings.value || {}),
      })
    );

    // 复权草稿加载
    prevAdjust = String(
      vm.adjust.value || settings.adjust.value || DEFAULT_APP_PREFERENCES.adjust
    );
    settingsDraft.adjust = prevAdjust;

    // NEW: “全部恢复默认”触发计数器（供内部组件监听以刷新快照）
    const resetAllTick = ref(0);

    // 行情显示与缠论设置内容组件
    const MainChartSettingsContent = defineComponent({
      props: { activeTab: { type: String, default: "display" } },
      setup(props) {
        // —— 分型与均线 三态快照/循环指针逻辑（保留上层控制，不下沉 UI 组件） —— //
        // 分型
        const ff = settingsDraft.fractalForm;
        const lastManualSnapshot = ref(getCurrentFractalCombination(ff));
        const globalCycleIndex = ref(0);
        function getCurrentFractalCombination(ff) {
          return {
            strong: !!ff.styleByStrength?.strong?.enabled,
            standard: !!ff.styleByStrength?.standard?.enabled,
            weak: !!ff.styleByStrength?.weak?.enabled,
            confirm: !!ff.confirmStyle?.enabled,
          };
        }
        function setCombination(ff, combo) {
          const s = ff.styleByStrength || {};
          ["strong", "standard", "weak"].forEach((k) => {
            if (!s[k])
              s[k] = JSON.parse(
                JSON.stringify(FRACTAL_DEFAULTS.styleByStrength[k])
              );
          });
          s.strong.enabled = !!combo.strong;
          s.standard.enabled = !!combo.standard;
          s.weak.enabled = !!combo.weak;
          ff.styleByStrength = { ...s };
          ff.showStrength = {
            strong: !!combo.strong,
            standard: !!combo.standard,
            weak: !!combo.weak,
          };
          ff.confirmStyle = {
            ...(ff.confirmStyle ||
              JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.confirmStyle))),
            enabled: !!combo.confirm,
          };
        }
        function isAllOn(combo) {
          return !!(
            combo.strong &&
            combo.standard &&
            combo.weak &&
            combo.confirm
          );
        }
        function isAllOff(combo) {
          return !!(
            !combo.strong &&
            !combo.standard &&
            !combo.weak &&
            !combo.confirm
          );
        }
        function statesForGlobalToggle() {
          const snap = lastManualSnapshot.value;
          if (isAllOn(snap) || isAllOff(snap)) return ["allOn", "allOff"];
          return ["allOn", "allOff", "snapshot"];
        }
        function applyGlobalState(ff, key) {
          if (key === "allOn") {
            setCombination(ff, { strong: true, standard: true, weak: true, confirm: true });
            return;
          }
          if (key === "allOff") {
            setCombination(ff, { strong: false, standard: false, weak: false, confirm: false });
            return;
          }
          if (key === "snapshot") {
            setCombination(ff, { ...lastManualSnapshot.value });
          }
        }
        function onGlobalToggleFractal() {
          const states = statesForGlobalToggle();
          const key = states[globalCycleIndex.value % states.length];
          applyGlobalState(settingsDraft.fractalForm, key);
          globalCycleIndex.value = (globalCycleIndex.value + 1) % states.length;
        }
        function globalToggleUi() {
          const cur = getCurrentFractalCombination(settingsDraft.fractalForm);
          return {
            checked: isAllOn(cur),
            indeterminate: !isAllOn(cur) && !isAllOff(cur),
          };
        }
        function updateSnapshotFromCurrent() {
          lastManualSnapshot.value = getCurrentFractalCombination(settingsDraft.fractalForm);
          globalCycleIndex.value = 0;
        }

        // 均线（主图 MA）三态
        function getMAKeys() {
          return Object.keys(settingsDraft.maForm || {});
        }
        function getCurrentMACombination() {
          const combo = {};
          for (const k of getMAKeys()) combo[k] = !!settingsDraft.maForm?.[k]?.enabled;
          return combo;
        }
        const maLastManualSnapshot = ref(getCurrentMACombination());
        const maGlobalCycleIndex = ref(0);
        function isAllMAOn(combo) {
          const ks = getMAKeys();
          return ks.length > 0 && ks.every((k) => combo[k] === true);
        }
        function isAllMAOff(combo) {
          const ks = getMAKeys();
          return ks.length > 0 && ks.every((k) => combo[k] === false);
        }
        function maStatesForGlobalToggle() {
          const snap = maLastManualSnapshot.value || {};
          if (isAllMAOn(snap) || isAllMAOff(snap)) return ["allOn", "allOff"];
          return ["allOn", "allOff", "snapshot"];
        }
        function applyMAGlobalState(stateKey) {
          const ks = getMAKeys();
          if (!ks.length) return;
          if (stateKey === "allOn") {
            for (const k of ks) {
              settingsDraft.maForm[k] = { ...(settingsDraft.maForm[k] || {}), enabled: true };
            }
            return;
          }
          if (stateKey === "allOff") {
            for (const k of ks) {
              settingsDraft.maForm[k] = { ...(settingsDraft.maForm[k] || {}), enabled: false };
            }
            return;
          }
          if (stateKey === "snapshot") {
            const snap = maLastManualSnapshot.value || {};
            for (const k of ks) {
              settingsDraft.maForm[k] = { ...(settingsDraft.maForm[k] || {}), enabled: !!snap[k] };
            }
          }
        }
        function onMAGlobalToggle() {
          const states = maStatesForGlobalToggle();
          const key = states[maGlobalCycleIndex.value % states.length];
          applyMAGlobalState(key);
          maGlobalCycleIndex.value = (maGlobalCycleIndex.value + 1) % states.length;
        }
        function maGlobalUi() {
          const cur = getCurrentMACombination();
          return { checked: isAllMAOn(cur), indeterminate: !isAllMAOn(cur) && !isAllMAOff(cur) };
        }
        function updateMASnapshotFromCurrent() {
          maLastManualSnapshot.value = getCurrentMACombination();
          maGlobalCycleIndex.value = 0;
        }

        // 全部恢复默认触发后刷新快照
        watch(resetAllTick, () => {
          try {
            lastManualSnapshot.value = getCurrentFractalCombination(settingsDraft.fractalForm);
            globalCycleIndex.value = 0;
            maLastManualSnapshot.value = getCurrentMACombination();
            maGlobalCycleIndex.value = 0;
          } catch {}
        });

        // —— Rows 构建（UI-only） —— //
        function rowsDisplay() {
          const rows = [];

          // 原始K线
          rows.push({
            key: "k-original",
            name: "原始K线",
            items: [
              { key: "adjust", label: "复权" },
              { key: "upColor", label: "阳线颜色" },
              { key: "upFade", label: "阳线淡显" },
              { key: "downColor", label: "阴线颜色" },
              { key: "downFade", label: "阴线淡显" },
            ],
            check: { type: "single", checked: !!settingsDraft.kForm.originalEnabled },
            reset: { visible: true, title: "恢复默认" },
          });

          // 合并K线
          rows.push({
            key: "k-merged",
            name: "合并K线",
            items: [
              { key: "outlineWidth", label: "轮廓线宽" },
              { key: "mUpColor", label: "上涨颜色" },
              { key: "mDownColor", label: "下跌颜色" },
              { key: "fillFade", label: "填充淡显" },
              { key: "displayOrder", label: "显示层级" },
            ],
            check: { type: "single", checked: !!settingsDraft.kForm.mergedEnabled },
            reset: { visible: true, title: "恢复默认" },
          });

          // 均线总控（三态）
          rows.push({
            key: "ma-global",
            name: "均线总控",
            items: [],
            check: { type: "tri", checked: !!maGlobalUi().checked, indeterminate: !!maGlobalUi().indeterminate },
            reset: { visible: false },
          });

          // 各 MA 行
          Object.entries(settingsDraft.maForm || {}).forEach(([key, conf]) => {
            rows.push({
              key: `ma-${key}`,
              name: `MA${conf.period}`,
              items: [
                { key: "ma-width", label: "线宽", maKey: key },
                { key: "ma-color", label: "颜色", maKey: key },
                { key: "ma-style", label: "线型", maKey: key },
                { key: "ma-period", label: "周期", maKey: key },
              ],
              check: { type: "single", checked: !!conf.enabled },
              reset: { visible: true, title: "恢复默认" },
            });
          });

          return rows;
        }

        function rowsChan() {
          const rows = [];

          // 涨跌标记
          rows.push({
            key: "chan-updown",
            name: "涨跌标记",
            items: [
              { key: "upShape", label: "上涨符号" },
              { key: "upColor", label: "上涨颜色" },
              { key: "downShape", label: "下跌符号" },
              { key: "downColor", label: "下跌颜色" },
              { key: "anchorPolicy", label: "承载点" },
            ],
            check: { type: "single", checked: !!settingsDraft.chanForm.showUpDownMarkers },
            reset: { visible: true, title: "恢复默认" },
          });

          // 分型判定（三态总控） + 判定参数
          const gui = globalToggleUi();
          rows.push({
            key: "fr-global",
            name: "分型判定",
            items: [
              { key: "fr-minTick", label: "最小tick" },
              { key: "fr-minPct", label: "最小幅度%" },
              { key: "fr-minCond", label: "判断条件" },
            ],
            check: { type: "tri", checked: !!gui.checked, indeterminate: !!gui.indeterminate },
            reset: { visible: true, title: "恢复默认" },
          });

          // 强/标准/弱 分型
          rows.push({
            key: "fr-strong",
            name: "强分型",
            items: [
              { key: "fr-botShape-strong", label: "底分符号" },
              { key: "fr-botColor-strong", label: "底分颜色" },
              { key: "fr-topShape-strong", label: "顶分符号" },
              { key: "fr-topColor-strong", label: "顶分颜色" },
              { key: "fr-fill-strong", label: "填充" },
            ],
            check: { type: "single", checked: !!settingsDraft.fractalForm.styleByStrength?.strong?.enabled },
            reset: { visible: true, title: "恢复默认" },
          });
          rows.push({
            key: "fr-standard",
            name: "标准分型",
            items: [
              { key: "fr-botShape-standard", label: "底分符号" },
              { key: "fr-botColor-standard", label: "底分颜色" },
              { key: "fr-topShape-standard", label: "顶分符号" },
              { key: "fr-topColor-standard", label: "顶分颜色" },
              { key: "fr-fill-standard", label: "填充" },
            ],
            check: { type: "single", checked: !!settingsDraft.fractalForm.styleByStrength?.standard?.enabled },
            reset: { visible: true, title: "恢复默认" },
          });
          rows.push({
            key: "fr-weak",
            name: "弱分型",
            items: [
              { key: "fr-botShape-weak", label: "底分符号" },
              { key: "fr-botColor-weak", label: "底分颜色" },
              { key: "fr-topShape-weak", label: "顶分符号" },
              { key: "fr-topColor-weak", label: "顶分颜色" },
              { key: "fr-fill-weak", label: "填充" },
            ],
            check: { type: "single", checked: !!settingsDraft.fractalForm.styleByStrength?.weak?.enabled },
            reset: { visible: true, title: "恢复默认" },
          });

          // 确认分型
          rows.push({
            key: "fr-confirm",
            name: "确认分型",
            items: [
              { key: "fr-confirm-botShape", label: "底分符号" },
              { key: "fr-confirm-botColor", label: "底分颜色" },
              { key: "fr-confirm-topShape", label: "顶分符号" },
              { key: "fr-confirm-topColor", label: "顶分颜色" },
              { key: "fr-confirm-fill", label: "填充" },
            ],
            check: { type: "single", checked: !!settingsDraft.fractalForm.confirmStyle?.enabled },
            reset: { visible: true, title: "恢复默认" },
          });

          // 简笔
          rows.push({
            key: "pen",
            name: "简笔",
            items: [
              { key: "pen-lineWidth", label: "线宽" },
              { key: "pen-color", label: "颜色" },
              { key: "pen-confirmedStyle", label: "确认线型" },
              { key: "pen-provisionalStyle", label: "预备线型" },
            ],
            check: { type: "single", checked: (settingsDraft.chanForm.pen?.enabled ?? PENS_DEFAULTS.enabled) === true },
            reset: { visible: true, title: "恢复默认" },
          });

          // 线段
          rows.push({
            key: "segment",
            name: "线段",
            items: [
              { key: "seg-lineWidth", label: "线宽" },
              { key: "seg-color", label: "颜色" },
              { key: "seg-lineStyle", label: "线型" },
            ],
            check: { type: "single", checked: !!(settingsDraft.chanForm.segment?.enabled ?? SEGMENT_DEFAULTS.enabled) },
            reset: { visible: true, title: "恢复默认" },
          });

          // 笔中枢
          rows.push({
            key: "penPivot",
            name: "笔中枢",
            items: [
              { key: "pv-lineWidth", label: "线宽" },
              { key: "pv-lineStyle", label: "线型" },
              { key: "pv-upColor", label: "上涨颜色" },
              { key: "pv-downColor", label: "下跌颜色" },
              { key: "pv-alpha", label: "透明度%" },
            ],
            check: { type: "single", checked: !!(settingsDraft.chanForm.penPivot?.enabled ?? true) },
            reset: { visible: true, title: "恢复默认" },
          });

          return rows;
        }

        // —— 事件：行级切换与重置 —— //
        function onRowToggle(row) {
          const key = String(row.key || "");
          // Display 页面
          if (key === "ma-global") {
            onMAGlobalToggle();
            return;
          }
          if (key === "k-original") {
            settingsDraft.kForm.originalEnabled = !settingsDraft.kForm.originalEnabled;
            return;
          }
          if (key === "k-merged") {
            settingsDraft.kForm.mergedEnabled = !settingsDraft.kForm.mergedEnabled;
            return;
          }
          if (key.startsWith("ma-")) {
            const mk = key.slice(3);
            const conf = settingsDraft.maForm[mk];
            if (conf) {
              conf.enabled = !conf.enabled;
              updateMASnapshotFromCurrent();
            }
            return;
          }

          // Chan 页面
          if (key === "fr-global") {
            onGlobalToggleFractal();
            return;
          }
          if (key === "chan-updown") {
            settingsDraft.chanForm.showUpDownMarkers = !settingsDraft.chanForm.showUpDownMarkers;
            return;
          }
          if (key === "fr-strong" || key === "fr-standard" || key === "fr-weak") {
            const lvl = key.split("-")[1];
            const s = settingsDraft.fractalForm.styleByStrength || {};
            const cur = s[lvl] || {};
            s[lvl] = { ...cur, enabled: !cur.enabled };
            settingsDraft.fractalForm.styleByStrength = s;
            const ss = settingsDraft.fractalForm.showStrength || {};
            settingsDraft.fractalForm.showStrength = { ...ss, [lvl]: !!s[lvl].enabled };
            updateSnapshotFromCurrent();
            return;
          }
          if (key === "fr-confirm") {
            const cur = settingsDraft.fractalForm.confirmStyle || {};
            settingsDraft.fractalForm.confirmStyle = { ...cur, enabled: !cur.enabled };
            updateSnapshotFromCurrent();
            return;
          }
          if (key === "pen") {
            const pen = settingsDraft.chanForm.pen || {};
            settingsDraft.chanForm.pen = { ...pen, enabled: !(pen.enabled ?? PENS_DEFAULTS.enabled) };
            return;
          }
          if (key === "segment") {
            const seg = settingsDraft.chanForm.segment || {};
            settingsDraft.chanForm.segment = { ...seg, enabled: !(seg.enabled ?? SEGMENT_DEFAULTS.enabled) };
            return;
          }
          if (key === "penPivot") {
            const pv = settingsDraft.chanForm.penPivot || {};
            settingsDraft.chanForm.penPivot = { ...pv, enabled: !(pv.enabled ?? true) };
          }
        }

        function onRowReset(row) {
          const key = String(row.key || "");
          if (key === "k-original") {
            Object.assign(settingsDraft.kForm, {
              upColor: DEFAULT_KLINE_STYLE.upColor,
              downColor: DEFAULT_KLINE_STYLE.downColor,
              originalFadeUpPercent: DEFAULT_KLINE_STYLE.originalFadeUpPercent,
              originalFadeDownPercent: DEFAULT_KLINE_STYLE.originalFadeDownPercent,
              originalEnabled: DEFAULT_KLINE_STYLE.originalEnabled,
            });
            settingsDraft.adjust = String(DEFAULT_APP_PREFERENCES.adjust || "none");
            return;
          }
          if (key === "k-merged") {
            settingsDraft.kForm.mergedEnabled = DEFAULT_KLINE_STYLE.mergedEnabled;
            settingsDraft.kForm.mergedK = { ...DEFAULT_KLINE_STYLE.mergedK };
            return;
          }
          if (key.startsWith("ma-")) {
            const mk = key.slice(3);
            const def = DEFAULT_MA_CONFIGS[mk];
            if (def) {
              settingsDraft.maForm[mk] = { ...def };
              updateMASnapshotFromCurrent();
            }
            return;
          }
          if (key === "chan-updown") {
            settingsDraft.chanForm.upShape = CHAN_DEFAULTS.upShape;
            settingsDraft.chanForm.upColor = CHAN_DEFAULTS.upColor;
            settingsDraft.chanForm.downShape = CHAN_DEFAULTS.downShape;
            settingsDraft.chanForm.downColor = CHAN_DEFAULTS.downColor;
            settingsDraft.chanForm.anchorPolicy = CHAN_DEFAULTS.anchorPolicy;
            settingsDraft.chanForm.showUpDownMarkers = CHAN_DEFAULTS.showUpDownMarkers;
            return;
          }
          if (key === "fr-global") {
            settingsDraft.fractalForm.minTickCount = FRACTAL_DEFAULTS.minTickCount;
            settingsDraft.fractalForm.minPct = FRACTAL_DEFAULTS.minPct;
            settingsDraft.fractalForm.minCond = FRACTAL_DEFAULTS.minCond;
            const d = JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.styleByStrength));
            d.strong.enabled = true; d.standard.enabled = true; d.weak.enabled = true;
            settingsDraft.fractalForm.styleByStrength = d;
            settingsDraft.fractalForm.showStrength = { strong: true, standard: true, weak: true };
            settingsDraft.fractalForm.confirmStyle = JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.confirmStyle));
            settingsDraft.fractalForm.confirmStyle.enabled = true;
            updateSnapshotFromCurrent();
            return;
          }
          if (key === "fr-strong" || key === "fr-standard" || key === "fr-weak") {
            const lvl = key.split("-")[1];
            const def = JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.styleByStrength[lvl]));
            const s = settingsDraft.fractalForm.styleByStrength || {};
            s[lvl] = def;
            settingsDraft.fractalForm.styleByStrength = s;
            const ss = settingsDraft.fractalForm.showStrength || {};
            settingsDraft.fractalForm.showStrength = { ...ss, [lvl]: true };
            updateSnapshotFromCurrent();
            return;
          }
          if (key === "fr-confirm") {
            const def = JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.confirmStyle));
            def.enabled = true;
            settingsDraft.fractalForm.confirmStyle = def;
            updateSnapshotFromCurrent();
            return;
          }
          if (key === "pen") {
            settingsDraft.chanForm.pen = JSON.parse(JSON.stringify(PENS_DEFAULTS));
            return;
          }
          if (key === "segment") {
            settingsDraft.chanForm.segment = JSON.parse(JSON.stringify(SEGMENT_DEFAULTS));
            return;
          }
          if (key === "penPivot") {
            settingsDraft.chanForm.penPivot = JSON.parse(JSON.stringify(CHAN_PEN_PIVOT_DEFAULTS));
          }
        }

        // —— control 槽：渲染每个 item 的具体控件 —— //
        function renderControl({ row, item }) {
          const k = String(row.key || "");
          const id = String(item.key || "");

          // Display 页面 —— 原始K线
          if (k === "k-original") {
            if (id === "adjust") {
              return h("select", {
                class: "input",
                value: String(settingsDraft.adjust || DEFAULT_APP_PREFERENCES.adjust),
                onChange: (e) => (settingsDraft.adjust = String(e.target.value || "none")),
              }, [
                h("option", { value: "none" }, "不复权"),
                h("option", { value: "qfq" }, "前复权"),
                h("option", { value: "hfq" }, "后复权"),
              ]);
            }
            if (id === "upColor") {
              return h("input", {
                class: "input color",
                type: "color",
                value: settingsDraft.kForm.upColor,
                onInput: (e) => (settingsDraft.kForm.upColor = String(e.target.value)),
              });
            }
            if (id === "upFade") {
              return h("input", {
                class: "input num",
                type: "number", min: 0, max: 100, step: 1,
                value: Number(settingsDraft.kForm.originalFadeUpPercent ?? 100),
                onInput: (e) => {
                  const v = Math.max(0, Math.min(100, Number(e.target.value || 100)));
                  settingsDraft.kForm.originalFadeUpPercent = v;
                },
              });
            }
            if (id === "downColor") {
              return h("input", {
                class: "input color",
                type: "color",
                value: settingsDraft.kForm.downColor,
                onInput: (e) => (settingsDraft.kForm.downColor = String(e.target.value)),
              });
            }
            if (id === "downFade") {
              return h("input", {
                class: "input num",
                type: "number", min: 0, max: 100, step: 1,
                value: Number(settingsDraft.kForm.originalFadeDownPercent ?? 0),
                onInput: (e) => {
                  const v = Math.max(0, Math.min(100, Number(e.target.value || 0)));
                  settingsDraft.kForm.originalFadeDownPercent = v;
                },
              });
            }
          }

          // Display —— 合并K线
          if (k === "k-merged") {
            const MK = settingsDraft.kForm.mergedK || (settingsDraft.kForm.mergedK = { ...DEFAULT_KLINE_STYLE.mergedK });
            if (id === "outlineWidth") {
              return h("input", {
                class: "input num", type: "number", min: 0.1, max: 6, step: 0.1,
                value: Number(MK.outlineWidth ?? 1.2),
                onInput: (e) => (settingsDraft.kForm.mergedK.outlineWidth = Math.max(0.1, Number(e.target.value || 1.2))),
              });
            }
            if (id === "mUpColor") {
              return h("input", {
                class: "input color", type: "color",
                value: MK.upColor, onInput: (e) => (settingsDraft.kForm.mergedK.upColor = String(e.target.value)),
              });
            }
            if (id === "mDownColor") {
              return h("input", {
                class: "input color", type: "color",
                value: MK.downColor, onInput: (e) => (settingsDraft.kForm.mergedK.downColor = String(e.target.value)),
              });
            }
            if (id === "fillFade") {
              return h("input", {
                class: "input num", type: "number", min: 0, max: 100, step: 1,
                value: Number(MK.fillFadePercent ?? 0),
                onInput: (e) => {
                  const v = Math.max(0, Math.min(100, Number(e.target.value || 0)));
                  settingsDraft.kForm.mergedK.fillFadePercent = v;
                },
              });
            }
            if (id === "displayOrder") {
              return h("select", {
                class: "input", value: String(MK.displayOrder || "first"),
                onChange: (e) => (settingsDraft.kForm.mergedK.displayOrder = String(e.target.value || "first")),
              }, [
                h("option", { value: "first" }, "先"),
                h("option", { value: "after" }, "后"),
              ]);
            }
          }

          // Display —— MA 行
          if (k.startsWith("ma-")) {
            const mk = k.slice(3);
            const conf = settingsDraft.maForm[mk] || {};
            if (id === "ma-width") {
              return h("input", {
                class: "input num", type: "number", min: 0.5, max: 4, step: 0.5,
                value: Number(conf.width ?? 1),
                onInput: (e) => (settingsDraft.maForm[mk].width = Number(e.target.value || 1)),
              });
            }
            if (id === "ma-color") {
              return h("input", {
                class: "input color", type: "color",
                value: conf.color,
                onInput: (e) => (settingsDraft.maForm[mk].color = String(e.target.value)),
              });
            }
            if (id === "ma-style") {
              return h("select", {
                class: "input", value: conf.style || "solid",
                onChange: (e) => (settingsDraft.maForm[mk].style = String(e.target.value || "solid")),
              }, [
                h("option", { value: "solid" }, "实线"),
                h("option", { value: "dashed" }, "虚线"),
                h("option", { value: "dotted" }, "点线"),
              ]);
            }
            if (id === "ma-period") {
              return h("input", {
                class: "input num", type: "number", min: 1, step: 1,
                value: Number(conf.period ?? 5),
                onInput: (e) => (settingsDraft.maForm[mk].period = Math.max(1, parseInt(e.target.value || 5, 10))),
              });
            }
          }

          // Chan —— 涨跌标记
          if (k === "chan-updown") {
            if (id === "upShape") {
              return h("select", {
                class: "input",
                value: settingsDraft.chanForm.upShape || CHAN_DEFAULTS.upShape,
                onChange: (e) => (settingsDraft.chanForm.upShape = String(e.target.value)),
              }, (FRACTAL_SHAPES || []).map(opt => h("option", { value: opt.v }, opt.label)));
            }
            if (id === "upColor") {
              return h("input", {
                class: "input color", type: "color",
                value: settingsDraft.chanForm.upColor || CHAN_DEFAULTS.upColor,
                onInput: (e) => (settingsDraft.chanForm.upColor = String(e.target.value)),
              });
            }
            if (id === "downShape") {
              return h("select", {
                class: "input",
                value: settingsDraft.chanForm.downShape || CHAN_DEFAULTS.downShape,
                onChange: (e) => (settingsDraft.chanForm.downShape = String(e.target.value)),
              }, (FRACTAL_SHAPES || []).map(opt => h("option", { value: opt.v }, opt.label)));
            }
            if (id === "downColor") {
              return h("input", {
                class: "input color", type: "color",
                value: settingsDraft.chanForm.downColor || CHAN_DEFAULTS.downColor,
                onInput: (e) => (settingsDraft.chanForm.downColor = String(e.target.value)),
              });
            }
            if (id === "anchorPolicy") {
              return h("select", {
                class: "input",
                value: settingsDraft.chanForm.anchorPolicy || CHAN_DEFAULTS.anchorPolicy,
                onChange: (e) => (settingsDraft.chanForm.anchorPolicy = String(e.target.value)),
              }, [
                h("option", { value: "right" }, "右端"),
                h("option", { value: "extreme" }, "极值"),
              ]);
            }
          }

          // Chan —— 分型判定参数
          if (k === "fr-global") {
            if (id === "fr-minTick") {
              return h("input", {
                class: "input num", type: "number", min: 0, step: 1,
                value: Number(settingsDraft.fractalForm.minTickCount ?? FRACTAL_DEFAULTS.minTickCount),
                onInput: (e) => (settingsDraft.fractalForm.minTickCount = Math.max(0, parseInt(e.target.value || 0, 10))),
              });
            }
            if (id === "fr-minPct") {
              return h("input", {
                class: "input num", type: "number", min: 0, step: 0.01,
                value: Number(settingsDraft.fractalForm.minPct ?? FRACTAL_DEFAULTS.minPct),
                onInput: (e) => (settingsDraft.fractalForm.minPct = Math.max(0, Number(e.target.value || 0))),
              });
            }
            if (id === "fr-minCond") {
              return h("select", {
                class: "input",
                value: String(settingsDraft.fractalForm.minCond || FRACTAL_DEFAULTS.minCond),
                onChange: (e) => (settingsDraft.fractalForm.minCond = String(e.target.value || "or")),
              }, [
                h("option", { value: "or" }, "或"),
                h("option", { value: "and" }, "与"),
              ]);
            }
          }

          // Chan —— 强/标/弱 分型
          const mapLvl = (kk) => kk.split("-")[1];
          if (k === "fr-strong" || k === "fr-standard" || k === "fr-weak") {
            const lvl = mapLvl(k);
            const s = settingsDraft.fractalForm.styleByStrength || {};
            const conf = s[lvl] || {};
            if (id === `fr-botShape-${lvl}`) {
              return h("select", {
                class: "input",
                value: conf.bottomShape,
                onChange: (e) => {
                  const ss = settingsDraft.fractalForm.styleByStrength || {};
                  ss[lvl] = { ...(ss[lvl] || conf), bottomShape: String(e.target.value) };
                  settingsDraft.fractalForm.styleByStrength = ss;
                },
              }, (FRACTAL_SHAPES || []).map(opt => h("option", { value: opt.v }, opt.label)));
            }
            if (id === `fr-botColor-${lvl}`) {
              return h("input", {
                class: "input color", type: "color",
                value: conf.bottomColor,
                onInput: (e) => {
                  const ss = settingsDraft.fractalForm.styleByStrength || {};
                  ss[lvl] = { ...(ss[lvl] || conf), bottomColor: String(e.target.value) };
                  settingsDraft.fractalForm.styleByStrength = ss;
                },
              });
            }
            if (id === `fr-topShape-${lvl}`) {
              return h("select", {
                class: "input",
                value: conf.topShape,
                onChange: (e) => {
                  const ss = settingsDraft.fractalForm.styleByStrength || {};
                  ss[lvl] = { ...(ss[lvl] || conf), topShape: String(e.target.value) };
                  settingsDraft.fractalForm.styleByStrength = ss;
                },
              }, (FRACTAL_SHAPES || []).map(opt => h("option", { value: opt.v }, opt.label)));
            }
            if (id === `fr-topColor-${lvl}`) {
              return h("input", {
                class: "input color", type: "color",
                value: conf.topColor,
                onInput: (e) => {
                  const ss = settingsDraft.fractalForm.styleByStrength || {};
                  ss[lvl] = { ...(ss[lvl] || conf), topColor: String(e.target.value) };
                  settingsDraft.fractalForm.styleByStrength = ss;
                },
              });
            }
            if (id === `fr-fill-${lvl}`) {
              return h("select", {
                class: "input",
                value: conf.fill,
                onChange: (e) => {
                  const ss = settingsDraft.fractalForm.styleByStrength || {};
                  ss[lvl] = { ...(ss[lvl] || conf), fill: String(e.target.value) };
                  settingsDraft.fractalForm.styleByStrength = ss;
                },
              }, (FRACTAL_FILLS || []).map(opt => h("option", { value: opt.v }, opt.label)));
            }
          }

          // Chan —— 确认分型
          if (k === "fr-confirm") {
            const cs = settingsDraft.fractalForm.confirmStyle || {};
            if (id === "fr-confirm-botShape") {
              return h("select", {
                class: "input",
                value: cs.bottomShape,
                onChange: (e) => (settingsDraft.fractalForm.confirmStyle.bottomShape = String(e.target.value)),
              }, (FRACTAL_SHAPES || []).map(opt => h("option", { value: opt.v }, opt.label)));
            }
            if (id === "fr-confirm-botColor") {
              return h("input", {
                class: "input color", type: "color",
                value: cs.bottomColor,
                onInput: (e) => (settingsDraft.fractalForm.confirmStyle.bottomColor = String(e.target.value)),
              });
            }
            if (id === "fr-confirm-topShape") {
              return h("select", {
                class: "input",
                value: cs.topShape,
                onChange: (e) => (settingsDraft.fractalForm.confirmStyle.topShape = String(e.target.value)),
              }, (FRACTAL_SHAPES || []).map(opt => h("option", { value: opt.v }, opt.label)));
            }
            if (id === "fr-confirm-topColor") {
              return h("input", {
                class: "input color", type: "color",
                value: cs.topColor,
                onInput: (e) => (settingsDraft.fractalForm.confirmStyle.topColor = String(e.target.value)),
              });
            }
            if (id === "fr-confirm-fill") {
              return h("select", {
                class: "input",
                value: cs.fill,
                onChange: (e) => (settingsDraft.fractalForm.confirmStyle.fill = String(e.target.value)),
              }, (FRACTAL_FILLS || []).map(opt => h("option", { value: opt.v }, opt.label)));
            }
          }

          // Chan —— 简笔
          if (k === "pen") {
            const pen = settingsDraft.chanForm.pen || {};
            if (id === "pen-lineWidth") {
              return h("input", {
                class: "input num", type: "number", min: 0.5, max: 6, step: 0.5,
                value: Number.isFinite(+pen.lineWidth) ? +pen.lineWidth : PENS_DEFAULTS.lineWidth,
                onInput: (e) => (settingsDraft.chanForm.pen = { ...pen, lineWidth: Math.max(0.5, Math.min(6, Number(e.target.value || PENS_DEFAULTS.lineWidth))) }),
              });
            }
            if (id === "pen-color") {
              return h("input", {
                class: "input color", type: "color",
                value: pen.color || PENS_DEFAULTS.color,
                onInput: (e) => (settingsDraft.chanForm.pen = { ...pen, color: String(e.target.value || PENS_DEFAULTS.color) }),
              });
            }
            if (id === "pen-confirmedStyle") {
              return h("select", {
                class: "input", value: pen.confirmedStyle || PENS_DEFAULTS.confirmedStyle,
                onChange: (e) => (settingsDraft.chanForm.pen = { ...pen, confirmedStyle: String(e.target.value) }),
              }, [
                h("option", { value: "solid" }, "实线"),
                h("option", { value: "dashed" }, "虚线"),
                h("option", { value: "dotted" }, "点线"),
              ]);
            }
            if (id === "pen-provisionalStyle") {
              return h("select", {
                class: "input", value: pen.provisionalStyle || PENS_DEFAULTS.provisionalStyle,
                onChange: (e) => (settingsDraft.chanForm.pen = { ...pen, provisionalStyle: String(e.target.value) }),
              }, [
                h("option", { value: "solid" }, "实线"),
                h("option", { value: "dashed" }, "虚线"),
                h("option", { value: "dotted" }, "点线"),
              ]);
            }
          }

          // Chan —— 线段
          if (k === "segment") {
            const sg = settingsDraft.chanForm.segment || {};
            if (id === "seg-lineWidth") {
              return h("input", {
                class: "input num", type: "number", min: 0.5, max: 6, step: 0.5,
                value: Number.isFinite(+sg.lineWidth) ? +sg.lineWidth : SEGMENT_DEFAULTS.lineWidth,
                onInput: (e) => (settingsDraft.chanForm.segment = { ...sg, lineWidth: Math.max(0.5, Math.min(6, Number(e.target.value || SEGMENT_DEFAULTS.lineWidth))) }),
              });
            }
            if (id === "seg-color") {
              return h("input", {
                class: "input color", type: "color",
                value: sg.color || SEGMENT_DEFAULTS.color,
                onInput: (e) => (settingsDraft.chanForm.segment = { ...sg, color: String(e.target.value || SEGMENT_DEFAULTS.color) }),
              });
            }
            if (id === "seg-lineStyle") {
              return h("select", {
                class: "input", value: sg.lineStyle || SEGMENT_DEFAULTS.lineStyle,
                onChange: (e) => (settingsDraft.chanForm.segment = { ...sg, lineStyle: String(e.target.value) }),
              }, [
                h("option", { value: "solid" }, "实线"),
                h("option", { value: "dashed" }, "虚线"),
                h("option", { value: "dotted" }, "点线"),
              ]);
            }
          }

          // Chan —— 笔中枢
          if (k === "penPivot") {
            const pv = settingsDraft.chanForm.penPivot || {};
            if (id === "pv-lineWidth") {
              return h("input", {
                class: "input num", type: "number", min: 0.5, max: 6, step: 0.1,
                value: Number.isFinite(+pv.lineWidth) ? +pv.lineWidth : CHAN_PEN_PIVOT_DEFAULTS.lineWidth,
                onInput: (e) => (settingsDraft.chanForm.penPivot = { ...pv, lineWidth: Math.max(0.5, Math.min(6, Number(e.target.value || CHAN_PEN_PIVOT_DEFAULTS.lineWidth))) }),
              });
            }
            if (id === "pv-lineStyle") {
              return h("select", {
                class: "input", value: pv.lineStyle || CHAN_PEN_PIVOT_DEFAULTS.lineStyle,
                onChange: (e) => (settingsDraft.chanForm.penPivot = { ...pv, lineStyle: String(e.target.value) }),
              }, [
                h("option", { value: "solid" }, "实线"),
                h("option", { value: "dashed" }, "虚线"),
                h("option", { value: "dotted" }, "点线"),
              ]);
            }
            if (id === "pv-upColor") {
              return h("input", {
                class: "input color", type: "color",
                value: pv.upColor || CHAN_PEN_PIVOT_DEFAULTS.upColor,
                onInput: (e) => (settingsDraft.chanForm.penPivot = { ...pv, upColor: String(e.target.value || CHAN_PEN_PIVOT_DEFAULTS.upColor) }),
              });
            }
            if (id === "pv-downColor") {
              return h("input", {
                class: "input color", type: "color",
                value: pv.downColor || CHAN_PEN_PIVOT_DEFAULTS.downColor,
                onInput: (e) => (settingsDraft.chanForm.penPivot = { ...pv, downColor: String(e.target.value || CHAN_PEN_PIVOT_DEFAULTS.downColor) }),
              });
            }
            if (id === "pv-alpha") {
              return h("input", {
                class: "input num", type: "number", min: 0, max: 100, step: 1,
                value: Number.isFinite(+pv.alphaPercent) ? +pv.alphaPercent : CHAN_PEN_PIVOT_DEFAULTS.alphaPercent,
                onInput: (e) => (settingsDraft.chanForm.penPivot = { ...pv, alphaPercent: Math.max(0, Math.min(100, Number(e.target.value || CHAN_PEN_PIVOT_DEFAULTS.alphaPercent))) }),
              });
            }
          }

          return null;
        }

        // 渲染
        return () => {
          const rows = props.activeTab === "chan" ? rowsChan() : rowsDisplay();
          return h(SettingsGrid, {
            rows,
            itemsPerRow: 5,
            onRowToggle,
            onRowReset,
          }, {
            control: (slotProps) => renderControl(slotProps),
          });
        };
      },
    });

    dialogManager.open({
      title: "行情显示设置",
      contentComponent: MainChartSettingsContent,
      props: {},
      tabs: [
        { key: "display", label: "行情显示" },
        { key: "chan", label: "缠论标记" },
      ],
      activeTab: "chan",
      // 全部恢复默认（统一合并表达式，pen 与其他项一致）
      onResetAll: () => {
        try {
          // 显示设置默认
          settingsDraft.kForm = JSON.parse(JSON.stringify(DEFAULT_KLINE_STYLE));
          settingsDraft.maForm = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS));
          settingsDraft.adjust = String(
            DEFAULT_APP_PREFERENCES.adjust || "none"
          );

          // 缠论设置默认（包含 pen 默认，与其他项统一在同一对象表达式中）
          settingsDraft.chanForm = JSON.parse(
            JSON.stringify({
              ...CHAN_DEFAULTS,
              pen: { ...PENS_DEFAULTS },
              segment: { ...SEGMENT_DEFAULTS },
              penPivot: { ...CHAN_PEN_PIVOT_DEFAULTS },
            })
          );

          // 分型设置默认
          settingsDraft.fractalForm = JSON.parse(
            JSON.stringify(FRACTAL_DEFAULTS)
          );

          // NEW: 触发“全部恢复默认”一次，供内部组件刷新快照
          resetAllTick.value++;
        } catch (e) {
          console.error("MainChartSettings onResetAll error:", e);
        }
      },
      // 保存并关闭（保持原逻辑，无需特别处理 pen）
      onSave: () => {
        try {
          // 数据持久化
          settings.setKlineStyle(settingsDraft.kForm);
          settings.setMaConfigs(settingsDraft.maForm);
          // NEW: penPivot 一并写入
          settings.setChanSettings({ ...(settingsDraft.chanForm || {}) });
          settings.setFractalSettings({ ...settingsDraft.fractalForm });

          const nextAdjust = String(settingsDraft.adjust || "none");
          settings.setAdjust(nextAdjust);

          // 应用到图面：仅 adjust 改变时才强制 reload；否则仅刷新中枢，立即前端重绘
          const needReload = nextAdjust !== prevAdjust;
          hub.execute("Refresh", {});
          if (needReload) {
            vm.reload({ force: true });
          }
          dialogManager.close();
        } catch (e) {
          dialogManager.close();
        }
      },
      onClose: () => dialogManager.close(),
    });
  } catch (e) {}
}

/* 标题与刷新状态 */
const displayHeader = ref({ name: "", code: "", freq: "" });
const displayTitle = computed(() => {
  const n = displayHeader.value.name || "",
    c = displayHeader.value.code || vm.code.value || "",
    f = displayHeader.value.freq || vm.freq.value || "";
  const src = (vm.meta.value?.source || "").trim(),
    srcLabel = src ? `（${src}）` : "";
  const adjText =
    { none: "", qfq: " 前复权", hfq: " 后复权" }[
      String(vm.adjust.value || "none")
    ] || "";
  return n
    ? `${n}（${c}）：${f}${srcLabel}${adjText}`
    : `${c}：${f}${srcLabel}${adjText}`;
});
const showRefreshed = ref(false);
const refreshedAt = ref(null);
const refreshedAtHHMMSS = computed(() => {
  if (!refreshedAt.value) return "";
  const d = refreshedAt.value,
    pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
});

/* 键盘左右键 */
let currentIndex = -1;
function focusWrap() {
  try {
    wrap.value?.focus?.();
  } catch {}
}

/* 缠论/分型/笔/线段/屏障缓存/笔中枢 —— 统一在 recomputeChan 中构建 */
const chanCache = ref({
  reduced: [],
  map: [],
  meta: null,
  fractals: [],
  pens: { confirmed: [], provisional: null, all: [] },
  segments: [], // 新增：元线段缓存
  barriersIndices: [], // NEW: 屏障竖线位置（原始K索引，含左右各一）
  pivots: [], // NEW: 笔中枢
});
function recomputeChan() {
  try {
    const arr = vm.candles.value || [];
    if (!arr.length) {
      chanCache.value = {
        reduced: [],
        map: [],
        meta: null,
        fractals: [],
        pens: { confirmed: [], provisional: null, all: [] },
        segments: [],
        barriersIndices: [],
        pivots: [], // 笔中枢
      };
      return;
    }
    const policy =
      settings.chanSettings.value.anchorPolicy || CHAN_DEFAULTS.anchorPolicy;
    const res = computeInclude(arr, { anchorPolicy: policy });
    const fr = computeFractals(res.reducedBars || [], {
      minTickCount: settings.fractalSettings.value.minTickCount || 0,
      minPct: settings.fractalSettings.value.minPct || 0,
      minCond: String(settings.fractalSettings.value.minCond || "or"),
    });

    // NEW: 计算画笔（承载点间距 gap≥4；同步更新上一预备笔终点在同类更极值时由 useChan 实现）
    const pens = computePens(
      res.reducedBars || [],
      fr || [],
      res.mapOrigToReduced || [],
      { minGapReduced: 4 }
    );

    // 新增：识别元线段（基于确认笔）；位置追加，不改变既有步骤顺序
    const segments = computeSegments(pens.confirmed || []);

    // NEW: 由 reducedBars 中的屏障标记计算竖线位置：gap 两侧紧邻原始K（left=end_idx_orig(prev)，right=start_idx_orig(curr)）
    const barrierIdxList = [];
    const rb = res.reducedBars || [];
    for (let i = 0; i < rb.length; i++) {
      const cur = rb[i];
      if (cur && cur.barrier_after_prev_bool) {
        const prev = i > 0 ? rb[i - 1] : null;
        const left = prev ? prev.end_idx_orig : null;
        const right = cur.start_idx_orig;
        if (Number.isFinite(+left)) barrierIdxList.push(+left);
        if (Number.isFinite(+right)) barrierIdxList.push(+right);
      }
    }

    // NEW: 计算“笔中枢”
    const pivots = computePenPivots(pens.confirmed || []);

    chanCache.value = {
      reduced: res.reducedBars || [],
      map: res.mapOrigToReduced || [],
      meta: res.meta || null,
      fractals: fr || [],
      pens: pens || { confirmed: [], provisional: null, all: [] },
      segments: segments || [],
      barriersIndices: barrierIdxList || [],
      pivots, // 保存“笔中枢”
    };
  } catch {
    chanCache.value = {
      reduced: [],
      map: [],
      meta: null,
      fractals: [],
      pens: { confirmed: [], provisional: null, all: [] },
      segments: [],
      barriersIndices: [],
      pivots: [],
    };
  }
}

/**
 * 覆盖层 series（一次性装配）
 * - 涨跌标记：anchor_idx_orig 作 x
 * - 分型：k2_idx_orig 作 x
 * - 笔/线段：*_idx_orig + *_y_pri
 * - 屏障：在 gap 两侧紧邻原始 K 处绘制竖线（markLine）
 */
function buildOverlaySeriesForOption({ hostW, visCount, markerW }) {
  const out = [];
  const reduced = chanCache.value.reduced || [];
  const fractals = chanCache.value.fractals || [];
  const pens = chanCache.value.pens || {
    confirmed: [],
    provisional: null,
    all: [],
  };
  const segments = chanCache.value.segments || [];
  const barrierIdxList = chanCache.value.barriersIndices || [];
  const pivots = chanCache.value.pivots || []; // NEW: 笔中枢

  // 屏障竖线（优先叠加，z 更高）
  if (barrierIdxList.length) {
    const bl = buildBarrierLines(barrierIdxList);
    out.push(...(bl.series || []));
  }

  // 涨跌标记
  if (settings.chanSettings.value.showUpDownMarkers && reduced.length) {
    // 正常路径由 layers.js 的集中高度控制
    const upDownLayer = buildUpDownMarkers(reduced, {
      chanSettings: settings.chanSettings.value,
      hostWidth: hostW,
      visCount,
      symbolWidthPx: markerW,
    });
    out.push(...(upDownLayer.series || []));
  } else {
    // 占位路径：统一从 index.js 预设取高度与偏移
    const markerHeight = Math.max(
      1,
      Math.round(Number(CHAN_DEFAULTS.markerHeightPx))
    );
    const offsetDownPx = Math.round(
      markerHeight + Number(CHAN_DEFAULTS.markerYOffsetPx)
    );

    out.push(
      {
        type: "scatter",
        id: "CHAN_UP",
        name: "CHAN_UP",
        yAxisIndex: 1,
        data: [],
        symbol: "triangle",
        symbolSize: () => [markerW, markerHeight],
        symbolOffset: [0, offsetDownPx],
        itemStyle: {
          color: CHAN_DEFAULTS.upColor,
          opacity: CHAN_DEFAULTS.opacity,
        },
        tooltip: { show: false },
        z: 2,
        emphasis: { scale: false },
      },
      {
        type: "scatter",
        id: "CHAN_DOWN",
        name: "CHAN_DOWN",
        yAxisIndex: 1,
        data: [],
        symbol: "triangle",
        symbolSize: () => [markerW, markerHeight],
        symbolOffset: [0, offsetDownPx],
        itemStyle: {
          color: CHAN_DEFAULTS.downColor,
          opacity: CHAN_DEFAULTS.opacity,
        },
        tooltip: { show: false },
        z: 2,
        emphasis: { scale: false },
      }
    );
  }

  // 分型标记
  const frEnabled = (settings.fractalSettings.value?.enabled ?? true) === true;
  if (frEnabled && reduced.length && fractals.length) {
    const frLayer = buildFractalMarkers(reduced, fractals, {
      fractalSettings: settings.fractalSettings.value,
      hostWidth: hostW,
      visCount,
      symbolWidthPx: markerW,
    });
    out.push(...(frLayer.series || []));
  } else {
    const FR_IDS = [
      "FR_TOP_STRONG",
      "FR_TOP_STANDARD",
      "FR_TOP_WEAK",
      "FR_BOT_STRONG",
      "FR_BOT_STANDARD",
      "FR_BOT_WEAK",
      "FR_TOP_CONFIRM",
      "FR_BOT_CONFIRM",
      "FR_CONFIRM_LINKS",
    ];
    for (const id of FR_IDS) {
      out.push({ id, name: id, type: "scatter", yAxisIndex: 0, data: [] });
    }
  }

  // 画笔折线（传入屏障索引，确保在断点处分段；每段为独立 series）
  const penEnabled =
    (settings.chanSettings.value?.pen?.enabled ?? PENS_DEFAULTS.enabled) ===
    true;
  if (
    penEnabled &&
    reduced.length &&
    (pens.confirmed.length || pens.provisional)
  ) {
    const penLayer = buildPenLines(pens, { barrierIdxList });
    out.push(...(penLayer.series || []));
  }

  // 元线段（每段独立 series；传入屏障索引以防跨断点）
  if ((segments || []).length) {
    const segLayer = buildSegmentLines(segments, { barrierIdxList });
    out.push(...(segLayer.series || []));
  }

  // NEW: 笔中枢（矩形框，静态框线）
  if ((pivots || []).length) {
    const pvLayer = buildPenPivotAreas(pivots, { barrierIdxList });
    out.push(...(pvLayer.series || []));
  }

  return out;
}

/* onDataZoom：ECharts-first 会话锁 + idle-commit（不抢权、会后承接） */
let dzIdleTimer = null;
const dzIdleDelayMs = 100; // 建议 100–200ms，避免频繁承接

// NEW: 拖移会话鼠标状态（仅鼠标未抬起时不结束交互）
let isMouseDown = false;
let zrMouseDownHandler = () => { isMouseDown = true; };
let zrMouseUpHandler = () => { isMouseDown = false; try { renderHub.endInteraction("main"); } catch {} };
let winMouseUpHandler = () => { isMouseDown = false; try { renderHub.endInteraction("main"); } catch {} };

/* onDataZoom：ECharts-first 会话锁 + idle-commit（不抢权、会后承接） */
function onDataZoom(params) {
  try {
    const info = (params && params.batch && params.batch[0]) || params || {};
    const len = (vm.candles.value || []).length;
    if (!len) return;

    // 2) 提取索引区间（优先索引，其次百分比）
    let sIdx, eIdx;
    if (
      typeof info.startValue !== "undefined" &&
      typeof info.endValue !== "undefined"
    ) {
      sIdx = Number(info.startValue);
      eIdx = Number(info.endValue);
    } else if (typeof info.start === "number" && typeof info.end === "number") {
      const maxIdx = len - 1;
      sIdx = Math.round((info.start / 100) * maxIdx);
      eIdx = Math.round((info.end / 100) * maxIdx);
    } else {
      return;
    }
    if (!Number.isFinite(sIdx) || !Number.isFinite(eIdx)) return;
    if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];
    sIdx = Math.max(0, sIdx);
    eIdx = Math.min(len - 1, eIdx);

    // NEW: 交互期间即时更新主窗顶栏预览（不改中枢与范围）
    const arr = vm.candles.value || [];
    previewStartStr.value = arr[sIdx]?.t || "";
    previewEndStr.value = arr[eIdx]?.t || "";
    previewBarsCount.value = Math.max(1, eIdx - sIdx + 1);
    // NEW: 广播给主窗（若交互源是副窗/指标窗）
    try {
      window.dispatchEvent(
        new CustomEvent("chan:preview-range", {
          detail: {
            code: vm.code.value,
            freq: vm.freq.value,
            sIdx,
            eIdx,
          },
        })
      );
    } catch {}

    // 会话锁：交互开始
    renderHub.beginInteraction("main");

    // 清空上一次 idle 计时器，启动新的（最后一次范围为准）
    if (dzIdleTimer) {
      clearTimeout(dzIdleTimer);
      dzIdleTimer = null;
    }
    dzIdleTimer = setTimeout(() => {
      try {
        // 交互结束：会后承接一次
        const bars_new = Math.max(1, eIdx - sIdx + 1);
        const tsArr = (vm.candles.value || []).map((d) => Date.parse(d.t));
        const anchorTs = Number.isFinite(tsArr[eIdx])
          ? tsArr[eIdx]
          : hub.getState().rightTs;

        const st = hub.getState();
        const changedBars = bars_new !== Math.max(1, Number(st.barsCount || 1));
        const changedEIdx =
          Number.isFinite(tsArr[eIdx]) && tsArr[eIdx] !== st.rightTs;

        if (changedBars || changedEIdx) {
          // 会后承接：仅这一次 hub.execute，触发持久化与锚定
          if (changedBars && changedEIdx) {
            hub.execute("ScrollZoom", {
              nextBars: bars_new,
              nextRightTs: anchorTs,
            });
          } else if (changedBars) {
            hub.execute("SetBarsManual", { nextBars: bars_new });
          } else if (changedEIdx) {
            hub.execute("Pan", { nextRightTs: anchorTs });
          }
        }
      } finally {
        // NEW: 仅在鼠标已抬起时才结束交互；鼠标未抬起保持拖移会话
        if (!isMouseDown) {
        renderHub.endInteraction("main");
        }
      }
    }, dzIdleDelayMs);
  } catch {}
}

/* 一次性装配渲染（交互期间不做 notMerge 重绘） */
function doSinglePassRender(snapshot) {
  try {
    if (!chart || !snapshot) return;
    const mySeq = ++renderSeq;

    // 先计算缠论（含分型/画笔/线段/屏障）
    recomputeChan();
    const reduced = chanCache.value.reduced || [];
    const mapReduced = chanCache.value.map || [];

    const initialRange = {
      startValue: snapshot.main.range.startValue,
      endValue: snapshot.main.range.endValue,
    };
    const tipPositioner = renderHub.getTipPositioner();

    // 标记存在则给主图内部挤空间（完全由 CHAN_DEFAULTS 决定几何与避让量）
    const anyMarkers =
      (settings.chanSettings.value?.showUpDownMarkers ?? true) === true &&
      reduced.length > 0;

    // 唯一数据源：高度与偏移取自 index.js 的 CHAN_DEFAULTS
    const markerHeight = Math.max(
      1,
      Math.round(Number(CHAN_DEFAULTS.markerHeightPx))
    );
    const markerYOffset = Math.max(
      0,
      Math.round(Number(CHAN_DEFAULTS.markerYOffsetPx))
    );
    const offsetDownPx = Math.round(markerHeight + markerYOffset);

    // 主图底部空白与横轴标签避让量：与符号向下偏移量一致，避免遮挡
    const mainBottomExtraPx = anyMarkers ? offsetDownPx : 0;
    const xAxisLabelMargin = anyMarkers ? offsetDownPx + 12 : 12;

    const rebuiltMainOption = buildMainChartOption(
      {
        candles: vm.candles.value || [],
        indicators: vm.indicators.value || {},
        chartType: vm.chartType.value || "kline",
        maConfigs: settings.maConfigs.value,
        freq: vm.freq.value || "1d",
        klineStyle: settings.klineStyle.value,
        adjust: vm.adjust.value || "none",
        reducedBars: reduced,
        mapOrigToReduced: mapReduced,
      },
      {
        initialRange,
        tooltipPositioner: tipPositioner,
        mainAxisLabelSpacePx: 28,
        xAxisLabelMargin,
        mainBottomExtraPx,
        isHovered: snapshot.main.isHovered, // 传入悬浮状态
      }
    );

    const bars = Math.max(1, snapshot.core?.barsCount || 1);
    const hostW = host.value ? host.value.clientWidth : 800;
    const markerW = snapshot.core?.markerWidthPx || 8;

    // 修改：传入 sIdx/eIdx，供覆盖层“笔中枢框线”静态绘制使用
    const overlaySeries = buildOverlaySeriesForOption({
      hostW,
      visCount: bars,
      markerW,
    });

    // 交互期间：跳过 notMerge 重绘（避免抢权）；可按需做轻量样式 patch（此处直接跳过）
    if (renderHub.isInteracting()) {
      // 选择性样式 patch示例（如需）：chart.setOption({ /* 仅样式 */ }, { notMerge:false, silent:true, lazyUpdate:true });
      return;
    }

    // 常规（非交互期）：一次性装配渲染
    const finalOption = {
      ...rebuiltMainOption,
      series: [...(rebuiltMainOption.series || []), ...overlaySeries],
    };

    // 程序化 dataZoom 签名守护（仅用于避免回环；逻辑保持不变）
    const guardSig = `${initialRange.startValue}:${initialRange.endValue}`;
    progZoomGuard.active = true;
    progZoomGuard.sig = guardSig;
    progZoomGuard.ts = Date.now();
    scheduleSetOption(finalOption, {
      notMerge: true,
      lazyUpdate: false,
      silent: true,
    });
    lastAppliedRange = { s: initialRange.startValue, e: initialRange.endValue };
    setTimeout(() => {
      progZoomGuard.active = false;
    }, 300);

    // 顶栏预览文案（保持不变）
    const sIdx = initialRange.startValue;
    const eIdx = initialRange.endValue;
    const arr = vm.candles.value || [];
    previewStartStr.value = arr[sIdx]?.t || "";
    previewEndStr.value = arr[eIdx]?.t || "";
    previewBarsCount.value = Math.max(1, eIdx - sIdx + 1);
  } catch {}
}
const previewStartStr = ref("");
const previewEndStr = ref("");
const previewBarsCount = ref(0);

// >>> 改：formattedStart/End 调用统一 fmtShort（传入当前 freq），保持行为一致 <<<
const formattedStart = computed(() => {
  return (
    (previewStartStr.value && fmtShort(previewStartStr.value)) ||
    fmtShort(vm.visibleRange.value.startStr) ||
    "-"
  );
});
const formattedEnd = computed(() => {
  return (
    (previewEndStr.value && fmtShort(previewEndStr.value, vm.freq.value)) ||
    fmtShort(vm.visibleRange.value.endStr, vm.freq.value) ||
    "-"
  );
});
const topBarsCount = computed(() => {
  return Number(previewBarsCount.value || vm.meta.value?.view_rows || 0);
});

/* 预设点击与滚轮缩放（保持原逻辑） */
function onClickPreset(preset) {
  try {
    const pkey = String(preset || "ALL");
    const st = hub.getState();
    hub.execute("ChangeWidthPreset", { presetKey: pkey, allRows: st.allRows });
  } catch {}
}

function onPreviewRange(ev) {
  try {
    const d = ev?.detail || {};
    // 仅在当前 code|freq 匹配时更新文案
    if (
      String(d.code || "") !== String(vm.code.value || "") ||
      String(d.freq || "") !== String(vm.freq.value || "")
    ) {
      return;
    }
    const arr = vm.candles.value || [];
    const s = Math.max(0, Math.min(arr.length - 1, Number(d.sIdx)));
    const e = Math.max(0, Math.min(arr.length - 1, Number(d.eIdx)));
    previewStartStr.value = arr[s]?.t || "";
    previewEndStr.value = arr[e]?.t || "";
    previewBarsCount.value = Math.max(1, e - s + 1);
    // 更新“原位输入框”的显示（基于预览值）
    fillInlineFieldsFromEffective();
  } catch {}
}

/* 生命周期 */
onMounted(() => {
  const el = host.value;
  if (!el) return;
  chart = echarts.init(el, null, {
    renderer: "canvas",
    width: el.clientWidth,
    height: el.clientHeight,
  });
  chart.group = "ct-sync";
  try {
    echarts.connect("ct-sync");
  } catch {}

  // NEW: 监听画布与窗口鼠标抬起/按下，维护拖移会话不被超时中断
  try {
    const zr = chart.getZr();
    zr.on("mousedown", zrMouseDownHandler);
    zr.on("mouseup", zrMouseUpHandler);
    window.addEventListener("mouseup", winMouseUpHandler);
  } catch {}

  chart.on("updateAxisPointer", (params) => {
    try {
      const len = (vm.candles.value || []).length;
      if (!len) return;

      // MOD: 移除所有 setOption 逻辑，仅保留 lastFocusTs 更新
      let idx = -1;
      const sd = Array.isArray(params?.seriesData)
        ? params.seriesData.find((x) => Number.isFinite(x?.dataIndex))
        : null;
      if (sd && Number.isFinite(sd.dataIndex)) {
        idx = sd.dataIndex;
      } else {
        const axisInfo = (params?.axesInfo && params.axesInfo[0]) || null;
        const v = axisInfo?.value;
        if (Number.isFinite(v)) {
          idx = Math.max(0, Math.min(len - 1, Number(v)));
        } else if (typeof v === "string" && v) {
          const dates = (vm.candles.value || []).map((d) => d.t);
          idx = dates.indexOf(v);
        }
      }
      if (idx < 0 || idx >= len) return;
      const tsVal = vm.candles.value[idx]?.t
        ? Date.parse(vm.candles.value[idx].t)
        : null;
      if (Number.isFinite(tsVal)) {
        settings.setLastFocusTs(vm.code.value, vm.freq.value, tsVal);
      }
    } catch {}
  });

  // 绑定 dataZoom：含“程序化守护 + 有效变化判定”
  chart.on("dataZoom", onDataZoom); // 会话锁 + idle-commit，会后承接到中枢

  // NEW: 订阅全局预览事件（来自副窗/指标窗的 dataZoom）
  try {
    window.addEventListener("chan:preview-range", onPreviewRange);
  } catch {}

  try {
    ro = new ResizeObserver(() => {
      safeResize();
    });
    ro.observe(el);
  } catch {}
  requestAnimationFrame(() => {
    safeResize();
  });

  // —— 订阅 useViewRenderHub：移到 chart.init 完成后（必要调序��� —— //
  // 说明：避免首帧快照在 chart 未初始化时被丢弃，导致不渲染。
  unsubId = renderHub.onRender((snapshot) => {
    doSinglePassRender(snapshot);
  });

  // 初始化“原位输入”的显示
  fillInlineFieldsFromEffective();
});

onBeforeUnmount(() => {
  if (unsubId != null) {
    renderHub.offRender(unsubId);
    unsubId = null;
  }
  // NEW: 解除订阅
  try {
    window.removeEventListener("chan:preview-range", onPreviewRange);
  } catch {}

  renderHub.endInteraction("main");
  try {
    ro && ro.disconnect();
  } catch {}
  ro = null;
  try {
    chart && chart.dispose();
  } catch {}
  chart = null;
  // ADD-BEGIN [组件卸载时取消权威订阅]
  try {
    hub.offChange(hubSubForInline);
  } catch {}
  // NEW: 解除鼠标事件监听
  try {
    const zr = chart && chart.getZr ? chart.getZr() : null;
    zr && zr.off && zr.off("mousedown", zrMouseDownHandler);
    zr && zr.off && zr.off("mouseup", zrMouseUpHandler);
    window.removeEventListener("mouseup", winMouseUpHandler);
  } catch {}
});

/* 标题/刷新徽标更新 */
watch(
  () => vm.meta.value,
  () => {
    updateHeaderFromCurrent();
    refreshedAt.value = new Date();
    showRefreshed.value = true;
    setTimeout(() => {
      showRefreshed.value = false;
    }, 2000);
    // 元信息更新后，同步一次“原位输入”的显示
    fillInlineFieldsFromEffective();
  },
  { deep: true }
);

function updateHeaderFromCurrent() {
  const sym = (vm.meta.value?.symbol || vm.code.value || "").trim();
  const frq = String(vm.meta.value?.freq || vm.freq.value || "").trim();
  let name = "";
  try {
    name = findBySymbol(sym)?.name?.trim() || "";
  } catch {}
  displayHeader.value = { name, code: sym, freq: frq };
}

/* 原位输入：起止日期/时间与 Bars */
const isMinuteFreq = computed(() => /m$/.test(String(vm.freq.value || "")));

// 原位输入的字段（起/止）
const startFields = reactive({ Y: "", M: "", D: "", h: "", m: "" });
const endFields = reactive({ Y: "", M: "", D: "", h: "", m: "" });

// Bars 原位输入
const barsStr = ref("");

// 权威订阅：任何渠道变更 bars/rightTs 后，起止与 Bars 立即刷新显示
const hubSubForInline = hub.onChange((st) => {
  syncFromHub(st);
});

function syncFromHub(st) {
  try {
    const arr = vm.candles.value || [];
    const len = arr.length;
    if (!len) return;
    // 以 hub.rightTs 定位 eIdx；若为空退到最右
    let eIdx = len - 1;
    if (Number.isFinite(+st.rightTs)) {
      const rt = +st.rightTs;
      for (let i = len - 1; i >= 0; i--) {
        const t = Date.parse(arr[i].t);
        if (Number.isFinite(t) && t <= rt) {
          eIdx = i;
          break;
        }
      }
    }
    // 以 hub.barsCount 推 sIdx（左端触底补齐）
    const bars = Math.max(1, Number(st.barsCount || 1));
    let sIdx = Math.max(0, eIdx - bars + 1);
    if (sIdx === 0 && eIdx - sIdx + 1 < bars) {
      eIdx = Math.min(len - 1, bars - 1);
    }
    // 更新预览（驱动现有显示链路）
    previewStartStr.value = arr[sIdx]?.t || "";
    previewEndStr.value = arr[eIdx]?.t || "";
    previewBarsCount.value = Math.max(1, eIdx - sIdx + 1);
    // 同步输入框与 Bars 文案
    fillInlineFieldsFromEffective();
    barsStr.value = String(Math.max(1, Number(st.barsCount || 1)));
  } catch {}
}

// 从“当前有效显示（预览优先，其次 vm.visibleRange）”填充各输入框
function fillInlineFieldsFromEffective() {
  try {
    const startIso =
      (previewStartStr.value && previewStartStr.value) ||
      vm.visibleRange.value.startStr ||
      "";
    const endIso =
      (previewEndStr.value && previewEndStr.value) ||
      vm.visibleRange.value.endStr ||
      "";
    if (!startIso || !endIso) return;
    const ds = new Date(startIso);
    const de = new Date(endIso);
    if (Number.isNaN(ds.getTime()) || Number.isNaN(de.getTime())) return;

    // 日族：仅年月日
    startFields.Y = String(ds.getFullYear());
    startFields.M = pad2(ds.getMonth() + 1);
    startFields.D = pad2(ds.getDate());

    endFields.Y = String(de.getFullYear());
    endFields.M = pad2(de.getMonth() + 1);
    endFields.D = pad2(de.getDate());

    // 分钟族：附加时分
    if (isMinuteFreq.value) {
      startFields.h = pad2(ds.getHours());
      startFields.m = pad2(ds.getMinutes());
      endFields.h = pad2(de.getHours());
      endFields.m = pad2(de.getMinutes());
    } else {
      startFields.h = "";
      startFields.m = "";
      endFields.h = "";
      endFields.m = "";
    }

    // Bars 输入框显示（以当前可见 view_rows）
    barsStr.value = String(
      Math.max(
        1,
        Number(previewBarsCount.value || vm.meta.value?.view_rows || 0)
      )
    );
  } catch {}
}

// ADD-BEGIN [两位数输入与滚轮仅改值（阻止页面滚动）]
// 说明：月/日/时/分始终显示两位；滚轮增减值仅改当前输入，不滚动页面。
function onTwoDigitInput(group, key, ev, min, max) {
  try {
    const raw = String(ev?.target?.value ?? "");
    const n = parseInt(raw.replace(/[^\d]/g, ""), 10);
    if (Number.isNaN(n)) return;
    const v = Math.max(min, Math.min(max, n));
    const pad2v = pad2(v); // >>> 改：使用统一 pad2 <<<
    if (group === "start") {
      startFields[key] = pad2v;
    } else {
      endFields[key] = pad2v;
    }
  } catch {}
}

function onWheelAdjust(group, key, e, min, max) {
  try {
    const tgt = group === "start" ? startFields : endFields;
    const curr = parseInt(String(tgt[key] || "0"), 10);
    const delta = e.deltaY < 0 ? +1 : -1;
    let next = Number.isFinite(curr) ? curr + delta : delta > 0 ? min : max;
    next = Math.max(min, Math.min(max, next));
    if (key === "Y") {
      tgt[key] = String(next);
    } else {
      tgt[key] = String(next).padStart(2, "0");
    }
  } catch {}
}

function onBarsWheel(e) {
  const curr = parseInt(String(barsStr.value || "1"), 10);
  const delta = e.deltaY < 0 ? +1 : -1;
  let next = Number.isFinite(curr) ? curr + delta : 1;
  next = Math.max(1, next);
  barsStr.value = String(next);
}

// 将“日族输入”应用为数据窗口（失焦触发）
function applyInlineRangeDaily() {
  try {
    const ys = parseInt(startFields.Y, 10),
      ms = parseInt(startFields.M, 10),
      ds = parseInt(startFields.D, 10);
    const ye = parseInt(endFields.Y, 10),
      me = parseInt(endFields.M, 10),
      de = parseInt(endFields.D, 10);
    if (!([ys, ms, ds, ye, me, de].every(Number.isFinite))) return;

    // 构造 YYYY-MM-DD 文本
    const toYMD = (y, m, d) =>
      `${String(y).padStart(4, "0")}-${pad2(m)}-${pad2(d)}`;

    const sY = toYMD(ys, ms, ds);
    const eY = toYMD(ye, me, de);

    // 从 ALL candles 查找索引（与原 applyManualRange 的逻辑一致）
    const arr = vm.candles.value || [];
    if (!arr.length) return;

    let sIdx = -1,
      eIdx = -1;
    for (let i = 0; i < arr.length; i++) {
      const ymd = String(arr[i].t || "").slice(0, 10);
      if (sIdx < 0 && ymd >= sY) sIdx = i;
      if (ymd <= eY) eIdx = i;
    }
    if (sIdx < 0) sIdx = 0;
    if (eIdx < 0) eIdx = arr.length - 1;
    if (sIdx > eIdx) {
      const t = sIdx;
      sIdx = eIdx;
      eIdx = t;
    }

    const nextBars = Math.max(1, eIdx - sIdx + 1);
    const anchorTs = Date.parse(arr[eIdx]?.t || "");
    if (!Number.isFinite(anchorTs)) return;

    hub.execute("SetDatesManual", { nextBars, nextRightTs: anchorTs });
  } catch {}
}

// 将“分钟族输入”应用为数据窗口（失焦触发）
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

    if (!([ys, ms, ds, hs, mins, ye, me, de, he, mine].every(Number.isFinite)))
      return;

    // 构造本地时间的 Date（浏览器本地时区）；与 ECharts/前端解析保持一致
    const startDt = new Date(ys, ms - 1, ds, hs, mins, 0, 0);
    const endDt = new Date(ye, me - 1, de, he, mine, 0, 0);
    const msStart = startDt.getTime();
    const msEnd = endDt.getTime();
    if (!Number.isFinite(msStart) || !Number.isFinite(msEnd)) return;

    const arr = vm.candles.value || [];
    if (!arr.length) return;

    const tsArr = arr.map((d) => Date.parse(d.t));
    let sIdx = -1,
      eIdx = -1;
    for (let i = 0; i < tsArr.length; i++) {
      const t = tsArr[i];
      if (!Number.isFinite(t)) continue;
      if (sIdx < 0 && t >= msStart) sIdx = i;
      if (t <= msEnd) eIdx = i;
    }
    if (sIdx < 0) sIdx = 0;
    if (eIdx < 0) eIdx = tsArr.length - 1;
    if (sIdx > eIdx) {
      const t = sIdx;
      sIdx = eIdx;
      eIdx = t;
    }

    const nextBars = Math.max(1, eIdx - sIdx + 1);
    const anchorTs = tsArr[eIdx];
    if (!Number.isFinite(anchorTs)) return;

    hub.execute("SetDatesManual", { nextBars, nextRightTs: anchorTs });
  } catch {}
}

// Bars 原位输入（失焦应用，行为与原高级面板一致）
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
