// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\accessors.js
// ==============================
// 说明：Chan 语义访问器（Semantic Accessors）
// 职责：
//   - 基于 candles（唯一真相源）+ idx_orig，对业务对象（fractal/pen/segment/reducedBar 等）进行“语义级回溯”
//   - 统一封装常用的端点价/价域/区间极值 idx 等派生读取，供算法与渲染复用
//
// 设计原则：
//   - 纯函数/无副作用：不缓存、不改写输入对象；
//   - 边界清晰：不实现任何识别算法（fractals/pens/segments/pivots），只做读取与派生；
//   - 复用既有基础层：依赖 chan/common.js 的 candleH/candleL/toNonNegIntIdx 等原子能力；
//   - API 命名直接表达语义：penEndpointY / segmentEndpointY / reducedBarRangeByExtreme / ...
// ==============================

import {
  candleH,
  candleL,
  toNonNegIntIdx,
  candleTs,
} from "./common";

/**
 * 创建 Chan 语义访问器
 * @param {Array<object>} candles - 原始K线（唯一真相源）
 */
export function createChanAccessors(candles) {
  const arr = Array.isArray(candles) ? candles : [];

  function _endpointIdxOrig(entity, which) {
    const idx =
      which === "start"
        ? toNonNegIntIdx(entity?.start_idx_orig)
        : toNonNegIntIdx(entity?.end_idx_orig);
    return idx != null ? idx : null;
  }

  /**
   * Pen/Segment 通用的端点价读取（按 dir_enum 语义）
   * 规则（系统统一约定）：
   *   - UP：start=low，end=high
   *   - DOWN：start=high，end=low
   *
   * @param {object} entity - {dir_enum,start_idx_orig,end_idx_orig}
   * @param {'start'|'end'} which
   * @returns {number} 端点价；非法时返回 NaN
   */
  function endpointYByDir(entity, which) {
    const dir = String(entity?.dir_enum || "").toUpperCase();
    const idx = _endpointIdxOrig(entity, which);
    if (idx == null) return NaN;

    if (dir === "UP") {
      return which === "start" ? candleL(arr, idx) : candleH(arr, idx);
    }
    if (dir === "DOWN") {
      return which === "start" ? candleH(arr, idx) : candleL(arr, idx);
    }
    return NaN;
  }

  /**
   * 读取一条笔在某端点的语义价
   * @param {object} pen
   * @param {'start'|'end'} which
   */
  function penEndpointY(pen, which) {
    return endpointYByDir(pen, which);
  }

  /**
   * 读取一条线段在某端点的语义价
   * @param {object} seg
   * @param {'start'|'end'} which
   */
  function segmentEndpointY(seg, which) {
    return endpointYByDir(seg, which);
  }

  /**
   * 读取一条笔的价域（lo/hi）
   * @param {object} pen
   * @returns {{lo:number, hi:number} | null}
   */
  function penRange(pen) {
    const a = penEndpointY(pen, "start");
    const b = penEndpointY(pen, "end");
    if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
    return { lo: Math.min(a, b), hi: Math.max(a, b) };
  }

  /**
   * 读取一条线段的价域（lo/hi）
   * @param {object} seg
   * @returns {{lo:number, hi:number} | null}
   */
  function segmentRange(seg) {
    const a = segmentEndpointY(seg, "start");
    const b = segmentEndpointY(seg, "end");
    if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
    return { lo: Math.min(a, b), hi: Math.max(a, b) };
  }

  /**
   * 读取笔端点 idx_orig（规范化）
   * @param {object} pen
   * @param {'start'|'end'} which
   * @returns {number|null}
   */
  function penIdxOrig(pen, which) {
    return _endpointIdxOrig(pen, which);
  }

  /**
   * 读取线段端点 idx_orig（规范化）
   * @param {object} seg
   * @param {'start'|'end'} which
   * @returns {number|null}
   */
  function segmentIdxOrig(seg, which) {
    return _endpointIdxOrig(seg, which);
  }

  /**
   * reducedBar 的极值价域（通过 g_idx_orig/d_idx_orig 回溯 candles）
   * - 这是 computeSegments.checkPair 需要的笔“价域”基础能力（原实现通过 rbHighByRedIdx/rbLowByRedIdx 计算）
   *
   * @param {object} rb - ReducedBar（Idx-Only）
   * @returns {{lo:number, hi:number} | null}
   */
  function reducedBarRangeByExtreme(rb) {
    const gi = toNonNegIntIdx(rb?.g_idx_orig);
    const di = toNonNegIntIdx(rb?.d_idx_orig);
    if (gi == null || di == null) return null;

    const hi = candleH(arr, gi);
    const lo = candleL(arr, di);

    if (!Number.isFinite(hi) || !Number.isFinite(lo)) return null;
    return { lo: Math.min(lo, hi), hi: Math.max(lo, hi) };
  }

  /**
   * 读取分型的语义价（top=>high, bottom=>low）
   * @param {object} fractal
   * @returns {number} 价；非法时 NaN
   */
  function fractalY(fractal) {
    const kind = String(fractal?.kind_enum || "");
    const idx = toNonNegIntIdx(fractal?.k2_idx_orig);
    if (idx == null) return NaN;
    if (kind === "top") return candleH(arr, idx);
    if (kind === "bottom") return candleL(arr, idx);
    return NaN;
  }

  /**
   * 区间极值点 idx_orig 查询（闭区间）
   * - dirUp=true：找最高点（high）
   * - dirUp=false：找最低点（low）
   *
   * @param {object} args
   * @param {number} args.leftIdxOrig
   * @param {number} args.rightIdxOrig
   * @param {boolean} args.dirUp
   * @returns {number|null} idx_orig
   */
  function findExtremeIdxInClosedRange({ leftIdxOrig, rightIdxOrig, dirUp }) {
    const a = toNonNegIntIdx(leftIdxOrig);
    const b = toNonNegIntIdx(rightIdxOrig);
    if (a == null || b == null) return null;

    const s = Math.min(a, b);
    const e = Math.max(a, b);

    let bestIdx = null;
    let bestVal = dirUp ? -Infinity : Infinity;

    for (let i = s; i <= e; i++) {
      const v = dirUp ? candleH(arr, i) : candleL(arr, i);
      if (!Number.isFinite(v)) continue;

      if (dirUp) {
        if (v > bestVal) {
          bestVal = v;
          bestIdx = i;
        }
      } else {
        if (v < bestVal) {
          bestVal = v;
          bestIdx = i;
        }
      }
    }

    return bestIdx;
  }

  /**
   * 读取 idx_orig 对应的 ts（毫秒），非法返回 null
   * @param {number} idxOrig
   * @returns {number|null}
   */
  function tsAt(idxOrig) {
    const v = candleTs(arr, idxOrig);
    return Number.isFinite(v) ? v : null;
  }

  return {
    candles: arr,

    // semantic
    penEndpointY,
    penRange,
    penIdxOrig,

    segmentEndpointY,
    segmentRange,
    segmentIdxOrig,

    reducedBarRangeByExtreme,

    fractalY,

    findExtremeIdxInClosedRange,

    // optional helpers
    tsAt,
  };
}
