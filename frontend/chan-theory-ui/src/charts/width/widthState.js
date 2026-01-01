// src/charts/width/widthState.js
// ==============================
// 说明：通用“宽度状态”单例（与 Vue 无关）
// - 职责：存放由 WidthController 计算出的“当前宽度”数值，供各类 series 的 symbolSize/样式函数读取。
// - 设计：
//   * 极简：纯 JS 变量 + get/set，不引入响应式，避免耦合与性能开销；
//   * 通用：不绑定“分型/涨跌/量窗”，只按 key 存值；
//   * 零副作用：不触发任何渲染，仅存取数据。
// ==============================

const _store = new Map();

/**
 * 设置某个宽度键的像素值
 * @param {string} key
 * @param {number|null} px
 */
export function setWidthPx(key, px) {
  const k = String(key || "").trim();
  if (!k) return;

  const n = Number(px);
  if (!Number.isFinite(n) || n <= 0) {
    // 冗余清理：无此 key 则无需 delete
    if (_store.has(k)) _store.delete(k);
    return;
  }

  // 冗余清理：同值短路，避免高频重复写入 Map
  const prev = _store.get(k);
  if (Number.isFinite(prev) && prev === n) return;

  _store.set(k, n);
}

/**
 * 读取某个宽度键的像素值
 * @param {string} key
 * @param {number} fallback
 * @returns {number}
 */
export function getWidthPx(key, fallback = 8) {
  const k = String(key || "").trim();
  const v = _store.get(k);
  const n = Number(v);
  if (Number.isFinite(n) && n > 0) return n;

  const fb = Number(fallback);
  return Number.isFinite(fb) && fb > 0 ? fb : 8;
}

/**
 * 批量设置（便捷）
 * @param {Record<string, number|null>} map
 */
export function setWidthPxBatch(map) {
  const obj = map && typeof map === "object" ? map : {};
  for (const [k, v] of Object.entries(obj)) {
    setWidthPx(k, v);
  }
}

/**
 * 清空（仅调试/测试用途）
 */
export function clearWidthStore() {
  _store.clear();
}
