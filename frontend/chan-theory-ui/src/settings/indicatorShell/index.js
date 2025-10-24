// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\indicatorShell\index.js
// ==============================
// 说明：指标窗设置壳的对外入口函数 openIndicatorSettings
// - 职责：通过全局 dialogManager 打开设置壳组件 IndicatorSettingsShell.vue。
// - 逻辑：
//   * 根据传入的 initialKind 确定 activeTab。
//   * VOL 和 AMOUNT 共享同一个 "量窗" 标签页。
//   * 为所有支持的指标构建 tabs 数组。
// ==============================

export async function openIndicatorSettings(dialogManager, { initialKind = "VOL" } = {}) {
  if (!dialogManager || typeof dialogManager.open !== "function") {
    console.warn("[settings/indicatorShell] dialogManager is required");
    return;
  }
  const mod = await import(/* @vite-ignore */ "./IndicatorSettingsShell.vue");
  const Shell = mod.default;

  const tabs = [
    { key: "VOL", label: "量窗" }, // VOL 和 AMOUNT 共用
    { key: "MACD", label: "MACD" },
    { key: "KDJ", label: "KDJ" },
    { key: "RSI", label: "RSI" },
    { key: "BOLL", label: "BOLL" },
  ];

  // 如果 initialKind 是 AMOUNT，则激活 VOL 标签页
  const activeTab = String(initialKind).toUpperCase() === 'AMOUNT' ? 'VOL' : String(initialKind).toUpperCase();

  dialogManager.open({
    title: "副图指标设置",
    contentComponent: Shell,
    props: { initialKind }, // 传递初始 kind，以便 Shell 内部知道上下文
    tabs,
    activeTab,
    // 保存与重置逻辑已移至 App.vue，通过 ref 直接调用子组件方法
    onClose: () => {
      try {
        dialogManager.close();
      } catch {}
    },
  });
}