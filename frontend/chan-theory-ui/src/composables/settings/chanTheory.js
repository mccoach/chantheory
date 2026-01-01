// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\settings\chanTheory.js
// ==============================
// 设置子模块：缠论参数
// - 职责：管理缠论标记（chanSettings）和分型（fractalSettings）的配置。
// ==============================

import { reactive } from "vue";
import { CHAN_DEFAULTS, FRACTAL_DEFAULTS } from "@/constants";
import { deepMerge } from "@/utils/objectUtils";

// 分型设置的特殊合并逻辑
function mergeFractalSettings(local = {}) {
  const defaults = JSON.parse(JSON.stringify(FRACTAL_DEFAULTS));
  const merged = deepMerge(defaults, local);
  // 确保 enabled 是布尔值
  if (local.confirmStyle) {
    merged.confirmStyle.enabled =
      (local.confirmStyle.enabled ?? defaults.confirmStyle.enabled) === true;
  }
  // NEW: 确保 markerPercent 为整数（50~100 由 UI 控制，这里只做兜底）
  if (merged.markerPercent == null) {
    merged.markerPercent = defaults.markerPercent;
  } else {
    const n = Math.round(Number(merged.markerPercent));
    merged.markerPercent = Number.isFinite(n) ? n : defaults.markerPercent;
  }
  return merged;
}

export function createChanTheoryState(localData = {}) {
  const state = reactive({
    chanSettings: deepMerge({}, CHAN_DEFAULTS, localData.chanSettings || {}),
    fractalSettings: mergeFractalSettings(localData.fractalSettings || {}),
  });

  const setters = {
    setChanSettings: (obj) => {
      state.chanSettings = deepMerge({}, CHAN_DEFAULTS, obj || {});
    },
    patchChanSettings: (patch) => {
        state.chanSettings = { ...(state.chanSettings || {}), ...(patch || {}) };
    },
    setFractalSettings: (obj) => {
      state.fractalSettings = mergeFractalSettings(obj || {});
    },
  };

  const onStorage = (newLocal) => {
    state.chanSettings = deepMerge({}, CHAN_DEFAULTS, newLocal.chanSettings || {});
    state.fractalSettings = mergeFractalSettings(newLocal.fractalSettings || {});
  };

  return { state, setters, onStorage };
}