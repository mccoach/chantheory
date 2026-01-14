// src/composables/useUniverseBuilder.js
// ==============================
// 本轮新增：懒排序（冻结自选排序键）
//   - 当排序 key=__starred__（自选列）时：点击排序那一刻生成 starredRankMap 快照
//   - 排序过程中只使用快照，不实时读取 watchlistSet，从而避免“取消星标后行位置立刻跳动”
//
// V4 - 复权/频率选择彻底去约束（按你最终规则）
//   - 默认值只是草稿：freq 默认 1d；adjust 默认 qfq
//   - 允许用户把 freq/adjust 全部取消为空集合
//   - 对 stock：任务派发规则写死（none + factors），不由此处“约束”
//   - 对 non-stock：严格按用户选择的 freq×adjust 做笛卡尔积；任一为空 => 0
// ==============================

import { computed, ref } from "vue";

const ALL_FREQS = ["1d", "1w", "1M", "1m", "5m", "15m", "30m", "60m"];
const DAY_FREQS = ["1d", "1w", "1M"];
const MIN_FREQS = ["1m", "5m", "15m", "30m", "60m"];
const ALL_ADJUSTS = ["none", "qfq", "hfq"];

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function normalizeFreq(v) {
  const s = asStr(v);
  return ALL_FREQS.includes(s) ? s : null;
}

function normalizeAdjust(v) {
  const s = asStr(v);
  return ALL_ADJUSTS.includes(s) ? s : null;
}

function intersectSize(a, b) {
  const A = a instanceof Set ? a : new Set();
  const B = b instanceof Set ? b : new Set();
  let cnt = 0;
  const [small, large] = A.size <= B.size ? [A, B] : [B, A];
  for (const x of small) if (large.has(x)) cnt += 1;
  return cnt;
}

function unionSet(a, b) {
  const out = new Set();
  if (a instanceof Set) for (const x of a) out.add(x);
  if (b instanceof Set) for (const x of b) out.add(x);
  return out;
}

function diffSet(a, b) {
  const out = new Set();
  if (!(a instanceof Set)) return out;
  const bb = b instanceof Set ? b : new Set();
  for (const x of a) if (!bb.has(x)) out.add(x);
  return out;
}

function stableSortWithBaseOrder(items, baseOrderMap, compareFn) {
  const arr = Array.isArray(items) ? items.slice() : [];
  arr.sort((a, b) => {
    const c = compareFn(a, b);
    if (c !== 0) return c;

    const sa = asStr(a?.symbol);
    const sb = asStr(b?.symbol);

    const oa = baseOrderMap.get(sa);
    const ob = baseOrderMap.get(sb);

    if (Number.isFinite(oa) && Number.isFinite(ob)) return oa - ob;
    if (Number.isFinite(oa)) return -1;
    if (Number.isFinite(ob)) return 1;

    return sa.localeCompare(sb);
  });
  return arr;
}

function buildBaseOrderMap(list) {
  const m = new Map();
  const arr = Array.isArray(list) ? list : [];
  for (let i = 0; i < arr.length; i++) {
    const sym = asStr(arr[i]?.symbol);
    if (sym) m.set(sym, i);
  }
  return m;
}

function makeScopeKey(group, value) {
  const g = asStr(group);
  const v = asStr(value);
  return `${g}:${v}`;
}

function isStockItem(it) {
  return String(it?.class || "").toLowerCase() === "stock";
}

function buildStarredRankMap(list, starredSet) {
  const out = new Map();
  const arr = Array.isArray(list) ? list : [];
  const ss = starredSet instanceof Set ? starredSet : new Set();

  for (const it of arr) {
    const sym = asStr(it?.symbol);
    if (!sym) continue;
    out.set(sym, ss.has(sym) ? 1 : 0);
  }
  return out;
}

