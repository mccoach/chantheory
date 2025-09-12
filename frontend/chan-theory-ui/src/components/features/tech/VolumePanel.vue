<!-- src/components/features/tech/VolumePanel.vue -->
<!-- 全量（含注释） -->
<!-- 变更要点：
1) render 中“是否继承 dataZoom”逻辑按主窗实现，设置变更不重置缩放；
2) 量窗设置新增“缩量标记启用”勾选（同时也为放量标记补充勾选，保持一致性）；
3) buildVolumeOption 已支持 enabled 开关 + 动态底部留白，面板无需再手工处理留白。
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

const wrap = ref(null);
const host = ref(null);
let chart = null;
let ro = null;
let winResizeHandler = null;
let detachSync = null;

// 标题
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
  try {
    name = findBySymbol(sym)?.name?.trim() || "";
  } catch {}
  displayHeader.value = { name, code: sym, freq: frq };
}

// 统计
const stat = ref({
  total: "-",
  mean: "-",
  max: "-",
  pumpDays: 0,
  maxConsecDump: 0,
});

// 模式
const mode = ref(settings.volSettings.value.mode);
const modeLabel = ref(mode.value === "amount" ? "额" : "量");
function switchMode(next) {
  const m = next === "amount" ? "amount" : "vol";
  settings.patchVolSettings({ mode: m });
  mode.value = m;
  modeLabel.value = m === "amount" ? "额" : "量";
  render(); // 由 render 内部决定是否继承 dataZoom
}

// 设置草稿
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
  markerPump: { ...DEFAULT_VOL_SETTINGS.markerPump }, // 包含 enabled
  markerDump: { ...DEFAULT_VOL_SETTINGS.markerDump }, // 包含 enabled
});
const draftRev = ref(0);

// 设置内容
const VolumeSettingsContent = defineComponent({
  props: { activeTab: { type: String, default: "" } },
  setup() {
    const nameCell = (text) => h("div", { class: "std-name" }, text);
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
      // 量额柱
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
      // MAVOL
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
              Object.assign(conf, DEFAULT_VOL_SETTINGS.mavolStyles[k]);
              conf.period = Math.max(1, parseInt(conf.period || 5, 10));
              draftRev.value++;
            }),
          ])
        );
      });
      // 放量标记（新增 enabled 勾选）
      const pump = settingsDraftVol.markerPump;
      rows.push(
        h("div", { class: "std-row", key: `pump-${draftRev.value}` }, [
          nameCell("放量标记"),
          itemCell(
            "符号",
            h(
              "select",
              {
                class: "input",
                value: pump.shape || "triangle",
                onChange: (e) =>
                  (settingsDraftVol.markerPump.shape = String(e.target.value)),
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
            "颜色",
            h("input", {
              class: "input color",
              type: "color",
              value: pump.color || "#ffb74d",
              onInput: (e) =>
                (settingsDraftVol.markerPump.color = String(
                  e.target.value || "#ffb74d"
                )),
            })
          ),
          itemCell(
            "阈值",
            h("input", {
              class: "input num",
              type: "number",
              min: 0.1,
              step: 0.1,
              value: Number(pump.threshold ?? 1.5),
              onInput: (e) =>
                (settingsDraftVol.markerPump.threshold = Math.max(
                  0.1,
                  Number(e.target.value || 1.5)
                )),
            })
          ),
          h("div"),
          h("div"),
          checkCell(
            !!pump.enabled,
            (e) => (settingsDraftVol.markerPump.enabled = !!e.target.checked)
          ),
          resetBtn(() => {
            Object.assign(
              settingsDraftVol.markerPump,
              DEFAULT_VOL_SETTINGS.markerPump
            );
            draftRev.value++;
          }),
        ])
      );
      // 缩量标记（新增 enabled 勾选 —— 需求点）
      const dump = settingsDraftVol.markerDump;
      rows.push(
        h("div", { class: "std-row", key: `dump-${draftRev.value}` }, [
          nameCell("缩量标记"),
          itemCell(
            "符号",
            h(
              "select",
              {
                class: "input",
                value: dump.shape || "diamond",
                onChange: (e) =>
                  (settingsDraftVol.markerDump.shape = String(e.target.value)),
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
            "颜色",
            h("input", {
              class: "input color",
              type: "color",
              value: dump.color || "#8d6e63",
              onInput: (e) =>
                (settingsDraftVol.markerDump.color = String(
                  e.target.value || "#8d6e63"
                )),
            })
          ),
          itemCell(
            "阈值",
            h("input", {
              class: "input num",
              type: "number",
              min: 0.1,
              step: 0.1,
              value: Number(dump.threshold ?? 0.5),
              onInput: (e) =>
                (settingsDraftVol.markerDump.threshold = Math.max(
                  0.1,
                  Number(e.target.value || 0.5)
                )),
            })
          ),
          h("div"),
          h("div"),
          checkCell(
            !!dump.enabled,
            (e) => (settingsDraftVol.markerDump.enabled = !!e.target.checked)
          ),
          resetBtn(() => {
            Object.assign(
              settingsDraftVol.markerDump,
              DEFAULT_VOL_SETTINGS.markerDump
            );
            draftRev.value++;
          }),
        ])
      );

      return h("div", { key: `vol-settings-root-${draftRev.value}` }, rows);
    };
  },
});

