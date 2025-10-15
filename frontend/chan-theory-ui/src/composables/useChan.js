// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useChan.js
// ==============================
// 缠论最小实现（全量文件 · 改造版）
// - computeInclude：去包含 + 承载点（anchor_idx_orig）+ 动态屏障分岛（CONTINUITY_BARRIER.basePct）。
// - computeFractals：分型识别（非重叠扫描），输出 k1/k2/k3 新命名；横轴统一用 k2_idx_orig；分岛（seq_id）。
// - computePens（重写）：按“先修极值、再验三条、首尾相连、净距≥3（rid差≥4）、相等不视更大、不跨屏障”规则，仅返回最终笔序列。
// - computeSegments：识别元线段（不跨屏障）。
// - NEW: computePenPivots：识别“笔中枢”（矩形）——滑动 P1~P4 判定形成，随后向右延续，直至遇到完全在外的第一笔。
// 兼容层：为不影响现有覆盖层渲染，computePens 返回 { confirmed: pens, provisional: null, all: pens }。
// 备注：屏障阈值采用“静态阈值”口径：thr = basePct；仅在 i>=10 时生效；零厚度中枢不成立（upper>lower 为必要条件）。

import { CONTINUITY_BARRIER } from "@/constants";

// [REPLACE] useChan.js 内部屏障检测函数 —— 改为“相邻原始K + 静态阈值 + 前10日豁免”
/**
 * 连续性屏障检测（静态阈值版）
 * 规则：
 *  - 仅在 i>=10（前10个交易日豁免）时开始检测；
 *  - 取前一日收盘 prevC 与当日最高/最低 thisH/thisL；
 *  - 计算 risePct = |(thisH - prevC) / prevC|，dropPct = |(prevC - thisL) / prevC|；
 *  - 两者任一 ≥ basePct 则在 i 之前判定为屏障（set.add(i)）。
 * 返回：{ set, list }，list含调试信息。
 */
function _detectContinuityBarriers(candles, basePct) {
  const set = new Set();
  const list = [];
  const n = Array.isArray(candles) ? candles.length : 0;
  const thr = Math.max(0, Number(CONTINUITY_BARRIER?.basePct));
  // const thr = Math.max(0, Number(CONTINUITY_BARRIER?.basePct ?? basePct ?? 0.15));

  const C = (i) => Number(candles[i]?.c);
  const H = (i) => Number(candles[i]?.h ?? candles[i]?.high);
  const L = (i) => Number(candles[i]?.l ?? candles[i]?.low);

  for (let i = 1; i < n; i++) {
    // 前10个交易日视为连续（从第11个开始比对）
    if (i < 10) continue;
    const prevC = C(i - 1);
    const thisH = H(i);
    const thisL = L(i);
    if (!Number.isFinite(prevC) || prevC === 0) continue;
    if (!Number.isFinite(thisH) || !Number.isFinite(thisL)) continue;

    const risePct = Math.abs((thisH - prevC) / prevC);
    const dropPct = Math.abs((prevC - thisL) / prevC);
    if (risePct >= thr || dropPct >= thr) {
      set.add(i); // 屏障发生在 i 之前
      list.push({ iLeft: i - 1, iRight: i, risePct, dropPct, thrPct: thr });
    }
  }
  return { set, list };
}

