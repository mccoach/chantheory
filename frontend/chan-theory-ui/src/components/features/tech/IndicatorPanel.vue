<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\tech\IndicatorPanel.vue -->
<!-- ============================== -->
<!-- 合并版 IndicatorPanel：既可渲染 成交量/成交额，也可渲染 MACD/KDJ/RSI/BOLL/OFF
     - 统一右上角关闭按钮（沿用原指标窗）
     - 统一左上角下拉选择（在指标项之前插入 成交量、成交额）
     - 右侧边悬浮拖动把手（仅悬停显示，拖动可排序；向父级发出 dragstart/dragend）
     - 双击打开设置窗：VOL/AMOUNT → 量窗设置；MACD/KDJ/RSI/BOLL → 统一指标设置（使用 SettingsGrid）
     - 统一顶栏标题：标的名称/代码/频率/来源/复权（参照主窗）
     - 保持与 ECharts 组联动（ct-sync）、横轴竖线对齐、dataZoom 交互会后承接
     - NEW: 使用 SettingsGrid 实现指标窗设置 UI（参照 MainChartSettingsContent 的写法）
-->
<template>
  <div
    ref="wrap"
    class="chart"
    @dblclick="openSettingsDialog"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
  >
    <div class="top-info">
      <select
        class="sel-kind"
        v-model="kindLocal"
        @change="onKindChange"
        title="选择副窗内容"
      >
        <option value="VOL">成交量</option>
        <option value="AMOUNT">成交额</option>
        <option value="MACD">MACD</option>
        <option value="KDJ">KDJ</option>
        <option value="RSI">RSI</option>
        <option value="BOLL">BOLL</option>
        <option value="OFF">OFF</option>
      </select>
      <div class="title">{{ displayTitle }}</div>
      <button
        class="btn-close"
        @click="$emit('close')"
        title="关闭此窗"
        aria-label="关闭"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
          <defs>
            <linearGradient id="gcx" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#3a3a3a" />
              <stop offset="1" stop-color="#242424" />
            </linearGradient>
          </defs>
          <rect
            x="2.5"
            y="2.5"
            rx="6"
            ry="6"
            width="19"
            height="19"
            fill="url(#gcx)"
            stroke="#8b8b8b"
            stroke-width="1"
          />
          <path
            d="M8 8 L16 16"
            stroke="#e6e6e6"
            stroke-width="1.8"
            stroke-linecap="round"
          />
          <path
            d="M16 8 L8 16"
            stroke="#e6e6e6"
            stroke-width="1.8"
            stroke-linecap="round"
          />
        </svg>
      </button>
    </div>

    <div ref="host" class="canvas-host"></div>

    <!-- 右侧悬浮拖动把手（仅悬停显示） -->
    <div
      class="drag-handle"
      draggable="true"
      title="拖动以调整顺序"
      @dragstart="onDragHandleStart"
      @dragend="onDragHandleEnd"
    >
      <div class="grip"></div>
    </div>

    <!-- 底部高度拖拽条 -->
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
  nextTick,
  computed,
  defineComponent,
  h,
  reactive,
} from "vue";
import * as echarts from "echarts";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { buildVolumeOption } from "@/charts/options";
import { DEFAULT_VOL_SETTINGS, UI_LIMITS, MARKER_SHAPE_OPTIONS, LINE_STYLES } from "@/constants";
import SettingsGrid from "@/components/ui/SettingsGrid.vue";

// props / emits
const props = defineProps({
  id: { type: [String, Number], required: true },
  kind: { type: String, default: "MACD" },
});
const emit = defineEmits(["update:kind", "close", "dragstart", "dragend"]);

// 注入
const vm = inject("marketView");
const hub = useViewCommandHub();
const renderHub = useViewRenderHub();
const settings = useUserSettings();
const { findBySymbol } = useSymbolIndex();
const dialogManager = inject("dialogManager");

// 渲染序号守护
let renderSeq = 0;
function isStale(seq) {
  return seq !== renderSeq;
}

// DOM / 实例
const wrap = ref(null);
const host = ref(null);
let chart = null;
let ro = null;

// 悬浮状态上报（合并后副窗统一使用 indicator key）
function onMouseEnter() {
  renderHub.setHoveredPanel("indicator");
}
function onMouseLeave() {
  renderHub.setHoveredPanel(null);
}

