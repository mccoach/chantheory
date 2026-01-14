// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useDialogManager.js
// ==============================
// 说明：全局对话框（设置弹窗）管理器（集中式）
// - 仅负责：管理当前激活弹窗的状态（title/contentComponent/onClose/props/tabs/activeTab/footerActions）与开关方法。
// - tabs：可选的标签页数组 [{key:'base',label:'基础'}, ...]，activeTab 初始来自 options.activeTab 或第一个 tabs。
// - footerActions：由业务提供按钮定义，ModalDialog 统一渲染（避免壳层硬编码业务按钮）。
// - 性能：使用 shallowRef 保存 activeDialog，对 contentComponent 使用 markRaw 避免 reactive 包装。
// ==============================

import { shallowRef, readonly, markRaw } from "vue";

const activeDialog = shallowRef(null);

/**
 * @typedef {{
 *   key?: string,
 *   label: string,
 *   variant?: 'default'|'ok'|'primary'|'danger',
 *   disabled?: boolean,
 *   title?: string,
 *   onClick?: Function,
 * }} FooterAction
 */

/**
 * 打开一个对话框
 * @param {object} options
 * @param {string} options.title
 * @param {object} options.contentComponent
 * @param {Function} [options.onClose]
 * @param {object} [options.props]
 * @param {Array<{key:string,label:string}>} [options.tabs]
 * @param {string} [options.activeTab]
 * @param {FooterAction[]} [options.footerActions]
 */
function open(options) {
  if (!options || !options.contentComponent) {
    console.warn("DialogManager.open: contentComponent is required");
    return;
  }

  const content = markRaw(options.contentComponent);
  const tabs = Array.isArray(options.tabs) ? options.tabs.slice() : [];
  const activeTab = options.activeTab || (tabs.length ? tabs[0].key : null);

  const footerActions = Array.isArray(options.footerActions)
    ? options.footerActions.slice()
    : [];

  activeDialog.value = {
    title: options.title || "设置",
    contentComponent: content,

    onClose: typeof options.onClose === "function" ? options.onClose : null,

    props: options.props || {},
    tabs,
    activeTab,

    // NEW: footerActions
    footerActions,
  };
}

function close() {
  activeDialog.value = null;
}

function setActiveTab(key) {
  if (!activeDialog.value || !activeDialog.value.tabs?.length) return;
  activeDialog.value = { ...activeDialog.value, activeTab: String(key || "") };
}

export function useDialogManager() {
  return {
    activeDialog: readonly(activeDialog),
    open,
    close,
    setActiveTab,
  };
}
