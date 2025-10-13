<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\MainChartPanel.vue -->
<!-- 说明：主图组件（接入“上游统一渲染中枢 useViewRenderHub” · 一次订阅一次渲染）
     本次仅适配 useChan 输出的新键；覆盖层 series 的构造保持原方法与时序，
     仅在 recomputeChan() 与 buildOverlaySeriesForOption() 内消费新键，不改变其余流程/顺序。
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
} from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import {
  computeInclude,
  computeFractals,
  computePens,
  computeSegments,
} from "@/composables/useChan"; // 新增：computeSegments
import { vSelectAll } from "@/utils/inputBehaviors";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import {
  buildUpDownMarkers,
  buildFractalMarkers,
  buildPenLines,
  buildSegmentLines,
  buildBarrierLines, // NEW: 屏障竖线
} from "@/charts/chan/layers"; // 新增：buildSegmentLines

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

/* 读取当前 dataZoom 范围（保持原逻辑） */
function getCurrentZoomIndexRange() {
  try {
    if (!chart) return null;
    const opt = chart.getOption?.();
    const dz = Array.isArray(opt?.dataZoom) ? opt.dataZoom : [];
    if (!dz.length) return null;
    const z = dz.find(
      (x) =>
        typeof x.startValue !== "undefined" && typeof x.endValue !== "undefined"
    );
    const len = (vm.candles.value || []).length;
    if (z && len > 0) {
      const sIdx = Math.max(0, Math.min(len - 1, Number(z.startValue)));
      const eIdx = Math.max(0, Math.min(len - 1, Number(z.endValue)));
      return { sIdx: Math.min(sIdx, eIdx), eIdx: Math.max(sIdx, eIdx) };
    }
  } catch {}
  return null;
}

