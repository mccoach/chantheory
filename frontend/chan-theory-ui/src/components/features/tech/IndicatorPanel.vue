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
let ro = null; // 已存在的 ResizeObserver 句柄（之前未使用）

// NEW: 指标窗缺少自适应，此处补充与量窗一致的安全 resize 实现
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

let dzIdleTimer = null;
const dzIdleDelayMs = 180;

/** 指标窗作为交互源：ECharts-first + idle-commit 会后承接 */
function onDataZoom(params) {
  try {
    const info = (params && params.batch && params.batch[0]) || params || {};
    const arr = vm.candles.value || [];
    const len = arr.length;
    if (!len) return;

    let sIdx, eIdx;
    if (typeof info.startValue !== "undefined" && typeof info.endValue !== "undefined") {
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

    renderHub.beginInteraction("indicator");
    if (dzIdleTimer) { clearTimeout(dzIdleTimer); dzIdleTimer = null; }
    dzIdleTimer = setTimeout(() => {
      try {
        const bars_new = Math.max(1, eIdx - sIdx + 1);
        const tsArr = arr.map((d) => Date.parse(d.t));
        const anchorTs = Number.isFinite(tsArr[eIdx]) ? tsArr[eIdx] : hub.getState().rightTs;
        const st = hub.getState();
        const changedBars = bars_new !== Math.max(1, Number(st.barsCount || 1));
        const changedEIdx = Number.isFinite(tsArr[eIdx]) && tsArr[eIdx] !== st.rightTs;

        if (changedBars || changedEIdx) {
          if (changedBars && changedEIdx) {
            hub.execute("ScrollZoom", { nextBars: bars_new, nextRightTs: anchorTs });
          } else if (changedBars) {
            hub.execute("SetBarsManual", { nextBars: bars_new });
          } else if (changedEIdx) {
            hub.execute("Pan", { nextRightTs: anchorTs });
          }
        }
      } finally {
        renderHub.endInteraction("indicator");
      }
    }, dzIdleDelayMs);
  } catch {}
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

  // NEW: 指标窗也可作为交互源
  chart.on("dataZoom", onDataZoom);

  // NEW: 绑定 ResizeObserver，保证窗口/容器尺寸变化时自动 chart.resize
  try {
    ro = new ResizeObserver(() => {
      safeResize();
    });
    ro.observe(el);
  } catch {}

  // NEW: 首帧安全 resize，避免初始尺寸边界值遗留
  requestAnimationFrame(() => {
    safeResize();
  });

  // 仍保留订阅：响应“非鼠标触发”的统一广播（如键盘左右）
  window.addEventListener("chan:hover-index", onGlobalHoverIndex);

  updateHeaderFromCurrent();
});

// 订阅上游渲染：交互期间避免 notMerge 重绘
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
    const notMerge = !renderHub.isInteracting();
    chart.setOption(option, notMerge);
  } catch (e) {
    console.error("Indicator renderHub onRender error:", e);
  }
});

onBeforeUnmount(() => {
  renderHub.offRender(unsubId);

  // NEW: 断开 ResizeObserver（一致性与防泄漏）
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
