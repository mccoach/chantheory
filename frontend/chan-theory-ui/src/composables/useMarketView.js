// src/composables/useMarketView.js
// ==============================
// V24.0 - useMarketView 收敛为纯业务执行器
//
// 当前职责：
//   - 读取后端当前标的结果
//   - 应用复权
//   - 计算指标
//   - 更新页面状态
//
// 命令权收敛：
//   - 不再自行 declareCurrentKline / declareCurrentFactors
//   - 不再自行 waitTasksDone
//   - 命令由 useCurrentSymbolData 在启动链/页面交互中显式发出
// ==============================

import { ref, watch, computed } from "vue";
import { fetchCandles } from "@/services/marketService";
import { fetchFactors } from "@/services/factorsAPI";
import { computeIndicators } from "@/composables/engines/indicators";
import { applyAdjustment } from "@/composables/engines/adjustment";
import { useUserSettings } from "@/composables/useUserSettings";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useViewRenderHub } from "@/composables/viewRenderHub";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
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

export function useMarketView(options = {}) {
  const autoStart = options?.autoStart !== false;
  const settings = useUserSettings();
  const renderHub = useViewRenderHub();
  const symbolIndex = useSymbolIndex();

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
  const rawCandles = ref([]);
  const factors = ref([]);
  const indicators = ref({});
  const profile = ref(null);

  const chartType = ref(settings.preferences.chartType || "kline");
  const visibleRange = ref({ startStr: "", endStr: "" });
  const displayBars = ref(0);

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

    const entry = symbolIndex.findBySymbol(currentSymbol, currentMarket);
    const cls = String(entry?.class || "").toLowerCase();
    const isStock = cls === "stock";

    const requestAdjust = isStock ? "none" : String(currentAdjust || "none");
    const shouldFetchFactors = isStock;

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
        const [candlesRes, factorsRes] = await Promise.all([
          fetchCandles(currentSymbol, currentFreq, {
            signal: ctl.signal,
            adjust: requestAdjust,
          }),
          shouldFetchFactors ? fetchFactors(currentSymbol) : Promise.resolve([]),
        ]);

        if (!isLatestRequest(mySeq) || ctl.signal.aborted) {
          return;
        }

        const metaRaw = candlesRes.meta || {};
        const completeness =
          metaRaw.is_latest === true ? "complete" : "incomplete";

        meta.value = {
          ...metaRaw,
          completeness,
        };

        rawCandles.value = candlesRes.candles || [];
        factors.value = Array.isArray(factorsRes) ? factorsRes : [];

        if (candlesRes.meta.all_rows > 0) {
          const wantAdjust = String(currentAdjust || "none");

          let finalCandles = [];

          if (isStock) {
            if (wantAdjust === "none") {
              finalCandles = rawCandles.value;
            } else {
              const hasFactors =
                Array.isArray(factors.value) && factors.value.length > 0;

              if (!hasFactors) {
                candles.value = [];
                indicators.value = {};
                error.value = "复权因子缺失，无法计算复权价格";
                meta.value = {
                  ...(meta.value || {}),
                  completeness: "incomplete",
                };
                return;
              }

              finalCandles = applyAdjustment(
                rawCandles.value,
                factors.value,
                wantAdjust
              );
            }
          } else {
            finalCandles = rawCandles.value;
          }

          candles.value = finalCandles;
          indicators.value = computeIndicators(
            finalCandles,
            indicatorConfig.value
          );

          const allRows = finalCandles.length;
          const minTs = finalCandles[0]?.ts;
          const maxTs = finalCandles[allRows - 1]?.ts;
          hub.setDatasetBounds({ minTs, maxTs, totalRows: allRows });

          error.value = "";
          console.log(
            `${ts()} [MarketView] load-ok symbol=${currentSymbol} market=${currentMarket} freq=${currentFreq} rows=${allRows}`
          );
        } else {
          candles.value = [];
          indicators.value = {};
          error.value = "暂无数据";
        }

        visibleRange.value = {
          startStr: meta.value.start || "",
          endStr: meta.value.end || "",
        };
        displayBars.value = meta.value.view_rows || 0;

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
        completeness: "incomplete",
      };
      profile.value = null;
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
    rawCandles,
    factors,
    indicators,
    profile,
    visibleRange,
    displayBars,
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
