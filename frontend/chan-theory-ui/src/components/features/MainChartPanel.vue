<!-- E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\components\features\MainChartPanel.vue -->
<!-- ====================================================================== -->
<!-- 主图组件（K线/HL柱 + MA + 缩放联动 + 缠论覆盖层）                         -->
<!-- 修复点（按 SOP 执行、最小补丁）：                                         -->
<!-- 1) 双击主窗打开设置窗（openSettingsDialog 实现，模板 @dblclick 已绑定）。  -->
<!-- 2) 恢复完整设置功能：两页设置——“行情显示（display）”与“缠论标记（chan）”。 -->
<!-- 3) 保存时：                                                             -->
<!--    - 写回 K 线样式/MA/缠论/分型设置到 useUserSettings；                  -->
<!--    - 复权 adjust 若变化，交由 useUserSettings → useMarketView 链路重载； -->
<!--      若未变化，直接 recomputeChan() + render() 立即生效；                -->
<!-- 4) 保持既有不变量：CHAN 占位（yAxisIndex=1）、dataZoom/hover 联动、       -->
<!--    覆盖式防抖与预览即时持久化、时间语义与接口契约均不变。                 -->
<!-- ====================================================================== -->

<template>
  <!-- 顶部功能区（三列布局） -->
  <div class="controls controls-grid">
    <!-- 左列：频率按钮组（仅切频，不改窗宽） -->
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

    <!-- 中列：起止 + bars（上下两行，靠左显示） -->
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

    <!-- 右列：窗宽预设按钮组 + 高级图标按钮 -->
    <div class="ctrl-col right">
      <div class="seg">
        <!-- 窗口预设按钮（从常量 WINDOW_PRESETS 渲染） -->
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

        <!-- 高级图标按钮（切换高级面板显隐） -->
        <button
          class="seg-btn adv-btn"
          :title="'自定义'"
          @click="toggleAdvanced"
        >
          <!-- 简洁滑块/设置风格图标 -->
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

  <!-- 高级面板（手动日期、N根缩放、当前可见窗口） -->
  <div v-if="advancedOpen" class="advanced-panel">
    <!-- 手动日期（本轮变更不触后端接口，沿用 reload 占位） -->
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

    <!-- 最近 N 根（bars 优先，右端锚定） -->
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

    <!-- 当前可见窗口（即时预览） -->
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

  <!-- 图表画布容器（双击打开设置窗） -->
  <div
    ref="wrap"
    class="chart"
    tabindex="0"
    @keydown="onKeydown"
    @mouseenter="focusWrap"
    @dblclick="openSettingsDialog"
    @wheel.prevent="onWheelZoom"
  >
    <!-- 顶部信息条：标题与状态 -->
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

    <!-- 下沿拖拽条：调整主窗高度 -->
    <div
      class="bottom-strip"
      title="上下拖拽调整窗体高度"
      @mousedown="onResizeHandleDown('bottom', $event)"
    ></div>
  </div>
</template>

<script setup>
/* ============================= */
/* 导入依赖（Vue/ECharts/本地模块） */
/* ============================= */
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
} from "vue"; // Vue 组合式 API
import * as echarts from "echarts"; // ECharts v6
import { buildMainChartOption, zoomSync } from "@/charts/options"; // 主图 option 与缩放联动
import {
  DEFAULT_MA_CONFIGS, // 默认 MA 配置
  CHAN_DEFAULTS, // 缠论默认
  DEFAULT_KLINE_STYLE, // K线样式默认
  DEFAULT_APP_PREFERENCES, // 应用偏好默认
  FRACTAL_DEFAULTS, // 分型默认
  FRACTAL_SHAPES, // 分型可选形状（常量）
  FRACTAL_FILLS, // 分型可选填充（常量）
  WINDOW_PRESETS, // 窗口预设列表
} from "@/constants"; // 常量源
import { useUserSettings } from "@/composables/useUserSettings"; // 用户设置（本地持久）
import { useSymbolIndex } from "@/composables/useSymbolIndex"; // 标的索引（名称显示用）
import { computeInclude, computeFractals } from "@/composables/useChan"; // 缠论/分型计算
import { vSelectAll } from "@/utils/inputBehaviors"; // 输入框自动全选
import { buildUpDownMarkers } from "@/charts/chan/layers"; // 缠论图层（涨跌标记）

