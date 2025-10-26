// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\common\useSettingsResetter.js
// ==============================
// 说明：统一“重置到默认”链路的小模块（仅作用于草稿，不保存、不刷新）
// - 职���：从 constants 默认配置深拷贝片段，写入指定草稿路径。
// - API：createSettingsResetter({ draft, defaults }) → { resetAll(), resetPath(path) }
// - 特性：
//   * 严格深拷贝，确保默认源不受污染；
//   * 支持点路径（如 "mergedK.upColor"）；
//   * 无副作用：只更新草稿对象；保存/刷新由外层按钮控制。
// ==============================

/** 纯 JSON 深拷贝（足够覆盖当前设置对象结构） */
function deepClone(obj) {
  return obj == null ? obj : JSON.parse(JSON.stringify(obj));
}

/** 取嵌套路径的值（不存在返回 undefined） */
function getByPath(obj, path) {
  if (!obj || !path) return undefined;
  const keys = String(path).split(".");
  let cur = obj;
  for (const k of keys) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = cur[k];
  }
  return cur;
}

/** 写入嵌套路径（中间节点不存在则创建为纯对象） */
function setByPath(obj, path, value) {
  if (!obj || !path) return;
  const keys = String(path).split(".");
  const last = keys.pop();
  let cur = obj;
  for (const k of keys) {
    if (cur[k] == null || typeof cur[k] !== "object") cur[k] = {};
    cur = cur[k];
  }
  cur[last] = value;
}

/**
 * 工厂：创建设置重置器
 * @param {{ draft: object, defaults: object }} params
 * @returns {{ resetAll: Function, resetPath: Function }}
 */
export function createSettingsResetter({ draft, defaults }) {
  if (!draft || !defaults) {
    console.warn("[useSettingsResetter] invalid args: draft/defaults required");
  }
  return {
    /** 全量重置：将整个 draft 重置为 defaults 的深拷贝 */
    resetAll() {
      try {
        const cloned = deepClone(defaults);
        // 逐键覆盖而非整体替换，保持 draft 响应式对象引用不变
        Object.keys(draft).forEach((k) => delete draft[k]);
        Object.keys(cloned || {}).forEach((k) => (draft[k] = cloned[k]));
      } catch (e) {
        console.error("[useSettingsResetter.resetAll] failed:", e);
      }
    },
    /**
     * 单路径重置：将 draft[path] 重置为 defaults[path] 的深拷贝
     * @param {string} path
     */
    resetPath(path) {
      try {
        const src = getByPath(defaults, path);
        const cloned = deepClone(src);
        setByPath(draft, path, cloned);
      } catch (e) {
        console.error("[useSettingsResetter.resetPath] failed:", path, e);
      }
    },
  };
}
