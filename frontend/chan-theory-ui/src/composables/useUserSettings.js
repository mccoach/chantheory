// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useUserSettings.js
// ==============================
// V5.0 - 自动持久化版
//
// 变更要点：
//   1. 删除原先“仅手动调用 saveAll 才落盘”的策略，对绝大多数写操作自动调用 saveAll。
//   2. 视图状态 viewState（窗宽 / 右端时间）仍由 ViewCommandHub 通过防抖统一触发 saveAll，
//      因此 viewState 的方法不做自动保存包装，避免高频拖拽时写入过于频繁。
//   3. 所有以 getXxx 开头的方法视为只读访问，不触发持久化。
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

  // ===== 主动保存接口（统一出口）=====
  function saveAll() {
    const flattenedState = {
      // 注意：各子模块的 state 已经将自身字段扁平到 LS 顶层命名空间
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

  // ===== 方法聚合 + 自动持久化包装 =====

  // 原始方法集合（不带自动保存）
  const rawMethods = {
    ...preferences.setters,
    ...viewState.methods,
    ...chartDisplay.setters,
    ...chanTheory.setters,
  };

  // 视图状态的方法名集合（需要跳过自动保存，由 ViewCommandHub 统一防抖触发）
  const viewStateMethodNames = new Set(Object.keys(viewState.methods || {}));

  // 包装后的方法集合
  const methodsWithAutoSave = {};

  Object.entries(rawMethods).forEach(([name, fn]) => {
    if (typeof fn !== "function") return;

    const isGetter = /^get[A-Z]/.test(name); // 约定：getXxx 为只读方法
    const isViewStateMethod = viewStateMethodNames.has(name);

    // 视图状态方法 + getXxx 系列：不自动保存
    if (isGetter || isViewStateMethod) {
      methodsWithAutoSave[name] = fn;
      return;
    }

    // 其它写操作：执行完立即触发 saveAll
    methodsWithAutoSave[name] = (...args) => {
      const result = fn(...args);
      try {
        saveAll();
      } catch (e) {
        console.error(`[useUserSettings] auto-save failed on method '${name}'`, e);
      }
      return result;
    };
  });

  // 构建最终导出的结构化 API（统一只读 state + 包装后的 methods + 显式 saveAll）
  _singleton = {
    // 按领域组织的只读状态
    preferences: readonly(preferences.state),
    viewState: readonly(viewState.state),
    chartDisplay: readonly(chartDisplay.state),
    chanTheory: readonly(chanTheory.state),

    // 所有方法（大部分已自动带 saveAll）
    ...methodsWithAutoSave,

    // 显式保存（仍保留给设置壳等场景使用）
    saveAll,
  };

  return _singleton;
}