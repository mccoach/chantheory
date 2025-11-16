// src/composables/useSettingsManager.js
// ==============================
// V2.0 - 使用统一配置Schema（消除硬编码）
// 
// 核心改造：
//   - 删除内部 keyDomainMap 硬编码
//   - 改用 constants/settingsSchema.js 的映射表
//   - 保持原有接口完全兼容
// ==============================

import { reactive } from "vue";
import { useUserSettings } from "@/composables/useUserSettings";
import { findDomainByKey } from "@/constants/settingsSchema";  // ← 新增导入

function keyToSetterName(key) {
  if (!key) return null;
  return `set${key.charAt(0).toUpperCase()}${key.slice(1)}`;
}

export function useSettingsManager({ settingsKey, defaultConfig, mergeFn }) {
  const settings = useUserSettings();

  // ===== 核心重构：使用统一Schema =====
  function readCurrentConfig() {
    try {
      const domain = findDomainByKey(settingsKey);  // ← 查表，不再硬编码
      
      if (!domain) {
        console.warn(`useSettingsManager: Unknown settingsKey '${settingsKey}'`);
        return {};
      }
      
      if (settings[domain] && settings[domain][settingsKey] !== undefined) {
        return settings[domain][settingsKey] ?? {};
      }
      
      return {};
    } catch (e) {
      console.error(`useSettingsManager: Failed to read config for key '${settingsKey}'`, e);
      return {};
    }
  }

  const localConfig = readCurrentConfig();
  const mergedConfig =
    typeof mergeFn === "function"
      ? mergeFn(localConfig)
      : { ...defaultConfig, ...localConfig };

  const draft = reactive(JSON.parse(JSON.stringify(mergedConfig)));

  const save = () => {
    try {
      const setterName = keyToSetterName(settingsKey);
      const setter = settings[setterName];
      if (typeof setter === "function") {
        setter(JSON.parse(JSON.stringify(draft)));
      } else {
        console.warn(`useSettingsManager: Setter '${setterName}' not found`);
      }
    } catch (e) {
      console.error(`useSettingsManager: Failed to save settings for key '${settingsKey}'`, e);
    }
  };

  const reset = () => {
    try {
      const defaults = JSON.parse(JSON.stringify(defaultConfig));
      Object.keys(draft).forEach(key => delete draft[key]);
      Object.assign(draft, defaults);
    } catch (e) {
      console.error(`useSettingsManager: Failed to reset settings for key '${settingsKey}'`, e);
    }
  };

  return { draft, save, reset };
}