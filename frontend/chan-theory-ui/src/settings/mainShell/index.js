// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\mainShell\index.js
// ==============================
// 说明：主窗设置壳的对外入口函数 openMainChartSettings
// - 职责：通过全局 dialogManager 打开设置壳组件 MainChartSettingsShell.vue。
// - 简化：移除 onSave/onResetAll 回调。保存和重置逻辑将由 App.vue 通过 ref 直接调用
//         MainChartSettingsShell.vue 实例上暴露的方法来完成，不再通过事件。
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
    ],
    activeTab,
    // 保存与重置逻辑已移至 App.vue，通过 ref 直接调用子组件方法
    onClose: () => {
      try {
        dialogManager.close();
      } catch {}
    },
  });
}
