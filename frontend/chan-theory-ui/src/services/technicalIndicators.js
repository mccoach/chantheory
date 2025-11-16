// frontend/src/services/technicalIndicators.js
// ==============================
// 说明：技术指标计算模块（移植自后端）
// 职责：
//   - 计算 MA / MACD / KDJ / RSI / BOLL
//   - 纯函数，无副作用
// ==============================

/**
 * 计算多条移动平均线
 * @param {Array<number>} closes - 收盘价序列
 * @param {Object} periodsMap - MA配置 {MA5: 5, MA10: 10, ...}
 * @returns {Object} {MA5: [...], MA10: [...]}
 */
export function calculateMA(closes, periodsMap) {
  const result = {}
  
  Object.entries(periodsMap || {}).forEach(([key, period]) => {
    const n = parseInt(period)
    if (!Number.isFinite(n) || n <= 0) return
    
    result[key] = closes.map((_, i) => {
      if (i < n - 1) return null
      
      let sum = 0
      for (let j = i - n + 1; j <= i; j++) {
        sum += closes[j]
      }
      return sum / n
    })
  })
  
  return result
}

/**
 * 计算MACD指标
 * @param {Array<number>} closes - 收盘价序列
 * @param {number} fast - 快线周期（默认12）
 * @param {number} slow - 慢线周期（默认26）
 * @param {number} signal - 信号线周期（默认9）
 * @returns {Object} {MACD_DIF, MACD_DEA, MACD_HIST}
 */
export function calculateMACD(closes, fast = 12, slow = 26, signal = 9) {
  const emaFast = calculateEMA(closes, fast)
  const emaSlow = calculateEMA(closes, slow)
  
  const dif = emaFast.map((v, i) => v - emaSlow[i])
  const dea = calculateEMA(dif, signal)
  const hist = dif.map((v, i) => (v - dea[i]) * 2)
  
  return {
    MACD_DIF: dif,
    MACD_DEA: dea,
    MACD_HIST: hist
  }
}

/**
 * 计算KDJ指标
 * @param {Array<number>} highs - 最高价序列
 * @param {Array<number>} lows - 最低价序列
 * @param {Array<number>} closes - 收盘价序列
 * @param {number} n - RSV周期（默认9）
 * @param {number} k - K值平滑（默认3）
 * @param {number} d - D值平滑（默认3）
 * @returns {Object} {KDJ_K, KDJ_D, KDJ_J}
 */
export function calculateKDJ(highs, lows, closes, n = 9, k = 3, d = 3) {
  // 计算RSV（未成熟随机值）
  const rsv = closes.map((c, i) => {
    if (i < n - 1) return 50
    
    const windowHigh = Math.max(...highs.slice(i - n + 1, i + 1))
    const windowLow = Math.min(...lows.slice(i - n + 1, i + 1))
    
    return ((c - windowLow) / (windowHigh - windowLow + 1e-12)) * 100
  })
  
  const kLine = calculateEMA(rsv, k)
  const dLine = calculateEMA(kLine, d)
  const jLine = kLine.map((kv, i) => 3 * kv - 2 * dLine[i])
  
  return {
    KDJ_K: kLine,
    KDJ_D: dLine,
    KDJ_J: jLine
  }
}

/**
 * 计算RSI指标
 * @param {Array<number>} closes - 收盘价序列
 * @param {number} period - 周期（默认14）
 * @returns {Object} {RSI}
 */
export function calculateRSI(closes, period = 14) {
  const changes = []
  for (let i = 1; i < closes.length; i++) {
    changes.push(closes[i] - closes[i - 1])
  }
  
  const gains = changes.map(c => c > 0 ? c : 0)
  const losses = changes.map(c => c < 0 ? -c : 0)
  
  const avgGain = calculateEMA(gains, period)
  const avgLoss = calculateEMA(losses, period)
  
  const rsi = avgGain.map((g, i) => {
    const rs = g / (avgLoss[i] + 1e-12)
    return 100 - (100 / (1 + rs))
  })
  
  // 首位补null对齐
  return { RSI: [null, ...rsi] }
}

/**
 * 计算布林带
 * @param {Array<number>} closes - 收盘价序列
 * @param {number} period - 周期（默认20）
 * @param {number} k - 标准差倍数（默认2）
 * @returns {Object} {BOLL_MID, BOLL_UPPER, BOLL_LOWER}
 */
export function calculateBOLL(closes, period = 20, k = 2) {
  const mid = calculateMA(closes, { BOLL_MID: period }).BOLL_MID
  
  const std = closes.map((_, i) => {
    if (i < period - 1) return 0
    
    const window = closes.slice(i - period + 1, i + 1)
    const mean = mid[i]
    const variance = window
      .map(v => Math.pow(v - mean, 2))
      .reduce((a, b) => a + b, 0) / period
    
    return Math.sqrt(variance)
  })
  
  const upper = mid.map((v, i) => v + k * std[i])
  const lower = mid.map((v, i) => v - k * std[i])
  
  return {
    BOLL_MID: mid,
    BOLL_UPPER: upper,
    BOLL_LOWER: lower
  }
}

/**
 * 计算EMA（指数移动平均）- 内部函数
 * @param {Array<number>} data - 数据序列
 * @param {number} period - 周期
 * @returns {Array<number>} EMA序列
 */
function calculateEMA(data, period) {
  const k = 2 / (period + 1)
  const ema = new Array(data.length)
  
  // 初始值 = 前n个数的SMA
  let sum = 0
  for (let i = 0; i < period && i < data.length; i++) {
    sum += data[i]
  }
  ema[period - 1] = sum / period
  
  // EMA递推公式
  for (let i = period; i < data.length; i++) {
    ema[i] = data[i] * k + ema[i - 1] * (1 - k)
  }
  
  return ema
}