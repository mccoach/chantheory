// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useMarketView.js
// ==============================
// 说明：页面核心状态与行为（修复复权响应式 + 移除 120m）
// 变更点：
// - 不再创建本地 adjust ref，直接使用并监听 useUserSettings 中的全局响应式 adjust 状态。
// - 从所有预设和计算逻辑中移除 120m。
// ==============================

import { ref, watch, computed } from "vue";                   // Vue 响应式 API
import { fetchCandles } from "@/services/marketService";      // 后端行情服务
import { useUserSettings } from "@/composables/useUserSettings"; // 用户本地设置

const PRESETS_BY_FREQ = {                                     // 频率 → 快捷预设
  "1m":  ["5D", "10D", "30D", "60D", "ALL"],
  "5m":  ["1M", "3M", "6M", "YTD", "ALL"],
  "15m": ["1M", "3M", "6M", "YTD", "ALL"],
  "30m": ["1M", "3M", "6M", "YTD", "ALL"],
  "60m": ["1M", "3M", "6M", "YTD", "ALL"],
  "1d":  ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "10Y", "ALL"],
  "1w":  ["YTD", "1Y", "3Y", "5Y", "10Y", "ALL"],
  "1M":  ["YTD", "1Y", "3Y", "5Y", "10Y", "ALL"],
};

const GRACE_MIN_SEC = 5;
const GRACE_DAILY_SEC = 180;
const DEFAULT_COOLDOWN_SEC = 10;

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
  const code = ref(settings.lastSymbol.value || "");
  const freq = ref(settings.freq?.value || "1d");
  // 修复：直接使用 settings 中的 adjust 响应式引用，不再创建本地 ref
  const adjust = settings.adjust;
  const start = ref(settings.lastStart.value || "");
  const end = ref(settings.lastEnd.value || "");
  const chartType = ref(settings.chartType?.value || "kline");

  const maPeriodsMap = computed(() => {
    const configs = settings.maConfigs.value || {};
    return Object.entries(configs)
      .filter(([, conf]) => conf && conf.enabled)
      .reduce((acc, [key, conf]) => {
        acc[key] = conf.period;
        return acc;
      }, {});
  });

  const useMACD = ref(settings.useMACD?.value ?? true);
  const useKDJ = ref(settings.useKDJ?.value ?? false);
  const useRSI = ref(settings.useRSI?.value ?? false);
  const useBOLL = ref(settings.useBOLL?.value ?? false);

  const loading = ref(false);
  const error = ref("");
  const meta = ref(null);
  const candles = ref([]);
  const indicators = ref({});

  const rng = ref({
    mode: start.value || end.value ? "manual" : "preset",
    preset: "", bars: null, startStr: start.value || "", endStr: end.value || "",
    visible: { startStr: "", endStr: "" },
  });

  const focusIndex = ref(-1);

  function getPresetsForCurrentFreq() { return PRESETS_BY_FREQ[freq.value] || []; }

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

  const lastFetchAt = new Map();
  function withinCooldown() {
    const key = `${code.value}|${freq.value}|${adjust.value}|${start.value || ""}|${end.value || ""}`; // 加上 adjust
    const prev = lastFetchAt.get(key) || 0;
    const now = Date.now();
    if (now - prev < DEFAULT_COOLDOWN_SEC * 1000) return true;
    lastFetchAt.set(key, now);
    return false;
  }

  async function reload(force = false) {
    if (!code.value) return;
    if (withinCooldown() && !force) return;
    loading.value = true;
    error.value = "";
    try {
      const data = await fetchCandles({
        code: code.value,
        freq: freq.value,
        adjust: adjust.value, // 使用全局响应式状态的值
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

  function toDateStr(d){ const p=(n)=>String(n).padStart(2,"0"); return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`; }
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
  function rangeFromBars(f,bars){
    const b=Math.max(1,parseInt(bars||0,10));
    const today=new Date(), endStr=toDateStr(today);
    let days=b;
    if(f==="1w")days=b*7; else if(f==="1M")days=b*30;
    else if(["1m","5m","15m","30m","60m"].includes(f)){ days=Math.max(1,Math.floor(b/100)||1); }
    const start=new Date(today); start.setDate(today.getDate()-(days-1));
    return{startStr:toDateStr(start),endStr};
  }
  function buildIncludeParam(){
    const arr=["vol"];
    if (Object.keys(maPeriodsMap.value).length > 0) arr.push("ma");
    if(useMACD.value)arr.push("macd"); if(useKDJ.value)arr.push("kdj");
    if(useRSI.value)arr.push("rsi"); if(useBOLL.value)arr.push("boll");
    return arr.join(",");
  }
  async function applyPreset(preset){
    const{startStr,endStr}=rangeFromPreset(preset);
    rng.value={mode:"preset",preset,bars:null,startStr,endStr,visible:{startStr:"",endStr:""}};
    start.value=startStr||""; end.value=endStr||"";
    await reload();
  }
  async function applyBars(n){
    const{startStr,endStr}=rangeFromBars(freq.value,n);
    rng.value={mode:"preset",preset:"",bars:Math.max(1,parseInt(n||0,10)),startStr,endStr,visible:{startStr:"",endStr:""}};
    start.value=startStr||""; end.value=endStr||"";
    await reload();
  }
  async function applyManual(s,e){
    rng.value={mode:"manual",preset:"",bars:null,startStr:s||"",endStr:e||"",visible:{startStr:"",endStr:""}};
    start.value=s||""; end.value=e||"";
    await reload();
  }
  function applyZoomWindow(visibleStartStr,visibleEndStr){ rng.value.visible={startStr:visibleStartStr||"",endStr:visibleEndStr||""}; }
  async function applyVisibleAsDataWindow(){ const vs=rng.value.visible||{}; await applyManual(vs.startStr||"",vs.endStr||""); }

  watch(code, (v)=>{ settings.setLastSymbol(v||""); reload(); });
  watch(freq, (v)=>{ settings.setFreq?.(v); scheduleAutoRefresh(); });
  // 修复：监听从 settings 中导入的全局 adjust 状态
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

  scheduleAutoRefresh();

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
