// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\settings\viewState.js
// ==============================
// 设置子模块：视图状态持久化
// V3.0 改动：
//   - 删除 viewAtRightEdge 相关方法（改为计算属性）
//   - 删除 viewLastFocusTs 相关方法（功能重叠且不稳定）
//
// V4.0 - NEW: viewTipTs（最后一次显示 tooltip 的 bar 的 ts）
//   - 语义：只要系统显示了某根 bar 的 tooltip，就把该 bar.ts 持久化；
//   - 用途：键盘左右移动以该 ts 为基点，映射到 idx 后 ±1 再 showTip。
// ==============================

import { reactive } from "vue";

const viewKey = (code, freq) => `${String(code || "").trim()}|${String(freq || "").trim()}`;

export function createViewState(localData = {}) {
  const state = reactive({
    viewRightTs: localData.viewRightTs || {},
    viewBars: localData.viewBars || {},

    // NEW: 最后一次“显示 tooltip”的 bar 的 ts（与 rightTs 窗口锚点解耦）
    viewTipTs: localData.viewTipTs || {},
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

    // NEW: tooltip 基点 ts
    setTipTs: (code, freq, ts) => {
      const key = viewKey(code, freq);
      if (ts == null) delete state.viewTipTs[key];
      else state.viewTipTs[key] = Number(ts);
    },
    getTipTs: (code, freq) => {
      const key = viewKey(code, freq);
      const val = state.viewTipTs[key];
      return Number.isFinite(+val) ? +val : null;
    },
  };

  // Storage sync handler
  const onStorage = (newLocal) => {
    state.viewRightTs = newLocal.viewRightTs || {};
    state.viewBars = newLocal.viewBars || {};
    state.viewTipTs = newLocal.viewTipTs || {};
  };

  return { state, methods, onStorage };
}
