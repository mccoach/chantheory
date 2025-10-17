// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\utils\numberUtils.js
// ==============================
// 数字工具（完全通用化·参数控制特例）
// - 目标：不保留写死的窄用途函数，业务特例通过参数控制。
// - 核心：formatNumberScaled（自动万级缩放+单位拼接+格式化）、autoDigits（自动小数位）
// - 辅助：clampNumber（通用钳制）、getByteUnits（字节单位阈值表）
// - 约定：金额单位不出现“元”；单位只使用“万/亿/万亿”
// ==============================

/**
 * 自动选择小数位（默认规则：|x|≥100 → 0位；|x|≥10 → 1位；否则 → 2位）
 * 可通过 opts.rules 自定义规则：
 * 例如：[{minAbs:1000,digits:0},{minAbs:100,digits:1},{minAbs:10,digits:2},{minAbs:0,digits:3}]
 * @param {number} x
 * @param {{rules?: Array<{minAbs:number,digits:number}>}} [opts]
 * @returns {number} digits
 */
export function autoDigits(x, opts = {}) {
  const rules = Array.isArray(opts.rules) && opts.rules.length
    ? opts.rules
    : [
        { minAbs: 100, digits: 0 },
        { minAbs: 10, digits: 1 },
        { minAbs: 0, digits: 2 },
      ];
  const ax = Math.abs(Number(x || 0));
  for (const r of rules) {
    if (ax >= r.minAbs) return r.digits;
  }
  return 2;
}

/**
 * 通用数值格式化（自动万级缩放 + 汉字单位 + 小数位 + 百分比 + 分组 + 业务后缀）
 * - 自动缩放：当整数部分位数 ≥ minIntDigitsToScale（默认 5）时触发，按 thresholds 选择“万/亿/万亿”
 * - 金额单位不出现“元”（即便不缩放）；数量同样只拼“万/亿/万亿”
 * - 百分比：opts.percent.base=1 表示传入即百分值；结果末尾拼接 %
 * - 业务后缀：通过 opts.suffix 控制（如 "手"），工具不写死业务词
 * @param {number} value
 * @param {{
 *   digits?: number,                 // 固定小数位；未给定则自动选择
 *   roundingMode?: 'round'|'floor'|'ceil'|'trunc'|'bankers', // 舍入模式
 *   percent?: { base?: number },     // 百分比：base=1 表示传入即百分数
 *   allowEmpty?: boolean,            // 非数值返回 ""（true）或 "-"（false, 默认）
 *   minIntDigitsToScale?: number,    // 缩放最小整数位数（默认 5）
 *   thresholds?: Array<{min:number,label:string,div:number}>, // 自定义缩放阈值表
 *   grouping?: boolean,              // 千分位分组（默认 false）
 *   suffix?: string                  // 业务后缀（如 "手"）
 * }} [opts]
 * @returns {string}
 */
export function formatNumberScaled(value, opts = {}) {
  const n = Number(value);
  if (!Number.isFinite(n)) return opts.allowEmpty ? "" : "-";

  // 百分比换算（base=1 表示传入即为百分数）
  const percentBase = opts.percent ? Number(opts.percent.base || 1) : null;

  // 默认“万级缩放”阈值（金额与数量同用，不出现“元”）
  const thresholds = Array.isArray(opts.thresholds) && opts.thresholds.length
    ? opts.thresholds
    : [
        { min: 1e12, label: "万亿", div: 1e12 },
        { min: 1e8,  label: "亿",   div: 1e8  },
        { min: 1e4,  label: "万",   div: 1e4  },
      ];

  // “整数部分不超过4位不过万”：达到 5 位才考虑缩放
  const minDigits = Number.isFinite(opts.minIntDigitsToScale)
    ? Math.max(1, opts.minIntDigitsToScale)
    : 5;
  const intLen = String(Math.floor(Math.abs(n))).length;

  // 选单位（满足整数位条件后按阈值选择）
  let div = 1;
  let unitLabel = "";
  if (intLen >= minDigits) {
    const matched = thresholds.find(t => Math.abs(n) >= t.min);
    if (matched) {
      div = matched.div;
      unitLabel = matched.label; // 自动拼“万/亿/万亿”
    }
  }

  // 缩放与百分比
  let scaled = n / div;
  if (percentBase != null) scaled = scaled / percentBase;

  // 位数与舍入
  const digits = Number.isFinite(opts.digits) ? opts.digits : autoDigits(scaled);
  const mode = String(opts.roundingMode || "round");
  const factor = Math.pow(10, digits);
  const raw = scaled * factor;
  let rounded;
  switch (mode) {
    case "floor":  rounded = Math.floor(raw) / factor; break;
    case "ceil":   rounded = Math.ceil(raw) / factor;  break;
    case "trunc":  rounded = (raw < 0 ? Math.ceil(raw) : Math.floor(raw)) / factor; break;
    case "bankers": {
      const floored = Math.floor(raw);
      const diff = raw - floored;
      rounded = (diff > 0.5) ? (floored + 1) / factor
        : (diff < 0.5) ? floored / factor
        : ((floored % 2 === 0 ? floored : floored + 1) / factor);
      break;
    }
    default:       rounded = Math.round(raw) / factor;
  }

  // 输出（可选千分位）
  let core = rounded.toFixed(digits);
  if (opts.grouping) {
    const [intPart, fracPart] = core.split(".");
    const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    core = fracPart != null ? `${grouped}.${fracPart}` : grouped;
  }

  // 拼接：单位 + 百分号 + 业务后缀（金额不出现“元”）
  const percentSign = percentBase != null ? "%" : "";
  const suffix = opts.suffix || "";
  return `${core}${unitLabel}${percentSign}${suffix}`;
}

/**
 * 通用钳制（支持整数/浮点）
 * @param {number|string} value
 * @param {{ min?:number, max?:number, integer?:boolean }} [opts]
 * @returns {number}
 */
export function clampNumber(value, opts = {}) {
  const intOnly = !!opts.integer;
  const n0 = intOnly ? parseInt(String(value), 10) : Number(value);
  const n = Number.isFinite(n0) ? n0 : (opts.min ?? 0);
  const min = Number.isFinite(opts.min) ? opts.min : -Infinity;
  const max = Number.isFinite(opts.max) ? opts.max : Infinity;
  return Math.max(min, Math.min(max, n));
}

/**
 * 字节单位阈值表（SI or Binary）
 * - 用于 formatNumberScaled 的 thresholds 参数，以实现 KB/MB/GB/TB 或 KiB/MiB/GiB/TiB 缩放
 * @param {{ si?: boolean }} [opts] - si=true 使用 1000 进制；否则使用 1024 进制
 * @returns {Array<{min:number,label:string,div:number}>}
 */
export function getByteUnits(opts = {}) {
  const si = !!opts.si;
  const base = si ? 1000 : 1024;
  return [
    { min: Math.pow(base, 4), label: si ? "TB" : "TiB", div: Math.pow(base, 4) },
    { min: Math.pow(base, 3), label: si ? "GB" : "GiB", div: Math.pow(base, 3) },
    { min: Math.pow(base, 2), label: si ? "MB" : "MiB", div: Math.pow(base, 2) },
    { min: Math.pow(base, 1), label: si ? "KB" : "KiB", div: Math.pow(base, 1) },
  ];
}
