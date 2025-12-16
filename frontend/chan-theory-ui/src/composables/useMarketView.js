// src/composables/useMarketView.js
// ==============================
// V17.1 - Task/Job 一致版（K+因子+档案）
//
// 核心职责：
//   - 根据 code/freq/adjust 驱动 K 线、因子、指标与档案(profile)的加载；
//   - 统一通过 ensure-data 声明 Task：current_kline/current_factors/current_profile；
//   - 通过 waitTasksDone 等待完成后，调用各自的快照接口：
//       * /api/candles         ← current_kline
//       * /api/factors         ← current_factors
//       * /api/profile/current ← current_profile
//
// 本次主要改动：
//   1. reload(opts) 支持 with_profile 标志：
//       - true  时：声明 current_kline + current_factors + current_profile，
//                  等 k/factors 完成后拉 K+因子，再等 profile 完成后拉档案快照；
//       - false 时：只声明/等待 current_kline + current_factors。
//   2. watch(adjust) 由“纯本地复权重算”改为调用 reload({with_profile:false})，
//      即改复权也会重新走 K+因子快照（stock 继续本地推算复权价，fund 直接用 K 线，不改原算法）。
//   3. 新增 profile ref（单 symbol 档案快照），由 reload(with_profile=true) 时更新。
//   4. code 变化时的 watch 不再受 autoStart 影响，任何标的切换都会触发一次 reload({with_profile:true})。
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
import { useEventStream } from "@/composables/useEventStream";
import { useViewRenderHub } from "@/composables/useViewRenderHub";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { fetchProfile } from "@/services/profileService";

let _abortCtl = null;
let _lastReqSeq = 0;

const hub = useViewCommandHub();
const eventStream = useEventStream();

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
  const profile = ref(null);           // 当前标的档案快照

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
    } catch {}
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
        const majorTaskIds = []; // current_kline + current_factors
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
            console.error(`${ts()} [MarketView] declare-current_profile-failed`, e);
            // 档案任务失败不影响 K+因子主流程
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
        const [candlesRes, factorsRes] = await Promise.all([
          fetchCandles(currentSymbol, currentFreq, {
            signal: ctl.signal,
            adjust: currentAdjust,
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
          // 标的类型判定：通过 symbol_index 的 class 字段（stock/fund/...）
          const entry = findBySymbol(currentSymbol);
          const cls = String(entry?.class || "").toLowerCase();
          const isStock = cls === "stock";

          const wantAdjust = String(currentAdjust || "none");

          let finalCandles = [];

          if (isStock) {
            // === 股票：前端负责复权计算（沿用原逻辑）===
            if (wantAdjust === "none") {
              // 不复权：直接使用原始 K 线
              finalCandles = rawCandles.value;
            } else {
              // 需要前/后复权：必须有因子
              const hasFactors =
                Array.isArray(factors.value) && factors.value.length > 0;

              if (!hasFactors) {
                // 无因子却要求复权 → 视为无法计算，清空数据并标红提示
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
            // === 非股票（如基金）：前端不再做复权运算，直接使用后端返回的价格 ===
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
            // 档案读取失败不阻断 K 线展示
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
    } finally {
      if (mySeq === _lastReqSeq && ctl === _abortCtl) {
        loading.value = false;
      }
    }
  }

  // ===== 复权方式变化 → 重新请求 K+因子，再按原逻辑本地复权/不复权 =====
  watch(adjust, () => {
    if (!code.value) return;
    // 改复权视为一次“主动刷新视图数据”，但不需要档案任务
    reload({ force_refresh: false, with_profile: false });
  });

  // ===== 指标开关变化（MACD/KDJ/RSI/BOLL） → 仅重算指标，不重拉数据 =====
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

  // ===== 标的变化 → 自动加载（K+因子+档案），不再受 autoStart 控制 =====
  watch(code, (newCode) => {
    settings.setLastSymbol(newCode || "");
    hub.execute("ChangeSymbol", { symbol: String(newCode || "") });
    // 任何一次 code 变化都视为“主动改标的动作”，必须触发一组完整任务
    reload({ force_refresh: false, with_profile: true });
  });

  // ===== 视图状态变化 → 更新 displayBars =====
  hub.onChange((st) => {
    displayBars.value = Math.max(1, Number(st.barsCount || 1));
  });

  hub.initFromPersist(code.value, freq.value);
  if (autoStart) {
    // 若上层未显式调用 reload，这里可以作为兜底。
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

    // 改频率：仅需要 K+因子，不需要档案任务
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