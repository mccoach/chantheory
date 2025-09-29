<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\MainChartPanel.vue -->
<!-- ====================================================================== -->
<!-- 主图组件（接入“上游统一渲染中枢 useViewRenderHub” · 一次订阅一次渲染）
     改动目标（一次性 setOption，杜绝竞态）：
     1) 保留原有参数准备与模块职责（buildMainChartOption、CHAN 覆盖层/分型标记等）；
     2) 将原本“基础主图 setOption + 覆盖层 series patch 的多次 setOption”合并为“单次 setOption 装配到位”，
        即在 onRender 回调中一次性准备好主图 option + 覆盖层 series，并一次 setOption(notMerge)；
     3) 避免在 ECharts 主流程期间调用 setOption/resize：所有 setOption/resize 经“双跳脱”调度（rAF+setTimeout(0)）；
     4) 订阅时机调整：renderHub.onRender 在 chart.init 之后注册（避免首帧快照被丢弃）。
     注：除上述必要调整外，其他交互、模块、计算流程保持原样；对原代码块顺序不调整，订阅时机移动处注明理由。
-->
<!-- ====================================================================== -->

<template>
  <!-- 顶部控制区（三列布局） -->
  <div class="controls controls-grid">
    <!-- 左列：频率按钮（切频会触发后端 reload） -->
    <div class="ctrl-col left">
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

    <!-- 中列：起止短文本与 Bars 数（显示层） -->
    <div class="ctrl-col middle">
      <div class="kv">
        <span class="k">起止：</span>
        <span class="v">{{ formattedStart }}</span>
        <span> → </span>
        <span class="v">{{ formattedEnd }}</span>
      </div>
      <div class="kv">
        <span class="k">Bars：</span>
        <span class="v">{{ topBarsCount }}</span>
      </div>
    </div>

    <!-- 右列：窗宽预设按钮 + 高级开关（预设仅本地处理） -->
    <div class="ctrl-col right">
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
        <button
          class="seg-btn adv-btn"
          :title="'自定义'"
          @click="toggleAdvanced"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M4 7h10M4 17h10"
              stroke="#ddd"
              stroke-width="1.8"
              stroke-linecap="round"
            />
            <circle cx="18" cy="7" r="2.2" fill="#ddd" />
            <circle cx="18" cy="17" r="2.2" fill="#ddd" />
          </svg>
        </button>
      </div>
    </div>
  </div>

  <!-- 高级面板（手输日期/N 根/可见窗口） -->
  <div v-if="advancedOpen" class="advanced-panel">
    <div class="adv-row">
      <div class="label">手动日期</div>
      <input
        type="date"
        class="date-input"
        v-model="advStart"
        v-select-all
        :title="'开始日期（YYYY-MM-DD）'"
      />
      <span class="sep">至</span>
      <input
        type="date"
        class="date-input"
        v-model="advEnd"
        v-select-all
        :title="'结束日期（YYYY-MM-DD）'"
      />
      <button
        class="btn small"
        @click="applyManualRange"
        :disabled="!canApplyManual"
      >
        应用
      </button>
    </div>
    <div class="adv-row">
      <div class="label">最近 N 根</div>
      <input class="bars-input" v-model="barsStr" placeholder="如 300" />
      <button
        class="btn small"
        @click="applyBarsRange"
        :disabled="!canApplyBars"
      >
        应用
      </button>
      <div class="hint">
        说明：N 根缩放仅通过中枢改变 bars（右端不变），按向下就近规则高亮预设。
      </div>
    </div>
    <div class="adv-row">
      <div class="label">可见窗口</div>
      <div class="visible">
        <span class="date">{{
          fmtShort(vm.visibleRange.value.startStr) || "-"
        }}</span>
        →
        <span class="date">{{
          fmtShort(vm.visibleRange.value.endStr) || "-"
        }}</span>
        <button
          class="btn small"
          @click="applyVisible"
          :disabled="!vm.visibleRange.value.startStr"
        >
          应用为数据窗口
        </button>
      </div>
    </div>
  </div>

  <!-- 主图画布容器 -->
  <div
    ref="wrap"
    class="chart"
    tabindex="0"
    @keydown="onKeydown"
    @mouseenter="focusWrap"
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
  defineComponent,
  h,
  reactive,
} from "vue";
import * as echarts from "echarts";
import {
  buildMainChartOption,
  createFixedTooltipPositioner,
} from "@/charts/options";
import {
  DEFAULT_MA_CONFIGS,
  CHAN_DEFAULTS,
  DEFAULT_KLINE_STYLE,
  DEFAULT_APP_PREFERENCES,
  FRACTAL_DEFAULTS,
  FRACTAL_SHAPES,
  FRACTAL_FILLS,
  WINDOW_PRESETS,
} from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { computeInclude, computeFractals } from "@/composables/useChan";
import { vSelectAll } from "@/utils/inputBehaviors";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import { buildUpDownMarkers, buildFractalMarkers } from "@/charts/chan/layers";

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

/* MOD: 增加“当前高亮预设键”的响应式变量，并订阅中枢快照 */
const activePresetKey = ref(hub.getState().presetKey || "ALL");
hub.onChange((st) => {
  activePresetKey.value = st.presetKey || "ALL";
});

/* 覆盖式防抖/序号守护 */
let renderSeq = 0;
function isStale(seq) {
  return seq !== renderSeq;
}
// 程序化 dataZoom 阻断：范围签名守护（active + sig + ts）
// 说明：
// - 渲染前记录本次程序化应用范围签名（startValue:endValue），onDataZoom 中若签名匹配则早退。
// - 若签名不匹配，视为真实用户交互，关闭守护继续处理；并设置兜底超时自动关闭。
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

// 高级面板输入与状态
const advancedOpen = ref(false);
const advStart = ref(vm.visibleRange.value.startStr || "");
const advEnd = ref(vm.visibleRange.value.endStr || "");
const barsStr = ref("");
const canApplyManual = computed(() => true);
const canApplyBars = computed(() => /^\d+$/.test((barsStr.value || "").trim()));
function toggleAdvanced() {
  advancedOpen.value = !advancedOpen.value;
}

