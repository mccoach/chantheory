// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\mainShell\index.js
// ==============================
// 说明：主窗设置壳的对外入口函数 openMainChartSettings
//
// V3.0 - footerActions 统一版
// 目标：所有弹窗底部按钮统一由 ModalDialog 渲染；业务通过 footerActions 配置。
//
// V4.0 - Dialog Action Contract（纯 key）
// 变更：footerActions 不再携带 onClick；只声明 key/label。
//       具体执行由 App.vue 按 action.key 路由到内容组件 expose 的 dialogActions[key]。
// ==============================

export async function openMainChartSettings(dialogManager, { activeTab = "chan" } = {}) {
  if (!dialogManager || typeof dialogManager.open !== "function") {
    console.warn("[settings/mainShell] dialogManager is required");
    return;
  }
  const mod = await import(/* @vite-ignore */ "./MainChartSettingsShell.vue");
  const Shell = mod.default;

  dialogManager.open({
    title: "行情显示设置",
    contentComponent: Shell,
    props: { initialActiveTab: activeTab },
    tabs: [
      { key: "display", label: "行情显示" },
      { key: "chan", label: "缠论标记" },
      { key: "atr", label: "ATR止损" },
    ],
    activeTab,

    footerActions: [
      {
        key: "reset_all",
        label: "全部恢复默认",
      },
      {
        key: "save",
        label: "保存并关闭",
        variant: "ok",
      },
      {
        key: "close",
        label: "取消",
      },
    ],

    onClose: () => {
      try {
        dialogManager.close();
      } catch {}
    },
  });
}
