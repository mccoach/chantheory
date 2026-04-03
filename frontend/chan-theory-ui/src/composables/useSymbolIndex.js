// frontend/chan-theory-ui/src/composables/useSymbolIndex.js
// ==============================
// V14.4 - CLEAN: 移除本轮排查诊断日志，保留正式修复
//
// 保留修复：
//   - 新增 backendLoaded：区分“本地兜底可用”与“后端正式快照已加载”
//   - useLocalOrBuiltin() 只负责兜底可搜索，不代表后端快照已完成
//   - ensureLoaded() 以 backendLoaded 为准，保证至少尝试一次后端快照加载
//
// 本轮清理：
//   - 删除 symbol_index 排查用的诊断日志、诊断辅助函数、诊断状态字段
//   - 不改业务语义
//   - 不改函数顺序
// ==============================

import { ref, readonly } from "vue";
import { api } from "@/api/client";
import RAW from "@/assets/symbols.index.json";

const LS_KEY = "chan_symbol_index_v1";
const LS_TS_KEY = "chan_symbol_index_updated_at";

const ready = ref(false);
const loading = ref(false);
const error = ref("");

// 区分“后端快照是否已正式加载”
const backendLoaded = ref(false);

const idx = ref([]);

let TinyPinyinMod = null;
let _loadingPromise = null;

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function nowTs() {
  return new Date().toISOString();
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function ensurePinyinLib() {
  if (TinyPinyinMod) return true;
  try {
    const mod = await import(/* @vite-ignore */ "tiny-pinyin");
    TinyPinyinMod = mod?.default || mod || null;
  } catch {
    TinyPinyinMod = null;
  }
  return !!TinyPinyinMod;
}

function loadCache() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveCache(items, updatedAt) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(items || []));
    if (updatedAt) localStorage.setItem(LS_TS_KEY, updatedAt);
  } catch {}
}

function enrichPinyin(item) {
  const name = String(item.name || "");
  if (name && TinyPinyinMod?.isSupported?.()) {
    const full = TinyPinyinMod.convertToPinyin(name, "", true).toLowerCase();
    const abbr = TinyPinyinMod.convertToPinyin(name, " ", true)
      .split(" ")
      .map((w) => (w ? w[0] : ""))
      .join("")
      .toLowerCase();
    item.pinyin = full;
    item.pinyin_abbr = abbr;
  } else {
    item.pinyin = item.pinyin || "";
    item.pinyin_abbr = item.pinyin_abbr || "";
  }
  return item;
}

function buildIndex(raw) {
  const arr = Array.isArray(raw) ? raw : [];
  return arr
    .filter((x) => x && x.symbol && x.name && x.market)
    .map((x) =>
      enrichPinyin({
        symbol: asStr(x.symbol),
        name: asStr(x.name),
        market: asStr(x.market).toUpperCase(),
        class: x.class == null ? null : asStr(x.class),
        type: x.type == null ? null : asStr(x.type),
        listingDate:
          x.listingDate != null
            ? x.listingDate
            : x.listing_date != null
              ? x.listing_date
              : null,
        pinyin: x.pinyin || "",
        pinyin_abbr: x.pinyin_abbr || "",
      })
    );
}

function isMatch(q, it) {
  const s = q.toLowerCase();
  return (
    it.symbol.startsWith(q) ||
    (it.pinyin && it.pinyin.startsWith(s)) ||
    (it.pinyin_abbr && it.pinyin_abbr.startsWith(s)) ||
    it.name.includes(q)
  );
}

function useLocalOrBuiltin() {
  const cached = loadCache();
  if (cached && cached.length) {
    idx.value = buildIndex(cached);
    ready.value = true;
    // 这里只代表 fallback 可用，不代表 backend 已加载
    backendLoaded.value = false;

    console.log(`${nowTs()} [SymbolIndex] load-cache count=${idx.value.length}`);
    return true;
  }

  idx.value = buildIndex(RAW);
  ready.value = true;
  // builtin 只是兜底
  backendLoaded.value = false;

  console.log(`${nowTs()} [SymbolIndex] use-builtin count=${idx.value.length}`);
  return false;
}

async function fetchIndexSnapshot() {
  try {
    const { data } = await api.get("/api/symbols/index", { timeout: 20000 });

    if (Array.isArray(data?.items) && data.items.length) {
      idx.value = buildIndex(data.items);
      ready.value = true;
      backendLoaded.value = true;
      saveCache(data.items, data.updated_at || new Date().toISOString());

      console.log(
        `${nowTs()} [SymbolIndex] snapshot-refreshed count=${data.items.length} updated_at=${data.updated_at || "null"}`
      );

      return { ok: true };
    }

    console.warn(`${nowTs()} [SymbolIndex] snapshot-empty fallback-cache-or-builtin`);
    useLocalOrBuiltin();
    return { ok: false, message: "snapshot empty" };
  } catch (e) {
    console.warn(`${nowTs()} [SymbolIndex] snapshot-fetch-failed fallback-cache-or-builtin`, e);
    useLocalOrBuiltin();
    return { ok: false, message: e?.message || "snapshot fetch failed" };
  }
}

async function ensureLoaded() {
  await ensurePinyinLib();

  // 不再以 ready 为“后端已加载”的判据
  if (backendLoaded.value) {
    return { ok: true };
  }

  if (_loadingPromise) return _loadingPromise;

  loading.value = true;
  error.value = "";

  _loadingPromise = (async () => {
    try {
      const r = await fetchIndexSnapshot();
      return { ok: r.ok, message: r.message };
    } catch (e) {
      error.value = e?.message || "symbol_index load failed";
      return { ok: false, message: error.value };
    } finally {
      loading.value = false;
      _loadingPromise = null;
    }
  })();

  return _loadingPromise;
}

async function waitReadable(options = {}) {
  const timeoutMs = Math.max(1000, Number(options?.timeoutMs || 60000));
  const deadline = Date.now() + timeoutMs;

  while (loading.value) {
    if (Date.now() > deadline) {
      return { ok: false, message: "[SymbolIndex] waitReadable timeout" };
    }
    await sleep(100);
  }

  return { ok: true };
}

export function useSymbolIndex() {
  if (!ready.value) {
    useLocalOrBuiltin();

    ensurePinyinLib().then((ok) => {
      if (ok) {
        const cached = loadCache();
        if (cached && cached.length) {
          idx.value = buildIndex(cached);
          ready.value = true;
          backendLoaded.value = false;
        } else {
          idx.value = buildIndex(RAW);
          ready.value = true;
          backendLoaded.value = false;
        }
      }
    });
  }

  function search(query, limit = 20) {
    const q = asStr(query);
    if (!q) return [];
    const out = [];
    for (const it of idx.value) {
      if (isMatch(q, it)) {
        out.push(it);
        if (out.length >= limit) break;
      }
    }

    return out;
  }

  function findBySymbol(symbol, market) {
    const q = asStr(symbol);
    const mk = asStr(market).toUpperCase();
    if (!q || !mk) return null;

    return (
      idx.value.find(
        (it) => it.symbol === q && asStr(it.market).toUpperCase() === mk
      ) || null
    );
  }

  function listAll({ clone = true } = {}) {
    const arr = Array.isArray(idx.value) ? idx.value : [];
    return clone === false ? arr : arr.slice();
  }

  return {
    ready: readonly(ready),
    loading: readonly(loading),
    error: readonly(error),

    search,
    findBySymbol,
    listAll,

    ensureLoaded,
    waitReadable,
  };
}
