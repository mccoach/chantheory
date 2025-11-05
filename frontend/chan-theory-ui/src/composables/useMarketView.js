// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useMarketView.js
// ==============================
// (REFACTORED - FINAL VERSION V3 - SSE REPAIRED)
// - (FIX) 修复了 SSE 处理器 `sseHandler` 中错误的 Python 日志调用，改为 `console.log`。
// - (FIX) 移除了对已不存在的 `heal_` 任务键的订阅逻辑，因为它在后端不会被发布。
// - 通过 `useEventStream` 订阅后台数据更新事件，当相关标的数据更新时，自动触发 `reload`。
// ==============================

import { ref, watch, computed, toRef, onUnmounted } from "vue";
import { fetchCandles } from "@/services/marketService";
import { useUserSettings } from "@/composables/useUserSettings";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useEventStream } from "@/composables/useEventStream";

// 模块级变量，用于请求覆盖式防抖
let _abortCtl = null;
let _lastReqSeq = 0;
let _lastAppliedKey = "";

// 获取命令中枢单例
const hub = useViewCommandHub();

// 根据参数生成唯一的请求键
function makeReqKey(p) {
  const parts = [
    p.code,
    p.freq,
    p.adjust,
  ];
  return parts.join("|");
}

export function useMarketView(options = {}) {
  const autoStart = options?.autoStart !== false;

  const settings = useUserSettings();
  const { onDataUpdated, offDataUpdated } = useEventStream();

  // --- 核心响应式状态 ---
  const code = ref(settings.preferences.lastSymbol || "");
  const freq = ref(settings.preferences.freq || "1d");
  const adjust = toRef(settings.preferences, 'adjust');
  const windowPreset = ref(settings.preferences.windowPreset || "ALL");
  const rightTs = ref(settings.getRightTs(code.value, freq.value) || null);

  const loading = ref(false);
  const error = ref("");
  const meta = ref(null);
  const candles = ref([]);
  const indicators = ref({});

  const chartType = ref(settings.preferences.chartType || "kline");
  const visibleRange = ref({ startStr: "", endStr: "" });
  const displayBars = ref(0);
  
  // --- SSE 事件驱动刷新 ---
  let sseUnsubscribers = [];
  const sseHandler = (eventData) => {
    // 只要是当前标的的任何数据更新，都触发刷新
    if (eventData?.symbol === code.value) {
      // (FIX) 修复错误的 Python 日志调用
      console.log(`[useMarketView] SSE triggered reload for ${code.value}`);
      reload({ force: true });
    }
  };

  // 监听 code 变化，重新订阅相关的所有SSE事件
  watch(code, (newCode) => {
    // 先取消所有旧的订阅
    sseUnsubscribers.forEach(unsub => unsub());
    sseUnsubscribers = [];
    
    if (newCode) {
      // 为当前标的的所有可能的任务key注册同一个处理器
      const ALL_FREQS = ['1m', '5m', '15m', '30m', '60m', '1d', '1w', '1M'];
      ALL_FREQS.forEach(f => {
        const taskKey = `candles_${newCode}_${f}`;
        onDataUpdated(taskKey, sseHandler);
        sseUnsubscribers.push(() => offDataUpdated(taskKey, sseHandler));
      });
      // (REMOVED) 移除对已不存在的 heal_ 任务的订阅
    }
  }, { immediate: true });

  onUnmounted(() => {
    sseUnsubscribers.forEach(unsub => unsub());
  });
  
  // --- 计算属性 ---
  const maPeriodsMap = computed(() => {
    const configs = settings.chartDisplay.maConfigs || {};
    return Object.entries(configs).reduce((acc, [key, conf]) => {
      const n = Number(conf?.period);
      if (Number.isFinite(n) && n > 0) acc[key] = n;
        return acc;
      }, {});
  });

  function buildIncludeParam() {
    return "ma,macd,kdj,rsi,boll,vol";
  }

  // --- 命令中枢订阅 ---
  hub.onChange((st) => {
    displayBars.value = Math.max(1, Number(st.barsCount || 1));
    rightTs.value = st.rightTs != null ? Number(st.rightTs) : rightTs.value;
    windowPreset.value = st.presetKey || windowPreset.value;
  });

  // --- 核心数据加载方法 ---
  async function reload(opts = {}) {
    if (!code.value) return;

    const params = {
      code: code.value,
      freq: freq.value,
      adjust: adjust.value,
      include: buildIncludeParam(),
      ma_periods: JSON.stringify(maPeriodsMap.value || {}),
    };

    const key = makeReqKey(params);
    if (key === _lastAppliedKey && !opts.force) {
      return;
    }

    try { if (_abortCtl) _abortCtl.abort(); } catch {}
    const ctl = new AbortController();
    _abortCtl = ctl;
    const mySeq = ++_lastReqSeq;

    loading.value = true;
    error.value = "";

    try {
      const data = await fetchCandles(params, { signal: ctl.signal });
      if (mySeq !== _lastReqSeq || ctl.signal.aborted) return;

      meta.value = data.meta || {};
      candles.value = data.candles || [];
      indicators.value = data.indicators || {};

      const allRowsNow = Number(meta.value?.all_rows || 0);
      const minTs = candles.value?.[0]?.t ? Date.parse(candles.value[0].t) : undefined;
      const maxTs = allRowsNow > 0 && candles.value?.[allRowsNow - 1] ? Date.parse(candles.value[allRowsNow - 1].t) : undefined;
      hub.setDatasetBounds({ minTs, maxTs, totalRows: allRowsNow });

      // 使用服务端的视窗建议来更新前端显示
      visibleRange.value = {
        startStr: meta.value.start || "",
        endStr: meta.value.end || "",
      };
      displayBars.value = meta.value.view_rows || 0;


      settings.setFreq(freq.value);
      _lastAppliedKey = key;
      
    } catch (e) {
      const msg = String(e?.message || "");
      const isAbort = e?.name === "CanceledError" || e?.code === "ERR_CANCELED" || e?.name === "AbortError" || msg.toLowerCase().includes("canceled") || msg.toLowerCase().includes("aborted");
      if (isAbort) return;
      error.value = e?.message || "请求失败";
    } finally {
      if (mySeq === _lastReqSeq && ctl === _abortCtl) {
        loading.value = false;
      }
    }
  }

  // --- 外部交互API ---
  function previewView(bars, anchorTs, sIdx, eIdx) {
      // 此函数现在仅由旧的 dataZoom 事件调用，新架构下其逻辑被简化
      // 核心状态变更由 command hub 管理，此处仅作兼容
  }

  function setFreq(newFreq) {
    if (!newFreq || newFreq === freq.value) return;
    freq.value = newFreq;
    settings.setFreq(newFreq);
    const st = hub.getState();
    hub.execute("ChangeFreq", { freq: newFreq, allRows: st.allRows });
    reload({ force: true });
  }
  
  async function applyPreset(preset) {
    const p = String(preset || "ALL");
    windowPreset.value = p;
    settings.setWindowPreset(p);
    const st = hub.getState();
    hub.execute("ChangeWidthPreset", { presetKey: p, allRows: st.allRows });
    // Reload is triggered by hub's watcher
  }
  
  async function setBars(bars) {
    const b = Math.max(1, Math.floor(Number(bars || 1)));
    hub.execute("SetBarsManual", { nextBars: b });
  }
  
  function zoomIn() {
    const v = hub.getState().barsCount || 1;
    setBars(Math.ceil(v / 1.2));
  }
  
  function zoomOut() {
    const v = hub.getState().barsCount || 1;
    setBars(Math.ceil(v * 1.2));
  }

  function applyLocalZoom(startIdx, endIdx, nextBars) {
    // This function is now deprecated as we use full-range rendering
  }

  // --- 初始化逻辑 ---
  watch(code, (v) => {
    settings.setLastSymbol(v || "");
    hub.execute("ChangeSymbol", { symbol: String(v || "") });
    if (autoStart) reload({ force: true });
  });
  
  watch(adjust, () => {
    if (autoStart) reload({ force: true });
  });
  
  // 监听hub的变化来触发reload
  hub.onChange(() => {
      reload();
  });

  hub.initFromPersist(code.value, freq.value);
  if (autoStart) {
    reload({ force: true });
  }

  // --- 导出 ---
  return {
    code, freq, adjust, chartType, loading, error, meta, candles, indicators,
    windowPreset, rightTs, visibleRange, displayBars,
    setFreq, applyPreset, setBars, zoomIn, zoomOut, reload,
    get viewStartIdx() { return Number(meta.value?.view_start_idx ?? 0); },
    get viewEndIdx() { return Number(meta.value?.view_end_idx ?? -1); },
    get allRows() { return Number(meta.value?.all_rows ?? 0); },
    get viewRows() { return Number(meta.value?.view_rows ?? 0); },
  };
}
