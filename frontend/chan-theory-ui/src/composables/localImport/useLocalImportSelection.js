// src/composables/localImport/useLocalImportSelection.js
// ==============================
// Local Import 弹窗：候选选择 / 快选 / 防重复提交
//
// 职责：
//   - 维护 selectedSet（唯一真相源）
//   - 构建快选 scope 的 universeSet
//   - 提供三态快选 UI 状态
//   - 提供候选表排序、选中判断
//   - 提供“重复提交判断”所需的 lastSubmittedSelectionSet
//
// 边界：
//   - 不做 HTTP
//   - 不做 dialog/footer 管理
//   - 不做弹窗 UI 布局
// ==============================

import { computed, ref } from "vue";
import { createTriStateController } from "@/composables/useTriToggle";

const ALL_SCOPE_KEY = "all:all";
const EMPTY_UI = { checked: false, indeterminate: false };

const MARKET_LABELS = {
  SH: "SH",
  SZ: "SZ",
  BJ: "BJ",
};

const CLASS_LABELS = {
  stock: "股票",
  fund: "基金",
  index: "指数",
};

const FIXED_FREQ_LABELS = {
  "1d": "1d",
  "5m": "5m",
  "1m": "1m",
};

const TYPE_GROUPS = {
  stock: [
    "科创板股票",
    "主板A股",
    "B股",
    "优先股",
    "创业板股票",
    "北交所股票",
  ],
  index: [
    "官方指数",
    "通达信指数",
  ],
  fund: [
    "场内ETF",
    "LOF基金",
    "公募REITs",
    "封闭式基金",
    "开放式基金",
  ],
};

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function asUpper(x) {
  return asStr(x).toUpperCase();
}

function selectionKey(item) {
  const it = item && typeof item === "object" ? item : {};
  return `${asUpper(it.market)}:${asStr(it.symbol)}|${asStr(it.freq)}`;
}

function scopeKey(group, value) {
  return `${asStr(group)}:${asStr(value)}`;
}

function normalizeClassLabel(v) {
  const k = asStr(v).toLowerCase();
  return CLASS_LABELS[k] || asStr(v);
}

function normalizeFileTime(v) {
  return v == null ? "" : asStr(v);
}

function cloneSet(src) {
  return src instanceof Set ? new Set(src) : new Set();
}

function setEquals(a, b) {
  if (!(a instanceof Set) || !(b instanceof Set)) return false;
  if (a.size !== b.size) return false;
  for (const x of a) {
    if (!b.has(x)) return false;
  }
  return true;
}

