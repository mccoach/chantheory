<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\tech\VolumePanel.vue -->
<!-- ============================== -->
<!-- 量窗（统一使用“唯一权威符号宽度广播” chan:marker-size；不自估宽度） -->
<!-- 本次重构： -->
<!-- - 保持本窗不作为交互源（inside-only），不更改 bars/rightTs；仅订阅事件以应用统一宽度。 -->
<!-- - 不扩范围：保留现有逻辑与顺序，新增注释说明中枢化策略；构造 option 时传入 overrideMarkWidth。 -->

<template>
  <div ref="wrap" class="chart" @dblclick="openSettingsDialog">
    <div class="top-info">
      <div class="seg">
        <button
          class="seg-btn"
          :class="{ active: mode === 'vol' }"
          title="图形切换为成交量"
          @click="switchMode('vol')"
        >
          量
        </button>
        <button
          class="seg-btn"
          :class="{ active: mode === 'amount' }"
          title="图形切换为成交额"
          @click="switchMode('amount')"
        >
          额
        </button>
      </div>
      <div class="title">{{ displayTitle }}</div>
      <div class="stats">
        <span class="kv">可见总{{ modeLabel }}: {{ stat.total }}</span>
        <span class="kv">均值: {{ stat.mean }}</span>
        <span class="kv">最大: {{ stat.max }}</span>
        <span class="kv">放量天数: {{ stat.pumpDays }}</span>
        <span class="kv">连续缩量: {{ stat.maxConsecDump }}</span>
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
  nextTick,
  computed,
  defineComponent,
  h,
  reactive,
} from "vue";
import * as echarts from "echarts";
import { buildVolumeOption, zoomSync } from "@/charts/options";
import { useUserSettings } from "@/composables/useUserSettings";
import { DEFAULT_VOL_SETTINGS } from "@/constants";
import { vSelectAll } from "@/utils/inputBehaviors";
import { useSymbolIndex } from "@/composables/useSymbolIndex";

defineOptions({ directives: { selectAll: vSelectAll } });

const vm = inject("marketView");
const settings = useUserSettings();
const { findBySymbol } = useSymbolIndex();
const dialogManager = inject("dialogManager");

// —— 统一标记宽度来源：仅订阅全局事件 chan:marker-size（保持项目不变量） —— //
const overrideMarkWidth = ref(null);
function onMarkerSize(ev) {
  try {
    const px = Number(ev?.detail?.px);
    if (Number.isFinite(px) && px > 0) overrideMarkWidth.value = px;
  } catch {}
}
onMounted(() => {
  window.addEventListener("chan:marker-size", onMarkerSize);
});
onBeforeUnmount(() => {
  window.removeEventListener("chan:marker-size", onMarkerSize);
});

// —— NEW: 宽度一旦变化，立即重绘 —— //
// 原因：buildVolumeOption 中的 symbolSize 闭包捕获了当前宽度值；若不重建 option，ECharts 不会重新取新的宽度。
watch(
  () => overrideMarkWidth.value,
  () => {
    try {
      render();
    } catch (e) {
      console.error("VolumePanel: re-render on marker size change failed:", e);
    }
  }
);

let renderSeq = 0;
function isStale(seq) {
  return seq !== renderSeq;
}

// hover 跨窗体广播（保持原逻辑）
function broadcastHoverIndex(idx) {
  try {
    window.dispatchEvent(
      new CustomEvent("chan:hover-index", { detail: { idx: Number(idx) } })
    );
  } catch {}
}

const wrap = ref(null);
const host = ref(null);
let chart = null;
let ro = null;
let detachSync = null;

