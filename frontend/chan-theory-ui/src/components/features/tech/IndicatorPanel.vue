<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\tech\IndicatorPanel.vue -->
<!-- ============================== -->
<!-- 指标窗（接入统一渲染中枢 · 移除 zoomSync 与 meta watcher）
     - 订阅 useViewRenderHub.onRender(snapshot) 后，调用 renderHub.getIndicatorOption(kind) 构建 option 并一次性 setOption。
     - 不作为交互源；onDataZoom inside-only 并早退。
-->
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
// NEW: 统一渲染中枢
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import { useSymbolIndex } from "@/composables/useSymbolIndex";

const vm = inject("marketView");
const hub = useViewCommandHub();
const renderHub = useViewRenderHub();
const { findBySymbol } = useSymbolIndex();
const dialogManager = inject("dialogManager");

// —— UI 序号守护（保持原逻辑） —— //
let renderSeq = 0;
function isStale(seq) {
  return seq !== renderSeq;
}

// —— hover 跨窗体广播（保持原逻辑） —— //
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
      // MOD: 保存后立即触发刷新（即使当前无可编辑项，保持一致的即时重绘行为）
      hub.execute("Refresh", {});
      dialogManager.close();
    },
    onClose: () => dialogManager.close(),
  });
}
function onKindChange() {
  emit("update:kind", kindLocal.value);
  // 渲染由 renderHub 快照驱动，无需主动 render
}

// —— 副窗不作为交互源（保持原逻辑）：仅 inside 联动，绝不更改 bars/rightTs —— //
function onDataZoom(_params) {
  return;
}

  // 订阅全局 hover，在本窗显示 tooltip/竖线
  function onGlobalHoverIndex(e) {
    try {
      const idx = Number(e?.detail?.idx);
      const arr = vm.candles.value || [];
      if (!chart || !arr.length) return;
      if (!Number.isFinite(idx) || idx < 0 || idx >= arr.length) return;
      chart.dispatchAction({ type: "showTip", dataIndex: idx, seriesIndex: 0 });
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

  // 组内/本窗联动：不再自建广播
  chart.getZr().on("mousemove", (e) => {
  });
  chart.on("updateAxisPointer", (params) => {
  });

  // 仍保留订阅：响应“非鼠标触发”的统一广播（如键盘左右）
    window.addEventListener("chan:hover-index", onGlobalHoverIndex);

  updateHeaderFromCurrent();
});

// 订阅上游渲染快照：一次性渲染（按当前 kind 构建）
const unsubId = renderHub.onRender((snapshot) => {
  try {
    if (!chart) return;
    const mySeq = ++renderSeq;
    if (String(kindLocal.value).toUpperCase() === "OFF") {
      chart.clear();
      return;
    }
    const option = renderHub.getIndicatorOption(kindLocal.value);
    if (!option) return;
    chart.setOption(option, true);
  } catch (e) {
    console.error("Indicator renderHub onRender error:", e);
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
});

watch(
  () => [vm.candles.value, vm.indicators.value, vm.freq.value, kindLocal.value],
  () => {
    // 渲染由 renderHub 快照驱动，无需主动 render
  },
  { deep: true }
);
watch(
  () => vm.meta.value,
  async () => {
    await nextTick();
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
