// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\interaction\hotkeys\presets.js
// ============================================================================
// 说明（逐行注释版）：
// - 提供“默认快捷键映射表”（defaultKeymap）与“命令中文名称映射”（commandLabels）。
// - 结构：
//   * defaultKeymap 是一个“作用域 → 组合键 → 命令”的映射表；用户可在运行时以 overrides 覆盖。
//   * commandLabels 是一个“命令 → 中文名称”的映射表，供 UI 展示。
// - 集成约定：
//   * 作用域 scope 包含：global / panel:symbol / panel:mainChart / modal:settings / modal:MAEditor。
//   * global 里的 openHotkeySettings（Ctrl+, / F1）由 App.vue 注册处理器来打开全局设置弹窗（dialogManager）。
//   * modal:settings 的 closeSettings/saveSettings 对应 Esc / Ctrl(Cmd)+Enter，具体执行在 App.vue 统一处理。
// ============================================================================

export const defaultKeymap = {
  // -----------------------------
  // 全局作用域（任何时候有效，但会被更顶层 scope 覆盖）
  // -----------------------------
  "global": {
    // 取消/关闭当前操作（仅供业务自行决定如何处理；对于 modal:settings，Esc 会由 modal:settings 接管）
    "Escape": "cancel",
    // 确认/保存当前操作（同上说明；modal:settings 场景由 modal:settings 接管）
    "Ctrl+Enter": "confirm",
    "Meta+Enter": "confirm",
    // 打开帮助（本项目中作为打开快捷键设置的备用触发）
    "F1": "openHotkeyHelp",
    // 打开快捷键设置（Ctrl + ,），App.vue 注册处理器调用 dialogManager.open
    "Ctrl+Comma": "openHotkeySettings",
    // 输入控件间快速移动
    "Tab": "focusNextField",
    "Shift+Tab": "focusPrevField",
    "Ctrl+Right": "focusNextField",
    "Ctrl+Left": "focusPrevField",
    // 快速刷新（Alt+R）
    "Alt+R": "refresh",
    // 打开/关闭导出菜单（Alt+E）
    "Alt+E": "toggleExportMenu"
  },

  // -----------------------------
  // 标的输入面板（SymbolPanel）的下拉交互
  // -----------------------------
  "panel:symbol": {
    // 下移/上移下拉选项
    "ArrowDown": "dropdownNext",
    "ArrowUp": "dropdownPrev",
    // 确认当前项
    "Enter": "dropdownConfirm",
    // 关闭下拉
    "Escape": "dropdownClose"
  },

  // -----------------------------
  // 主图快捷切换（预留，示例映射）
  // -----------------------------
  "panel:mainChart": {
    // 切换分时/日/周/月（示例，实际由业务决定是否实现）
    "KeyT": "setTimeMode",
    "KeyD": "setDay",
    "KeyW": "setWeek",
    "KeyM": "setMonth",
    // 快速切换分钟周期（Alt+数字）
    "Alt+Digit1": "set1m",
    "Alt+Digit5": "set5m",
    "Alt+Digit3": "set15m",
    "Alt+Digit4": "set30m",
    "Alt+Digit6": "set60m"
  },

  // -----------------------------
  // 设置弹窗专用作用域（由 App.vue 统一注册处理器）：
  // - Esc：关闭当前设置弹窗
  // - Ctrl/Cmd+Enter：保存并应用
  // -----------------------------
  "modal:settings": {
    "Escape": "closeSettings",
    "Ctrl+Enter": "saveSettings",
    "Meta+Enter": "saveSettings"
  },

  // -----------------------------
  // 预留：MA 编辑器专用作用域（当前未使用，未来可扩展）
  // -----------------------------
  "modal:MAEditor": {
    "Escape": "cancelEdit",
    "Enter": "confirmEdit",
    "Ctrl+Enter": "confirmEdit",
    "Meta+Enter": "confirmEdit",
    "ArrowLeft": "prevMA",
    "ArrowRight": "nextMA",
    "Equal": "incPeriod",           // 加号键（需要按住 Shift 时，浏览器产生 Equal）
    "Minus": "decPeriod",           // 减号键
    "Shift+ArrowUp": "incWidth",
    "Shift+ArrowDown": "decWidth",
    "Ctrl+ArrowUp": "cycleStyleNext",
    "Ctrl+ArrowDown": "cycleStylePrev"
  }
};

// ============================================================================
// 命令中文名称（UI 友好显示用途）
// - 若某命令没有中文名称，则 UI 回退使用命令自身键名。
// ============================================================================

export const commandLabels = {
  // 全局基础
  cancel: "取消/关闭当前操作",
  confirm: "确认/保存当前操作",
  openHotkeyHelp: "打开快捷键帮助",
  openHotkeySettings: "打开快捷键设置",
  focusNextField: "跳转到下一个输入框",
  focusPrevField: "跳转到上一个输入框",
  refresh: "刷新数据",
  toggleExportMenu: "打开/关闭导出菜单",

  // 标的下拉
  dropdownNext: "下拉选择下一项",
  dropdownPrev: "下拉选择上一项",
  dropdownConfirm: "下拉确认选择",
  dropdownClose: "关闭下拉",

  // 主图切换（示例）
  setTimeMode: "切换分时",
  setDay: "切换日K",
  setWeek: "切换周K",
  setMonth: "切换月K",
  set1m: "切换1分钟K线",
  set5m: "切换5分钟K线",
  set15m: "切换15分钟K线",
  set30m: "切换30分钟K线",
  set60m: "切换60分钟K线",

  // 设置弹窗（modal:settings）
  closeSettings: "关闭设置弹窗",
  saveSettings: "保存设置并关闭",

  // MA 编辑器（预留）
  cancelEdit: "取消当前MA编辑",
  confirmEdit: "确认当前MA编辑",
  prevMA: "切换上一条MA",
  nextMA: "切换下一条MA",
  incPeriod: "周期 +1",
  decPeriod: "周期 -1",
  incWidth: "线宽 +1",
  decWidth: "线宽 -1",
  cycleStyleNext: "线型切换下一项",
  cycleStylePrev: "线型切换上一项"
};
