/* E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useMarketView.js */
/* ============================== */
/* 说明：页面核心状态与行为（统一窗长 + 切频不跳变） */
/* 变更点（严格限域、最小必要改动）： */
/* - 固定统一窗长列表 UNIFIED_PRESETS（扩展款 10 项：5D、10D、1M、3M、6M、YTD、1Y、3Y、5Y、ALL） */
/* - getPresetsForCurrentFreq() 统一返回 UNIFIED_PRESETS，按钮在 SymbolPanel 固定不变 */
/* - 初始无 lastStart/lastEnd 时，rng 默认 preset='ALL'（UI 高亮 ALL），符合“默认选 ALL” */
/* 其余逻辑保持不变：start/end 仍持久化，applyPreset/applyManual 等沿用原实现。 */
/* ============================== */

import { ref, watch, computed } from "vue";                   // Vue 响应式 API
import { fetchCandles } from "@/services/marketService";      // 后端行情服务
import { useUserSettings } from "@/composables/useUserSettings"; // 用户本地设置

/* 统一窗长列表（扩展款 10 项） */
const UNIFIED_PRESETS = [
  "5D", "10D",
  "1M", "3M", "6M",
  "YTD", "1Y", "3Y", "5Y",
  "ALL",
];

const GRACE_MIN_SEC = 5;          // 分钟级宽限（秒）
const GRACE_DAILY_SEC = 180;      // 日/周/月宽限（秒）
const DEFAULT_COOLDOWN_SEC = 10;  // 轻冷却

/* 计算下一数据边界时刻（用于自动刷新调度） */
function computeNextBoundaryTs(freq) {
  const now = new Date();
  const hm = now.getHours() * 60 + now.getMinutes();
  const isAfterClose = hm >= 15 * 60;
  const inMorning = hm >= 9 * 60 + 30 && hm < 11 * 60 + 30;
  const inAfternoon = hm >= 13 * 60 && hm < 15 * 60;
  const stepMap = {"1m":1,"5m":5,"15m":15,"30m":30,"60m":60};
  if (freq in stepMap) {
    const step = stepMap[freq];
    if (!inMorning && !inAfternoon) return null;
    const minutesSinceMidnight = now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60;
    const nextK = Math.ceil(minutesSinceMidnight / step) * step;
    const nextH = Math.floor(nextK / 60);
    const nextM = nextK % 60;
    const next = new Date(now.getFullYear(), now.getMonth(), now.getDate(), nextH, nextM, 0, 0);
    return next.getTime() + GRACE_MIN_SEC * 1000;
  }
  if (freq === "1d" || freq === "1w" || freq === "1M") {
    if (isAfterClose) return null;
    const next = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 15, 0, 0, 0);
    return next.getTime() + GRACE_DAILY_SEC * 1000;
  }
  return null;
}