const displayHeader = ref({ name: "", code: "", freq: "" });
const displayTitle = computed(() => {
  const n = displayHeader.value.name || "",
    c = displayHeader.value.code || vm.code.value || "",
    f = displayHeader.value.freq || vm.freq.value || "";
  return n ? `${n}（${c}）：${f}` : `${c}：${f}`;
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

const stat = ref({
  total: "-",
  mean: "-",
  max: "-",
  pumpDays: 0,
  maxConsecDump: 0,
});
const mode = ref(settings.volSettings.value.mode);
const modeLabel = ref(mode.value === "amount" ? "额" : "量");
function switchMode(next) {
  const m = next === "amount" ? "amount" : "vol";
  settings.patchVolSettings({ mode: m });
  mode.value = m;
  modeLabel.value = m === "amount" ? "额" : "量";
}

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
const VolumeSettingsContent = defineComponent({
  setup() {
    const nameCell = (t) => h("div", { class: "std-name" }, t);
    const itemCell = (label, input) =>
      h("div", { class: "std-item" }, [
        h("div", { class: "std-item-label" }, label),
        h("div", { class: "std-item-input" }, [input]),
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
          onClick,
          type: "button",
        }),
      ]);
    return () => {
      const rows = [];
      const vb = settingsDraftVol.volBar;
      rows.push(
        h("div", { class: "std-row", key: `volbar-${draftRev.value}` }, [
          nameCell("量额柱"),
          itemCell(
            "柱宽%",
            h("input", {
              class: "input num",
              type: "number",
              min: 10,
              max: 100,
              step: 1,
              value: Number(vb.barPercent ?? 100),
              onInput: (e) =>
                (settingsDraftVol.volBar.barPercent = Math.max(
                  10,
                  Math.min(100, Math.round(+e.target.value || 100))
                )),
            })
          ),
          itemCell(
            "阳线颜色",
            h("input", {
              class: "input color",
              type: "color",
              value: vb.upColor || "#ef5350",
              onInput: (e) =>
                (settingsDraftVol.volBar.upColor = String(
                  e.target.value || "#ef5350"
                )),
            })
          ),
          itemCell(
            "阴线颜色",
            h("input", {
              class: "input color",
              type: "color",
              value: vb.downColor || "#26a69a",
              onInput: (e) =>
                (settingsDraftVol.volBar.downColor = String(
                  e.target.value || "#26a69a"
                )),
            })
          ),
          h("div"),
          h("div"),
          h("div", { class: "std-check" }),
          resetBtn(() => {
            Object.assign(settingsDraftVol.volBar, DEFAULT_VOL_SETTINGS.volBar);
            draftRev.value++;
          }),
        ])
      );
      Object.entries(settingsDraftVol.mavolForm).forEach(([k, conf]) => {
        rows.push(
          h("div", { class: "std-row", key: `mrow-${k}-${draftRev.value}` }, [
            nameCell(`MAVOL${conf.period}`),
            itemCell(
              "线宽",
              h("input", {
                class: "input num",
                type: "number",
                min: 0.5,
                max: 4,
                step: 0.5,
                value: Number(conf.width ?? 1),
                onInput: (e) => (conf.width = Number(e.target.value || 1)),
              })
            ),
            itemCell(
              "颜色",
              h("input", {
                class: "input color",
                type: "color",
                value: conf.color || "#ee6666",
                onInput: (e) =>
                  (conf.color = String(e.target.value || "#ee6666")),
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
              const def = DEFAULT_VOL_SETTINGS.mavolStyles[k];
              if (def) {
                settingsDraftVol.mavolForm[k] = { ...def };
                draftRev.value++;
              }
            }),
          ])
        );
      });
      rows.push(
        h("div", { class: "std-row", key: `pump-${draftRev.value}` }, [
          nameCell("放量标记"),
          itemCell(
            "形状",
            h(
              "select",
              {
                class: "input",
                value:
                  settingsDraftVol.markerPump.shape ||
                  DEFAULT_VOL_SETTINGS.markerPump.shape,
                onChange: (e) =>
                  (settingsDraftVol.markerPump.shape = String(e.target.value)),
              },
              [
                h("option", "triangle"),
                h("option", "diamond"),
                h("option", "circle"),
                h("option", "rect"),
              ]
            )
          ),
          itemCell(
            "颜色",
            h("input", {
              class: "input color",
              type: "color",
              value:
                settingsDraftVol.markerPump.color ||
                DEFAULT_VOL_SETTINGS.markerPump.color,
              onInput: (e) =>
                (settingsDraftVol.markerPump.color = String(e.target.value)),
            })
          ),
          itemCell(
            "阈值",
            h("input", {
              class: "input num",
              type: "number",
              min: 0.1,
              step: 0.1,
              value: Number.isFinite(+settingsDraftVol.markerPump.threshold)
                ? +settingsDraftVol.markerPump.threshold
                : DEFAULT_VOL_SETTINGS.markerPump.threshold,
              onInput: (e) =>
                (settingsDraftVol.markerPump.threshold = Math.max(
                  0.1,
                  Number(
                    e.target.value || DEFAULT_VOL_SETTINGS.markerPump.threshold
                  )
                )),
            })
          ),
          h("div"),
          h("div"),
          checkCell(
            !!settingsDraftVol.markerPump.enabled,
            (e) => (settingsDraftVol.markerPump.enabled = !!e.target.checked)
          ),
          resetBtn(() => {
            settingsDraftVol.markerPump = {
              ...DEFAULT_VOL_SETTINGS.markerPump,
            };
            draftRev.value++;
          }),
        ])
      );
      rows.push(
        h("div", { class: "std-row", key: `dump-${draftRev.value}` }, [
          nameCell("缩量标记"),
          itemCell(
            "形状",
            h(
              "select",
              {
                class: "input",
                value:
                  settingsDraftVol.markerDump.shape ||
                  DEFAULT_VOL_SETTINGS.markerDump.shape,
                onChange: (e) =>
                  (settingsDraftVol.markerDump.shape = String(e.target.value)),
              },
              [
                h("option", "triangle"),
                h("option", "diamond"),
                h("option", "circle"),
                h("option", "rect"),
              ]
            )
          ),
          itemCell(
            "颜色",
            h("input", {
              class: "input color",
              type: "color",
              value:
                settingsDraftVol.markerDump.color ||
                DEFAULT_VOL_SETTINGS.markerDump.color,
              onInput: (e) =>
                (settingsDraftVol.markerDump.color = String(e.target.value)),
            })
          ),
          itemCell(
            "阈值",
            h("input", {
              class: "input num",
              type: "number",
              min: 0.1,
              step: 0.1,
              value: Number.isFinite(+settingsDraftVol.markerDump.threshold)
                ? +settingsDraftVol.markerDump.threshold
                : DEFAULT_VOL_SETTINGS.markerDump.threshold,
              onInput: (e) =>
                (settingsDraftVol.markerDump.threshold = Math.max(
                  0.1,
                  Number(
                    e.target.value || DEFAULT_VOL_SETTINGS.markerDump.threshold
                  )
                )),
            })
          ),
          h("div"),
          h("div"),
          checkCell(
            !!settingsDraftVol.markerDump.enabled,
            (e) => (settingsDraftVol.markerDump.enabled = !!e.target.checked)
          ),
          resetBtn(() => {
            settingsDraftVol.markerDump = {
              ...DEFAULT_VOL_SETTINGS.markerDump,
            };
            draftRev.value++;
          }),
        ])
      );
      return h("div", { key: `vol-settings-root-${draftRev.value}` }, rows);
    };
  },
});
function openSettingsDialog() {
  const vs = settings.volSettings.value || {};
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
        draftRev.value++;
      } catch (e) {
        console.error("resetAll (Volume) failed:", e);
      }
    },
    onSave: () => {
      settings.setVolSettings({
        ...vs,
        volBar: { ...settingsDraftVol.volBar },
        mavolStyles: { ...settingsDraftVol.mavolForm },
        markerPump: { ...settingsDraftVol.markerPump },
        markerDump: { ...settingsDraftVol.markerDump },
      });
      dialogManager.close();
    },
    onClose: () => dialogManager.close(),
  });
}

