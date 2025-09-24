<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\MainChartPanel.vue -->
<!-- ====================================================================== -->
<!-- 主图组件（K线/HL柱 + MA + 缩放联动 + 缠论覆盖层 + 分型标记）                -->
<!-- 本版新增要点（逐行注释说明）：                                             -->
<!-- 1) 缩放/拖动与窗宽预设：仅前端本地处理；触达右端且存在缺口时才触发后端 reload。 -->
<!-- 2) 标记符号宽度随缩放变化：新增 localVisRows（当前可见根数），               -->
<!--    在 onDataZoom/onClickPreset/applyZoomByMeta 中维护，                     -->
<!--    updateChanMarkers 以 localVisRows 替代 meta.view_rows 估算柱宽；          -->
<!--    从而在不触发后端的缩放/拖动/预设场景，标记尺寸仍随视窗变化。              -->
<!-- 3) 保持不变量：function render/recomputeChan/updateChanMarkers 等标记；      -->
<!--    dataZoom/updateAxisPointer/getZr("mousemove") 事件绑定；                 -->
<!--    CHAN_UP/CHAN_DOWN 占位；设置窗内容与打开标记；buildFractalMarkers 存在。  -->
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
        <span class="v">{{ barsCount }}</span>
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

  <!-- 高级面板（保留原功能占位） -->
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
      <div class="hint">说明：N 根缩放调用后端计算（右端锚定）。</div>
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

  <!-- 主图画布容器（双击打开设置窗；滚轮仅本地；inside dataZoom 驱动 onDataZoom） -->
  <div
    ref="wrap"
    class="chart"
    tabindex="0"
    @keydown="onKeydown"
    @mouseenter="focusWrap"
    @dblclick="openSettingsDialog"
    @wheel.prevent="onWheelZoom"
  >
    <!-- 顶部信息条：标题与刷新状态提示 -->
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

    <!-- ECharts 宿主画布 -->
    <div ref="host" class="canvas-host"></div>

    <!-- 下沿拖拽条（调整主窗高度） -->
    <div
      class="bottom-strip"
      title="上下拖拽调整窗体高度"
      @mousedown="onResizeHandleDown('bottom', $event)"
    ></div>
  </div>
</template>

<script setup>
// 组合式 API 与 ECharts
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

// 主图 option + dataZoom 联动
import { buildMainChartOption, zoomSync } from "@/charts/options";

// 常量与工具
import {
  DEFAULT_MA_CONFIGS,
  CHAN_DEFAULTS,
  DEFAULT_KLINE_STYLE,
  DEFAULT_APP_PREFERENCES,
  FRACTAL_DEFAULTS,
  FRACTAL_SHAPES,
  FRACTAL_FILLS,
  WINDOW_PRESETS,
  pickPresetByBarsCountDown, // 本地“向下就近”预设高亮
  presetToBars, // 本地 预设→bars 根数
} from "@/constants";

// 用户设置与标的索引
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";

// 去包含与分型识别
import { computeInclude, computeFractals } from "@/composables/useChan";

// 输入框行为
import { vSelectAll } from "@/utils/inputBehaviors";

// 缠论覆盖层：涨跌标记（隐藏 y 轴）与分型标记（主轴）
import { buildUpDownMarkers, buildFractalMarkers } from "@/charts/chan/layers";

// 指令注册
defineOptions({ directives: { selectAll: vSelectAll } });

// 注入 composables
const vm = inject("marketView");
const settings = useUserSettings();
const { findBySymbol } = useSymbolIndex();
const dialogManager = inject("dialogManager");

// 覆盖式防抖：渲染序号
let renderSeq = 0;
function isStale(seq) {
  return seq !== renderSeq;
}

// 预设列表
const presets = computed(() => WINDOW_PRESETS.slice());

// 频率切换（触发后端）
const isActiveK = (f) => vm.chartType.value === "kline" && vm.freq.value === f;
function activateK(f) {
  vm.chartType.value = "kline";
  vm.setFreq(f);
}

