// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useMarketView.js
// ==============================
// 覆盖式防抖（Abort + reqId）+ 中枢化显示状态订阅（bars/rightTs/presetKey）
// 本次重构（轻度）：保持原函数/变量顺序，不扩大范围，仅补充注释与确保 anchor_ts = 中枢 rightTs。
// - 显示状态与后端解耦：任何 UI 交互先汇总到 useViewCommandHub，reload 时以 hub.rightTs 为锚点，服务端一次成型返回 meta.view_*。
// - FIX: 导入 toRef，并正确使用它来创建 adjust 的响应式引用。
// ==============================

import { ref, watch, computed, toRef } from "vue";
import { fetchCandles } from "@/services/marketService";
import { useUserSettings } from "@/composables/useUserSettings";
// 新增：命令中枢（单例）
import { useViewCommandHub } from "@/composables/useViewCommandHub";

// 模块私有：管理“仅保留最新请求”
let _abortCtl = null;
let _lastReqSeq = 0;
let _lastAppliedKey = "";

// —— 新增：注入命令中枢（保持原位置与顺序，不调整） —— //
const hub = useViewCommandHub();

function makeReqKey(p) {
  const parts = [
    p.code,
    p.freq,
    p.adjust,
    p.window_preset ?? "",
    Number.isFinite(+p.bars) ? +p.bars : "",
    Number.isFinite(+p.anchor_ts) ? +p.anchor_ts : "",
    p.include ?? "",
    p.ma_periods ?? "",
  ];
  return parts.join("|");
}

