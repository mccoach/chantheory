<!-- src/components/features/MainChartPanel.vue -->
<!-- ============================== -->
<!-- 说明：主行情面板（严格限域改动） -->
<!-- 本次变更（修复 H-L 柱图例颜色）： -->
<!-- - 修改 render 函数，在调用 buildMainChartOption 时，额外传入 mapOrigToReduced: chanCache.value.map。 -->
<!--   这使得 tooltip 格式化函数能访问到原始 K 线到合并后 K 线的映射关系，从而正确判断 H-L 柱的颜色。 -->
<!-- 其余逻辑保持不变。 -->
<!-- ============================== -->
<template>
  <!-- 顶部控制条：周期切换按钮等（保持原有实现） -->
  <div class="controls">
    <div class="hint">K线图：</div>
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
        60分钟
      </button>
    </div>
    <div class="right-actions"></div>
  </div>

  <!-- 主图容器：可键盘左右、双击打开设置、顶部显示状态 -->
  <div
    ref="wrap"
    class="chart"
    tabindex="0"
    @keydown="onKeydown"
    @mouseenter="focusWrap"
    @dblclick="openSettingsDialog"
  >
    <!-- 画布内顶栏：左标题、中空、右状态徽标（加载/刷新时间） -->
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

    <!-- ECharts 宿主 -->
    <div ref="host" class="canvas-host"></div>

    <!-- 底部拖拽把手 -->
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
import { buildMainChartOption, zoomSync } from "@/charts/options";
import {
  DEFAULT_MA_CONFIGS,
  CHAN_DEFAULTS,
  CHAN_MARKER_PRESETS,
} from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { computeInclude } from "@/composables/useChan";
import { vSelectAll } from "@/utils/inputBehaviors";
import { buildUpDownMarkers } from "@/charts/chan/layers";

defineOptions({ directives: { selectAll: vSelectAll } });

const vm = inject("marketView");
const settings = useUserSettings();
const { findBySymbol } = useSymbolIndex();
const dialogManager = inject("dialogManager");

const isActiveK = (freq) =>
  vm.chartType.value === "kline" && vm.freq.value === freq;

async function activateK(f) {
  vm.chartType.value = "kline";
  vm.freq.value = f;
  await vm.reload(true);
}

const wrap = ref(null);
const host = ref(null);
let chart = null;
let ro = null;
let winResizeHandler = null;
let detachSync = null;

