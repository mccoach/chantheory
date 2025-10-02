// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useChan.js
// ==============================
// 缠论最小实现（逐行注释）
// - computeInclude(candles, {anchorPolicy})：去包含 + 决定承载点（anchor_idx），anchor_idx 为“原始 K 数组索引”
// - computeFractals(reducedBars, params)：基于 HL 柱识别分型（非重叠扫描），并输出 xIndex=中柱 anchor_idx（关键修复点）
// ==============================

/**
 * 去包含 + 涨跌判定（原实现保持不变）
 * - reducedBars[i] 结构含：
 *   * idx_start/idx_end：覆盖的原始 K 区间（原始索引）
 *   * hi/lo：合并高低
 *   * dir：方向（+1/-1）
 *   * hi_idx/lo_idx：极值落在原始 K 的索引
 *   * anchor_idx：承载点在原始 K 中的索引（right/extreme）
 * - mapOrigToReduced[k]：原始第 k 根映射到哪一根复合 K 及其角色（carrier/merged）
 */
export function computeInclude(candles, opts = {}) {
  const anchorPolicy = opts.anchorPolicy === "extreme" ? "extreme" : "right"; // 承载策略
  const N = Array.isArray(candles) ? candles.length : 0; // 原始根数
  const reduced = []; // 复合序列
  const map = new Array(N); // 原始→复合映射
  let lastDir = 0; // 最近方向（用于判定包含合并方向）

  // 取高/低/时间（容错）
  const H = (i) => Number(candles[i]?.h ?? candles[i]?.high ?? NaN);
  const L = (i) => Number(candles[i]?.l ?? candles[i]?.low ?? NaN);
  const T = (i) => String(candles[i]?.t ?? "");

  // a→b 相对关系：+1 上涨；-1 下跌；0 包含
  function relation(a, b) {
    const up = a.hi < b.hi && a.lo < b.lo;
    const dn = a.hi > b.hi && a.lo > b.lo;
    if (up) return +1;
    if (dn) return -1;
    return 0;
  }

  // 决定合并方向：优先用 prev→a 的关系，否则用最近方向，再否则启发默认 +1
  function decideDirection(a, prev, b) {
    if (a.dir !== 0) return a.dir;
    if (prev) {
      const r = relation(prev, a);
      if (r !== 0) return r;
    }
    if (lastDir !== 0) return lastDir;
    if (a.hi !== b.hi || a.lo !== b.lo)
      return b.hi - a.hi + (b.lo - a.lo) >= 0 ? +1 : -1;
    return +1;
  }

  // 将原始区间 [s..e] 映射到某个复合 K（其中承载点标记为 carrier）
  function fillMapRange(s, e, reducedIndex) {
    for (let k = s; k <= e; k++) {
      map[k] = {
        reducedIndex,
        role: k === reduced[reducedIndex].idx_end ? "carrier" : "merged",
      };
    }
  }

  // 主循环：从左到右扫描原始 K
  for (let i = 0; i < N; i++) {
    const hi = H(i);
    const lo = L(i);
    if (!Number.isFinite(hi) || !Number.isFinite(lo)) continue; // 非法行跳过

    // 构造单根复合 K（默认承载点为当前 i）
    const base = {
      idx_start: i,
      idx_end: i,
      hi,
      lo,
      dir: 0,
      t_start: T(i),
      t_end: T(i),
      hi_idx: i,
      lo_idx: i,
      anchor_idx: i, // 关键：承载点在原始 K 索引
      reason: "normal",
    };

    if (reduced.length === 0) {
      reduced.push(base);
      map[i] = { reducedIndex: 0, role: "carrier" };
      continue;
    }

    const a = reduced[reduced.length - 1]; // 栈尾复合 K
    const b = base; // 当前
    const r = relation(a, b); // a→b 关系

    if (r === +1 || r === -1) {
      b.dir = r;
      lastDir = r;
      reduced.push(b);
      map[i] = { reducedIndex: reduced.length - 1, role: "carrier" };
      continue;
    }

    // r===0：包含，按方向合并
    const prev = reduced.length >= 2 ? reduced[reduced.length - 2] : null;
    const trend = decideDirection(a, prev, b);
    a.dir = a.dir === 0 ? trend : a.dir;

    if (a.dir >= 0) {
      // 新：先缓存，再决定是否更新索引（避免与已覆盖的 a.hi/a.lo 比较）
      const prevHi = a.hi, prevLo = a.lo;
      const newHi = Math.max(a.hi, b.hi);
      const newLo = Math.max(a.lo, b.lo);
      a.hi = newHi;
      a.lo = newLo;
      if (newHi !== prevHi && newHi === b.hi) a.hi_idx = i;
      if (newLo !== prevLo && newLo === b.lo) a.lo_idx = i;
      a.idx_end = i;
      a.t_end = b.t_end;
      a.reason = "inclusion-merge-up";
      lastDir = a.dir;
      a.anchor_idx =
        anchorPolicy === "extreme"
          ? a.dir > 0
            ? a.hi_idx
            : a.lo_idx
          : a.idx_end; // 承载：极值/右端
      fillMapRange(a.idx_start, a.idx_end, reduced.length - 1);
    } else {
      const prevHi = a.hi, prevLo = a.lo;
      const newHi = Math.min(a.hi, b.hi);
      const newLo = Math.min(a.lo, b.lo);
      a.hi = newHi;
      a.lo = newLo;
      if (newHi !== prevHi && newHi === b.hi) a.hi_idx = i;
      if (newLo !== prevLo && newLo === b.lo) a.lo_idx = i;
      a.idx_end = i;
      a.t_end = b.t_end;
      a.reason = "inclusion-merge-down";
      lastDir = a.dir;
      a.anchor_idx =
        anchorPolicy === "extreme"
          ? a.dir < 0
            ? a.lo_idx
            : a.hi_idx
          : a.idx_end;
      fillMapRange(a.idx_start, a.idx_end, reduced.length - 1);
    }
  }

  // 单根复合 K 的映射补齐（若有）
  for (let j = 0; j < reduced.length; j++) {
    const rj = reduced[j];
    if (rj.idx_start === rj.idx_end) {
      map[rj.idx_start] = { reducedIndex: j, role: "carrier" };
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
 * 分型识别（非重叠扫描）——支持 minTickCount/minPct 与组合逻辑 minCond('or'|'and')
 * 关键点：
 * - xIndex = 中柱 anchor_idx（“原始 K 索引”，用于横轴定位）
 * - tickUnit 自动估计（取最近窗口内 hi/lo 的最小正差），用于换算最小 tick 数条件
 * - minCond='and' 时需同时满足 tick/pct；'or' 满足其一即可（门槛为 0 时视为满足）
 */
export function computeFractals(reducedBars, params = {}) {
  const out = [];
  const N = Array.isArray(reducedBars) ? reducedBars.length : 0;
  if (N < 3) return out;

  const minTickCount = Math.max(0, Number(params.minTickCount || 0));
  const minPct = Math.max(0, Number(params.minPct || 0)); // 百分比，0=关闭
  const minCond =
    params.minCond === "and" || params.minCond === "or" ? params.minCond : "or";

  // 便捷取值
  const G = (rb) => Number(rb?.hi);
  const D = (rb) => Number(rb?.lo);
  const T = (rb) => String(rb?.t_end || rb?.t || "");
  const Dir = (rb) => Number(rb?.dir || 0);
  const AX = (rb, fallback) => Number(rb?.anchor_idx ?? fallback); // anchor 原始 K 索引

  // 估计最小 tick 单位（取最近窗口内 hi/lo 的最小正差）
  function estimateTickUnit(bars) {
    let unit = Infinity;
    const take = Math.min(bars.length, 200); // 最近 200 根内估计
    for (let i = Math.max(0, bars.length - take); i < bars.length; i++) {
      const a = bars[i];
      if (!a) continue;
      const vals = [G(a), D(a)];
      for (const v of vals) {
        if (!Number.isFinite(v)) continue;
        for (let j = i - 3; j <= i + 3; j++) {
          // 小范围内比对
          if (j < 0 || j >= bars.length || j === i) continue;
          const b = bars[j];
          if (!b) continue;
          const vals2 = [G(b), D(b)];
          for (const u of vals2) {
            if (!Number.isFinite(u)) continue;
            const diff = Math.abs(v - u);
            if (diff > 0 && diff < unit) unit = diff;
          }
        }
      }
    }
    if (!Number.isFinite(unit) || unit <= 0) return null;
    // 对 A 股常见 0.01 做一次兜底（避免出现 1e-15 的浮点误差）
    const rounded = Math.abs(Math.round(unit * 100) / 100);
    return rounded > 0 ? rounded : unit;
  }

  const tickUnit = minTickCount > 0 ? estimateTickUnit(reducedBars) : null;

  // 判定组合器
  function passSignificanceTop(g2, g1, g3) {
    // tick 条件：g2 相对两侧至少高出 minTickCount * tickUnit
    const tickOk =
      minTickCount <= 0
        ? true
        : tickUnit
        ? g2 - g1 >= minTickCount * tickUnit &&
          g2 - g3 >= minTickCount * tickUnit
        : true; // 无法估计 tickUnit 则放行

    // 百分比条件：g2 相对两侧的百分比差满足阈值
    const base = Math.max(Math.abs(g1), Math.abs(g3), 1);
    const pctOk =
      minPct <= 0
        ? true
        : ((g2 - g1) / base) * 100 >= minPct &&
          ((g2 - g3) / base) * 100 >= minPct;

    return minCond === "and" ? tickOk && pctOk : tickOk || pctOk;
  }
  function passSignificanceBottom(d2, d1, d3) {
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

  // 非重叠扫描
  let i = 0;
  while (i + 2 < N) {
    const b1 = reducedBars[i],
      b2 = reducedBars[i + 1],
      b3 = reducedBars[i + 2];
    const d2 = Dir(b2),
      d3 = Dir(b3);
    const G1 = G(b1),
      D1 = D(b1),
      G2 = G(b2),
      D2 = D(b2),
      G3 = G(b3),
      D3 = D(b3);
    const t1 = T(b1),
      t2 = T(b2),
      t3 = T(b3);
    const M1 = (G1 + D1) / 2;

    // 横坐标：中柱的 anchor_idx（原始 K 索引）
    const xIndex = AX(b2, i + 1);

    // 顶分：涨→跌
    if (d2 > 0 && d3 < 0) {
      if (passSignificanceTop(G2, G1, G3)) {
        let strength = "standard";
        if (D3 < D1) strength = "strong";
        else if (D3 > M1) strength = "weak";
        out.push({
          id: `F-${i}-${i + 1}-${i + 2}-top`,
          type: "top",
          i1: i,
          i2: i + 1,
          i3: i + 2,
          xIndex, // 横坐标：原始 K 索引
          anchor_index: i + 1,
          t1,
          t2,
          t3,
          G1,
          D1,
          G2,
          D2,
          G3,
          D3,
          M1,
          strength,
          dir_seq: "+-",
          params: { minTickCount, minPct, minCond }, // 记录使用的参数
          algo_version: "fractal_v1.0",
          significance: {
            tick_ok: minTickCount === 0 || !!tickUnit,
            pct_ok: minPct === 0,
          },
          confirm: { paired: false },
          labels: ["fractal", "top"],
          note: "",
        });
        // MOD: 允许分型共用 K 线 —— 步进改为 1（原为 i += 3）
        i += 1;
        continue;
      }
    }

    // 底分：跌→涨
    if (d2 < 0 && d3 > 0) {
      if (passSignificanceBottom(D2, D1, D3)) {
        let strength = "standard";
        if (G3 > G1) strength = "strong";
        else if (G3 < M1) strength = "weak";
        out.push({
          id: `F-${i}-${i + 1}-${i + 2}-bottom`,
          type: "bottom",
          i1: i,
          i2: i + 1,
          i3: i + 2,
          xIndex,
          anchor_index: i + 1,
          t1,
          t2,
          t3,
          G1,
          D1,
          G2,
          D2,
          G3,
          D3,
          M1,
          strength,
          dir_seq: "-+",
          params: { minTickCount, minPct, minCond },
          algo_version: "fractal_v1.0",
          significance: {
            tick_ok: minTickCount === 0 || !!tickUnit,
            pct_ok: minPct === 0,
          },
          confirm: { paired: false },
          labels: ["fractal", "bottom"],
          note: "",
        });
        // MOD: 允许分型共用 K 线 —— 步进改为 1（原为 i += 3）
        i += 1;
        continue;
      }
    }

    i += 1;
  }

  // 确认分型（严格不等 & 紧邻配对）
  for (let k = 0; k + 1 < out.length; k++) {
    const a = out[k],
      b = out[k + 1];
    if (a.type !== b.type) continue;
    if (b.i1 !== a.i3 + 1) continue; // 紧邻

    if (a.type === "top") {
      const G3 = a.G3,
        D3 = a.D3,
        G4 = b.G1,
        D4 = b.D1,
        G2 = a.G2,
        G5 = b.G2;
      if (G4 < G3 && D4 < D3 && G5 < G2) {
        a.confirm = { paired: true, pair_id: `${a.id}|${b.id}`, role: "first" };
        b.confirm = {
          paired: true,
          pair_id: `${a.id}|${b.id}`,
          role: "second",
        };
      }
    } else {
      const G3 = a.G3,
        D3 = a.D3,
        G4 = b.G1,
        D4 = b.D1,
        D2 = a.D2,
        D5 = b.D2;
      if (G4 > G3 && D4 > D3 && D5 > D2) {
        a.confirm = { paired: true, pair_id: `${a.id}|${b.id}`, role: "first" };
        b.confirm = {
          paired: true,
          pair_id: `${a.id}|${b.id}`,
          role: "second",
        };
      }
    }
  }

  return out;
}

// ==============================
// 新增：画笔（笔）识别 —— computePens
// - 以分型承载点映射到合并K（reducedIndex）为基础，使用“承载点索引差值 gap = endReducedIdx - startReducedIdx”判定成笔。
// - 默认 MIN_GAP_REDUCED=4（分型窗口三根，中柱承载点；保证两分型之间至少存在一根不属于两边分型窗口的独立合并K）。
// - 输出 pens = { confirmed: [...], provisional: {...}|null, all: [...]}，每条笔含起止原/合并索引、方向、幅度与跨度等。
// ==============================
export function computePens(
  reducedBars,
  fractals,
  mapOrigToReduced,
  params = {}
) {
  const minGap = Number.isFinite(+params.minGapReduced)
    ? Math.max(1, Math.floor(+params.minGapReduced))
    : 4; // 默认 4

  // 强度优先级（用于同位/同值的并列选择）
  const strengthRank = { strong: 3, standard: 2, weak: 1 };

  // 1) 建立“候选分型承载点”集合：每个 reducedIndex 仅保留更极值者
  const candidatesByRid = new Map(); // ridx → {ridx, origIdx, type, y, id, strength}
  for (const f of fractals || []) {
    const origIdx = Number(f?.xIndex);
    const mapEnt = (mapOrigToReduced || [])[origIdx];
    const ridx = Number(mapEnt?.reducedIndex);
    if (!Number.isFinite(origIdx) || !Number.isFinite(ridx)) continue;

    const type = String(f?.type || "");
    if (type !== "top" && type !== "bottom") continue;

    const y =
      type === "top" ? Number(f?.G2) : Number(f?.D2); // 顶用 G2，底用 D2
    if (!Number.isFinite(y)) continue;

    const prev = candidatesByRid.get(ridx);
    if (!prev) {
      candidatesByRid.set(ridx, {
        ridx,
        origIdx,
        type,
        y,
        id: String(f?.id || `${type}-${origIdx}`),
        strength: String(f?.strength || "standard"),
      });
      continue;
    }
    // 同位择优：顶取更高；底取更低；并用强度做次级比较
    if (type === prev.type) {
      const better =
        type === "top"
          ? y > prev.y ||
            (y === prev.y &&
              (strengthRank[String(f?.strength || "standard")] || 0) >
                (strengthRank[prev.strength] || 0))
          : y < prev.y ||
            (y === prev.y &&
              (strengthRank[String(f?.strength || "standard")] || 0) >
                (strengthRank[prev.strength] || 0));
      if (better) {
        candidatesByRid.set(ridx, {
          ridx,
          origIdx,
          type,
          y,
          id: String(f?.id || `${type}-${origIdx}`),
          strength: String(f?.strength || "standard"),
        });
      }
      // 若不同类型分型出现在同位（极端情况），优先保留“更极值”的那个，不做复合；此处简单忽略异类覆盖。
    } else {
      // 不同类型同位：优先保留“更极值”的那个
      const preferNew =
        type === "top"
          ? y > prev.y
          : y < prev.y; // 顶更高/底更低者优先
      if (preferNew) {
        candidatesByRid.set(ridx, {
          ridx,
          origIdx,
          type,
          y,
          id: String(f?.id || `${type}-${origIdx}`),
          strength: String(f?.strength || "standard"),
        });
      }
    }
  }

  // 排序为扫描序列（按 reducedIndex 升序）
  const candidates = Array.from(candidatesByRid.values()).sort(
    (a, b) => a.ridx - b.ridx
  );

  // 状态机：currentStart ← 同类更极值更新；遇到反分型且 gap≥minGap → 新预备笔成立，前一预备笔正式确认
  let currentStart = null; // {ridx,origIdx,type,y,id,strength}
  let provisionalPen = null; // 上一个预备笔（等待下一笔成立后确认）
  const confirmedPens = []; // 已确认的笔

  function makePen(start, end) {
    const dir = start.type === "bottom" ? "UP" : "DOWN";
    const startReducedIdx = Number(start.ridx);
    const endReducedIdx = Number(end.ridx);
    const startOrigIdx = Number(start.origIdx);
    const endOrigIdx = Number(end.origIdx);
    const spanReducedBars = endReducedIdx - startReducedIdx;
    const amplitudeAbs =
      dir === "UP" ? Number(end.y) - Number(start.y) : Number(start.y) - Number(end.y);
    return {
      startReducedIdx,
      endReducedIdx,
      startOrigIdx,
      endOrigIdx,
      direction: dir,
      spanReducedBars,
      amplitudeAbs,
      startY: Number(start.y),
      endY: Number(end.y),
      startFractalId: start.id,
      endFractalId: end.id,
      state: "provisional",
    };
  }

  for (const pt of candidates) {
    if (!currentStart) {
      currentStart = pt;
      continue;
    }

    if (pt.type === currentStart.type) {
      // 同类型更极值更新起点
      const better =
        pt.type === "top" ? pt.y > currentStart.y : pt.y < currentStart.y;
      if (better) {
        // —— 修复点：在更新形成笔起点的同时，若存在上一条“预备笔”，同步更新其终点为新的 currentStart —— //
        // 这样保证“相邻两笔首尾相连”：前一笔的 end == 后一笔的 start（currentStart）
        currentStart = pt;
        if (provisionalPen) {
          provisionalPen.endReducedIdx = Number(pt.ridx);
          provisionalPen.endOrigIdx = Number(pt.origIdx);
          provisionalPen.endY = Number(pt.y);
          provisionalPen.endFractalId = String(pt.id);

          // 方向保持不变（由 start.type 决定），重算跨度与幅度
          provisionalPen.spanReducedBars =
            provisionalPen.endReducedIdx - provisionalPen.startReducedIdx;
          provisionalPen.amplitudeAbs =
            provisionalPen.direction === "UP"
              ? provisionalPen.endY - Number(provisionalPen.startY)
              : Number(provisionalPen.startY) - provisionalPen.endY;
        }
      }
      continue;
    }

    // 遇到反分型：判定承载点距差 gap
    const gap = Number(pt.ridx) - Number(currentStart.ridx);
    if (gap >= minGap) {
      // 新预备笔成立
      const newPen = makePen(currentStart, pt);
      // 前一预备笔 → 正式确认
      if (provisionalPen) {
        provisionalPen.state = "confirmed";
        confirmedPens.push(provisionalPen);
      }
      provisionalPen = newPen;
      // 约束：每一笔的起点必然与前一笔的终点一致 —— currentStart 切换为当前反分型
      currentStart = pt;
    } else {
      // 距离不足：忽略，不成笔；允许后续继续更新 currentStart（仅同类更极值）
      continue;
    }
  }

  const allPens = confirmedPens.slice();
  if (provisionalPen) allPens.push(provisionalPen);

  return {
    confirmed: confirmedPens,
    provisional: provisionalPen,
    all: allPens,
  };
}
