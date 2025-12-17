// src/composables/engines/adjustment.js
// ==============================
// 说明：复权计算引擎（稀疏因子版，区分前复权/后复权运算方向）
// 职责：根据稀疏复权因子对K线数据进行前复权/后复权调整。
// 规则（Baostock 官方文档对照版）：
//   - 前复权(qfq)：复权价 = 不复权价 × qfq_factor
//   - 后复权(hfq)：复权价 = 不复权价 × hfq_factor
// 设计：
//   - 因子列表 factors 仅包含“因子发生变化”的日期（稀疏序列）；
//   - 对每个K线bar，根据其交易日 YYYYMMDD，使用“最后一个 date <= barDate 的因子”；
//   - 若在该日期之前没有任何因子，则因子默认为 1.0（即不调整）。
// ==============================

import { timestampToYYYYMMDD } from '@/utils/timeParse'

/**
 * 从稀疏因子列表构造“按日期前向填充”的查找结构
 * 
 * @param {Array<{date:number,qfq_factor:number,hfq_factor:number}>} factors
 * @returns {Array<{date:number,qfq_factor:number,hfq_factor:number}>} 按日期升序去重后的因子列表
 */
function prepareSortedFactors(factors) {
  if (!Array.isArray(factors) || factors.length === 0) {
    return []
  }

  // 按 date 升序排序，遇到同一 date 多条时保留最后一条（以防上游重复）
  const sorted = [...factors].sort((a, b) => {
    const da = Number(a.date || 0)
    const db = Number(b.date || 0)
    return da - db
  })

  const uniq = []
  let lastDate = null
  for (const f of sorted) {
    const d = Number(f.date || 0)
    if (!Number.isFinite(d) || d <= 0) continue
    if (d === lastDate) {
      // 同日多条：覆盖前一条
      uniq[uniq.length - 1] = f
    } else {
      uniq.push(f)
      lastDate = d
    }
  }

  return uniq
}

/**
 * 在稀疏因子列表中，为 barDate 找到“最后一个 date <= barDate”的因子
 * 使用二分查找，时间复杂度 O(logN)
 * 
 * @param {Array<{date:number,qfq_factor:number,hfq_factor:number}>} sortedFactors - prepareSortedFactors 的返回值
 * @param {number} barDate - YYYYMMDD 整数
 * @returns {Object|null} 因子记录或 null
 */
function findLastFactorBeforeOrOn(sortedFactors, barDate) {
  const n = sortedFactors.length
  if (n === 0) return null

  let lo = 0
  let hi = n - 1
  let bestIdx = -1

  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    const d = sortedFactors[mid].date

    if (d <= barDate) {
      bestIdx = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }

  return bestIdx >= 0 ? sortedFactors[bestIdx] : null
}

/**
 * 应用复权调整（稀疏因子 + 前向填充版）
 * 
 * 规则（与 Baostock 文档对齐）：
 *   - adjustType === 'qfq'（前复权）：复权价 = 原价 × qfq_factor
 *   - adjustType === 'hfq'（后复权）：复权价 = 原价 × hfq_factor
 *   - adjustType === 'none'：不调整，直接返回原价
 * 
 * @param {Array} candles - 原始K线数据 [{ts, o, h, l, c, v, ...}, ...]
 * @param {Array<{date:number,qfq_factor:number,hfq_factor:number}>} factors - 稀疏因子列表
 * @param {string} adjustType - 复权方式 'none'|'qfq'|'hfq'
 * @returns {Array} 调整后的K线（浅拷贝，每个bar增加 _raw 字段保存原值）
 */
export function applyAdjustment(candles, factors, adjustType) {
  // 不复权或无因子：直接返回原数组（保持引用语义，与旧行为一致）
  if (adjustType === 'none' || !Array.isArray(factors) || factors.length === 0) {
    return candles
  }

  // 准备排序后的稀疏因子列表
  const sortedFactors = prepareSortedFactors(factors)
  if (sortedFactors.length === 0) {
    return candles
  }

  const isQfq = adjustType === 'qfq'
  const isHfq = adjustType === 'hfq'
  if (!isQfq && !isHfq) {
    // 未知类型，安全起见不做调整
    return candles
  }

  // 对每个 bar 按日期查找最新可用因子并应用
  return candles.map(bar => {
    if (!bar || typeof bar.ts === 'undefined') {
      return bar
    }

    const barDate = timestampToYYYYMMDD(bar.ts)
    if (!Number.isFinite(barDate) || barDate <= 0) {
      return bar
    }

    const factorRec = findLastFactorBeforeOrOn(sortedFactors, barDate)
    if (!factorRec) {
      // 在该日期之前没有任何因子 → 因子默认为 1.0，不调整
      return bar
    }

    const q = Number(factorRec.qfq_factor || 1)
    const h = Number(factorRec.hfq_factor || 1)

    let fVal
    if (isQfq) {
      // 前复权：原价 × qfq_factor
      if (!Number.isFinite(q) || q === 0) {
        return bar
      }
      fVal = q
    } else {
      // 后复权：原价 × hfq_factor
      if (!Number.isFinite(h) || h === 0) {
        return bar
      }
      fVal = h
    }

    const rawO = bar.o
    const rawH = bar.h
    const rawL = bar.l
    const rawC = bar.c

    const adjO = rawO * fVal
    const adjH = rawH * fVal
    const adjL = rawL * fVal
    const adjC = rawC * fVal

    return {
      ...bar,
      o: adjO,
      h: adjH,
      l: adjL,
      c: adjC,
      _raw: {
        o: rawO,
        h: rawH,
        l: rawL,
        c: rawC,
      },
    }
  })
}