// src/interaction/handlers/global.js
// ==============================
// 说明：全局快捷键处理器注册器
// 职责：为 global 和 modal:settings 作用域注册处理器
// 设计：纯函数，接收依赖注入，零内部状态
// ==============================

/**
 * 注册全局作用域的快捷键处理器
 * 
 * @param {Object} deps - 依赖注入
 * @param {Object} deps.hotkeys - HotkeyService 实例
 * @param {Object} deps.dialogManager - DialogManager 实例
 * @param {Object} deps.vm - MarketView 实例
 * @param {Object} deps.renderHub - RenderHub 实例
 */
export function registerGlobalHandlers({ hotkeys, dialogManager, vm, renderHub }) {
  if (!hotkeys) {
    console.warn('[Handlers] hotkeys service is required');
    return;
  }

  console.log('[Handlers] 🎹 注册全局快捷键处理器...');

  // ===== global 作用域 =====
  hotkeys.registerHandlers("global", {
    // 打开快捷键设置（Ctrl+, 或 F1）
    openHotkeySettings: async () => {
      console.log('[Hotkey] 触发：打开快捷键设置');
      try {
        const mod = await import('@/components/ui/HotkeySettingsDialog.vue');
        dialogManager.open({
          title: "快捷键设置",
          contentComponent: mod.default,
        });
      } catch (err) {
        console.error('[Hotkey] 打开设置失败', err);
      }
    },

    openHotkeyHelp: async () => {
      console.log('[Hotkey] 触发：打开帮助');
      try {
        const mod = await import('@/components/ui/HotkeySettingsDialog.vue');
        dialogManager.open({
          title: "快捷键帮助",
          contentComponent: mod.default,
        });
      } catch (err) {
        console.error('[Hotkey] 打开帮助失败', err);
      }
    },

    // 刷新数据（Alt+R）
    refresh: () => {
      console.log('[Hotkey] 触发：刷新数据');
      try {
        vm?.reload?.({ force_refresh: true });
      } catch (err) {
        console.error('[Hotkey] 刷新失败', err);
      }
    },

    // 十字线左移（ArrowLeft）
    cursorLeft: () => {
      console.log('[Hotkey] 触发：光标左移');
      try {
        renderHub?.moveCursorByStep?.(-1);
      } catch (err) {
        console.error('[Hotkey] 光标左移失败', err);
      }
    },

    // 十字线右移（ArrowRight）
    cursorRight: () => {
      console.log('[Hotkey] 触发：光标右移');
      try {
        renderHub?.moveCursorByStep?.(1);
      } catch (err) {
        console.error('[Hotkey] 光标右移失败', err);
      }
    },
  });

  console.log('[Handlers] ✅ global 作用域已注册');
}

/**
 * 注册设置弹窗作用域的快捷键处理器
 * 
 * @param {Object} deps - 依赖注入
 * @param {Object} deps.hotkeys - HotkeyService 实例
 * @param {Function} deps.onClose - 关闭回调
 * @param {Function} deps.onSave - 保存回调
 */
export function registerModalSettingsHandlers({ hotkeys, onClose, onSave }) {
  if (!hotkeys) {
    console.warn('[Handlers] hotkeys service is required');
    return;
  }

  console.log('[Handlers] 🎹 注册 modal:settings 处理器...');

  hotkeys.registerHandlers("modal:settings", {
    // 关闭设置（Esc）
    closeSettings: () => {
      console.log('[Hotkey] 触发：关闭设置');
      try {
        onClose?.();
      } catch (err) {
        console.error('[Hotkey] 关闭失败', err);
      }
    },

    // 保存设置（Ctrl+Enter）
    saveSettings: () => {
      console.log('[Hotkey] 触发：保存设置');
      try {
        onSave?.();
      } catch (err) {
        console.error('[Hotkey] 保存失败', err);
      }
    },
  });

  console.log('[Handlers] ✅ modal:settings 作用域已注册');
}

/**
 * 注销所有处理器（应用卸载时调用）
 * 
 * @param {Object} deps - 依赖注入
 * @param {Object} deps.hotkeys - HotkeyService 实例
 */
export function unregisterAllHandlers({ hotkeys }) {
  if (!hotkeys) return;

  console.log('[Handlers] 🗑️ 注销所有处理器...');
  
  try {
    hotkeys.unregisterHandlers("global");
    hotkeys.unregisterHandlers("modal:settings");
    console.log('[Handlers] ✅ 所有处理器已注销');
  } catch (err) {
    console.error('[Handlers] 注销失败', err);
  }
}