// [MODIFY] computeInclude：恢复“相邻原始K + 静态阈值”的分岛开关；删除动态阈值逻辑
export function computeInclude(candles, opts = {}) {
  const anchorPolicy = opts.anchorPolicy === "extreme" ? "extreme" : "right";
  const N = Array.isArray(candles) ? candles.length : 0;
  const reduced = [];
  const map = new Array(N);
  let lastDir = 0;

  // 新增：按静态阈值检测原始K屏障（前10日豁免）
  const { set: barrierSet } = _detectContinuityBarriers(
    candles,
    CONTINUITY_BARRIER?.basePct
  );

  let seq_id = 0; // 连续性岛编号（从 1 起）

  const H = (i) => Number(candles[i]?.h ?? candles[i]?.high ?? NaN);
  const L = (i) => Number(candles[i]?.l ?? candles[i]?.low ?? NaN);
  const T_iso = (i) => String(candles[i]?.t ?? "");

  function relation(a, b) {
    const up = a.g_pri < b.g_pri && a.d_pri < b.d_pri;
    const dn = a.g_pri > b.g_pri && a.d_pri > b.d_pri;
    if (up) return +1;
    if (dn) return -1;
    return 0;
  }
  function decideDirection(a, prev, b) {
    if (a.dir_int !== 0) return a.dir_int;
    if (prev) {
      const r = relation(prev, a);
      if (r !== 0) return r;
    }
    if (lastDir !== 0) return lastDir;
    if (a.g_pri !== b.g_pri || a.d_pri !== b.d_pri)
      return b.g_pri - a.g_pri + (b.d_pri - a.d_pri) >= 0 ? +1 : -1;
    return +1;
  }
  function fillMapRange(s, e, reducedIndex, seqId) {
    for (let k = s; k <= e; k++) {
      map[k] = {
        reduced_idx: reducedIndex,
        role_str: k === reduced[reducedIndex].end_idx_orig ? "carrier" : "merged",
        seq_id: seqId,
      };
    }
  }

  for (let i = 0; i < N; i++) {
    const hi = H(i);
    const lo = L(i);
    if (!Number.isFinite(hi) || !Number.isFinite(lo)) continue;

    // —— 修改点：首根或屏障处开启新岛（相邻原始K + 静态阈值；前10日豁免） —— //
    const openNewSeq = i === 0 || barrierSet.has(i);
    if (openNewSeq) {
      seq_id = seq_id + 1;
      lastDir = 0;
    }

    const base = {
      start_idx_orig: i,
      end_idx_orig: i,
      g_pri: hi,
      d_pri: lo,
      dir_int: 0,
      start_t_iso: T_iso(i),
      end_t_iso: T_iso(i),
      g_idx_orig: i,
      d_idx_orig: i,
      anchor_idx_orig: i,
      reason_str: "normal",
      seq_id,
      barrier_after_prev_bool: openNewSeq && i > 0,
    };

    if (reduced.length === 0 || openNewSeq) {
      reduced.push(base);
      map[i] = { reduced_idx: reduced.length - 1, role_str: "carrier", seq_id };
      continue;
    }

    const a = reduced[reduced.length - 1];
    const b = base;
    const r = relation(a, b);

    if (r === +1 || r === -1) {
      // —— 删除：动态阈值判定与在 push 时开新岛 —— //
      // 仅保留方向入栈
      b.dir_int = r;
      lastDir = r;
      reduced.push(b);
      map[i] = { reduced_idx: reduced.length - 1, role_str: "carrier", seq_id };
      continue;
    }

    // r===0：包含合并（不跨岛）
    const prev = reduced.length >= 2 ? reduced[reduced.length - 2] : null;
    const trend = decideDirection(a, prev, b);
    a.dir_int = a.dir_int === 0 ? trend : a.dir_int;

    if (a.dir_int >= 0) {
      const prevHi = a.g_pri, prevLo = a.d_pri;
      const newHi = Math.max(a.g_pri, b.g_pri);
      const newLo = Math.max(a.d_pri, b.d_pri);
      a.g_pri = newHi; a.d_pri = newLo;
      if (newHi !== prevHi && newHi === b.g_pri) a.g_idx_orig = i;
      if (newLo !== prevLo && newLo === b.d_pri) a.d_idx_orig = i;
      a.end_idx_orig = i; a.end_t_iso = b.end_t_iso;
      a.reason_str = "inclusion-merge-up";
      lastDir = a.dir_int;
      a.anchor_idx_orig =
        anchorPolicy === "extreme"
          ? a.dir_int > 0
            ? a.g_idx_orig
            : a.d_idx_orig
          : a.end_idx_orig;
      fillMapRange(a.start_idx_orig, a.end_idx_orig, reduced.length - 1, a.seq_id);
    } else {
      const prevHi = a.g_pri, prevLo = a.d_pri;
      const newHi = Math.min(a.g_pri, b.g_pri);
      const newLo = Math.min(a.d_pri, b.d_pri);
      a.g_pri = newHi; a.d_pri = newLo;
      if (newHi !== prevHi && newHi === b.g_pri) a.g_idx_orig = i;
      if (newLo !== prevLo && newLo === b.d_pri) a.d_idx_orig = i;
      a.end_idx_orig = i; a.end_t_iso = b.end_t_iso;
      a.reason_str = "inclusion-merge-down";
      lastDir = a.dir_int;
      a.anchor_idx_orig =
        anchorPolicy === "extreme"
          ? a.dir_int < 0
            ? a.d_idx_orig
            : a.g_idx_orig
          : a.end_idx_orig;
      fillMapRange(a.start_idx_orig, a.end_idx_orig, reduced.length - 1, a.seq_id);
    }
  }

  // 单根映射补齐（若有）
  for (let j = 0; j < reduced.length; j++) {
    const rj = reduced[j];
    if (rj.start_idx_orig === rj.end_idx_orig) {
      map[rj.start_idx_orig] = { reduced_idx: j, role_str: "carrier", seq_id: rj.seq_id };
    }
  }

  const meta = {
    algo: "include_v1",
    anchorPolicy,
    generated_at: new Date().toISOString(),
  };
  return { reducedBars: reduced, mapOrigToReduced: map, meta };
}

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

