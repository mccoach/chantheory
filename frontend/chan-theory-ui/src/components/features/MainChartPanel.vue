<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\MainChartPanel.vue -->
<!-- ====================================================================== -->
<!-- 主图组件（根因修复 · 去除顶层 await import · 程序化 dataZoom 守护 + 有效变化判定）
     变更说明（严格最小改动，未改变原有代码块顺序；仅在必要处插入逻辑）：
     1) 新增“程序化 dataZoom 标志位 programmaticZoomInProgress”，任何通过程序调用
        dispatchAction/setOption 导致的 dataZoom 事件，onDataZoom 开头直接 return，阻断回环。
     2) 新增“有效变化判定（第一性原则）”：仅当关键三项（barsCount/rightTs/hostWidth→markerWidthPx）
        的离散意义上发生变化时，才调用 hub.execute(…)；未变则直接 return。
        - onDataZoom：若 bars 未变 → Pan（仅右端）；若 bars 变化 → ScrollZoom（双改）。
        - onWheelZoom：以“当前鼠标位置 convertFromPixel → centerIdx”为中心缩放；若不可用回退 currentIndex。
        - 按键左右 KeyMove：以“最后一次聚焦 bar”为起点（跨窗体保持一致，并实时持久化），
          在切片内仅更新高亮不移动窗口；越界时按步平滑移动 rightTs，保持聚焦 bar 在可视范围内。
     3) 新增 lastAppliedRange 记忆已应用范围，避免 dataZoom 循环。
     4) render() 中 setOption 前后加守护，并给 dataZoom 注入初始范围，根除首帧闪回 ALL 问题。
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
          :class="{ active: vm.windowPreset.value === p }"
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

  <!-- 高级面板 -->
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
    @wheel.prevent="onWheelZoom"
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
import { buildUpDownMarkers, buildFractalMarkers } from "@/charts/chan/layers";

// 指令注册（保留）
defineOptions({ directives: { selectAll: vSelectAll } });

// 注入（保留顺序）
const vm = inject("marketView");
const settings = useUserSettings();
const { findBySymbol } = useSymbolIndex();
const dialogManager = inject("dialogManager");

// —— 新增：显示状态中枢（单例） —— //
const hub = useViewCommandHub();

// 覆盖式防抖（保留）
let renderSeq = 0;
function isStale(seq) {
  return seq !== renderSeq;
}

// 预设列表（保留）
const presets = computed(() => WINDOW_PRESETS.slice());

// 频率切换（保留）
const isActiveK = (f) => vm.chartType.value === "kline" && vm.freq.value === f;
function activateK(f) {
  vm.chartType.value = "kline";
  vm.setFreq(f);
}

// 高级面板（保留）
const advancedOpen = ref(false);
const advStart = ref(vm.visibleRange.value.startStr || "");
const advEnd = ref(vm.visibleRange.value.endStr || "");
const barsStr = ref("");
const canApplyManual = computed(() => true);
const canApplyBars = computed(() => /^\d+$/.test((barsStr.value || "").trim()));
function toggleAdvanced() {
  advancedOpen.value = !advancedOpen.value;
}

// ECharts 句柄与观察者（保留）
const wrap = ref(null);
const host = ref(null);
let chart = null;
let ro = null;
let detachSync = null;

// --- 关键修复：记忆最后一次成功应用的 dataZoom 范围，打断“持续闪回”的循环 ---
let lastAppliedRange = { s: null, e: null };

// —— 新增：程序化 dataZoom 守护标志 —— //
// 说明：任何通过程序（dispatchAction/setOption）触发的 dataZoom 事件，onDataZoom 直接 return，阻断回环。
let programmaticZoomInProgress = false;

// 设置草稿（保留）
// 新增字段（在 openSettingsDialog 时合入默认）
const settingsDraft = reactive({
  kForm: { ...DEFAULT_KLINE_STYLE }, // 包含 originalEnabled/mergedEnabled/displayOrder/mergedK
  maForm: {},
  chanForm: { ...CHAN_DEFAULTS },
  fractalForm: { ...FRACTAL_DEFAULTS },
  adjust: DEFAULT_APP_PREFERENCES.adjust,
});

