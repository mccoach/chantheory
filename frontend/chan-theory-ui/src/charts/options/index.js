// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\options\index.js
// ==============================
// 说明：charts/options 聚合出口（对外接口与签名保持不变）
// - 删除旧文件 src/charts/options.js，改为目录 + index.js 聚合导出
// - 外部继续使用 import { ... } from "@/charts/options"
// ==============================

export { createFixedTooltipPositioner } from "./tooltips/positioner";

export { buildMainChartOption } from "./builders/main";
export { buildVolumeOption } from "./builders/volume";
export { buildMacdOption } from "./builders/macd";
export { buildBollOption } from "./builders/boll";
export { buildKdjOrRsiOption } from "./builders/kdjRsi";
