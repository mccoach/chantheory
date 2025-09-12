// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useChan.js  // 文件路径（新增）
// ==============================                                               // 说明：缠论“去包含 + 涨跌判定”最小实现（纯函数）
// 说明：computeInclude(candles, {anchorPolicy}) → { reducedBars, mapOrigToReduced, meta } // 仅使用 high/low/time
// 设计：单次左→右扫描，包含时按 a 的方向合并；承载点默认右端（idx_end），支持 'extreme' 切换。   // 算法遵循你确认的规则
// ==============================                                               // 结束头注释

export function computeInclude(candles, opts = {}) {
  // 导出主函数
  const anchorPolicy = opts.anchorPolicy === "extreme" ? "extreme" : "right"; // 承载点策略（'right' 默认）
  const N = Array.isArray(candles) ? candles.length : 0; // 原始根数（防御性）
  const reduced = []; // 复合序列（输出）
  const map = new Array(N); // 原始→复合映射（输出）
  let lastDir = 0; // 最近一次确定的方向（-1/0/+1）

  // 小工具：提取高/低/时间（容错）
  const H = (i) => Number(candles[i]?.h ?? candles[i]?.high ?? NaN); // 取高
  const L = (i) => Number(candles[i]?.l ?? candles[i]?.low ?? NaN); // 取低
  const T = (i) => String(candles[i]?.t ?? ""); // 取时（ISO）

  // 小工具：判定 a→b 的涨跌（仅看高/低）
  function relation(a, b) {
    // 返回 +1/-1/0（上涨/下跌/包含）
    const up = a.hi < b.hi && a.lo < b.lo; // 上涨条件
    const dn = a.hi > b.hi && a.lo > b.lo; // 下跌条件
    if (up) return +1; // 上涨
    if (dn) return -1; // 下跌
    return 0; // 包含
  }

  // 小工具：决定合并方向（a.dir 若未定，优先与 prev 比较，否则用 lastDir，再不行默认 +1）
  function decideDirection(a, prev, b) {
    // 决策方向
    if (a.dir !== 0) return a.dir; // a 已有方向
    if (prev) {
      // 存在前一复合K
      const r = relation(prev, a); // prev→a 关系
      if (r !== 0) return r; // 非包含，直接用
    }
    if (lastDir !== 0) return lastDir; // 使用最近方向
    // 如果仍无法判定，尝试用 a/b 的相对极值给一个启发，否则默认 +1
    if (a.hi !== b.hi || a.lo !== b.lo) {
      // 极值不同
      return b.hi - a.hi + (b.lo - a.lo) >= 0 ? +1 : -1; // 粗略启发
    }
    return +1; // 最后保底为上涨
  }

  // 小工具：更新 map（把 [s..e] 这一段的原始索引映射到 reducedIndex，end 为 carrier）
  function fillMapRange(s, e, reducedIndex) {
    // 写入映射
    for (let k = s; k <= e; k++) {
      // 遍历覆盖段
      map[k] = {
        reducedIndex,
        role: k === reduced[reducedIndex].idx_end ? "carrier" : "merged",
      }; // 赋值
    }
  }

  // 主循环：从左到右
  for (let i = 0; i < N; i++) {
    // 遍历原始 K
    const hi = H(i); // 当前高
    const lo = L(i); // 当前低
    if (!Number.isFinite(hi) || !Number.isFinite(lo)) {
      // 非法跳过
      continue; // 跳过异常行
    }
    const base = {
      // 构造单根复合K
      idx_start: i, // 起索引
      idx_end: i, // 止索引（默认自身）
      hi,
      lo, // 高低
      dir: 0, // 方向未知
      t_start: T(i), // 起时间
      t_end: T(i), // 止时间
      hi_idx: i, // 极大所在原始索引
      lo_idx: i, // 极小所在原始索引
      anchor_idx: i, // 承载索引（默认右端=当前）
      reason: "normal", // 形成原因（调试）
    }; // 结束 base

    if (reduced.length === 0) {
      // 首根
      reduced.push(base); // 压入
      map[i] = { reducedIndex: 0, role: "carrier" }; // 映射为承载
      continue; // 处理下一根
    }

    const a = reduced[reduced.length - 1]; // 栈尾 a
    const b = base; // 当前 b
    const r = relation(a, b); // a→b 关系

    if (r === +1 || r === -1) {
      // 非包含：上涨/下跌
      b.dir = r; // b 的方向
      lastDir = r; // 更新最近方向
      reduced.push(b); // 直接追加为新复合K
      map[i] = { reducedIndex: reduced.length - 1, role: "carrier" }; // 本根为承载
      continue; // 下一个
    }

    // r === 0 → 含包：按 a 的方向合并 a 与 b
    const prev = reduced.length >= 2 ? reduced[reduced.length - 2] : null; // 取前一复合K
    const trend = decideDirection(a, prev, b); // 决定合并方向
    a.dir = a.dir === 0 ? trend : a.dir; // 若 a 未定，补充方向

    if (a.dir >= 0) {
      // 上方向并（上包）
      // 新极值
      const newHi = Math.max(a.hi, b.hi); // 合并高
      const newLo = Math.max(a.lo, b.lo); // 合并低
      // 更新 a
      a.hi = newHi; // 写高
      a.lo = newLo; // 写低
      a.hi_idx =
        newHi === a.hi && a.idx_end !== i
          ? a.hi_idx
          : newHi === b.hi
          ? i
          : a.hi_idx; // 极大索引
      a.lo_idx =
        newLo === a.lo && a.idx_end !== i
          ? a.lo_idx
          : newLo === b.lo
          ? i
          : a.lo_idx; // 极小索引
      a.idx_end = i; // 扩展右端
      a.t_end = b.t_end; // 更新时间
      a.reason = "inclusion-merge-up"; // 标注原因
      lastDir = a.dir; // 记录方向
      // 承载点策略
      a.anchor_idx =
        anchorPolicy === "extreme"
          ? a.dir > 0
            ? a.hi_idx
            : a.lo_idx // 极值承载（上用 hi）
          : a.idx_end; // 右端承载
      // 填映射
      fillMapRange(a.idx_start, a.idx_end, reduced.length - 1); // 覆盖段映射
    } else {
      // 下方向并（下包）
      const newHi = Math.min(a.hi, b.hi); // 合并高（取小）
      const newLo = Math.min(a.lo, b.lo); // 合并低（取小）
      a.hi = newHi; // 写高
      a.lo = newLo; // 写低
      a.hi_idx =
        newHi === a.hi && a.idx_end !== i
          ? a.hi_idx
          : newHi === b.hi
          ? i
          : a.hi_idx; // 极大索引（下包）
      a.lo_idx =
        newLo === a.lo && a.idx_end !== i
          ? a.lo_idx
          : newLo === b.lo
          ? i
          : a.lo_idx; // 极小索引（下包）
      a.idx_end = i; // 扩展右端
      a.t_end = b.t_end; // 更新时间
      a.reason = "inclusion-merge-down"; // 标注原因
      lastDir = a.dir; // 记录方向
      a.anchor_idx =
        anchorPolicy === "extreme"
          ? a.dir < 0
            ? a.lo_idx
            : a.hi_idx // 极值承载（下用 lo）
          : a.idx_end; // 右端承载
      fillMapRange(a.idx_start, a.idx_end, reduced.length - 1); // 覆盖段映射
    }
  }

  // 填充“单根”复合K的映射（可能在首根时未覆盖）
  for (let j = 0; j < reduced.length; j++) {
    // 遍历复合K
    const rj = reduced[j]; // 当前复合K
    if (rj.idx_start === rj.idx_end) {
      // 单根
      map[rj.idx_start] = { reducedIndex: j, role: "carrier" }; // 自身承载
    } // 结束 if
  } // 结束 for

  // 输出 meta
  const meta = {
    // 元信息
    algo: "include_v1", // 算法名
    anchorPolicy, // 承载策略
    generated_at: new Date().toISOString(), // 生成时间
  }; // 结束 meta

  return { reducedBars: reduced, mapOrigToReduced: map, meta }; // 返回结果
} // 结束 computeInclude
