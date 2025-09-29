// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useSymbolIndex.js
// 标的索引（Local-first）：优先本地缓存 → 后端 /api/symbols/index → 内置示例
// - 可选动态加载 tiny-pinyin；若依赖缺失则自动降级（仅代码/中文匹配，不报错）
// - API：ready, search(query, limit), findBySymbol(symbol), ensureIndexFresh(force)

import { ref } from "vue";
import { api } from "@/api/client";
import RAW from "@/assets/symbols.index.json";

const LS_KEY = "chan_symbol_index_v1";
const LS_TS_KEY = "chan_symbol_index_updated_at";

const ready = ref(false);
const idx = ref([]);

// 可选拼音引擎（动态加载 tiny-pinyin）
let TinyPinyinMod = null;
async function ensurePinyinLib() {
  if (TinyPinyinMod) return true;
  try {
    const mod = await import(/* @vite-ignore */ "tiny-pinyin");
    // 兼容 default 与命名导出
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

// 为条目补齐拼音字段（如果可用）
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
    .filter((x) => x && x.symbol && x.name)
    .map((x) =>
      enrichPinyin({
        symbol: String(x.symbol).trim(),
        name: String(x.name).trim(),
        market: String(x.market || "").toUpperCase(),
        type: String(x.type || "").toUpperCase(),
        pinyin: x.pinyin || "",
        pinyin_abbr: x.pinyin_abbr || "",
      })
    );
}

// 匹配规则：代码前缀 / 拼音前缀 / 拼音首字母前缀 / 中文包含
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
    return true;
  }
  idx.value = buildIndex(RAW);
  ready.value = true;
  return false;
}

// 启动时拉取后端索引，写入本地缓存；加载前尽量加载拼音库以生成拼音字段
export async function ensureIndexFresh(force = false) {
  // 可选加载拼音库（不阻塞后续流程）
  await ensurePinyinLib();
  try {
    const url = `/api/symbols/index${force ? "?refresh=1" : ""}`;
    const { data } = await api.get(url, { timeout: 20000 });
    if (Array.isArray(data?.items) && data.items.length) {
      idx.value = buildIndex(data.items);
      ready.value = true;
      saveCache(data.items, data.updated_at || new Date().toISOString());
      return true;
    }
  } catch {
    // 忽略网络错误，继续回退
  }
  return useLocalOrBuiltin();
}

export function useSymbolIndex() {
  if (!ready.value) {
    // 启动时先用本地/内置，避免首屏空白
    useLocalOrBuiltin();
    // 异步尝试加载拼音库并重建索引（改善拼音检索体验）
    ensurePinyinLib().then((ok) => {
      if (ok) {
        const cached = loadCache();
        if (cached && cached.length) {
          idx.value = buildIndex(cached);
        } else {
          idx.value = buildIndex(RAW);
        }
      }
    });
  }
  function search(query, limit = 20) {
    const q = String(query || "").trim();
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
  function findBySymbol(symbol) {
    const q = String(symbol || "").trim();
    if (!q) return null;
    return idx.value.find((it) => it.symbol === q) || null;
  }
  return { ready, search, findBySymbol, ensureIndexFresh };
}