// 尺寸安全 resize
function safeResize() {
  if (!chart || !host.value) return;
  const seq = renderSeq;
  requestAnimationFrame(() => {
    if (isStale(seq)) return;
    try {
      chart.resize({
        width: host.value.clientWidth,
        height: host.value.clientHeight,
      });
    } catch {}
  });
}

// 选择种类
const kindLocal = ref(props.kind.toUpperCase());
watch(
  () => props.kind,
  (v) => {
    kindLocal.value = String(v || "MACD").toUpperCase();
  }
);
function onKindChange() {
  emit("update:kind", kindLocal.value);
  // NEW: 选完立即重绘当前副窗（不等待快照）
  try {
    const opt = renderHub.getIndicatorOption(kindLocal.value);
    if (opt && chart) {
      chart.setOption(opt, { notMerge: true, silent: true });
    }
  } catch (e) {
    console.warn("indicator immediate refresh failed:", e);
  }
}

// 顶栏标题（参照主窗：名称/代码/频率/来源/复权）
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
function updateHeaderFromCurrent() {
  const sym = (vm.meta.value?.symbol || vm.code.value || "").trim();
  const frq = String(vm.meta.value?.freq || vm.freq.value || "").trim();
  let name = "";
  try {
    name = findBySymbol(sym)?.name?.trim() || "";
  } catch {}
  displayHeader.value = { name, code: sym, freq: frq };
}

// 设置窗：两套逻辑（VOL/AMOUNT 使用量窗设置；指标类占位说明）
function openSettingsDialog() {
  const K = String(kindLocal.value || "").toUpperCase();
  if (K === "VOL" || K === "AMOUNT") {
    openVolSettingsDialog();
  } else {
    const IndicatorSettingsContent = defineComponent({
      setup() {
        return () =>
          h(
            "div",
            { class: "settings-hint" },
            "当前指标窗暂无更多设置项，后续版本将开放参数配置。"
          );
      },
    });
    dialogManager.open({
      title: `${K} 指标设置`,
      contentComponent: IndicatorSettingsContent,
      onSave: () => {
        hub.execute("Refresh", {});
        dialogManager.close();
      },
      onClose: () => dialogManager.close(),
    });
  }
}

// —— 量窗设置（复用原 VolumePanel 的设置 UI，移除顶部“量/额模式”切换，模式由下拉 VOL/AMOUNT 控制，不写回 settings.mode） —— //
const settingsDraftVol = reactive({
  volBar: { ...DEFAULT_VOL_SETTINGS.volBar },
  mavolForm: {
    MAVOL5: {
      enabled: true,
      period: 5,
      width: 1,
      style: "solid",
      color: "#ee6666",
    },
    MAVOL10: {
      enabled: true,
      period: 10,
      width: 1,
      style: "solid",
      color: "#fac858",
    },
    MAVOL20: {
      enabled: true,
      period: 20,
      width: 1,
      style: "solid",
      color: "#5470c6",
    },
  },
  markerPump: { ...DEFAULT_VOL_SETTINGS.markerPump },
  markerDump: { ...DEFAULT_VOL_SETTINGS.markerDump },
});
const draftRev = ref(0);
const resetAllTickVol = ref(0);

