// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\index.js
// ==============================
// 说明：拆分后的缠论图层模块的统一出口 (Barrel File)
// - 职责：聚合所有独立的图层构造器模块，提供单一的引用入口。
// - 优点：上游模块（如 useViewRenderHub）无需关心内部文件结构，便于未来维护。
// ==============================

export { buildUpDownMarkers } from './upDownMarkers';
export { buildFractalMarkers } from './fractals';
export { buildPenLines } from './pens';
export { buildSegmentLines } from './segments';
export { buildBarrierLines } from './barriers';
export { buildPenPivotAreas } from './pivots';