// 手输“起止日期”应用：根据 ALL candles 查索引 → hub.execute(SetDatesManual)
function applyManualRange() {
  const a = String(advStart.value || "").trim();
  const b = String(advEnd.value || "").trim();
  if (!a || !b) return;
  const arr = vm.candles.value || [];
  if (!arr.length) return;
  const toYMD = (s) => String(s).slice(0, 10);
  const sY = toYMD(a);
  const eY = toYMD(b);
  let sIdx = -1,
    eIdx = -1;
  for (let i = 0; i < arr.length; i++) {
    const ymd = toYMD(arr[i].t || "");
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
  if (!isFinite(anchorTs)) return;
  hub.execute("SetDatesManual", { nextBars, nextRightTs: anchorTs });
}

// 手输“N 根”应用：仅改变 bars（右端不变）
function applyBarsRange() {
  const n = Math.max(1, parseInt(String(barsStr.value || "1"), 10));
  hub.execute("SetBarsManual", { nextBars: n });
}

// 将“当前可见窗口”（vm.visibleRange）应用为数据窗口：SetDatesManual
function applyVisible() {
  const start = String(vm.visibleRange.value.startStr || "").trim();
  const end = String(vm.visibleRange.value.endStr || "").trim();
  if (!start || !end) return;
  const arr = vm.candles.value || [];
  if (!arr.length) return;
  const getIdxOfIso = (iso) => {
    const ms = Date.parse(iso);
    if (!isFinite(ms)) return -1;
    let best = -1;
    for (let i = 0; i < arr.length; i++) {
      const t = Date.parse(arr[i].t || "");
      if (isFinite(t) && t <= ms) best = i;
      if (t > ms) break;
    }
    return best;
  };
  const sIdx = Math.max(0, getIdxOfIso(start));
  let eIdx = Math.max(0, getIdxOfIso(end));
  if (eIdx < sIdx) eIdx = sIdx;
  const nextBars = Math.max(1, eIdx - sIdx + 1);
  const anchorTs = Date.parse(arr[eIdx]?.t || "");
  if (!isFinite(anchorTs)) return;
  hub.execute("SetDatesManual", { nextBars, nextRightTs: anchorTs });
}

/* 画布/实例与 Resize */
const wrap = ref(null);
const host = ref(null);
let chart = null;
let ro = null;

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

/* 设置弹窗（保持原逻辑） */
const settingsDraft = reactive({
  kForm: { ...DEFAULT_KLINE_STYLE },
  maForm: {},
  chanForm: { ...CHAN_DEFAULTS },
  fractalForm: { ...FRACTAL_DEFAULTS },
  adjust: DEFAULT_APP_PREFERENCES.adjust,
});
let prevAdjust = "none";
function openSettingsDialog() {
  try {
    settingsDraft.kForm = JSON.parse(
      JSON.stringify({
        ...DEFAULT_KLINE_STYLE,
        ...(settings.klineStyle.value || {}),
      })
    );
    const maDefaults = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS));
    const maLocal = settings.maConfigs.value || {};
    Object.keys(maDefaults).forEach((k) => {
      if (maLocal[k]) maDefaults[k] = { ...maDefaults[k], ...maLocal[k] };
    });
    settingsDraft.maForm = maDefaults;
    settingsDraft.chanForm = JSON.parse(
      JSON.stringify({
        ...CHAN_DEFAULTS,
        ...(settings.chanSettings.value || {}),
      })
    );
    settingsDraft.fractalForm = JSON.parse(
      JSON.stringify({
        ...FRACTAL_DEFAULTS,
        ...(settings.fractalSettings.value || {}),
      })
    );
    prevAdjust = String(
      vm.adjust.value || settings.adjust.value || DEFAULT_APP_PREFERENCES.adjust
    );
    settingsDraft.adjust = prevAdjust;

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
              type: "button",
              onClick,
            }),
          ]);

        // 行情显示（原始K/合并K/MA）
        const renderDisplay = () => {
          const K = settingsDraft.kForm;
          const rows = [];

          // —— 原始K线行（按：柱宽/阳线颜色/阴线颜色/复权/显示层级/勾选框/重置按钮） —— //
          rows.push(
            h("div", { class: "std-row" }, [
              nameCell("原始K线"),
              // 复权
              itemCell(
                "复权",
                h(
                  "select",
                  {
                    class: "input",
                    value: String(
                      settingsDraft.adjust || DEFAULT_APP_PREFERENCES.adjust
                    ),
                    onChange: (e) =>
                      (settingsDraft.adjust = String(e.target.value || "none")),
                  },
                  [
                    h("option", { value: "none" }, "不复权"),
                    h("option", { value: "qfq" }, "前复权"),
                    h("option", { value: "hfq" }, "后复权"),
                  ]
                )
              ),
              // 阳线颜色
              itemCell(
                "阳线颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: K.upColor || DEFAULT_KLINE_STYLE.upColor,
                  onInput: (e) =>
                    (settingsDraft.kForm.upColor = String(
                      e.target.value || DEFAULT_KLINE_STYLE.upColor
                    )),
                })
              ),
              // 阳线淡显（0~100）
              itemCell(
                "阳线淡显",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0,
                  max: 100,
                  step: 1,
                  value: Number(
                    K.originalFadeUpPercent ??
                      DEFAULT_KLINE_STYLE.originalFadeUpPercent
                  ),
                  onInput: (e) => {
                    const v = Math.max(
                      0,
                      Math.min(
                        100,
                        Number(
                          e.target.value ||
                            DEFAULT_KLINE_STYLE.originalFadeUpPercent
                        )
                      )
                    );
                    settingsDraft.kForm.originalFadeUpPercent = v;
                  },
                })
              ),
              // 阴线颜色
              itemCell(
                "阴线颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: K.downColor || DEFAULT_KLINE_STYLE.downColor,
                  onInput: (e) =>
                    (settingsDraft.kForm.downColor = String(
                      e.target.value || DEFAULT_KLINE_STYLE.downColor
                    )),
                })
              ),
              // 阴线淡显（0~100）
              itemCell(
                "阴线淡显",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0,
                  max: 100,
                  step: 1,
                  value: Number(
                    K.originalFadeDownPercent ??
                      DEFAULT_KLINE_STYLE.originalFadeDownPercent
                  ),
                  onInput: (e) => {
                    const v = Math.max(
                      0,
                      Math.min(
                        100,
                        Number(
                          e.target.value ||
                            DEFAULT_KLINE_STYLE.originalFadeDownPercent
                        )
                      )
                    );
                    settingsDraft.kForm.originalFadeDownPercent = v;
                  },
                })
              ),
              // 原始K线开关
              checkCell(
                !!K.originalEnabled,
                (e) =>
                  (settingsDraft.kForm.originalEnabled = !!e.target.checked)
              ),
              // 重置：恢复原始K线相关默认与复权默认
              resetBtn(() => {
                Object.assign(settingsDraft.kForm, {
                  upColor: DEFAULT_KLINE_STYLE.upColor,
                  downColor: DEFAULT_KLINE_STYLE.downColor,
                  originalFadeUpPercent:
                    DEFAULT_KLINE_STYLE.originalFadeUpPercent,
                  originalFadeDownPercent:
                    DEFAULT_KLINE_STYLE.originalFadeDownPercent,
                  originalEnabled: DEFAULT_KLINE_STYLE.originalEnabled,
                });
                settingsDraft.adjust = String(
                  DEFAULT_APP_PREFERENCES.adjust || "none"
                );
              }),
            ])
          );

          // 合并K线行：轮廓线宽 / 上涨颜色 / 下跌颜色 / 填充淡显 / 显示层级（先/后） / 勾选 / 重置
          const MK =
            settingsDraft.kForm.mergedK ||
            (settingsDraft.kForm.mergedK = { ...DEFAULT_KLINE_STYLE.mergedK });
          rows.push(
            h("div", { class: "std-row" }, [
              nameCell("合并K线"),
              // 轮廓线宽
              itemCell(
                "轮廓线宽",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0.1,
                  max: 6,
                  step: 0.1,
                  value: Number(
                    MK.outlineWidth ?? DEFAULT_KLINE_STYLE.mergedK.outlineWidth
                  ),
                  onInput: (e) =>
                    (settingsDraft.kForm.mergedK.outlineWidth = Math.max(
                      0.1,
                      Number(e.target.value || 1.2)
                    )),
                })
              ),
              // 上涨颜色（轮廓与填充）
              itemCell(
                "上涨颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: MK.upColor || DEFAULT_KLINE_STYLE.mergedK.upColor,
                  onInput: (e) =>
                    (settingsDraft.kForm.mergedK.upColor = String(
                      e.target.value || DEFAULT_KLINE_STYLE.mergedK.upColor
                    )),
                })
              ),
              // 下跌颜色（轮廓与填充）
              itemCell(
                "下跌颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: MK.downColor || DEFAULT_KLINE_STYLE.mergedK.downColor,
                  onInput: (e) =>
                    (settingsDraft.kForm.mergedK.downColor = String(
                      e.target.value || DEFAULT_KLINE_STYLE.mergedK.downColor
                    )),
                })
              ),
              // 填充淡显（0~100）
              itemCell(
                "填充淡显",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0,
                  max: 100,
                  step: 1,
                  value: Number(
                    MK.fillFadePercent ??
                      DEFAULT_KLINE_STYLE.mergedK.fillFadePercent
                  ),
                  onInput: (e) => {
                    const v = Math.max(
                      0,
                      Math.min(100, Number(e.target.value || 0))
                    );
                    settingsDraft.kForm.mergedK.fillFadePercent = v;
                  },
                })
              ),
              // 显示层级（先/后）
              itemCell(
                "显示层级",
                h(
                  "select",
                  {
                    class: "input",
                    value: String(
                      MK.displayOrder ||
                        DEFAULT_KLINE_STYLE.mergedK.displayOrder
                    ),
                    onChange: (e) =>
                      (settingsDraft.kForm.mergedK.displayOrder = String(
                        e.target.value
                      )),
                  },
                  [
                    h("option", { value: "first" }, "先"),
                    h("option", { value: "after" }, "后"),
                  ]
                )
              ),
              // 合并K线开关
              checkCell(
                !!settingsDraft.kForm.mergedEnabled,
                (e) => (settingsDraft.kForm.mergedEnabled = !!e.target.checked)
              ),
              // 重置：恢复合并K线相关默认
              resetBtn(() => {
                settingsDraft.kForm.mergedEnabled =
                  DEFAULT_KLINE_STYLE.mergedEnabled;
                settingsDraft.kForm.mergedK = {
                  ...DEFAULT_KLINE_STYLE.mergedK,
                };
              }),
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
                    value:
                      conf.color ||
                      DEFAULT_MA_CONFIGS[key]?.color ||
                      DEFAULT_MA_CONFIGS.MA5.color,
                    onInput: (e) =>
                      (settingsDraft.maForm[key].color = String(
                        e.target.value ||
                          DEFAULT_MA_CONFIGS[key]?.color ||
                          DEFAULT_MA_CONFIGS.MA5.color
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
                    max: 999,
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
                  const def = DEFAULT_MA_CONFIGS[key];
                  if (def) {
                    settingsDraft.maForm[key] = { ...def };
                  }
                }),
              ])
            );
          });
          return rows;
        };

        // 缠论设置（保留原有“涨跌标记 + 分型判定 + 强/标准/弱 + 确认分型”）
        const renderChan = () => {
          const cf = settingsDraft.chanForm;
          const rows = [];

          // 涨跌标记
          rows.push(
            h("div", { class: "std-row" }, [
              nameCell("涨跌标记"),
              itemCell(
                "上涨符号",
                h(
                  "select",
                  {
                    class: "input",
                    value: cf.upShape || CHAN_DEFAULTS.upShape,
                    onChange: (e) =>
                      (settingsDraft.chanForm.upShape = String(e.target.value)),
                  },
                  (FRACTAL_SHAPES || []).map((opt) =>
                    h("option", { value: opt.v }, opt.label)
                  )
                )
              ),
              itemCell(
                "上涨颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: cf.upColor || CHAN_DEFAULTS.upColor,
                  onInput: (e) =>
                    (settingsDraft.chanForm.upColor = String(
                      e.target.value || CHAN_DEFAULTS.upColor
                    )),
                })
              ),
              itemCell(
                "下跌符号",
                h(
                  "select",
                  {
                    class: "input",
                    value: cf.downShape || CHAN_DEFAULTS.downShape,
                    onChange: (e) =>
                      (settingsDraft.chanForm.downShape = String(
                        e.target.value
                      )),
                  },
                  (FRACTAL_SHAPES || []).map((opt) =>
                    h("option", { value: opt.v }, opt.label)
                  )
                )
              ),
              itemCell(
                "下跌颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: cf.downColor || CHAN_DEFAULTS.downColor,
                  onInput: (e) =>
                    (settingsDraft.chanForm.downColor = String(
                      e.target.value || CHAN_DEFAULTS.downColor
                    )),
                })
              ),
              itemCell(
                "承载点",
                h(
                  "select",
                  {
                    class: "input",
                    value: cf.anchorPolicy || CHAN_DEFAULTS.anchorPolicy,
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
                    (settingsDraft.chanForm.showUpDownMarkers =
                      !!e.target.checked),
                }),
              ]),
              resetBtn(() => {
                settingsDraft.chanForm.upShape = CHAN_DEFAULTS.upShape;
                settingsDraft.chanForm.upColor = CHAN_DEFAULTS.upColor;
                settingsDraft.chanForm.downShape = CHAN_DEFAULTS.downShape;
                settingsDraft.chanForm.downColor = CHAN_DEFAULTS.downColor;
                settingsDraft.chanForm.anchorPolicy =
                  CHAN_DEFAULTS.anchorPolicy;
                settingsDraft.chanForm.showUpDownMarkers =
                  CHAN_DEFAULTS.showUpDownMarkers;
              }),
            ])
          );

          // 分型判定 + 强/标准/弱 + 确认分型（完整回归）
          const ff = settingsDraft.fractalForm;
          const styleByStrength = (ff.styleByStrength =
            ff.styleByStrength ||
            JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.styleByStrength)));
          const confirmStyle = (ff.confirmStyle =
            ff.confirmStyle ||
            JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.confirmStyle)));

          rows.push(
            h("div", { class: "std-row" }, [
              nameCell("分型判定"),
              itemCell(
                "最小tick",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0,
                  step: 1,
                  value: Number(
                    ff.minTickCount ?? FRACTAL_DEFAULTS.minTickCount
                  ),
                  onInput: (e) =>
                    (settingsDraft.fractalForm.minTickCount = Math.max(
                      0,
                      parseInt(
                        e.target.value || FRACTAL_DEFAULTS.minTickCount,
                        10
                      )
                    )),
                })
              ),
              itemCell(
                "最小幅度%",
                h("input", {
                  class: "input num",
                  type: "number",
                  min: 0,
                  step: 0.01,
                  value: Number(ff.minPct ?? FRACTAL_DEFAULTS.minPct),
                  onInput: (e) =>
                    (settingsDraft.fractalForm.minPct = Math.max(
                      0,
                      Number(e.target.value || FRACTAL_DEFAULTS.minPct)
                    )),
                })
              ),
              itemCell(
                "判断条件",
                h(
                  "select",
                  {
                    class: "input",
                    value: String(ff.minCond || FRACTAL_DEFAULTS.minCond),
                    onChange: (e) =>
                      (settingsDraft.fractalForm.minCond = String(
                        e.target.value
                      )),
                  },
                  [
                    h("option", { value: "or" }, "或"),
                    h("option", { value: "and" }, "与"),
                  ]
                )
              ),
              h("div"),
              h("div"),
              h("div"),
              resetBtn(() => {
                settingsDraft.fractalForm.minTickCount =
                  FRACTAL_DEFAULTS.minTickCount;
                settingsDraft.fractalForm.minPct = FRACTAL_DEFAULTS.minPct;
                settingsDraft.fractalForm.minCond = FRACTAL_DEFAULTS.minCond;
              }),
            ])
          );

          const specs = [
            { k: "strong", label: "强分型" },
            { k: "standard", label: "标准分型" },
            { k: "weak", label: "弱分型" },
          ];
          function resetStrengthRow(key) {
            styleByStrength[key] = JSON.parse(
              JSON.stringify(FRACTAL_DEFAULTS.styleByStrength[key])
            );
          }
          for (const sp of specs) {
            const conf = styleByStrength[sp.k];
            rows.push(
              h("div", { class: "std-row" }, [
                nameCell(sp.label),
                itemCell(
                  "底分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.bottomShape,
                      onChange: (e) =>
                        (conf.bottomShape = String(e.target.value)),
                    },
                    (FRACTAL_SHAPES || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                itemCell(
                  "底分颜色",
                  h("input", {
                    class: "input color",
                    type: "color",
                    value: conf.bottomColor,
                    onInput: (e) => (conf.bottomColor = String(e.target.value)),
                  })
                ),
                itemCell(
                  "顶分符号",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.topShape,
                      onChange: (e) => (conf.topShape = String(e.target.value)),
                    },
                    (FRACTAL_SHAPES || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                itemCell(
                  "顶分颜色",
                  h("input", {
                    class: "input color",
                    type: "color",
                    value: conf.topColor,
                    onInput: (e) => (conf.topColor = String(e.target.value)),
                  })
                ),
                itemCell(
                  "填充",
                  h(
                    "select",
                    {
                      class: "input",
                      value: conf.fill,
                      onChange: (e) => (conf.fill = String(e.target.value)),
                    },
                    (FRACTAL_FILLS || []).map((opt) =>
                      h("option", { value: opt.v }, opt.label)
                    )
                  )
                ),
                h("div", { class: "std-check" }, [
                  h("input", {
                    type: "checkbox",
                    checked: !!conf.enabled,
                    onChange: (e) => (conf.enabled = !!e.target.checked),
                  }),
                ]),
                resetBtn(() => resetStrengthRow(sp.k)),
              ])
            );
          }

          rows.push(
            h("div", { class: "std-row" }, [
              nameCell("确认分型"),
              itemCell(
                "底分符号",
                h(
                  "select",
                  {
                    class: "input",
                    value: confirmStyle.bottomShape,
                    onChange: (e) =>
                      (settingsDraft.fractalForm.confirmStyle.bottomShape =
                        String(e.target.value)),
                  },
                  (FRACTAL_SHAPES || []).map((opt) =>
                    h("option", { value: opt.v }, opt.label)
                  )
                )
              ),
              itemCell(
                "底分颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: confirmStyle.bottomColor,
                  onInput: (e) =>
                    (settingsDraft.fractalForm.confirmStyle.bottomColor =
                      String(e.target.value)),
                })
              ),
              itemCell(
                "顶分符号",
                h(
                  "select",
                  {
                    class: "input",
                    value: confirmStyle.topShape,
                    onChange: (e) =>
                      (settingsDraft.fractalForm.confirmStyle.topShape = String(
                        e.target.value
                      )),
                  },
                  (FRACTAL_SHAPES || []).map((opt) =>
                    h("option", { value: opt.v }, opt.label)
                  )
                )
              ),
              itemCell(
                "顶分颜色",
                h("input", {
                  class: "input color",
                  type: "color",
                  value: confirmStyle.topColor,
                  onInput: (e) =>
                    (settingsDraft.fractalForm.confirmStyle.topColor = String(
                      e.target.value
                    )),
                })
              ),
              itemCell(
                "填充",
                h(
                  "select",
                  {
                    class: "input",
                    value: confirmStyle.fill,
                    onChange: (e) =>
                      (settingsDraft.fractalForm.confirmStyle.fill = String(
                        e.target.value
                      )),
                  },
                  (FRACTAL_FILLS || []).map((opt) =>
                    h("option", { value: opt.v }, opt.label)
                  )
                )
              ),
              h("div", { class: "std-check" }, [
                h("input", {
                  type: "checkbox",
                  checked: !!confirmStyle.enabled,
                  onChange: (e) =>
                    (settingsDraft.fractalForm.confirmStyle.enabled =
                      !!e.target.checked),
                }),
              ]),
              resetBtn(() => {
                const def = FRACTAL_DEFAULTS.confirmStyle;
                settingsDraft.fractalForm.confirmStyle = JSON.parse(
                  JSON.stringify(def)
                );
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

    dialogManager.open({
      title: "行情显示设置",
      contentComponent: MainChartSettingsContent,
      props: {},
      tabs: [
        { key: "display", label: "行情显示" },
        { key: "chan", label: "缠论标记" },
      ],
      activeTab: "display",
      onResetAll: () => {
        try {
          Object.assign(settingsDraft.kForm, { ...DEFAULT_KLINE_STYLE });
          settingsDraft.adjust = String(
            DEFAULT_APP_PREFERENCES.adjust || "none"
          );
          const defs = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS));
          settingsDraft.maForm = defs;
          settingsDraft.chanForm = JSON.parse(JSON.stringify(CHAN_DEFAULTS));
          settingsDraft.fractalForm = JSON.parse(
            JSON.stringify(FRACTAL_DEFAULTS)
          );
        } catch (e) {}
      },
      onSave: () => {
        try {
          settings.setKlineStyle(settingsDraft.kForm);
          settings.setMaConfigs(settingsDraft.maForm);
          settings.setChanSettings({ ...settingsDraft.chanForm });
          settings.setFractalSettings({ ...settingsDraft.fractalForm });
          const nextAdjust = String(settingsDraft.adjust || "none");
          const adjustChanged = nextAdjust !== prevAdjust;
          if (adjustChanged) {
            settings.setAdjust(nextAdjust);
          }

          // MOD: 立即触发中枢刷新，发布新快照 -> 即时应用新设置
          hub.execute("Refresh", {});

          dialogManager.close();
        } catch (e) {
          dialogManager.close();
        }
      },
      onClose: () => dialogManager.close(),
    });
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

/* 键盘左右键（保持原逻辑） */
let currentIndex = -1;
function onGlobalHoverIndex(e) {
  const idx = Number(e?.detail?.idx);
  if (Number.isFinite(idx) && idx >= 0) {
    currentIndex = idx;
    try {
      const arr = vm.candles.value || [];
      const tsVal = arr[idx]?.t ? Date.parse(arr[idx].t) : null;
      if (Number.isFinite(tsVal)) {
        settings.setLastFocusTs(vm.code.value, vm.freq.value, tsVal);
      }
    } catch {}
  }
}
function focusWrap() {
  try {
    wrap.value?.focus?.();
  } catch {}
}
function onKeydown(e) {
  if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
  e.preventDefault();

  const arr = vm.candles.value || [];
  const len = arr.length;
  if (!len) return;

  const sIdx = Number(vm.meta.value?.view_start_idx ?? 0);
  const eIdx = Number(vm.meta.value?.view_end_idx ?? len - 1);
  const tsArr = arr.map((d) => Date.parse(d.t));

  // 起点：优先当前 currentIndex；否则从持久化的最后聚焦 ts 回找索引；再否则以 eIdx 起
  let startIdx =
    Number.isFinite(currentIndex) && currentIndex >= 0 ? currentIndex : -1;
  if (startIdx < 0) {
    try {
      const lastTs = settings.getLastFocusTs(vm.code.value, vm.freq.value);
      if (Number.isFinite(lastTs)) {
        const found = tsArr.findIndex(
          (t) => Number.isFinite(t) && t === lastTs
        );
        startIdx = found >= 0 ? found : -1;
      }
    } catch {}
  }
  if (startIdx < 0) startIdx = eIdx; // 兜底以右端为起点

  // 目标索引（一步）
  let nextIdx = startIdx + (e.key === "ArrowLeft" ? -1 : +1);
  nextIdx = Math.max(0, Math.min(len - 1, nextIdx));

  // 若在当前视窗内 → 仅更新十字线/tooltip，对齐交给 ECharts 组联动（唯一机制）
  const inView = nextIdx >= sIdx && nextIdx <= eIdx;

  currentIndex = nextIdx;

  try {
    // 使用 ECharts 内建：先更新轴指示（会通过 group 联动同步其它窗体）
    // 将数据索引转换为像素 X 坐标
    const pxX =
      chart && typeof chart.convertToPixel === "function"
        ? chart.convertToPixel({ xAxisIndex: 0 }, nextIdx)
        : null;
    if (Number.isFinite(pxX)) {
      chart.dispatchAction({
        type: "updateAxisPointer",
        currTrigger: "mousemove",
        x: pxX,
      });
    }
    // 源窗显式 showTip，保证本窗 tooltip 可见（其他窗体会随 group 联动对齐）
    chart.dispatchAction({
      type: "showTip",
      seriesIndex: 0,
      dataIndex: currentIndex,
    });
  } catch {}

  // 持久化最新聚焦 ts（保留）
  try {
    const tsv = tsArr[nextIdx];
    if (Number.isFinite(tsv)) {
      settings.setLastFocusTs(vm.code.value, vm.freq.value, tsv);
    }
  } catch {}

  if (inView) return;

  // 越界：按步平滑移动窗口（bars 宽度保持不变），仅调整 rightTs（中枢路径不变）
  const viewWidth = Math.max(1, eIdx - sIdx + 1);
  let newEIdx = eIdx;
  if (nextIdx < sIdx) {
    const delta = sIdx - nextIdx; // 向左越界步数
    newEIdx = Math.max(viewWidth - 1, eIdx - delta);
  } else if (nextIdx > eIdx) {
    const delta = nextIdx - eIdx; // 向右越界步数
    newEIdx = Math.min(len - 1, eIdx + delta);
  }
  const nextRightTs = Number.isFinite(tsArr[newEIdx])
    ? tsArr[newEIdx]
    : tsArr[eIdx];

  if (Number.isFinite(nextRightTs)) {
    hub.execute("KeyMove", { nextRightTs });
  }
}

/* 缠论/分型覆盖层 —— 构造覆盖层 series（一次性装配） */
const chanCache = ref({ reduced: [], map: [], meta: null, fractals: [] });
function recomputeChan() {
  try {
    const arr = vm.candles.value || [];
    if (!arr.length) {
      chanCache.value = { reduced: [], map: [], meta: null, fractals: [] };
      return;
    }
    const policy =
      settings.chanSettings.value.anchorPolicy || CHAN_DEFAULTS.anchorPolicy;
    const res = computeInclude(arr, { anchorPolicy: policy });
    const fr = computeFractals(res.reducedBars || [], {
      minTickCount: settings.fractalSettings.value.minTickCount || 0,
      minPct: settings.fractalSettings.value.minPct || 0,
      minCond: String(settings.fractalSettings.value.minCond || "or"),
    });
    chanCache.value = {
      reduced: res.reducedBars || [],
      map: res.mapOrigToReduced || [],
      meta: res.meta || null,
      fractals: fr || [],
    };
  } catch {
    chanCache.value = { reduced: [], map: [], meta: null, fractals: [] };
  }
}

/**
 * 构造覆盖层 series（一次性装配）
 * - 保持原有 buildUpDownMarkers/buildFractalMarkers 的使用与样式；
 * - 若禁用或无数据，则输出占位系列（CHAN_UP/CHAN_DOWN 空），满足不变量；
 * - 返回数组，供主图 option.series 直接拼接。
 */
function buildOverlaySeriesForOption({ hostW, visCount, markerW }) {
  const out = [];
  const reduced = chanCache.value.reduced || [];
  const fractals = chanCache.value.fractals || [];

  // 涨跌标记
  if (settings.chanSettings.value.showUpDownMarkers && reduced.length) {
    const upDownLayer = buildUpDownMarkers(reduced, {
      chanSettings: settings.chanSettings.value,
      hostWidth: hostW,
      visCount,
      symbolWidthPx: markerW,
    });
    out.push(...(upDownLayer.series || []));
  } else {
    out.push(
      {
        type: "scatter",
        id: "CHAN_UP",
        name: "CHAN_UP",
        yAxisIndex: 1,
        data: [],
        symbol: "triangle",
        symbolSize: () => [8, 10],
        symbolOffset: [0, 12], // 上移，避免与底部轴标签重叠
        itemStyle: {
          color: settings.chanSettings.value.upColor || CHAN_DEFAULTS.upColor,
          opacity: settings.chanSettings.value.opacity ?? CHAN_DEFAULTS.opacity,
        },
        tooltip: { show: false },
        z: 2,
        emphasis: { scale: false },
      },
      {
        type: "scatter",
        id: "CHAN_DOWN",
        name: "CHAN_DOWN",
        yAxisIndex: 1,
        data: [],
        symbol: "triangle",
        symbolSize: () => [8, 10],
        symbolOffset: [0, 12],
        itemStyle: {
          color:
            settings.chanSettings.value.downColor || CHAN_DEFAULTS.downColor,
          opacity: settings.chanSettings.value.opacity ?? CHAN_DEFAULTS.opacity,
        },
        tooltip: { show: false },
        z: 2,
        emphasis: { scale: false },
      }
    );
  }

  // 分型标记
  const frEnabled = (settings.fractalSettings.value?.enabled ?? true) === true;
  if (frEnabled && reduced.length && fractals.length) {
    const frLayer = buildFractalMarkers(reduced, fractals, {
      fractalSettings: settings.fractalSettings.value,
      hostWidth: hostW,
      visCount,
      symbolWidthPx: markerW,
    });
    out.push(...(frLayer.series || []));
  } else {
    const FR_IDS = [
      "FR_TOP_STRONG",
      "FR_TOP_STANDARD",
      "FR_TOP_WEAK",
      "FR_BOT_STRONG",
      "FR_BOT_STANDARD",
      "FR_BOT_WEAK",
      "FR_TOP_CONFIRM",
      "FR_BOT_CONFIRM",
      "FR_CONFIRM_LINKS",
    ];
    for (const id of FR_IDS) {
      out.push({ id, name: id, type: "scatter", yAxisIndex: 0, data: [] });
    }
  }

  return out;
}

// 交互会话标记与 idle-commit 提交
let userZoomActive = false;
let _dzIdleTimer = null;
let _pendingRange = null;

// dataZoom 期间：不回写范围；仅在短 idle/松手后一次性承接
function onDataZoom(params) {
  try {
    const info = (params && params.batch && params.batch[0]) || params || {};
    const len = (vm.candles.value || []).length;
    if (!len) return;

    // 提取索引区间（优先索引，其次百分比）
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

    // 标记：进入交互会话；仅缓存最终范围
    userZoomActive = true;
    _pendingRange = { sIdx, eIdx };

    // idle-commit：短空闲后一次性承接到中枢
    if (_dzIdleTimer) clearTimeout(_dzIdleTimer);
    _dzIdleTimer = setTimeout(() => {
      try {
        if (!_pendingRange) {
          userZoomActive = false;
          return;
        }
        const { sIdx: s, eIdx: e } = _pendingRange;
        const bars_new = Math.max(1, e - s + 1);
        const tsArr = (vm.candles.value || []).map((d) => Date.parse(d.t));
        const anchorTs = Number.isFinite(tsArr[e])
          ? tsArr[e]
          : hub.getState().rightTs;

        const currBars = Math.max(1, Number(hub.getState().barsCount || 1));
        const currRt = hub.getState().rightTs;
        const needBars = bars_new !== currBars;
        const needRt = Number.isFinite(anchorTs) && anchorTs !== currRt;

        if (needBars || needRt) {
          const action = needBars ? "ScrollZoom" : "Pan";
          const payload = needBars
            ? { nextBars: bars_new, nextRightTs: anchorTs }
            : { nextRightTs: anchorTs };
          hub.execute(action, payload);
        }
      } finally {
        _pendingRange = null;
        userZoomActive = false;
      }
    }, 120); // 短 idle（120ms）后承接一次
  } catch {}
}

/* 一次订阅一次渲染：订阅放到 chart.init 完成后（必要调序） */
let unsubId = null;

function doSinglePassRender(snapshot) {
  try {
    if (!chart || !snapshot) return;
    const mySeq = ++renderSeq;

    // —— 合并K线修复：先 recomputeChan，再用 reducedBars 重建主图 option —— //
    recomputeChan();
    const reduced = chanCache.value.reduced || [];
    const mapReduced = chanCache.value.map || [];

    // 若处于交互会话（用户拖拽/缩放进行中），禁止我们注入 initialRange，避免抢权；
    // 会后承接由 onDataZoom idle-commit 完成。
    const initialRange = userZoomActive
      ? undefined
      : {
          startValue: snapshot.main.range.startValue,
          endValue: snapshot.main.range.endValue,
        };

    // —— tooltip 位置从上游统一源头订阅（renderHub），确保与副窗一致 —— //
    const tipPositioner = renderHub.getTipPositioner();

    // —— 标记显示与避让策略（符号空间仅从“主图有效区内部”挤出） —— //
    const anyMarkers =
      (settings.chanSettings.value?.showUpDownMarkers ?? true) === true &&
      reduced.length > 0;

    // 标签带与标签文本的“基础”间距（恒定）：
    const DEFAULT_MAIN_AXIS_LABEL_SPACE_PX = 28; // 标签带总高度（标签与 slider 的相对间距恒定）
    const BASE_XAXIS_LABEL_MARGIN = 12; // 标签文本到轴线的基础内距（恒定）

    // MOD: 仅通过“主图有效区底部补位”来为符号挤出空间（关闭符号则回收为 0）
    // 建议用统一宽度源近似为符号的垂直尺寸，并加一侧安全边距
    const MARKER_HEIGHT_PX = Math.max(
      2,
      Math.round(snapshot.core?.markerWidthPx || 4)
    );
    const SAFE_PADDING_PX = 12;
    const mainBottomExtraPx = anyMarkers
      ? MARKER_HEIGHT_PX + SAFE_PADDING_PX - 8
      : 0;

    // 关键补偿：标签文本相对轴线的内距等量增加 mainBottomExtraPx，
    // 这样轴线上移多少（挤出符号空间），标签就向下补偿多少，保证“标签相对 slider/画布底边的位置恒定不变”
    const xAxisLabelMargin = BASE_XAXIS_LABEL_MARGIN + mainBottomExtraPx;

    // 组装主图 option（初始范围 + 固定定位器 + 补位与标签补偿）
    const rebuiltMainOption = buildMainChartOption(
      {
        candles: vm.candles.value || [],
        indicators: vm.indicators.value || {},
        chartType: vm.chartType.value || "kline",
        maConfigs: settings.maConfigs.value,
        freq: vm.freq.value || "1d",
        klineStyle: settings.klineStyle.value,
        adjust: vm.adjust.value || "none",
        reducedBars: reduced, // 合并K线数据（关键）
        mapOrigToReduced: mapReduced, // 原始索引→合并索引映射
      },
      {
        initialRange, // 统一可视范围
        tooltipPositioner: tipPositioner, // ← 新增：统一注入定位器
        mainAxisLabelSpacePx: DEFAULT_MAIN_AXIS_LABEL_SPACE_PX, // 不变：标签带高度（标签与 slider 间距恒定）
        xAxisLabelMargin, // 补偿：标签文本到轴线的内距 = 基础值 + 主图内部补位
        mainBottomExtraPx, // 仅此项随标记开关调整“主图有效区高度”
        isInteractionSource: true,
      }
    );

    // 覆盖层（一次性装配到主图 series；保持标记原位置不变）
    const bars = Math.max(1, snapshot.core?.barsCount || 1);
    const hostW = host.value ? host.value.clientWidth : 800;
    const markerW = snapshot.core?.markerWidthPx || 8;
    const overlaySeries = buildOverlaySeriesForOption({
      hostW,
      visCount: bars,
      markerW,
    });

    // —— 保留函数式样式，禁止 JSON 深拷贝（否则 itemStyle.color 等函数会丢失） —— //
    const finalOption = {
      // 浅拷贝主 option 顶层，保留函数与引用
      ...rebuiltMainOption,
      // 独立拷贝 series 数组（保留每个系列对象内的函数）
      series: [...(rebuiltMainOption.series || [])],
    };
    // 拼接覆盖层系列（一次性装配，不改变原合并K线数据结构）
    finalOption.series.push(...overlaySeries);

    // 程序化 dataZoom 签名守护开启（记录本次应用范围签名）
    const guardSig = `${initialRange.startValue}:${initialRange.endValue}`;
    progZoomGuard.active = true;
    progZoomGuard.sig = guardSig;
    progZoomGuard.ts = Date.now();

    // 交互期间与日常渲染：均使用 notMerge=false 的轻量合并，避免重置 ECharts 内建会话状态
    scheduleSetOption(finalOption, {
      notMerge: false,
      lazyUpdate: true,
      silent: true,
    });

    lastAppliedRange = { s: initialRange.startValue, e: initialRange.endValue };

    // 兜底关闭守护（避免长时间处于 active 导致误判）
    setTimeout(() => {
      progZoomGuard.active = false;
    }, 300);

    // 顶栏预览文案
    const sIdx = initialRange.startValue;
    const eIdx = initialRange.endValue;
    const arr = vm.candles.value || [];
    previewStartStr.value = arr[sIdx]?.t || "";
    previewEndStr.value = arr[eIdx]?.t || "";
    previewBarsCount.value = Math.max(1, eIdx - sIdx + 1);
  } catch {}
}

/* 预览显示（保持原逻辑） */
function pad2(n) {
  return String(n).padStart(2, "0");
}
function fmtShort(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const Y = d.getFullYear(),
      M = pad2(d.getMonth() + 1),
      D = pad2(d.getDate());
    if (/m$/.test(String(vm.freq.value || ""))) {
      const h = pad2(d.getHours()),
        m = pad2(d.getMinutes());
      return `${Y}-${M}-${D} ${h}:${m}`;
    }
    return `${Y}-${M}-${D}`;
  } catch {
    return "";
  }
}
const previewStartStr = ref("");
const previewEndStr = ref("");
const previewBarsCount = ref(0);
const formattedStart = computed(() => {
  return (
    (previewStartStr.value && fmtShort(previewStartStr.value)) ||
    fmtShort(vm.visibleRange.value.startStr) ||
    "-"
  );
});
const formattedEnd = computed(() => {
  return (
    (previewEndStr.value && fmtShort(previewEndStr.value)) ||
    fmtShort(vm.visibleRange.value.endStr) ||
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

/* 生命周期（订阅时机调整到 chart.init 后） */
onMounted(() => {
  const el = host.value;
  if (!el) return;
  chart = echarts.init(el, null, {
    renderer: "canvas",
    width: el.clientWidth,
    height: el.clientHeight,
  });
  chart.group = "ct-sync";

  chart.on("updateAxisPointer", (params) => {
    try {
      const axisInfo = (params?.axesInfo && params.axesInfo[0]) || null;
      const label = axisInfo?.value;
      const dates = (vm.candles.value || []).map((d) => d.t);
      const idx = dates.indexOf(label);
      const len = (vm.candles.value || []).length;
      if (idx >= 0 && idx < len) {
        currentIndex = idx;
        // 将“最后聚焦 ts”持久化，供键盘左右键作为起跳点
        const tsVal = vm.candles.value[idx]?.t
          ? Date.parse(vm.candles.value[idx].t)
          : null;
        if (Number.isFinite(tsVal)) {
          settings.setLastFocusTs(vm.code.value, vm.freq.value, tsVal);
        }
      }
    } catch {}
  });

  // 绑定 dataZoom：含“程序化守护 + 有效变化判定”
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

  // —— 订阅 useViewRenderHub：移到 chart.init 完成后（必要调序） —— //
  // 说明：避免首帧快照在 chart 未初始化时被丢弃，导致不渲染。
  unsubId = renderHub.onRender((snapshot) => {
    doSinglePassRender(snapshot);
  });
});

onBeforeUnmount(() => {
  if (unsubId != null) {
    renderHub.offRender(unsubId);
    unsubId = null;
  }

  try {
    ro && ro.disconnect();
  } catch {}
  ro = null;
  try {
    chart && chart.dispose();
  } catch {}
  chart = null;
});

/* 标题/刷新徽标更新（保持原逻辑） */
watch(
  () => vm.meta.value,
  () => {
    updateHeaderFromCurrent();
    refreshedAt.value = new Date();
    showRefreshed.value = true;
    setTimeout(() => {
      showRefreshed.value = false;
    }, 2000);
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
</script>

<style scoped>
.controls-grid {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  column-gap: 16px;
  margin: 0 0 8px 0;
}
.ctrl-col.middle {
  text-align: left;
  color: #ddd;
  user-select: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ctrl-col.right {
  display: inline-flex;
  align-items: center;
}
.kv .k {
  color: #bbb;
}
.kv .v {
  color: #ddd;
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
.adv-btn svg {
  display: block;
}
.adv-btn:hover svg path {
  stroke: #fff;
}
.adv-btn:hover svg circle {
  fill: #fff;
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
  height: 18px;
  background: transparent;
}
</style>