const VolumeSettingsContent = defineComponent({
  setup() {
    // ========== 保留：快照与三态逻辑（均线总控） ========== //
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

    function getMavolKeys() {
      return Object.keys(settingsDraftVol.mavolForm || {});
    }
    function getCurrentMavolCombination() {
      const combo = {};
      for (const k of getMavolKeys()) {
        combo[k] = !!settingsDraftVol.mavolForm?.[k]?.enabled;
      }
      return combo;
    }
    const mavolLastManualSnapshot = ref(getCurrentMavolCombination());
    const mavolGlobalCycleIndex = ref(0);

    function primeMavolGlobalCycle() {
      const snap = mavolLastManualSnapshot.value || {};
      const ks = getMavolKeys();
      const allOnNow = ks.length > 0 && ks.every((k) => !!snap[k]);
      mavolGlobalCycleIndex.value = allOnNow ? 1 : 0;
    }
    primeMavolGlobalCycle();

    function isAllMavolOn(combo) {
      const ks = getMavolKeys();
      return ks.length > 0 && ks.every((k) => combo[k] === true);
    }
    function isAllMavolOff(combo) {
      const ks = getMavolKeys();
      return ks.length > 0 && ks.every((k) => combo[k] === false);
    }
    function mavolStatesForGlobalToggle() {
      const snap = mavolLastManualSnapshot.value || {};
      if (isAllMavolOn(snap) || isAllMavolOff(snap)) {
        return ["allOn", "allOff"];
      }
      return ["allOn", "allOff", "snapshot"];
    }
    function applyMavolGlobalState(stateKey) {
      const ks = getMavolKeys();
      if (!ks.length) return;
      if (stateKey === "allOn") {
        for (const k of ks) {
          if (!settingsDraftVol.mavolForm[k]) settingsDraftVol.mavolForm[k] = {};
          settingsDraftVol.mavolForm[k].enabled = true;
        }
        return;
      }
      if (stateKey === "allOff") {
        for (const k of ks) {
          if (!settingsDraftVol.mavolForm[k]) settingsDraftVol.mavolForm[k] = {};
          settingsDraftVol.mavolForm[k].enabled = false;
        }
        return;
      }
      if (stateKey === "snapshot") {
        const snap = mavolLastManualSnapshot.value || {};
        for (const k of ks) {
          if (!settingsDraftVol.mavolForm[k]) settingsDraftVol.mavolForm[k] = {};
          settingsDraftVol.mavolForm[k].enabled = !!snap[k];
        }
        return;
      }
    }
    function mavolGlobalUi() {
      const cur = getCurrentMavolCombination();
      return {
        checked: isAllMavolOn(cur),
        indeterminate: !isAllMavolOn(cur) && !isAllMavolOff(cur),
      };
    }
    function onMavolGlobalToggle() {
      const states = mavolStatesForGlobalToggle();
      const key = states[mavolGlobalCycleIndex.value % states.length];
      withSnapshotSuppressed("mavol-global", () => applyMavolGlobalState(key));
      mavolGlobalCycleIndex.value = (mavolGlobalCycleIndex.value + 1) % states.length;
    }
    function updateMavolSnapshotFromCurrent() {
      if (!shouldUpdateSnapshot()) return;
      mavolLastManualSnapshot.value = getCurrentMavolCombination();
      mavolGlobalCycleIndex.value = 0;
    }

    watch(resetAllTickVol, () => {
      try {
        mavolLastManualSnapshot.value = getCurrentMavolCombination();
        mavolGlobalCycleIndex.value = 0;
      } catch {}
    });

    // ========== 构造 rows（统一数据结构） ========== //
    function buildRows() {
      const rows = [];

      // 量额柱
      rows.push({
        key: "vol-bar",
        name: "量额柱",
        items: [
          { key: "barPercent", label: "柱宽%" },
          { key: "upColor", label: "阳线颜色" },
          { key: "downColor", label: "阴线颜色" },
        ],
        check: { visible: false }, // 不显示复选
        reset: { visible: true, title: "恢复默认" },
      });

      // 均线总控（三态）
      const maUi = mavolGlobalUi();
      rows.push({
        key: "mavol-global",
        name: "均线总控",
        items: [], // 无额外项
        check: {
          type: "tri",
          checked: maUi.checked,
          indeterminate: maUi.indeterminate,
        },
        reset: { visible: false },
      });

      // MAVOL 三条线
      Object.entries(settingsDraftVol.mavolForm || {}).forEach(([k, conf]) => {
        rows.push({
          key: `mavol-${k}`,
          name: `MAVOL${conf.period}`,
          items: [
            { key: "width", label: "线宽", maKey: k },
            { key: "color", label: "颜色", maKey: k },
            { key: "style", label: "线型", maKey: k },
            { key: "period", label: "周期", maKey: k },
          ],
          check: { type: "single", checked: !!conf.enabled },
          reset: { visible: true, title: "恢复默认" },
        });
      });

      // 放量标记
      rows.push({
        key: "marker-pump",
        name: "放量标记",
        items: [
          { key: "pumpShape", label: "形状" },
          { key: "pumpColor", label: "颜色" },
          { key: "pumpThreshold", label: "阈值" },
        ],
        check: { type: "single", checked: !!settingsDraftVol.markerPump.enabled },
        reset: { visible: true, title: "恢复默认" },
      });

      // 缩量标记
      rows.push({
        key: "marker-dump",
        name: "缩量标记",
        items: [
          { key: "dumpShape", label: "形状" },
          { key: "dumpColor", label: "颜色" },
          { key: "dumpThreshold", label: "阈值" },
        ],
        check: { type: "single", checked: !!settingsDraftVol.markerDump.enabled },
        reset: { visible: true, title: "恢复默认" },
      });

      return rows;
    }

    // ========== 行级事件（切换/重置） ========== //
    function onRowToggle(row) {
      const k = String(row.key || "");
      if (k === "mavol-global") {
        onMavolGlobalToggle();
        return;
      }
      if (k.startsWith("mavol-")) {
        const mk = k.slice(6); // 'mavol-MAVOL5' -> 'MAVOL5'
        const conf = settingsDraftVol.mavolForm[mk];
        if (conf) {
          conf.enabled = !conf.enabled;
          updateMavolSnapshotFromCurrent();
        }
        return;
      }
      if (k === "marker-pump") {
        settingsDraftVol.markerPump.enabled = !settingsDraftVol.markerPump.enabled;
        return;
      }
      if (k === "marker-dump") {
        settingsDraftVol.markerDump.enabled = !settingsDraftVol.markerDump.enabled;
      }
    }

    function onRowReset(row) {
      const k = String(row.key || "");
      if (k === "vol-bar") {
        Object.assign(settingsDraftVol.volBar, DEFAULT_VOL_SETTINGS.volBar);
        draftRev.value++;
        return;
      }
      if (k.startsWith("mavol-")) {
        const mk = k.slice(6);
        const def = DEFAULT_VOL_SETTINGS.mavolStyles[mk];
        if (def) {
          settingsDraftVol.mavolForm[mk] = { ...def };
          updateMavolSnapshotFromCurrent();
          draftRev.value++;
        }
        return;
      }
      if (k === "marker-pump") {
        settingsDraftVol.markerPump = { ...DEFAULT_VOL_SETTINGS.markerPump };
        draftRev.value++;
        return;
      }
      if (k === "marker-dump") {
        settingsDraftVol.markerDump = { ...DEFAULT_VOL_SETTINGS.markerDump };
        draftRev.value++;
      }
    }

    // ========== 控件槽位渲染（renderControl） ========== //
    function renderControl({ row, item }) {
      const k = String(row.key || "");
      const id = String(item.key || "");

      // 量额柱
      if (k === "vol-bar") {
        if (id === "barPercent") {
          return h("input", {
            class: "input num",
            type: "number",
            min: UI_LIMITS.barWidthPercent.min,
            max: UI_LIMITS.barWidthPercent.max,
            step: UI_LIMITS.barWidthPercent.step,
            value: Number(settingsDraftVol.volBar.barPercent ?? 100),
            onInput: (e) =>
              (settingsDraftVol.volBar.barPercent = Math.max(
                UI_LIMITS.barWidthPercent.min,
                Math.min(UI_LIMITS.barWidthPercent.max, Math.round(+e.target.value || 100))
              )),
          });
        }
        if (id === "upColor") {
          return h("input", {
            class: "input color",
            type: "color",
            value: settingsDraftVol.volBar.upColor || DEFAULT_VOL_SETTINGS.volBar.upColor,
            onInput: (e) => (settingsDraftVol.volBar.upColor = String(e.target.value)),
          });
        }
        if (id === "downColor") {
          return h("input", {
            class: "input color",
            type: "color",
            value: settingsDraftVol.volBar.downColor || DEFAULT_VOL_SETTINGS.volBar.downColor,
            onInput: (e) => (settingsDraftVol.volBar.downColor = String(e.target.value)),
          });
        }
      }

      // MAVOL 行
      if (k.startsWith("mavol-")) {
        const mk = k.slice(6);
        const conf = settingsDraftVol.mavolForm[mk] || {};
        if (id === "width") {
          return h("input", {
            class: "input num",
            type: "number",
            min: UI_LIMITS.lineWidth.min,
            max: UI_LIMITS.lineWidth.max,
            step: UI_LIMITS.lineWidth.step,
            value: Number(conf.width ?? 1),
            onInput: (e) => (settingsDraftVol.mavolForm[mk].width = Number(e.target.value || 1)),
          });
        }
        if (id === "color") {
          return h("input", {
            class: "input color",
            type: "color",
            value: conf.color || DEFAULT_VOL_SETTINGS.mavolStyles[mk]?.color,
            onInput: (e) => (settingsDraftVol.mavolForm[mk].color = String(e.target.value)),
          });
        }
        if (id === "style") {
          return h(
            "select",
            {
              class: "input",
              value: conf.style || "solid",
              onChange: (e) => (settingsDraftVol.mavolForm[mk].style = String(e.target.value)),
            },
            LINE_STYLES.map(opt => h("option", { value: opt.v }, opt.label))
          );
        }
        if (id === "period") {
          return h("input", {
            class: "input num",
            type: "number",
            min: UI_LIMITS.positiveInteger.min,
            step: UI_LIMITS.positiveInteger.step,
            value: Number(conf.period ?? 5),
            onInput: (e) =>
              (settingsDraftVol.mavolForm[mk].period = Math.max(
                UI_LIMITS.positiveInteger.min,
                parseInt(e.target.value || 5, 10)
              )),
          });
        }
      }

      // 放量标记
      if (k === "marker-pump") {
        if (id === "pumpShape") {
          return h(
            "select",
            {
              class: "input",
              value: settingsDraftVol.markerPump.shape || DEFAULT_VOL_SETTINGS.markerPump.shape,
              onChange: (e) => (settingsDraftVol.markerPump.shape = String(e.target.value)),
            },
            MARKER_SHAPE_OPTIONS.map(opt => h("option", { value: opt.v }, opt.label))
          );
        }
        if (id === "pumpColor") {
          return h("input", {
            class: "input color",
            type: "color",
            value: settingsDraftVol.markerPump.color || DEFAULT_VOL_SETTINGS.markerPump.color,
            onInput: (e) => (settingsDraftVol.markerPump.color = String(e.target.value)),
          });
        }
        if (id === "pumpThreshold") {
          return h("input", {
            class: "input num",
            type: "number",
            min: UI_LIMITS.nonNegativeFloat.min,
            step: UI_LIMITS.nonNegativeFloat.step,
            value: Number.isFinite(+settingsDraftVol.markerPump.threshold)
              ? +settingsDraftVol.markerPump.threshold
              : DEFAULT_VOL_SETTINGS.markerPump.threshold,
            onInput: (e) =>
              (settingsDraftVol.markerPump.threshold = Math.max(
                UI_LIMITS.nonNegativeFloat.min,
                Number(e.target.value || DEFAULT_VOL_SETTINGS.markerPump.threshold)
              )),
          });
        }
      }

      // 缩量标记
      if (k === "marker-dump") {
        if (id === "dumpShape") {
          return h(
            "select",
            {
              class: "input",
              value: settingsDraftVol.markerDump.shape || DEFAULT_VOL_SETTINGS.markerDump.shape,
              onChange: (e) => (settingsDraftVol.markerDump.shape = String(e.target.value)),
            },
            MARKER_SHAPE_OPTIONS.map(opt => h("option", { value: opt.v }, opt.label))
          );
        }
        if (id === "dumpColor") {
          return h("input", {
            class: "input color",
            type: "color",
            value: settingsDraftVol.markerDump.color || DEFAULT_VOL_SETTINGS.markerDump.color,
            onInput: (e) => (settingsDraftVol.markerDump.color = String(e.target.value)),
          });
        }
        if (id === "dumpThreshold") {
          return h("input", {
            class: "input num",
            type: "number",
            min: UI_LIMITS.nonNegativeFloat.min,
            step: UI_LIMITS.nonNegativeFloat.step,
            value: Number.isFinite(+settingsDraftVol.markerDump.threshold)
              ? +settingsDraftVol.markerDump.threshold
              : DEFAULT_VOL_SETTINGS.markerDump.threshold,
            onInput: (e) =>
              (settingsDraftVol.markerDump.threshold = Math.max(
                UI_LIMITS.nonNegativeFloat.min,
                Number(e.target.value || DEFAULT_VOL_SETTINGS.markerDump.threshold)
              )),
          });
        }
      }

      return null;
    }

    // ========== 渲染函数（使用 SettingsGrid） ========== //
    return () => {
      const rows = buildRows();
      return h(
        SettingsGrid,
        {
          rows,
          itemsPerRow: 5,
          onRowToggle,
          onRowReset,
        },
        {
          control: (slotProps) => renderControl(slotProps),
        }
      );
    };
  },
});

