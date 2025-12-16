// src/interaction/handlers/scopes.js
// ==============================
// 说明：快捷键作用域管理器
// 职责：管理弹窗打开/关闭时的作用域切换
// 设计：纯函数，零状态，依赖注入
// ==============================

/**
 * 处理弹窗打开时的作用域切换
 * 
 * @param {Object} deps
 * @param {Object} deps.hotkeys - HotkeyService 实例
 * @param {string} deps.scope - 作用域名称（如 'modal:settings'）
 */
export function pushDialogScope({ hotkeys, scope }) {
  if (!hotkeys || !scope) return;
  
  try {
    hotkeys.pushScope(scope);
  } catch (err) {
    console.error(`[Scopes] 压入作用域失败: ${scope}`, err);
  }
}

/**
 * 处理弹窗关闭时的作用域切换
 * 
 * @param {Object} deps
 * @param {Object} deps.hotkeys - HotkeyService 实例
 * @param {string} deps.scope - 作用域名称
 */
export function popDialogScope({ hotkeys, scope }) {
  if (!hotkeys || !scope) return;
  
  try {
    hotkeys.popScope(scope);
  } catch (err) {
    console.error(`[Scopes] 弹出作用域失败: ${scope}`, err);
  }
}