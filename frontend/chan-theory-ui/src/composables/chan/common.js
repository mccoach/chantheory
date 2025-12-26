// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\common.js
// ==============================
// Projection Layer（投影工具层，Idx-Only + 单一真相源）
//
// 最高约束：
//   - candles 是 ts / ohlc(/v/a...) 的唯一真相源（Single Source of Truth）。
//   - 任何业务元素对象（ReducedBar/Fractal/Pen/Segment/...）禁止存 ts/pri。
//   - “读取时间/价格/字段”必须以 idx_orig 回溯 candles，且应走本模块，避免各层重复造轮子。
//
// 本模块只做两类通用能力：
//   A) Candle Access：给 idx_orig 就能取任意字段（ts/o/h/l/c/v/a/...）
//   B) Generic Projection：把“某对象中的某索引字段（或索引空间）”解析成 idx_orig
//      - 不绑定任何层级语义；不内置“分型/笔/线段”的特殊规则；
//      - 调用方通过 spec（规则）告诉投影器：如何从对象拿到 idx_orig。
// ==============================

/**
 * 规范化 idx（只接受非负整数索引）
 * @param {any} x
 * @returns {number|null}
 */
export function toNonNegIntIdx(x) {
  const n = Number(x);
  if (!Number.isFinite(n)) return null;
  const i = Math.trunc(n);
  if (i !== n) return null;
  return i >= 0 ? i : null;
}

/**
 * 读取 candles[idx_orig]（idx_orig 为原始K线索引）
 * @param {Array<object>} candles
 * @param {number} idxOrig
 * @returns {object|null}
 */
export function candleAt(candles, idxOrig) {
  const arr = Array.isArray(candles) ? candles : [];
  const i = toNonNegIntIdx(idxOrig);
  if (i == null || i >= arr.length) return null;
  return arr[i] || null;
}

/**
 * 读取 candle 字段（返回 number|null；不做单位转换/业务语义）
 * - 这是“读取时间/价格/成交量/成交额”的统一出口
 *
 * @param {Array<object>} candles
 * @param {number} idxOrig
 * @param {string} field - 任意字段名，如 'ts'|'o'|'h'|'l'|'c'|'v'|'a'|'tr'...
 * @returns {number|null}
 */