function onDataZoom(_params) {
  // 副窗不作为交互源；仅主图触发 setBars，副窗跟随 meta（避免循环）
  return;
}

function applyZoomByMeta(seq) {
  if (!chart) return;
  if (isStale(seq)) return;
  const len = (vm.candles.value || []).length;
  if (!len) return;
  const sIdx = Number(vm.meta.value?.view_start_idx ?? 0);
  const eIdx = Number(vm.meta.value?.view_end_idx ?? len - 1);

  const delta = {
    dataZoom: [{ type: "inside", startValue: sIdx, endValue: eIdx }],
  };

  try {
    if (isStale(seq)) return;
    chart.dispatchAction({ type: "hideTip" });
  } catch {}
  chart.setOption(delta, { notMerge: false, lazyUpdate: true, silent: true });
}

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
  chart.getZr().on("mousemove", (e) => {
    try {
      const point = [e.offsetX, e.offsetY];
      const result = chart.convertFromPixel({ seriesIndex: 0 }, point);
      if (Array.isArray(result)) {
        const idx = Math.round(result[0]);
        const l = (vm.candles.value || []).length;
        if (Number.isFinite(idx) && idx >= 0 && idx < l) {
          broadcastHoverIndex(idx);
        }
      }
    } catch {}
  });
  chart.on("updateAxisPointer", (params) => {
    try {
      const axisInfo = (params?.axesInfo && params.axesInfo[0]) || null;
      const label = axisInfo?.value;
      const dates = (vm.candles.value || []).map((d) => d.t);
      const idx = dates.indexOf(label);
      if (idx >= 0) {
        broadcastHoverIndex(idx);
      }
    } catch {}
  });
  chart.on("dataZoom", onDataZoom);
  try {
    ro = new ResizeObserver(() => {
      safeResize();
    });
    ro.observe(el);
  } catch {}
  requestAnimationFrame(() => {
    safeResize();
  });
  detachSync = zoomSync.attach(
    "volume",
    chart,
    () => (vm.candles.value || []).length
  );
  render();
  updateHeaderFromCurrent();
});

