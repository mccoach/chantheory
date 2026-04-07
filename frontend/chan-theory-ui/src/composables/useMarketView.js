// src/composables/useMarketView.js
// ==============================
// V25.0 - candles 唯一正式入口版
//
// 当前职责：
//   - 直接读取后端 /api/candles 最终结果
//   - 不再拉 factors
//   - 不再做前端复权
//   - 不再等待 current_kline/current_factors
//   - 基于最终 candles 做前端指标计算与页面状态更新
// ==============================

import { ref, watch, computed } from "vue";
import { fetchCandles } from "@/services/marketService";
import { computeIndicators } from "@/composables/engines/indicators";
import { useUserSettings } from "@/composables/useUserSettings";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/viewRenderHub";
import { fetchProfile } from "@/services/profileService";

let _abortCtl = null;
let _lastReqSeq = 0;

const hub = useViewCommandHub();

function ts() {
  return new Date().toISOString();
}

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function asMarket(x) {
  return asStr(x).toUpperCase();
}

function normalizeIdentity(input = {}) {
  return {
    symbol: asStr(input.symbol),
    market: asMarket(input.market),
  };
}

function isValidIdentity(input = {}) {
  const id = normalizeIdentity(input);
  return !!(id.symbol && id.market);
}

function normalizeRefreshInterval(v) {
  if (v == null || v === "") return null;
  const n = Number(v);
  if (!Number.isFinite(n)) return null;
  const i = Math.floor(n);
  return i >= 1 ? i : null;
}