/**
 * 识别笔 —— 重写版（遵循“先修极值、再验三条/首尾相连/净距≥3/不跨屏障/相等不触发修正”）
 * 参数：
 *  - reducedBars：合并K序列
 *  - fractals：computeFractals 的输出数组
 *  - mapOrigToReduced：未用（保留签名兼容）
 *  - params.minGapReduced：最小间距阈值（默认 4），rid差≥4 ⇔ 净距≥3
 * 返回：
 *  { confirmed: pensArray, provisional: null, all: pensArray }
 * 变更：仅在同 seq_id 内识别与推进；笔对象新增 seq_id。
 */
export function computePens(
  reducedBars,
  fractals,
  _mapOrigToReduced,
  params = {}
) {
  const pens = [];
  const MIN_GAP = Math.max(1, Number(params?.minGapReduced ?? 4));

  // 分岛：按 seq_id 将 fractals 分组
  const bySeq = new Map();
  for (const f of Array.isArray(fractals) ? fractals : []) {
    const sid = Number(f?.seq_id || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push(f);
  }

  // id->索引映射（用于 pen 中回填 start/end 的 fractal 索引）
  const id2idxGlobal = new Map();
  (Array.isArray(fractals) ? fractals : []).forEach((f, i) => {
    if (f?.id_str) id2idxGlobal.set(String(f.id_str), i);
  });

  function ridGap(S, E) {
    if (!S || !E) return -1;
    return Number(E.k2_idx_red) - Number(S.k2_idx_red);
  }
  function gapOK(S, E) {
    const g = ridGap(S, E);
    return g >= MIN_GAP;
  }
  function isOppositePair(S, E) {
    if (!S || !E) return false;
    const a = String(S.kind_enum || "");
    const b = String(E.kind_enum || "");
    return (a === "bottom" && b === "top") || (a === "top" && b === "bottom");
  }
  // 区间极值排他（开区间），返回 {ok, fix, culprit}
  function exclusivityOK(S, E, frArr) {
    if (!S || !E) return { ok: false, fix: null, culprit: null };
    const left = Number(S.k2_idx_red), right = Number(E.k2_idx_red);
    if (right - left <= 1) return { ok: true, fix: null, culprit: null };
    const l = Math.min(left, right), r = Math.max(left, right);
    for (const f of frArr || []) {
      const rid = Number(f.k2_idx_red);
      if (rid <= l || rid >= r) continue; // 开区间
      if (S.kind_enum === "bottom" && E.kind_enum === "top") {
        if (f.kind_enum === "bottom" && Number(f.k2_d_pri) < Number(S.k2_d_pri))
          return { ok: false, fix: "start", culprit: f };
        if (f.kind_enum === "top" && Number(f.k2_g_pri) > Number(E.k2_g_pri))
          return { ok: false, fix: "end", culprit: f };
      } else if (S.kind_enum === "top" && E.kind_enum === "bottom") {
        if (f.kind_enum === "top" && Number(f.k2_g_pri) > Number(S.k2_g_pri))
          return { ok: false, fix: "start", culprit: f };
        if (f.kind_enum === "bottom" && Number(f.k2_d_pri) < Number(E.k2_d_pri))
          return { ok: false, fix: "end", culprit: f };
      }
    }
    return { ok: true, fix: null, culprit: null };
  }

  function dirOf(S, E) {
    if (!S || !E) return null;
    if (S.kind_enum === "bottom" && E.kind_enum === "top") return "UP";
    if (S.kind_enum === "top" && E.kind_enum === "bottom") return "DOWN";
    return null;
  }

  // 合并K价格获取
  function barAtRed(idx) {
    return reducedBars && reducedBars[Number(idx)] ? reducedBars[Number(idx)] : {};
  }

  // 生成一笔
  function buildPen(S, E, sid) {
    const start_idx_red = Number(S.k2_idx_red);
    const end_idx_red = Number(E.k2_idx_red);
    const start_idx_orig = Number(S.k2_idx_orig);
    const end_idx_orig = Number(E.k2_idx_orig);

    const sBar = barAtRed(start_idx_red);
    const eBar = barAtRed(end_idx_red);

    const start_g_pri = Number(sBar.g_pri);
    const start_d_pri = Number(sBar.d_pri);
    const end_g_pri = Number(eBar.g_pri);
    const end_d_pri = Number(eBar.d_pri);

    const d = dirOf(S, E) || (S.kind_enum === "bottom" ? "UP" : "DOWN");
    const start_y_pri = d === "UP" ? start_d_pri : start_g_pri;
    const end_y_pri = d === "UP" ? end_g_pri : end_d_pri;

    const start_frac_idx_int = id2idxGlobal.has(String(S.id_str || "")) ? Number(id2idxGlobal.get(String(S.id_str))) : -1;
    const end_frac_idx_int = id2idxGlobal.has(String(E.id_str || "")) ? Number(id2idxGlobal.get(String(E.id_str))) : -1;

    return {
      start_frac_idx_int,
      end_frac_idx_int,
      start_frac_id_str: String(S.id_str || ""),
      end_frac_id_str: String(E.id_str || ""),

      start_idx_red,
      end_idx_red,
      start_idx_orig,
      end_idx_orig,

      start_g_pri,
      start_d_pri,
      end_g_pri,
      end_d_pri,
      start_y_pri,
      end_y_pri,

      span_red_cnt_int: end_idx_red - start_idx_red,
      amp_abs_pri: Math.abs(end_y_pri - start_y_pri),
      dir_enum: d,
      seq_id: sid,
    };
  }

  // 将“上一笔终点”同步为 newStartFractal（保持首尾相连），并向左连锁回溯到稳定
  function propagateToPreviousPens(newStartFractal, sid, frArr) {
    if (!pens.length) return;
    // 仅处理同岛范围
    let i = pens.length - 1;
    let carryEndFr = newStartFractal;
    while (i >= 0) {
      const pen = pens[i];
      if (Number(pen.seq_id) !== Number(sid)) break;

      // 更新 pen 的终点为 carryEndFr
      if (Number(pen.end_idx_red) !== Number(carryEndFr.k2_idx_red)) {
        pen.end_idx_red = Number(carryEndFr.k2_idx_red);
        pen.end_idx_orig = Number(carryEndFr.k2_idx_orig);
        const eBar = barAtRed(pen.end_idx_red);
        pen.end_g_pri = Number(eBar.g_pri);
        pen.end_d_pri = Number(eBar.d_pri);
        pen.end_y_pri = pen.dir_enum === "UP" ? pen.end_g_pri : pen.end_d_pri;
        pen.span_red_cnt_int = pen.end_idx_red - pen.start_idx_red;
      }

      // 若笔退化（起点>=终点），移除该笔并继续向更左一笔传播
      if (pen.start_idx_red >= pen.end_idx_red) {
        pens.splice(i, 1);
        // carryEndFr 不变（仍然是新的起点），继续 i-- 回溯
        i -= 1;
        continue;
      }

      // 构造此笔的起止分型快照，检查区间排他
      const S = {
        kind_enum: pen.dir_enum === "UP" ? "bottom" : "top",
        k2_idx_red: pen.start_idx_red,
        k2_idx_orig: pen.start_idx_orig,
        k2_d_pri: pen.start_d_pri,
        k2_g_pri: pen.start_g_pri,
        id_str: pen.start_frac_id_str,
      };
      const E = {
        kind_enum: pen.dir_enum === "UP" ? "top" : "bottom",
        k2_idx_red: pen.end_idx_red,
        k2_idx_orig: pen.end_idx_orig,
        k2_d_pri: pen.end_d_pri,
        k2_g_pri: pen.end_g_pri,
        id_str: pen.end_frac_id_str,
      };

      const ex = exclusivityOK(S, E, frArr);
      if (!ex.ok && ex.fix === "start" && ex.culprit) {
        // 起点右移为“更大极值”
        const c = ex.culprit;
        pen.start_idx_red = Number(c.k2_idx_red);
        pen.start_idx_orig = Number(c.k2_idx_orig);
        const sBar = barAtRed(pen.start_idx_red);
        pen.start_g_pri = Number(sBar.g_pri);
        pen.start_d_pri = Number(sBar.d_pri);
        pen.start_y_pri = pen.dir_enum === "UP" ? pen.start_d_pri : pen.start_g_pri;
        pen.span_red_cnt_int = pen.end_idx_red - pen.start_idx_red;
        pen.start_frac_id_str = String(c.id_str || "");
        pen.start_frac_idx_int = id2idxGlobal.has(String(c.id_str || "")) ? Number(id2idxGlobal.get(String(c.id_str))) : -1;

        // 同步更左一笔的“终点”为该新起点（继续回溯）
        carryEndFr = c;
        i -= 1;
        continue;
      } else if (!ex.ok && ex.fix === "end" && ex.culprit) {
        // 此分支很少见：将当前笔的终点也调整为更大极值（不继续左传）
        const c = ex.culprit;
        pen.end_idx_red = Number(c.k2_idx_red);
        pen.end_idx_orig = Number(c.k2_idx_orig);
        const eBar = barAtRed(pen.end_idx_red);
        pen.end_g_pri = Number(eBar.g_pri);
        pen.end_d_pri = Number(eBar.d_pri);
        pen.end_y_pri = pen.dir_enum === "UP" ? pen.end_g_pri : pen.end_d_pri;
        pen.span_red_cnt_int = pen.end_idx_red - pen.start_idx_red;
        pen.end_frac_id_str = String(c.id_str || "");
        pen.end_frac_idx_int = id2idxGlobal.has(String(c.id_str || "")) ? Number(id2idxGlobal.get(String(c.id_str))) : -1;
        // 不继续连锁，视为稳定
        break;
      } else {
        // 已稳定，结束回溯
        break;
      }
    }
  }

  // 分岛推进
  for (const [sid, arrF0] of bySeq.entries()) {
    // 同岛分型序列按 k2_idx_red 递增
    const frArr = (arrF0 || []).slice().sort((a, b) => a.k2_idx_red - b.k2_idx_red);
    if (!frArr.length) continue;

    // 首笔：同步维护“最高顶”与“最低底”，任一端刷新后立即重验净距与排他
    let S = null; // 当前笔起点分型
    let E = null; // 当前笔终点分型
    let haveFirstPen = false;

    let bestTop = null;
    let bestBottom = null;

    const tryMakeFirstPen = () => {
      if (!bestTop || !bestBottom) return false;
      // 自然决定方向：按左右顺序
      let candS = null, candE = null;
      if (bestBottom.k2_idx_red < bestTop.k2_idx_red) {
        candS = bestBottom; candE = bestTop;
      } else if (bestTop.k2_idx_red < bestBottom.k2_idx_red) {
        candS = bestTop; candE = bestBottom;
      } else {
        return false; // 同 rid 不可能成笔
      }
      if (!isOppositePair(candS, candE)) return false;

      // 先修极值（区间排他）
      const ex = exclusivityOK(candS, candE, frArr);
      if (!ex.ok) {
        if (ex.fix === "start" && ex.culprit) {
          if (candS.kind_enum === "top") {
            if (!bestTop || ex.culprit.k2_g_pri > bestTop.k2_g_pri) bestTop = ex.culprit;
          } else {
            if (!bestBottom || ex.culprit.k2_d_pri < bestBottom.k2_d_pri) bestBottom = ex.culprit;
          }
        } else if (ex.fix === "end" && ex.culprit) {
          if (candE.kind_enum === "top") {
            if (!bestTop || ex.culprit.k2_g_pri > bestTop.k2_g_pri) bestTop = ex.culprit;
          } else {
            if (!bestBottom || ex.culprit.k2_d_pri < bestBottom.k2_d_pri) bestBottom = ex.culprit;
          }
        }
        return false;
      }

      // 净距
      if (!gapOK(candS, candE)) return false;

      // 成笔
      const pen = buildPen(candS, candE, sid);
      pens.push(pen);
      S = candE; // 下一笔起点 = 本笔终点（首尾相连）
      E = null;
      haveFirstPen = true;
      return true;
    };

    for (let i = 0; i < frArr.length; i++) {
      const f = frArr[i];

      if (!haveFirstPen) {
        // 跟踪双向极值（严格更高顶/更低底；相等不更新）
        if (f.kind_enum === "top") {
          if (!bestTop || Number(f.k2_g_pri) > Number(bestTop.k2_g_pri)) {
            bestTop = f;
            // 端更新后立即尝试成笔
            tryMakeFirstPen();
          }
        } else {
          if (!bestBottom || Number(f.k2_d_pri) < Number(bestBottom.k2_d_pri)) {
            bestBottom = f;
            tryMakeFirstPen();
          }
        }
        continue;
      }

      // 常规阶段：已确定上一笔，当前笔起点 S 已定（=上一笔终点）
      // 方向由 S 决定：S=bottom -> UP；S=top -> DOWN
      const curDir = S.kind_enum === "bottom" ? "UP" : "DOWN";

      if (f.kind_enum === S.kind_enum) {
        // 起点方向分型：遇“更极值”则右移起点（相等不触发）
        if (
          (curDir === "UP" && Number(f.k2_d_pri) < Number(S.k2_d_pri)) ||
          (curDir === "DOWN" && Number(f.k2_g_pri) > Number(S.k2_g_pri))
        ) {
          S = f;
          // 首尾相连：同步上一笔终点 = 新起点；并向左回溯到稳定
          propagateToPreviousPens(S, sid, frArr);
          // 若终点在新起点左侧/被覆盖则清空 E
          if (E && Number(S.k2_idx_red) >= Number(E.k2_idx_red)) E = null;
        }
      } else {
        // 终点方向：初次赋值或遇“更极值”则替换终点
        if (!E) E = f;
        else {
          if (
            (curDir === "UP" && Number(f.k2_g_pri) > Number(E.k2_g_pri)) ||
            (curDir === "DOWN" && Number(f.k2_d_pri) < Number(E.k2_d_pri))
          ) {
            E = f;
          }
        }
      }

      // 每次 S/E 变化后，先修极值、再验三条
      if (E) {
        // 先修：区间排他
        const ex = exclusivityOK(S, E, frArr);
        if (!ex.ok) {
          if (ex.fix === "start" && ex.culprit) {
            S = ex.culprit;
            propagateToPreviousPens(S, sid, frArr);
            if (E && Number(S.k2_idx_red) >= Number(E.k2_idx_red)) E = null;
          } else if (ex.fix === "end" && ex.culprit) {
            E = ex.culprit;
          }
          // 修正后继续下一轮扫描
          continue;
        }

        // 三硬条件：1) 反向分型（由构造保证）；2) 净距；3) 排他（已通过）
        if (gapOK(S, E)) {
          // 在压入新笔前，首尾相连：上一笔终点 = 当前 S（若上一步未通过 propagate 同步）
          if (pens.length) {
            const prev = pens[pens.length - 1];
            if (Number(prev.seq_id) === Number(sid)) {
              if (Number(prev.end_idx_red) !== Number(S.k2_idx_red)) {
                prev.end_idx_red = Number(S.k2_idx_red);
                prev.end_idx_orig = Number(S.k2_idx_orig);
                const eBar = barAtRed(prev.end_idx_red);
                prev.end_g_pri = Number(eBar.g_pri);
                prev.end_d_pri = Number(eBar.d_pri);
                prev.end_y_pri = prev.dir_enum === "UP" ? prev.end_g_pri : prev.end_d_pri;
                prev.span_red_cnt_int = prev.end_idx_red - prev.start_idx_red;
              }
            }
          }
          // 压入当前笔
          const pen = buildPen(S, E, sid);
          pens.push(pen);
          // 下一笔：起点=本笔终点；清空 E；方向自然交替
          S = E;
          E = null;
        }
      }
    }
    // 本 seq 结束：无需输出“预备笔”，按规则仅返回最终已成的笔序列
  }

  return { confirmed: pens, provisional: null, all: pens };
}

/**
 * 元线段识别（完全重写版）
 * 变更：按 seq_id 分组推进；线段对象新增 seq_id。
 */
export function computeSegments(pensConfirmed) {
  const segs = [];
  const pens = Array.isArray(pensConfirmed) ? pensConfirmed : [];

  const bySeq = new Map();
  for (const p of pens) {
    const sid = Number(p?.seq_id || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push(p);
  }

  function dirUp(p) { return String(p?.dir_enum || "").toUpperCase() === "UP"; }
  function penLow(p) { const a = Number(p?.start_d_pri), b = Number(p?.end_d_pri); return Math.min(a, b); }
  function penHigh(p) { const a = Number(p?.start_g_pri), b = Number(p?.end_g_pri); return Math.max(a, b); }

  // 成功判定（严格不等）
  function checkPair(pCur, pNext) {
    const l1 = penLow(pCur), h1 = penHigh(pCur);
    const l2 = penLow(pNext), h2 = penHigh(pNext);
    const overlapLow = Math.max(l1, l2), overlapHigh = Math.min(h1, h2);
    const overlapOk = overlapHigh > overlapLow;
    const c1 = l1 < l2 && h1 > h2; const c2 = l2 < l1 && h2 > h1;
    const notContainOk = !(c1 || c2);

    // 发展一致（严格）
    let trendOk = false;
    if (dirUp(pCur) && dirUp(pNext)) trendOk = l2 > l1 && h2 > h1;
    else if (!dirUp(pCur) && !dirUp(pNext)) trendOk = h2 < h1 && l2 < l1;
    return { ok: overlapOk && notContainOk && trendOk };
  }

  for (const [sid, arr] of bySeq.entries()) {
    let s = 0;
    while (s < arr.length) {
      const startPen = arr[s];
      if (!startPen) break;

      const up = dirUp(startPen);

      let hasSuccess = false;
      let curIdx = s;
      let lastSuccessNextIdx = -1;
      const successNextIdxList = [];
      const checks = [];

      while (curIdx + 2 < arr.length) {
        const nextIdx = curIdx + 2;
        const pCur = arr[curIdx], pNext = arr[nextIdx];
        if (dirUp(pCur) !== dirUp(pNext)) { checks.push({ ok: false }); break; }
        const evalRes = checkPair(pCur, pNext);
        checks.push({ ok: evalRes.ok });
        if (evalRes.ok) {
          hasSuccess = true;
          lastSuccessNextIdx = nextIdx;
          successNextIdxList.push(nextIdx);
          curIdx = nextIdx;
          continue;
        } else {
          break;
        }
      }

      if (hasSuccess && lastSuccessNextIdx >= 0) {
        const endPen = arr[lastSuccessNextIdx];
        const start_idx_orig = Number(startPen.start_idx_orig);
        const end_idx_orig = Number(endPen.end_idx_orig);
        const start_y_pri = up ? Number(startPen.start_d_pri) : Number(startPen.start_g_pri);
        const end_y_pri = up ? Number(endPen.end_g_pri) : Number(endPen.end_d_pri);

        const segment = {
          start_pen_idx_int: s,
          end_pen_idx_int: lastSuccessNextIdx,
          start_frac_idx_int: Number(startPen.start_frac_idx_int ?? -1),
          end_frac_idx_int: Number(endPen.end_frac_idx_int ?? -1),
          start_idx_red: Number(startPen.start_idx_red),
          end_idx_red: Number(endPen.end_idx_red),
          start_idx_orig,
          end_idx_orig,
          start_g_pri: Number(startPen.start_g_pri),
          start_d_pri: Number(startPen.start_d_pri),
          end_g_pri: Number(endPen.end_g_pri),
          end_d_pri: Number(endPen.end_d_pri),
          start_y_pri,
          end_y_pri,
          dir_enum: up ? "UP" : "DOWN",
          success_pen_idx_arr: successNextIdxList.slice(),
          checks_arr: checks.slice(),
          end_gap_exists_bool: (function () {
            const lookA = lastSuccessNextIdx + 1;
            const lookB = lastSuccessNextIdx + 3;
            if (lookB >= arr.length) return true;
            const a = arr[lookA], b = arr[lookB];
            if (!a || !b) return true;
            if (dirUp(a) !== dirUp(b)) return true;
            return !checkPair(a, b).ok;
          })(),
          seq_id: sid,
        };

        segs.push(segment);
        s = lastSuccessNextIdx + 1;
      } else {
        const mid = (typeof curIdx === "number") ? curIdx + 1 : s + 1;
        if (mid < arr.length) s = mid; else break;
      }
    }
  }

  return segs;
}

// ==============================
// NEW: 识别“笔中枢”（矩形）
// 说明：按每个 seq_id（岛）独立扫描；以 P1~P4 滑窗：
//   - upper = min(P2.high, P4.high)，lower = max(P2.low, P4.low)
//   - 必须 upper > lower（零厚度不成立）
//   - P1“外部性”：P1.start_y_pri < lower 或 P1.start_y_pri > upper（严格不等）
//   - 中枢方向：暂按 P1.dir_enum 决定（按你的要求）
//   - 延续：从 P5 开始，若“完全在外”（start/end 同在上沿之上或同在下沿之下）则结束，否则延续；右沿取“完全在外的第一笔”的 start_idx_orig；若未遇到完全在外，右沿取本岛最后一笔的 end_idx_orig。
// 返回：[{ seq_id, left_idx_orig, right_idx_orig, upper, lower, dir_enum }]
// ==============================
export function computePenPivots(pensConfirmed) {
  const pivots = [];
  const pens = Array.isArray(pensConfirmed) ? pensConfirmed : [];
  if (!pens.length) return pivots;

  // 按岛分组并按时间顺序排序（以 start_idx_orig）
  const bySeq = new Map();
  for (const p of pens) {
    const sid = Number(p?.seq_id || 1);
    if (!bySeq.has(sid)) bySeq.set(sid, []);
    bySeq.get(sid).push(p);
  }
  for (const [sid, arr] of bySeq.entries()) {
    const seqPens = (arr || []).slice().sort((a, b) => a.start_idx_orig - b.start_idx_orig);
    if (seqPens.length < 4) continue;

    // 取单笔的“高/低”：采用最终笔端点输出（唯一真相源），避免中间推导
    const penHigh = (p) => Math.max(Number(p.start_y_pri), Number(p.end_y_pri));
    const penLow = (p) => Math.min(Number(p.start_y_pri), Number(p.end_y_pri));

    let i = 0;
    while (i + 3 < seqPens.length) {
      const P1 = seqPens[i];
      const P2 = seqPens[i + 1];
      const P3 = seqPens[i + 2];
      const P4 = seqPens[i + 3];

      // 上下沿（零厚度不成立）
      const upper = Math.min(penHigh(P2), penHigh(P4));
      const lower = Math.max(penLow(P2), penLow(P4));
      if (!(Number.isFinite(upper) && Number.isFinite(lower))) {
        i += 1;
        continue;
      }
      if (!(upper > lower)) {
        i += 1;
        continue; // 零厚度不成立
      }

      // P1“外部性”修改：必须在 P2-P4 的整体包络范围以外（严格不等）
      // 整体包络：envMin = min(P2.low, P4.low)，envMax = max(P2.high, P4.high)
      const p1Start = Number(P1.start_y_pri);
      const envMax = Math.max(penHigh(P2), penHigh(P4));
      const envMin = Math.min(penLow(P2), penLow(P4));
      if (!Number.isFinite(p1Start) || !(p1Start > envMax || p1Start < envMin)) {
        i += 1;
        continue;
      }

      // 成立：记录左沿与方向（方向按 P1）
      const left_idx_orig = Number(P1.end_idx_orig);
      const dir_enum = String(P1?.dir_enum || "").toUpperCase(); // 'UP'|'DOWN'
      let right_idx_orig = null;

      // 延续：从 P5 开始
      let j = i + 4;
      let endedByOutside = false;
      while (j < seqPens.length) {
        const Pk = seqPens[j];
        const sY = Number(Pk.start_y_pri);
        const eY = Number(Pk.end_y_pri);
        if (!Number.isFinite(sY) || !Number.isFinite(eY)) {
          j += 1;
          continue;
        }
        // “完全在外”：起止两端都在上沿之上，或都在下沿之下（严格不等）
        const bothAbove = sY > upper && eY > upper;
        const bothBelow = sY < lower && eY < lower;
        if (bothAbove || bothBelow) {
          right_idx_orig = Number(Pk.start_idx_orig); // 右沿 = 第一根完全在外笔的“起点”
          endedByOutside = true;
          break;
        }
        j += 1;
      }
      if (!endedByOutside) {
        // 未遇到完全在外：以本岛最后一笔的“终点”作为右沿（与规则的“外第一笔起点”保持一致语义上最右覆盖）
        const lastPen = seqPens[seqPens.length - 1];
        right_idx_orig = Number(lastPen?.end_idx_orig ?? left_idx_orig);
      }

      // 写入中枢
      pivots.push({
        seq_id: sid,
        left_idx_orig,
        right_idx_orig,
        upper,
        lower,
        dir_enum, // 'UP'|'DOWN'
      });

      // 下一次扫描从“完全在外”的那一笔（或末尾）作为新的 P1
      if (endedByOutside) {
        // i 跳到 j - 1（该笔作为新的 P1）
        i = Math.max(0, j - 1);
      } else {
        // 已到岛末尾
        break;
      }
    }
  }

  return pivots;
}
