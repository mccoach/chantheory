// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\settings\preferences.js
// ==============================
// 设置子模块：应用偏好与历史记录
// V3.1 改动：
//   - 修复 setAtrBasePrice 对 null/空串 的处理（避免 Number(null)===0 导致误判）
// ==============================

import { reactive } from "vue";
import { DEFAULT_APP_PREFERENCES, SYMBOL_HISTORY_MAX, ATR_BASE_PRICE_HISTORY_MAX } from "@/constants";

export function createPreferencesState(localData = {}) {
  const state = reactive({
    lastSymbol: localData.lastSymbol || "",
    lastStart: localData.lastStart || "",
    lastEnd: localData.lastEnd || "",
    hotkeyOverrides: localData.hotkeyOverrides || {},
    chartType: localData.chartType || DEFAULT_APP_PREFERENCES.chartType,
    freq: localData.freq || DEFAULT_APP_PREFERENCES.freq,
    adjust: localData.adjust || DEFAULT_APP_PREFERENCES.adjust,
    useMACD:
      typeof localData.useMACD === "boolean"
        ? localData.useMACD
        : DEFAULT_APP_PREFERENCES.useMACD,
    useKDJ:
      typeof localData.useKDJ === "boolean"
        ? localData.useKDJ
        : DEFAULT_APP_PREFERENCES.useKDJ,
    useRSI:
      typeof localData.useRSI === "boolean"
        ? localData.useRSI
        : DEFAULT_APP_PREFERENCES.useRSI,
    useBOLL:
      typeof localData.useBOLL === "boolean"
        ? localData.useBOLL
        : DEFAULT_APP_PREFERENCES.useBOLL,
    styleOverrides: localData.styleOverrides || {},
    indicatorPanes: Array.isArray(localData.indicatorPanes)
      ? localData.indicatorPanes.map((x) => ({
          kind: String(x?.kind || "MACD"),
        }))
      : [],
    symbolHistory: Array.isArray(localData.symbolHistory)
      ? localData.symbolHistory.filter(
          (x) => x && typeof x.symbol === "string" && Number.isFinite(+x.ts)
        )
      : [],

    panelHeights:
      localData.panelHeights && typeof localData.panelHeights === "object"
        ? localData.panelHeights
        : {},

    atrBasePrice:
      localData.atrBasePrice != null && Number.isFinite(+localData.atrBasePrice)
        ? +localData.atrBasePrice
        : null,
    atrBasePriceHistory: Array.isArray(localData.atrBasePriceHistory)
      ? localData.atrBasePriceHistory
          .map((x) => Number(x))
          .filter((n) => Number.isFinite(n))
      : [],
  });

  const setters = {
    setLastSymbol: (s) => (state.lastSymbol = String(s || "")),
    setLastStart: (s) => (state.lastStart = String(s || "")),
    setLastEnd: (s) => (state.lastEnd = String(s || "")),
    setHotkeyOverrides: (o) => (state.hotkeyOverrides = o || {}),
    setFreq: (f) => (state.freq = f || DEFAULT_APP_PREFERENCES.freq),
    setAdjust: (adj) => (state.adjust = adj || DEFAULT_APP_PREFERENCES.adjust),
    setChartType: (t) =>
      (state.chartType = t || DEFAULT_APP_PREFERENCES.chartType),
    setUseMACD: (v) => (state.useMACD = !!v),
    setUseKDJ: (v) => (state.useKDJ = !!v),
    setUseRSI: (v) => (state.useRSI = !!v),
    setUseBOLL: (v) => (state.useBOLL = !!v),
    setStyleOverrides: (o) => (state.styleOverrides = o || {}),
    updateStyleOverride: (chartKey, seriesName, patch) => {
      const ck = String(chartKey || ""),
        sn = String(seriesName || "");
      if (!ck || !sn) return;
      const group = { ...(state.styleOverrides[ck] || {}) };
      group[sn] = { ...(group[sn] || {}), ...(patch || {}) };
      state.styleOverrides = { ...state.styleOverrides, [ck]: group };
    },
    resetStyleOverride: (chartKey, seriesName) => {
      const ck = String(chartKey || ""),
        sn = String(seriesName || "");
      if (!ck || !sn) return;
      const group = { ...(state.styleOverrides[ck] || {}) };
      delete group[sn];
      state.styleOverrides = { ...state.styleOverrides, [ck]: group };
    },
    setIndicatorPanes: (arr) => {
      state.indicatorPanes = Array.isArray(arr)
        ? arr.map((x) => ({ kind: String(x?.kind || "MACD") }))
        : [];
    },
    addSymbolHistoryEntry: (symbol) => {
      const sym = String(symbol || "").trim();
      if (!sym) return;
      const nowTs = Date.now();
      const list = Array.isArray(state.symbolHistory)
        ? state.symbolHistory.slice()
        : [];
      const idx = list.findIndex((x) => String(x.symbol || "") === sym);
      if (idx >= 0) list.splice(idx, 1);
      list.unshift({ symbol: sym, ts: nowTs });
      state.symbolHistory = list.slice(0, Math.max(1, Number(SYMBOL_HISTORY_MAX || 200)));
    },
    getSymbolHistoryList: () => {
      const list = Array.isArray(state.symbolHistory)
        ? state.symbolHistory.slice()
        : [];
      return list.sort((a, b) => Number(b.ts || 0) - Number(a.ts || 0));
    },

    setPanelHeight: (panelKey, px) => {
      const k = String(panelKey || "").trim();
      const n = Number(px);
      if (!k) return;
      if (!Number.isFinite(n) || n <= 0) {
        const next = { ...(state.panelHeights || {}) };
        delete next[k];
        state.panelHeights = next;
        return;
      }
      state.panelHeights = { ...(state.panelHeights || {}), [k]: Math.round(n) };
    },
    getPanelHeight: (panelKey) => {
      const k = String(panelKey || "").trim();
      if (!k) return null;
      const v = state.panelHeights?.[k];
      return Number.isFinite(+v) ? Math.round(+v) : null;
    },

    // ===== FIX: 对 null/空串 特判，避免 Number(null)===0 =====
    setAtrBasePrice: (v) => {
      if (v == null || v === "") {
        state.atrBasePrice = null;
      } else {
        const n = Number(v);
        state.atrBasePrice = Number.isFinite(n) ? n : null;
      }
    },

    // ===== NEW: ATR 基准价历史（类似标的历史）=====
    addAtrBasePriceHistoryEntry: (v) => {
      const n = Number(v);
      if (!Number.isFinite(n)) return;

      const list = Array.isArray(state.atrBasePriceHistory)
        ? state.atrBasePriceHistory.slice()
        : [];

      const i = list.findIndex((x) => Number(x) === n);
      if (i >= 0) list.splice(i, 1);
      list.unshift(n);

      state.atrBasePriceHistory = list.slice(
        0,
        Math.max(1, Number(ATR_BASE_PRICE_HISTORY_MAX || 50))
      );
    },

    getAtrBasePriceHistoryList: () => {
      const list = Array.isArray(state.atrBasePriceHistory)
        ? state.atrBasePriceHistory.slice()
        : [];
      return list.slice(0);
    },
  };

  const onStorage = (newLocal) => {
    Object.keys(state).forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(newLocal, key)) {
        state[key] = newLocal[key];
      }
    });
  };

  return { state, setters, onStorage };
}
