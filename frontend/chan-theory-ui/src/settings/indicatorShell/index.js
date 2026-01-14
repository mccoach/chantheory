// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\indicatorShell\index.js
// ==============================
// 说明：指标窗设置壳的对外入口函数 openIndicatorSettings
//
// V3.0 - footerActions 统一版
// 目标：所有弹窗底部按钮统一由 ModalDialog 渲染；业务通过 footerActions 配置。
//
// V4.0 - Dialog Action Contract（纯 key）
// 变更：footerActions 不再携带 onClick；只声明 key/label。
//       具体执行由 App.vue 按 action.key 路由到内容组件 expose 的 dialogActions[key]。
// ==============================

export async function openIndicatorSettings(dialogManager, { initialKind = "VOL" } = {}) {
  if (!dialogManager || typeof dialogManager.open !== "function") {
    console.warn("[settings/indicatorShell] dialogManager is required");
    return;
  }
  const mod = await import(/* @vite-ignore */ "./IndicatorSettingsShell.vue");
  const Shell = mod.default;

  const tabs = [
    { key: "VOL", label: "量窗" },
    { key: "MACD", label: "MACD" },
    { key: "KDJ", label: "KDJ" },
    { key: "RSI", label: "RSI" },
    { key: "BOLL", label: "BOLL" },
  ];

  const activeTab = String(initialKind).toUpperCase() === "AMOUNT"
    ? "VOL"
    : String(initialKind).toUpperCase();

  dialogManager.open({
    title: "副图指标设置",
    contentComponent: Shell,
    props: { initialKind },
    tabs,
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