// 当前可见根数（保留）
const localVisRows = ref(Math.max(1, Number(vm.meta.value?.view_rows || 1)));

// —— 新增：预览态的 start/end/bars 引用（用于顶栏即时显示） —— //
const previewStartStr = ref(""); // 即时预览的起始 ISO
const previewEndStr = ref(""); // 即时预览的结束 ISO
const previewBarsCount = ref(0); // 即时预览的 bars 数（中枢 barsCount）

// —— Helper：将毫秒转 ISO（保留格式规则） —— //
function msToIso(ms) {
  try {
    return new Date(ms).toISOString();
  } catch {
    return null;
  }
}

// —— Helper：从当前中枢状态与本地 candles 计算预览 sIdx/eIdx 与起止字符串 —— //
// 说明：为满足“顶栏实时显示”，任何主动交互完成后调用一次本函数并应用 dataZoom（dispatchAction）。
function computePreviewRangeFromHub() {
  const arr = vm.candles.value || [];
  const len = arr.length;
  if (!len) return null;
  const tsArr = arr
    .map((d) => Date.parse(d.t))
    .filter((x) => Number.isFinite(x));
  if (!tsArr.length) return null;

  const st = hub.getState();
  const bars = Math.max(1, Number(st.barsCount || 1));
  let eIdx = len - 1;
  if (Number.isFinite(st.rightTs)) {
    for (let i = len - 1; i >= 0; i--) {
      if (tsArr[i] <= st.rightTs) {
        eIdx = i;
        break;
      }
    }
  }
  const sIdx = Math.max(0, eIdx - bars + 1);
  const startStr = msToIso(tsArr[sIdx]) || arr[sIdx]?.t || "";
  const endStr = msToIso(tsArr[eIdx]) || arr[eIdx]?.t || "";
  return { sIdx, eIdx, startStr, endStr, bars };
}

// —— Helper：应用预览区间到图表（程序化 dataZoom，带标志位阻断回环） —— //
function applyPreviewRange(range) {
  if (!range || !chart) return;
  try {
    programmaticZoomInProgress = true;
    chart.dispatchAction({
      type: "dataZoom",
      startValue: range.sIdx,
      endValue: range.eIdx,
    });
    // --- 关键修复：更新记忆范围 ---
    lastAppliedRange = { s: range.sIdx, e: range.eIdx };
  } catch {}
  // rAF 后恢复，确保本轮程序化 dataZoom 不被 onDataZoom 处理
  requestAnimationFrame(() => {
    programmaticZoomInProgress = false;
  });
}

/* 异步 setOption 包装 */
// —— Helper：异步 setOption 封装（新增） —— //
// 说明：为避免在主流程/事件中调用 setOption，引入异步补丁封装；不改变原函数调用点前后顺序，仅将底层 setOption 调用改为异步。
function scheduleSetOption(patch, opts) {
  requestAnimationFrame(() => {
    try {
      chart && chart.setOption(patch, opts);
    } catch (e) {
      console.error("scheduleSetOption error:", e);
    }
  });
}