export function useLocalImportSelection({ candidatesRef }) {
  const selectedSet = ref(new Set());
  const lastSubmittedSelectionSet = ref(null);
  const sortState = ref({ key: "symbol", dir: "asc" });

  const candidateRows = computed(() => {
    const list = Array.isArray(candidatesRef?.value) ? candidatesRef.value : [];
    return list.map((it) => ({
      market: asUpper(it.market),
      symbol: asStr(it.symbol),
      freq: asStr(it.freq),
      name: asStr(it.name),
      class: asStr(it.class).toLowerCase(),
      classText: normalizeClassLabel(it.class),
      type: asStr(it.type),
      fileTime: normalizeFileTime(it.file_datetime),
      updatedAt: "",
      _rowKey: selectionKey(it),
    }));
  });

  const allUniverseSet = computed(() => {
    const out = new Set();
    for (const row of candidateRows.value) out.add(row._rowKey);
    return out;
  });

  function buildScopeSetByPredicate(predicate) {
    const out = new Set();
    for (const row of candidateRows.value) {
      if (predicate(row)) out.add(row._rowKey);
    }
    return out;
  }

  const scopeUniverseMap = computed(() => {
    const map = new Map();

    map.set(ALL_SCOPE_KEY, allUniverseSet.value);

    map.set(scopeKey("market", "SH"), buildScopeSetByPredicate((r) => r.market === "SH"));
    map.set(scopeKey("market", "SZ"), buildScopeSetByPredicate((r) => r.market === "SZ"));
    map.set(scopeKey("market", "BJ"), buildScopeSetByPredicate((r) => r.market === "BJ"));

    map.set(scopeKey("class", "stock"), buildScopeSetByPredicate((r) => r.class === "stock"));
    map.set(scopeKey("class", "fund"), buildScopeSetByPredicate((r) => r.class === "fund"));
    map.set(scopeKey("class", "index"), buildScopeSetByPredicate((r) => r.class === "index"));

    map.set(scopeKey("freq", "1d"), buildScopeSetByPredicate((r) => r.freq === "1d"));
    map.set(scopeKey("freq", "5m"), buildScopeSetByPredicate((r) => r.freq === "5m"));
    map.set(scopeKey("freq", "1m"), buildScopeSetByPredicate((r) => r.freq === "1m"));

    for (const tp of TYPE_GROUPS.stock) {
      map.set(scopeKey("type", tp), buildScopeSetByPredicate((r) => r.class === "stock" && r.type === tp));
    }
    for (const tp of TYPE_GROUPS.index) {
      map.set(scopeKey("type", tp), buildScopeSetByPredicate((r) => r.class === "index" && r.type === tp));
    }
    for (const tp of TYPE_GROUPS.fund) {
      map.set(scopeKey("type", tp), buildScopeSetByPredicate((r) => r.class === "fund" && r.type === tp));
    }

    return map;
  });

  const tri = createTriStateController({
    getUi(_scopeKey, universeSet) {
      const U = universeSet instanceof Set ? universeSet : new Set();
      let selectedCount = 0;
      for (const k of U) {
        if (selectedSet.value.has(k)) selectedCount += 1;
      }
      const totalCount = U.size;
      return {
        checked: totalCount > 0 && selectedCount === totalCount,
        indeterminate: totalCount > 0 && selectedCount > 0 && selectedCount < totalCount,
        selectedCount,
        totalCount,
      };
    },

    applyAll(_scopeKey, universeSet) {
      const U = universeSet instanceof Set ? universeSet : new Set();
      const next = new Set(selectedSet.value);
      for (const k of U) next.add(k);
      selectedSet.value = next;
    },

    applyNone(_scopeKey, universeSet) {
      const U = universeSet instanceof Set ? universeSet : new Set();
      const next = new Set(selectedSet.value);
      for (const k of U) next.delete(k);
      selectedSet.value = next;
    },

    applySnapshot(_scopeKey, universeSet, snapshotSet) {
      const U = universeSet instanceof Set ? universeSet : new Set();
      const S = snapshotSet instanceof Set ? snapshotSet : new Set();

      const next = new Set(selectedSet.value);
      for (const k of U) next.delete(k);
      for (const k of S) next.add(k);

      selectedSet.value = next;
    },

    buildSnapshot(_scopeKey, universeSet) {
      const U = universeSet instanceof Set ? universeSet : new Set();
      const snap = new Set();
      for (const k of U) {
        if (selectedSet.value.has(k)) snap.add(k);
      }
      return snap;
    },
  });

  const allScopeDescriptors = computed(() => {
    const list = [];

    list.push({
      scopeKey: ALL_SCOPE_KEY,
      universeSet: scopeUniverseMap.value.get(ALL_SCOPE_KEY) || new Set(),
    });

    for (const key of ["SH", "SZ", "BJ"]) {
      list.push({
        scopeKey: scopeKey("market", key),
        universeSet: scopeUniverseMap.value.get(scopeKey("market", key)) || new Set(),
      });
    }

    for (const key of ["stock", "fund", "index"]) {
      list.push({
        scopeKey: scopeKey("class", key),
        universeSet: scopeUniverseMap.value.get(scopeKey("class", key)) || new Set(),
      });
    }

    for (const key of ["1d", "5m", "1m"]) {
      list.push({
        scopeKey: scopeKey("freq", key),
        universeSet: scopeUniverseMap.value.get(scopeKey("freq", key)) || new Set(),
      });
    }

    for (const tp of TYPE_GROUPS.stock) {
      list.push({
        scopeKey: scopeKey("type", tp),
        universeSet: scopeUniverseMap.value.get(scopeKey("type", tp)) || new Set(),
      });
    }
    for (const tp of TYPE_GROUPS.index) {
      list.push({
        scopeKey: scopeKey("type", tp),
        universeSet: scopeUniverseMap.value.get(scopeKey("type", tp)) || new Set(),
      });
    }
    for (const tp of TYPE_GROUPS.fund) {
      list.push({
        scopeKey: scopeKey("type", tp),
        universeSet: scopeUniverseMap.value.get(scopeKey("type", tp)) || new Set(),
      });
    }

    return list;
  });

  function calcScopeUi(universeSet) {
    const U = universeSet instanceof Set ? universeSet : new Set();
    let selectedCount = 0;
    for (const k of U) {
      if (selectedSet.value.has(k)) selectedCount += 1;
    }
    const totalCount = U.size;

    return {
      checked: totalCount > 0 && selectedCount === totalCount,
      indeterminate: totalCount > 0 && selectedCount > 0 && selectedCount < totalCount,
      selectedCount,
      totalCount,
    };
  }

  const scopeUiMap = computed(() => {
    const out = {};
    for (const sc of allScopeDescriptors.value) {
      tri.ensureScope(sc.scopeKey, sc.universeSet);
      out[sc.scopeKey] = calcScopeUi(sc.universeSet);
    }
    return out;
  });

  function syncSnapshotsExcept(scopeKey0) {
    tri.syncSnapshotsOnExternalChange(scopeKey0, allScopeDescriptors.value);
  }

  function onScopeToggle(scopeKey0) {
    const U = scopeUniverseMap.value.get(scopeKey0) || new Set();
    tri.ensureScope(scopeKey0, U);
    tri.cycle(scopeKey0, U);
    syncSnapshotsExcept(scopeKey0);
  }

  const marketScopeItems = computed(() => [
    { scopeKey: scopeKey("market", "SH"), label: MARKET_LABELS.SH },
    { scopeKey: scopeKey("market", "SZ"), label: MARKET_LABELS.SZ },
    { scopeKey: scopeKey("market", "BJ"), label: MARKET_LABELS.BJ },
  ]);

  const classScopeItems = computed(() => [
    { scopeKey: scopeKey("class", "stock"), label: CLASS_LABELS.stock },
    { scopeKey: scopeKey("class", "fund"), label: CLASS_LABELS.fund },
    { scopeKey: scopeKey("class", "index"), label: CLASS_LABELS.index },
  ]);

  const freqScopeItems = computed(() => [
    { scopeKey: scopeKey("freq", "1d"), label: FIXED_FREQ_LABELS["1d"] },
    { scopeKey: scopeKey("freq", "5m"), label: FIXED_FREQ_LABELS["5m"] },
    { scopeKey: scopeKey("freq", "1m"), label: FIXED_FREQ_LABELS["1m"] },
  ]);

  const stockTypeScopeItems = computed(() =>
    TYPE_GROUPS.stock.map((x) => ({ scopeKey: scopeKey("type", x), label: x }))
  );
  const indexTypeScopeItems = computed(() =>
    TYPE_GROUPS.index.map((x) => ({ scopeKey: scopeKey("type", x), label: x }))
  );
  const fundTypeScopeItems = computed(() =>
    TYPE_GROUPS.fund.map((x) => ({ scopeKey: scopeKey("type", x), label: x }))
  );

  function scopeCountText(scopeKey0) {
    const ui = scopeUiMap.value[scopeKey0];
    if (!ui) return "(0/0)";
    return `(${ui.selectedCount}/${ui.totalCount})`;
  }

  const sortedCandidates = computed(() => {
    const list = candidateRows.value.slice();
    const { key, dir } = sortState.value || {};
    const d = dir === "desc" ? -1 : 1;
    const sortKey = asStr(key) || "symbol";

    list.sort((a, b) => {
      if (sortKey === "__selected__") {
        const sa = selectedSet.value.has(a._rowKey) ? 1 : 0;
        const sb = selectedSet.value.has(b._rowKey) ? 1 : 0;
        if (sa !== sb) return (sa - sb) * d;
        return a._rowKey.localeCompare(b._rowKey);
      }

      if (sortKey === "__starred__") {
        return a._rowKey.localeCompare(b._rowKey);
      }

      const va = String(a?.[sortKey] ?? "");
      const vb = String(b?.[sortKey] ?? "");
      if (va === vb) return a._rowKey.localeCompare(b._rowKey);
      return va.localeCompare(vb) * d;
    });

    return list;
  });

  function selectedItems() {
    const out = [];
    for (const row of sortedCandidates.value) {
      if (!selectedSet.value.has(row._rowKey)) continue;
      out.push({
        market: row.market,
        symbol: row.symbol,
        freq: row.freq,
      });
    }
    return out;
  }

  function isSelected(row) {
    return selectedSet.value.has(asStr(row?._rowKey));
  }

  function onToggleSelect(row) {
    const key = asStr(row?._rowKey);
    if (!key) return;

    const next = new Set(selectedSet.value);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    selectedSet.value = next;

    syncSnapshotsExcept("__row_toggle__");
  }

  return {
    ALL_SCOPE_KEY,
    EMPTY_UI,

    selectedSet,
    lastSubmittedSelectionSet,
    sortState,

    candidateRows,
    sortedCandidates,

    scopeUiMap,
    marketScopeItems,
    classScopeItems,
    freqScopeItems,
    stockTypeScopeItems,
    indexTypeScopeItems,
    fundTypeScopeItems,

    cloneSet,
    setEquals,
    scopeCountText,
    onScopeToggle,
    isSelected,
    onToggleSelect,
    selectedItems,
  };
}