// 打开设置
function openSettingsDialog() {
  const vs = settings.volSettings.value || {};
  // 柱体
  Object.assign(settingsDraftVol.volBar, {
    barPercent: Number.isFinite(+vs?.volBar?.barPercent)
      ? Math.max(10, Math.min(100, Math.round(+vs.volBar.barPercent)))
      : DEFAULT_VOL_SETTINGS.volBar.barPercent,
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
  // 放/缩量标记（含 enabled）
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
    onSave: () => {
      const mavolStyles = {};
      Object.entries(settingsDraftVol.mavolForm).forEach(([key, conf]) => {
        mavolStyles[key] = {
          enabled: !!conf.enabled,
          width: Number.isFinite(+conf.width) ? +conf.width : 1,
          style: conf.style || "solid",
          color: conf.color || "#ee6666",
          period: Math.max(1, parseInt(conf.period || 5, 10)),
        };
      });
      settings.setVolSettings({
        ...vs,
        volBar: {
          barPercent: Math.max(
            10,
            Math.min(
              100,
              Math.round(+settingsDraftVol.volBar.barPercent || 100)
            )
          ),
          upColor:
            settingsDraftVol.volBar.upColor ||
            DEFAULT_VOL_SETTINGS.volBar.upColor,
          downColor:
            settingsDraftVol.volBar.downColor ||
            DEFAULT_VOL_SETTINGS.volBar.downColor,
        },
        mavolStyles,
        markerPump: { ...settingsDraftVol.markerPump }, // 包含 enabled
        markerDump: { ...settingsDraftVol.markerDump }, // 包含 enabled
      });
      dialogManager.close();
      render();
    },
    onClose: () => dialogManager.close(),
  });
}

// 频率记录（用于是否继承 dataZoom 的判断）
const lastFreq = ref(vm.freq.value);
const visibleRange = ref({ sIdx: 0, eIdx: 0 });

// 渲染（按主窗逻辑决定是否继承 dataZoom）
function render() {
  if (!chart) return;
  const dzCurrent = getCurrentZoomIndexRange();
  const totalLen = (vm.candles.value || []).length || 1;
  const sIdx = Number.isFinite(+dzCurrent?.sIdx) ? +dzCurrent.sIdx : 0;
  const eIdx = Number.isFinite(+dzCurrent?.eIdx)
    ? +dzCurrent.eIdx
    : totalLen - 1;
  const visCount = Math.max(1, eIdx - sIdx + 1);
  const hostWidth = host.value ? host.value.clientWidth : 0;

  const option = buildVolumeOption(
    {
      candles: vm.candles.value,
      indicators: vm.indicators.value,
      freq: vm.freq.value,
      volCfg: settings.volSettings.value,
      volEnv: { hostWidth, visCount },
    },
    {}
  );

  // 与主窗一致：是否允许继承上次 dataZoom
  let allowCarryZoom = lastFreq.value === vm.freq.value;
  const prevOpt = chart.getOption?.();
  const lenNow = (vm.candles.value || []).length;
  if (
    allowCarryZoom &&
    prevOpt &&
    Array.isArray(prevOpt.dataZoom) &&
    prevOpt.dataZoom.length
  ) {
    const z = prevOpt.dataZoom.find((x) => typeof x.startValue !== "undefined");
    if (
      z &&
      typeof z.endValue !== "undefined" &&
      lenNow > 0 &&
      Number(z.endValue) >= lenNow - 1
    ) {
      allowCarryZoom = false;
    }
  } else if (lastFreq.value !== vm.freq.value) {
    allowCarryZoom = false;
  }
  if (
    allowCarryZoom &&
    prevOpt &&
    Array.isArray(prevOpt.dataZoom) &&
    prevOpt.dataZoom.length
  ) {
    option.dataZoom = prevOpt.dataZoom;
  }

  chart.setOption(option, true);
  lastFreq.value = vm.freq.value;

  const dz2 = getCurrentZoomIndexRange();
  if (dz2) {
    visibleRange.value = { sIdx: dz2.sIdx, eIdx: dz2.eIdx };
    recomputeVisibleStats({ startValue: dz2.sIdx, endValue: dz2.eIdx });
  } else {
    recomputeVisibleStats({ startValue: sIdx, endValue: eIdx });
  }
}