// 设置窗内容组件（保留）
// 改动点：renderDisplay 内首行“原始K线”与“合并K线”行的控件与重置；onSave 合并新字段
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

    // 保留原 renderDisplay/renderChan ...
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
            (e) => (settingsDraft.kForm.originalEnabled = !!e.target.checked)
          ),
          // 重置：恢复原始K线相关默认与复权默认
          resetBtn(() => {
            Object.assign(settingsDraft.kForm, {
              upColor: DEFAULT_KLINE_STYLE.upColor,
              downColor: DEFAULT_KLINE_STYLE.downColor,
              originalFadeUpPercent: DEFAULT_KLINE_STYLE.originalFadeUpPercent,
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
                  MK.displayOrder || DEFAULT_KLINE_STYLE.mergedK.displayOrder
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
            settingsDraft.kForm.mergedK = { ...DEFAULT_KLINE_STYLE.mergedK };
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
                  (settingsDraft.chanForm.downShape = String(e.target.value)),
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
                (settingsDraft.chanForm.showUpDownMarkers = !!e.target.checked),
            }),
          ]),
          resetBtn(() => {
            settingsDraft.chanForm.upShape = CHAN_DEFAULTS.upShape;
            settingsDraft.chanForm.upColor = CHAN_DEFAULTS.upColor;
            settingsDraft.chanForm.downShape = CHAN_DEFAULTS.downShape;
            settingsDraft.chanForm.downColor = CHAN_DEFAULTS.downColor;
            settingsDraft.chanForm.anchorPolicy = CHAN_DEFAULTS.anchorPolicy;
            settingsDraft.chanForm.showUpDownMarkers =
              CHAN_DEFAULTS.showUpDownMarkers;
          }),
        ])
      );

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
              value: Number(ff.minTickCount ?? 0),
              onInput: (e) =>
                (settingsDraft.fractalForm.minTickCount = Math.max(
                  0,
                  parseInt(e.target.value || 0, 10)
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
              value: Number(ff.minPct ?? 0),
              onInput: (e) =>
                (settingsDraft.fractalForm.minPct = Math.max(
                  0,
                  Number(e.target.value || 0)
                )),
            })
          ),
          itemCell(
            "判断条件",
            h(
              "select",
              {
                class: "input",
                value: String(ff.minCond || "or"),
                onChange: (e) =>
                  (settingsDraft.fractalForm.minCond = String(e.target.value)),
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
                  onChange: (e) => (conf.bottomShape = String(e.target.value)),
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
                  (settingsDraft.fractalForm.confirmStyle.bottomShape = String(
                    e.target.value
                  )),
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
                (settingsDraft.fractalForm.confirmStyle.bottomColor = String(
                  e.target.value
                )),
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

// 打开设置窗（保留）
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
        } catch (e) {
          console.error("resetAll (MainChart) failed:", e);
        }
      },
      onSave: async () => {
        try {
          settings.setKlineStyle(settingsDraft.kForm);
          settings.setMaConfigs(settingsDraft.maForm);
          settings.setChanSettings({ ...settingsDraft.chanForm });
          settings.setFractalSettings({ ...settingsDraft.fractalForm });
          const nextAdjust = String(settingsDraft.adjust || "none");
          const adjustChanged = nextAdjust !== prevAdjust;
          if (adjustChanged) {
            settings.setAdjust(nextAdjust);
          } else {
            recomputeChan();
            render();
          }
          dialogManager.close();
        } catch (e) {
          console.error("apply settings failed:", e);
          dialogManager.close();
        }
      },
      onClose: () => dialogManager.close(),
    });
  } catch (e) {
    console.error("openSettingsDialog error:", e);
  }
}

// 标题与刷新状态（保留）
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

