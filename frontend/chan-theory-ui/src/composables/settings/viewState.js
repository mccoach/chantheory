// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\settings\viewState.js
// ==============================
// 设置子模块：视图状态持久化
//
// V5.0 - BREAKING: 视图状态 key 升级为双主键语义（market:symbol|freq）
// 改动：
//   - view key 从 symbol|freq 升级为 market:symbol|freq
//   - 新增 buildViewIdentityKey(symbol, market, freq)
//   - 读取/写入都要求同时传 symbol + market + freq
//
// 保持：
//   - viewTipTs 语义不变：最后一次显示 tooltip 的 bar.ts
// ==============================

import { reactive } from "vue";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

export function buildViewIdentityKey(symbol, market, freq) {
  const sym = asStr(symbol);
  const mk = asStr(market).toUpperCase();
  const fr = asStr(freq);
  return `${mk}:${sym}|${fr}`;
}

export function createViewState(localData = {}) {
  const state = reactive({
    viewRightTs: localData.viewRightTs || {},
    viewBars: localData.viewBars || {},
    viewTipTs: localData.viewTipTs || {},
  });

  const methods = {
    setRightTs: (symbol, market, freq, ts) => {
      const key = buildViewIdentityKey(symbol, market, freq);
      if (ts == null) delete state.viewRightTs[key];
      else state.viewRightTs[key] = Number(ts);
    },

    getRightTs: (symbol, market, freq) => {
      const key = buildViewIdentityKey(symbol, market, freq);
      const val = state.viewRightTs[key];
      return Number.isFinite(+val) ? +val : null;
    },

    setViewBars: (symbol, market, freq, bars) => {
      const key = buildViewIdentityKey(symbol, market, freq);
      if (!Number.isFinite(+bars) || +bars < 1) delete state.viewBars[key];
      else state.viewBars[key] = Math.max(1, Math.ceil(+bars));
    },

    getViewBars: (symbol, market, freq) => {
      const key = buildViewIdentityKey(symbol, market, freq);
      const val = state.viewBars[key];
      return Number.isFinite(+val) ? Math.max(1, Math.ceil(+val)) : null;
    },

    setTipTs: (symbol, market, freq, ts) => {
      const key = buildViewIdentityKey(symbol, market, freq);
      if (ts == null) delete state.viewTipTs[key];
      else state.viewTipTs[key] = Number(ts);
    },

    getTipTs: (symbol, market, freq) => {
      const key = buildViewIdentityKey(symbol, market, freq);
      const val = state.viewTipTs[key];
      return Number.isFinite(+val) ? +val : null;
    },
  };

  const onStorage = (newLocal) => {
    state.viewRightTs = newLocal.viewRightTs || {};
    state.viewBars = newLocal.viewBars || {};
    state.viewTipTs = newLocal.viewTipTs || {};
  };

  return { state, methods, onStorage };
}
