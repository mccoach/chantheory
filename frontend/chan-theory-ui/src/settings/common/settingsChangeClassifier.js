// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\common\settingsChangeClassifier.js
// ==============================
// 设置变更分类器（阶段2 · 单一真相源）
//
// 目标：
//   - 仅用于“用户暴露交互”的设置弹窗保存（SettingsShell）
//   - 对 draft 做 baseline diff，输出 changedPaths
//   - 将 changedPaths 归类为 FULL 或 PATCH（facet × kind）
//   - 任意命中 FULL => FULL；否则 => PATCH（但若出现未覆盖项，则升级 FULL）
//
// 设计约束：
//   - 纯函数/零副作用（除 createBaselineKeeper 内部保存 baseline）
//   - 明确性优于隐晦性：路径规则显式列举，不做魔法推断
//   - 不与 ECharts 重叠：仅产出“决策与计划”，不执行渲染
// ==============================

function isPlainObject(x) {
  return x && typeof x === "object" && !Array.isArray(x);
}

function deepCloneJson(x) {
  return x == null ? x : JSON.parse(JSON.stringify(x));
}

/**
 * 基线快照持有器：用于 SettingsShell 在 mounted/open 时保存 baseline
 * @param {any} initialDraft
 * @returns {{ getBaseline:Function, setBaseline:Function }}
 */
export function createBaselineKeeper(initialDraft) {
  let _baseline = deepCloneJson(initialDraft);

  return {
    getBaseline() {
      return _baseline;
    },
    setBaseline(nextDraft) {
      _baseline = deepCloneJson(nextDraft);
    },
  };
}

/**
 * 计算两个 JSON 对象的变更路径集合（点路径）
 * - 只用于设置对象：通常是 plainObject + 少量 array（如 maConfigs/indicatorPanes 这里不走）
 * - 对数组：若任意元素不同，则直接记录数组路径（不展开逐元素 diff，避免复杂化）
 *
 * @param {any} a
 * @param {any} b
 * @param {string} [basePath]
 * @param {Set<string>} [out]
 * @returns {string[]} changed paths
 */
export function diffPaths(a, b, basePath = "", out = new Set()) {
  if (a === b) return Array.from(out);

  const path = String(basePath || "");

  // 基元或 null
  const aPrim = a == null || typeof a !== "object";
  const bPrim = b == null || typeof b !== "object";
  if (aPrim || bPrim) {
    out.add(path || "");
    return Array.from(out);
  }

  // 数组：任何差异直接记该路径
  if (Array.isArray(a) || Array.isArray(b)) {
    // 统一按 JSON 字符串比较（设置对象数组通常较小，如 concepts；但我们这里主要 diff settings draft）
    try {
      const sa = JSON.stringify(a);
      const sb = JSON.stringify(b);
      if (sa !== sb) out.add(path || "");
    } catch {
      out.add(path || "");
    }
    return Array.from(out);
  }

  // 对象：递归 key
  const keys = new Set([...Object.keys(a || {}), ...Object.keys(b || {})]);
  for (const k of keys) {
    const nextPath = path ? `${path}.${k}` : k;
    const va = a ? a[k] : undefined;
    const vb = b ? b[k] : undefined;

    if (va === vb) continue;

    const vaObj = va != null && typeof va === "object";
    const vbObj = vb != null && typeof vb === "object";

    if (vaObj && vbObj && isPlainObject(va) && isPlainObject(vb)) {
      diffPaths(va, vb, nextPath, out);
    } else if (vaObj && vbObj && Array.isArray(va) && Array.isArray(vb)) {
      // 数组：不展开
      try {
        if (JSON.stringify(va) !== JSON.stringify(vb)) out.add(nextPath);
      } catch {
        out.add(nextPath);
      }
    } else {
      out.add(nextPath);
    }
  }

  return Array.from(out);
}

/**
 * 路径分类规则条目
 * @typedef {{
 *   prefix: string,
 *   mode: 'FULL'|'PATCH',
 *   facet?: string,
 *   kind?: string,
 *   match?: (path:string)=>boolean
 * }} Rule
 */

/**
 * 将 changedPaths 映射到分类结果
 * @param {string[]} changedPaths
 * @param {Rule[]} rules
 * @returns {{
 *   items: Array<{path:string, mode:'FULL'|'PATCH', facet?:string, kind?:string, rulePrefix?:string}>,
 *   hasFull: boolean,
 *   hasUnknown: boolean,
 *   unknown: string[],
 * }}
 */
export function classifyPaths(changedPaths, rules) {
  const paths = (Array.isArray(changedPaths) ? changedPaths : [])
    .map((p) => String(p || ""))
    .filter(Boolean);

  const items = [];
  const unknown = [];

  for (const p of paths) {
    let hit = null;

    for (const r of Array.isArray(rules) ? rules : []) {
      const pref = String(r?.prefix || "");
      const okPref = pref ? (p === pref || p.startsWith(`${pref}.`) || p.startsWith(pref)) : false;

      let ok = okPref;
      if (typeof r?.match === "function") {
        try {
          ok = !!r.match(p);
        } catch {
          ok = false;
        }
      }

      if (ok) {
        hit = r;
        break;
      }
    }

    if (!hit) {
      unknown.push(p);
      continue;
    }

    const mode = hit.mode === "FULL" ? "FULL" : "PATCH";

    items.push({
      path: p,
      mode,
      facet: mode === "PATCH" ? String(hit.facet || "") : undefined,
      kind: mode === "PATCH" ? String(hit.kind || "") : undefined,
      rulePrefix: String(hit.prefix || ""),
    });
  }

  const hasFull = items.some((x) => x.mode === "FULL");
  const hasUnknown = unknown.length > 0;

  return { items, hasFull, hasUnknown, unknown };
}

/**
 * 将 classification items 聚合成 patchPlan（facet -> Set(kind)）
 * @param {Array<{mode:string, facet?:string, kind?:string}>} items
 * @returns {Record<string, string[]>}
 */
export function buildPatchPlan(items) {
  const map = new Map(); // facet -> Set(kind)

  for (const it of Array.isArray(items) ? items : []) {
    if (it?.mode !== "PATCH") continue;
    const facet = String(it?.facet || "").trim();
    const kind = String(it?.kind || "").trim();
    if (!facet || !kind) continue;

    if (!map.has(facet)) map.set(facet, new Set());
    map.get(facet).add(kind);
  }

  const out = {};
  for (const [facet, set] of map.entries()) {
    out[facet] = Array.from(set.values()).sort();
  }
  return out;
}
