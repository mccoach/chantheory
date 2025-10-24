// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\utils\objectUtils.js
// ==============================
// 说明：通用的对象处理工具函数
// - deepMerge: 递归深度合并对象，用于 settings 加载和合并。
// ==============================

/**
 * 递归深度合并一个或多个源对象的属性到目标对象。
 * @param {object} target - 目标对象，将被修改。
 * @param {...object} sources - 一个或多个源对象。
 * @returns {object} - 返回修改后的目标对象。
 */
export function deepMerge(target, ...sources) {
  if (!sources.length) {
    return target;
  }
  const source = sources.shift();

  if (target && typeof target === 'object' && source && typeof source === 'object') {
    for (const key in source) {
      if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
        if (!target[key]) {
          Object.assign(target, { [key]: {} });
        }
        deepMerge(target[key], source[key]);
      } else {
        Object.assign(target, { [key]: source[key] });
      }
    }
  }

  return deepMerge(target, ...sources);
}
