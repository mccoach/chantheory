// src/composables/useMarketView.js
// ==============================
// V17.5 - force_refresh 指令触发“仅一次”FULL（在数据落地后触发，避免重复 full）
//
// 变更说明（按你的最新条文）：
//   - 仅当实际动作指令为 reload(force_refresh=true) 时触发 FULL；
//   - FULL 仅触发一次：在 candles/indicators/meta（及可选 profile）落地后触发；
//   - 不绑定按钮/快捷键等用户行为；不影响 symbol_index 强制刷新；
//   - 若请求被取消/过期（seq 不匹配）则不触发 FULL。
// ==============================

import { ref, watch, computed, toRef } from "vue";
import { fetchCandles } from "@/services/marketService";
import {
  declareCurrentKline,
  declareCurrentFactors,
  declareCurrentProfile,
} from "@/services/ensureDataAPI";
import { waitTasksDone } from "@/composables/useTaskWaiter";
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

export function useMarketView(options = {}) {
  const autoStart = options?.autoStart !== false;
  const settings = useUserSettings();
  const renderHub = useViewRenderHub();
  const { findBySymbol } = useSymbolIndex();

  const code = ref(settings.preferences.lastSymbol || "");
  const freq = ref(settings.preferences.freq || "1d");
  const adjust = toRef(settings.preferences, "adjust");

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

  /**
   * 统一加载入口
   *
   * @param {object} opts
   * @param {boolean} [opts.force_refresh=false] - 是否强制刷新（force_fetch）
   * @param {boolean} [opts.with_profile=false] - 是否顺带触发/读取 current_profile
   */
  async function reload(opts = {}) {
    if (!code.value) return;

    const currentSymbol = code.value;
    const currentFreq = freq.value;
    const currentAdjust = adjust.value;
    const forceRefresh = !!opts.force_refresh;
    const withProfile = opts.with_profile === true;

    try {
      if (_abortCtl) _abortCtl.abort();
    } catch { }
    const ctl = new AbortController();
    _abortCtl = ctl;
    const mySeq = ++_lastReqSeq;

    loading.value = true;
    error.value = "";

    try {
      console.log(
        `${ts()} [MarketView] declare symbol=${currentSymbol} freq=${currentFreq} adjust=${currentAdjust} force=${forceRefresh} profile=${withProfile}`
      );

      await renderHub._executeBatch(async () => {
        // ===== Step 1: 声明 Task =====
        const majorTaskIds = [];
        let profileTaskId = null;

        try {
          const kTask = await declareCurrentKline({
            symbol: currentSymbol,
            freq: currentFreq,
            adjust: currentAdjust,
            force_fetch: forceRefresh,
          });
          if (kTask?.task_id) {
            majorTaskIds.push(String(kTask.task_id));
          }
        } catch (e) {
          console.error(`${ts()} [MarketView] declare-current_kline-failed`, e);
          throw e;
        }

        try {
          const fTask = await declareCurrentFactors({
            symbol: currentSymbol,
            force_fetch: forceRefresh,
          });
          if (fTask?.task_id) {
            majorTaskIds.push(String(fTask.task_id));
          }
        } catch (e) {
          console.error(`${ts()} [MarketView] declare-current_factors-failed`, e);
          throw e;
        }

        if (withProfile) {
          try {
            const pTask = await declareCurrentProfile({
              symbol: currentSymbol,
              force_fetch: forceRefresh,
            });
            if (pTask?.task_id) {
              profileTaskId = String(pTask.task_id);
            }
          } catch (e) {
            console.error(
              `${ts()} [MarketView] declare-current_profile-failed`,
              e
            );
          }
        }

        if (mySeq !== _lastReqSeq || ctl.signal.aborted) {
          return;
        }

        // ===== Step 2: 等待 K+因子任务完成 =====
        if (majorTaskIds.length) {
          await waitTasksDone({
            taskIds: majorTaskIds,
            timeoutMs: 30000,
          });

          if (mySeq !== _lastReqSeq || ctl.signal.aborted) {
            return;
          }
        }

        // ===== Step 3: 拉取业务数据（/api/candles + /api/factors）=====
        const entry = findBySymbol(currentSymbol);
        const cls = String(entry?.class || "").toLowerCase();
        const isStock = cls === "stock";

        const requestAdjust = isStock ? "none" : String(currentAdjust || "none");

        const [candlesRes, factorsRes] = await Promise.all([
          fetchCandles(currentSymbol, currentFreq, {
            signal: ctl.signal,
            adjust: requestAdjust,
          }),
          fetchFactors(currentSymbol),
        ]);

        if (mySeq !== _lastReqSeq || ctl.signal.aborted) {
          return;
        }

        // ===== Step 4: 更新 K 线 + 因子 + 指标 =====
        const metaRaw = candlesRes.meta || {};
        const completeness =
          metaRaw.is_latest === true ? "complete" : "incomplete";

        meta.value = {
          ...metaRaw,
          completeness,
        };

        rawCandles.value = candlesRes.candles || [];
        factors.value = factorsRes || [];

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

          indicators.value = computeIndicators(finalCandles, indicatorConfig.value);

          const allRows = finalCandles.length;
          const minTs = finalCandles[0]?.ts;
          const maxTs = finalCandles[allRows - 1]?.ts;
          hub.setDatasetBounds({ minTs, maxTs, totalRows: allRows });

          error.value = "";
          console.log(
            `${ts()} [MarketView] load-ok symbol=${currentSymbol} freq=${currentFreq} rows=${allRows}`
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

        // ===== Step 5: 若需要档案，等待 current_profile 完成并读取快照 =====
        if (withProfile && profileTaskId) {
          try {
            await waitTasksDone({
              taskIds: [profileTaskId],
              timeoutMs: 30000,
            });

            if (mySeq !== _lastReqSeq || ctl.signal.aborted) {
              return;
            }

            const pf = await fetchProfile(currentSymbol);
            if (mySeq !== _lastReqSeq || ctl.signal.aborted) {
              return;
            }
            profile.value = pf || null;
          } catch (e) {
            console.error(`${ts()} [MarketView] load-profile-failed`, e);
          }
        }
      });

      // ===== NEW: force_refresh 指令在数据落地后触发一次 FULL =====
      if (forceRefresh && mySeq === _lastReqSeq && !ctl.signal.aborted) {
        try {
          // 仅一次：此时 vm.candles/indicators 已经是最终状态（或已结束），full 计算不会重复。
          renderHub.requestRender({ intent: "force_full" });
        } catch {}
      }
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
    } finally {
      if (mySeq === _lastReqSeq && ctl === _abortCtl) {
        loading.value = false;
      }
    }
  }

  watch(adjust, () => {
    if (!code.value) return;
    reload({ force_refresh: false, with_profile: false });
  });

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

  watch(code, (newCode) => {
    settings.setLastSymbol(newCode || "");

    settings.setAtrBasePrice(null);

    hub.execute("ChangeSymbol", { symbol: String(newCode || "") });
    reload({ force_refresh: false, with_profile: true });
  });

  hub.onChange((st) => {
    displayBars.value = Math.max(1, Number(st.barsCount || 1));
  });

  hub.initFromPersist(code.value, freq.value);
  if (autoStart) {
    reload({ force_refresh: false, with_profile: true });
  }

  function setFreq(newFreq) {
    if (!newFreq || newFreq === freq.value) return;

    freq.value = newFreq;
    settings.setFreq(newFreq);

    hub.execute("ChangeFreq", {
      freq: newFreq,
      allRows: candles.value.length,
    });

    reload({ force_refresh: false, with_profile: false });
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
    setFreq,
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