// 高级面板状态与行为（占位）
const advancedOpen = ref(false);
const advStart = ref(vm.visibleRange.value.startStr || "");
const advEnd = ref(vm.visibleRange.value.endStr || "");
const barsStr = ref("");
const canApplyManual = computed(() => true);
const canApplyBars = computed(() => /^\d+$/.test((barsStr.value || "").trim()));
function toggleAdvanced() {
  advancedOpen.value = !advancedOpen.value;
}
async function applyManualRange() {
  await vm.reload?.(true);
}
async function applyBarsRange() {
  const n = parseInt((barsStr.value || "").trim(), 10);
  if (Number.isFinite(n) && n > 0) {
    vm.previewView(n, vm.rightTs.value);
    vm.setBars(n); // 保留此入口后端触发（契约不变）
    advStart.value = vm.visibleRange.value.startStr || "";
    advEnd.value = vm.visibleRange.value.endStr || "";
  }
}
async function applyVisible() {
  const arr = vm.candles.value || [];
  if (!arr.length) return;
  advStart.value = vm.visibleRange.value.startStr || "";
  advEnd.value = vm.visibleRange.value.endStr || "";
}

// 时间短文本格式化
const isMinute = computed(() => /m$/.test(String(vm.freq.value || "")));
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
    if (isMinute.value) {
      const h = pad2(d.getHours()),
        m = pad2(d.getMinutes());
      return `${Y}-${M}-${D} ${h}:${m}`;
    }
    return `${Y}-${M}-${D}`;
  } catch {
    return "";
  }
}
const formattedStart = computed(
  () => fmtShort(vm.visibleRange.value.startStr) || "-"
);
const formattedEnd = computed(
  () => fmtShort(vm.visibleRange.value.endStr) || "-"
);
const barsCount = computed(() => {
  const d = Number(vm.displayBars?.value || 0);
  return Number.isFinite(d) && d > 0
    ? d
    : Number(vm.meta.value?.view_rows || 0);
});

// ECharts 句柄与观察者
const wrap = ref(null);
const host = ref(null);
let chart = null;
let ro = null;
let detachSync = null;

// 设置草稿（K/MA/缠论/分型/复权）
const settingsDraft = reactive({
  kForm: { ...DEFAULT_KLINE_STYLE },
  maForm: {},
  chanForm: { ...CHAN_DEFAULTS },
  fractalForm: { ...FRACTAL_DEFAULTS },
  adjust: DEFAULT_APP_PREFERENCES.adjust,
});

// =============================
// 新增：当前可见根数（本地持有），用于标记尺寸估算
// localVisRows：不触发后端时，仍可根据 dataZoom 变化更新标记尺寸
// =============================
const localVisRows = ref(Math.max(1, Number(vm.meta.value?.view_rows || 1))); // 初始化为 meta.view_rows 或 1

// 设置窗内容组件（包含不变量：defineComponent）
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
              value: Number(K.barPercent ?? DEFAULT_KLINE_STYLE.barPercent),
              onInput: (e) =>
                (settingsDraft.kForm.barPercent = Number(e.target.value || 0)),
            })
          ),
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
                  (settingsDraft.adjust = String(e.target.value)),
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
                value: K.subType || DEFAULT_KLINE_STYLE.subType,
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
          resetBtn(() => {
            Object.assign(settingsDraft.kForm, { ...DEFAULT_KLINE_STYLE });
            settingsDraft.adjust = String(
              DEFAULT_APP_PREFERENCES.adjust || "none"
            );
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
            checkCell(
              !!conf.enabled,
              (e) => (conf.enabled = !!e.target.checked)
            ),
            resetBtn(() => {
              const def = DEFAULT_MA_CONFIGS[key];
              if (def) {
                // 直接覆盖该 MA 的草稿配置为默认
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
        JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.confirmStyle))); // confirmStyle

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
          nameCell("确认分型"), // 确认分型（中文标记）
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

// 打开设置窗（包含不变量标记：openSettingsDialog/dialogManager.open/tabs/activeTab）
let prevAdjust = "none";
function openSettingsDialog() {
  try {
    // 草稿初始化
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

    // 打开弹窗
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
          // K线样式
          Object.assign(settingsDraft.kForm, { ...DEFAULT_KLINE_STYLE });
          settingsDraft.adjust = String(DEFAULT_APP_PREFERENCES.adjust || "none");
          // MA 全量恢复默认
          const defs = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS));
          settingsDraft.maForm = defs;
          // 缠论标记
          settingsDraft.chanForm = JSON.parse(JSON.stringify(CHAN_DEFAULTS));
          // 分型设置
          settingsDraft.fractalForm = JSON.parse(JSON.stringify(FRACTAL_DEFAULTS));
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

// 标题与刷新状态
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

// 键盘左右键（保留原实现）
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
  const sIdx = Number(vm.meta.value?.view_start_idx ?? 0);
  const eIdx = Number(vm.meta.value?.view_end_idx ?? len - 1);
  if (!Number.isFinite(currentIndex) || currentIndex < 0) currentIndex = eIdx;
  currentIndex += e.key === "ArrowLeft" ? -1 : +1;
  currentIndex = Math.max(sIdx, Math.min(eIdx, currentIndex));
  try {
    const seq = renderSeq;
    chart.dispatchAction({
      type: "showTip",
      seriesIndex: 0,
      dataIndex: currentIndex,
    });
    if (isStale(seq)) return;
    chart.dispatchAction({
      type: "highlight",
      seriesIndex: 0,
      dataIndex: currentIndex,
    });
  } catch {}
}

// 缠论/分型缓存与重算（包含不变量：function recomputeChan(）
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

// CHAN 占位系列（隐藏 y 轴 index=1；包含不变量 id: "CHAN_UP"/"CHAN_DOWN"）
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
    if (patches.length) chart.setOption({ series: patches }, false);
  } catch {}
}