export function useMarketView() {
  const settings = useUserSettings();                          // 用户设置
  const code = ref(settings.lastSymbol.value || "");           // 标的代码
  const freq = ref(settings.freq?.value || "1d");              // 频率
  const adjust = settings.adjust;                               // 复权（直接用全局响应式）
  const start = ref(settings.lastStart.value || "");           // 开始日期（YYYY-MM-DD）
  const end = ref(settings.lastEnd.value || "");               // 结束日期（YYYY-MM-DD）
  const chartType = ref(settings.chartType?.value || "kline"); // 图形类型

  /* MA 周期映射（固定键 → 周期） */
  const maPeriodsMap = computed(() => {
    const configs = settings.maConfigs.value || {};
    return Object.entries(configs)
      .filter(([, conf]) => conf && conf.enabled)
      .reduce((acc, [key, conf]) => {
        acc[key] = conf.period;
        return acc;
      }, {});
  });

  /* 其它指标开关（保持原有） */
  const useMACD = ref(settings.useMACD?.value ?? true);
  const useKDJ = ref(settings.useKDJ?.value ?? false);
  const useRSI = ref(settings.useRSI?.value ?? false);
  const useBOLL = ref(settings.useBOLL?.value ?? false);

  /* 加载状态与数据容器 */
  const loading = ref(false);
  const error = ref("");
  const meta = ref(null);
  const candles = ref([]);
  const indicators = ref({});

  /* 区间模型：新增默认 ALL 的初始化（当且仅当没有持久化 start/end 时） */
  const noSavedRange = !(start.value || end.value);
  const rng = ref({
    mode: noSavedRange ? "preset" : "preset",     // 维持 preset 模式；若用户手动修改，会在 applyManual 中置 "manual"
    preset: noSavedRange ? "ALL" : "",            // 无保存则默认 ALL；有保存则保持空（显示为“自定义/手动”）
    bars: null,
    startStr: start.value || "",
    endStr: end.value || "",
    visible: { startStr: "", endStr: "" },
  });

  /* 当前 hover 索引（跨窗体联动） */
  const focusIndex = ref(-1);

  /* 统一窗长列表（供 UI 按钮使用） */
  function getPresetsForCurrentFreq() {
    return UNIFIED_PRESETS.slice(); // 固定列表，跨频率不变
  }

  /* 自动刷新调度（保持原有） */
  let autoTimer = null;
  function scheduleAutoRefresh() {
    if (autoTimer) { clearTimeout(autoTimer); autoTimer = null; }
    const nextTs = computeNextBoundaryTs(freq.value);
    if (!nextTs) return;
    const delay = Math.max(0, nextTs - Date.now());
    autoTimer = setTimeout(async () => {
      await reload();
      scheduleAutoRefresh();
    }, delay);
  }

  /* 轻冷却（同一查询 10s 内避免过度请求） */
  const lastFetchAt = new Map();
  function withinCooldown() {
    const key = `${code.value}|${freq.value}|${adjust.value}|${start.value || ""}|${end.value || ""}`;
    const prev = lastFetchAt.get(key) || 0;
    const now = Date.now();
    if (now - prev < DEFAULT_COOLDOWN_SEC * 1000) return true;
    lastFetchAt.set(key, now);
    return false;
  }

  /* 主动刷新（保留逻辑；不改变 start/end） */
  async function reload(force = false) {
    if (!code.value) return;
    if (withinCooldown() && !force) return;
    loading.value = true;
    error.value = "";
    try {
      const data = await fetchCandles({
        code: code.value,
        freq: freq.value,
        adjust: adjust.value,
        start: start.value || undefined,
        end: end.value || undefined,
        include: buildIncludeParam(),
        ma_periods: JSON.stringify(maPeriodsMap.value),
      });
      meta.value = data.meta;
      candles.value = data.candles || [];
      indicators.value = data.indicators || {};
    } catch (e) {
      error.value = e?.message || "请求失败";
    } finally {
      loading.value = false;
    }
  }

  /* 日期字符串工具 */
  function toDateStr(d){ const p=(n)=>String(n).padStart(2,"0"); return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`; }

  /* 预设 → 日期窗口 */
  function rangeFromPreset(preset){
    const today=new Date(), endStr=toDateStr(today);
    const s=(preset||"").toUpperCase().trim();
    if(!s||s==="ALL")return{startStr:"",endStr};
    if(s==="YTD"){ const y0=new Date(today.getFullYear(),0,1); return{startStr:toDateStr(y0),endStr}; }
    const m=s.match(/^(\d+)([DMY])$/);
    if(!m)return{startStr:"",endStr};
    const n=parseInt(m[1],10), unit=m[2];
    const days=unit==="D"?n:unit==="M"?n*30:n*365;
    const start=new Date(today); start.setDate(today.getDate()-(days-1));
    return{startStr:toDateStr(start),endStr};
  }

  /* 近 N 根（保留逻辑，用于“最近 N 根”按钮） */
  function rangeFromBars(f,bars){
    const b=Math.max(1,parseInt(bars||0,10));
    const today=new Date(), endStr=toDateStr(today);
    let days=b;
    if(f==="1w")days=b*7; else if(f==="1M")days=b*30;
    else if(["1m","5m","15m","30m","60m"].includes(f)){ days=Math.max(1,Math.floor(b/100)||1); }
    const start=new Date(today); start.setDate(today.getDate()-(days-1));
    return{startStr:toDateStr(start),endStr};
  }

  /* include 参数拼装 */
  function buildIncludeParam(){
    const arr=["vol"];
    if (Object.keys(maPeriodsMap.value).length > 0) arr.push("ma");
    if(useMACD.value)arr.push("macd"); if(useKDJ.value)arr.push("kdj");
    if(useRSI.value)arr.push("rsi"); if(useBOLL.value)arr.push("boll");
    return arr.join(",");
  }

  /* 应用预设：设置 rng 并刷新（start/end 持久化由 watcher 完成） */
  async function applyPreset(preset){
    const{startStr,endStr}=rangeFromPreset(preset);
    rng.value={mode:"preset",preset,bars:null,startStr,endStr,visible:{startStr:"",endStr:""}};
    start.value=startStr||""; end.value=endStr||"";
    await reload(true);
  }

  /* 最近 N 根 → 日期窗口（保留） */
  async function applyBars(n){
    const{startStr,endStr}=rangeFromBars(freq.value,n);
    rng.value={mode:"preset",preset:"",bars:Math.max(1,parseInt(n||0,10)),startStr,endStr,visible:{startStr:"",endStr:""}};
    start.value=startStr||""; end.value=endStr||"";
    await reload(true);
  }

  /* 手动日期 → 进入 manual 模式（保留） */
  async function applyManual(s,e){
    rng.value={mode:"manual",preset:"",bars:null,startStr:s||"",endStr:e||"",visible:{startStr:"",endStr:""}};
    start.value=s||""; end.value=e||"";
    await reload(true);
  }

  /* 记录可见窗口（由图表联动传入） */
  function applyZoomWindow(visibleStartStr,visibleEndStr){ rng.value.visible={startStr:visibleStartStr||"",endStr:visibleEndStr||""}; }

  /* 将可见窗口作为数据窗口（保留） */
  async function applyVisibleAsDataWindow(){ const vs=rng.value.visible||{}; await applyManual(vs.startStr||"",vs.endStr||""); }

  /* —— 持久化与联动 —— */
  watch(code, (v)=>{ settings.setLastSymbol(v||""); reload(); });
  watch(freq, (v)=>{ settings.setFreq?.(v); scheduleAutoRefresh(); });
  watch(adjust, (v)=>{ settings.setAdjust?.(v); reload(); });
  watch(start, (v)=>settings.setLastStart(v||""));
  watch(end, (v)=>settings.setLastEnd(v||""));
  watch(chartType, (v)=>settings.setChartType?.(v));
  watch([useMACD,useKDJ,useRSI,useBOLL], ([b,c,d,e])=>{
    settings.setUseMACD?.(b); settings.setUseKDJ?.(c);
    settings.setUseRSI?.(d); settings.setUseBOLL?.(e);
    reload();
  }, { deep:true });
  watch(maPeriodsMap, (newVal, oldVal) => { if (JSON.stringify(newVal) !== JSON.stringify(oldVal)) reload(); }, { deep: true });

  /* 首次调度自动刷新 */
  scheduleAutoRefresh();

  /* 导出接口 */
  return {
    code, freq, adjust, start, end, chartType, maPeriodsMap,
    useMACD, useKDJ, useRSI, useBOLL,
    loading, error, meta, candles, indicators,
    rng, getPresetsForCurrentFreq,
    applyPreset, applyBars, applyManual, applyZoomWindow, applyVisibleAsDataWindow,
    reload,
    focusIndex,
  };
}
