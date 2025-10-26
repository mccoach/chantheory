// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useUserSettings.js
// ==============================
// 说明：重构为用户设置的“聚合器”
// - 职责：加载/保存/同步 LocalStorage，并将配置分发给各个子模块进行管理。
// - 导出：一个按领域组织的、包含响应式状态和方法的结构化对象。
// - 修正：将 volSettings 归入 chartDisplay 模块。
// - REFACTORED: 修复了因浅层展开状态(...)导致响应式更新丢失，从而无法持久化的问题。
//   通过将聚合状态改为嵌套结构，并相应调整持久化逻辑，确保所有设置变更都能被正确侦听和保存。
// ==============================

import { reactive, watch, readonly } from "vue";
import { createPreferencesState } from "./settings/preferences";
import { createViewState } from "./settings/viewState";
import { createChartDisplayState } from "./settings/chartDisplay";
import { createChanTheoryState } from "./settings/chanTheory";

const LS_KEY = "chan_user_settings_v1";

const loadFromLocal = () => {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
};

const saveToLocal = (obj) => {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(obj));
  } catch {}
};

const debounce = (fn, ms = 300) => {
  let t = null;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
};

let _singleton = null;

export function useUserSettings() {
  if (_singleton) return _singleton;

  const localData = loadFromLocal();

  // 创建各个领域的子模块实例
  const preferences = createPreferencesState(localData);
  const viewState = createViewState(localData);
  const chartDisplay = createChartDisplayState(localData);
  const chanTheory = createChanTheoryState(localData);

  // REFACTORED: 聚合所有子模块的状态。
  // 使用嵌套结构而不是扁平化展开，以确保对子状态对象属性（如 indicatorPanes 数组）的重新赋值能被 watch 捕获。
  const aggregatedState = reactive({
    preferences: preferences.state,
    viewState: viewState.state,
    chartDisplay: chartDisplay.state,
    chanTheory: chanTheory.state,
  });

  // REFACTORED: 统一的持久化：深度监听聚合后的状态。
  // 在保存前，将嵌套的 aggregatedState 重新展平为 localStorage 的存储结构。
  const saveDebounced = debounce((nestedState) => {
    const flattenedState = {
      ...nestedState.preferences,
      ...nestedState.viewState,
      ...nestedState.chartDisplay,
      ...nestedState.chanTheory,
    };
    saveToLocal(flattenedState);
  }, 300);

  watch(aggregatedState, (newState) => saveDebounced(newState), { deep: true });

  // 统一的跨标签页同步
  const onStorage = (e) => {
    if (e.key !== LS_KEY || !e.newValue) return;
    try {
      const newLocal = JSON.parse(e.newValue);
      // 各个子模块负责响应该事件并更新自己的状态
      preferences.onStorage(newLocal);
      viewState.onStorage(newLocal);
      chartDisplay.onStorage(newLocal);
      chanTheory.onStorage(newLocal);
    } catch {}
  };
  if (typeof window !== "undefined") {
    window.addEventListener("storage", onStorage);
  }

  // 聚合所有 setters 和 methods
  const allMethods = {
    ...preferences.setters,
    ...viewState.methods,
    ...chartDisplay.setters,
    ...chanTheory.setters,
  };

  // 构建最终导出的结构化 API
  _singleton = {
    // 导出按领域组织的只读状态
    preferences: readonly(preferences.state),
    viewState: readonly(viewState.state),
    chartDisplay: readonly(chartDisplay.state),
    chanTheory: readonly(chanTheory.state),
    // 导出所有方法
    ...allMethods,
  };

  return _singleton;
}
