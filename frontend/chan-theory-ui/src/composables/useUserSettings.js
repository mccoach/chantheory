// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useUserSettings.js
// ==============================
// 说明：重构为用户设置的“聚合器”
// - 职责：加载/保存/同步 LocalStorage，并将配置分发给各个子模块进行管理。
// - 导出：一个按领域组织的、包含响应式状态和方法的结构化对象。
// - 修正：将 volSettings 归入 chartDisplay 模块。
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

  // 聚合所有子模块的状态
  const aggregatedState = reactive({
    ...preferences.state,
    ...viewState.state,
    ...chartDisplay.state,
    ...chanTheory.state,
  });

  // 统一的持久化：深度监听聚合后的状态
  const saveDebounced = debounce((s) => saveToLocal(s), 300);
  watch(aggregatedState, (newState) => saveDebounced(newState), { deep: true });

  // 统一的跨标签页同步
  const onStorage = (e) => {
    if (e.key !== LS_KEY || !e.newValue) return;
    try {
      const newLocal = JSON.parse(e.newValue);
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
