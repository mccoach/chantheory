<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\tech\IndicatorPanel.vue -->
<!--
说明（集中式设置弹窗 + 全局快捷键保持生效）：
- 使用全局 dialogManager 打开设置弹窗（本组件不再管理 mask/快捷键作用域）。
- 设置窗当前不含具体参数，仅展示“暂无更多设置项”的提示，可后续扩展。
- 其它图表行为（渲染/缩放同步/标题更新/拖拽改高）保持与改造前一致。
-->

<template>
  <!-- 图表容器（双击打开设置弹窗） -->
  <div ref="wrap" class="chart" @dblclick="openSettingsDialog">
    <!-- 画布内顶栏：左下拉（指标种类） → 中标题 → 右关闭按钮 -->
    <div class="top-info">
      <!-- 左：指标种类选择 -->
      <select class="sel-kind" v-model="kindLocal" @change="onKindChange" title="选择指标">
        <option value="MACD">MACD</option>
        <option value="KDJ">KDJ</option>
        <option value="RSI">RSI</option>
        <option value="BOLL">BOLL</option>
        <option value="OFF">OFF</option>
      </select>
      <!-- 中：标题（名称（代码）-频率） -->
      <div class="title">{{ displayTitle }}</div>
      <!-- 右：关闭按钮 -->
      <button class="btn-close" @click="$emit('close')" title="关闭此窗" aria-label="关闭">
        <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
          <defs>
            <linearGradient id="gcx" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#3a3a3a" />
              <stop offset="1" stop-color="#242424" />
            </linearGradient>
          </defs>
          <rect x="2.5" y="2.5" rx="6" ry="6" width="19" height="19" fill="url(#gcx)" stroke="#8b8b8b" stroke-width="1" />
          <path d="M8 8 L16 16" stroke="#e6e6e6" stroke-width="1.8" stroke-linecap="round" />
          <path d="M16 8 L8 16" stroke="#e6e6e6" stroke-width="1.8" stroke-linecap="round" />
        </svg>
      </button>
    </div>

    <!-- 画布宿主（ECharts 渲染区域） -->
    <div ref="host" class="canvas-host"></div>

    <!-- 底部拖拽把手（上下调整高度） -->
    <div
      class="bottom-strip"
      title="上下拖拽调整窗体高度"
      @mousedown="onResizeHandleDown('bottom', $event)"
    ></div>
  </div>
</template>

<script setup>
// ==============================
// 脚本：指标副窗（MACD/KDJ/RSI/BOLL）
// - 渲染函数保持原有风格
// - 设置弹窗改由 dialogManager 统一管理（本窗当前仅展示提示）
// ==============================

// Vue 组合式 API
import {
  inject,            // 注入全局依赖（marketView / dialogManager）
  onMounted,         // 挂载
  onBeforeUnmount,   // 卸载
  ref,               // 响应式
  watch,             // 侦听
  nextTick,          // 下一帧
  computed,          // 计算属性
  defineComponent,   // 内联定义设置内容组件
  h,                 // 渲染函数
} from "vue";

// ECharts
import * as echarts from "echarts"; // ECharts 实例

// 业务工具
import {
  buildKdjOrRsiOption,    // KDJ/RSI/BOLL 选项生成器（与改造前一致）
  buildMacdOption,        // MACD 选项生成器
  zoomSync,               // 多窗缩放同步
} from "@/charts/options";
import { useSymbolIndex } from "@/composables/useSymbolIndex"; // 名称解析（Local-first）

// 注入全局依赖
const vm = inject("marketView");              // 市场视图（code/freq/candles/indicators/meta）
const { findBySymbol } = useSymbolIndex();    // 名称解析
const dialogManager = inject("dialogManager");// 全局弹窗管理器

// 组件 props / emits
const props = defineProps({ kind: { type: String, default: "MACD" } }); // 初始指标种类
const emit = defineEmits(["update:kind", "close"]);                     // 更新种类 / 关闭

// DOM 与实例句柄
const wrap = ref(null);    // 外壳
const host = ref(null);    // ECharts 宿主
let chart = null;          // ECharts 实例
let ro = null;             // ResizeObserver
let winResizeHandler = null; // window.resize 监听
let detachSync = null;     // 缩放同步解绑

// 本地指标种类（双向绑定）
const kindLocal = ref(props.kind);
watch(
  () => props.kind,
  (v) => { kindLocal.value = v; }
);

// 标题展示（名称（代码）-频率）
const displayHeader = ref({ name: "", code: "", freq: "" });
const displayTitle = computed(() => {
  const n = displayHeader.value.name || "";
  const c = displayHeader.value.code || vm.code.value || "";
  const f = displayHeader.value.freq || vm.freq.value || "";
  return n ? `${n}（${c}）：${f}` : `${c}：${f}`;
});
function updateHeaderFromCurrent() {
  const sym = (vm.meta.value?.symbol || vm.code.value || "").trim();
  const frq = String(vm.meta.value?.freq || vm.freq.value || "").trim();
  let name = "";
  try { name = findBySymbol(sym)?.name?.trim() || ""; } catch {}
  displayHeader.value = { name, code: sym, freq: frq };
}

// 内联定义“设置内容组件”（当前仅提示，无参数）
const IndicatorSettingsContent = defineComponent({
  // 提示内容：可后续扩展为真实参数面板
  setup() {
    return () => h("div", { class: "settings-hint" }, "当前指标窗暂无更多设置项，后续版本将开放参数配置。");
  },
});