export function useMarketView(options = {}) {
  const autoStart = options?.autoStart !== false;

  const settings = useUserSettings();

  // —— 核心状态（保持原导出签名与前后顺序） —— //
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

  // MOD: 统一传递设置中“出现”的所有 MA 周期，无视 enabled（一次性计算，后续只控制显示）
  const maPeriodsMap = computed(() => {
    const configs = settings.chartDisplay.maConfigs || {};
    return Object.entries(configs).reduce((acc, [key, conf]) => {
      const n = Number(conf?.period);
      if (Number.isFinite(n) && n > 0) acc[key] = n;
        return acc;
      }, {});
  });

  // MOD: 始终请求全量指标（ma,macd,kdj,rsi,boll,vol），由前端决定显示与样式；避免切换开关时等待后端
  function buildIncludeParam() {
    return "ma,macd,kdj,rsi,boll,vol";
  }

  // —— 中枢订阅（显示层文案同步）：不改变 bars/rightTs，仅更新展示 —— //
  hub.onChange((st) => {
    displayBars.value = Math.max(1, Number(st.barsCount || 1));
    rightTs.value = st.rightTs != null ? Number(st.rightTs) : rightTs.value;
    windowPreset.value = st.presetKey || windowPreset.value;
  });

  // 预览态（保留导出签名；内部委派中枢，避免分散状态源）
  function previewView(bars, anchorTs, sIdx, eIdx) {
    const b = Math.max(1, Math.floor(Number(bars || 1)));
    if (Number.isFinite(+sIdx) && Number.isFinite(+eIdx)) {
      hub.execute("ScrollZoom", { nextBars: b, nextRightTs: anchorTs });
    } else {
      hub.execute("SetBarsManual", { nextBars: b });
    }
  }

  // 本地缩放（保留导出；委派中枢）
  function applyLocalZoom(startIdx, endIdx, nextBars) {
    const arr = candles.value || [];
    const n = arr.length;
    if (!n) return;
    const sIdx = Math.max(0, Math.min(n - 1, Number(startIdx)));
    const eIdx = Math.max(0, Math.min(n - 1, Number(endIdx)));
    const anchorTs = arr[eIdx]?.t ? Date.parse(arr[eIdx].t) : rightTs.value;
    const b = Math.max(1, Number(nextBars || eIdx - sIdx + 1));
    hub.execute("ScrollZoom", { nextBars: b, nextRightTs: anchorTs });
  }

  // 统一加载（服务端一次成型 + 覆盖式防抖）：anchor_ts 始终取中枢 rightTs
  async function reload(opts = {}) {
    if (!code.value) return;

    const st = hub.getState();
    const anchor = Number.isFinite(+st.rightTs)
      ? Math.floor(+st.rightTs)
      : undefined;

    const params = {
      code: code.value,
      freq: freq.value,
      adjust: adjust.value,
      include: buildIncludeParam(), // MOD
      ma_periods: JSON.stringify(maPeriodsMap.value || {}), // MOD: 全量 MA 周期
      window_preset: opts.window_preset ?? windowPreset.value,
      bars: Math.max(1, Math.floor(Number(st.barsCount || 1))),
      anchor_ts: anchor, // —— 关键：统一以中枢 rightTs 作为锚点 —— //
    };

    const key = makeReqKey(params);
    if (key === _lastAppliedKey && !opts.force) {
      return;
    }

    try {
      if (_abortCtl) _abortCtl.abort();
    } catch {}

    const ctl = new AbortController();
    _abortCtl = ctl;
    const mySeq = ++_lastReqSeq;

    loading.value = true;
    error.value = "";

    const preAtRightEdge =
      settings.getAtRightEdge(code.value, freq.value) || false;
    const prevRightTs = rightTs.value;

    try {
      const data = await fetchCandles(params, { signal: ctl.signal });

      if (mySeq !== _lastReqSeq || ctl !== _abortCtl) {
        return;
      }

      meta.value = data.meta || {};
      candles.value = data.candles || [];
      indicators.value = data.indicators || [];

      const allRowsNow = Number(meta.value?.all_rows || 0);
      const viewRows = Number(meta.value?.view_rows || 0);
      displayBars.value = viewRows || displayBars.value;
      visibleRange.value = {
        startStr: meta.value.start || visibleRange.value.startStr || "",
        endStr: meta.value.end || visibleRange.value.endStr || "",
      };

      // —— 落地后设置数据集边界（中枢：触底保持/越界夹取，仅修正 rightTs，不改 bars） —— //
      const minTs = candles.value?.[0]?.t
        ? Date.parse(candles.value[0].t)
        : undefined;
      const maxTs = candles.value?.[allRowsNow - 1]?.t
        ? Date.parse(candles.value[allRowsNow - 1].t)
        : undefined;
      hub.setDatasetBounds({ minTs, maxTs, totalRows: allRowsNow });

      settings.setFreq(freq.value);
      _lastAppliedKey = key;
    } catch (e) {
      const msg = String(e?.message || "");
      const isAbort =
        e?.name === "CanceledError" ||
        e?.code === "ERR_CANCELED" ||
        e?.name === "AbortError" ||
        msg.toLowerCase().includes("canceled") ||
        msg.toLowerCase().includes("aborted");
      if (isAbort) return;
      error.value = e?.message || "请求失败";
    } finally {
      if (mySeq === _lastReqSeq && ctl === _abortCtl) {
        loading.value = false;
      }
    }
  }

  // 交互 API（保持签名；内部委派中枢）
  function setFreq(newFreq) {
    if (!newFreq || newFreq === freq.value) return;
    freq.value = newFreq;
    settings.setFreq(newFreq);
    const st = hub.getState();
    hub.execute("ChangeFreq", { freq: newFreq, allRows: st.allRows }); // bars=查表，右端不变
    reload({
      force: true,
      window_preset: windowPreset.value,
      anchor_ts: st.rightTs,
    });
  }
  async function applyPreset(preset) {
    const p = String(preset || "ALL");
    windowPreset.value = p;
    settings.setWindowPreset(p);
    const st = hub.getState();
    hub.execute("ChangeWidthPreset", { presetKey: p, allRows: st.allRows }); // bars=查表，右端不变
    await reload({ force: true, window_preset: p, anchor_ts: st.rightTs });
  }
  async function setBars(bars, anchorTs) {
    const b = Math.max(1, Math.floor(Number(bars || 1)));
    const a = Number.isFinite(+anchorTs)
      ? Math.floor(+anchorTs)
      : rightTs.value ?? undefined;
    hub.execute("SetBarsManual", { nextBars: b });
  }
  function zoomIn() {
    const v = Number(meta.value?.view_rows || 0) || 1;
    setBars(Math.ceil(v / 1.2), rightTs.value);
  }
  function zoomOut() {
    const v = Number(meta.value?.view_rows || 0) || 1;
    setBars(Math.ceil(v * 1.2), rightTs.value);
  }

  // 初始化（保持原逻辑）
  watch(code, (v) => {
    settings.setLastSymbol(v || "");
    hub.execute("ChangeSymbol", { symbol: String(v || "") });
    if (autoStart) reload({ force: true });
  });
  watch(adjust, () => {
    // setAdjust 由 useUserSettings 内部的 watch 自动处理
    if (autoStart) reload({ force: true });
  });

  hub.initFromPersist(code.value, freq.value);
  if (autoStart) {
    reload({ force: true });
  }

  // 导出（保持签名）
  return {
    code,
    freq,
    adjust,
    chartType,
    loading,
    error,
    meta,
    candles,
    indicators,
    windowPreset,
    rightTs,
    visibleRange,
    displayBars,
    previewView,
    setFreq,
    applyPreset,
    setBars,
    zoomIn,
    zoomOut,
    reload,
    applyLocalZoom,
    get viewStartIdx() {
      return Number(meta.value?.view_start_idx ?? 0);
    },
    get viewEndIdx() {
      return Number(meta.value?.view_end_idx ?? -1);
    },
    get allRows() {
      return Number(meta.value?.all_rows ?? 0);
    },
    get viewRows() {
      return Number(meta.value?.view_rows ?? 0);
    },
  };
}