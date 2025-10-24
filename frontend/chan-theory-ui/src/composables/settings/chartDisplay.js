// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\settings\chartDisplay.js
// ==============================
// 设置子模块：图表显示
// - 职责：管理 K 线样式（klineStyle）、MA 均线配置（maConfigs）、量窗设置（volSettings）。
// ==============================

import { reactive } from "vue";
import { DEFAULT_KLINE_STYLE, DEFAULT_MA_CONFIGS, DEFAULT_VOL_SETTINGS } from "@/constants";

// 递归深度合并工具，用于确保本地的深层配置能正确覆盖默认值
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

export function createChartDisplayState(localData = {}) {
  const state = reactive({
    klineStyle: deepMerge(DEFAULT_KLINE_STYLE, localData.klineStyle || {}),
    maConfigs: deepMerge(DEFAULT_MA_CONFIGS, localData.maConfigs || {}),
    volSettings: deepMerge(DEFAULT_VOL_SETTINGS, localData.volSettings || {}),
  });

  const setters = {
    setKlineStyle: (obj) => {
      state.klineStyle = deepMerge(DEFAULT_KLINE_STYLE, obj || {});
    },
    setMaConfigs: (obj) => {
      state.maConfigs = deepMerge(DEFAULT_MA_CONFIGS, obj || {});
    },
    updateMa: (key, patch) => {
      if (state.maConfigs[key]) {
        state.maConfigs[key] = { ...(state.maConfigs[key] || {}), ...(patch || {}) };
      }
    },
    setVolSettings: (obj) => {
      state.volSettings = deepMerge(DEFAULT_VOL_SETTINGS, obj || {});
    },
    patchVolSettings: (patch) => {
      state.volSettings = { ...(state.volSettings || {}), ...(patch || {}) };
    },
  };

  const onStorage = (newLocal) => {
    state.klineStyle = deepMerge(DEFAULT_KLINE_STYLE, newLocal.klineStyle || {});
    state.maConfigs = deepMerge(DEFAULT_MA_CONFIGS, newLocal.maConfigs || {});
    state.volSettings = deepMerge(DEFAULT_VOL_SETTINGS, newLocal.volSettings || {});
  };

  return { state, setters, onStorage };
}
