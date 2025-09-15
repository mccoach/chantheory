/* E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useMarketView.js */
/* ============================== */
/* 说明：页面核心状态与行为（窗长与频率解耦 + 持久化）。 */
/* - 启动优先读取本地持久化：freq 与 windowPreset 分别读取，失败回退 constants 默认。 */
/* - 频率切换不再隐式改变窗长；窗长按钮/手动区间只影响数据窗口，不改频率。 */
/* - WINDOW_PRESETS 按钮集合从 constants 引入，不再写死。 */
/* 修复：将 rng 的定义提前，避免 IIFE 引用未初始化的 rng。 */
/* 其余逻辑（自动刷新/轻冷却/请求参数/ma_periods 构建）保持不变。 */
/* ============================== */

import { ref, watch, computed } from "vue";                   // Vue 响应式 API
import { fetchCandles } from "@/services/marketService";      // 后端 /api/candles
import { useUserSettings } from "@/composables/useUserSettings"; // 本地设置
import { WINDOW_PRESETS, DEFAULT_APP_PREFERENCES } from "@/constants"; // 集中默认

// 非“用户设置”的运行时调度参数（交互时序），保留在本处：不是用户可配置项
const GRACE_MIN_SEC = 5;                                      // 分钟级宽限
const GRACE_DAILY_SEC = 180;                                  // 日/周/月宽限
const DEFAULT_COOLDOWN_SEC = 10;                              // 轻冷却

// 计算下一数据边界时刻（用于自动刷新）
function computeNextBoundaryTs(freq) {
  const now = new Date();                                     // 当前时间
  const hm = now.getHours() * 60 + now.getMinutes();          // 分钟总数
  const isAfterClose = hm >= 15 * 60;                         // 是否收盘后
  const inMorning = hm >= 9 * 60 + 30 && hm < 11 * 60 + 30;   // 盘中：上午
  const inAfternoon = hm >= 13 * 60 && hm < 15 * 60;          // 盘中：下午
  const stepMap = { "1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60 }; // 分钟步长
  if (freq in stepMap) {                                      // 分钟族
    const step = stepMap[freq];                               // 步长
    if (!inMorning && !inAfternoon) return null;              // 非盘中不调度
    const minutesSinceMidnight =
      now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60; // 当天分
    const nextK = Math.ceil(minutesSinceMidnight / step) * step;       // 下一个右端分钟
    const nextH = Math.floor(nextK / 60);                              // 时
    const nextM = nextK % 60;                                          // 分
    const next = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      nextH,
      nextM,
      0,
      0
    );                                                                  // 下一个边界
    return next.getTime() + GRACE_MIN_SEC * 1000;                       // +宽限秒
  }
  if (freq === "1d" || freq === "1w" || freq === "1M") {                // 日/周/月
    if (isAfterClose) return null;                                      // 已过 15:00 不调度
    const next = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 15, 0, 0, 0);
    return next.getTime() + GRACE_DAILY_SEC * 1000;                     // +宽限秒
  }
  return null;                                                          // 其它频率无调度
}