onBeforeUnmount(() => {
  try {
    ro && ro.disconnect();
  } catch {}
  ro = null;
  try {
    detachSync && detachSync();
  } catch {}
  detachSync = null;
  try {
    chart && chart.dispose();
  } catch {}
  chart = null;
});

function render() {
  if (!chart) return;
  const mySeq = ++renderSeq;

  const option = buildVolumeOption(
    {
      candles: vm.candles.value,
      indicators: vm.indicators.value,
      freq: vm.freq.value,
      volCfg: settings.volSettings.value,
      volEnv: {
        hostWidth: host.value ? host.value.clientWidth : 0,
        visCount: Number(vm.meta.value?.view_rows || 1),
        overrideMarkWidth: overrideMarkWidth.value, // —— 统一宽度来源（事件） —— //
      },
    },
    {}
  );

  if (isStale(mySeq)) return;
  chart.setOption(option, true);
  applyZoomByMeta(mySeq);
  recomputeVisibleStats(mySeq);
  updateHeaderFromCurrent();
}

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
function recomputeVisibleStats(seq) {
  if (isStale(seq)) return;
  try {
    const range = getCurrentZoomIndexRange();
    const len = (vm.candles.value || []).length;
    if (!len || !range) {
      stat.value = {
        total: "-",
        mean: "-",
        max: "-",
        pumpDays: 0,
        maxConsecDump: 0,
      };
      return;
    }
    const { sIdx, eIdx } = range;
    const isAmount = (settings.volSettings.value?.mode || "vol") === "amount";
    const baseSeries = isAmount
      ? (vm.candles.value || []).map((d) =>
          typeof d.a === "number" ? d.a : null
        )
      : vm.indicators.value?.VOLUME ||
        (vm.candles.value || []).map((d) =>
          typeof d.v === "number" ? d.v : null
        );
    let sum = 0,
      cnt = 0,
      mx = 0;
    for (let i = sIdx; i <= eIdx; i++) {
      const v = Number(baseSeries[i]);
      if (Number.isFinite(v)) {
        sum += v;
        cnt += 1;
        if (v > mx) mx = v;
      }
    }
    const mean = cnt > 0 ? sum / cnt : 0;
    const fmt0 = (x) => (Number.isFinite(+x) ? (+x).toFixed(0) : "-");
    if (isStale(seq)) return;
    stat.value = {
      total: fmt0(sum),
      mean: fmt0(mean),
      max: fmt0(mx),
      pumpDays: 0,
      maxConsecDump: 0,
    };
  } catch {
    if (isStale(seq)) return;
    stat.value = {
      total: "-",
      mean: "-",
      max: "-",
      pumpDays: 0,
      maxConsecDump: 0,
    };
  }
}

watch(
  () => [
    vm.candles.value,
    vm.indicators.value,
    vm.freq.value,
    settings.volSettings.value,
  ],
  () => render(),
  { deep: true }
);
watch(
  () => vm.meta.value,
  async () => {
    await nextTick();
    const mySeq = ++renderSeq;
    applyZoomByMeta(mySeq);
    updateHeaderFromCurrent();
  },
  { deep: true }
);

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
    try {
      const seq = renderSeq;
      chart &&
        chart.resize({
          width: host.value.clientWidth,
          height: host.value.clientHeight,
        });
      if (!isStale(seq)) render();
    } catch {}
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
  height: 24vh;
  min-height: 160px;
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
  gap: 10px;
  padding: 0 8px;
  z-index: 5;
  background: linear-gradient(
    to bottom,
    rgba(17, 17, 17, 0.85),
    rgba(17, 17, 17, 0.35),
    rgba(17, 17, 17, 0)
  );
}
.seg {
  display: inline-flex;
  align-items: center;
  border: 1px solid #444;
  border-radius: 8px;
  overflow: hidden;
  background: #1a1a1a;
}
.seg-btn {
  background: transparent;
  color: #ddd;
  border: none;
  padding: 3px 10px;
  cursor: pointer;
  user-select: none;
  font-size: 12px;
  line-height: 1;
  height: 22px;
  border-radius: 0;
}
.seg-btn + .seg-btn {
  border-left: 1px solid #444;
}
.seg-btn.active {
  background: #2b4b7e;
  color: #fff;
}
.title {
  font-size: 13px;
  font-weight: 600;
  color: #ddd;
  user-select: none;
}
.stats {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
  color: #bbb;
  font-size: 12px;
}
.stats .kv {
  white-space: nowrap;
}
.canvas-host {
  position: absolute;
  left: 0;
  right: 0;
  top: 28px;
  bottom: 8px;
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