const settingsDraft = reactive({
  kForm: {
    barPercent: 100,
    upColor: "#f56c6c",
    downColor: "#26a69a",
    subType: "candlestick",
  },
  maForm: {},
  chanForm: { ...CHAN_DEFAULTS },
});

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
          onClick,
          type: "button",
        }),
      ]);

    const renderDisplay = () => {
      const K = settingsDraft.kForm;
      const rows = [];
      rows.push(
        h("div", { class: "std-row" }, [
          nameCell("K 线"),
          itemCell(
            "柱宽%",
            h("input", {
              class: "input num",
              type: "number",
              min: 10,
              max: 100,
              step: 5,
              value: Number(K.barPercent ?? 100),
              onInput: (e) =>
                (settingsDraft.kForm.barPercent = Number(e.target.value || 0)),
            })
          ),
          itemCell(
            "阳线颜色",
            h("input", {
              class: "input color",
              type: "color",
              value: K.upColor || "#f56c6c",
              onInput: (e) =>
                (settingsDraft.kForm.upColor = String(
                  e.target.value || "#f56c6c"
                )),
            })
          ),
          itemCell(
            "阴线颜色",
            h("input", {
              class: "input color",
              type: "color",
              value: K.downColor || "#26a69a",
              onInput: (e) =>
                (settingsDraft.kForm.downColor = String(
                  e.target.value || "#26a69a"
                )),
            })
          ),
          itemCell(
            "复权",
            h(
              "select",
              {
                class: "input",
                value: String(vm.adjust.value || "none"),
                onChange: (e) => (vm.adjust.value = String(e.target.value)),
              },
              [
                h("option", { value: "none" }, "不复权"),
                h("option", { value: "qfq" }, "前复权"),
                h("option", { value: "hfq" }, "后复权"),
              ]
            )
          ),
          itemCell(
            "样式",
            h(
              "select",
              {
                class: "input",
                value: K.subType || "candlestick",
                onChange: (e) =>
                  (settingsDraft.kForm.subType = String(e.target.value)),
              },
              [
                h("option", { value: "candlestick" }, "蜡烛图"),
                h("option", { value: "bar" }, "HL柱图"),
              ]
            )
          ),
          h("div", { class: "std-check" }),
          resetBtn(() =>
            Object.assign(settingsDraft.kForm, {
              barPercent: 100,
              upColor: "#f56c6c",
              downColor: "#26a69a",
              subType: "candlestick",
            })
          ),
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
                value: conf.color || "#ee6666",
                onInput: (e) =>
                  (settingsDraft.maForm[key].color = String(
                    e.target.value || "#ee6666"
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
                    (settingsDraft.maForm[key].style = String(e.target.value)),
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
                  (settingsDraft.maForm[key].period = Math.max(
                    1,
                    parseInt(e.target.value || 5, 10)
                  )),
              })
            ),
            h("div"),
            h("div", { class: "std-check" }),
            resetBtn(() => {
              const def = DEFAULT_MA_CONFIGS[key] || {
                enabled: true,
                period: 5,
                width: 1,
                style: "solid",
                color: "#ee6666",
              };
              Object.assign(settingsDraft.maForm[key], def);
            }),
          ])
        );
      });

      return rows;
    };

    const renderChan = () => {
      const cf = settingsDraft.chanForm;
      const rows = [];
      rows.push(
        h("div", { class: "std-row" }, [
          nameCell("涨跌标记"),
          itemCell(
            "上涨符号",
            h(
              "select",
              {
                class: "input",
                value: cf.upShape || "triangle",
                onChange: (e) =>
                  (settingsDraft.chanForm.upShape = String(e.target.value)),
              },
              [
                h("option", { value: "triangle" }, "▲"),
                h("option", { value: "diamond" }, "◆"),
                h("option", { value: "rect" }, "■"),
                h("option", { value: "circle" }, "●"),
                h("option", { value: "pin" }, "📍"),
                h("option", { value: "arrow" }, "⬇"),
              ]
            )
          ),
          itemCell(
            "上涨颜色",
            h("input", {
              class: "input color",
              type: "color",
              value: cf.upColor || "#f56c6c",
              onInput: (e) =>
                (settingsDraft.chanForm.upColor = String(
                  e.target.value || "#f56c6c"
                )),
            })
          ),
          itemCell(
            "下跌符号",
            h(
              "select",
              {
                class: "input",
                value: cf.downShape || "triangle",
                onChange: (e) =>
                  (settingsDraft.chanForm.downShape = String(e.target.value)),
              },
              [
                h("option", { value: "triangle" }, "▲"),
                h("option", { value: "diamond" }, "◆"),
                h("option", { value: "rect" }, "■"),
                h("option", { value: "circle" }, "●"),
                h("option", { value: "pin" }, "📍"),
                h("option", { value: "arrow" }, "⬇"),
              ]
            )
          ),
          itemCell(
            "下跌颜色",
            h("input", {
              class: "input color",
              type: "color",
              value: cf.downColor || "#00ff00",
              onInput: (e) =>
                (settingsDraft.chanForm.downColor = String(
                  e.target.value || "#00ff00"
                )),
            })
          ),
          itemCell(
            "承载点",
            h(
              "select",
              {
                class: "input",
                value: cf.anchorPolicy || "right",
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
                (settingsDraft.chanForm.showUpDownMarkers = !!e.target.checked),
            }),
          ]),
          resetBtn(() => {
            settingsDraft.chanForm.upShape = "triangle";
            settingsDraft.chanForm.upColor = "#f56c6c";
            settingsDraft.chanForm.downShape = "triangle";
            settingsDraft.chanForm.downColor = "#00ff00";
            settingsDraft.chanForm.anchorPolicy = "right";
            settingsDraft.chanForm.showUpDownMarkers = true;
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

function openSettingsDialog() {
  Object.assign(
    settingsDraft.kForm,
    JSON.parse(
      JSON.stringify(
        settings.klineStyle.value || {
          barPercent: 100,
          upColor: "#f56c6c",
          downColor: "#26a69a",
          subType: "candlestick",
        }
      )
    )
  );
  const maDefaults = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS));
  const maLocal = settings.maConfigs.value || {};
  Object.keys(maDefaults).forEach((k) => {
    if (maLocal[k]) maDefaults[k] = { ...maDefaults[k], ...maLocal[k] };
  });
  settingsDraft.maForm = maDefaults;
  Object.assign(
    settingsDraft.chanForm,
    JSON.parse(JSON.stringify(settings.chanSettings.value || CHAN_DEFAULTS))
  );

  const snapMA = extractMAKey(settings.maConfigs.value || {});
  const prevAdjust = String(vm.adjust.value || "none");

  dialogManager.open({
    title: "行情显示设置",
    contentComponent: MainChartSettingsContent,
    props: {},
    tabs: [
      { key: "display", label: "行情显示" },
      { key: "chan", label: "缠论标记" },
    ],
    activeTab: "display",
    onSave: async () => {
      settings.setKlineStyle(settingsDraft.kForm);
      settings.setMaConfigs(settingsDraft.maForm);
      settings.setChanSettings({ ...settingsDraft.chanForm });

      const nextMA = extractMAKey(settingsDraft.maForm || {});
      const needReload = JSON.stringify(nextMA) !== JSON.stringify(snapMA);
      const currAdjust = String(vm.adjust.value || "none");
      const adjustChanged = currAdjust !== prevAdjust;

      if (needReload && !adjustChanged) await vm.reload(true);
      else {
        recomputeChan();
        render();
      }

      dialogManager.close();
    },
    onClose: () => dialogManager.close(),
  });
}

function extractMAKey(ma) {
  const out = {};
  Object.keys(ma || {}).forEach((k) => {
    const m = ma[k] || {};
    out[k] = { p: Number(m.period || 0), e: !!m.enabled };
  });
  return out;
}

const displayHeader = ref({ name: "", code: "", freq: "" });
const displayTitle = computed(() => {
  const n = displayHeader.value.name || "";
  const c = displayHeader.value.code || vm.code.value || "";
  const f = displayHeader.value.freq || vm.freq.value || "";
  const src = (vm.meta.value?.source || "").trim();
  const srcLabel = src ? `（${src}）` : "";
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
  const d = refreshedAt.value;
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
});
let refreshedTimer = null;

let currentIndex = -1;
function onGlobalHoverIndex(e) {
  const idx = Number(e?.detail?.idx);
  if (Number.isFinite(idx) && idx >= 0) currentIndex = idx;
}
function focusWrap() {
  try {
    wrap.value?.focus?.();
  } catch {}
}
function onKeydown(e) {
  if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
  e.preventDefault();
  const len = (vm.candles.value || []).length;
  if (!len) return;
  if (currentIndex < 0) currentIndex = Math.max(0, len - 1);
  currentIndex += e.key === "ArrowLeft" ? -1 : +1;
  currentIndex = Math.max(0, Math.min(len - 1, currentIndex));
  try {
    chart.dispatchAction({
      type: "showTip",
      seriesIndex: 0,
      dataIndex: currentIndex,
    });
    chart.dispatchAction({
      type: "highlight",
      seriesIndex: 0,
      dataIndex: currentIndex,
    });
  } catch {}
}

const chanCache = ref({ reduced: [], map: [], meta: null });
function recomputeChan() {
  try {
    const arr = vm.candles.value || [];
    if (!arr.length) {
      chanCache.value = { reduced: [], map: [], meta: null };
      return;
    }
    const policy =
      settings.chanSettings.value.anchorPolicy || CHAN_DEFAULTS.anchorPolicy;
    const res = computeInclude(arr, { anchorPolicy: policy });
    chanCache.value = {
      reduced: res.reducedBars || [],
      map: res.mapOrigToReduced || [],
      meta: res.meta || null,
    };
  } catch {
    chanCache.value = { reduced: [], map: [], meta: null };
  }
}

const lastFreq = ref(vm.freq.value);

function getVisibleCount() {
  const len = (vm.candles.value || []).length || 1;
  try {
    const dz = chart?.getOption()?.dataZoom;
    const z = Array.isArray(dz)
      ? dz.find((x) => typeof x.startValue !== "undefined")
      : null;
    if (z) return Math.max(1, Number(z.endValue) - Number(z.startValue) + 1);
  } catch {}
  return len;
}

function updateChanMarkersOnZoom() {
  if (!chart) return;
  const showMarkers = !!settings.chanSettings.value.showUpDownMarkers;
  if (!showMarkers) {
    chart.setOption({
      series: [
        { id: "CHAN_UP", data: [] },
        { id: "CHAN_DOWN", data: [] },
      ],
    });
    return;
  }
  const reduced = chanCache.value.reduced || [];
  if (!reduced.length) return;
  const layer = buildUpDownMarkers(reduced, {
    theme: {},
    chanSettings: settings.chanSettings.value,
    hostWidth: host.value ? host.value.clientWidth : 800,
    visCount: getVisibleCount(),
  });
  chart.setOption({ series: layer.series }, false);
}

function render() {
  if (!chart) return;
  const option = buildMainChartOption(
    {
      candles: vm.candles.value,
      indicators: vm.indicators.value,
      chartType: vm.chartType.value,
      maConfigs: settings.maConfigs.value,
      freq: vm.freq.value,
      klineStyle: settings.klineStyle.value,
      adjust: vm.adjust.value,
      reducedBars: chanCache.value.reduced,
      // 关键修改：传入 `mapOrigToReduced`
      mapOrigToReduced: chanCache.value.map,
    },
    { tooltipClass: "ct-fixed-tooltip" }
  );

  const showMarkers = !!settings.chanSettings.value.showUpDownMarkers;
  if (showMarkers && (chanCache.value.reduced || []).length) {
    const auxAxis = { type: "value", min: 0, max: 1, show: false };
    if (Array.isArray(option.yAxis)) {
      if (option.yAxis.length === 1) option.yAxis = [option.yAxis[0], auxAxis];
    } else {
      option.yAxis = [option.yAxis, auxAxis];
    }
    const layer = buildUpDownMarkers(chanCache.value.reduced, {
      theme: {},
      chanSettings: settings.chanSettings.value,
      hostWidth: host.value ? host.value.clientWidth : 800,
      visCount: getVisibleCount(),
    });
    option.series = Array.isArray(option.series)
      ? option.series.concat(layer.series || [])
      : layer.series || [];
    if (option.xAxis) {
      const margin = Math.max(
        option.xAxis?.axisLabel?.margin || 6,
        layer.extra?.xAxisLabelMargin || 16
      );
      if (Array.isArray(option.xAxis))
        option.xAxis = option.xAxis.map((xa, idx) =>
          idx === 0
            ? { ...xa, axisLabel: { ...(xa.axisLabel || {}), margin } }
            : xa
        );
      else
        option.xAxis = {
          ...option.xAxis,
          axisLabel: { ...(option.xAxis.axisLabel || {}), margin },
        };
    }
  }

  let allowCarryZoom = lastFreq.value === vm.freq.value;
  const prev = chart.getOption?.();
  const lenNow = (vm.candles.value || []).length;
  if (
    allowCarryZoom &&
    prev &&
    Array.isArray(prev.dataZoom) &&
    prev.dataZoom.length
  ) {
    const z = prev.dataZoom.find((x) => typeof x.startValue !== "undefined");
    if (
      z &&
      typeof z.endValue !== "undefined" &&
      lenNow > 0 &&
      Number(z.endValue) >= lenNow - 1
    )
      allowCarryZoom = false;
  } else if (lastFreq.value !== vm.freq.value) {
    allowCarryZoom = false;
  }
  if (
    allowCarryZoom &&
    prev &&
    Array.isArray(prev.dataZoom) &&
    prev.dataZoom.length
  )
    option.dataZoom = prev.dataZoom;

  chart.setOption(option, true);
  lastFreq.value = vm.freq.value;
  updateChanMarkersOnZoom();
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
        const idx = Math.round(result[0]),
          l = (vm.candles.value || []).length;
        if (Number.isFinite(idx) && idx >= 0 && idx < l) currentIndex = idx;
      }
    } catch {}
  });
  chart.on("updateAxisPointer", (params) => {
    try {
      const axisInfo = (params?.axesInfo && params.axesInfo[0]) || null;
      const label = axisInfo?.value;
      const dates = (vm.candles.value || []).map((d) => d.t);
      const idx = dates.indexOf(label);
      if (idx >= 0) currentIndex = idx;
    } catch {}
  });
  chart.on("dataZoom", () => {
    updateChanMarkersOnZoom();
  });

  try {
    ro = new ResizeObserver(() => {
      if (chart && host.value)
        chart.resize({
          width: host.value.clientWidth,
          height: host.value.clientHeight,
        });
      updateChanMarkersOnZoom();
    });
    ro.observe(el);
  } catch {}
  winResizeHandler = () => {
    if (chart && host.value)
      chart.resize({
        width: host.value.clientWidth,
        height: host.value.clientHeight,
      });
    updateChanMarkersOnZoom();
  };
  window.addEventListener("chan:hover-index", onGlobalHoverIndex);

  await nextTick();
  requestAnimationFrame(() => {
    if (chart && host.value)
      chart.resize({
        width: host.value.clientWidth,
        height: host.value.clientHeight,
      });
  });

  detachSync = zoomSync.attach(
    "main",
    chart,
    () => (vm.candles.value || []).length
  );
  recomputeChan();
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
  }
  if (chart) {
    try {
      chart.dispose();
    } catch {}
    chart = null;
  }
  if (refreshedTimer) {
    clearTimeout(refreshedTimer);
    refreshedTimer = null;
  }
  window.removeEventListener("chan:hover-index", onGlobalHoverIndex);
});

