// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useDialogManager.js
// ==============================
// 说明：全局对话框（设置弹窗）管理器（集中式）
// - 仅负责：管理当前激活弹窗的状态（title/contentComponent/onSave/onClose/props/tabs/activeTab）与开关方法。
// - tabs：可选的标签页数组 [{key:'base',label:'基础'}, ...]，activeTab 初始来自 options.activeTab 或第一个 tabs。
// - 性能：使用 shallowRef 保存 activeDialog，对 contentComponent 使用 markRaw 避免 reactive 包装。
// ==============================

import { shallowRef, readonly, markRaw } from "vue"; // 引入浅响应式与 markRaw

// 全局唯一的激活弹窗状态（shallowRef：仅一层响应式）
const activeDialog = shallowRef(null); // 初始为 null 表示无弹窗

/**
 * 打开一个对话框
 * @param {object} options - 打开参数
 * @param {string} options.title - 弹窗标题
 * @param {object} options.contentComponent - 作为弹窗内容的组件对象（将被 markRaw）
 * @param {Function} [options.onSave] - “保存并关闭”命令回调
 * @param {Function} [options.onClose] - “取消/关闭”命令回调
 * @param {object} [options.props] - 传递给内容组件的 props
 * @param {Array<{key:string,label:string}>} [options.tabs] - 可选：标签页数组（为空或缺省则不显示标签条）
 * @param {string} [options.activeTab] - 可选：初始活动标签 key（默认 tabs[0].key）
 */
function open(options) {
  // 保护性：若传入无组件，直接拒绝
  if (!options || !options.contentComponent) {
    console.warn("DialogManager.open: contentComponent is required");
    return;
  }
  // 使用 markRaw 包裹组件，避免被 reactive 化
  const content = markRaw(options.contentComponent);
  // 处理 tabs（可选）
  const tabs = Array.isArray(options.tabs) ? options.tabs.slice() : [];
  const activeTab = options.activeTab || (tabs.length ? tabs[0].key : null);

  // 写入激活状态（shallowRef 仅对第一层做响应式跟踪）
  activeDialog.value = {
    title: options.title || "设置", // 标题（默认“设置”）
    contentComponent: content, // 内容组件（已 markRaw）
    onSave: typeof options.onSave === "function" ? options.onSave : null, // 保存回调
    onClose: typeof options.onClose === "function" ? options.onClose : null, // 关闭回调
    onResetAll:
      typeof options.onResetAll === "function" ? options.onResetAll : null, // 全部恢复默认回调
    props: options.props || {}, // 透传 props
    tabs, // 标签页数组（可空）
    activeTab, // 当前活动标签（可空）
  };
}

/**
 * 关闭当前激活对话框
 */
function close() {
  activeDialog.value = null; // 清空状态
}

/**
 * 切换当前活动标签（若无 tabs 则忽略）
 * @param {string} key -   签 key
 */
function setActiveTab(key) {
  if (!activeDialog.value || !activeDialog.value.tabs?.length) return;
  activeDialog.value = { ...activeDialog.value, activeTab: String(key || "") };
}

/**
 * 导出组合式
 */
export function useDialogManager() {
  return {
    activeDialog: readonly(activeDialog), // 只读暴露状态（外部不可直接改）
    open, // 打开
    close, // 关闭
    setActiveTab, // 切换 tab
  };
}