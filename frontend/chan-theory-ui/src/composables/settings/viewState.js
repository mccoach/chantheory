// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\settings\viewState.js
// ==============================
// 设置子模块：视图状态持久化
// - 职责：管理与每个图表视图（code|freq）相关的持久化状态，如锚点、可见根数等。
// ==============================

import { reactive } from "vue";

const viewKey = (code, freq) => `${String(code || "").trim()}|${String(freq || "").trim()}`;

export function createViewState(localData = {}) {
  const state = reactive({
    viewRightTs: localData.viewRightTs || {},
    viewBars: localData.viewBars || {},
    viewAtRightEdge: localData.viewAtRightEdge || {},
    viewLastFocusTs: localData.viewLastFocusTs || {},
  });

  // Setters & Getters
  const methods = {
    setRightTs: (code, freq, ts) => {
      const key = viewKey(code, freq);
      if (ts == null) delete state.viewRightTs[key];
      else state.viewRightTs[key] = Number(ts);
    },
    getRightTs: (code, freq) => {
      const key = viewKey(code, freq);
      const val = state.viewRightTs[key];
      return Number.isFinite(+val) ? +val : null;
    },
    setViewBars: (code, freq, bars) => {
      const key = viewKey(code, freq);
      if (!Number.isFinite(+bars) || +bars < 1) delete state.viewBars[key];
      else state.viewBars[key] = Math.max(1, Math.ceil(+bars));
    },
    getViewBars: (code, freq) => {
      const key = viewKey(code, freq);
      const val = state.viewBars[key];
      return Number.isFinite(+val) ? Math.max(1, Math.ceil(+val)) : null;
    },
    setAtRightEdge: (code, freq, isAtRight) => {
      const key = viewKey(code, freq);
      state.viewAtRightEdge[key] = !!isAtRight;
    },
    getAtRightEdge: (code, freq) => {
      const key = viewKey(code, freq);
      return !!state.viewAtRightEdge[key];
    },
    setLastFocusTs: (code, freq, ts) => {
      const key = viewKey(code, freq);
      if (ts == null) delete state.viewLastFocusTs[key];
      else state.viewLastFocusTs[key] = Number(ts);
    },
    getLastFocusTs: (code, freq) => {
      const key = viewKey(code, freq);
      const val = state.viewLastFocusTs[key];
      return Number.isFinite(+val) ? +val : null;
    },
  };

  // Storage sync handler
  const onStorage = (newLocal) => {
    state.viewRightTs = newLocal.viewRightTs || {};
    state.viewBars = newLocal.viewBars || {};
    state.viewAtRightEdge = newLocal.viewAtRightEdge || {};
    state.viewLastFocusTs = newLocal.viewLastFocusTs || {};
  };
  
  return { state, methods, onStorage };
}