export function useUniverseBuilder({ itemsRef, watchlistSetRef } = {}) {
  // ==============================
  // 1) 基础数据
  // ==============================
  const itemsAll = computed(() => {
    const arr = itemsRef?.value;
    return Array.isArray(arr) ? arr : [];
  });

  // selectedSet：唯一真相源（Set<symbol>）
  // 默认空集合 => 快速筛选/标的选择初始全不选
  const selectedSet = ref(new Set());

  // ==============================
  // 2) freq / adjust（默认值只是草稿）
  // ==============================
  const selectedFreqs = ref(new Set(["1d"]));
  const selectedAdjusts = ref(new Set(["qfq"]));

  function toggleFreq(freq) {
    const f = normalizeFreq(freq);
    if (!f) return;
    const next = new Set(selectedFreqs.value);
    if (next.has(f)) next.delete(f);
    else next.add(f);
    // NEW: 允许 freq 为空（你要求），不做自动补回
    selectedFreqs.value = next;
  }

  function selectAllDayFreqs() {
    selectedFreqs.value = new Set(DAY_FREQS);
  }

  function selectAllMinuteFreqs() {
    selectedFreqs.value = new Set(MIN_FREQS);
  }

  function toggleAdjust(adj) {
    const a = normalizeAdjust(adj);
    if (!a) return;

    const next = new Set(selectedAdjusts.value);
    if (next.has(a)) next.delete(a);
    else next.add(a);

    // NEW: 允许 adjust 为空（你要求），不做自动补回
    selectedAdjusts.value = next;
  }

  // ==============================
  // 3) 统计（保留：是否包含非 stock）
  // ==============================
  const selectionStats = computed(() => {
    const map = new Map();
    for (const it of itemsAll.value) {
      const sym = asStr(it?.symbol);
      if (sym) map.set(sym, it);
    }

    let nTotal = 0;
    let hasNonStock = false;

    for (const s of selectedSet.value) {
      const it = map.get(s);
      if (!it) continue;
      nTotal += 1;
      if (!isStockItem(it)) hasNonStock = true;
    }

    return { nTotal, hasNonStock };
  });

  const counts = computed(() => ({ nTotal: selectionStats.value.nTotal }));

  // 保留字段（未来可能用于显示），但不再用于“UI禁用”
  const adjustEnabled = computed(() => selectionStats.value.hasNonStock === true);

  // 任务数估算（占位接口）：允许 A/F 为 0
  const jobEstimate = computed(() => {
    const n = counts.value.nTotal;
    const F = selectedFreqs.value.size;
    const A = selectedAdjusts.value.size;
    const jobs_total = n * F * A;
    return { F, A, jobs_total };
  });

  // ==============================
  // 4) 分组集合：watchlist / market / board / class / type
  // ==============================
  const groupDefs = computed(() => {
    const items = itemsAll.value;
    const watchSet = watchlistSetRef?.value instanceof Set ? watchlistSetRef.value : new Set();

    const markets = new Map();
    const boards = new Map();
    const classes = new Map();
    const types = new Map();

    for (const it of items) {
      const sym = asStr(it?.symbol);
      if (!sym) continue;

      const mk = asStr(it?.market).toUpperCase();
      if (mk) {
        if (!markets.has(mk)) markets.set(mk, new Set());
        markets.get(mk).add(sym);
      }

      const bd = asStr(it?.board);
      if (bd) {
        if (!boards.has(bd)) boards.set(bd, new Set());
        boards.get(bd).add(sym);
      }

      const cls = asStr(it?.class).toLowerCase();
      if (cls) {
        if (!classes.has(cls)) classes.set(cls, new Set());
        classes.get(cls).add(sym);
      }

      const tp = asStr(it?.type).toUpperCase();
      if (tp) {
        if (!types.has(tp)) types.set(tp, new Set());
        types.get(tp).add(sym);
      }
    }

    const watchlistGroup = {
      groupKey: "watchlist",
      items: [
        {
          scopeKey: makeScopeKey("watchlist", "all"),
          label: "自选",
          universeSet: new Set(Array.from(watchSet)),
        },
      ],
    };

    const marketGroup = {
      groupKey: "market",
      items: Array.from(markets.entries())
        .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
        .map(([k, set]) => ({
          scopeKey: makeScopeKey("market", k),
          label: k,
          universeSet: set,
        })),
    };

    const boardGroup = {
      groupKey: "board",
      items: Array.from(boards.entries())
        .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
        .map(([k, set]) => ({
          scopeKey: makeScopeKey("board", k),
          label: k,
          universeSet: set,
        })),
    };

    const classGroup = {
      groupKey: "class",
      items: Array.from(classes.entries())
        .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
        .map(([k, set]) => ({
          scopeKey: makeScopeKey("class", k),
          label: k,
          universeSet: set,
        })),
    };

    const typeGroup = {
      groupKey: "type",
      items: Array.from(types.entries())
        .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
        .map(([k, set]) => ({
          scopeKey: makeScopeKey("type", k),
          label: k,
          universeSet: set,
        })),
    };

    return [watchlistGroup, marketGroup, boardGroup, classGroup, typeGroup];
  });

  // ==============================
  // 5) 行级勾选
  // ==============================
  function toggleSymbolSelected(symbol) {
    const sym = asStr(symbol);
    if (!sym) return;

    const next = new Set(selectedSet.value);
    if (next.has(sym)) next.delete(sym);
    else next.add(sym);

    selectedSet.value = next;
  }

  // ==============================
  // 6) 排序（稳定排序 + 自选懒排序）
  // ==============================
  const sortState = ref({ key: "symbol", dir: "asc" });
  const baseOrderMapRef = ref(buildBaseOrderMap(itemsAll.value));

  const starredRankMapRef = ref(null);

  function setSort(key) {
    const k = asStr(key);
    if (!k) return;

    baseOrderMapRef.value = buildBaseOrderMap(sortedItems.value);

    if (k === "__starred__") {
      const starredSet = watchlistSetRef?.value instanceof Set ? watchlistSetRef.value : new Set();
      starredRankMapRef.value = buildStarredRankMap(itemsAll.value, starredSet);
    } else {
      starredRankMapRef.value = null;
    }

    const cur = sortState.value || { key: "symbol", dir: "asc" };
    let dir = "asc";
    if (cur.key === k) dir = cur.dir === "asc" ? "desc" : "asc";
    sortState.value = { key: k, dir };
  }

  function normalizeComparable(v) {
    if (v == null) return "";
    return v;
  }

  function compareByKey(a, b, key, dir, starredSet, starredRankMap) {
    const d = dir === "desc" ? -1 : 1;

    if (key === "__selected__") {
      const sa = selectedSet.value.has(asStr(a?.symbol)) ? 1 : 0;
      const sb = selectedSet.value.has(asStr(b?.symbol)) ? 1 : 0;
      if (sa === sb) return 0;
      return sa > sb ? 1 * d : -1 * d;
    }

    if (key === "__starred__") {
      const symA = asStr(a?.symbol);
      const symB = asStr(b?.symbol);

      if (starredRankMap instanceof Map) {
        const ra = starredRankMap.get(symA) || 0;
        const rb = starredRankMap.get(symB) || 0;
        if (ra === rb) return 0;
        return ra > rb ? 1 * d : -1 * d;
      }

      const sa = starredSet.has(symA) ? 1 : 0;
      const sb = starredSet.has(symB) ? 1 : 0;
      if (sa === sb) return 0;
      return sa > sb ? 1 * d : -1 * d;
    }

    const va = normalizeComparable(a?.[key]);
    const vb = normalizeComparable(b?.[key]);

    const na = Number(va);
    const nb = Number(vb);
    const bothNum = Number.isFinite(na) && Number.isFinite(nb);

    if (bothNum) {
      if (na === nb) return 0;
      return na > nb ? 1 * d : -1 * d;
    }

    const sa = String(va == null ? "" : va);
    const sb = String(vb == null ? "" : vb);
    if (sa === sb) return 0;
    return sa.localeCompare(sb) * d;
  }

  const sortedItems = computed(() => {
    const list = itemsAll.value;

    const starredSet = watchlistSetRef?.value instanceof Set ? watchlistSetRef.value : new Set();

    const { key, dir } = sortState.value || {};
    const sortKey = asStr(key) || "symbol";
    const sortDir = dir === "desc" ? "desc" : "asc";

    const baseOrderMap = baseOrderMapRef.value instanceof Map ? baseOrderMapRef.value : buildBaseOrderMap(list);

    const starredRankMap = sortKey === "__starred__" ? starredRankMapRef.value : null;

    return stableSortWithBaseOrder(list, baseOrderMap, (a, b) =>
      compareByKey(a, b, sortKey, sortDir, starredSet, starredRankMap)
    );
  });

  // ==============================
  // 7) selectorGroups（三态展示所需的统计：selectedCount/totalCount）
  // ==============================
  const selectorGroups = computed(() => {
    const groups = [];

    for (const g of groupDefs.value) {
      const items = [];
      for (const it of g.items) {
        const U = it.universeSet instanceof Set ? it.universeSet : new Set();
        const selectedCount = intersectSize(selectedSet.value, U);
        const totalCount = U.size;

        const checked = totalCount > 0 && selectedCount === totalCount;
        const indeterminate = totalCount > 0 && selectedCount > 0 && selectedCount < totalCount;

        items.push({
          scopeKey: it.scopeKey,
          label: it.label,
          universeSet: U,
          checked,
          indeterminate,
          selectedCount,
          totalCount,
        });
      }

      groups.push({ groupKey: g.groupKey, items });
    }

    return groups;
  });

  // ==============================
  // 8) 导出数据
  // ==============================
  const selectedRowsForExport = computed(() => {
    const out = [];
    const sel = selectedSet.value;

    for (const it of sortedItems.value) {
      const sym = asStr(it?.symbol);
      if (!sym) continue;
      if (sel.has(sym)) out.push(it);
    }
    return out;
  });

  // ==============================
  // 9) tri 单源辅助（供 DataDownloadDialog 绑定 tri 控制器）
  // ==============================
  function triSetSnapshotForScope(scopeKey, universeSet) {
    const key = asStr(scopeKey);
    if (!key) return;
    const U = universeSet instanceof Set ? universeSet : new Set();
    const snap = new Set();
    const S = selectedSet.value;
    const [small, large] = S.size <= U.size ? [S, U] : [U, S];
    for (const x of small) if (large.has(x)) snap.add(x);
    _triSnapshotMap.value.set(key, snap);
  }

  function triGetSnapshotForScope(scopeKey) {
    const key = asStr(scopeKey);
    if (!key) return new Set();
    return _triSnapshotMap.value.get(key) || new Set();
  }

  const _triSnapshotMap = ref(new Map());

  function triSyncSnapshotsOnExternalChange(sourceScopeKey, scopes) {
    const src = asStr(sourceScopeKey);
    const list = Array.isArray(scopes) ? scopes : [];

    const next = new Map(_triSnapshotMap.value);

    for (const sc of list) {
      const key = asStr(sc?.scopeKey);
      if (!key) continue;

      const U = sc?.universeSet instanceof Set ? sc.universeSet : new Set();

      if (src && key === src) continue;

      const snap = new Set();
      const S = selectedSet.value;
      const [small, large] = S.size <= U.size ? [S, U] : [U, S];
      for (const x of small) if (large.has(x)) snap.add(x);

      next.set(key, snap);
    }

    _triSnapshotMap.value = next;
  }

  // ==============================
  // 10) scope 操作（供 tri controller 调用）
  // ==============================
  function applyScopeAll(scopeKey, universeSet) {
    const U = universeSet instanceof Set ? universeSet : new Set();
    selectedSet.value = unionSet(selectedSet.value, U);
  }

  function applyScopeNone(scopeKey, universeSet) {
    const U = universeSet instanceof Set ? universeSet : new Set();
    selectedSet.value = diffSet(selectedSet.value, U);
  }

  function applyScopeSnapshot(scopeKey, universeSet, snapshotSet) {
    const U = universeSet instanceof Set ? universeSet : new Set();
    const snap = snapshotSet instanceof Set ? snapshotSet : new Set();

    let next = diffSet(selectedSet.value, U);
    next = unionSet(next, snap);
    selectedSet.value = next;
  }

  return {
    itemsAll,
    sortedItems,

    selectedSet,
    toggleSymbolSelected,

    selectorGroups,

    sortState,
    setSort,

    selectedFreqs,
    toggleFreq,
    selectAllDayFreqs,
    selectAllMinuteFreqs,

    selectedAdjusts,
    toggleAdjust,
    adjustEnabled,

    counts,
    jobEstimate,

    selectedRowsForExport,

    triSyncSnapshotsOnExternalChange,
    triSetSnapshotForScope,
    triGetSnapshotForScope,

    applyScopeAll,
    applyScopeNone,
    applyScopeSnapshot,
  };
}
