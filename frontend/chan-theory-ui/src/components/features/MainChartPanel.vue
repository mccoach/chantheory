<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\MainChartPanel.vue -->
<!-- ====================================================================== -->
<!-- 主图组件（接入“上游统一渲染中枢 useViewRenderHub” · 一次订阅一次渲染）
     本轮改动目标（第一轮：仅改布局 + 原位输入；删除原高级面板）：
     1) 顶栏布局改为“两行两列”：
        - 第一行：左列为改频按钮（靠左），右列为窗宽预设按钮（靠右）；
        - 第二行：左列为起止时间“原位输入”（按频率显示日/分钟族），右列为 Bars 数“原位输入”（失焦应用）。
     2) 原“高级面板”删除，手输日期/N 根功能迁移为“原位输入”，其余行为与现状保持一致（严格守护）。
     3) 原交互与渲染机制（onDataZoom 会后承接、中枢两帧合并、程序化阻断、idle-commit、一次性 setOption）保持不变。
-->
<!-- ====================================================================== -->

<template>
  <!-- 顶部控制区（两行两列） -->
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
} from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { computeInclude, computeFractals } from "@/composables/useChan";
import { vSelectAll } from "@/utils/inputBehaviors";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import { buildUpDownMarkers, buildFractalMarkers } from "@/charts/chan/layers";

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

/* MOD: 增加“当前高亮预设键”的响应式变量，并订阅中枢快照 */
const activePresetKey = ref(hub.getState().presetKey || "ALL");
hub.onChange((st) => {
  activePresetKey.value = st.presetKey || "ALL";
});

/* 覆盖式防抖/序号守护 */
let renderSeq = 0;
function isStale(seq) {
  return seq !== renderSeq;
}

/* 程序化 dataZoom 守护（保持原变量与逻辑） */
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

/* —— 移除高级面板相关状态/模板（迁移为“原位输入”，其余逻辑保持不变） —— */

/* 画布/实例与 Resize */
const wrap = ref(null);
const host = ref(null);
let chart = null;
let ro = null;

// NEW: 订阅 ID 句柄（用于 renderHub.onRender 的取消订阅）
// 说明：之前未声明导致 mounted 钩子赋值 unsubId 报错，此处补充在模块作用域统一声明。
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

