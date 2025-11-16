// src/charts/options/index.js
// ==============================
// V2.0 - 更新导出路径
// ==============================

export { createFixedTooltipPositioner } from "./positioning/tooltip";  // ← 修改路径

export { buildMainChartOption } from "./builders/main";
export { buildVolumeOption } from "./builders/volume";
export { buildMacdOption } from "./builders/macd";
export { buildBollOption } from "./builders/boll";
export { buildKdjOrRsiOption } from "./builders/kdjRsi";

// ===== 新增：骨架生成器导出 =====
export { createTechSkeleton } from "./skeleton/tech";