// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\chan\fractals.js
// ==============================
// 说明：从 useChan.js 拆分出的分型识别模块
// - 核心职责：从合并K线序列中识别顶分型和底分型。
// - 算法：采用非重叠扫描，按岛（seq_id）独立进行。
// ==============================

/**
 * 分型识别（非重叠扫描）——输出新命名
 * 变更：按 seq_id 分岛执行，不跨岛；输出新增 seq_id 字段。
 */
export function computeFractals(reducedBars, params = {}) {
  const out = [];
  const N = Array.isArray(reducedBars) ? reducedBars.length : 0;
  if (N < 3) return out;

  // 分岛分组
  const bySeq = new Map();
  for (let i = 0; i < N; i++) {
    const rb = reducedBars[i];
    const sid = Number(rb?.seq_id || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push({ rb, idx: i });
  }

  // 原参数解析
  const minTickCount = Math.max(0, Number(params.minTickCount || 0));
  const minPct = Math.max(0, Number(params.minPct || 0)); // 百分比，0=关闭
  const minCond =
    params.minCond === "and" || params.minCond === "or" ? params.minCond : "or";

  // 工具
  function G(rb) { return Number(rb?.g_pri); }
  function D(rb) { return Number(rb?.d_pri); }
  function T(rb) { return String(rb?.end_t_iso || rb?.start_t_iso || ""); }
  function Dir(rb) { return Number(rb?.dir_int || 0); }
  function K2_ORIG(rb, fallback) { return Number.isFinite(+rb?.anchor_idx_orig) ? +rb.anchor_idx_orig : fallback; }
  function K_RED(idx) { return Number(idx); }

  function estimateTickUnit(bars) {
    let unit = Infinity;
    const take = Math.min(bars.length, 200);
    for (let i = Math.max(0, bars.length - take); i < bars.length; i++) {
      const a = bars[i];
      if (!a) continue;
      const vals = [G(a.rb), D(a.rb)];
      for (const v of vals) {
        if (!Number.isFinite(v)) continue;
        for (let j = i - 3; j <= i + 3; j++) {
          if (j < 0 || j >= bars.length || j === i) continue;
          const b = bars[j];
          if (!b) continue;
          const vals2 = [G(b.rb), D(b.rb)];
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
  const tickUnitGlobal = minTickCount > 0 ? estimateTickUnit(reducedBars) : null;

  function passSignificanceTop(g2, g1, g3, tickUnit) {
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
  function passSignificanceBottom(d2, d1, d3, tickUnit) {
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

  // 分岛执行
  for (const [sid, arr] of bySeq.entries()) {
    if (!arr || arr.length < 3) continue;

    const tickUnit = minTickCount > 0 ? estimateTickUnit(arr) : tickUnitGlobal;
    let i = 0;
    while (i + 2 < arr.length) {
      const b1 = arr[i].rb, b2 = arr[i + 1].rb, b3 = arr[i + 2].rb;
      const d2 = Dir(b2), d3 = Dir(b3);
      const G1 = G(b1), D1 = D(b1), G2 = G(b2), D2 = D(b2), G3 = G(b3), D3 = D(b3);
      const t1 = T(b1), t2 = T(b2), t3 = T(b3);
      const M1 = (G1 + D1) / 2;
      const k1r = arr[i].idx, k2r = arr[i + 1].idx, k3r = arr[i + 2].idx;
      const k2_idx_orig = K2_ORIG(b2, k2r);

      if (d2 > 0 && d3 < 0) {
        if (passSignificanceTop(G2, G1, G3, tickUnit)) {
          let strength = "standard";
          if (D3 < D1) strength = "strong";
          else if (D3 > M1) strength = "weak";
          out.push({
            id_str: `F-${k1r}-${k2r}-${k3r}-top`,
            kind_enum: "top",
            k1_idx_red: K_RED(k1r),
            k2_idx_red: K_RED(k2r),
            k3_idx_red: K_RED(k3r),
            k1_t_iso: t1,
            k2_t_iso: t2,
            k3_t_iso: t3,
            k1_g_pri: G1,
            k1_d_pri: D1,
            k2_g_pri: G2,
            k2_d_pri: D2,
            k3_g_pri: G3,
            k3_d_pri: D3,
            k1_mid_pri: M1,
            k2_idx_orig,
            strength_enum: strength,
            dir_seq_str: "+-",
            min_tick_cnt_int: minTickCount,
            min_pct_num: minPct,
            min_cond_enum: minCond,
            algo_ver_str: "fractal_v1.0",
            sig_tick_ok_bool: minTickCount === 0 || !!tickUnit,
            sig_pct_ok_bool: minPct === 0,
            cf_paired_bool: false,
            cf_pair_id_str: undefined,
            cf_role_enum: undefined,
            labels_arr: ["fractal", "top"],
            note_str: "",
            seq_id: sid,
          });
          i += 1;
          continue;
        }
      }

      if (d2 < 0 && d3 > 0) {
        if (passSignificanceBottom(D2, D1, D3, tickUnit)) {
          let strength = "standard";
          if (G3 > G1) strength = "strong";
          else if (G3 < M1) strength = "weak";
          out.push({
            id_str: `F-${k1r}-${k2r}-${k3r}-bottom`,
            kind_enum: "bottom",
            k1_idx_red: K_RED(k1r),
            k2_idx_red: K_RED(k2r),
            k3_idx_red: K_RED(k3r),
            k1_t_iso: t1,
            k2_t_iso: t2,
            k3_t_iso: t3,
            k1_g_pri: G1,
            k1_d_pri: D1,
            k2_g_pri: G2,
            k2_d_pri: D2,
            k3_g_pri: G3,
            k3_d_pri: D3,
            k1_mid_pri: M1,
            k2_idx_orig,
            strength_enum: strength,
            dir_seq_str: "-+",
            min_tick_cnt_int: minTickCount,
            min_pct_num: minPct,
            min_cond_enum: minCond,
            algo_ver_str: "fractal_v1.0",
            sig_tick_ok_bool: minTickCount === 0 || !!tickUnit,
            sig_pct_ok_bool: minPct === 0,
            cf_paired_bool: false,
            cf_pair_id_str: undefined,
            cf_role_enum: undefined,
            labels_arr: ["fractal", "bottom"],
            note_str: "",
            seq_id: sid,
          });
          i += 1;
          continue;
        }
      }
      i += 1;
    }

    // 确认分型：仅同 sid 内配对
    const groupOut = out.filter((f) => f.seq_id === sid);
    const byStartRed = new Map();
    for (const f of groupOut) {
      const arr2 = byStartRed.get(f.k1_idx_red) || [];
      arr2.push(f);
      byStartRed.set(f.k1_idx_red, arr2);
    }
    for (const a of groupOut) {
      if (a.cf_paired_bool) continue;
      const candidates = byStartRed.get(a.k3_idx_red + 1) || [];
      for (const b of candidates) {
        if (a.kind_enum !== b.kind_enum) continue;
        if (a.kind_enum === "top") {
          const G2 = a.k2_g_pri, G3 = a.k3_g_pri, D3 = a.k3_d_pri;
          const G4 = b.k1_g_pri, D4 = b.k1_d_pri, G5 = b.k2_g_pri;
          if (G5 < G2 && G4 < G3 && D4 < D3) {
            a.cf_paired_bool = true;
            a.cf_pair_id_str = `${a.id_str}|${b.id_str}`;
            a.cf_role_enum = "first";
            b.cf_paired_bool = true;
            b.cf_pair_id_str = `${a.id_str}|${b.id_str}`;
            b.cf_role_enum = "second";
            break;
          }
        } else {
          const D2 = a.k2_d_pri, D3 = a.k3_d_pri, G3 = a.k3_g_pri;
          const G4 = b.k1_g_pri, D4 = b.k1_d_pri, D5 = b.k2_d_pri;
          if (D5 > D2 && D4 > D3 && G4 > G3) {
            a.cf_paired_bool = true;
            a.cf_pair_id_str = `${a.id_str}|${b.id_str}`;
            a.cf_role_enum = "first";
            b.cf_paired_bool = true;
            b.cf_pair_id_str = `${a.id_str}|${b.id_str}`;
            b.cf_role_enum = "second";
            break;
          }
        }
      }
    }
  }

  return out;
}
