// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\interaction\plugin\vue.js
// ==============================
// 说明：Vue 快捷键插件（修复响应式更新）
// - 引入 vue 的 watch，在插件安装时，不仅读取一次用户覆盖，还持续监听其变化。
// - 当用户在设置面板保存新快捷键时，hotkeyOverrides ref 变化，watch 会触发，
//   调用 hotkeys.setUserOverrides(newOverrides) 将最新配置同步到服务内部，保证立即生效。
//
// V2.1 - NEW: NumberSpinner Enter 提交后“跳到下一格/上一格”归口 hotkeys（方案B）
// - NumberSpinner 在提交成功后派发 window 事件：chan:numspin-focus-next {dir:+1|-1}
// - 插件侧监听此事件并调用 hotkeys.focusNextPrev(dir)，实现一致的焦点跳转策略
// - 事件监听在卸载时清理，避免泄漏
// ==============================

import { watch } from "vue"; // 引入 watch 用于监听响应式变化
import { HotkeyService } from "../hotkeys/registry.js";
import { defaultKeymap } from "../hotkeys/presets.js";

export default {
  install(app, options = {}) {
    const hotkeys = new HotkeyService(defaultKeymap); // 创建服务实例

    // NEW: 监听 NumberSpinner 提交后的“请求跳转焦点”事件
    const onNumspinFocusMove = (e) => {
      try {
        const dirRaw = e?.detail?.dir;
        const dir = Number(dirRaw);
        if (!Number.isFinite(dir) || dir === 0) return;

        // 复用 hotkeys 内置的 focusNextPrev（浏览器默认 Tab 顺序语义）
        hotkeys.focusNextPrev(dir > 0 ? +1 : -1);
      } catch {}
    };

    try {
      window.addEventListener("chan:numspin-focus-next", onNumspinFocusMove);
    } catch {}

    // 修复：不仅读取初始值，还要 watch 它的变化
    if (options.userOverrides && typeof options.userOverrides.value !== 'undefined') {
      // 1. 初始设置
      hotkeys.setUserOverrides(options.userOverrides.value);

      // 2. 监听后续变更
      watch(
        options.userOverrides, // 直接监听 ref
        (newOverrides) => {
          hotkeys.setUserOverrides(newOverrides); // 当 ref 变化时，更新服务
        },
        { deep: true } // 深度监听
      );
    }

    app.provide("hotkeys", hotkeys); // 注入

    // HMR 或卸载时清理
    if (app.__hotkeys_uninstall__) {
      try { app.__hotkeys_uninstall__(); } catch {}
    }
    app.__hotkeys_uninstall__ = () => {
      try { window.removeEventListener("chan:numspin-focus-next", onNumspinFocusMove); } catch {}
      hotkeys.destroy();
    };
  },
};