/* 设置弹窗（草稿加载 + pen 合并表达式统一） */
const settingsDraft = reactive({
  kForm: { ...DEFAULT_KLINE_STYLE },
  maForm: {},
  chanForm: { ...CHAN_DEFAULTS },
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
        pen: {
          ...PENS_DEFAULTS,
          ...((settings.chanSettings.value || {}).pen || {}),
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
        const nameCell = (text) => h("div", { class: "std-name" }, text);
        const itemCell = (label, node) =>
          h("div", { class: "std-item" }, [
            h("div", { class: "std-item-label" }, label),
            h("div", { class: "std-item-input" }, [node]),
          ]);
        const simpleCheckCell = (checked, onChange) =>
          h("div", { class: "std-check" }, [
            h("input", {
              type: "checkbox",
              checked,
              onChange,
              // —— 关键修复：普通复选框必须显式清除 indeterminate —— //
              onVnodeMounted(vnode) {
                try {
                  if (vnode?.el) vnode.el.indeterminate = false;
                } catch {}
              },
              onVnodeUpdated(vnode) {
                try {
                  if (vnode?.el) vnode.el.indeterminate = false;
                } catch {}
              },
            }),
          ]);
        // tri-state checkbox：通过 vnode 钩子设置 indeterminate
        function triCheckCell({ checked, indeterminate, onToggle }) {
          return h("div", { class: "std-check" }, [
            h("input", {
              type: "checkbox",
              checked,
              onChange: onToggle,
              onVnodeMounted(vnode) {
                try {
                  vnode.el && (vnode.el.indeterminate = !!indeterminate);
                } catch {}
              },
              onVnodeUpdated(vnode) {
                try {
                  vnode.el && (vnode.el.indeterminate = !!indeterminate);
                } catch {}
              },
            }),
          ]);
        }
        const resetBtn = (onClick) =>
          h("div", { class: "std-reset" }, [
            h("button", {
              class: "btn icon",
              title: "恢复默认",
              type: "button",
              onClick,
            }),
          ]);

        // —— 分型总开关快照与循环逻辑（仅针对四项 enabled） —— //
        const ff = settingsDraft.fractalForm;
        const lastManualSnapshot = ref(getCurrentFractalCombination(ff)); // 只在四项 enabled 改变时更新
        const globalCycleIndex = ref(0); // 总开关循环指针

        // —— 快照更新抑制（分型/均线总控共用） —— //
        const snapshotSuppressKeys = new Set();
        function withSnapshotSuppressed(key, fn) {
          try {
            if (key) snapshotSuppressKeys.add(String(key));
            if (typeof fn === "function") fn();
          } finally {
            if (key) snapshotSuppressKeys.delete(String(key));
          }
        }
        function shouldUpdateSnapshot() {
          return snapshotSuppressKeys.size === 0;
        }

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
          // showStrength 与 enabled 同步（避免与渲染层不一致）
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
          // 若快照为“全开/全关”，仅两态；否则三态
          const snap = lastManualSnapshot.value;
          if (isAllOn(snap) || isAllOff(snap)) {
            return ["allOn", "allOff"];
          }
          return ["allOn", "allOff", "snapshot"];
        }
        function applyGlobalState(ff, stateKey) {
          if (stateKey === "allOn") {
            setCombination(ff, {
              strong: true,
              standard: true,
              weak: true,
              confirm: true,
            });
            return;
          }
          if (stateKey === "allOff") {
            setCombination(ff, {
              strong: false,
              standard: false,
              weak: false,
              confirm: false,
            });
            return;
          }
          if (stateKey === "snapshot") {
            setCombination(ff, { ...lastManualSnapshot.value });
            return;
          }
        }
        function globalToggleUi(ff) {
          const cur = getCurrentFractalCombination(ff);
          return {
            checked: isAllOn(cur),
            indeterminate: !isAllOn(cur) && !isAllOff(cur),
          };
        }
        function onGlobalToggle(ff) {
          const states = statesForGlobalToggle();
          const stateKey = states[globalCycleIndex.value % states.length];
          // —— 总控开关批量改变时抑制快照更新 —— //
          withSnapshotSuppressed("fractal-global", () =>
            applyGlobalState(ff, stateKey)
          );
          // 总控点击不更新快照；用于“恢复快照”
          globalCycleIndex.value = (globalCycleIndex.value + 1) % states.length;
        }
        function updateSnapshotFromCurrent() {
          // —— 仅在未抑制时更新快照（各分项直接点击触发） —— //
          if (!shouldUpdateSnapshot()) return;
          lastManualSnapshot.value = getCurrentFractalCombination(
            settingsDraft.fractalForm
          );
          globalCycleIndex.value = 0; // 重置循环起点
        }

        // —— 均线总控三态 + 快照逻辑（与分型总控一致化；快照持久于组件会话，不随 render 重置） —— //
        function getMAKeys() {
          return Object.keys(settingsDraft.maForm || {});
        }
        function getCurrentMACombination() {
          const combo = {};
          for (const k of getMAKeys()) {
            combo[k] = !!settingsDraft.maForm?.[k]?.enabled;
          }
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
          if (isAllMAOn(snap) || isAllMAOff(snap)) {
            return ["allOn", "allOff"];
          }
          return ["allOn", "allOff", "snapshot"];
        }
        function applyMAGlobalState(stateKey) {
          const ks = getMAKeys();
          if (!ks.length) return;
          if (stateKey === "allOn") {
            for (const k of ks) {
              if (!settingsDraft.maForm[k]) settingsDraft.maForm[k] = {};
              // 仅修改属性，不替换对象引用（与分型总控一致）
              settingsDraft.maForm[k].enabled = true;
            }
            return;
          }
          if (stateKey === "allOff") {
            for (const k of ks) {
              if (!settingsDraft.maForm[k]) settingsDraft.maForm[k] = {};
              settingsDraft.maForm[k].enabled = false;
            }
            return;
          }
          if (stateKey === "snapshot") {
            const snap = maLastManualSnapshot.value || {};
            for (const k of ks) {
              if (!settingsDraft.maForm[k]) settingsDraft.maForm[k] = {};
              settingsDraft.maForm[k].enabled = !!snap[k];
            }
            return;
          }
        }
        function maGlobalUi() {
          const cur = getCurrentMACombination();
          return {
            checked: isAllMAOn(cur),
            indeterminate: !isAllMAOn(cur) && !isAllMAOff(cur),
          };
        }
        function onMAGlobalToggle() {
          const states = maStatesForGlobalToggle();
          const key = states[maGlobalCycleIndex.value % states.length];
          // 均线总控批量改变时抑制快照更新（防止 render 导致快照被“隐式重置”）
          withSnapshotSuppressed("ma-global", () => applyMAGlobalState(key));
          // 总控点击不更新快照（用于“恢复快照”）
          maGlobalCycleIndex.value =
            (maGlobalCycleIndex.value + 1) % states.length;
        }
        function updateMASnapshotFromCurrent() {
          // 仅在非总控路径时更新快照（只记录各 MA 勾选状态）
          if (!shouldUpdateSnapshot()) return;
          maLastManualSnapshot.value = getCurrentMACombination();
          maGlobalCycleIndex.value = 0;
        }

        // NEW: 监听“全部恢复默认”计数器，统一刷新分型与均线快照（并重置循环指针）
        watch(resetAllTick, () => {
          try {
            // 分型快照刷新
            lastManualSnapshot.value = getCurrentFractalCombination(
              settingsDraft.fractalForm
            );
            globalCycleIndex.value = 0;
            // 均线快照刷新
            maLastManualSnapshot.value = getCurrentMACombination();
            maGlobalCycleIndex.value = 0;
          } catch {}
        });

        // 行情显示页（仅更新草稿）
        const renderDisplay = () => {
          const K = settingsDraft.kForm;
          const rows = [];

          // —— 原始K线行（按：柱宽/阳线颜色/阴线颜色/复权/显示层级/勾选框/重置按钮） —— //
          rows.push(
            h("div", { class: "std-row" }, [
              nameCell("原始K线"),
              // 复权
              itemCell(
                "复权",
                h(
                  "select",
                  {
                    class: "input",
                    value: String(
                      settingsDraft.adjust || DEFAULT_APP_PREFERENCES.adjust
                    ),
                    onChange: (e) =>
                      (settingsDraft.adjust = String(e.target.value || "none")),
                  },
                  [
                    h("option", { value: "none" }, "不复权"),
                    h("option", { value: "qfq" }, "前复权"),
                    h("option", { value: "hfq" }, "后复权"),
                  ]
                )
              ),
              // 阳线颜色
              itemCell(
                "阳线颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: K.upColor || DEFAULT_KLINE_STYLE.upColor,
                  onInput: (e) =>
                    (settingsDraft.kForm.upColor = String(
                      e.target.value || DEFAULT_KLINE_STYLE.upColor
                    )),
                })
              ),
              // 阳线淡显（0~100）
              itemCell(
                "阳线淡显",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0,
                  max: 100,
                  step: 1,
                  value: Number(
                    K.originalFadeUpPercent ??
                      DEFAULT_KLINE_STYLE.originalFadeUpPercent
                  ),
                  onInput: (e) => {
                    const v = Math.max(
                      0,
                      Math.min(
                        100,
                        Number(
                          e.target.value ||
                            DEFAULT_KLINE_STYLE.originalFadeUpPercent
                        )
                      )
                    );
                    settingsDraft.kForm.originalFadeUpPercent = v;
                  },
                })
              ),
              // 阴线颜色
              itemCell(
                "阴线颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: K.downColor || DEFAULT_KLINE_STYLE.downColor,
                  onInput: (e) =>
                    (settingsDraft.kForm.downColor = String(
                      e.target.value || DEFAULT_KLINE_STYLE.downColor
                    )),
                })
              ),
              // 阴线淡显（0~100）
              itemCell(
                "阴线淡显",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0,
                  max: 100,
                  step: 1,
                  value: Number(
                    K.originalFadeDownPercent ??
                      DEFAULT_KLINE_STYLE.originalFadeDownPercent
                  ),
                  onInput: (e) => {
                    const v = Math.max(
                      0,
                      Math.min(
                        100,
                        Number(
                          e.target.value ||
                            DEFAULT_KLINE_STYLE.originalFadeDownPercent
                        )
                      )
                    );
                    settingsDraft.kForm.originalFadeDownPercent = v;
                  },
                })
              ),
              simpleCheckCell(!!K.originalEnabled, (e) => {
                settingsDraft.kForm.originalEnabled = !!e.target.checked;
              }),
              resetBtn(() => {
                Object.assign(settingsDraft.kForm, {
                  upColor: DEFAULT_KLINE_STYLE.upColor,
                  downColor: DEFAULT_KLINE_STYLE.downColor,
                  originalFadeUpPercent:
                    DEFAULT_KLINE_STYLE.originalFadeUpPercent,
                  originalFadeDownPercent:
                    DEFAULT_KLINE_STYLE.originalFadeDownPercent,
                  originalEnabled: DEFAULT_KLINE_STYLE.originalEnabled,
                });
                settingsDraft.adjust = String(
                  DEFAULT_APP_PREFERENCES.adjust || "none"
                );
              }),
            ])
          );

          // 合并K线行：轮廓线宽 / 上涨颜色 / 下跌颜色 / 填充淡显 / 显示层级（先/后） / 勾选 / 重置
          const MK =
            settingsDraft.kForm.mergedK ||
            (settingsDraft.kForm.mergedK = { ...DEFAULT_KLINE_STYLE.mergedK });
          rows.push(
            h("div", { class: "std-row" }, [
              nameCell("合并K线"),
              // 轮廓线宽
              itemCell(
                "轮廓线宽",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0.1,
                  max: 6,
                  step: 0.1,
                  value: Number(
                    MK.outlineWidth ?? DEFAULT_KLINE_STYLE.mergedK.outlineWidth
                  ),
                  onInput: (e) =>
                    (settingsDraft.kForm.mergedK.outlineWidth = Math.max(
                      0.1,
                      Number(e.target.value || 1.2)
                    )),
                })
              ),
              // 上涨颜色（轮廓与填充）
              itemCell(
                "上涨颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: MK.upColor || DEFAULT_KLINE_STYLE.mergedK.upColor,
                  onInput: (e) =>
                    (settingsDraft.kForm.mergedK.upColor = String(
                      e.target.value || DEFAULT_KLINE_STYLE.mergedK.upColor
                    )),
                })
              ),
              // 下跌颜色（轮廓与填充）
              itemCell(
                "下跌颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: MK.downColor || DEFAULT_KLINE_STYLE.mergedK.downColor,
                  onInput: (e) =>
                    (settingsDraft.kForm.mergedK.downColor = String(
                      e.target.value || DEFAULT_KLINE_STYLE.mergedK.downColor
                    )),
                })
              ),
              // 填充淡显（0~100）
              itemCell(
                "填充淡显",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0,
                  max: 100,
                  step: 1,
                  value: Number(
                    MK.fillFadePercent ??
                      DEFAULT_KLINE_STYLE.mergedK.fillFadePercent
                  ),
                  onInput: (e) => {
                    const v = Math.max(
                      0,
                      Math.min(100, Number(e.target.value || 0))
                    );
                    settingsDraft.kForm.mergedK.fillFadePercent = v;
                  },
                })
              ),
              // 显示层级（先/后）
              itemCell(
                "显示层级",
                h(
                  "select",
                  {
                    class: "input",
                    value: String(
                      MK.displayOrder ||
                        DEFAULT_KLINE_STYLE.mergedK.displayOrder
                    ),
                    onChange: (e) =>
                      (settingsDraft.kForm.mergedK.displayOrder = String(
                        e.target.value
                      )),
                  },
                  [
                    h("option", { value: "first" }, "先"),
                    h("option", { value: "after" }, "后"),
                  ]
                )
              ),
              simpleCheckCell(
                !!settingsDraft.kForm.mergedEnabled,
                (e) => (settingsDraft.kForm.mergedEnabled = !!e.target.checked)
              ),
              // 重置：恢复合并K线相关默认
              resetBtn(() => {
                settingsDraft.kForm.mergedEnabled =
                  DEFAULT_KLINE_STYLE.mergedEnabled;
                settingsDraft.kForm.mergedK = {
                  ...DEFAULT_KLINE_STYLE.mergedK,
                };
              }),
            ])
          );

          // “均线总控”行（第2-6列空，第7列勾选框，第8列空）
          {
            const mui = maGlobalUi();
            rows.push(
              h("div", { class: "std-row" }, [
                nameCell("均线总控"),
                h("div"),
                h("div"),
                h("div"),
                h("div"),
                h("div"),
                triCheckCell({
                  checked: mui.checked,
                  indeterminate: mui.indeterminate,
                  onToggle: onMAGlobalToggle,
                }),
                h("div"),
              ])
            );
          }

          // MA 行（仅更新草稿；保存时统一持久化 + 应用）
          Object.entries(settingsDraft.maForm || {}).forEach(([key, conf]) => {
            rows.push(
              h("div", { class: "std-row" }, [
                nameCell(`MA${conf.period}`),
                itemCell(
                  "线宽",
                  h("input", {
                    class: "input num",
                    type: "number",
                    min: 0.5,
                    max: 4,
                    step: 0.5,
                    value: Number(conf.width ?? 1),
                    onInput: (e) =>
                      (settingsDraft.maForm[key].width = Number(
                        e.target.value || 1
                      )),
                  })
                ),
                itemCell(
                  "颜色",
                  h("input", {
                    class: "input color",
                    type: "color",
                    value:
                      conf.color ||
                      DEFAULT_MA_CONFIGS[key]?.color ||
                      DEFAULT_MA_CONFIGS.MA5.color,
                    onInput: (e) =>
                      (settingsDraft.maForm[key].color = String(
                        e.target.value
                      )),
                  })
                ),
                itemCell(
                  "线型",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.style || "solid",
                      onChange: (e) =>
                        (settingsDraft.maForm[key].style = String(
                          e.target.value
                        )),
                    },
                    [
                      h("option", { value: "solid" }, "实线"),
                      h("option", { value: "dashed" }, "虚线"),
                      h("option", { value: "dotted" }, "点线"),
                    ]
                  )
                ),
                itemCell(
                  "周期",
                  h("input", {
                    class: "input num",
                    type: "number",
                    min: 1,
                    max: 999,
                    step: 1,
                    value: Number(conf.period ?? 5),
                    onInput: (e) =>
                      (settingsDraft.maForm[key].period = Math.max(
                        1,
                        parseInt(e.target.value || 5, 10)
                      )),
                  })
                ),
                h("div"), //空列占位
                simpleCheckCell(!!conf.enabled, (e) => {
                  settingsDraft.maForm[key].enabled = !!e.target.checked;
                  // 单项勾选改变后，更新“均线总控”的快照（仅保存勾选状态）
                  updateMASnapshotFromCurrent();
                }),
                resetBtn(() => {
                  const def = DEFAULT_MA_CONFIGS[key];
                  if (def) {
                    settingsDraft.maForm[key] = { ...def };
                    // 单项重置后更新均线快照
                    updateMASnapshotFromCurrent();
                  }
                }),
              ])
            );
          });

          return rows;
        };

        // 缠论设置（分型与画笔）——仅更新草稿；保存时持久化
        const renderChan = () => {
          const cf = settingsDraft.chanForm;
          const rows = [];

          // 涨跌标记
          rows.push(
            h("div", { class: "std-row" }, [
              nameCell("涨跌标记"),
              itemCell(
                "上涨符号",
                h(
                  "select",
                  {
                    class: "input",
                    value: cf.upShape || CHAN_DEFAULTS.upShape,
                    onChange: (e) =>
                      (settingsDraft.chanForm.upShape = String(e.target.value)),
                  },
                  (FRACTAL_SHAPES || []).map((opt) =>
                    h("option", { value: opt.v }, opt.label)
                  )
                )
              ),
              itemCell(
                "上涨颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: cf.upColor || CHAN_DEFAULTS.upColor,
                  onInput: (e) =>
                    (settingsDraft.chanForm.upColor = String(
                      e.target.value || CHAN_DEFAULTS.upColor
                    )),
                })
              ),
              itemCell(
                "下跌符号",
                h(
                  "select",
                  {
                    class: "input",
                    value: cf.downShape || CHAN_DEFAULTS.downShape,
                    onChange: (e) =>
                      (settingsDraft.chanForm.downShape = String(
                        e.target.value
                      )),
                  },
                  (FRACTAL_SHAPES || []).map((opt) =>
                    h("option", { value: opt.v }, opt.label)
                  )
                )
              ),
              itemCell(
                "下跌颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: cf.downColor || CHAN_DEFAULTS.downColor,
                  onInput: (e) =>
                    (settingsDraft.chanForm.downColor = String(
                      e.target.value || CHAN_DEFAULTS.downColor
                    )),
                })
              ),
              itemCell(
                "承载点",
                h(
                  "select",
                  {
                    class: "input",
                    value: cf.anchorPolicy || CHAN_DEFAULTS.anchorPolicy,
                    onChange: (e) =>
                      (settingsDraft.chanForm.anchorPolicy = String(
                        e.target.value
                      )),
                  },
                  [
                    h("option", { value: "right" }, "右端"),
                    h("option", { value: "extreme" }, "极值"),
                  ]
                )
              ),
              simpleCheckCell(!!cf.showUpDownMarkers, (e) => {
                settingsDraft.chanForm.showUpDownMarkers = !!e.target.checked;
              }),
              resetBtn(() => {
                settingsDraft.chanForm.upShape = CHAN_DEFAULTS.upShape;
                settingsDraft.chanForm.upColor = CHAN_DEFAULTS.upColor;
                settingsDraft.chanForm.downShape = CHAN_DEFAULTS.downShape;
                settingsDraft.chanForm.downColor = CHAN_DEFAULTS.downColor;
                settingsDraft.chanForm.anchorPolicy =
                  CHAN_DEFAULTS.anchorPolicy;
                settingsDraft.chanForm.showUpDownMarkers =
                  CHAN_DEFAULTS.showUpDownMarkers;
              }),
            ])
          );

          // 分型判定（第7列为无标题总开关 tri-state；第8列重置）
          const ff = settingsDraft.fractalForm;
          const styleByStrength = (ff.styleByStrength =
            ff.styleByStrength ||
            JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.styleByStrength)));
          const confirmStyle = (ff.confirmStyle =
            ff.confirmStyle ||
            JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.confirmStyle)));

          const globalUi = globalToggleUi(ff);

          rows.push(
            h("div", { class: "std-row" }, [
              nameCell("分型判定"),
              itemCell(
                "最小tick",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0,
                  step: 1,
                  value: Number(
                    ff.minTickCount ?? FRACTAL_DEFAULTS.minTickCount
                  ),
                  onInput: (e) =>
                    (settingsDraft.fractalForm.minTickCount = Math.max(
                      0,
                      parseInt(
                        e.target.value || FRACTAL_DEFAULTS.minTickCount,
                        10
                      )
                    )),
                })
              ),
              itemCell(
                "最小幅度%",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0,
                  step: 0.01,
                  value: Number(ff.minPct ?? FRACTAL_DEFAULTS.minPct),
                  onInput: (e) =>
                    (settingsDraft.fractalForm.minPct = Math.max(
                      0,
                      Number(e.target.value || FRACTAL_DEFAULTS.minPct)
                    )),
                })
              ),
              itemCell(
                "判断条件",
                h(
                  "select",
                  {
                    class: "input",
                    value: String(ff.minCond || FRACTAL_DEFAULTS.minCond),
                    onChange: (e) =>
                      (settingsDraft.fractalForm.minCond = String(
                        e.target.value
                      )),
                  },
                  [
                    h("option", { value: "or" }, "或"),
                    h("option", { value: "and" }, "与"),
                  ]
                )
              ),
              h("div"), //空列占位
              h("div"), //空列占位
              // 第7列：总开关（无标题，仅 checkbox，三态）
              triCheckCell({
                checked: globalUi.checked,
                indeterminate: globalUi.indeterminate,
                onToggle: () => onGlobalToggle(ff),
              }),
              // 第8列：重置
              resetBtn(() => {
                settingsDraft.fractalForm.minTickCount =
                  FRACTAL_DEFAULTS.minTickCount;
                settingsDraft.fractalForm.minPct = FRACTAL_DEFAULTS.minPct;
                settingsDraft.fractalForm.minCond = FRACTAL_DEFAULTS.minCond;
                const d = JSON.parse(
                  JSON.stringify(FRACTAL_DEFAULTS.styleByStrength)
                );
                d.strong.enabled = true;
                d.standard.enabled = true;
                d.weak.enabled = true;
                settingsDraft.fractalForm.styleByStrength = d;
                settingsDraft.fractalForm.showStrength = {
                  strong: true,
                  standard: true,
                  weak: true,
                };
                settingsDraft.fractalForm.confirmStyle = JSON.parse(
                  JSON.stringify(FRACTAL_DEFAULTS.confirmStyle)
                );
                settingsDraft.fractalForm.confirmStyle.enabled = true;
                // 重置后，快照更新并循环指针归零
                lastManualSnapshot.value = getCurrentFractalCombination(
                  settingsDraft.fractalForm
                );
                globalCycleIndex.value = 0;
              }),
            ])
          );

          // 强分型行（仅在 enabled 改变时更新快照）
          (() => {
            const conf = styleByStrength.strong;
            rows.push(
              h("div", { class: "std-row" }, [
                nameCell("强分型"),
                itemCell(
                  "底分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.bottomShape,
                      onChange: (e) => {
                        const s =
                          settingsDraft.fractalForm.styleByStrength || {};
                        s.strong = {
                          ...(s.strong || conf),
                          bottomShape: String(e.target.value),
                        };
                        settingsDraft.fractalForm.styleByStrength = s;
                      },
                    },
                    (FRACTAL_SHAPES || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                itemCell(
                  "底分颜色",
                  h("input", {
                    class: "input color",
                    type: "color",
                    value: conf.bottomColor,
                    onInput: (e) => {
                      const s = settingsDraft.fractalForm.styleByStrength || {};
                      s.strong = {
                        ...(s.strong || conf),
                        bottomColor: String(e.target.value),
                      };
                      settingsDraft.fractalForm.styleByStrength = s;
                    },
                  })
                ),
                itemCell(
                  "顶分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.topShape,
                      onChange: (e) => {
                        const s =
                          settingsDraft.fractalForm.styleByStrength || {};
                        s.strong = {
                          ...(s.strong || conf),
                          topShape: String(e.target.value),
                        };
                        settingsDraft.fractalForm.styleByStrength = s;
                      },
                    },
                    (FRACTAL_SHAPES || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                itemCell(
                  "顶分颜色",
                  h("input", {
                    class: "input color",
                    type: "color",
                    value: conf.topColor,
                    onInput: (e) => {
                      const s = settingsDraft.fractalForm.styleByStrength || {};
                      s.strong = {
                        ...(s.strong || conf),
                        topColor: String(e.target.value),
                      };
                      settingsDraft.fractalForm.styleByStrength = s;
                    },
                  })
                ),
                itemCell(
                  "填充",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.fill,
                      onChange: (e) => {
                        const s =
                          settingsDraft.fractalForm.styleByStrength || {};
                        s.strong = {
                          ...(s.strong || conf),
                          fill: String(e.target.value),
                        };
                        settingsDraft.fractalForm.styleByStrength = s;
                      },
                    },
                    (FRACTAL_FILLS || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                simpleCheckCell(!!conf.enabled, (e) => {
                  const s = settingsDraft.fractalForm.styleByStrength || {};
                  s.strong = {
                    ...(s.strong || conf),
                    enabled: !!e.target.checked,
                  };
                  settingsDraft.fractalForm.styleByStrength = s;
                  const ss = settingsDraft.fractalForm.showStrength || {};
                  settingsDraft.fractalForm.showStrength = {
                    ...ss,
                    strong: !!e.target.checked,
                  };
                  updateSnapshotFromCurrent(); // 仅在四项 enabled 改变时更新快照
                }),
                resetBtn(() => {
                  const d = JSON.parse(
                    JSON.stringify(FRACTAL_DEFAULTS.styleByStrength.strong)
                  );
                  const s = settingsDraft.fractalForm.styleByStrength || {};
                  s.strong = d;
                  settingsDraft.fractalForm.styleByStrength = s;
                  // showStrength 同步默认
                  const ss = settingsDraft.fractalForm.showStrength || {};
                  settingsDraft.fractalForm.showStrength = {
                    ...ss,
                    strong: true,
                  };
                  // 修正：分型快照更新调用自身
                  updateSnapshotFromCurrent();
                }),
              ])
            );
          })();

          // 标准分型行（仅在 enabled 改变时更新快照）
          (() => {
            const conf = styleByStrength.standard;
            rows.push(
              h("div", { class: "std-row" }, [
                nameCell("标准分型"),
                itemCell(
                  "底分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.bottomShape,
                      onChange: (e) => {
                        const s =
                          settingsDraft.fractalForm.styleByStrength || {};
                        s.standard = {
                          ...(s.standard || conf),
                          bottomShape: String(e.target.value),
                        };
                        settingsDraft.fractalForm.styleByStrength = s;
                      },
                    },
                    (FRACTAL_SHAPES || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                itemCell(
                  "底分颜色",
                  h("input", {
                    class: "input color",
                    type: "color",
                    value: conf.bottomColor,
                    onInput: (e) => {
                      const s = settingsDraft.fractalForm.styleByStrength || {};
                      s.standard = {
                        ...(s.standard || conf),
                        bottomColor: String(e.target.value),
                      };
                      settingsDraft.fractalForm.styleByStrength = s;
                    },
                  })
                ),
                itemCell(
                  "顶分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.topShape,
                      onChange: (e) => {
                        const s =
                          settingsDraft.fractalForm.styleByStrength || {};
                        s.standard = {
                          ...(s.standard || conf),
                          topShape: String(e.target.value),
                        };
                        settingsDraft.fractalForm.styleByStrength = s;
                      },
                    },
                    (FRACTAL_SHAPES || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                itemCell(
                  "顶分颜色",
                  h("input", {
                    class: "input color",
                    type: "color",
                    value: conf.topColor,
                    onInput: (e) => {
                      const s = settingsDraft.fractalForm.styleByStrength || {};
                      s.standard = {
                        ...(s.standard || conf),
                        topColor: String(e.target.value),
                      };
                      settingsDraft.fractalForm.styleByStrength = s;
                    },
                  })
                ),
                itemCell(
                  "填充",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.fill,
                      onChange: (e) => {
                        const s =
                          settingsDraft.fractalForm.styleByStrength || {};
                        s.standard = {
                          ...(s.standard || conf),
                          fill: String(e.target.value),
                        };
                        settingsDraft.fractalForm.styleByStrength = s;
                      },
                    },
                    (FRACTAL_FILLS || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                simpleCheckCell(!!conf.enabled, (e) => {
                  const s = settingsDraft.fractalForm.styleByStrength || {};
                  s.standard = {
                    ...(s.standard || conf),
                    enabled: !!e.target.checked,
                  };
                  settingsDraft.fractalForm.styleByStrength = s;
                  const ss = settingsDraft.fractalForm.showStrength || {};
                  settingsDraft.fractalForm.showStrength = {
                    ...ss,
                    standard: !!e.target.checked,
                  };
                  updateSnapshotFromCurrent();
                }),
                resetBtn(() => {
                  const d = JSON.parse(
                    JSON.stringify(FRACTAL_DEFAULTS.styleByStrength.standard)
                  );
                  const s = settingsDraft.fractalForm.styleByStrength || {};
                  s.standard = d;
                  settingsDraft.fractalForm.styleByStrength = s;
                  const ss = settingsDraft.fractalForm.showStrength || {};
                  settingsDraft.fractalForm.showStrength = {
                    ...ss,
                    standard: true,
                  };
                  updateSnapshotFromCurrent();
                }),
              ])
            );
          })();

          // 弱分型行（仅在 enabled 改变时更新快照）
          (() => {
            const conf = styleByStrength.weak;
            rows.push(
              h("div", { class: "std-row" }, [
                nameCell("弱分型"),
                itemCell(
                  "底分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.bottomShape,
                      onChange: (e) => {
                        const s =
                          settingsDraft.fractalForm.styleByStrength || {};
                        s.weak = {
                          ...(s.weak || conf),
                          bottomShape: String(e.target.value),
                        };
                        settingsDraft.fractalForm.styleByStrength = s;
                      },
                    },
                    (FRACTAL_SHAPES || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                itemCell(
                  "底分颜色",
                  h("input", {
                    class: "input color",
                    type: "color",
                    value: conf.bottomColor,
                    onInput: (e) => {
                      const s = settingsDraft.fractalForm.styleByStrength || {};
                      s.weak = {
                        ...(s.weak || conf),
                        bottomColor: String(e.target.value),
                      };
                      settingsDraft.fractalForm.styleByStrength = s;
                    },
                  })
                ),
                itemCell(
                  "顶分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.topShape,
                      onChange: (e) => {
                        const s =
                          settingsDraft.fractalForm.styleByStrength || {};
                        s.weak = {
                          ...(s.weak || conf),
                          topShape: String(e.target.value),
                        };
                        settingsDraft.fractalForm.styleByStrength = s;
                      },
                    },
                    (FRACTAL_SHAPES || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                itemCell(
                  "顶分颜色",
                  h("input", {
                    class: "input color",
                    type: "color",
                    value: conf.topColor,
                    onInput: (e) => {
                      const s = settingsDraft.fractalForm.styleByStrength || {};
                      s.weak = {
                        ...(s.weak || conf),
                        topColor: String(e.target.value),
                      };
                      settingsDraft.fractalForm.styleByStrength = s;
                    },
                  })
                ),
                itemCell(
                  "填充",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.fill,
                      onChange: (e) => {
                        const s =
                          settingsDraft.fractalForm.styleByStrength || {};
                        s.weak = {
                          ...(s.weak || conf),
                          fill: String(e.target.value),
                        };
                        settingsDraft.fractalForm.styleByStrength = s;
                      },
                    },
                    (FRACTAL_FILLS || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                simpleCheckCell(!!conf.enabled, (e) => {
                  const s = settingsDraft.fractalForm.styleByStrength || {};
                  s.weak = {
                    ...(s.weak || conf),
                    enabled: !!e.target.checked,
                  };
                  settingsDraft.fractalForm.styleByStrength = s;
                  const ss = settingsDraft.fractalForm.showStrength || {};
                  settingsDraft.fractalForm.showStrength = {
                    ...ss,
                    weak: !!e.target.checked,
                  };
                  updateSnapshotFromCurrent();
                }),
                resetBtn(() => {
                  const d = JSON.parse(
                    JSON.stringify(FRACTAL_DEFAULTS.styleByStrength.weak)
                  );
                  const s = settingsDraft.fractalForm.styleByStrength || {};
                  s.weak = d;
                  settingsDraft.fractalForm.styleByStrength = s;
                  const ss = settingsDraft.fractalForm.showStrength || {};
                  settingsDraft.fractalForm.showStrength = {
                    ...ss,
                    weak: true,
                  };
                  updateSnapshotFromCurrent();
                }),
              ])
            );
          })();

          // 确认分型行（仅在 enabled 改变时更新快照）
          (() => {
            const cs = confirmStyle;
            rows.push(
              h("div", { class: "std-row" }, [
                nameCell("确认分型"),
                itemCell(
                  "底分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: cs.bottomShape,
                      onChange: (e) =>
                        (settingsDraft.fractalForm.confirmStyle.bottomShape =
                          String(e.target.value)),
                    },
                    (FRACTAL_SHAPES || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                itemCell(
                  "底分颜色",
                  h("input", {
                    class: "input color",
                    type: "color",
                    value: cs.bottomColor,
                    onInput: (e) =>
                      (settingsDraft.fractalForm.confirmStyle.bottomColor =
                        String(e.target.value)),
                  })
                ),
                itemCell(
                  "顶分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: cs.topShape,
                      onChange: (e) =>
                        (settingsDraft.fractalForm.confirmStyle.topShape =
                          String(e.target.value)),
                    },
                    (FRACTAL_SHAPES || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                itemCell(
                  "顶分颜色",
                  h("input", {
                    class: "input color",
                    type: "color",
                    value: cs.topColor,
                    onInput: (e) =>
                      (settingsDraft.fractalForm.confirmStyle.topColor = String(
                        e.target.value
                      )),
                  })
                ),
                itemCell(
                  "填充",
                  h(
                    "select",
                    {
                      class: "input",
                      value: cs.fill,
                      onChange: (e) =>
                        (settingsDraft.fractalForm.confirmStyle.fill = String(
                          e.target.value
                        )),
                    },
                    (FRACTAL_FILLS || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                simpleCheckCell(!!cs.enabled, (e) => {
                  settingsDraft.fractalForm.confirmStyle = {
                    ...(settingsDraft.fractalForm.confirmStyle || cs),
                    enabled: !!e.target.checked,
                  };
                  updateSnapshotFromCurrent();
                }),
                resetBtn(() => {
                  const def = JSON.parse(
                    JSON.stringify(FRACTAL_DEFAULTS.confirmStyle)
                  );
                  def.enabled = true;
                  settingsDraft.fractalForm.confirmStyle = def;
                  updateSnapshotFromCurrent();
                }),
              ])
            );
          })();

          // 画笔设置
          const penCfg =
            settingsDraft.chanForm.pen &&
            typeof settingsDraft.chanForm.pen === "object"
              ? settingsDraft.chanForm.pen
              : JSON.parse(JSON.stringify(PENS_DEFAULTS));

          rows.push(
            h("div", { class: "std-row" }, [
              nameCell("简笔"),
              // 线宽
              itemCell(
                "线宽",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0.5,
                  max: 6,
                  step: 0.5,
                  value: Number.isFinite(+penCfg.lineWidth)
                    ? +penCfg.lineWidth
                    : PENS_DEFAULTS.lineWidth,
                  onInput: (e) => {
                    const v = Math.max(
                      0.5,
                      Math.min(
                        6,
                        Number(e.target.value || PENS_DEFAULTS.lineWidth)
                      )
                    );
                    settingsDraft.chanForm.pen = Object.assign({}, penCfg, {
                      lineWidth: v,
                    });
                  },
                })
              ),
              // 颜色
              itemCell(
                "颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: penCfg.color || PENS_DEFAULTS.color,
                  onInput: (e) => {
                    settingsDraft.chanForm.pen = Object.assign({}, penCfg, {
                      color: String(e.target.value || PENS_DEFAULTS.color),
                    });
                  },
                })
              ),
              // 确认线型
              itemCell(
                "确认线型",
                h(
                  "select",
                  {
                    class: "input",
                    value:
                      penCfg.confirmedStyle || PENS_DEFAULTS.confirmedStyle,
                    onChange: (e) => {
                      settingsDraft.chanForm.pen = Object.assign({}, penCfg, {
                        confirmedStyle: String(e.target.value),
                      });
                    },
                  },
                  [
                    h("option", { value: "solid" }, "实线"),
                    h("option", { value: "dashed" }, "虚线"),
                    h("option", { value: "dotted" }, "点线"),
                  ]
                )
              ),
              // 预备线型
              itemCell(
                "预备线型",
                h(
                  "select",
                  {
                    class: "input",
                    value:
                      penCfg.provisionalStyle || PENS_DEFAULTS.provisionalStyle,
                    onChange: (e) => {
                      settingsDraft.chanForm.pen = Object.assign({}, penCfg, {
                        provisionalStyle: String(e.target.value),
                      });
                    },
                  },
                  [
                    h("option", { value: "solid" }, "实线"),
                    h("option", { value: "dashed" }, "虚线"),
                    h("option", { value: "dotted" }, "点线"),
                  ]
                )
              ),
              h("div"), // 空列占位
              simpleCheckCell(
                (penCfg.enabled ?? PENS_DEFAULTS.enabled) === true,
                (e) => {
                  settingsDraft.chanForm.pen = Object.assign({}, penCfg, {
                    enabled: !!e.target.checked,
                  });
                }
              ),
              resetBtn(() => {
                settingsDraft.chanForm.pen = JSON.parse(
                  JSON.stringify(PENS_DEFAULTS)
                );
              }),
            ])
          );

          return rows;
        };

        return () =>
          h("div", {}, [
            ...(props.activeTab === "chan" ? renderChan() : renderDisplay()),
          ]);
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
      activeTab: "display",
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
          settings.setChanSettings({ ...settingsDraft.chanForm });
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

/* 缠论/分型/笔/线段/屏障缓存 —— 统一在 recomputeChan 中构建 */
const chanCache = ref({
  reduced: [],
  map: [],
  meta: null,
  fractals: [],
  pens: { confirmed: [], provisional: null, all: [] },
  segments: [], // 新增：元线段缓存
  barriersIndices: [], // NEW: 屏障竖线位置（原始K索引，含左右各一）
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

    chanCache.value = {
      reduced: res.reducedBars || [],
      map: res.mapOrigToReduced || [],
      meta: res.meta || null,
      fractals: fr || [],
      pens: pens || { confirmed: [], provisional: null, all: [] },
      segments: segments || [],
      barriersIndices: barrierIdxList, // NEW
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

  return out;
}

/* onDataZoom：ECharts-first 会话锁 + idle-commit（不抢权、会后承接） */
let dzIdleTimer = null;
const dzIdleDelayMs = 100; // 建议 100–200ms，避免频繁承接

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
        renderHub.endInteraction("main");
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

/* 预览显示 */
function pad2(n) {
  return String(n).padStart(2, "0");
}
function fmtShort(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const Y = d.getFullYear(),
      M = pad2(d.getMonth() + 1),
      D = pad2(d.getDate());
    if (/m$/.test(String(vm.freq.value || ""))) {
      const h = pad2(d.getHours()),
        m = pad2(d.getMinutes());
      return `${Y}-${M}-${D} ${h}:${m}`;
    }
    return `${Y}-${M}-${D}`;
  } catch {
    return "";
  }
}
const previewStartStr = ref("");
const previewEndStr = ref("");
const previewBarsCount = ref(0);
const formattedStart = computed(() => {
  return (
    (previewStartStr.value && fmtShort(previewStartStr.value)) ||
    fmtShort(vm.visibleRange.value.startStr) ||
    "-"
  );
});
const formattedEnd = computed(() => {
  return (
    (previewEndStr.value && fmtShort(previewEndStr.value)) ||
    fmtShort(vm.visibleRange.value.endStr) ||
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

  // NEW: 注册主窗 chart，并在鼠标进入主窗时设置为“激活面板”
  try {
    renderHub.registerChart("main", chart);
    el.addEventListener("mouseenter", () => {
      renderHub.setActivePanel("main");
    });
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
    const pad2v = String(v).padStart(2, "0");
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
