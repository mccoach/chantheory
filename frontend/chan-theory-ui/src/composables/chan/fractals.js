// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\fractals.js
// ==============================
// 说明：分型识别模块（Idx-Only Schema 版 + 确认分型派生结构）
// - 核心职责：从合并K线序列（ReducedBars）中识别顶分型与底分型。
// - 单一真相源：任何价格/时间必须通过 idx_orig 回溯 candles 读取。
// - 输出：
//     1) computeFractals：严格按 Fractal Schema，仅包含关键索引与属性字段；严禁输出 ts/pri/cf_* 等字段。
//     2) computeFractalConfirmPairs：返回 confirmPairs 派生结构（与 fractals 同级），用于渲染确认分型与确认连线。
//        confirmPairs 本身也遵循 Idx-Only：只保存 fractals 数组下标，不保存任何价格/时间。
// ==============================

import { candleH, candleL, toNonNegIntIdx } from "./common";

/**
 * 分型识别（非重叠扫描）—— Idx-Only 输出
 *
 * Fractal Schema（必须满足）：
 *   - k1_idx_red, k2_idx_red, k3_idx_red（合并K序列索引）
 *   - k2_idx_orig（物理定位：顶/底极值点对应的原始K索引）
 *   - kind_enum（'top'|'bottom'）
 *   - strength_enum（'strong'|'standard'|'weak'）
 *   - seq_id
 *
 * @param {Array<object>} candles - 原始K线（唯一真相源）
 * @param {Array<object>} reducedBars - 合并K线（Idx-Only ReducedBar）
 * @param {object} params
 * @param {number} params.minTickCount
 * @param {number} params.minPct
 * @param {'and'|'or'} params.minCond
 * @returns {Array<object>} fractals（Idx-Only）
 */
