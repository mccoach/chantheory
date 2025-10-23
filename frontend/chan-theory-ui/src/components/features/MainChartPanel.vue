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
import {
  inject,
  onMounted,
  onBeforeUnmount,
  ref,
  watch,
  computed,
  reactive,
} from "vue";
import * as echarts from "echarts";
import { WINDOW_PRESETS } from "@/constants"; // REFACTORED: 移除不再使用的常量
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import { openMainChartSettings } from "@/settings/mainShell";

import { pad2, fmtShort } from "@/utils/timeFormat";

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

/* 设置弹窗（改为独立壳调用） */
function openSettingsDialog() {
  try {
    openMainChartSettings(dialogManager, { activeTab: "chan" });
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

// REFACTORED: 移除 recomputeChan 和 buildOverlaySeriesForOption

/* onDataZoom：ECharts-first 会话锁 + idle-commit（不抢权、会后承接） */
let dzIdleTimer = null;
const dzIdleDelayMs = 100; // 建议 100–200ms，避免频繁承接

// NEW: 拖移会话鼠标状态（仅鼠标未抬起时不结束交互）
let isMouseDown = false;
let zrMouseDownHandler = () => {
  isMouseDown = true;
};
let zrMouseUpHandler = () => {
  isMouseDown = false;
  try {
    renderHub.endInteraction("main");
  } catch {}
};
let winMouseUpHandler = () => {
  isMouseDown = false;
  try {
    renderHub.endInteraction("main");
  } catch {}
};

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

/* REFACTORED: 一次性装配渲染（消费 hub 预构建的 option） */
function doSinglePassRender(snapshot) {
  try {
    if (!chart || !snapshot) return;
    const mySeq = ++renderSeq;

    if (renderHub.isInteracting()) {
      return;
    }

    const finalOption = snapshot.main?.option;
    if (!finalOption) return;

    // 程序化 dataZoom 守护
    const initialRange = snapshot.main.range;
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

    // 更新顶栏预览文案
    const sIdx = initialRange.startValue;
    const eIdx = initialRange.endValue;
    const arr = vm.candles.value || [];
    previewStartStr.value = arr[sIdx]?.t || "";
    previewEndStr.value = arr[eIdx]?.t || "";
    previewBarsCount.value = Math.max(1, eIdx - sIdx + 1);
  } catch (e) {
    console.error("MainChartPanel render error:", e);
  }
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
      const list = vm.candles.value || [];
      const len = list.length;
      if (!len) return;

      let idx = -1;

      const sd = Array.isArray(params?.seriesData)
        ? params.seriesData.find((x) => Number.isFinite(x?.dataIndex))
        : null;
      if (sd && Number.isFinite(sd.dataIndex)) {
        idx = sd.dataIndex;
      } else {
        const xInfo = Array.isArray(params?.axesInfo)
          ? params.axesInfo.find((ai) => ai && ai.axisDim === "x")
          : null;
        const v = xInfo?.value;

        if (Number.isFinite(v)) {
          idx = Math.max(0, Math.min(len - 1, Number(v)));
        } else if (typeof v === "string" && v) {
          const dates = list.map((d) => d.t);
          idx = dates.indexOf(v);
        } else {
          const b0 = Array.isArray(params?.batch)
            ? params.batch.find((b) => Number.isFinite(b?.dataIndex))
            : null;
          if (b0 && Number.isFinite(b0.dataIndex)) {
            idx = Math.max(0, Math.min(len - 1, Number(b0.dataIndex)));
          }
        }
      }

      if (idx < 0 || idx >= len) return;
      const tIso = list[idx]?.t;
      const tsVal = tIso ? Date.parse(tIso) : NaN;
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

  // —— 订阅 useViewRenderHub：移到 chart.init 完成后（必要调序    —— //
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
    if (![ys, ms, ds, ye, me, de].every(Number.isFinite)) return;

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

    if (![ys, ms, ds, hs, mins, ye, me, de, he, mine].every(Number.isFinite))
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
