// src/composables/useTriToggle.js
// ==============================
// 三态开关标准化模块（全站唯一归口）
//
// 设计目标（按你的要求修正后）：
//   - 规则统一：边界集合U、非自发更新快照、三态循环及退化两态循环（以下载弹窗规则为准）
//   - 样式统一：checkbox skin 已在 global.css（本模块不涉及样式）
//   - 业务代码最小：业务只提供“语义注入”，通用逻辑全部在此处
//
// 本模块提供两层API：
//   A) createTriStateController：通用集合三态控制器（可用于下载弹窗 scope）
//   B) createBooleanGroupTriController：布尔开关组适配器（用于设置窗总控）
//
// 约束：
//   - 本模块不持有业务真相源 selectedSet
//   - snapshot 仅在 external sync 时更新（调用方明确调用 syncSnapshotsOnExternalChange）
//
// V1.1 - NEW: v-tri-state 指令（DOM 强制同步）
//   - 背景：原生 checkbox 的 indeterminate 只是“视觉态”，用户点击后会残留 checked 真值，
//           导致在外部清空/联动时出现“应不选却反弹为勾选”的通用问题（下载弹窗/设置窗均可复现）。
//   - 解决：在 mounted/updated 强制写入 el.indeterminate 与 el.checked，使 UI 永远由真实状态决定。
// ==============================

import { shallowRef } from "vue";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function ensureSet(x) {
  return x instanceof Set ? x : new Set();
}

function setEquals(a, b) {
  if (a === b) return true;
  if (!(a instanceof Set) || !(b instanceof Set)) return false;
  if (a.size !== b.size) return false;
  for (const x of a) if (!b.has(x)) return false;
  return true;
}

function normalizeMode(m) {
  const s = String(m || "").toLowerCase();
  if (s === "all") return "all";
  if (s === "none") return "none";
  return "snapshot";
}

function defaultUiOf({ selectedCount, totalCount }) {
  const total = Math.max(0, Number(totalCount || 0));
  const sel = Math.max(0, Number(selectedCount || 0));
  return {
    checked: total > 0 && sel === total,
    indeterminate: total > 0 && sel > 0 && sel < total,
    selectedCount: sel,
    totalCount: total,
  };
}

/**
 * 通用三态控制器（适用于“某个 scope 对应一个 U 集合”的所有场景）
 *
 * @param {object} deps
 * @param {(scopeKey:string, universeSet:Set<any>)=>({checked:boolean, indeterminate:boolean, selectedCount:number, totalCount:number})} deps.getUi
 * @param {(scopeKey:string, universeSet:Set<any>)=>void} deps.applyAll
 * @param {(scopeKey:string, universeSet:Set<any>)=>void} deps.applyNone
 * @param {(scopeKey:string, universeSet:Set<any>, snapshot:Set<any>)=>void} deps.applySnapshot
 * @param {(scopeKey:string, universeSet:Set<any>)=>Set<any>} deps.buildSnapshot  // 返回 selected ∩ U
 */
export function createTriStateController({
  getUi,
  applyAll,
  applyNone,
  applySnapshot,
  buildSnapshot,
} = {}) {
  if (typeof getUi !== "function") throw new Error("[Tri] getUi is required");
  if (typeof applyAll !== "function") throw new Error("[Tri] applyAll is required");
  if (typeof applyNone !== "function") throw new Error("[Tri] applyNone is required");
  if (typeof applySnapshot !== "function") throw new Error("[Tri] applySnapshot is required");
  if (typeof buildSnapshot !== "function") throw new Error("[Tri] buildSnapshot is required");

  // scopeKey -> snapshot(Set)
  const snapshotMap = shallowRef(new Map());

  // scopeKey -> lastMode('snapshot'|'all'|'none')
  const lastModeMap = shallowRef(new Map());

  function ensureScope(scopeKey, universeSet) {
    const key = asStr(scopeKey);
    const U = ensureSet(universeSet);
    if (!key) return;

    if (!snapshotMap.value.has(key)) {
      const snap = ensureSet(buildSnapshot(key, U));
      const next = new Map(snapshotMap.value);
      next.set(key, snap);
      snapshotMap.value = next;
    }

    if (!lastModeMap.value.has(key)) {
      const next = new Map(lastModeMap.value);
      next.set(key, "snapshot");
      lastModeMap.value = next;
    }
  }

  function getSnapshot(scopeKey) {
    const key = asStr(scopeKey);
    return snapshotMap.value.get(key) || new Set();
  }

  function setSnapshot(scopeKey, snapshotSet) {
    const key = asStr(scopeKey);
    if (!key) return;
    const next = new Map(snapshotMap.value);
    next.set(key, ensureSet(snapshotSet));
    snapshotMap.value = next;
  }

  function getLastMode(scopeKey) {
    const key = asStr(scopeKey);
    const v = lastModeMap.value.get(key);
    return v === "all" || v === "none" ? v : "snapshot";
  }

  function setLastMode(scopeKey, mode) {
    const key = asStr(scopeKey);
    if (!key) return;
    const next = new Map(lastModeMap.value);
    next.set(key, normalizeMode(mode));
    lastModeMap.value = next;
  }

  function isSnapshotDegenerated(scopeKey, universeSet) {
    const key = asStr(scopeKey);
    const U = ensureSet(universeSet);
    const S = getSnapshot(key);

    if (U.size === 0) return true; // 空集合：退化
    if (S.size === 0) return true; // 快照全不选：退化
    if (S.size === U.size && setEquals(S, U)) return true; // 快照全选：退化
    return false;
  }

  /**
   * external change：同步快照（规则2：非自发更新）
   * @param {string} sourceScopeKey - 本次变化来源的 scopeKey；该 scope 的快照不更新
   * @param {Array<{scopeKey:string, universeSet:Set<any>}>} scopes - 需要同步的 scope 列表
   */
  function syncSnapshotsOnExternalChange(sourceScopeKey, scopes) {
    const src = asStr(sourceScopeKey);
    const list = Array.isArray(scopes) ? scopes : [];

    const next = new Map(snapshotMap.value);

    for (const sc of list) {
      const key = asStr(sc?.scopeKey);
      if (!key) continue;

      const U = ensureSet(sc?.universeSet);
      ensureScope(key, U);

      if (key === src) continue;

      next.set(key, ensureSet(buildSnapshot(key, U)));
    }

    snapshotMap.value = next;
  }

  /**
   * 自身点击：循环（规则3：三态 + 退化两态）
   */
  function cycle(scopeKey, universeSet) {
    const key = asStr(scopeKey);
    const U = ensureSet(universeSet);

    ensureScope(key, U);

    const ui = getUi(key, U) || {};
    const checked = ui.checked === true;

    if (isSnapshotDegenerated(key, U)) {
      const nextMode = checked ? "none" : "all";
      setLastMode(key, nextMode);
      if (nextMode === "all") applyAll(key, U);
      else applyNone(key, U);
      return nextMode;
    }

    const seq = ["snapshot", "all", "none"];
    const cur = getLastMode(key);
    const idx = seq.indexOf(cur);
    const nextMode = seq[(idx + 1) % seq.length];

    setLastMode(key, nextMode);

    if (nextMode === "all") applyAll(key, U);
    else if (nextMode === "none") applyNone(key, U);
    else applySnapshot(key, U, getSnapshot(key));

    return nextMode;
  }

  return {
    snapshotMap,
    lastModeMap,

    ensureScope,

    getSnapshot,
    setSnapshot,

    getLastMode,
    setLastMode,

    isSnapshotDegenerated,

    syncSnapshotsOnExternalChange,
    cycle,
  };
}