export function candleNum(candles, idxOrig, field) {
  const k = candleAt(candles, idxOrig);
  if (!k) return null;
  const v = k?.[field];
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * 读取 candle 的任意字段（不强制 number）
 * @param {Array<object>} candles
 * @param {number} idxOrig
 * @param {string} field
 * @returns {any}
 */
export function candleGet(candles, idxOrig, field) {
  const k = candleAt(candles, idxOrig);
  if (!k) return null;
  return k?.[field];
}

/**
 * 批量读取一个 idx_orig 对应 candle 的多个字段（扁平返回）
 * @param {Array<object>} candles
 * @param {number} idxOrig
 * @param {Array<string>} fields
 * @returns {Object<string, any>}
 */
export function candlePick(candles, idxOrig, fields) {
  const k = candleAt(candles, idxOrig);
  const out = {};
  const fs = Array.isArray(fields) ? fields : [];
  if (!k) {
    for (const f of fs) out[f] = null;
    return out;
  }
  for (const f of fs) out[f] = k?.[f];
  return out;
}

/**
 * 常用快捷读取（完全通用，仅是 candleNum 的别名，便于调用���表达意图）
 * 注：这些函数不代表“业务语义”，只是字段快捷名。
 */
export function candleTs(candles, idxOrig) { return candleNum(candles, idxOrig, "ts"); }
export function candleO(candles, idxOrig) { return candleNum(candles, idxOrig, "o"); }
export function candleH(candles, idxOrig) { return candleNum(candles, idxOrig, "h"); }
export function candleL(candles, idxOrig) { return candleNum(candles, idxOrig, "l"); }
export function candleC(candles, idxOrig) { return candleNum(candles, idxOrig, "c"); }
export function candleV(candles, idxOrig) { return candleNum(candles, idxOrig, "v"); }
export function candleA(candles, idxOrig) { return candleNum(candles, idxOrig, "a"); }

/**
 * 提供一个“读取器”对象（可选；减少调用方重复传 candles）
 * @param {Array<object>} candles
 * @returns {{
 *   at: Function,
 *   num: Function,
 *   get: Function,
 *   pick: Function
 * }}
 */
export function createCandleReader(candles) {
  return {
    at: (idxOrig) => candleAt(candles, idxOrig),
    num: (idxOrig, field) => candleNum(candles, idxOrig, field),
    get: (idxOrig, field) => candleGet(candles, idxOrig, field),
    pick: (idxOrig, fields) => candlePick(candles, idxOrig, fields),
  };
}

// ==============================
// Anchor：动态推导（不存储）
// ==============================

/**
 * 承载点（Anchor）动态推导：不在 ReducedBar 上存 anchor_idx。
 *
 * policy:
 *   - 'left'   -> start_idx_orig
 *   - 'right'  -> end_idx_orig
 *   - 'extreme'-> dir_int>0 取 g_idx_orig；dir_int<0 取 d_idx_orig；dir_int==0 兜底 right
 *
 * @param {object} rb ReducedBar（Idx-Only Schema）
 * @param {'left'|'right'|'extreme'} policy
 * @returns {number|null} idx_orig
 */
export function resolveAnchorIdx(rb, policy) {
  if (!rb || typeof rb !== "object") return null;

  const p =
    policy === "left" || policy === "right" || policy === "extreme"
      ? policy
      : "right";

  const s = toNonNegIntIdx(rb.start_idx_orig);
  const e = toNonNegIntIdx(rb.end_idx_orig);
  const g = toNonNegIntIdx(rb.g_idx_orig);
  const d = toNonNegIntIdx(rb.d_idx_orig);

  if (p === "left") return s != null ? s : e;
  if (p === "right") return e != null ? e : s;

  const dir = Number(rb.dir_int || 0);
  if (dir > 0) return g != null ? g : (e != null ? e : s);
  if (dir < 0) return d != null ? d : (e != null ? e : s);

  // dir==0：兜底 right
  return e != null ? e : s;
}

// ==============================
// Generic Projection（通用递归投影器）
// ==============================
//
// 目标：让业务层“声明规则（spec）”，投影器负责把任意对象解析为 idx_orig。
// 这样：
//   - common 不绑定任何层级；
//   - 业务算法不再散落各种“idx_red->reducedBars->idx_orig”的重复代码；
//   - 同一个投影器可以跨层复用（ReducedBars/Pens/Segments/未来更多层）。
//
// spec 是一个“纯数据/少量回调”的描述对象：
//   - origKeys: 直接从 entity 读取 idx_orig 的字段名（string 或 string[]）
//   - from: 递归链：
//       * kind: 'red'|'pen'|'custom'
//       * keys: 在 entity 上取索引的字段名（string 或 string[]）
//       * pick: (containerItem, entity) => idx_orig   // 可选；默认尝试 containerItem 上的 origKeys
//       * next: 继续递归的 spec（用于 pen->...）
//
// 注意：投影器只做“索引解析”，不做“价格/时间语义”。价格/时间一律由 candle* 系列函数读取。
// ==============================

function asKeyList(x) {
  if (typeof x === "string" && x) return [x];
  return Array.isArray(x) ? x.filter((k) => typeof k === "string" && k) : [];
}

function readFirstIdxFromKeys(obj, keys) {
  const ks = asKeyList(keys);
  for (const k of ks) {
    const v = toNonNegIntIdx(obj?.[k]);
    if (v != null) return v;
  }
  return null;
}

function defaultPickIdxOrig(containerItem, _entity, defaultOrigKeys) {
  if (!containerItem || typeof containerItem !== "object") return null;
  return readFirstIdxFromKeys(containerItem, defaultOrigKeys);
}

/**
 * 创建通用投影器
 * @param {object} ctx
 * @param {Array<object>} [ctx.reducedBars]
 * @param {Array<object>} [ctx.pens]
 * @returns {{
 *   resolveIdxOrig: (entity:any, spec:object) => (number|null)
 * }}
 */
export function createProjector(ctx = {}) {
  const reducedBars = Array.isArray(ctx.reducedBars) ? ctx.reducedBars : null;
  const pens = Array.isArray(ctx.pens) ? ctx.pens : null;

  /**
   * 递归解析 idx_orig
   * @param {any} entity
   * @param {object} spec
   * @param {Set<any>} [seen]
   * @param {number} [depth]
   * @returns {number|null}
   */
  function resolveIdxOrig(entity, spec, seen = new Set(), depth = 0) {
    if (!entity || typeof entity !== "object") return null;
    if (!spec || typeof spec !== "object") return null;

    if (depth > 8) return null; // 防意外递归过深
    if (seen.has(entity)) return null;
    seen.add(entity);

    // 1) 直接 idx_orig
    const direct = readFirstIdxFromKeys(entity, spec.origKeys);
    if (direct != null) return direct;

    // 2) 递归链
    const from = spec.from;
    if (!from || typeof from !== "object") return null;

    const kind = String(from.kind || "").toLowerCase();
    const idx = readFirstIdxFromKeys(entity, from.keys);
    if (idx == null) return null;

    if (kind === "red") {
      if (!reducedBars || idx < 0 || idx >= reducedBars.length) return null;
      const rb = reducedBars[idx];

      // pick 返回 idx_orig；若未提供 pick，则默认从 rb 上按 spec.origKeys 尝试（由调用方决定 origKeys 是 start/end/g/d 等）
      const picked =
        typeof from.pick === "function"
          ? from.pick(rb, entity)
          : defaultPickIdxOrig(rb, entity, spec.origKeys);

      const p = toNonNegIntIdx(picked);
      return p != null ? p : null;
    }

    if (kind === "pen") {
      if (!pens || idx < 0 || idx >= pens.length) return null;
      const pen = pens[idx];

      // nextSpec：允许 pen->... 的进一步递归；否则尝试按 spec.origKeys 在 pen 上读取
      const nextSpec = from.next && typeof from.next === "object" ? from.next : null;

      if (nextSpec) {
        return resolveIdxOrig(pen, nextSpec, seen, depth + 1);
      }

      const picked =
        typeof from.pick === "function"
          ? from.pick(pen, entity)
          : readFirstIdxFromKeys(pen, spec.origKeys);

      const p = toNonNegIntIdx(picked);
      return p != null ? p : null;
    }

    if (kind === "custom") {
      // custom：调用方自定义容器与取值逻辑（不在 common 内做任何层级假设）
      // 约定：
      //   from.getContainer: (ctx) => Array|Object
      //   from.pick: (container, idx, entity) => idx_orig
      try {
        const container =
          typeof from.getContainer === "function" ? from.getContainer(ctx) : null;

        const picked =
          typeof from.pick === "function" ? from.pick(container, idx, entity) : null;

        const p = toNonNegIntIdx(picked);
        return p != null ? p : null;
      } catch {
        return null;
      }
    }

    return null;
  }

  return { resolveIdxOrig };
}
