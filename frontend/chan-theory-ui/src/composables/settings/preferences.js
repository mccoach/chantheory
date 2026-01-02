// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\settings\preferences.js
// ==============================
// 设置子模块：应用偏好与历史记录
// V3.0 改动：
//   - 删除 windowPreset 相关逻辑（改为计算属性）
// ==============================

import { reactive } from "vue";
import { DEFAULT_APP_PREFERENCES } from "@/constants";

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

    // NEW: 各窗体高度持久化（按 panelKey 存 px）
    // 结构：{ [panelKey: string]: number }
    panelHeights:
      localData.panelHeights && typeof localData.panelHeights === "object"
        ? localData.panelHeights
        : {},
  });

  // Setters
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
      const MAX_STORE = 200;
      state.symbolHistory = list.slice(0, MAX_STORE);
    },
    getSymbolHistoryList: () => {
      const list = Array.isArray(state.symbolHistory)
        ? state.symbolHistory.slice()
        : [];
      return list.sort((a, b) => Number(b.ts || 0) - Number(a.ts || 0));
    },

    // NEW: 窗体高度读写（panelKey -> px）
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
  };

  // Storage sync handler
  const onStorage = (newLocal) => {
    Object.keys(state).forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(newLocal, key)) {
        state[key] = newLocal[key];
      }
    });
  };

  return { state, setters, onStorage };
}