function getCurrentZoomIndexRange() {
  try {
    if (!chart) return null;
    const opt = chart.getOption?.();
    const dz = Array.isArray(opt?.dataZoom) ? opt.dataZoom : [];
    if (!dz.length) return null;
    const z = dz.find(
      (x) =>
        typeof x.startValue !== "undefined" || typeof x.endValue !== "undefined"
    );
    const len = (vm.candles.value || []).length;
    if (!len) return null;
    if (
      z &&
      typeof z.startValue !== "undefined" &&
      typeof z.endValue !== "undefined"
    ) {
      const sIdx = Math.max(0, Math.min(len - 1, Number(z.startValue)));
      const eIdx = Math.max(0, Math.min(len - 1, Number(z.endValue)));
      return { sIdx: Math.min(sIdx, eIdx), eIdx: Math.max(sIdx, eIdx) };
    }
    const z2 = dz[0];
    if (z2 && typeof z2.start === "number" && typeof z2.end === "number") {
      const maxIdx = len - 1;
      const sIdx = Math.round((z2.start / 100) * maxIdx);
      const eIdx = Math.round((z2.end / 100) * maxIdx);
      return {
        sIdx: Math.max(0, Math.min(maxIdx, Math.min(sIdx, eIdx))),
        eIdx: Math.max(0, Math.min(maxIdx, Math.max(sIdx, eIdx))),
      };
    }
  } catch {}
  return null;
}