/* ============================= */
/* 指令注册：v-select-all           */
/* ============================= */
defineOptions({ directives: { selectAll: vSelectAll } });

/* ============================= */
/* 注入与实例：市场视图/设置/对话框 */
/* ============================= */
const vm = inject("marketView"); // 市场视图（useMarketView）
const settings = useUserSettings(); // 用户设置
const { findBySymbol } = useSymbolIndex(); // 名称查询
const dialogManager = inject("dialogManager"); // 全局对话框管理器

/* ============================= */
/* UI 渲染序号（覆盖式防抖守护）   */
/* ============================= */
let renderSeq = 0; // 每次渲染自增序号
function isStale(seq) {
  return seq !== renderSeq;
} // 判断是否过时

/* ============================= */
/* Hover 跨窗体广播（主→副）        */
/* ============================= */
function broadcastHoverIndex(idx) {
  try {
    window.dispatchEvent(
      new CustomEvent("chan:hover-index", { detail: { idx: Number(idx) } })
    );
  } catch {}
}

/* ============================= */
/* 窗口预设按钮（UI 渲染来源）      */
/* ============================= */
const presets = computed(() => WINDOW_PRESETS.slice());

/* ============================= */
/* 频率切换（左列按钮）            */
/* ============================= */
const isActiveK = (f) => vm.chartType.value === "kline" && vm.freq.value === f; // 当前频率高亮
function activateK(f) {
  vm.chartType.value = "kline";
  vm.setFreq(f);
} // 切频

/* ============================= */
/* 预设窗宽切换（右列按钮）        */
/* ============================= */
function onClickPreset(p) {
  vm.applyPreset(p);
}

/* ============================= */
/* 高级面板状态与行为              */
/* ============================= */
const advancedOpen = ref(false); // 高级面板显隐
const advStart = ref(vm.visibleRange.value.startStr || ""); // 手动起始
const advEnd = ref(vm.visibleRange.value.endStr || ""); // 手动结束
const barsStr = ref(""); // 输入 N 根
const canApplyManual = computed(() => true); // 占位
const canApplyBars = computed(() => /^\d+$/.test((barsStr.value || "").trim())); // N 为整数

function toggleAdvanced() {
  advancedOpen.value = !advancedOpen.value;
} // 显隐切换
async function applyManualRange() {
  await vm.reload?.(true);
} // 占位：沿用 reload
async function applyBarsRange() {
  // 最近 N 根应用
  const n = parseInt((barsStr.value || "").trim(), 10);
  if (Number.isFinite(n) && n > 0) {
    vm.previewView(n, vm.rightTs.value); // 预览立即刷新起止/bars
    vm.setBars(n); // 后端一次成型视窗
    advStart.value = vm.visibleRange.value.startStr || "";
    advEnd.value = vm.visibleRange.value.endStr || "";
  }
}
async function applyVisible() {
  // 将当前可见窗口应用为数据窗口（占位）
  const arr = vm.candles.value || [];
  if (!arr.length) return;
  advStart.value = vm.visibleRange.value.startStr || "";
  advEnd.value = vm.visibleRange.value.endStr || "";
}

/* ============================= */
/* 起止/Bars 文案（显示层格式化）   */
/* ============================= */
const isMinute = computed(() => /m$/.test(String(vm.freq.value || ""))); // 分钟族判断
function pad2(n) {
  return String(n).padStart(2, "0");
} // 两位补零
function fmtShort(iso) {
  // ISO → 短文本
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
); // 起
const formattedEnd = computed(
  () => fmtShort(vm.visibleRange.value.endStr) || "-"
); // 止
const barsCount = computed(() => {
  // Bars
  const d = Number(vm.displayBars?.value || 0);
  return Number.isFinite(d) && d > 0
    ? d
    : Number(vm.meta.value?.view_rows || 0);
});

/* ============================= */
/* ECharts 实例/宿主/观察者         */
/* ============================= */
const wrap = ref(null); // 外层容器
const host = ref(null); // ECharts 宿主
let chart = null; // ECharts 实例
let ro = null; // ResizeObserver
let detachSync = null; // zoomSync 解绑函数