export function useMarketView(options = {}) {
  const autoStart = options?.autoStart !== false;
  const settings = useUserSettings();
  const renderHub = useViewRenderHub();

  const initialIdentity = settings.getLastSymbolIdentity
    ? settings.getLastSymbolIdentity()
    : {
        symbol: settings.preferences.lastSymbol || "",
        market: settings.preferences.lastMarket || "",
      };

  const normalizedInitialIdentity = normalizeIdentity(initialIdentity);

  const code = ref(normalizedInitialIdentity.symbol);
  const market = ref(normalizedInitialIdentity.market);

  const freq = ref(settings.preferences.freq || "1d");
  const adjust = ref(settings.preferences.adjust || "none");

  const loading = ref(false);
  const error = ref("");
  const meta = ref(null);
  const candles = ref([]);
  const indicators = ref({});
  const profile = ref(null);

  const chartType = ref(settings.preferences.chartType || "kline");
  const visibleRange = ref({ startStr: "", endStr: "" });
  const displayBars = ref(0);

  const autoRefreshEnabled = computed(
    () => settings.preferences.autoRefreshEnabled === true
  );
  const refreshIntervalSeconds = computed(() =>
    autoRefreshEnabled.value
      ? normalizeRefreshInterval(settings.preferences.refreshIntervalSeconds)
      : null
  );

  const indicatorConfig = computed(() => ({
    maPeriodsMap: (() => {
      const configs = settings.chartDisplay.maConfigs || {};
      return Object.entries(configs).reduce((acc, [key, conf]) => {
        const n = Number(conf?.period);
        if (Number.isFinite(n) && n > 0) acc[key] = n;
        return acc;
      }, {});
    })(),
    maConfigs: settings.chartDisplay.maConfigs,
    useMACD: settings.preferences.useMACD,
    useKDJ: settings.preferences.useKDJ,
    useRSI: settings.preferences.useRSI,
    useBOLL: settings.preferences.useBOLL,
    macdSettings: settings.chartDisplay.macdSettings,
    atrStopSettings: settings.chartDisplay.atrStopSettings,
    atrBasePrice: settings.preferences.atrBasePrice,
  }));

  function isLatestRequest(reqSeq) {
    return reqSeq === _lastReqSeq;
  }

  async function reload(opts = {}) {
    const identity = normalizeIdentity({
      symbol: code.value,
      market: market.value,
    });

    if (!isValidIdentity(identity)) return;

    const currentSymbol = identity.symbol;
    const currentMarket = identity.market;
    const currentFreq = freq.value;
    const currentAdjust = adjust.value;
    const withProfile = opts.with_profile === true;

    try {
      if (_abortCtl) _abortCtl.abort();
    } catch {}

    const ctl = new AbortController();
    _abortCtl = ctl;
    const mySeq = ++_lastReqSeq;

    loading.value = true;
    error.value = "";

    try {
      await renderHub._executeBatch(async () => {
        const candlesRes = await fetchCandles(
          currentSymbol,
          currentMarket,
          currentFreq,
          {
            signal: ctl.signal,
            adjust: currentAdjust,
            refreshIntervalSeconds: refreshIntervalSeconds.value,
          }
        );

        if (!isLatestRequest(mySeq) || ctl.signal.aborted) {
          return;
        }

        const metaRaw = candlesRes.meta || {};
        const hasGap = metaRaw.has_gap === true;
        const gapMessage =
          metaRaw.gap_message == null ? "" : String(metaRaw.gap_message);
        const actualAdjust =
          metaRaw.actual_adjust == null
            ? String(currentAdjust || "none")
            : String(metaRaw.actual_adjust || "none");

        meta.value = {
          ...metaRaw,
          has_gap: hasGap,
          gap_message: gapMessage,
          actual_adjust: actualAdjust,
          completeness: hasGap ? "incomplete" : "complete",
        };

        const finalCandles = Array.isArray(candlesRes.candles)
          ? candlesRes.candles
          : [];

        candles.value = finalCandles;
        indicators.value = computeIndicators(finalCandles, indicatorConfig.value);

        if (finalCandles.length > 0) {
          const allRows = finalCandles.length;
          const minTs = finalCandles[0]?.ts;
          const maxTs = finalCandles[allRows - 1]?.ts;
          hub.setDatasetBounds({ minTs, maxTs, totalRows: allRows });

          visibleRange.value = {
            startStr: meta.value.start || "",
            endStr: meta.value.end || "",
          };
          displayBars.value = meta.value.view_rows || 0;

          error.value = "";

          console.log(
            `${ts()} [MarketView] load-ok symbol=${currentSymbol} market=${currentMarket} freq=${currentFreq} rows=${allRows} has_gap=${hasGap} actual_adjust=${actualAdjust}`
          );
        } else {
          hub.setDatasetBounds({ minTs: null, maxTs: null, totalRows: 0 });
          visibleRange.value = { startStr: "", endStr: "" };
          displayBars.value = 0;
          error.value = "暂无数据";
        }

        settings.setFreq(freq.value);

        if (withProfile) {
          try {
            const pf = await fetchProfile(currentSymbol, currentMarket);
            if (!isLatestRequest(mySeq) || ctl.signal.aborted) {
              return;
            }
            profile.value = pf || null;
          } catch (e) {
            console.error(`${ts()} [MarketView] load-profile-failed`, e);
            profile.value = null;
          }
        }
      });
    } catch (e) {
      const msg = String(e?.message || "");
      const isCanceled =
        e?.name === "CanceledError" ||
        e?.code === "ERR_CANCELED" ||
        e?.name === "AbortError" ||
        msg.toLowerCase().includes("canceled") ||
        msg.toLowerCase().includes("aborted");

      if (isCanceled) {
        return;
      }

      const isTimeout = msg.includes("超时");
      error.value = isTimeout ? "数据拉取超时" : e?.message || "请求失败";
      candles.value = [];
      indicators.value = {};
      console.error(`${ts()} [MarketView] load-failed`, e);

      meta.value = {
        ...(meta.value || {}),
        has_gap: true,
        gap_message: error.value,
        completeness: "incomplete",
      };
      profile.value = null;
      hub.setDatasetBounds({ minTs: null, maxTs: null, totalRows: 0 });
    } finally {
      if (mySeq === _lastReqSeq && ctl === _abortCtl) {
        loading.value = false;
      }
    }
  }

  watch(
    indicatorConfig,
    () => {
      if (!candles.value.length) return;
      indicators.value = computeIndicators(
        candles.value,
        indicatorConfig.value
      );
    },
    { deep: true }
  );

  watch(
    [code, market],
    ([newCode, newMarket]) => {
      const identity = normalizeIdentity({
        symbol: newCode,
        market: newMarket,
      });

      if (!isValidIdentity(identity)) return;

      settings.setLastSymbolIdentity({
        symbol: identity.symbol,
        market: identity.market,
      });
      settings.setAtrBasePrice(null);

      hub.execute("ChangeSymbol", {
        symbol: identity.symbol,
        market: identity.market,
      });
    }
  );

  hub.onChange((st) => {
    displayBars.value = Math.max(1, Number(st.barsCount || 1));
  });

  hub.initFromPersist(code.value, market.value, freq.value);

  if (autoStart) {
    reload({ with_profile: true });
  }

  function setSymbolIdentity(input = {}) {
    const identity = normalizeIdentity(input);
    if (!isValidIdentity(identity)) return;

    code.value = identity.symbol;
    market.value = identity.market;
  }

  function setFreq(newFreq) {
    if (!newFreq || newFreq === freq.value) return;

    freq.value = newFreq;
    settings.setFreq(newFreq);

    hub.execute("ChangeFreq", {
      freq: newFreq,
      allRows: candles.value.length,
    });
  }

  function setAdjust(newAdjust) {
    const next = String(newAdjust || "none");
    if (next === adjust.value) return;
    adjust.value = next;
    settings.setAdjust(next);
  }

  function applyPreset(preset) {
    const p = String(preset || "ALL");
    settings.setWindowPreset?.(p);
    const st = hub.getState();
    hub.execute("ChangeWidthPreset", { presetKey: p, allRows: st.allRows });
  }

  function setBars(bars) {
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

  return {
    code,
    market,
    freq,
    adjust,
    chartType,
    loading,
    error,
    meta,
    candles,
    indicators,
    profile,
    visibleRange,
    displayBars,
    autoRefreshEnabled,
    refreshIntervalSeconds,
    setSymbolIdentity,
    setFreq,
    setAdjust,
    applyPreset,
    setBars,
    zoomIn,
    zoomOut,
    reload,
    get allRows() {
      return Number(meta.value?.all_rows ?? 0);
    },
  };
}
