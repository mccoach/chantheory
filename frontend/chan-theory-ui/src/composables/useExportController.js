// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useExportController.js
// ==============================
// 说明：导出控制器（注册/互斥/统一参数）
// 变更要点：
// - 默认背景/像素比从 DEFAULT_EXPORT_SETTINGS 引用，不再在此写死。
// 其他逻辑（互斥/能力发现/状态）保持不变。
// ==============================

import { ref } from "vue"; // 响应式
import { DEFAULT_EXPORT_SETTINGS } from "@/constants"; // 集中默认：导出设置

export function useExportController(options = {}) {
  // 创建控制器
  const registry = new Map(); // 目标注册表
  const exporting = ref(false); // 导出中标志

  const isBusy =
    typeof options.isBusy === "function" ? options.isBusy : () => false; // 忙判定
  const filenameBuilder =
    typeof options.filenameBuilder === "function"
      ? options.filenameBuilder
      : (format) => {
          const now = new Date();
          const pad = (n) => String(n).padStart(2, "0");
          const stamp =
            [
              now.getFullYear(),
              pad(now.getMonth() + 1),
              pad(now.getDate()),
            ].join("") +
            "-" +
            [
              pad(now.getHours()),
              pad(now.getMinutes()),
              pad(now.getSeconds()),
            ].join("");
          return `export-${stamp}.${format}`;
        };

  // 改用集中默认：背景/像素比
  const defaultParams = {
    background: DEFAULT_EXPORT_SETTINGS.background, // 统一背景
    pixelRatio: DEFAULT_EXPORT_SETTINGS.pixelRatio, // 统一像素比
  };

  function register(targetId, impl, meta = {}) {
    registry.set(targetId, { impl, meta });
  } // 注册
  function unregister(targetId) {
    registry.delete(targetId);
  } // 注销
  function listTargets() {
    return Array.from(registry.keys());
  } // 目标列表
  function listFormats(targetId) {
    // 可用格式
    const entry = registry.get(targetId);
    if (!entry) return [];
    const { impl } = entry;
    return ["png", "jpg", "svg", "html"].filter(
      (k) => typeof impl[k] === "function"
    );
  }

  async function doExport(params) {
    // 统一导出入口
    if (exporting.value)
      return { ok: false, error: new Error("导出任务仍在进行中，请稍后") };
    if (isBusy())
      return { ok: false, error: new Error("数据加载中，导出不可用") };
    const { targetId, format } = params || {};
    const entry = registry.get(targetId);
    if (!entry)
      return { ok: false, error: new Error(`导出目标未注册: ${targetId}`) };
    const fn = entry.impl[format];
    if (typeof fn !== "function")
      return { ok: false, error: new Error(`不支持的导出格式: ${format}`) };
    const filename = params.filename || filenameBuilder(format);
    const ctx = {
      filename,
      background: defaultParams.background,
      pixelRatio: defaultParams.pixelRatio,
      extra: params.extra || {},
    };
    exporting.value = true;
    try {
      await Promise.resolve(fn(ctx));
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err };
    } finally {
      exporting.value = false;
    }
  }

  return {
    register,
    unregister,
    listTargets,
    listFormats,
    export: doExport,
    exporting,
  };
}