// 缠论标记更新（包含不变量：function updateChanMarkers(）
function updateChanMarkers(seq) {
  if (!chart) return;
  if (isStale(seq)) return;

  const reduced = chanCache.value.reduced || [];
  const fractals = chanCache.value.fractals || [];

  // NEW: 使用 localVisRows 替代 meta.view_rows（在不触发后端场景也随缩放变化）
  const visCount = Math.max(
    1,
    Number(localVisRows.value || vm.meta.value?.view_rows || 1)
  );
  const hostW = host.value ? host.value.clientWidth : 800;

  try {
    ensureChanSeriesPresent();
  } catch {}
  const patches = [];

  // 涨跌标记（隐藏 y 轴）
  if (settings.chanSettings.value.showUpDownMarkers && reduced.length) {
    const upDownLayer = buildUpDownMarkers(reduced, {
      chanSettings: settings.chanSettings.value,
      hostWidth: hostW,
      visCount,
    });
    patches.push(...(upDownLayer.series || []));
  } else {
    patches.push({ id: "CHAN_UP", data: [] }, { id: "CHAN_DOWN", data: [] });
  }

  // 分型标记（主价格轴；buildFractalMarkers 不变量存在）
  const frEnabled = (settings.fractalSettings.value?.enabled ?? true) === true;
  if (frEnabled && reduced.length && fractals.length) {
    const frLayer = buildFractalMarkers(reduced, fractals, {
      fractalSettings: settings.fractalSettings.value,
      hostWidth: hostW,
      visCount,
    });
    patches.push(...(frLayer.series || [])); // buildFractalMarkers(
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
    chart.setOption({ series: patches }, false);
  } catch {}
}

// 右端近端判定（前端近似）
const MINUTE_GRACE_SEC = 5;
const DAILY_GRACE_SEC = 180;
function isTradingDayApprox(d) {
  const wd = d.getDay();
  return wd >= 1 && wd <= 5;
}
function _alignToRightEdgeMinute(t, minutes) {
  const tm = new Date(t);
  tm.setSeconds(0, 0);
  const total = tm.getHours() * 60 + tm.getMinutes();
  const k = Math.floor(total / minutes) * minutes;
  const hh = Math.floor(k / 60),
    mm = k % 60;
  tm.setHours(hh, mm, 0, 0);
  return tm.getTime();
}
function computeExpectedLastEndMs(freq, nowMs) {
  const now = new Date(Number.isFinite(+nowMs) ? +nowMs : Date.now());
  if (!isTradingDayApprox(now)) {
    if (freq.endsWith("m")) return null;
    const back = new Date(now.getTime());
    for (let i = 0; i < 7; i++) {
      back.setDate(back.getDate() - 1);
      if (isTradingDayApprox(back)) break;
    }
    back.setHours(15, 0, 0, 0);
    return back.getTime();
  }
  if (freq.endsWith("m")) {
    const minutes = parseInt(freq.replace("m", ""), 10);
    const nowAdj = new Date(now.getTime() - MINUTE_GRACE_SEC * 1000);
    const y = nowAdj.getFullYear(),
      M = nowAdj.getMonth(),
      d = nowAdj.getDate();
    const s1 = new Date(y, M, d, 9, 30, 0, 0).getTime();
    const e1 = new Date(y, M, d, 11, 30, 0, 0).getTime();
    const s2 = new Date(y, M, d, 13, 0, 0, 0).getTime();
    const e2 = new Date(y, M, d, 15, 0, 0, 0).getTime();
    const n = nowAdj.getTime();
    if (n < s1) {
      const back = new Date(nowAdj.getTime());
      for (let i = 0; i < 7; i++) {
        back.setDate(back.getDate() - 1);
        if (isTradingDayApprox(back)) break;
      }
      back.setHours(15, 0, 0, 0);
      return back.getTime();
    } else if (n >= s1 && n <= e1) {
      const aligned = _alignToRightEdgeMinute(n, minutes);
      return Math.min(Math.max(aligned, s1), e1);
    } else if (n > e1 && n < s2) {
      return e1;
    } else if (n >= s2 && n <= e2) {
      const aligned = _alignToRightEdgeMinute(n, minutes);
      return Math.min(Math.max(aligned, s2), e2);
    } else {
      return e2;
    }
  }
  const nowAdj = new Date(now.getTime() - DAILY_GRACE_SEC * 1000);
  const y = nowAdj.getFullYear(),
    M = nowAdj.getMonth(),
    d = nowAdj.getDate();
  if (freq === "1d") {
    const cut = new Date(y, M, d, 15, 0, 0, 0).getTime();
    return cut;
  }
  if (freq === "1w") {
    const tmp = new Date(nowAdj.getTime());
    const wd = tmp.getDay();
    const daysToFri = 5 - wd;
    tmp.setDate(tmp.getDate() + daysToFri);
    for (let i = 0; i < 7 && !isTradingDayApprox(tmp); i++)
      tmp.setDate(tmp.getDate() - 1);
    tmp.setHours(15, 0, 0, 0);
    return tmp.getTime();
  }
  if (freq === "1M") {
    const firstNext = new Date(y, M + 1, 1, 0, 0, 0, 0);
    const last = new Date(firstNext.getTime() - 24 * 3600 * 1000);
    for (let i = 0; i < 7 && !isTradingDayApprox(last); i++)
      last.setDate(last.getDate() - 1);
    last.setHours(15, 0, 0, 0);
    return last.getTime();
  }
  return null;
}

