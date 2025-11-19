// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\settings\chartDisplay.js
// ==============================
// 设置子模块：图表显示
// - 职责：管理 K 线样式（klineStyle）、MA 均线配置（maConfigs）、量窗设置（volSettings）、MACD 设置（macdSettings）。
// ==============================

import { reactive } from "vue";
import {
  DEFAULT_KLINE_STYLE,
  DEFAULT_MA_CONFIGS,
  DEFAULT_VOL_SETTINGS,
  DEFAULT_MACD_SETTINGS,
} from "@/constants";
import { deepMerge } from "@/utils/objectUtils"; // NEW

// 递归深度合并工具，用于确保本地的深层配置能正确覆盖默认值 (REMOVED)

export function createChartDisplayState(localData = {}) {
  const state = reactive({
    klineStyle: deepMerge({}, DEFAULT_KLINE_STYLE, localData.klineStyle || {}),
    maConfigs: deepMerge({}, DEFAULT_MA_CONFIGS, localData.maConfigs || {}),
    volSettings: deepMerge(
      {},
      DEFAULT_VOL_SETTINGS,
      localData.volSettings || {}
    ),
    macdSettings: deepMerge(
      {},
      DEFAULT_MACD_SETTINGS,
      localData.macdSettings || {}
    ),
  });

  const setters = {
    setKlineStyle: (obj) => {
      state.klineStyle = deepMerge({}, DEFAULT_KLINE_STYLE, obj || {});
    },
    setMaConfigs: (obj) => {
      state.maConfigs = deepMerge({}, DEFAULT_MA_CONFIGS, obj || {});
    },
    updateMa: (key, patch) => {
      if (state.maConfigs[key]) {
        state.maConfigs[key] = {
          ...(state.maConfigs[key] || {}),
          ...(patch || {}),
        };
      }
    },
    setVolSettings: (obj) => {
      state.volSettings = deepMerge({}, DEFAULT_VOL_SETTINGS, obj || {});
    },
    patchVolSettings: (patch) => {
      state.volSettings = { ...(state.volSettings || {}), ...(patch || {}) };
    },
    setMacdSettings: (obj) => {
      state.macdSettings = deepMerge({}, DEFAULT_MACD_SETTINGS, obj || {}); // ← 新增
    },
    patchMacdSettings: (patch) => {
      state.macdSettings = { ...(state.macdSettings || {}), ...(patch || {}) }; // ← 新增
    },
  };

  const onStorage = (newLocal) => {
    state.klineStyle = deepMerge(
      {},
      DEFAULT_KLINE_STYLE,
      newLocal.klineStyle || {}
    );
    state.maConfigs = deepMerge(
      {},
      DEFAULT_MA_CONFIGS,
      newLocal.maConfigs || {}
    );
    state.volSettings = deepMerge(
      {},
      DEFAULT_VOL_SETTINGS,
      newLocal.volSettings || {}
    );
    state.macdSettings = deepMerge(
      {},
      DEFAULT_MACD_SETTINGS,
      newLocal.macdSettings || {}
    );
  };

  return { state, setters, onStorage };
}
