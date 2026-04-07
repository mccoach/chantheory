// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\settings\preferences.js
// ==============================
// 设置子模块：应用偏好与历史记录
//
// V5.0 - 行情实时刷新偏好收口
// 改动：
//   - 新增 autoRefreshEnabled
//   - 新增 refreshIntervalSeconds
//   - 统一使用 null 表示“静态查看/不自动刷新”
// ==============================

import { reactive } from "vue";
import {
  DEFAULT_APP_PREFERENCES,
  SYMBOL_HISTORY_MAX,
  ATR_BASE_PRICE_HISTORY_MAX,
} from "@/constants";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function normalizeRefreshInterval(v) {
  if (v == null || v === "") return null;
  const n = Number(v);
  if (!Number.isFinite(n)) return null;
  const i = Math.floor(n);
  return i >= 1 ? i : null;
}

export function createPreferencesState(localData = {}) {
  const state = reactive({
    lastSymbol: localData.lastSymbol || "",
    lastMarket: localData.lastMarket || "",
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
          (x) =>
            x &&
            typeof x.symbol === "string" &&
            typeof x.market === "string" &&
            Number.isFinite(+x.ts)
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

    // NEW
    autoRefreshEnabled:
      typeof localData.autoRefreshEnabled === "boolean"
        ? localData.autoRefreshEnabled
        : DEFAULT_APP_PREFERENCES.autoRefreshEnabled,
    refreshIntervalSeconds: normalizeRefreshInterval(
      localData.refreshIntervalSeconds ?? DEFAULT_APP_PREFERENCES.refreshIntervalSeconds
    ),
  });

  const setters = {
    setLastSymbol: (s) => (state.lastSymbol = asStr(s)),
    setLastMarket: (m) => (state.lastMarket = asStr(m).toUpperCase()),

    setLastSymbolIdentity: ({ symbol, market } = {}) => {
      state.lastSymbol = asStr(symbol);
      state.lastMarket = asStr(market).toUpperCase();
    },

    getLastSymbolIdentity: () => {
      const symbol = asStr(state.lastSymbol);
      const market = asStr(state.lastMarket).toUpperCase();
      return { symbol, market };
    },

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

    addSymbolHistoryEntry: ({ symbol, market } = {}) => {
      const sym = asStr(symbol);
      const mk = asStr(market).toUpperCase();
      if (!sym || !mk) return;

      const nowTs = Date.now();
      const list = Array.isArray(state.symbolHistory)
        ? state.symbolHistory.slice()
        : [];

      const idx = list.findIndex(
        (x) =>
          asStr(x?.symbol) === sym &&
          asStr(x?.market).toUpperCase() === mk
      );
      if (idx >= 0) list.splice(idx, 1);

      list.unshift({ symbol: sym, market: mk, ts: nowTs });
      state.symbolHistory = list.slice(
        0,
        Math.max(1, Number(SYMBOL_HISTORY_MAX || 200))
      );
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

    setAtrBasePrice: (v) => {
      if (v == null || v === "") {
        state.atrBasePrice = null;
      } else {
        const n = Number(v);
        state.atrBasePrice = Number.isFinite(n) ? n : null;
      }
    },

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

    // NEW
    setAutoRefreshEnabled: (v) => {
      state.autoRefreshEnabled = !!v;
      if (!state.autoRefreshEnabled) {
        state.refreshIntervalSeconds = null;
      }
    },

    setRefreshIntervalSeconds: (v) => {
      state.refreshIntervalSeconds = normalizeRefreshInterval(v);
      state.autoRefreshEnabled = state.refreshIntervalSeconds != null;
    },

    getRefreshIntervalSeconds: () => {
      return normalizeRefreshInterval(state.refreshIntervalSeconds);
    },
  };

  const onStorage = (newLocal) => {
    Object.keys(state).forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(newLocal, key)) {
        state[key] = newLocal[key];
      }
    });

    state.refreshIntervalSeconds = normalizeRefreshInterval(state.refreshIntervalSeconds);
    state.autoRefreshEnabled =
      state.refreshIntervalSeconds != null
        ? true
        : !!state.autoRefreshEnabled;
  };

  return { state, setters, onStorage };
}