// dataZoom 本地处理（包含不变量：chart.on("dataZoom"）
function onDataZoom(params) {
  try {
    const info = (params && params.batch && params.batch[0]) || params || {};
    const len = (vm.candles.value || []).length;
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
    } else {
      return;
    }
    if (!Number.isFinite(sIdx) || !Number.isFinite(eIdx)) return;
    if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];
    sIdx = Math.max(0, sIdx);
    eIdx = Math.min(len - 1, eIdx);

    const bars = Math.max(1, eIdx - sIdx + 1);
    const arr = vm.candles.value || [];
    const endTs = arr[eIdx]?.t ? Date.parse(arr[eIdx].t) : null;

    // 本地预览与持久化
    vm.previewView(
      bars,
      Number.isFinite(endTs) ? endTs : vm.rightTs.value,
      sIdx,
      eIdx
    );

    // NEW：更新本地可见根数，用于标记尺寸（无后端也能变化）
    localVisRows.value = bars;

    // 本地更新预设高亮
    const allRows = len;
    let nextPreset = "ALL";
    if (allRows > 0 && bars < allRows)
      nextPreset = pickPresetByBarsCountDown(vm.freq.value, bars, allRows);
    vm.windowPreset.value = nextPreset;
    settings.setWindowPreset(nextPreset);

    // 触达右端 → 近端比对（存在缺口才触发后端）
    if (eIdx === allRows - 1) {
      const lastIso = arr[allRows - 1]?.t || null;
      const lastMs = lastIso ? Date.parse(lastIso) : null;
      const expectMs = computeExpectedLastEndMs(vm.freq.value, Date.now());
      if (Number.isFinite(lastMs) && Number.isFinite(expectMs)) {
        const gapMs = expectMs - lastMs;
        const graceMs =
          (vm.freq.value.endsWith("m") ? MINUTE_GRACE_SEC : DAILY_GRACE_SEC) *
          1000;
        if (gapMs > graceMs) vm.reload({ force: true });
      }
    }

    // NEW：缩放后立即更新标记尺寸（不触发后端）
    updateChanMarkers(renderSeq);
  } catch {}
}