/* 设置弹窗（保持原逻辑） */
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
    settingsDraft.kForm = JSON.parse(
      JSON.stringify({
        ...DEFAULT_KLINE_STYLE,
        ...(settings.klineStyle.value || {}),
      })
    );
    const maDefaults = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS));
    const maLocal = settings.maConfigs.value || {};
    Object.keys(maDefaults).forEach((k) => {
      if (maLocal[k]) maDefaults[k] = { ...maDefaults[k], ...maLocal[k] };
    });
    settingsDraft.maForm = maDefaults;
    settingsDraft.chanForm = JSON.parse(
      JSON.stringify({
        ...CHAN_DEFAULTS,
        ...(settings.chanSettings.value || {}),
      })
    );
    settingsDraft.fractalForm = JSON.parse(
      JSON.stringify({
        ...FRACTAL_DEFAULTS,
        ...(settings.fractalSettings.value || {}),
      })
    );
    prevAdjust = String(
      vm.adjust.value || settings.adjust.value || DEFAULT_APP_PREFERENCES.adjust
    );
    settingsDraft.adjust = prevAdjust;

    const MainChartSettingsContent = defineComponent({
      props: { activeTab: { type: String, default: "display" } },
      setup(props) {
        const nameCell = (text) => h("div", { class: "std-name" }, text);
        const itemCell = (label, node) =>
          h("div", { class: "std-item" }, [
            h("div", { class: "std-item-label" }, label),
            h("div", { class: "std-item-input" }, [node]),
          ]);
        const checkCell = (checked, onChange) =>
          h("div", { class: "std-check" }, [
            h("input", { type: "checkbox", checked, onChange }),
          ]);
        const resetBtn = (onClick) =>
          h("div", { class: "std-reset" }, [
            h("button", {
              class: "btn icon",
              title: "恢复默认",
              type: "button",
              onClick,
            }),
          ]);

        // 行情显示（原始K/合并K/MA）
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
              // 原始K线开关
              checkCell(
                !!K.originalEnabled,
                (e) =>
                  (settingsDraft.kForm.originalEnabled = !!e.target.checked)
              ),
              // 重置：恢复原始K线相关默认与复权默认
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
              // 合并K线开关
              checkCell(
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
          Object.keys(settingsDraft.maForm || {}).forEach((key) => {
            const conf = settingsDraft.maForm[key];
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
                        e.target.value ||
                          DEFAULT_MA_CONFIGS[key]?.color ||
                          DEFAULT_MA_CONFIGS.MA5.color
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
                      onChange: (e) => (conf.style = String(e.target.value)),
                    },
                    [
                      h("option", "solid"),
                      h("option", "dashed"),
                      h("option", "dotted"),
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
                      (conf.period = Math.max(
                        1,
                        parseInt(e.target.value || 5, 10)
                      )),
                  })
                ),
                h("div"),
                checkCell(
                  !!conf.enabled,
                  (e) => (conf.enabled = !!e.target.checked)
                ),
                resetBtn(() => {
                  const def = DEFAULT_MA_CONFIGS[key];
                  if (def) {
                    settingsDraft.maForm[key] = { ...def };
                  }
                }),
              ])
            );
          });
          return rows;
        };

        // 缠论设置（保留原有“涨跌标记 + 分型判定 + 强/标准/弱 + 确认分型”）
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
              h("div", { class: "std-check" }, [
                h("input", {
                  type: "checkbox",
                  checked: !!cf.showUpDownMarkers,
                  onChange: (e) =>
                    (settingsDraft.chanForm.showUpDownMarkers =
                      !!e.target.checked),
                }),
              ]),
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

          // 分型判定 + 强/标准/弱 + 确认分型（完整回归）
          const ff = settingsDraft.fractalForm;
          const styleByStrength = (ff.styleByStrength =
            ff.styleByStrength ||
            JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.styleByStrength)));
          const confirmStyle = (ff.confirmStyle =
            ff.confirmStyle ||
            JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.confirmStyle)));

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
              h("div"),
              h("div"),
              h("div"),
              resetBtn(() => {
                settingsDraft.fractalForm.minTickCount =
                  FRACTAL_DEFAULTS.minTickCount;
                settingsDraft.fractalForm.minPct = FRACTAL_DEFAULTS.minPct;
                settingsDraft.fractalForm.minCond = FRACTAL_DEFAULTS.minCond;
              }),
            ])
          );

          const specs = [
            { k: "strong", label: "强分型" },
            { k: "standard", label: "标准分型" },
            { k: "weak", label: "弱分型" },
          ];
          function resetStrengthRow(key) {
            styleByStrength[key] = JSON.parse(
              JSON.stringify(FRACTAL_DEFAULTS.styleByStrength[key])
            );
          }
          for (const sp of specs) {
            const conf = styleByStrength[sp.k];
            rows.push(
              h("div", { class: "std-row" }, [
                nameCell(sp.label),
                itemCell(
                  "底分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.bottomShape,
                      onChange: (e) =>
                        (conf.bottomShape = String(e.target.value)),
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
                    onInput: (e) => (conf.bottomColor = String(e.target.value)),
                  })
                ),
                itemCell(
                  "顶分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.topShape,
                      onChange: (e) => (conf.topShape = String(e.target.value)),
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
                    onInput: (e) => (conf.topColor = String(e.target.value)),
                  })
                ),
                itemCell(
                  "填充",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.fill,
                      onChange: (e) => (conf.fill = String(e.target.value)),
                    },
                    (FRACTAL_FILLS || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                h("div", { class: "std-check" }, [
                  h("input", {
                    type: "checkbox",
                    checked: !!conf.enabled,
                    onChange: (e) => (conf.enabled = !!e.target.checked),
                  }),
                ]),
                resetBtn(() => resetStrengthRow(sp.k)),
              ])
            );
          }

          rows.push(
            h("div", { class: "std-row" }, [
              nameCell("确认分型"),
              itemCell(
                "底分符号",
                h(
                  "select",
                  {
                    class: "input",
                    value: confirmStyle.bottomShape,
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
                  value: confirmStyle.bottomColor,
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
                    value: confirmStyle.topShape,
                    onChange: (e) =>
                      (settingsDraft.fractalForm.confirmStyle.topShape = String(
                        e.target.value
                      )),
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
                  value: confirmStyle.topColor,
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
                    value: confirmStyle.fill,
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
              h("div", { class: "std-check" }, [
                h("input", {
                  type: "checkbox",
                  checked: !!confirmStyle.enabled,
                  onChange: (e) =>
                    (settingsDraft.fractalForm.confirmStyle.enabled =
                      !!e.target.checked),
                }),
              ]),
              resetBtn(() => {
                const def = FRACTAL_DEFAULTS.confirmStyle;
                settingsDraft.fractalForm.confirmStyle = JSON.parse(
                  JSON.stringify(def)
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
      onResetAll: () => {
        try {
          Object.assign(settingsDraft.kForm, { ...DEFAULT_KLINE_STYLE });
          settingsDraft.adjust = String(
            DEFAULT_APP_PREFERENCES.adjust || "none"
          );
          const defs = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS));
          settingsDraft.maForm = defs;
          settingsDraft.chanForm = JSON.parse(JSON.stringify(CHAN_DEFAULTS));
          settingsDraft.fractalForm = JSON.parse(
            JSON.stringify(FRACTAL_DEFAULTS)
          );
        } catch (e) {}
      },
      onSave: () => {
        try {
          settings.setKlineStyle(settingsDraft.kForm);
          settings.setMaConfigs(settingsDraft.maForm);
          settings.setChanSettings({ ...settingsDraft.chanForm });
          settings.setFractalSettings({ ...settingsDraft.fractalForm });
          const nextAdjust = String(settingsDraft.adjust || "none");
          const adjustChanged = nextAdjust !== prevAdjust;
          if (adjustChanged) {
            settings.setAdjust(nextAdjust);
          }

          // MOD: 立即触发中枢刷新，发布新快照 -> 即时应用新设置
          hub.execute("Refresh", {});
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

/* 键盘左右键（保持原逻辑） */
let currentIndex = -1;

function focusWrap() {
  try {
    wrap.value?.focus?.();
  } catch {}
}

/* 缠论/分型覆盖层 —— 构造覆盖层 series（一次性装配） */
const chanCache = ref({ reduced: [], map: [], meta: null, fractals: [] });
function recomputeChan() {
  try {
    const arr = vm.candles.value || [];
    if (!arr.length) {
      chanCache.value = { reduced: [], map: [], meta: null, fractals: [] };
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
    chanCache.value = {
      reduced: res.reducedBars || [],
      map: res.mapOrigToReduced || [],
      meta: res.meta || null,
      fractals: fr || [],
    };
  } catch {
    chanCache.value = { reduced: [], map: [], meta: null, fractals: [] };
  }
}

/**
 * 构造覆盖层 series（一次性装配）
 * - 保持原有 buildUpDownMarkers/buildFractalMarkers 的使用与样式；
 * - 若禁用或无数据，则输出占位系列（CHAN_UP/CHAN_DOWN 空），满足不变量；
 * - 返回数组，供主图 option.series 直接拼接。
 */
function buildOverlaySeriesForOption({ hostW, visCount, markerW }) {
  const out = [];
  const reduced = chanCache.value.reduced || [];
  const fractals = chanCache.value.fractals || [];

  // 涨跌标记
  if (settings.chanSettings.value.showUpDownMarkers && reduced.length) {
    const upDownLayer = buildUpDownMarkers(reduced, {
      chanSettings: settings.chanSettings.value,
      hostWidth: hostW,
      visCount,
      symbolWidthPx: markerW,
    });
    out.push(...(upDownLayer.series || []));
  } else {
    out.push(
      {
        type: "scatter",
        id: "CHAN_UP",
        name: "CHAN_UP",
        yAxisIndex: 1,
        data: [],
        symbol: "triangle",
        symbolSize: () => [8, 10],
        symbolOffset: [0, 12], // 上移，避免与底部轴标签重叠
        itemStyle: {
          color: settings.chanSettings.value.upColor || CHAN_DEFAULTS.upColor,
          opacity: settings.chanSettings.value.opacity ?? CHAN_DEFAULTS.opacity,
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
        symbolSize: () => [8, 10],
        symbolOffset: [0, 12],
        itemStyle: {
          color:
            settings.chanSettings.value.downColor || CHAN_DEFAULTS.downColor,
          opacity: settings.chanSettings.value.opacity ?? CHAN_DEFAULTS.opacity,
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

  return out;
}

// 会话空闲承接（交互结束短 idle 后一次性承接到中枢）
let dzIdleTimer = null;
const dzIdleDelayMs = 100; // 建议 160–200ms，避免频繁承接

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

/* 一次订阅一次渲染：交互期间不做 notMerge 重绘，避免抢权 */
function doSinglePassRender(snapshot) {
  try {
    if (!chart || !snapshot) return;
    const mySeq = ++renderSeq;

    // —— 合并K线修复：先 recomputeChan，再用 reducedBars 重建主图 option —— //
    recomputeChan();
    const reduced = chanCache.value.reduced || [];
    const mapReduced = chanCache.value.map || [];

    const initialRange = {
      startValue: snapshot.main.range.startValue,
      endValue: snapshot.main.range.endValue,
    };
    const tipPositioner = renderHub.getTipPositioner();

    // 标记存在则给主图内部挤空间（逻辑保持不变）
    const anyMarkers =
      (settings.chanSettings.value?.showUpDownMarkers ?? true) === true &&
      reduced.length > 0;
    const MARKER_HEIGHT_PX = Math.max(
      2,
      Math.round(snapshot.core?.markerWidthPx || 4)
    );
    const SAFE_PADDING_PX = 12;
    const mainBottomExtraPx = anyMarkers
      ? MARKER_HEIGHT_PX + SAFE_PADDING_PX - 8
      : 0;
    const xAxisLabelMargin = 12 + mainBottomExtraPx;

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
        isHovered: snapshot.main.isHovered, // MOD: 传入悬浮状态
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

/* 预览显示（保持原逻辑） */
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

/* 生命周期（订阅时机调整到 chart.init 后） */
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

  // —— 订阅 useViewRenderHub：移到 chart.init 完成后（必要调序） —— //
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

/* 标题/刷新徽标更新（保持原逻辑） */
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

/* ============================= */
/* 原位输入：起止日期/时间与 Bars */
/* ============================= */

const isMinuteFreq = computed(() => /m$/.test(String(vm.freq.value || "")));

// 原位输入的字段（起/止）
const startFields = reactive({ Y: "", M: "", D: "", h: "", m: "" });
const endFields = reactive({ Y: "", M: "", D: "", h: "", m: "" });

// Bars 原位输入
const barsStr = ref("");

// ADD-BEGIN [权威订阅：任何渠道变更 bars/rightTs 后，起止与 Bars 立即刷新显示]
// 说明：此前信息源头主要依赖 previewStartStr/previewEndStr 与 vm.visibleRange（来自 vm.meta.view_*），
// 某些“纯本地交互路径”（未触发后端）在极端情况下可能出现轻微滞后。现在改为 hub.onChange 权威订阅，
// 用 hub.barsCount/rightTs + ALL candles 计算 sIdx/eIdx → 回填 preview* 与输入框，保证实时一致。
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
    if (!Number.isFinite(ys) || !Number.isFinite(ms) || !Number.isFinite(ds))
      return;
    if (!Number.isFinite(ye) || !Number.isFinite(me) || !Number.isFinite(de))
      return;

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

    // 基本校验
    if (
      ![ys, ms, ds, hs, mins].every(Number.isFinite) ||
      ![ye, me, de, he, mine].every(Number.isFinite)
    )
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

/* 结束：原位输入实现 */

/* 订阅上游渲染（保持原逻辑） */
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
</style>
