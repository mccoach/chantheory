// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useUserSettings.js
// ==============================
// V4.0 - 删除 watch，改为主动保存
// 
// 核心改造：
//   1. 删除 watch(settingsPanelState, ...)（过度抽象）
//   2. 新增 saveAll() 方法（主动保存）
//   3. 保留跨标签页同步（storage 事件）
// 
// 职责边界：
//   - 本模块：管理设置的读取/保存（不监听变化）
//   - 设置面板：调用 saveAll() 触发持久化
//   - 命令中枢：管理视图状态的持久化
// ==============================

import { reactive, readonly } from "vue";
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
    preferences: preferences.state,
    viewState: viewState.state,
    chartDisplay: chartDisplay.state,
    chanTheory: chanTheory.state,
  });

  // ===== 删除：watch 监听（改为主动保存）=====

  // ===== 新增：主动保存接口 =====
  function saveAll() {
    const flattenedState = {
      ...aggregatedState.preferences,
      ...aggregatedState.viewState,
      ...aggregatedState.chartDisplay,
      ...aggregatedState.chanTheory,
    };
    saveToLocal(flattenedState);
  }

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
    saveAll,  // ← 新增：主动保存
  };

  return _singleton;
}