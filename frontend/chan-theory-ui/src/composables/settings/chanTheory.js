// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\settings\chanTheory.js
// ==============================
// 设置子模块：缠论参数
// - 职责：管理缠论标记（chanSettings）和分型（fractalSettings）的配置。
// ==============================

import { reactive } from "vue";
import { CHAN_DEFAULTS, FRACTAL_DEFAULTS } from "@/constants";

// 递归深度合并工具
function deepMerge(target, source) {
    const output = { ...target };
    if (target && typeof target === 'object' && source && typeof source === 'object') {
        Object.keys(source).forEach(key => {
            if (source[key] && typeof source[key] === 'object' && key in target) {
                output[key] = deepMerge(target[key], source[key]);
            } else {
                output[key] = source[key];
            }
        });
    }
    return output;
}

// 分型设置的特殊合并逻辑
function mergeFractalSettings(local = {}) {
  const defaults = JSON.parse(JSON.stringify(FRACTAL_DEFAULTS));
  const merged = deepMerge(defaults, local);
  // 确保 enabled 是布尔值
  if (local.confirmStyle) {
    merged.confirmStyle.enabled = (local.confirmStyle.enabled ?? defaults.confirmStyle.enabled) === true;
  }
  return merged;
}

export function createChanTheoryState(localData = {}) {
  const state = reactive({
    chanSettings: deepMerge(CHAN_DEFAULTS, localData.chanSettings || {}),
    fractalSettings: mergeFractalSettings(localData.fractalSettings || {}),
  });

  const setters = {
    setChanSettings: (obj) => {
      state.chanSettings = deepMerge(CHAN_DEFAULTS, obj || {});
    },
    patchChanSettings: (patch) => {
        state.chanSettings = { ...(state.chanSettings || {}), ...(patch || {}) };
    },
    setFractalSettings: (obj) => {
      state.fractalSettings = mergeFractalSettings(obj || {});
    },
  };

  const onStorage = (newLocal) => {
    state.chanSettings = deepMerge(CHAN_DEFAULTS, newLocal.chanSettings || {});
    state.fractalSettings = mergeFractalSettings(newLocal.fractalSettings || {});
  };

  return { state, setters, onStorage };
}
