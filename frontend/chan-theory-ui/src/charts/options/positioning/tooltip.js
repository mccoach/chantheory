// src/charts/options/positioning/tooltip.js
// ==============================
// V2.0 - 使用常量版
// ==============================
import { TOOLTIP_STYLE } from '@/constants/ui/tooltip'

let GLOBAL_TIP_SIDE = "left";

export function createFixedTooltipPositioner(defaultSide = "left", getOffset) {
  if (GLOBAL_TIP_SIDE !== "left" && GLOBAL_TIP_SIDE !== "right") {
    GLOBAL_TIP_SIDE = defaultSide === "right" ? "right" : "left";
  }
  return function (pos, _params, dom, _rect, size) {
    const host = dom && dom.parentElement ? dom.parentElement : null;
    const hostRect = host ? host.getBoundingClientRect() : { width: 800 };
    
    // ===== 修复：使用常量 =====
    const tipW = (size && size.contentSize && size.contentSize[0]) || TOOLTIP_STYLE.defaultWidth;
    const margin = TOOLTIP_STYLE.margin;
    const x = Array.isArray(pos) ? pos[0] : 0;
    const nearLeft = x <= tipW + margin + 12;
    const nearRight = hostRect.width - x <= tipW + margin + 12;
    if (nearLeft) GLOBAL_TIP_SIDE = "right";
    else if (nearRight) GLOBAL_TIP_SIDE = "left";

    const baseX =
      GLOBAL_TIP_SIDE === "left"
        ? margin
        : Math.max(margin, hostRect.width - tipW - margin);
    const baseY = TOOLTIP_STYLE.baseY;

    let off = { x: 0, y: 0 };
    try {
      const t = typeof getOffset === "function" ? getOffset() : null;
      if (t && typeof t.x === "number" && typeof t.y === "number") off = t;
    } catch {}
    return [baseX + (off.x || 0), baseY + (off.y || 0)];
  };
}