// 点击预设本地处理（更新 dataZoom + 本地近端比对 + 更新标记尺寸）
function onClickPreset(preset) {
  try {
    const allRows = (vm.candles.value || []).length;
    if (!allRows) return;
    const targetBars = presetToBars(
      vm.freq.value,
      String(preset || "ALL"),
      allRows
    );
    vm.windowPreset.value = String(preset || "ALL");
    settings.setWindowPreset(vm.windowPreset.value);

    const eIdx = allRows - 1;
    const sIdx = Math.max(0, eIdx - targetBars + 1);
    const arr = vm.candles.value || [];
    const lastIso = arr[eIdx]?.t || null;
    const anchorTs = lastIso ? Date.parse(lastIso) : vm.rightTs.value;

    vm.previewView(
      targetBars,
      Number.isFinite(anchorTs) ? anchorTs : vm.rightTs.value,
      sIdx,
      eIdx
    );

    // NEW：更新本地可见根数，用于标记尺寸
    localVisRows.value = targetBars;

    const delta = {
      dataZoom: [
        { type: "inside", startValue: sIdx, endValue: eIdx },
        { type: "slider", startValue: sIdx, endValue: eIdx },
      ],
    };
    try {
      chart.setOption(delta, {
        notMerge: false,
        lazyUpdate: true,
        silent: true,
      });
    } catch {}

    const expectMs = computeExpectedLastEndMs(vm.freq.value, Date.now());
    const lastMs = lastIso ? Date.parse(lastIso) : null;
    if (Number.isFinite(lastMs) && Number.isFinite(expectMs)) {
      const gapMs = expectMs - lastMs;
      const graceMs =
        (vm.freq.value.endsWith("m") ? MINUTE_GRACE_SEC : DAILY_GRACE_SEC) *
        1000;
      if (gapMs > graceMs) vm.reload({ force: true });
    }

    // NEW：预设切换后立即更新标记尺寸（不触发后端）
    updateChanMarkers(renderSeq);
  } catch {}
}

// 滚轮缩放：依赖 inside dataZoom → onDataZoom；本函数不触发后端
function onWheelZoom() {
  /* no-op */
}

// 应用服务端视窗（保持原逻辑，同时更新 localVisRows）
function applyZoomByMeta(seq) {
  if (!chart) return;
  if (isStale(seq)) return;
  const len = (vm.candles.value || []).length;
  if (!len) return;
  const sIdx = Number(vm.meta.value?.view_start_idx ?? 0);
  const eIdx = Number(vm.meta.value?.view_end_idx ?? len - 1);

  // NEW：服务端视窗变化时同步本地可见根数（用于标记尺寸）
  localVisRows.value = Math.max(1, eIdx - sIdx + 1);

  const delta = {
    dataZoom: [
      { type: "inside", startValue: sIdx, endValue: eIdx },
      { type: "slider", startValue: sIdx, endValue: eIdx },
    ],
  };
  try {
    if (isStale(seq)) return;
    chart.dispatchAction({ type: "hideTip" });
  } catch {}
  chart.setOption(delta, { notMerge: false, lazyUpdate: true, silent: true });
}

// 安全 resize（rAF 防抖）
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
    // NEW：尺寸变化也可能影响标记宽度估算（hostWidth），做一次标记更新
    updateChanMarkers(renderSeq);
  });
}

// 挂载初始化（包含不变量：getZr("mousemove")/chart.on("updateAxisPointer")/chart.on("dataZoom")）
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

  // 首帧：重算 → 渲染 → 标记更新 → 标题更新
  recomputeChan();
  render();
  updateChanMarkers(renderSeq);
  updateHeaderFromCurrent();

  window.addEventListener("chan:hover-index", onGlobalHoverIndex);
});

// 卸载清理
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

// 渲染主图（包含不变量：function render(）
function render() {
  if (!chart) return;
  const mySeq = ++renderSeq;

  const needAvoidAxis = !!(
    settings.chanSettings.value.showUpDownMarkers &&
    (chanCache.value.reduced || []).length > 0
  );
  const extraAxisLabelMargin = needAvoidAxis ? 20 : 6;

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
    { tooltipClass: "ct-fixed-tooltip", xAxisLabelMargin: extraAxisLabelMargin }
  );

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
  chart.setOption(option, { notMerge: true, lazyUpdate: false, silent: true });

  updateChanMarkers(mySeq);
  applyZoomByMeta(mySeq);
}

// 数据/配置变化重算重绘
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

// meta 变化应用视窗与标记更新（包含不变量：updateChanMarkers 标记）
watch(
  () => vm.meta.value,
  async () => {
    await nextTick();
    const mySeq = ++renderSeq;
    applyZoomByMeta(mySeq);
    updateChanMarkers(mySeq);
    updateHeaderFromCurrent();
    refreshedAt.value = new Date();
    showRefreshed.value = true;
    setTimeout(() => {
      showRefreshed.value = false;
    }, 2000);
  },
  { deep: true }
);

// 下沿拖拽高度调整
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

// 标题更新
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
/* 控制区布局与按钮样式 */
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

/* 主图画布与信息条 */
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
