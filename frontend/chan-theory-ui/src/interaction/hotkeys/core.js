// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\interaction\hotkeys\core.js
// ==============================
// 说明：全局键盘事件归一化与分发辅助（保持简单）
// - 提供 toCombo：将 KeyboardEvent 规范化为统一组合字符串（如 "Ctrl+Shift+Digit1"）
// - 提供 isReservedBrowserCombo：判断浏览器保留快捷键以绕过
// 注：输入框白名单的扩展逻辑已在 registry.js 中处理
// ==============================

const keyAlias = {                   // 常见键名别名 → 标准键名
  // Escape 系列：覆盖 Windows/Mac/旧 WebKit/国产壳等可能的变体
  Esc: "Escape",                     // 常见别名
  ESC: "Escape",                     // 全大写变体
  Cancel: "Escape",                  // 少量实现会返回 "Cancel"
  "U+001B": "Escape",                // 极旧实现（早期 WebKit/IE）可能返回的编码样式
  // 方向键
  Left: "ArrowLeft",               // Left → ArrowLeft
  Right: "ArrowRight",             // Right → ArrowRight
  Up: "ArrowUp",                   // Up → ArrowUp
  Down: "ArrowDown",               // Down → ArrowDown
  // 其它常见按键
  "+": "Equal",                    // + → 等号键（Equal）
  "-": "Minus",                    // - → 减号键（Minus）
  ",": "Comma",                    // , → 逗号键（Comma）
};                                  // 结束别名映射

function normKey(base) {            // 归一化原始 key
  if (!base) return "";             // 空值保护
  const k = base.length === 1 ? base : base; // 单字符保持原样
  return keyAlias[k] || k;          // 尝试别名映射，否则原样返回
}                                   // 结束 normKey

export function toCombo(e) {        // 将 KeyboardEvent 转换为组合键字符串
  if (e.isComposing) return "";     // 输入法组合时忽略
  let k = e.key;                    // 读取按键名
  if (/^\d$/.test(k)) {             // 如果是数字（0-9）
    return withMods(e, e.code);     // 使用 e.code（如 Digit1）以更稳
  }                                 // 结束数字处理
  k = normKey(k);                   // 别名归一化
  if (k.length > 1) {               // 功能键统一首字母大写
    k = k[0].toUpperCase() + k.slice(1);
  }                                 // 结束大写处理
  return withMods(e, k);            // 拼接修饰键并返回
}                                   // 结束 toCombo

function withMods(e, keyName) {     // 拼接修饰键
  const parts = [];                 // 组合片段数组
  if (e.ctrlKey) parts.push("Ctrl");// Ctrl
  if (e.metaKey) parts.push("Meta");// Meta（Mac Command）
  if (e.altKey) parts.push("Alt");  // Alt
  if (e.shiftKey && keyName !== "Shift") parts.push("Shift"); // Shift（避免重复）
  parts.push(keyName);              // 追加主键
  return parts.join("+");           // 组合字符串
}                                   // 结束 withMods

export function isReservedBrowserCombo(e) { // 判断是否为浏览器保留组合
  const combo = toCombo(e);         // 规范化组合
  const reserved = new Set([        // 常见浏览器级快捷键
    "Ctrl+L",                       // 地址栏
    "Ctrl+T",                       // 新标签
    "Ctrl+W",                       // 关闭标签
    "F5",                           // 刷新
    "Ctrl+R",                       // 刷新
    "Meta+R",                       // 刷新（Mac）
    "Meta+W",                       // 关闭标签（Mac）
    "Meta+T",                       // 新标签（Mac）
  ]);                                // 结束集合
  return reserved.has(combo);        // 是保留则返回 true
}                                   // 结束 isReservedBrowserCombo
