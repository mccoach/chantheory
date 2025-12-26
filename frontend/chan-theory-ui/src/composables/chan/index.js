// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\index.js
// ==============================
// 说明：拆分后的缠论算法模块的统一出口 (Barrel File)
// - 职责：聚合所有独立的算法模块，提供单一的引用入口。
// - 优点：上游模块（如 useViewRenderHub）无需关心内部文件结构，便于未来维护。
// ==============================

export { detectContinuityBarriers } from './barriers';
export { computeInclude } from './include';
export { computeFractals, computeFractalConfirmPairs } from './fractals';
export { computePens } from './pens';
export { computeSegments } from './segments';
export { computePenPivots } from './pivots';