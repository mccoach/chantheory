// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options\tooltips\positioner.js
// ==============================
// 说明：统一固定 tooltip 定位器（主/量/指标复用）
// - ESM 单例 GLOBAL_TIP_SIDE：在左右边缘自动切换“固定在左/右侧的容器内位置”
// - getOffset 可选：返回 {x,y} 叠加偏移
// ==============================

let GLOBAL_TIP_SIDE = "left";

export function createFixedTooltipPositioner(defaultSide = "left", getOffset) {
  if (GLOBAL_TIP_SIDE !== "left" && GLOBAL_TIP_SIDE !== "right") {
    GLOBAL_TIP_SIDE = defaultSide === "right" ? "right" : "left";
  }
  return function (pos, _params, dom, _rect, size) {
    const host = dom && dom.parentElement ? dom.parentElement : null;
    const hostRect = host ? host.getBoundingClientRect() : { width: 800 };
    const tipW = (size && size.contentSize && size.contentSize[0]) || 260;
    const margin = 8;
    const x = Array.isArray(pos) ? pos[0] : 0;
    const nearLeft = x <= tipW + margin + 12;
    const nearRight = hostRect.width - x <= tipW + margin + 12;
    if (nearLeft) GLOBAL_TIP_SIDE = "right";
    else if (nearRight) GLOBAL_TIP_SIDE = "left";

    const baseX =
      GLOBAL_TIP_SIDE === "left"
        ? margin
        : Math.max(margin, hostRect.width - tipW - margin);
    const baseY = 8;

    let off = { x: 0, y: 0 };
    try {
      const t = typeof getOffset === "function" ? getOffset() : null;
      if (t && typeof t.x === "number" && typeof t.y === "number") off = t;
    } catch {}
    return [baseX + (off.x || 0), baseY + (off.y || 0)];
  };
}