export function computeFractals(candles, reducedBars, params = {}) {
  const out = [];
  const N = Array.isArray(reducedBars) ? reducedBars.length : 0;
  if (N < 3) return out;

  // ===== 参数解析（保持原逻辑语义）=====
  const minTickCount = Math.max(0, Number(params.minTickCount || 0));
  const minPct = Math.max(0, Number(params.minPct || 0)); // 百分比，0=关闭
  const minCond =
    params.minCond === "and" || params.minCond === "or" ? params.minCond : "or";

  // ===== 预计算：每根 ReducedBar 的 High/Low（从 candles 回溯）=====
  const highs = new Array(N);
  const lows = new Array(N);
  const seqIds = new Array(N);
  const dirs = new Array(N);

  for (let i = 0; i < N; i++) {
    const rb = reducedBars[i];
    seqIds[i] = Number(rb?.seq_id || 1);
    dirs[i] = Number(rb?.dir_int || 0);

    const gi = toNonNegIntIdx(rb?.g_idx_orig);
    const di = toNonNegIntIdx(rb?.d_idx_orig);

    const h = gi != null ? candleH(candles, gi) : null;
    const l = di != null ? candleL(candles, di) : null;

    highs[i] = Number.isFinite(h) ? h : NaN;
    lows[i] = Number.isFinite(l) ? l : NaN;
  }

  // ===== 分岛分组（按 seq_id 不跨岛扫描）=====
  const bySeq = new Map();
  for (let i = 0; i < N; i++) {
    const sid = Number(seqIds[i] || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push(i); // 存全局 idx_red
  }

  function estimateTickUnit(idxList) {
    // 原算法精神：从局部相邻范围估计最小价格单位（tick）
    // 这里只使用 highs/lows（从 candles 回溯得到），不存储任何 pri 字段。
    let unit = Infinity;
    const list = Array.isArray(idxList) ? idxList : [];
    const take = Math.min(list.length, 200);

    for (let ii = Math.max(0, list.length - take); ii < list.length; ii++) {
      const idx = list[ii];
      const vals = [highs[idx], lows[idx]];
      for (const v of vals) {
        if (!Number.isFinite(v)) continue;

        for (let jj = ii - 3; jj <= ii + 3; jj++) {
          if (jj < 0 || jj >= list.length || jj === ii) continue;
          const jdx = list[jj];
          const vals2 = [highs[jdx], lows[jdx]];
          for (const u of vals2) {
            if (!Number.isFinite(u)) continue;
            const diff = Math.abs(v - u);
            if (diff > 0 && diff < unit) unit = diff;
          }
        }
      }
    }

    if (!Number.isFinite(unit) || unit <= 0) return null;
    const rounded = Math.abs(Math.round(unit * 100) / 100);
    return rounded > 0 ? rounded : unit;
  }

  // 显著度判定（保持旧语义：tick 与 pct 可 OR/AND）
  function passTop(g2, g1, g3, tickUnit) {
    const tickOk =
      minTickCount <= 0
        ? true
        : tickUnit
        ? g2 - g1 >= minTickCount * tickUnit &&
          g2 - g3 >= minTickCount * tickUnit
        : true;

    const base = Math.max(Math.abs(g1), Math.abs(g3), 1);
    const pctOk =
      minPct <= 0
        ? true
        : ((g2 - g1) / base) * 100 >= minPct &&
          ((g2 - g3) / base) * 100 >= minPct;

    return minCond === "and" ? tickOk && pctOk : tickOk || pctOk;
  }

  function passBottom(d2, d1, d3, tickUnit) {
    const tickOk =
      minTickCount <= 0
        ? true
        : tickUnit
        ? d1 - d2 >= minTickCount * tickUnit &&
          d3 - d2 >= minTickCount * tickUnit
        : true;

    const base = Math.max(Math.abs(d1), Math.abs(d3), 1);
    const pctOk =
      minPct <= 0
        ? true
        : ((d1 - d2) / base) * 100 >= minPct &&
          ((d3 - d2) / base) * 100 >= minPct;

    return minCond === "and" ? tickOk && pctOk : tickOk || pctOk;
  }

  function k2IdxOrigFor(kind, k2Red) {
    const rb = reducedBars[k2Red];
    if (!rb) return null;

    if (kind === "top") {
      const gi = toNonNegIntIdx(rb.g_idx_orig);
      if (gi != null) return gi;
    } else {
      const di = toNonNegIntIdx(rb.d_idx_orig);
      if (di != null) return di;
    }

    // 极端情况下兜底到右端（仍是 idx_orig，非 ts/pri）
    const end = toNonNegIntIdx(rb.end_idx_orig);
    return end != null ? end : toNonNegIntIdx(rb.start_idx_orig);
  }

  // ===== 分岛执行：非重叠扫描（保持原有推进方式的窗口扫描语义）=====
  for (const [sid, idxList] of bySeq.entries()) {
    if (!idxList || idxList.length < 3) continue;

    const tickUnit = minTickCount > 0 ? estimateTickUnit(idxList) : null;

    for (let p = 0; p + 2 < idxList.length; p++) {
      const k1 = idxList[p];
      const k2 = idxList[p + 1];
      const k3 = idxList[p + 2];

      const d2 = Number(dirs[k2] || 0);
      const d3 = Number(dirs[k3] || 0);

      const G1 = highs[k1],
        D1 = lows[k1];
      const G2 = highs[k2],
        D2 = lows[k2];
      const G3 = highs[k3],
        D3 = lows[k3];

      if (![G1, D1, G2, D2, G3, D3].every((x) => Number.isFinite(x))) continue;

      const M1 = (G1 + D1) / 2;

      // 顶分：dir2 >0 且 dir3 <0
      if (d2 > 0 && d3 < 0) {
        if (!passTop(G2, G1, G3, tickUnit)) continue;

        let strength = "standard";
        if (D3 < D1) strength = "strong";
        else if (D3 > M1) strength = "weak";

        const k2_idx_orig = k2IdxOrigFor("top", k2);
        if (k2_idx_orig == null) continue;

        out.push({
          k1_idx_red: k1,
          k2_idx_red: k2,
          k3_idx_red: k3,
          k2_idx_orig,
          kind_enum: "top",
          strength_enum: strength,
          seq_id: sid,
        });

        continue;
      }

      // 底分：dir2 <0 且 dir3 >0
      if (d2 < 0 && d3 > 0) {
        if (!passBottom(D2, D1, D3, tickUnit)) continue;

        let strength = "standard";
        if (G3 > G1) strength = "strong";
        else if (G3 < M1) strength = "weak";

        const k2_idx_orig = k2IdxOrigFor("bottom", k2);
        if (k2_idx_orig == null) continue;

        out.push({
          k1_idx_red: k1,
          k2_idx_red: k2,
          k3_idx_red: k3,
          k2_idx_orig,
          kind_enum: "bottom",
          strength_enum: strength,
          seq_id: sid,
        });
      }
    }
  }

  return out;
}

/**
 * 计算“确认分型配对”——派生结构（Idx-Only）
 *
 * 旧实现回顾（你给的原代码）：
 *   - 在 fractal 对象上写入 cf_paired_bool/cf_pair_id_str/cf_role_enum；
 *   - 渲染层通过这些字段绘制确认分型标记与确认连线。
 *
 * 新实现（合规方式）：
 *   - 不修改 fractals 对象（保持其严格符合 Fractal Schema）；
 *   - 返回 confirmPairs：与 fractals 同级别的配对结构，用于指导渲染落地；
 *   - confirmPairs 自身也不存 ts/pri，只存 fractal 下标及少量属性。
 *
 * 返回结构：
 * {
 *   pairs: Array<{ a:number, b:number, kind_enum:'top'|'bottom', seq_id:number }>,
 *   paired: boolean[],   // 与 fractals 等长
 *   role: Array<('first'|'second'|null)> // 与 fractals 等长
 * }
 *
 * @param {Array<object>} candles
 * @param {Array<object>} reducedBars
 * @param {Array<object>} fractals - Idx-Only fractals（computeFractals 的输出）
 * @returns {object} confirmPairs
 */
export function computeFractalConfirmPairs(candles, reducedBars, fractals) {
  const fr = Array.isArray(fractals) ? fractals : [];
  const rbArr = Array.isArray(reducedBars) ? reducedBars : [];

  const paired = new Array(fr.length).fill(false);
  const role = new Array(fr.length).fill(null);
  const pairs = [];

  if (!fr.length || rbArr.length === 0) {
    return { pairs, paired, role };
  }

  // reducedBars 的高/低（均通过 idx_orig 回溯 candles）
  function G(redIdx) {
    const i = toNonNegIntIdx(redIdx);
    if (i == null || i >= rbArr.length) return NaN;
    const gi = toNonNegIntIdx(rbArr[i]?.g_idx_orig);
    if (gi == null) return NaN;
    const v = candleH(candles, gi);
    return Number.isFinite(v) ? v : NaN;
  }
  function D(redIdx) {
    const i = toNonNegIntIdx(redIdx);
    if (i == null || i >= rbArr.length) return NaN;
    const di = toNonNegIntIdx(rbArr[i]?.d_idx_orig);
    if (di == null) return NaN;
    const v = candleL(candles, di);
    return Number.isFinite(v) ? v : NaN;
  }

  // 1) 分岛：仅在同 seq_id 内配对（严格回归旧规则）
  const bySeq = new Map(); // seq_id -> fractalIndex[]
  for (let i = 0; i < fr.length; i++) {
    const sid = Number(fr[i]?.seq_id || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push(i);
  }

  // 2) 对每个岛：构建 byStartRed：k1_idx_red -> fractalIndex[]
  for (const [sid, idxList] of bySeq.entries()) {
    const group = Array.isArray(idxList) ? idxList : [];
    if (!group.length) continue;

    const byStartRed = new Map();
    for (const fi of group) {
      const k1r = toNonNegIntIdx(fr[fi]?.k1_idx_red);
      if (k1r == null) continue;
      const arr = byStartRed.get(k1r) || [];
      arr.push(fi);
      byStartRed.set(k1r, arr);
    }

    // 3) 按旧逻辑：遍历 a，查候选 b（b 的 k1_idx_red == a.k3_idx_red + 1）
    for (const aIdx of group) {
      if (paired[aIdx]) continue;

      const a = fr[aIdx];
      if (!a) continue;

      const k3a = toNonNegIntIdx(a.k3_idx_red);
      if (k3a == null) continue;

      const candidates = byStartRed.get(k3a + 1) || [];
      if (!candidates.length) continue;

      const aKind = String(a.kind_enum || "");
      if (aKind !== "top" && aKind !== "bottom") continue;

      for (const bIdx of candidates) {
        if (paired[aIdx]) break;
        if (paired[bIdx]) continue;

        const b = fr[bIdx];
        if (!b) continue;

        if (String(b.kind_enum || "") !== aKind) continue;

        // ===== 旧判定��件逐项等价回归（但数值从 candles 回溯） =====
        if (aKind === "top") {
          const G2a = G(a.k2_idx_red);
          const G3a = G(a.k3_idx_red);
          const D3a = D(a.k3_idx_red);

          const G4b = G(b.k1_idx_red);
          const D4b = D(b.k1_idx_red);
          const G5b = G(b.k2_idx_red);

          if (![G2a, G3a, D3a, G4b, D4b, G5b].every((x) => Number.isFinite(x))) {
            continue;
          }

          // 原条件：G5b < G2a && G4b < G3a && D4b < D3a
          if (G5b < G2a && G4b < G3a && D4b < D3a) {
            paired[aIdx] = true;
            paired[bIdx] = true;
            role[aIdx] = "first";
            role[bIdx] = "second";
            pairs.push({ a: aIdx, b: bIdx, kind_enum: "top", seq_id: sid });
            break;
          }
        } else {
          const D2a = D(a.k2_idx_red);
          const D3a = D(a.k3_idx_red);
          const G3a = G(a.k3_idx_red);

          const G4b = G(b.k1_idx_red);
          const D4b = D(b.k1_idx_red);
          const D5b = D(b.k2_idx_red);

          if (![D2a, D3a, G3a, G4b, D4b, D5b].every((x) => Number.isFinite(x))) {
            continue;
          }

          // 原条件：D5b > D2a && D4b > D3a && G4b > G3a
          if (D5b > D2a && D4b > D3a && G4b > G3a) {
            paired[aIdx] = true;
            paired[bIdx] = true;
            role[aIdx] = "first";
            role[bIdx] = "second";
            pairs.push({ a: aIdx, b: bIdx, kind_enum: "bottom", seq_id: sid });
            break;
          }
        }
      }
    }
  }

  return { pairs, paired, role };
}