function openVolSettingsDialog() {
  const vs = settings.volSettings.value || {};
  // 量柱
  Object.assign(settingsDraftVol.volBar, {
    barPercent: Math.max(
      10,
      Math.min(
        100,
        Math.round(
          +(vs?.volBar?.barPercent ?? DEFAULT_VOL_SETTINGS.volBar.barPercent)
        )
      )
    ),
    upColor: vs?.volBar?.upColor || DEFAULT_VOL_SETTINGS.volBar.upColor,
    downColor: vs?.volBar?.downColor || DEFAULT_VOL_SETTINGS.volBar.downColor,
  });
  // MAVOL
  const form = {};
  ["MAVOL5", "MAVOL10", "MAVOL20"].forEach((key) => {
    const d = DEFAULT_VOL_SETTINGS.mavolStyles[key];
    const v = (vs.mavolStyles && vs.mavolStyles[key]) || {};
    form[key] = {
      enabled: key in (vs.mavolStyles || {}) ? !!v.enabled : d.enabled,
      width: Number.isFinite(+v.width) ? +v.width : d.width,
      style: v.style || d.style,
      color: v.color || d.color,
      period: Math.max(1, parseInt(v.period != null ? v.period : d.period, 10)),
    };
  });
  settingsDraftVol.mavolForm = form;
  // 放/缩量
  Object.assign(settingsDraftVol.markerPump, {
    enabled: (vs?.markerPump?.enabled ?? true) === true,
    shape: vs?.markerPump?.shape || DEFAULT_VOL_SETTINGS.markerPump.shape,
    color: vs?.markerPump?.color || DEFAULT_VOL_SETTINGS.markerPump.color,
    threshold: Number.isFinite(+vs?.markerPump?.threshold)
      ? +vs.markerPump.threshold
      : DEFAULT_VOL_SETTINGS.markerPump.threshold,
  });
  Object.assign(settingsDraftVol.markerDump, {
    enabled: (vs?.markerDump?.enabled ?? true) === true,
    shape: vs?.markerDump?.shape || DEFAULT_VOL_SETTINGS.markerDump.shape,
    color: vs?.markerDump?.color || DEFAULT_VOL_SETTINGS.markerDump.color,
    threshold: Number.isFinite(+vs?.markerDump?.threshold)
      ? +vs.markerDump.threshold
      : DEFAULT_VOL_SETTINGS.markerDump.threshold,
  });
  draftRev.value++;

  dialogManager.open({
    title: "量窗设置",
    contentComponent: VolumeSettingsContent,
    props: {},
    onResetAll: () => {
      try {
        settingsDraftVol.volBar = { ...DEFAULT_VOL_SETTINGS.volBar };
        settingsDraftVol.mavolForm = JSON.parse(
          JSON.stringify(DEFAULT_VOL_SETTINGS.mavolStyles)
        );
        settingsDraftVol.markerPump = { ...DEFAULT_VOL_SETTINGS.markerPump };
        settingsDraftVol.markerDump = { ...DEFAULT_VOL_SETTINGS.markerDump };
        resetAllTickVol.value++;
        draftRev.value++;
      } catch (e) {
        console.error("resetAll (Volume) failed:", e);
      }
    },
    onSave: () => {
      // 保存样式与标记，不改变全局 mode（由下拉 VOL/AMOUNT 控制）
      const vs0 = settings.volSettings.value || {};
      settings.setVolSettings({
        ...vs0,
        volBar: { ...settingsDraftVol.volBar },
        mavolStyles: { ...settingsDraftVol.mavolForm },
        markerPump: { ...settingsDraftVol.markerPump },
        markerDump: { ...settingsDraftVol.markerDump },
        mode: vs0.mode, // 不改动
      });
      hub.execute("Refresh", {});
      dialogManager.close();
    },
    onClose: () => dialogManager.close(),
  });
}