watch(
  () => [
    vm.candles.value,
    vm.indicators.value,
    vm.chartType.value,
    vm.freq.value,
    settings.maConfigs.value,
    settings.chanSettings.value,
    settings.klineStyle.value,
    vm.adjust.value,
  ],
  () => {
    recomputeChan();
    render();
  },
  { deep: true }
);

watch(
  () => vm.loading.value,
  async (isLoading) => {
    if (isLoading) {
      if (refreshedTimer) {
        clearTimeout(refreshedTimer);
        refreshedTimer = null;
      }
      return;
    }
    await nextTick();
    updateHeaderFromCurrent();
    refreshedAt.value = new Date();
    showRefreshed.value = true;
    if (refreshedTimer) clearTimeout(refreshedTimer);
    refreshedTimer = setTimeout(() => {
      showRefreshed.value = false;
      refreshedTimer = null;
    }, 2000);
  }
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
    if (chart && host.value)
      chart.resize({
        width: host.value.clientWidth,
        height: host.value.clientHeight,
      });
  }
}
function onResizeHandleUp() {
  dragging = false;
  window.removeEventListener("mousemove", onResizeHandleMove);
}

function updateHeaderFromCurrent() {
  const sym = (vm.meta.value?.symbol || vm.code.value || "").trim();
  const frq = String(vm.meta.value?.freq || vm.freq.value || "").trim();
  let name = "";
  try {
    name = findBySymbol(sym)?.name?.trim() || "";
  } catch {}
  displayHeader.value = { name, code: sym, freq: frq };
}
</script>

<style scoped>
.controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin: 0 0 8px 0;
}
.hint {
  color: #bbb;
  font-size: 14px;
  user-select: none;
}
.seg {
  display: inline-flex;
  align-items: center;
  border: 1px solid #444;
  border-radius: 10px;
  overflow: hidden;
  background: #1a1a1a;
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
.right-actions {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
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

.input {
  background: #0f0f0f;
  color: #ddd;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 4px 6px;
  width: 100%;
  box-sizing: border-box;
}
.input.num {
  text-align: center;
}
.input.color {
  height: 24px;
  padding: 1px;
  border: none;
  background: transparent;
}
.btn {
  background: #2a2a2a;
  color: #ddd;
  border: 1px solid #444;
  border-radius: 4px;
  padding: 6px 10px;
  cursor: pointer;
}
.btn.icon {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
</style>
