<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\tech\VolumePanel.vue -->
<!-- ============================== -->
<!-- 量窗（接入统一渲染中枢 · 恢复 MAVOL/放缩量标记设置 UI · 移除旧链路）
     - 只订阅 useViewRenderHub.onRender(snapshot)，一次性 setOption 渲染（含统一 initialRange 与 overrideMarkWidth）。
     - 设置面板恢复 MAVOL 三条线与放/缩量标记的参数编辑，保存到 settings.volSettings，并由渲染中枢监控 settings 变化重新发布快照。
     - 不再监听 meta 或使用 zoomSync；onDataZoom inside-only 并早退。
-->
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
import { useUserSettings } from "@/composables/useUserSettings";
import { DEFAULT_VOL_SETTINGS } from "@/constants";
import { vSelectAll } from "@/utils/inputBehaviors";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import { useViewCommandHub } from "@/composables/useViewCommandHub";

defineOptions({ directives: { selectAll: vSelectAll } });

const vm = inject("marketView");
const renderHub = useViewRenderHub();
const settings = useUserSettings();
const { findBySymbol } = useSymbolIndex();
const dialogManager = inject("dialogManager");
const hub = useViewCommandHub();

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

    // 行：量额柱基础样式
    const rows = [];
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
            value: Number(settingsDraftVol.volBar.barPercent ?? 100),
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
            value:
              settingsDraftVol.volBar.upColor ||
              DEFAULT_VOL_SETTINGS.volBar.upColor,
            onInput: (e) =>
              (settingsDraftVol.volBar.upColor = String(
                e.target.value || DEFAULT_VOL_SETTINGS.volBar.upColor
              )),
          })
        ),
        itemCell(
          "阴线颜色",
          h("input", {
            class: "input color",
            type: "color",
            value:
              settingsDraftVol.volBar.downColor ||
              DEFAULT_VOL_SETTINGS.volBar.downColor,
            onInput: (e) =>
              (settingsDraftVol.volBar.downColor = String(
                e.target.value || DEFAULT_VOL_SETTINGS.volBar.downColor
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

    // 行：MAVOL 三条线参数
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
                (conf.period = Math.max(1, parseInt(e.target.value || 5, 10))),
            })
          ),
          h("div"),
          checkCell(!!conf.enabled, (e) => (conf.enabled = !!e.target.checked)),
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

    // 行：放量标记
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

    // 行：缩量标记
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

    return () => h("div", { key: `vol-settings-root-${draftRev.value}` }, rows);
  },
});

// 打开设置窗：从 settings 加载现值到草稿，保存时写回 settings.volSettings
function openSettingsDialog() {
  const vs = settings.volSettings.value || {};

  // 量柱样式
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

  // MAVOL 三条线
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

  // 放/缩量标记
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
      // 写回 settings.volSettings，并由渲染中枢监听 settings 变化后重新发布快照
      settings.setVolSettings({
        ...vs,
        volBar: { ...settingsDraftVol.volBar },
        mavolStyles: { ...settingsDraftVol.mavolForm },
        markerPump: { ...settingsDraftVol.markerPump },
        markerDump: { ...settingsDraftVol.markerDump },
        mode: mode.value,
      });

      // MOD: 立即触发中枢刷新，发布新快照 -> 即时应用新设置
      hub.execute("Refresh", {});

      dialogManager.close();
    },
    onClose: () => dialogManager.close(),
  });
}

let dzIdleTimer = null;
const dzIdleDelayMs = 180;

/** 副窗作为交互源：ECharts-first + idle-commit 会后承接 */
function onDataZoom(params) {
  try {
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

    // NEW: 广播预览范围（主窗顶栏实时更新）
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

    renderHub.beginInteraction("volume");
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
        renderHub.endInteraction("volume");
      }
    }, dzIdleDelayMs);
  } catch {}
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

function schedule(fn) {
  try {
    requestAnimationFrame(() => setTimeout(fn, 0));
  } catch {
    setTimeout(fn, 0);
  }
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

  // NEW: 注册副窗 chart，并在鼠标进入副窗时设置为激活面板
  try {
    renderHub.registerChart("volume", chart);
    el.addEventListener("mouseenter", () => {
      renderHub.setActivePanel("volume");
    });
  } catch {}

  // 组内/本窗联动（无需自建广播）
  chart.getZr().on("mousemove", (_e) => {
    // 交由 ECharts 内建处理悬浮即可，无需显式 showTip
  });
  chart.on("updateAxisPointer", (_params) => {
    // 交由组联动对齐，无需转发
  });
  chart.on("dataZoom", onDataZoom); // 新增：副窗支持作为交互源

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

// 订阅上游渲染快照：一次性渲染
const unsubId = renderHub.onRender((snapshot) => {
  try {
    if (!chart) return;
    const mySeq = ++renderSeq;
    const notMerge = !renderHub.isInteracting(); // ECharts-first：交互期禁止 notMerge 重绘
    chart.setOption(snapshot.volume.option, notMerge);
    recomputeVisibleStats(mySeq);
  } catch (e) {
    console.error("Volume renderHub onRender error:", e);
  }
});

onBeforeUnmount(() => {
  // 卸载宿主事件
  try {
    ro && ro.disconnect();
  } catch {}
  ro = null;
  try {
    chart && chart.dispose();
  } catch {}
  chart = null;
});

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
      if (!isStale(seq)) {
        // 渲染由渲染中枢快照驱动，无需手动 render
      }
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