// dataZoom：会后承接
let dzIdleTimer = null;
const dzIdleDelayMs = 180;

// NEW: 拖移会话鼠标状态（仅鼠标未抬起时不结束交互）
let isMouseDown = false;
let zrMouseDownHandler = () => { isMouseDown = true; };
let zrMouseUpHandler = () => {
  isMouseDown = false;
  try { renderHub.endInteraction(`indicator:${props.id}`); } catch {} 
};
let winMouseUpHandler = () => {
  isMouseDown = false;
  try { renderHub.endInteraction(`indicator:${props.id}`); } catch {} 
};

function onDataZoom(params) {
  try {
    // NEW: 仅对“当前激活的副窗实例”处理 dataZoom；其他实例直接忽略
    const isActive = renderHub.getActiveChart?.() === chart;
    if (!isActive && !isMouseDown) return;

    const info = (params && params.batch && params.batch[0]) || params || {};
    const arr = vm.candles.value || [];
    const len = arr.length;
    if (!len) return;
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
    } else return;
    if (!Number.isFinite(sIdx) || !Number.isFinite(eIdx)) return;
    if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];
    sIdx = Math.max(0, sIdx);
    eIdx = Math.min(len - 1, eIdx);

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

    // 交互开始：带上“实例级源键”（indicator:${id}），避免被其它副窗误终止
    renderHub.beginInteraction(`indicator:${props.id}`);
    if (dzIdleTimer) {
      clearTimeout(dzIdleTimer);
      dzIdleTimer = null;
    }
    dzIdleTimer = setTimeout(() => {
      try {
        const bars_new = Math.max(1, eIdx - sIdx + 1);
        const tsArr = arr.map((d) => Date.parse(d.t));
        const anchorTs = Number.isFinite(tsArr[eIdx])
          ? tsArr[eIdx]
          : hub.getState().rightTs;
        const st = hub.getState();
        const changedBars = bars_new !== Math.max(1, Number(st.barsCount || 1));
        const changedEIdx =
          Number.isFinite(tsArr[eIdx]) && tsArr[eIdx] !== st.rightTs;

        if (changedBars || changedEIdx) {
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
        // 仅在鼠标已抬起时才结束交互；保持拖移不中断
        if (!isMouseDown) {
          renderHub.endInteraction(`indicator:${props.id}`);
        }
      }
    }, dzIdleDelayMs);
  } catch {}
}

