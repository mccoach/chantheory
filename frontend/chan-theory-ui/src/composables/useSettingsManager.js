// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useSettingsManager.js
// ==============================
// 说明：通用设置管理器（数据驱动，无UI）
// - 职责：提供一个通用的、可复用的机制来管理任何一项设置的“草稿-加载-保存-重置”生命周期。
// - 设计：
//   * 工厂函数：useSettingsManager({ settingsKey, defaultConfig, mergeFn })
//   * settingsKey: 在 useUserSettings 中的存储键。
//   * defaultConfig: 来自 constants 的出厂默认配置。
//   * mergeFn (可选): 自定义合并函数，用于深度合并加载的设置。
// - 返回：{ draft, save, reset }
//   * draft: 一个 reactive 对象，供 UI 面板直接绑定。
//   * save: 将草稿写回 useUserSettings。
//   * reset: 将草稿恢复到出厂默认值。
// ==============================

import { reactive } from "vue";
import { useUserSettings } from "@/composables/useUserSettings";

// 将 settingsKey (camelCase) 转换为 useUserSettings 中的 setter 方法名 (PascalCase)
// e.g., 'klineStyle' -> 'setKlineStyle'
function keyToSetterName(key) {
  if (!key) return null;
  return `set${key.charAt(0).toUpperCase()}${key.slice(1)}`;
}

export function useSettingsManager({ settingsKey, defaultConfig, mergeFn }) {
  const settings = useUserSettings();

  // 1. 创建草稿对象
  // 初始状态：从 useUserSettings 加载，并与默认值合并
  const localConfig = settings[settingsKey]?.value ?? {};
  const mergedConfig =
    typeof mergeFn === "function"
      ? mergeFn(localConfig)
      : { ...defaultConfig, ...localConfig };

  const draft = reactive(JSON.parse(JSON.stringify(mergedConfig)));

  // 2. 保存方法
  const save = () => {
    try {
      const setterName = keyToSetterName(settingsKey);
      const setter = settings[setterName];
      if (typeof setter === "function") {
        // 使用 toRaw 避免将 Vue 的响应式代理存入 LocalStorage
        setter(JSON.parse(JSON.stringify(draft)));
      } else {
        console.warn(`useSettingsManager: Setter '${setterName}' not found in useUserSettings.`);
      }
    } catch (e) {
      console.error(`useSettingsManager: Failed to save settings for key '${settingsKey}'`, e);
    }
  };

  // 3. 重置方法
  const reset = () => {
    try {
      const defaults = JSON.parse(JSON.stringify(defaultConfig));
      // 直接修改 reactive 对象的属性，以触发 UI 更新
      Object.keys(draft).forEach(key => delete draft[key]);
      Object.assign(draft, defaults);
    } catch (e) {
      console.error(`useSettingsManager: Failed to reset settings for key '${settingsKey}'`, e);
    }
  };

  return { draft, save, reset };
}