/**
 * 布尔开关组适配器（设置窗总控专用，但仍是“集合U”模型）
 *
 * @param {object} deps
 * @param {string} deps.scopeKey
 * @param {Array<string>} deps.keys - 组内元素 key 列表（U 的元素）
 * @param {(key:string)=>boolean} deps.get
 * @param {(key:string, v:boolean)=>void} deps.set
 */
export function createBooleanGroupTriController({ scopeKey, keys, get, set }) {
  const sk = asStr(scopeKey);
  const arr = Array.isArray(keys) ? keys.map(asStr).filter(Boolean) : [];
  const U = new Set(arr);

  function getUi(_scopeKey, universeSet) {
    const UU = universeSet instanceof Set ? universeSet : U;
    let selectedCount = 0;
    for (const k of UU) if (get(k)) selectedCount += 1;
    return defaultUiOf({ selectedCount, totalCount: UU.size });
  }

  function applyAll(_scopeKey, universeSet) {
    const UU = universeSet instanceof Set ? universeSet : U;
    for (const k of UU) set(k, true);
  }

  function applyNone(_scopeKey, universeSet) {
    const UU = universeSet instanceof Set ? universeSet : U;
    for (const k of UU) set(k, false);
  }

  function applySnapshot(_scopeKey, universeSet, snapshot) {
    const UU = universeSet instanceof Set ? universeSet : U;
    const S = ensureSet(snapshot);
    for (const k of UU) set(k, S.has(k));
  }

  function buildSnapshot(_scopeKey, universeSet) {
    const UU = universeSet instanceof Set ? universeSet : U;
    const snap = new Set();
    for (const k of UU) if (get(k)) snap.add(k);
    return snap;
  }

  const tri = createTriStateController({
    getUi,
    applyAll,
    applyNone,
    applySnapshot,
    buildSnapshot,
  });

  // 初始化：snapshot 默认取“打开时刻”的当前状态（业务侧创建该 controller 时即为 baseline）
  tri.setSnapshot(sk, buildSnapshot(sk, U));
  tri.ensureScope(sk, U);

  return {
    scopeKey: sk,
    universeSet: U,

    tri,

    // 便捷：直接给总控 UI 用
    getUi: () => getUi(sk, U),

    // 便捷：总控自身点击
    cycle: () => tri.cycle(sk, U),

    // 外部变化：更新 snapshot（规则2）
    syncSnapshotFromCurrent: () => {
      tri.setSnapshot(sk, buildSnapshot(sk, U));
    },
  };
}

// ==============================
// NEW: v-tri-state（DOM 强制同步指令）
// ==============================
//
// 用途：所有三态 checkbox 一律使用该指令，保证：
//   - UI 只由真实状态 {checked, indeterminate} 决定；
//   - 用户点击产生的 checkbox.checked 残留不会污染后续显示；
//   - indeterminate=true 时强制 el.checked=false，消除“半选但勾选真值为 true”的反弹源。
// 使用：
//   <input type="checkbox" v-tri-state="{ checked: xxx, indeterminate: yyy }" />
//
function _normalizeTriValue(val) {
  const v = val && typeof val === "object" ? val : {};
  return {
    checked: v.checked === true,
    indeterminate: v.indeterminate === true,
  };
}

function _applyTriState(el, binding) {
  try {
    const { checked, indeterminate } = _normalizeTriValue(binding?.value);

    if (indeterminate) {
      el.indeterminate = true;
      el.checked = false;
      return;
    }

    el.indeterminate = false;
    el.checked = checked === true;
  } catch {}
}

export const vTriState = {
  mounted(el, binding) {
    _applyTriState(el, binding);
  },
  updated(el, binding) {
    _applyTriState(el, binding);
  },
};
