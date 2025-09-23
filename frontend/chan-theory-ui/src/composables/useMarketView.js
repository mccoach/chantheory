/* E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useMarketView.js */
/* ============================== */
/* 覆盖式防抖（Abort + reqId）+ 缩放后自动高亮窗宽（pickPresetByBarsCountDown）
 * 新增：
 *  - displayBars：用于“随交互即时显示”的 bars 数（不等待回包）。
 *  - previewView(bars, anchorTs, sIdx, eIdx)：交互发生时立即刷新并持久化起止/根数。
 *  - 可配置 autoStart（默认 true）：未探活前可设为 false，避免首刷超时。
 */
import { ref, watch, computed } from "vue";
import { fetchCandles } from "@/services/marketService";
import { useUserSettings } from "@/composables/useUserSettings";
import { pickPresetByBarsCountDown } from "@/constants";

// 模块私有：管理“仅保留最新请求”
let _abortCtl = null; // 当前在途请求的 AbortController
let _lastReqSeq = 0; // 递增的请求序号（最新为基准）
let _lastAppliedKey = ""; // 可选：用于避免重复提交完全相同参数（轻量去重）

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
  const autoStart = options?.autoStart !== false; // 默认 true

  const settings = useUserSettings();

  // —— 核心可持久化状态 —— //
  const code = ref(settings.lastSymbol.value || "");
  const freq = ref(settings.freq?.value || "1d");
  const adjust = settings.adjust; // none|qfq|hfq
  const windowPreset = ref(settings.windowPreset.value || "ALL");
  const rightTs = ref(settings.getRightTs(code.value, freq.value) || null);

  // —— 数据与元信息 —— //
  const loading = ref(false);
  const error = ref("");
  const meta = ref(null);
  const candles = ref([]);
  const indicators = ref({});

  // —— 展示辅助 —— //
  const chartType = ref(settings.chartType?.value || "kline");
  // 注意：visibleRange 现在既用于回包落地，也用于“预览态”（previewView 即时更新）
  const visibleRange = ref({ startStr: "", endStr: "" });
  // 新增：随交互即时 bars 显示（预览态）
  const displayBars = ref(0);

  const maPeriodsMap = computed(() => {
    const configs = settings.maConfigs.value || {};
    return Object.entries(configs)
      .filter(([, conf]) => conf && conf.enabled)
      .reduce((acc, [key, conf]) => {
        acc[key] = conf.period;
        return acc;
      }, {});
  });
  function buildIncludeParam() {
    const arr = ["vol"];
    const mc = Object.keys(maPeriodsMap.value);
    if (mc.length > 0) arr.push("ma");
    if (settings.useMACD.value) arr.push("macd");
    if (settings.useKDJ.value) arr.push("kdj");
    if (settings.useRSI.value) arr.push("rsi");
    if (settings.useBOLL.value) arr.push("boll");
    return arr.join(",");
  }

  // —— 预览态：随交互即时刷新起止/根数并持久化 —— //
  function previewView(bars, anchorTs, sIdx, eIdx) {
    // 立即更新显示的 bars
    const b = Math.max(1, Math.floor(Number(bars || 1)));
    displayBars.value = b;

    // 立即持久化“缩放根数与右端锚点”
    try {
      settings.setViewBars(code.value, freq.value, b);
      if (Number.isFinite(+anchorTs)) {
        rightTs.value = Math.floor(+anchorTs);
        settings.setRightTs(code.value, freq.value, rightTs.value);
      }
    } catch {}

    // 立即刷新前端“起止时间文案”（不等待回包）
    try {
      const arr = candles.value || [];
      const n = arr.length;
      // sIdx/eIdx 由交互处传入（更准），否则根据 anchor/bars 用当前 ALL 序列估算
      let si = Number.isFinite(+sIdx)
        ? Math.max(0, Math.min(n - 1, +sIdx))
        : null;
      let ei = Number.isFinite(+eIdx)
        ? Math.max(0, Math.min(n - 1, +eIdx))
        : null;

      if (si == null || ei == null) {
        // 根据 anchorTs/bars 推导
        if (n > 0) {
          let endIndex = n - 1;
          const aTs = Number.isFinite(+anchorTs) ? +anchorTs : rightTs.value;
          if (Number.isFinite(+aTs)) {
            for (let i = n - 1; i >= 0; i--) {
              const t = Date.parse(arr[i]?.t || "");
              if (Number.isFinite(t) && t <= aTs) {
                endIndex = i;
                break;
              }
            }
          }
          const startIndex = Math.max(0, endIndex - b + 1);
          si = startIndex;
          ei = endIndex;
        }
      }

      const sStr =
        Number.isFinite(+si) && arr[si]?.t
          ? String(arr[si].t)
          : visibleRange.value.startStr;
      const eStr =
        Number.isFinite(+ei) && arr[ei]?.t
          ? String(arr[ei].t)
          : visibleRange.value.endStr;

      visibleRange.value = { startStr: sStr || "", endStr: eStr || "" };
    } catch {
      // 容错：不阻断交互
    }
  }

  // —— 统一加载（服务端一次成型 + 覆盖式防抖） —— //
  async function reload(opts = {}) {
    if (!code.value) return;

    const params = {
      code: code.value,
      freq: freq.value,
      adjust: adjust.value,
      include: buildIncludeParam(),
      ma_periods: JSON.stringify(maPeriodsMap.value || {}),
      window_preset: opts.window_preset ?? windowPreset.value,
      bars: Number.isFinite(+opts.bars)
        ? Math.max(1, Math.floor(+opts.bars))
        : undefined,
      anchor_ts: Number.isFinite(+opts.anchor_ts)
        ? Math.floor(+opts.anchor_ts)
        : rightTs.value ?? undefined,
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

    try {
      const data = await fetchCandles(params, { signal: ctl.signal });

      if (mySeq !== _lastReqSeq || ctl !== _abortCtl) {
        return;
      }

      meta.value = data.meta || {};
      candles.value = data.candles || [];
      indicators.value = data.indicators || [];

      // 回包落地：更新“最终可见窗口文案与 bars”
      const allRows = Number(meta.value?.all_rows || 0);
      const viewRows = Number(meta.value?.view_rows || 0);
      displayBars.value = viewRows || displayBars.value; // 回包覆盖预览值（若有）
      visibleRange.value = {
        startStr: meta.value.start || visibleRange.value.startStr || "",
        endStr: meta.value.end || visibleRange.value.endStr || "",
      };

      // 右端锚点持久化：优先使用参数 anchor_ts，否则用回包 end
      if (params.anchor_ts != null) {
        rightTs.value = params.anchor_ts;
      } else if (meta.value.end) {
        const endMs = Date.parse(meta.value.end);
        if (!Number.isNaN(endMs)) rightTs.value = endMs;
      }

      // 自动高亮窗宽（仅当 bars 缩放触发时）
      let nextPreset = String(
        meta.value.window_preset_effective || windowPreset.value || "ALL"
      );
      if (Number.isFinite(+opts.bars)) {
        if (allRows > 0 && viewRows >= allRows) {
          nextPreset = "ALL";
        } else if (allRows > 0 && viewRows > 0) {
          nextPreset = pickPresetByBarsCountDown(freq.value, viewRows, allRows);
        }
      }
      windowPreset.value = nextPreset;
      settings.setWindowPreset(nextPreset);

      settings.setFreq(freq.value);
      if (rightTs.value != null)
        settings.setRightTs(code.value, freq.value, rightTs.value);

      // 记住已生效参数键（去重基准）
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

  // —— 交互 API —— //
  function setFreq(newFreq) {
    if (!newFreq || newFreq === freq.value) return;
    freq.value = newFreq;
    settings.setFreq(newFreq);
    reload({
      force: true,
      window_preset: windowPreset.value,
      anchor_ts: rightTs.value,
    });
  }
  async function applyPreset(preset) {
    const p = String(preset || "ALL");
    windowPreset.value = p;
    settings.setWindowPreset(p);
    await reload({ force: true, window_preset: p, anchor_ts: rightTs.value });
  }
  async function setBars(bars, anchorTs) {
    const b = Math.max(1, Math.floor(Number(bars || 1)));
    const a = Number.isFinite(+anchorTs)
      ? Math.floor(+anchorTs)
      : rightTs.value ?? undefined;
    await reload({ force: true, bars: b, anchor_ts: a });
  }
  function zoomIn() {
    const v = Number(meta.value?.view_rows || 0) || 1;
    setBars(Math.ceil(v / 1.2), rightTs.value);
  }
  function zoomOut() {
    const v = Number(meta.value?.view_rows || 0) || 1;
    setBars(Math.ceil(v * 1.2), rightTs.value);
  }

  // —— 初始化 —— //
  watch(code, (v) => {
    settings.setLastSymbol(v || "");
    if (autoStart) reload({ force: true });
  });
  watch(adjust, () => {
    settings.setAdjust?.(adjust.value);
    if (autoStart) reload({ force: true });
  });

  if (autoStart) {
    reload({ force: true });
  }

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
    displayBars, // 新增：用于 SymbolPanel 实时显示 bars
    previewView, // 新增：供交互时即时刷新
    setFreq,
    applyPreset,
    setBars,
    zoomIn,
    zoomOut,
    reload,
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