onMounted(async () => {
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

  // NEW: 用“实例级键”注册与设为激活，避免多副窗互相覆盖
  try {
    renderHub.registerChart(`indicator:${props.id}`, chart);
    el.addEventListener("mouseenter", () => {
      renderHub.setActivePanel(`indicator:${props.id}`);
    });
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

  chart.on("dataZoom", onDataZoom);

  // ResizeObserver 与首帧 safeResize
  try {
    ro = new ResizeObserver(() => {
      safeResize();
    });
    ro.observe(el);
  } catch {}
  requestAnimationFrame(() => {
    safeResize();
  });

  updateHeaderFromCurrent();
});

// 订阅上游渲染：根据 kind 渲染 VOL/AMOUNT 或指标
const unsubId = renderHub.onRender((snapshot) => {
  try {
    if (!chart) return;
    const mySeq = ++renderSeq;

    const kind = String(kindLocal.value || "").toUpperCase();
    if (kind === "OFF") {
      chart.clear();
      return;
    }

    const notMerge = !renderHub.isInteracting();

    if (kind === "VOL" || kind === "AMOUNT") {
      // 局部构建量窗 option（覆写 mode 为当前下拉选择）
      const candles =
        snapshot?.indicatorsBase?.candles || vm.candles.value || [];
      const indicators =
        snapshot?.indicatorsBase?.indicators || vm.indicators.value || {};
      const freq = snapshot?.indicatorsBase?.freq || vm.freq.value || "1d";
      const volCfg = {
        ...(settings.volSettings.value || {}),
        mode: kind === "AMOUNT" ? "amount" : "vol",
      };
      const vis = Math.max(1, snapshot?.core?.barsCount || 1);
      const option = buildVolumeOption(
        {
          candles,
          indicators,
          freq,
          volCfg,
          volEnv: {
            hostWidth: host.value?.clientWidth || 0,
            visCount: vis,
            overrideMarkWidth: snapshot?.core?.markerWidthPx,
          },
        },
        {
          initialRange: snapshot?.volume?.range || snapshot?.main?.range,
          tooltipPositioner: renderHub.getTipPositioner(),
          isHovered: snapshot?.indicatorsBase?.isHovered,
        }
      );
      chart.setOption(option, { notMerge, silent: true });
    } else {
      const option = renderHub.getIndicatorOption(kindLocal.value);
      if (!option) return;
      chart.setOption(option, { notMerge, silent: true });
    }
  } catch (e) {
    console.error("Unified indicator panel onRender error:", e);
  }
});

onBeforeUnmount(() => {
  renderHub.offRender(unsubId);

  if (ro) {
    try {
      ro.disconnect();
    } catch {}
    ro = null;
  }

  if (chart) {
    try {
      chart.dispose();
    } catch {}
    chart = null;
  }
  try {
    renderHub.unregisterChart("indicator");
  } catch {}
  // NEW: 解除鼠标事件监听
  try {
    const zr = chart && chart.getZr ? chart.getZr() : null;
    zr && zr.off && zr.off("mousedown", zrMouseDownHandler);
    zr && zr.off && zr.off("mouseup", zrMouseUpHandler);
    window.removeEventListener("mouseup", winMouseUpHandler);
  } catch {}
});

// 监听元信息变化以刷新左上标题
watch(
  () => vm.meta.value,
  async () => {
    await nextTick();
    updateHeaderFromCurrent();
  },
  { deep: true }
);

// 右侧拖动把手：向父发出 drag 事件
function onDragHandleStart(e) {
  try {
    e.dataTransfer && e.dataTransfer.setData("text/plain", String(props.id));
  } catch {}
  emit("dragstart");
}
function onDragHandleEnd() {
  emit("dragend");
}

// 底部拖拽高度
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
</script>

<style scoped>
.chart {
  position: relative;
  width: 100%;
  height: 220px;
  background: #111;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  overflow: hidden;
  margin: 0;
}
.top-info {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 28px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  z-index: 5;
  background: linear-gradient(
    to bottom,
    rgba(17, 17, 17, 0.85),
    rgba(17, 17, 17, 0.35),
    rgba(17, 17, 17, 0)
  );
}
.sel-kind {
  height: 22px;
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #8a8a8a;
  border-radius: 6px;
  padding: 0 6px;
}
.title {
  font-size: 13px;
  font-weight: 600;
  color: #ddd;
  user-select: none;
  margin-left: 8px;
}
.btn-close {
  margin-left: auto;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
}

/* 画布区域 */
.canvas-host {
  position: absolute;
  left: 0;
  right: 0;
  top: 28px;
  bottom: 8px;
}

/* 底部高度拖拽条 */
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

/* 右侧悬浮拖动把手（仅在悬停 chart 时显示） */
.drag-handle {
  position: absolute;
  top: 28px;
  bottom: 8px;
  right: 0;
  width: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(
    to left,
    rgba(255, 255, 255, 0.08),
    rgba(255, 255, 255, 0)
  );
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  opacity: 0;
  transition: opacity 120ms ease;
}

.chart:hover .drag-handle {
  opacity: 1;
}

.drag-handle:hover {
  cursor: grab;
  background: linear-gradient(
    to left,
    rgba(255, 255, 255, 0.14),
    rgba(255, 255, 255, 0)
  );
  border-left-color: rgba(255, 255, 255, 0.12);
}

.drag-handle:active {
  cursor: grabbing;
}

.drag-handle .grip {
  width: 4px;
  height: 40%;
  border-radius: 2px;
  background-image: radial-gradient(#bfbfbf 1px, transparent 1px);
  background-size: 4px 6px;
  background-position: center;
  opacity: 0.7;
}

/* 指标设置占位提示 */
.settings-hint {
  color: #bbb;
  font-size: 13px;
  padding: 4px 2px;
}
</style>