// 键盘左右键（修复：以最后聚焦 bar 为起点；切片内不移动窗口；越界时平滑移动 rightTs）
let currentIndex = -1;
function onGlobalHoverIndex(e) {
  const idx = Number(e?.detail?.idx);
  if (Number.isFinite(idx) && idx >= 0) {
    currentIndex = idx;
    try {
      const arr = vm.candles.value || [];
      const tsVal = arr[idx]?.t ? Date.parse(arr[idx].t) : null;
      if (Number.isFinite(tsVal)) {
        settings.setLastFocusTs(vm.code.value, vm.freq.value, tsVal); // 实时持久化最后聚焦 ts
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

  // 若在当前视窗内 → 仅更新高亮，不移动窗口
  if (nextIdx >= sIdx && nextIdx <= eIdx) {
    currentIndex = nextIdx;
    try {
      const seq = renderSeq;
      chart.dispatchAction({
        type: "showTip",
        seriesIndex: 0,
        dataIndex: currentIndex,
      });
      if (!isStale(seq)) {
        chart.dispatchAction({
          type: "highlight",
          seriesIndex: 0,
          dataIndex: currentIndex,
        });
      }
    } catch {}
    // 持久化最新聚焦 ts
    try {
      const tsv = tsArr[nextIdx];
      if (Number.isFinite(tsv)) {
        settings.setLastFocusTs(vm.code.value, vm.freq.value, tsv);
      }
    } catch {}
    return;
  }

  // 越界：按步平滑移动窗口（bars 宽度保持不变），仅调整 rightTs
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

  // 仅移动切片右端（平滑 Pan）
  if (Number.isFinite(nextRightTs)) {
    hub.execute("KeyMove", { nextRightTs });
  }

  // 更新高亮为目标 bar，并持久化最后聚焦 ts
  currentIndex = nextIdx;
  try {
    const seq = renderSeq;
    chart.dispatchAction({
      type: "showTip",
      seriesIndex: 0,
      dataIndex: currentIndex,
    });
    if (!isStale(seq)) {
      chart.dispatchAction({
        type: "highlight",
        seriesIndex: 0,
        dataIndex: currentIndex,
      });
    }
  } catch {}
  try {
    const tsv = tsArr[nextIdx];
    if (Number.isFinite(tsv)) {
      settings.setLastFocusTs(vm.code.value, vm.freq.value, tsv);
    }
  } catch {}
}

// 缠论/分型缓存与重算（保留）
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

// CHAN 占位系列（保留，但调用 setOption 改为异步封装）
function chanPlaceholderSeriesCommon() {
  return {
    type: "scatter",
    yAxisIndex: 1,
    data: [],
    symbol: "triangle",
    symbolSize: () => [8, 10],
    symbolOffset: [0, 12],
    itemStyle: { color: "#f56c6c", opacity: 0.9 },
    tooltip: { show: false },
    z: 2,
    emphasis: { scale: false },
  };
}
function ensureChanSeriesPresent() {
  if (!chart) return;
  try {
    const opt = chart.getOption?.();
    const series = Array.isArray(opt?.series) ? opt.series : [];
    const hasUp = series.some((s) => s && s.id === "CHAN_UP");
    const hasDn = series.some((s) => s && s.id === "CHAN_DOWN");
    const patches = [];
    if (!hasUp) {
      const base = chanPlaceholderSeriesCommon();
      patches.push({
        ...base,
        id: "CHAN_UP",
        name: "CHAN_UP",
        itemStyle: {
          color: settings.chanSettings.value.upColor || "#f56c6c",
          opacity: 0.9,
        },
      });
    }
    if (!hasDn) {
      const base = chanPlaceholderSeriesCommon();
      patches.push({
        ...base,
        id: "CHAN_DOWN",
        name: "CHAN_DOWN",
        itemStyle: {
          color: settings.chanSettings.value.downColor || "#00ff00",
          opacity: 0.9,
        },
      });
    }
    if (patches.length) {
      // —— 变更：占位系列 patch 改为异步 setOption —— //
      scheduleSetOption({ series: patches }, false);
    }
  } catch {}
}

// 缠论标记更新（统一使用中枢 markerWidthPx；series patch 改为异步）
async function updateChanMarkers(seq) {
  if (!chart) return;
  if (isStale(seq)) return;

  const reduced = chanCache.value.reduced || [];
  const fractals = chanCache.value.fractals || [];

  const visCount = Math.max(
    1,
    Number(localVisRows.value || vm.meta.value?.view_rows || 1)
  );
  const hostW = host.value ? host.value.clientWidth : 800;
  const markerW = hub.markerWidthPx.value;

  try {
    ensureChanSeriesPresent();
  } catch {}
  const patches = [];

  if (settings.chanSettings.value.showUpDownMarkers && reduced.length) {
    const upDownLayer = buildUpDownMarkers(reduced, {
      chanSettings: settings.chanSettings.value,
      hostWidth: hostW,
      visCount,
      symbolWidthPx: markerW,
    });
    patches.push(...(upDownLayer.series || []));
  } else {
    patches.push({ id: "CHAN_UP", data: [] }, { id: "CHAN_DOWN", data: [] });
  }

  const frEnabled = (settings.fractalSettings.value?.enabled ?? true) === true;
  if (frEnabled && reduced.length && fractals.length) {
    const frLayer = buildFractalMarkers(reduced, fractals, {
      fractalSettings: settings.fractalSettings.value,
      hostWidth: hostW,
      visCount,
      symbolWidthPx: markerW,
    });
    patches.push(...(frLayer.series || []));
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
    for (const id of FR_IDS) patches.push({ id, data: [] });
  }

  try {
    if (isStale(seq)) return;
    // —— 变更：series patch 改为异步 setOption —— //
    scheduleSetOption({ series: patches }, false);
  } catch {}
}

// —— 修复 onDataZoom：程序化守护 + 有效变化判定 + Pan/Zoom 分支 —— //
function onDataZoom(params) {
  try {
    // 1) 程序化 dataZoom：直接忽略（阻断回环）
    if (programmaticZoomInProgress) return;

    const info = (params && params.batch && params.batch[0]) || params || {};
    const len = (vm.candles.value || []).length;
    if (!len) return;

    // 2) 提取索引区间（优先索引，其次百分比）
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

    // —— 新增：若这次 dataZoom 跟“最后一次已应用范围”完全相同，直接返回，打断循环 —— //
    if (lastAppliedRange.s === sIdx && lastAppliedRange.e === eIdx) {
      return;
    }

    // 3) 有效变化判定（仅关键三项）
    const currBars = Math.max(
      1,
      Number(hub.getState().barsCount || vm.viewRows || 1)
    );
    const bars_new = Math.max(1, eIdx - sIdx + 1);

    // 注意：用 vm.viewEndIdx 可能与当前图上的范围不同步，容易误判。
    // 改成用 lastAppliedRange.e（若已初始化），更贴近当前图的真实范围。
    const currEIdx = Number.isFinite(lastAppliedRange.e)
      ? lastAppliedRange.e
      : Number(vm.viewEndIdx);
    const changedBars = bars_new !== currBars;
    const changedEIdx = eIdx !== currEIdx;

    if (!changedBars && !changedEIdx) {
      // 无离散变化：直接忽略
      return;
    }

    // 4) Pan vs ScrollZoom 判定与执行
    const tsArr = (vm.candles.value || []).map((d) => Date.parse(d.t));
    const anchorTs = Number.isFinite(tsArr[eIdx])
      ? tsArr[eIdx]
      : hub.getState().rightTs;

    if (!changedBars && changedEIdx) {
      // 仅右端变化 → Pan
      // 再次对比 rightTs，避免不必要执行
      if (anchorTs !== hub.getState().rightTs) {
        hub.execute("Pan", { nextRightTs: anchorTs });
      }
    } else {
      // 视为缩放：bars 或 bars+右端双变
      if (bars_new !== currBars || anchorTs !== hub.getState().rightTs) {
        hub.execute("ScrollZoom", {
          nextBars: bars_new,
          nextRightTs: anchorTs,
        });
      }
    }

    // —— 新增：顶栏预览即时更新（不等待后端） —— //
    previewBarsCount.value = bars_new;
    const startStr =
      msToIso(tsArr[sIdx]) || (vm.candles.value || [])[sIdx]?.t || "";
    const endStr =
      msToIso(tsArr[eIdx]) || (vm.candles.value || [])[eIdx]?.t || "";
    previewStartStr.value = startStr || "";
    previewEndStr.value = endStr || "";
    // 注：不在此处调用 setOption；交由 watch(meta)/异步 patch 统一落地
  } catch {}
}

// 预设：右端不变，仅改变左端（不触发 setOption；交由 watch(meta) 落地）
function onClickPreset(preset) {
  try {
    const pkey = String(preset || "ALL");
    // --- 关键修复：移除此判断，确保每次点击都执行，从而将非标准 bars 校正为标准值 ---
    // if (vm.windowPreset.value === pkey) {
    //   // 预设键未变，直接忽略（这是导致问题的根源）
    //   return;
    // }
    vm.windowPreset.value = pkey;
    settings.setWindowPreset(vm.windowPreset.value);
    const st = hub.getState();
    hub.execute("ChangeWidthPreset", { presetKey: pkey, allRows: st.allRows });

    // —— 新增：预览 —— //
    const range = computePreviewRangeFromHub();
    if (range) {
      applyPreviewRange(range);
      previewStartStr.value = range.startStr || "";
      previewEndStr.value = range.endStr || "";
      previewBarsCount.value = range.bars;
    }
  } catch (e) {
    console.error("onClickPreset error:", e);
  }
}

// 滚轮缩放：双改；以“当前鼠标悬浮位置”为中心（convertFromPixel），不可用时回退 currentIndex
function onWheelZoom(e) {
  const arr = vm.candles.value || [];
  const n = arr.length;
  if (!n || !chart) return;

  // —— 修复 convertFromPixel 前的“坐标系就绪”判断（新增） —— //
  const opt = chart.getOption?.() || {};
  const readyCoord =
    Array.isArray(opt?.xAxis) &&
    (Array.isArray(opt?.series) ? opt.series.length > 0 : false);
  if (!readyCoord) return;

  // 优先：根据当前鼠标位置计算中心索引（更稳健）
  let centerIdx = -1;
  try {
    const result = chart.convertFromPixel({ seriesIndex: 0 }, [
      e.offsetX,
      e.offsetY,
    ]);
    if (Array.isArray(result)) {
      centerIdx = Math.round(result[0]);
    }
  } catch {}
  if (!Number.isFinite(centerIdx) || centerIdx < 0 || centerIdx >= n) {
    centerIdx =
      Number.isFinite(currentIndex) && currentIndex >= 0
        ? Math.max(0, Math.min(n - 1, currentIndex))
        : Math.floor((vm.viewStartIdx + vm.viewEndIdx) / 2);
  }

  // 目标 bars
  const currBars = Math.max(
    1,
    Number(hub.getState().barsCount || vm.viewRows || 1)
  );
  const deltaBars =
    e.deltaY < 0
      ? -Math.max(1, Math.floor(currBars * 0.12))
      : Math.max(1, Math.floor(currBars * 0.12));
  let nextBars = Math.max(1, currBars + deltaBars);

  // 以 centerIdx 为中心确定窗口，并计算 anchorTs
  const half = Math.floor(nextBars / 2);
  let sIdx = Math.max(0, centerIdx - half);
  let eIdx = sIdx + nextBars - 1;
  if (eIdx > n - 1) {
    eIdx = n - 1;
    sIdx = Math.max(0, eIdx - nextBars + 1);
  }
  const anchorTs = Date.parse(arr[eIdx]?.t);

  // 有效变化判定：bars 或 rightTs 任一变化
  const st = hub.getState();
  const changedBars = nextBars !== st.barsCount;
  const changedRt = Number.isFinite(anchorTs) && anchorTs !== st.rightTs;

  if (!changedBars && !changedRt) return;

  hub.execute("ScrollZoom", { nextBars, nextRightTs: anchorTs });
}

// 应用服务端视窗（程序化 dataZoom，带标志位）
function applyZoomByMeta(seq) {
  if (!chart) return;
  if (isStale(seq)) return;
  const len = (vm.candles.value || []).length;
  if (!len) return;
  const sIdx = Number(vm.meta.value?.view_start_idx ?? 0);
  const eIdx = Number(vm.meta.value?.view_end_idx ?? len - 1);

  localVisRows.value = Math.max(1, eIdx - sIdx + 1);
  // 若与已应用范围一致则无需再发 dataZoom
  if (lastAppliedRange.s === sIdx && lastAppliedRange.e === eIdx) return;

  try {
    programmaticZoomInProgress = true;
    chart.dispatchAction({
      type: "dataZoom",
      startValue: sIdx,
      endValue: eIdx,
    });
    // —— 新增：更新记忆范围 —— //
    lastAppliedRange = { s: sIdx, e: eIdx };
  } catch {}
  requestAnimationFrame(() => {
    programmaticZoomInProgress = false;
  });
}

// 安全 resize：仅当 markerWidthPx 将变化时才执行中枢（避免噪声）
function safeResize() {
  if (!chart || !host.value) return;
  const seq = renderSeq;
  requestAnimationFrame(() => {
    if (isStale(seq)) return;
    try {
      const nextW = host.value.clientWidth;
      chart.resize({
        width: nextW,
        height: host.value.clientHeight,
      });
      // 关键变化判定：markerWidthPx 是否会改变
      const st = hub.getState();
      const approxNextMarker = Math.max(
        1,
        Math.min(16, Math.round((nextW * 0.88) / Math.max(1, st.barsCount)))
      );
      if (approxNextMarker !== hub.markerWidthPx.value) {
        hub.execute("ResizeHost", { widthPx: nextW });
      }
    } catch {}
    updateChanMarkers(renderSeq);
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

  // —— 修复 convertFromPixel 调用前的坐标系就绪判断（新增） —— //
  chart.getZr().on("mousemove", (e) => {
    try {
      const opt = chart.getOption?.() || {};
      const readyCoord =
        Array.isArray(opt?.xAxis) &&
        (Array.isArray(opt?.series) ? opt.series.length > 0 : false);
      if (!readyCoord) return;
      const result = chart.convertFromPixel({ seriesIndex: 0 }, [
        e.offsetX,
        e.offsetY,
      ]);
      if (Array.isArray(result)) {
        const idx = Math.round(result[0]);
        const l = (vm.candles.value || []).length;
        if (Number.isFinite(idx) && idx >= 0 && idx < l)
          broadcastHoverIndex(idx);
      }
    } catch {}
  });

  chart.on("updateAxisPointer", (params) => {
    try {
      const axisInfo = (params?.axesInfo && params.axesInfo[0]) || null;
      const label = axisInfo?.value;
      const dates = (vm.candles.value || []).map((d) => d.t);
      const idx = dates.indexOf(label);
      if (idx >= 0) broadcastHoverIndex(idx);
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

  detachSync = zoomSync.attach(
    "main",
    chart,
    () => (vm.candles.value || []).length
  );

  // —— 中枢订阅：保持原逻辑（预览与事件转发） —— //
  hub.onChange((snapshot) => {
    try {
      // 禁止在程序化 dataZoom 期间改变窗口预设高亮；仅在 bars 真实变化时由 onDataZoom 决定
      vm.windowPreset.value = snapshot.presetKey || vm.windowPreset.value;
      window.dispatchEvent(
        new CustomEvent("chan:marker-size", {
          detail: { px: snapshot.markerWidthPx },
        })
      );
    } catch {}
    requestAnimationFrame(() => updateChanMarkers(renderSeq));

    // —— 只在确实变化时才程序化设置 dataZoom，避免“每次广播都触发 dataZoom” —— //
    const range = computePreviewRangeFromHub();
    if (range) {
      // 若当前将要应用的范围与最后一次已应用一致，则不再触发 dataZoom
      if (
        lastAppliedRange.s !== range.sIdx ||
        lastAppliedRange.e !== range.eIdx
      ) {
        applyPreviewRange(range); // 内部会设置 programmatic 守护
        // 预览文案
        previewStartStr.value = range.startStr || "";
        previewEndStr.value = range.endStr || "";
        previewBarsCount.value = range.bars;
      }
    }
  });

  recomputeChan();
  render();
  requestAnimationFrame(() => updateChanMarkers(renderSeq)); // 首帧异步标记层更新
  updateHeaderFromCurrent();

  window.addEventListener("chan:hover-index", onGlobalHoverIndex);
});

onBeforeUnmount(() => {
  window.removeEventListener("chan:hover-index", onGlobalHoverIndex);
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

// 渲染主图（主 setOption 保留；增量 series patch异步；dataZoom 落地由 applyZoomByMeta 负责）
function render() {
  if (!chart) return;
  const mySeq = ++renderSeq;

  const needAvoidAxis = !!(
    settings.chanSettings.value.showUpDownMarkers &&
    (chanCache.value.reduced || []).length > 0
  );
  const extraAxisLabelMargin = needAvoidAxis ? 20 : 6;

  // --- 关键修复：在 buildMainChartOption 时传入初始范围 ---
  const len = (vm.candles.value || []).length;
  const sInit = Number(vm.meta.value?.view_start_idx ?? 0);
  const eInit = Number(vm.meta.value?.view_end_idx ?? (len ? len - 1 : 0));

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
      mapOrigToReduced: chanCache.value.map,
    },
    {
      tooltipClass: "ct-fixed-tooltip",
      xAxisLabelMargin: extraAxisLabelMargin,
      // 传递初始范围给 options.js 的 applyUi
      initialRange: { startValue: sInit, endValue: eInit },
    }
  );

  // 保持 CHAN 占位系列存在（原逻辑）
  const seriesArr = Array.isArray(option.series) ? option.series : [];
  const haveUp = seriesArr.some((s) => s && s.id === "CHAN_UP");
  const haveDn = seriesArr.some((s) => s && s.id === "CHAN_DOWN");
  if (!haveUp || !haveDn) {
    const upBase = chanPlaceholderSeriesCommon();
    const dnBase = chanPlaceholderSeriesCommon();
    if (!haveUp) {
      seriesArr.push({
        ...upBase,
        id: "CHAN_UP",
        name: "CHAN_UP",
        itemStyle: {
          color: settings.chanSettings.value.upColor || "#f56c6c",
          opacity: 0.9,
        },
      });
    }
    if (!haveDn) {
      seriesArr.push({
        ...dnBase,
        id: "CHAN_DOWN",
        name: "CHAN_DOWN",
        itemStyle: {
          color: settings.chanSettings.value.downColor || "#00ff00",
          opacity: 0.9,
        },
      });
    }
    option.series = seriesArr;
  }

  try {
    chart.dispatchAction({ type: "hideTip" });
  } catch {}

  // --- 关键修复：setOption 期间开启程序化守护，并同步记忆范围 ---
  programmaticZoomInProgress = true;
  chart.setOption(option, { notMerge: true, lazyUpdate: false, silent: true });
  lastAppliedRange = { s: sInit, e: eInit }; // 同步记忆
  requestAnimationFrame(() => {
    programmaticZoomInProgress = false; // 恢复
    updateChanMarkers(mySeq); // 异步标记层 patch
    // 再次以 meta 落地（如果与 lastAppliedRange 相同，applyZoomByMeta 会短路不再触发）
    applyZoomByMeta(mySeq);
  });
}

// 数据/配置变化重算重绘（保留顺序；异步标记层）
watch(
  () => [
    vm.candles.value,
    vm.indicators.value,
    vm.chartType.value,
    vm.freq.value,
    settings.maConfigs.value,
    settings.klineStyle.value,
    vm.adjust.value,
    settings.fractalSettings.value,
  ],
  () => {
    recomputeChan();
    render();
  },
  { deep: true }
);

// meta 变化应用视窗与标记更新（保留；异步提示与标记层）
watch(
  () => vm.meta.value,
  async () => {
    await nextTick();
    const mySeq = ++renderSeq;
    applyZoomByMeta(mySeq);
    requestAnimationFrame(() => updateChanMarkers(mySeq)); // 异步
    updateHeaderFromCurrent();
    refreshedAt.value = new Date();
    showRefreshed.value = true;
    setTimeout(() => {
      showRefreshed.value = false;
    }, 2000);
  },
  { deep: true }
);

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

// 标题更新（保留）
function updateHeaderFromCurrent() {
  const sym = (vm.meta.value?.symbol || vm.code.value || "").trim();
  const frq = String(vm.meta.value?.freq || vm.freq.value || "").trim();
  let name = "";
  try {
    name = findBySymbol(sym)?.name?.trim() || "";
  } catch {}
  displayHeader.value = { name, code: sym, freq: frq };
}

// 顶栏显示：起止（优先预览）、Bars（优先预览）
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

// 跨窗 hover（保留）
function broadcastHoverIndex(idx) {
  try {
    window.dispatchEvent(
      new CustomEvent("chan:hover-index", { detail: { idx: Number(idx) } })
    );
  } catch {}
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