export function useMarketView() {
  const settings = useUserSettings();                        // 用户设置（含 windowPreset）

  // —— 标的/频率/复权 —— //
  const code = ref(settings.lastSymbol.value || "");         // 标的代码
  const freq = ref(settings.freq?.value || DEFAULT_APP_PREFERENCES.freq); // 频率解耦，默认 constants
  const adjust = settings.adjust;                            // 复权，响应式 ref

  // —— 数据窗口（start/end） —— //
  const start = ref("");                                     // 数据窗口开始（YYYY-MM-DD）
  const end = ref("");                                       // 数据窗口结束（YYYY-MM-DD）

  // —— 窗口模型（提前定义，避免初始化中引用未定义） —— //
  const rng = ref({
    mode: "preset",                                          // preset/manual
    preset: settings.windowPreset.value || DEFAULT_APP_PREFERENCES.windowPreset, // 初始预设
    bars: null,                                              // 最近 N 根（可选）
    startStr: "",                                            // 数据窗口开始字符串
    endStr: "",                                              // 数据窗口结束字符串
    visible: { startStr: "", endStr: "" },                   // 可见窗口（图上 dataZoom）
  });

  const windowPresetRef = settings.windowPreset;             // 持久化窗长预设 ref

  // 工具：日期 → YYYY-MM-DD
  function toDateStr(d) {
    const pad = (n) => String(n).padStart(2, "0");           // 左补零
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  // 从预设计算区间
  function rangeFromPreset(preset) {
    const today = new Date();                                // 今天
    const endStr = toDateStr(today);                         // 结束为今天
    const s = (preset || "").toUpperCase().trim();           // 规范预设
    if (!s || s === "ALL") return { startStr: "", endStr };  // ALL：不指定开始
    if (s === "YTD") {                                       // 年初至今
      const y0 = new Date(today.getFullYear(), 0, 1);
      return { startStr: toDateStr(y0), endStr };
    }
    const m = s.match(/^(\d+)([DMY])$/);                     // N D/M/Y
    if (!m) return { startStr: "", endStr };
    const n = parseInt(m[1], 10);                            // 数值
    const unit = m[2];                                       // 单位
    const days = unit === "D" ? n : unit === "M" ? n * 30 : n * 365; // 近似折算
    const st = new Date(today);                              // 开始日期
    st.setDate(today.getDate() - (days - 1));                // 往前推
    return { startStr: toDateStr(st), endStr };              // 返回起止
  }

  // 近 N 根 → 区间（近似）
  function rangeFromBars(f, bars) {
    const b = Math.max(1, parseInt(bars || 0, 10));          // 正整数
    const today = new Date();                                 // 今天
    const endStr = toDateStr(today);                          // 结束
    let days = b;                                             // 默认按天
    if (f === "1w") days = b * 7;                             // 周→天
    else if (f === "1M") days = b * 30;                       // 月→天
    else if (["1m", "5m", "15m", "30m", "60m"].includes(f)) { // 分钟族
      days = Math.max(1, Math.floor(b / 100) || 1);           // 近似按 100 根/天
    }
    const st = new Date(today);                               // 开始
    st.setDate(today.getDate() - (days - 1));                 // 推算开始
    return { startStr: toDateStr(st), endStr };               // 返回起止
  }

  // 初始化窗口逻辑（解耦窗长与频率；修复：rng 已在前面定义）
  (function initWindow() {
    const preset = windowPresetRef.value || DEFAULT_APP_PREFERENCES.windowPreset; // 读取窗长预设
    if (preset) {                                             // 有预设 → 按预设计算
      const { startStr, endStr } = rangeFromPreset(preset);
      start.value = startStr || "";                           // 写 start
      end.value = endStr || "";                               // 写 end
      rng.value = {                                           // 更新 rng
        mode: "preset",
        preset,
        bars: null,
        startStr,
        endStr,
        visible: { startStr: "", endStr: "" },
      };
      return;                                                 // 完成初始化
    }
    // 无预设 → 尝试旧的 lastStart/lastEnd 兼容（手动模式）
    const ls = settings.lastStart.value || "";
    const le = settings.lastEnd.value || "";
    if (ls || le) {
      start.value = ls;                                       // 用旧手动起止
      end.value = le;
      rng.value = {
        mode: "manual",
        preset: "",
        bars: null,
        startStr: ls,
        endStr: le,
        visible: { startStr: "", endStr: "" },
      };
    } else {
      // 都不存在 → 回退默认预设 'ALL'
      const { startStr, endStr } = rangeFromPreset(DEFAULT_APP_PREFERENCES.windowPreset);
      start.value = startStr || "";
      end.value = endStr || "";
      rng.value = {
        mode: "preset",
        preset: DEFAULT_APP_PREFERENCES.windowPreset,
        bars: null,
        startStr,
        endStr,
        visible: { startStr: "", endStr: "" },
      };
    }
  })();

  // —— 指标相关 —— //
  const chartType = ref(settings.chartType?.value || DEFAULT_APP_PREFERENCES.chartType); // 图形类型持久化
  const maPeriodsMap = computed(() => {                                    // 启用的 MA 映射
    const configs = settings.maConfigs.value || {};
    return Object.entries(configs)
      .filter(([, conf]) => conf && conf.enabled)
      .reduce((acc, [key, conf]) => {
        acc[key] = conf.period;
        return acc;
      }, {});
  });

  const useMACD = ref(settings.useMACD?.value ?? DEFAULT_APP_PREFERENCES.useMACD); // 指标开关
  const useKDJ  = ref(settings.useKDJ?.value  ?? DEFAULT_APP_PREFERENCES.useKDJ);
  const useRSI  = ref(settings.useRSI?.value  ?? DEFAULT_APP_PREFERENCES.useRSI);
  const useBOLL = ref(settings.useBOLL?.value ?? DEFAULT_APP_PREFERENCES.useBOLL);

  // —— 数据容器 —— //
  const loading = ref(false);
  const error = ref("");
  const meta = ref(null);
  const candles = ref([]);
  const indicators = ref({});

  // —— 自动刷新调度 —— //
  let autoTimer = null;
  function scheduleAutoRefresh() {
    if (autoTimer) { clearTimeout(autoTimer); autoTimer = null; }            // 清旧调度
    const nextTs = computeNextBoundaryTs(freq.value);                        // 下一边界
    if (!nextTs) return;                                                     // 无边界则返回
    const delay = Math.max(0, nextTs - Date.now());                          // 距离时间
    autoTimer = setTimeout(async () => {                                     // 定时执行
      await reload();
      scheduleAutoRefresh();                                                 // 继续循环调度
    }, delay);
  }

  // —— 轻冷却 —— //
  const lastFetchAt = new Map();                                             // 最近请求时间
  function withinCooldown() {
    const key = `${code.value}|${freq.value}|${adjust.value}|${start.value || ""}|${end.value || ""}`; // 幂等键
    const prev = lastFetchAt.get(key) || 0;                                  // 上次时间
    const now = Date.now();                                                  // 当前时间
    if (now - prev < DEFAULT_COOLDOWN_SEC * 1000) return true;               // 冷却期内
    lastFetchAt.set(key, now);                                               // 记录时间
    return false;                                                            // 不在冷却
  }

  // —— 数据拉取 —— //
  async function reload(force = false) {
    if (!code.value) return;                                                 // 无代码不拉
    if (withinCooldown() && !force) return;                                  // 冷却期内不拉
    loading.value = true;                                                    // 置加载
    error.value = "";                                                        // 清错误
    try {
      const data = await fetchCandles({
        code: code.value,                                                    // 标的
        freq: freq.value,                                                    // 频率
        adjust: adjust.value,                                                // 复权
        start: start.value || undefined,                                     // 起（可能空）
        end: end.value || undefined,                                         // 止（可能空）
        include: buildIncludeParam(),                                        // 指标
        ma_periods: JSON.stringify(maPeriodsMap.value),                      // MA 周期映射（仅启用项）
      });
      meta.value = data.meta;                                                // 元信息
      candles.value = data.candles || [];                                    // 蜡烛
      indicators.value = data.indicators || {};                              // 指标
    } catch (e) {
      error.value = e?.message || "请求失败";                                 // 记录错误
    } finally {
      loading.value = false;                                                 // 复位加载
    }
  }

  // —— include 构建 —— //
  function buildIncludeParam() {
    const arr = ["vol"];                                                     // 固定包含 VOL
    if (Object.keys(maPeriodsMap.value).length > 0) arr.push("ma");          // 有启用 MA 则追加
    if (useMACD.value) arr.push("macd");                                     // 其它指标按开关追加
    if (useKDJ.value)  arr.push("kdj");
    if (useRSI.value)  arr.push("rsi");
    if (useBOLL.value) arr.push("boll");
    return arr.join(",");                                                    // 逗号分隔
  }

  // —— 窗长操作（写回持久化的 windowPreset） —— //
  async function applyPreset(preset) {
    settings.setWindowPreset(preset || DEFAULT_APP_PREFERENCES.windowPreset); // 持久化窗长预设
    const { startStr, endStr } = rangeFromPreset(preset);                    // 计算区间
    rng.value = {                                                            // 切换为预设模式
      mode: "preset",
      preset,
      bars: null,
      startStr,
      endStr,
      visible: { startStr: "", endStr: "" },
    };
    start.value = startStr || "";                                            // 应用起止
    end.value = endStr || "";
    await reload(true);                                                      // 强制重载数据
  }

  async function applyBars(n) {
    // “最近 N 根”属于手动行为（不写 windowPreset）
    const { startStr, endStr } = rangeFromBars(freq.value, n);               // 计算区间
    rng.value = {                                                            // 仍按 preset 模式（bars 近似）
      mode: "preset",
      preset: "",
      bars: Math.max(1, parseInt(n || 0, 10)),
      startStr,
      endStr,
      visible: { startStr: "", endStr: "" },
    };
    start.value = startStr || "";                                            // 应用起止
    end.value = endStr || "";
    await reload(true);                                                      // 强制重载
  }

  async function applyManual(s, e) {
    // 手动模式清空 windowPreset，以 lastStart/lastEnd 生效
    settings.setWindowPreset("");                                            // 清空预设（进入手动）
    rng.value = {                                                            // 切换为手动模式
      mode: "manual",
      preset: "",
      bars: null,
      startStr: s || "",
      endStr: e || "",
      visible: { startStr: "", endStr: "" },
    };
    start.value = s || "";                                                   // 应用起止
    end.value = e || "";
    await reload(true);                                                      // 强制重载
  }

  function applyZoomWindow(visibleStartStr, visibleEndStr) {
    rng.value.visible = { startStr: visibleStartStr || "", endStr: visibleEndStr || "" }; // 记录可见窗口
  }

  async function applyVisibleAsDataWindow() {
    const vs = rng.value.visible || {};                                      // 读取可见
    await applyManual(vs.startStr || "", vs.endStr || "");                   // 应用为数据窗口
  }

  // —— 持久化联动 —— //
  watch(code, (v) => { settings.setLastSymbol(v || ""); reload(); });        // 代码变化立刻拉取
  watch(freq, (v) => { settings.setFreq?.(v); scheduleAutoRefresh(); });     // 频率变化仅刷新调度
  watch(adjust, (v) => { settings.setAdjust?.(v); reload(); });              // 复权变化重载

  // 手动区间才保存 lastStart/lastEnd；预设模式以 windowPreset 为准
  watch(start, (v) => { if (rng.value.mode === "manual") settings.setLastStart(v || ""); });
  watch(end,   (v) => { if (rng.value.mode === "manual") settings.setLastEnd(v || ""); });

  watch(chartType, (v) => settings.setChartType?.(v));                       // 图形类型持久化

  watch([useMACD, useKDJ, useRSI, useBOLL], ([b, c, d, e]) => {              // 指标开关变化
    settings.setUseMACD?.(b);
    settings.setUseKDJ?.(c);
    settings.setUseRSI?.(d);
    settings.setUseBOLL?.(e);
    reload();
  }, { deep: true });

  watch(maPeriodsMap, (newVal, oldVal) => {                                  // 启用的 MA 变化
    if (JSON.stringify(newVal) !== JSON.stringify(oldVal)) reload();
  }, { deep: true });

  // 启动调度自动刷新
  scheduleAutoRefresh();

  // —— 导出 API —— //
  return {
    // 核心数据与参数
    code, freq, adjust, start, end, chartType, maPeriodsMap,
    // 指标开关
    useMACD, useKDJ, useRSI, useBOLL,
    // 数据与状态
    loading, error, meta, candles, indicators,
    // 窗口模型与操作
    rng,
    getPresetsForCurrentFreq: () => WINDOW_PRESETS.slice(),  // 按钮集合（与频率解耦）
    applyPreset, applyBars, applyManual, applyZoomWindow, applyVisibleAsDataWindow,
    // 数据刷新
    reload,
    // hover 联动（保持原有 API）
    focusIndex: ref(-1),
  };
}