function recomputeVisibleStats(params) {
  try {
    const dates = (vm.candles.value || []).map((d) => d.t);
    const len = dates.length;
    if (!len) {
      stat.value = {
        total: "-",
        mean: "-",
        max: "-",
        pumpDays: 0,
        maxConsecDump: 0,
      };
      visibleRange.value = { sIdx: 0, eIdx: 0 };
      return;
    }
    const info = (params && params.batch && params.batch[0]) || params || {};
    let sIdx = 0,
      eIdx = len - 1;
    if (
      typeof info.startValue !== "undefined" &&
      typeof info.endValue !== "undefined"
    ) {
      sIdx = Math.max(0, Math.min(len - 1, Number(info.startValue)));
      eIdx = Math.max(0, Math.min(len - 1, Number(info.endValue)));
    } else if (typeof info.start === "number" && typeof info.end === "number") {
      const maxIdx = len - 1;
      sIdx = Math.round((info.start / 100) * maxIdx);
      eIdx = Math.round((info.end / 100) * maxIdx);
      sIdx = Math.max(0, Math.min(maxIdx, sIdx));
      eIdx = Math.max(0, Math.min(maxIdx, eIdx));
    }
    if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];
    visibleRange.value = { sIdx, eIdx };

    const vs = settings.volSettings.value || {};
    const baseSeries =
      vs.mode === "amount"
        ? (vm.candles.value || []).map((d) =>
            typeof d.a === "number" ? d.a : null
          )
        : vm.indicators.value?.VOLUME ||
          (vm.candles.value || []).map((d) =>
            typeof d.v === "number" ? d.v : null
          );

    const enablePeriods = Object.values(vs.mavolStyles || {})
      .filter((x) => x && x.enabled)
      .map((x) => +x.period)
      .filter((n) => Number.isFinite(n) && n > 0);
    const minP = enablePeriods.length ? Math.min(...enablePeriods) : null;

    const mavol = (function smaLocal(arr, n) {
      if (!Array.isArray(arr) || !arr.length || !Number.isFinite(+n) || n <= 0)
        return new Array(arr.length).fill(null);
      const out = new Array(arr.length).fill(null);
      let sum = 0,
        cnt = 0;
      for (let i = 0; i < arr.length; i++) {
        const v = Number(arr[i]);
        if (Number.isFinite(v)) {
          sum += v;
          cnt += 1;
        }
        if (i >= n) {
          const ov = Number(arr[i - n]);
          if (Number.isFinite(ov)) {
            sum -= ov;
            cnt -= 1;
          }
        }
        out[i] = cnt > 0 && i >= n - 1 ? sum / cnt : null;
      }
      return out;
    })(baseSeries, minP || 0);

    const pumpK = Number.isFinite(+vs?.markerPump?.threshold)
      ? +vs.markerPump.threshold
      : DEFAULT_VOL_SETTINGS.markerPump.threshold;
    const dumpK = Number.isFinite(+vs?.markerDump?.threshold)
      ? +vs.markerDump.threshold
      : DEFAULT_VOL_SETTINGS.markerDump.threshold;

    let sum = 0,
      cnt = 0,
      mx = 0,
      pumpDays = 0,
      maxConsecDump = 0,
      currDump = 0;
    for (let i = sIdx; i <= eIdx; i++) {
      const v = Number(baseSeries[i]);
      if (Number.isFinite(v)) {
        sum += v;
        cnt += 1;
        if (v > mx) mx = v;
      }
      if (
        mavol &&
        pumpK > 0 &&
        Number.isFinite(v) &&
        Number.isFinite(mavol[i]) &&
        mavol[i] > 0 &&
        v >= pumpK * mavol[i]
      )
        pumpDays += 1;
      if (
        mavol &&
        dumpK > 0 &&
        Number.isFinite(v) &&
        Number.isFinite(mavol[i]) &&
        mavol[i] > 0 &&
        v <= dumpK * mavol[i]
      ) {
        currDump += 1;
        if (currDump > maxConsecDump) maxConsecDump = currDump;
      } else {
        currDump = 0;
      }
    }
    const mean = cnt > 0 ? sum / cnt : 0;
    const fmt0 = (x) => (Number.isFinite(+x) ? (+x).toFixed(0) : "-");
    stat.value = {
      total: fmt0(sum),
      mean: fmt0(mean),
      max: fmt0(mx),
      pumpDays,
      maxConsecDump,
    };
  } catch {
    stat.value = {
      total: "-",
      mean: "-",
      max: "-",
      pumpDays: 0,
      maxConsecDump: 0,
    };
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
  try {
    chart.getZr().on("mousemove", (e) => {
      try {
        const point = [e.offsetX, e.offsetY];
        const result = chart.convertFromPixel({ seriesIndex: 0 }, point);
        if (Array.isArray(result)) {
          const idx = Math.round(result[0]);
          const len = (vm.candles.value || []).length;
          if (Number.isFinite(idx) && idx >= 0 && idx < len) {
            window.dispatchEvent(
              new CustomEvent("chan:hover-index", { detail: { idx } })
            );
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
          window.dispatchEvent(
            new CustomEvent("chan:hover-index", { detail: { idx } })
          );
        }
      } catch {}
    });
  } catch {}
  try {
    ro = new ResizeObserver(() =>
      chart?.resize({
        width: host.value.clientWidth,
        height: host.value.clientHeight,
      })
    );
    ro.observe(el);
  } catch {}
  winResizeHandler = () =>
    chart?.resize({
      width: host.value.clientWidth,
      height: host.value.clientHeight,
    });
  window.addEventListener("resize", winResizeHandler);

  await nextTick();
  requestAnimationFrame(() =>
    chart?.resize({
      width: host.value.clientWidth,
      height: host.value.clientHeight,
    })
  );

  detachSync = zoomSync.attach(
    "volume",
    chart,
    () => (vm.candles.value || []).length
  );

  chart.on("dataZoom", (params) => {
    recomputeVisibleStats(params);
    const info = (params && params.batch && params.batch[0]) || params || {};
    if (
      typeof info.startValue !== "undefined" &&
      typeof info.endValue !== "undefined"
    ) {
      visibleRange.value = { sIdx: info.startValue, eIdx: info.endValue };
    } else if (typeof info.start === "number" && typeof info.end === "number") {
      const len = (vm.candles.value || []).length;
      const maxIdx = Math.max(0, len - 1);
      const sIdx = Math.round((info.start / 100) * maxIdx);
      const eIdx = Math.round((info.end / 100) * maxIdx);
      visibleRange.value = {
        sIdx: Math.max(0, Math.min(maxIdx, Math.min(sIdx, eIdx))),
        eIdx: Math.max(0, Math.min(maxIdx, Math.max(sIdx, eIdx))),
      };
    }
    render();
  });

  visibleRange.value = {
    sIdx: 0,
    eIdx: Math.max(0, (vm.candles.value || []).length - 1),
  };
  render();
  updateHeaderFromCurrent();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", winResizeHandler);
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
});

// 统一 watcher：交由 render 内部决定是否继承 dataZoom
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
  () => vm.loading.value,
  async (isLoading) => {
    if (isLoading) return;
    await nextTick();
    updateHeaderFromCurrent();
  }
);

// 拖拽改高
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
  border: 1px solid #444;
  border-radius: 6px;
  padding: 6px 10px;
  color: #ddd;
  cursor: pointer;
}
.btn.icon {
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style>