/* ============================= */
/* 设置草稿：K线/MA/复权/缠论/分型   */
/* ============================= */
const settingsDraft = reactive({
  kForm: { ...DEFAULT_KLINE_STYLE }, // K 线样式草稿
  maForm: {}, // MA 配置草稿（键：MA5/MA10/...）
  chanForm: { ...CHAN_DEFAULTS }, // 缠论可视草稿
  fractalForm: { ...FRACTAL_DEFAULTS }, // 分型可视草稿
  adjust: DEFAULT_APP_PREFERENCES.adjust, // 复权草稿
});

/* ============================= */
/* 设置窗体内容：两页（display/chan） */
/* ============================= */
const MainChartSettingsContent = defineComponent({
  // 外壳（ModalDialog）会把 activeTab 透传进来
  props: { activeTab: { type: String, default: "display" } },
  setup(props) {
    // 通用单元格构建器（左：名称，右：控件）
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
        h(
          "button",
          { class: "btn icon", title: "恢复默认", type: "button", onClick },
          "⟲"
        ),
      ]);

    // 页面1：行情显示（K线/MA/复权）
    const renderDisplay = () => {
      const K = settingsDraft.kForm; // K 线样式草稿
      const rows = [];

      // K线样式 + 复权
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
          h("div", { class: "std-check" }), // 对齐占位
          resetBtn(() => {
            // 恢复默认（K线样式 + 复权）
            Object.assign(settingsDraft.kForm, { ...DEFAULT_KLINE_STYLE });
            settingsDraft.adjust = String(
              DEFAULT_APP_PREFERENCES.adjust || "none"
            );
          }),
        ])
      );

      // 多行：MA 配置（遍历每条 MAx）
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
            h("div"), // 对齐占位
            checkCell(
              !!conf.enabled,
              (e) => (conf.enabled = !!e.target.checked)
            ),
            resetBtn(() => {
              const def = DEFAULT_MA_CONFIGS[key];
              if (def) Object.assign(settingsDraft.maForm[key], def);
            }),
          ])
        );
      });

      return rows;
    };

    // 页面2：缠论标记（涨跌标记 + 分型参数/外观）
    const renderChan = () => {
      const cf = settingsDraft.chanForm; // 缠论可视草稿
      const rows = [];

      // 涨跌标记（上/下符号与颜色，承载点策略，显示开关，重置）
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

      // 分型判定参数（最小 tick / 最小幅度% / 判断条件）
      const ff = settingsDraft.fractalForm; // 分型草稿
      const styleByStrength = (ff.styleByStrength =
        ff.styleByStrength ||
        JSON.parse(JSON.stringify(FRACTAL_DEFAULTS.styleByStrength)));

      // 确认分型样式 防御性初始化（用于“确认分型”设置行）
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

      // 三档样式（强/标准/弱：底/顶形状颜色、填充、启用；逐档恢复默认）
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

      // 追加一行“确认分型”设置（字段同其他分型设置）
      rows.push(
        h("div", { class: "std-row" }, [
          nameCell("确认分型"),
          // 底分符号
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
          // 底分颜色
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
          // 顶分符号
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
          // 顶分颜色
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
          // 填充
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
          // 启用
          h("div", { class: "std-check" }, [
            h("input", {
              type: "checkbox",
              checked: !!confirmStyle.enabled,
              onChange: (e) =>
                (settingsDraft.fractalForm.confirmStyle.enabled =
                  !!e.target.checked),
            }),
          ]),
          // 恢复默认
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

    // 根据 activeTab 渲染对应页面
    return () =>
      h("div", {}, [
        ...(props.activeTab === "chan" ? renderChan() : renderDisplay()),
      ]);
  },
});

/* ============================= */
/* 双击主窗打开设置窗（两页设置）     */
/* - 默认页：行情显示（display）       */
/* - 保存：回写设置，复权变化则触发重载 */
/* ============================= */
let prevAdjust = "none"; // 进入设置窗前的复权值
function openSettingsDialog() {
  try {
    // 1) K 线样式草稿（默认+本地合并）
    settingsDraft.kForm = JSON.parse(
      JSON.stringify({
        ...DEFAULT_KLINE_STYLE,
        ...(settings.klineStyle.value || {}),
      })
    );

    // 2) MA 草稿（默认+本地合并）
    const maDefaults = JSON.parse(JSON.stringify(DEFAULT_MA_CONFIGS));
    const maLocal = settings.maConfigs.value || {};
    Object.keys(maDefaults).forEach((k) => {
      if (maLocal[k]) maDefaults[k] = { ...maDefaults[k], ...maLocal[k] };
    });
    settingsDraft.maForm = maDefaults;

    // 3) 缠论/分型 草稿（默认+本地合并）
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

    // 4) 复权草稿与原值记录
    prevAdjust = String(
      vm.adjust.value || settings.adjust.value || DEFAULT_APP_PREFERENCES.adjust
    );
    settingsDraft.adjust = prevAdjust;

    // 5) 打开设置弹窗（两页，默认页 = 行情显示）
    dialogManager.open({
      title: "行情显示设置",
      contentComponent: MainChartSettingsContent,
      props: {},
      tabs: [
        { key: "display", label: "行情显示" },
        { key: "chan", label: "缠论标记" },
      ],
      activeTab: "display", // 按你的要求：默认页为“行情显示”
      onSave: async () => {
        try {
          // 写回显示设置
          settings.setKlineStyle(settingsDraft.kForm);
          settings.setMaConfigs(settingsDraft.maForm);

          // 写回缠论/分型设置
          settings.setChanSettings({ ...settingsDraft.chanForm });
          settings.setFractalSettings({ ...settingsDraft.fractalForm });

          // 复权变更处理
          const nextAdjust = String(settingsDraft.adjust || "none");
          const adjustChanged = nextAdjust !== prevAdjust;
          if (adjustChanged) {
            settings.setAdjust(nextAdjust); // 交由 useMarketView 链路触发一次成型重载
          } else {
            // 未变更复权：仅本地重算/重绘，立即生效
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

/* ============================= */
/* 顶部标题与刷新状态文案            */
/* ============================= */
const displayHeader = ref({ name: "", code: "", freq: "" }); // 标题信息
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
  const d = refreshedAt.value,
    pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
});

/* ============================= */
/* 键盘左右键从 hover 最近点起跳     */
/* ============================= */
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

/* ============================= */
/* 缠论/分型缓存与重算             */
/* ============================= */
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

/* ============================= */
/* CHAN 占位系列（隐藏 yAxis=1）    */
/* ============================= */
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

/* ============================= */
/* 缠论标记更新（根据 reducedBars）  */
/* ============================= */
function updateChanMarkers(seq) {
  if (!chart) return;
  if (isStale(seq)) return;
  const reduced = chanCache.value.reduced || [];
  try {
    ensureChanSeriesPresent();
  } catch {}
  if (!settings.chanSettings.value.showUpDownMarkers || !reduced.length) {
    try {
      if (isStale(seq)) return;
      chart.setOption(
        {
          series: [
            { id: "CHAN_UP", data: [] },
            { id: "CHAN_DOWN", data: [] },
          ],
        },
        false
      );
    } catch {}
    return;
  }
  const layer = buildUpDownMarkers(reduced, {
    chanSettings: settings.chanSettings.value,
    hostWidth: host.value ? host.value.clientWidth : 800,
    visCount: Number(vm.meta.value?.view_rows || 1),
  });
  try {
    if (isStale(seq)) return;
    chart.setOption({ series: layer.series }, false);
  } catch {}
}

/* ============================= */
/* dataZoom 事件：预览并提交缩放     */
/* ============================= */
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

    vm.previewView(
      bars,
      Number.isFinite(endTs) ? endTs : vm.rightTs.value,
      sIdx,
      eIdx
    );
    vm.setBars(bars, Number.isFinite(endTs) ? endTs : vm.rightTs.value);
  } catch {}
}

/* ============================= */
/* 应用服务端视窗（meta.view_*）      */
/* ============================= */
function applyZoomByMeta(seq) {
  if (!chart) return;
  if (isStale(seq)) return;
  const len = (vm.candles.value || []).length;
  if (!len) return;
  const sIdx = Number(vm.meta.value?.view_start_idx ?? 0);
  const eIdx = Number(vm.meta.value?.view_end_idx ?? len - 1);
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

/* ============================= */
/* 安全 resize（rAF 防抖）          */
/* ============================= */
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

/* ============================= */
/* 挂载：初始化 ECharts/联动/监听     */
/* ============================= */
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

  // 像素反查索引并广播 hover
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

  // 轴指示器更新时（tooltip 移动）广播 hover
  chart.on("updateAxisPointer", (params) => {
    try {
      const axisInfo = (params?.axesInfo && params.axesInfo[0]) || null;
      const label = axisInfo?.value;
      const dates = (vm.candles.value || []).map((d) => d.t);
      const idx = dates.indexOf(label);
      if (idx >= 0) broadcastHoverIndex(idx);
    } catch {}
  });

  // 缩放联动
  chart.on("dataZoom", onDataZoom);

  // 宿主尺寸观察
  try {
    ro = new ResizeObserver(() => {
      safeResize();
    });
    ro.observe(el);
  } catch {}
  requestAnimationFrame(() => {
    safeResize();
  });

  // 联动注册（主窗作为源）
  detachSync = zoomSync.attach(
    "main",
    chart,
    () => (vm.candles.value || []).length
  );

  // 首帧重算与渲染
  recomputeChan();
  render();
  updateHeaderFromCurrent();

  // 跨窗 hover 订阅
  window.addEventListener("chan:hover-index", onGlobalHoverIndex);
});

/* ============================= */
/* 卸载：解绑事件/销毁实例           */
/* ============================= */
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

/* ============================= */
/* 渲染主图：构造 option 并 set      */
/* ============================= */
function render() {
  if (!chart) return;
  const mySeq = ++renderSeq;

  // 有 CHAN 标记时适当增加横轴标签间距
  const needAvoidAxis = !!(
    settings.chanSettings.value.showUpDownMarkers &&
    (chanCache.value.reduced || []).length > 0
  );
  const extraAxisLabelMargin = needAvoidAxis ? 20 : 6;

  // 构造主图 option（K线或 HL 柱 + MA）
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

  // 保证 CHAN_UP/CHAN_DOWN 占位（隐藏 yAxis=1）存在
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

  // 应用 option（notMerge=true）
  try {
    chart.dispatchAction({ type: "hideTip" });
  } catch {}
  chart.setOption(option, { notMerge: true, lazyUpdate: false, silent: true });

  // 缠论标记与视窗同步
  updateChanMarkers(mySeq);
  applyZoomByMeta(mySeq);
}

/* ============================= */
/* 数据/配置变化 → 重算重绘           */
/* ============================= */
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

/* ============================= */
/* 服务端 meta（视窗）变化 → 应用     */
/* ============================= */
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

/* ============================= */
/* 滚轮缩放（占位）                  */
/* ============================= */
function onWheelZoom() {
  vm[vm.meta.value ? "zoomIn" : "zoomIn"]();
}

/* ============================= */
/* 画布高度拖拽调整                 */
/* ============================= */
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

/* ============================= */
/* 标题信息：从当前元信息/索引提取     */
/* ============================= */
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
/* ============================= */
/* 三列控制区布局与按钮样式           */
/* ============================= */
.controls-grid {
  display: grid; /* 三列网格布局 */
  grid-template-columns: auto 1fr auto; /* 左：自适应，中：伸展，右：自适应 */
  align-items: center; /* 垂直居中 */
  column-gap: 16px; /* 列间距 */
  margin: 0 0 8px 0; /* 与图表间距 */
}
.ctrl-col.left {
  /* 左列容器占位 */
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

/* 键值行 */
.kv .k {
  color: #bbb;
}
.kv .v {
  color: #ddd;
}

/* 连体按钮（频率/窗宽） */
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

/* 高级图标按钮 hover 细节 */
.adv-btn svg {
  display: block;
}
.adv-btn:hover svg path {
  stroke: #fff;
}
.adv-btn:hover svg circle {
  fill: #fff;
}

/* ============================= */
/* 图表画布容器与信息条样式           */
/* ============================= */
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
