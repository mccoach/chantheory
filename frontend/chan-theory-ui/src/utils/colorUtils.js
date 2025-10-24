// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\utils\colorUtils.js
// ==============================
// 说明：颜色工具（通用，不含业务语义）
// - hexToRgba：十六进制 → rgba；alpha=0 时返回 'transparent'（用于空心填充）
// ==============================

/**
 * 将十六进制颜色转为 rgba 字符串
 * @param {string} hex - '#RRGGBB' 或 'RRGGBB'
 * @param {number} alpha - 透明度（0..1），当 alpha=0 返回 'transparent'
 * @returns {string} rgba(...) 或 'transparent'
 */
export function hexToRgba(hex, alpha = 1.0) {
  try {
    const a = Math.max(0, Math.min(1, Number(alpha ?? 1)));
    if (a === 0) return "transparent"; // 兼容语义：0→空心
    const h = String(hex || "").replace("#", "");
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    if ([r, g, b].some((v) => Number.isNaN(v))) throw new Error("bad hex");
    return `rgba(${r},${g},${b},${a})`;
  } catch {
    // 失败：回退到原 hex 或默认占位色
    return hex || "#999";
  }
}