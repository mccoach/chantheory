// src/settings/localImport/index.js
// ==============================
// 说明：盘后导入弹窗入口（UI 配置下沉）
// 职责：
//   - 统一封装“打开盘后导入弹窗”的 dialog 配置
//   - 让 SymbolPanel 回归“只负责 UI 和用户动作”
// 设计：
//   - 不承载导入业务
//   - 不承载状态
//   - 纯入口函数
// ==============================

export async function openLocalImportDialog(dialogManager) {
  if (!dialogManager || typeof dialogManager.open !== "function") {
    console.warn("[settings/localImport] dialogManager is required");
    return;
  }

  const mod = await import("@/components/ui/LocalImportDialog.vue");

  dialogManager.open({
    title: "盘后数据导入",
    contentComponent: mod.default,
    props: {},
    footerActions: [
      {
        key: "start_import",
        label: "开始导入",
        variant: "ok",
        disabled: false,
      },
      {
        key: "cancel_import",
        label: "停止导入",
        disabled: false,
      },
      {
        key: "retry_import",
        label: "重试失败",
        disabled: false,
      },
      {
        key: "close",
        label: "关闭",
      },
    ],
  });
}
