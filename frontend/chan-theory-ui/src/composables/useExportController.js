// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useExportController.js
// 作用：提供“导出控制器”注册中心与统一调度；避免 App 通过 ref 紧耦合子组件
// 设计要点：
// - register/unregister：面板在挂载/卸载时注册/注销自身导出实现
// - export：统一入口，处理互斥、禁用规则（如加载中）、统一文件名策略与默认参数
// - listTargets/listFormats：能力发现，便于 UI（下拉菜单）动态展示
// - exporting：对外暴露导出中的状态，UI 可据此禁用按钮

import { ref } from "vue"; // 引入 Vue 的响应式能力

export function useExportController(options = {}) {
  // 目标注册表：Map<targetId, { impl, meta }>
  // - targetId：如 'main'（主图）、'volume'（成交量）、'indicator'（指标副图）
  // - impl：{ png?:fn, jpg?:fn, svg?:fn, html?:fn } 任一可缺省
  // - meta：可选元数据，如 getLabel() 返回用于 UI 展示的名称
  const registry = new Map(); // 使用 Map 管理，便于增删与能力查询

  // 导出中互斥状态：true 表示正在导出，避免并发导出拖垮主线程
  const exporting = ref(false); // 响应式状态，UI 可读

  // 业务态检测：是否允许导出（例如正在加载时禁用）
  // - 由上层注入函数 options.isBusy(): boolean，默认返回 false（不忙）
  const isBusy =
    typeof options.isBusy === "function" ? options.isBusy : () => false;

  // 文件名生成策略：由上层注入，默认退回简单策略（仅时间戳）
  // - 签名：filenameBuilder(format: 'png'|'jpg'|'svg'|'html'): string
  const filenameBuilder =
    typeof options.filenameBuilder === "function"
      ? options.filenameBuilder
      : (format) => {
          // 默认文件名：export-YYYYMMDD-HHmmss.ext
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

  // 默认导出参数：背景色与像素比，可按需覆盖
  const defaultParams = {
    background: "#111", // 背景色统一为深色，与页面视觉一致
    pixelRatio: 2, // 导出 PNG/JPG 的放大倍数
  };

  // 注册导出实现
  // - targetId: string
  // - impl: { png?: (ctx)=>Promise|void, jpg?:..., svg?:..., html?:... }
  // - meta: { getLabel?: ()=>string }（可选）
  function register(targetId, impl, meta = {}) {
    registry.set(targetId, { impl, meta }); // 将实现与元数据写入注册表
  }

  // 注销导出实现（面板卸载时调用）
  function unregister(targetId) {
    registry.delete(targetId); // 从注册表移除
  }

  // 查询当前已注册的目标 ID 列表（供 UI 展示）
  function listTargets() {
    return Array.from(registry.keys()); // 返回所有 key
  }

  // 查询某个目标支持的导出格式（返回可用格式数组）
  function listFormats(targetId) {
    const entry = registry.get(targetId); // 读取注册项
    if (!entry) return []; // 未注册则返回空
    const { impl } = entry; // 解构实现对象
    // 收集存在的键作为可用格式
    return ["png", "jpg", "svg", "html"].filter(
      (k) => typeof impl[k] === "function"
    );
  }

  // 统一导出入口
  // - params: { targetId: string, format: 'png'|'jpg'|'svg'|'html', filename?: string, extra?: object }
  // - 返回：Promise<{ ok: boolean, error?: any }>
  async function doExport(params) {
    // 若正在导出，直接拒绝（避免并发）
    if (exporting.value) {
      return { ok: false, error: new Error("导出任务仍在进行中，请稍后") }; // 返回错误信息
    }
    // 若业务侧处于忙碌（例如 vm.loading），拒绝导出
    if (isBusy()) {
      return { ok: false, error: new Error("数据加载中，导出不可用") }; // 返回错误
    }
    // 解析参数与默认值
    const { targetId, format } = params || {}; // 提取目标与格式
    const entry = registry.get(targetId); // 获取对应注册项
    if (!entry) {
      return { ok: false, error: new Error(`导出目标未注册: ${targetId}`) }; // 目标不存在
    }
    const fn = entry.impl[format]; // 查找指定格式的导出实现
    if (typeof fn !== "function") {
      return { ok: false, error: new Error(`不支持的导出格式: ${format}`) }; // 不支持该格式
    }
    // 构造上下文：文件名与通用参数（背景/像素比等）
    const filename = params.filename || filenameBuilder(format); // 文件名：优先使用入参，否则统一策略生成
    const ctx = {
      filename, // 期望的输出文件名（含扩展名）
      background: defaultParams.background, // 背景色
      pixelRatio: defaultParams.pixelRatio, // 放大倍数
      extra: params.extra || {}, // 透传扩展参数（预留）
    };
    // 切换互斥状态并尝试执行导出
    exporting.value = true; // 进入导出状态
    try {
      await Promise.resolve(fn(ctx)); // 兼容同步/异步实现
      return { ok: true }; // 成功返回
    } catch (err) {
      return { ok: false, error: err }; // 捕获异常并回传
    } finally {
      exporting.value = false; // 恢复状态
    }
  }

  // 对外暴露控制器接口
  return {
    // 注册/注销
    register, // 注册目标导出实现
    unregister, // 注销目标导出实现
    // 能力查询
    listTargets, // 查询已注册目标
    listFormats, // 查询目标可用格式
    // 统一导出
    export: doExport, // 执行导出
    // 状态
    exporting, // 导出中状态（UI 可读）
  };
}
