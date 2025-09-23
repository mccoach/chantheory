<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\tech\IndicatorPanel.vue -->
<!-- 全量输出：指标窗（UI 序号守护覆盖式防抖 + 跨窗体 hover 广播） -->
<template>
  <div ref="wrap" class="chart" @dblclick="openSettingsDialog">
    <div class="top-info">
      <select
        class="sel-kind"
        v-model="kindLocal"
        @change="onKindChange"
        title="选择指标"
      >
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
} from "vue";
import * as echarts from "echarts";
import {
  buildKdjOrRsiOption,
  buildMacdOption,
  zoomSync,
} from "@/charts/options";
import { useSymbolIndex } from "@/composables/useSymbolIndex";

const vm = inject("marketView");
const { findBySymbol } = useSymbolIndex();
const dialogManager = inject("dialogManager");

// —— UI 序号守护 —— //
let renderSeq = 0;
function isStale(seq) {
  return seq !== renderSeq;
}

// —— hover 跨窗体广播 —— //
function broadcastHoverIndex(idx) {
  try {
    window.dispatchEvent(
      new CustomEvent("chan:hover-index", { detail: { idx: Number(idx) } })
    );
  } catch {}
}

const props = defineProps({ kind: { type: String, default: "MACD" } });
const emit = defineEmits(["update:kind", "close"]);

const wrap = ref(null);
const host = ref(null);
let chart = null;
let ro = null;
let detachSync = null;
let isProgrammaticZoom = false;

const kindLocal = ref(props.kind);
watch(
  () => props.kind,
  (v) => {
    kindLocal.value = v;
  }
);

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

function openSettingsDialog() {
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
    title: `${String(kindLocal.value).toUpperCase()} 指标设置`,
    contentComponent: IndicatorSettingsContent,
    onSave: () => {
      dialogManager.close();
      render();
    },
    onClose: () => dialogManager.close(),
  });
}
function onKindChange() {
  emit("update:kind", kindLocal.value);
  render();
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
  chart.on("dataZoom", onDataZoom);
  try {
    ro = new ResizeObserver(() => {
      try {
        const seq = renderSeq;
        chart &&
          chart.resize({
            width: host.value.clientWidth,
            height: host.value.clientHeight,
          });
        if (!isStale(seq)) {
          // 可选：不强制 render，以 meta 触发即可
        }
      } catch {}
    });
    ro.observe(el);
  } catch {}
  requestAnimationFrame(() => {
    try {
      chart &&
        chart.resize({
          width: host.value.clientWidth,
          height: host.value.clientHeight,
        });
    } catch {}
  });
  const key = `indicator-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 6)}`;
  detachSync = zoomSync.attach(
    key,
    chart,
    () => (vm.candles.value || []).length
  );

  // —— 广播当前窗体 hover 索引 —— //
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

  render();
  updateHeaderFromCurrent();
});
onBeforeUnmount(() => {
  if (ro) {
    try {
      ro.disconnect();
    } catch {}
    ro = null;
  }
  if (detachSync) {
    try {
      detachSync();
    } catch {}
    detachSync = null;
  }
  if (chart) {
    try {
      chart.dispose();
    } catch {}
    chart = null;
  }
});

function render() {
  if (!chart) return;
  const mySeq = ++renderSeq;

  const data = {
    candles: vm.candles.value,
    indicators: vm.indicators.value,
    freq: vm.freq.value,
  };
  const uiOpts = { tooltipClass: "ct-fixed-tooltip" };
  let option = null;
  const k = String(kindLocal.value || "").toUpperCase();
  if (k === "OFF") {
    chart.clear();
    return;
  }
  if (k === "MACD") option = buildMacdOption(data, uiOpts);
  else if (k === "KDJ")
    option = buildKdjOrRsiOption(
      { ...data, useKDJ: true, useRSI: false },
      uiOpts
    );
  else if (k === "RSI" || k === "BOLL")
    option = buildKdjOrRsiOption(
      { ...data, useKDJ: false, useRSI: true },
      uiOpts
    );
  else
    option = buildKdjOrRsiOption(
      { ...data, useKDJ: false, useRSI: true },
      uiOpts
    );
  option = Object.assign({}, option, {
    axisPointer: {
      show: true,
      type: "cross",
      snap: false,
      link: [{ xAxisIndex: "all" }],
      label: { show: false },
    },
  });

  if (isStale(mySeq)) return;
  chart.setOption(option, true);
  applyZoomByMeta(mySeq);
}
watch(
  () => [vm.candles.value, vm.indicators.value, vm.freq.value, kindLocal.value],
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
  z-index: 2;
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
  background: 透明;
  border: none;
  padding: 0;
  cursor: pointer;
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
  height: 18px;
  background: transparent;
}
.settings-hint {
  color: #bbb;
  font-size: 13px;
  padding: 4px 2px;
}
</style>
