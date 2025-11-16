// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\settings\viewState.js
// ==============================
// 设置子模块：视图状态持久化
// V3.0 改动：
//   - 删除 viewAtRightEdge 相关方法（改为计算属性）
//   - 删除 viewLastFocusTs 相关方法（功能重叠且不稳定）
// ==============================

import { reactive } from "vue";

const viewKey = (code, freq) => `${String(code || "").trim()}|${String(freq || "").trim()}`;

export function createViewState(localData = {}) {
  const state = reactive({
    viewRightTs: localData.viewRightTs || {},
    viewBars: localData.viewBars || {},
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
  };

  // Storage sync handler
  const onStorage = (newLocal) => {
    state.viewRightTs = newLocal.viewRightTs || {};
    state.viewBars = newLocal.viewBars || {};
  };

  return { state, methods, onStorage };
}