// 打开设置弹窗（双击图表）
function openSettingsDialog() {
  dialogManager.open({
    title: `${String(kindLocal.value).toUpperCase()} 指标设置`, // 标题
    contentComponent: IndicatorSettingsContent,               // 内容（提示）
    onSave: () => {
      // 当前无可保存参数，按“保存”视作确认并关闭
      dialogManager.close();
      render(); // 触发一次重绘（稳健性）
    },
    onClose: () => dialogManager.close(),                    // 关闭
  });
}

// 指标种类变更（更新外部 v-model 并重绘）
function onKindChange() {
  emit("update:kind", kindLocal.value); // 通知父层
  render();                             // 重绘
}

// 渲染（根据 kindLocal 与 vm 数据生成 Option 并 setOption）
function render() {
  if (!chart) return;
  const kind = String(kindLocal.value || "").toUpperCase();

  // OFF：清空
  if (kind === "OFF") {
    chart.clear();
    return;
  }

  // 组装通用数据与 UI 参数
  const data = { candles: vm.candles.value, indicators: vm.indicators.value, freq: vm.freq.value };
  const uiOpts = { tooltipClass: "ct-fixed-tooltip" };

  // 选择对应生成器
  let option = null;
  if (kind === "MACD") {
    option = buildMacdOption(data, uiOpts);
  } else if (kind === "KDJ") {
    option = buildKdjOrRsiOption({ ...data, useKDJ: true, useRSI: false }, uiOpts);
  } else if (kind === "RSI" || kind === "BOLL") {
    option = buildKdjOrRsiOption({ ...data, useKDJ: false, useRSI: true }, uiOpts);
  } else {
    // 未知类型：默认使用 RSI 容器
    option = buildKdjOrRsiOption({ ...data, useKDJ: false, useRSI: true }, uiOpts);
  }

  // 应用 Option
  chart.setOption(option, true);
}

// 拖拽改高（与主窗一致）
let dragging = false;  // 是否拖拽中
let startY = 0;        // 起始 Y
let startH = 0;        // 起始高
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
    if (chart && host.value)
      chart.resize({ width: host.value.clientWidth, height: host.value.clientHeight });
  }
}
function onResizeHandleUp() {
  dragging = false;
  window.removeEventListener("mousemove", onResizeHandleMove);
}

// 生命周期：挂载 → 初始化图表/缩放同步/首次渲染
onMounted(async () => {
  const el = host.value;
  if (!el) return;

  // 初始化 ECharts 实例
  chart = echarts.init(el, null, { renderer: "canvas", width: el.clientWidth, height: el.clientHeight });
  chart.group = "ct-sync";
  try { echarts.connect("ct-sync"); } catch {}

  // 容器尺寸观察
  try {
    ro = new ResizeObserver(() => {
      if (chart && host.value)
        chart.resize({ width: host.value.clientWidth, height: host.value.clientHeight });
    });
    ro.observe(el);
  } catch {}

  // window.resize
  winResizeHandler = () => {
    if (chart && host.value)
      chart.resize({ width: host.value.clientWidth, height: host.value.clientHeight });
  };
  window.addEventListener("resize", winResizeHandler);

  // 首帧 resize
  await nextTick();
  requestAnimationFrame(() => {
    if (chart && host.value)
      chart.resize({ width: host.value.clientWidth, height: host.value.clientHeight });
  });

  // 新增：派发最后悬停索引（与主/量窗一致）
  try {
    chart.getZr().on("mousemove", (e) => {
      try {
        const point = [e.offsetX, e.offsetY];
        const result = chart.convertFromPixel({ seriesIndex: 0 }, point);
        if (Array.isArray(result)) {
          const idx = Math.round(result[0]);
          const len = (vm.candles.value || []).length;
          if (Number.isFinite(idx) && idx >= 0 && idx < len) {
            window.dispatchEvent(new CustomEvent("chan:hover-index", { detail: { idx } }));
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
          window.dispatchEvent(new CustomEvent("chan:hover-index", { detail: { idx } }));
        }
      } catch {}
    });
  } catch {}

  // 缩放同步：加入同步组
  const key = `indicator-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  detachSync = zoomSync.attach(key, chart, () => (vm.candles.value || []).length);

  // 首帧渲染与标题更新
  render();
  updateHeaderFromCurrent();
});

// 卸载：解绑监听/释放实例
onBeforeUnmount(() => {
  window.removeEventListener("resize", winResizeHandler);
  if (ro) { try { ro.disconnect(); } catch {} ro = null; }
  if (detachSync) { try { detachSync(); } catch {} detachSync = null; }
  if (chart) { try { chart.dispose(); } catch {} chart = null; }
});

// 监听：数据/频率/指标种类变化 → 重绘
watch(
  () => [vm.candles.value, vm.indicators.value, vm.freq.value, kindLocal.value],
  () => render(),
  { deep: true }
);

// 监听：加载完成 → 更新标题（加载中保持旧标题）
watch(
  () => vm.loading.value,
  async (isLoading) => {
    if (isLoading) return;
    await nextTick();
    updateHeaderFromCurrent();
  }
);
</script>

<style scoped>
/* 容器 */
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

/* 顶栏（画布内）：左下拉 → 中标题 → 右关闭 */
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
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
}

/* 画布宿主与把手 */
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
.bottom-strip:hover {
  cursor: ns-resize;
}

/* 设置提示文案 */
.settings-hint {
  color: #bbb;
  font-size: 13px;
  padding: 4px 2px;
}
</style>
