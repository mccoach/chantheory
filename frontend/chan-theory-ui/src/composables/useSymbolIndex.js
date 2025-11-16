// frontend/chan-theory-ui/src/composables/useSymbolIndex.js
// ==============================
// V4.0 - 支持档案信息（最小化修改版）
// 改动：
//   - enrichPinyin 增加档案字段处理
//   - buildIndex 传递档案字段
//   - 其他逻辑完全保持不变
// ==============================

import { ref } from "vue";
import { api } from "@/api/client";
import RAW from "@/assets/symbols.index.json";
import { useEventStream } from "./useEventStream";

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

// ===== 核心修改：为条目补齐拼音字段 + 档案字段 =====
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
  
  // ===== 新增：保留档案字段（驼峰命名，便于前端使用）=====
  item.totalShares = item.total_shares || null;
  item.floatShares = item.float_shares || null;
  item.listingDate = item.listing_date || null;
  item.industry = item.industry || null;
  item.region = item.region || null;
  item.concepts = Array.isArray(item.concepts) ? item.concepts : [];
  
  return item;
}

// ===== 核心修改：buildIndex 传递档案字段 =====
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
        
        // ===== 新增：传递档案字段 =====
        total_shares: x.total_shares || null,
        float_shares: x.float_shares || null,
        listing_date: x.listing_date || null,
        industry: x.industry || null,
        region: x.region || null,
        concepts: x.concepts || [],
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
      
      console.log(`[SymbolIndex] ✅ 索引已刷新，共 ${data.items.length} 个标的`);
      
      return true;
    }
  } catch {
    // 忽略网络错误，继续回退
  }
  return useLocalOrBuiltin();
}

// ===== 单例初始化标记（避免重复订阅）=====
let _sseSubscribed = false;

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
  
  // ===== SSE订阅（原有逻辑保持不变）=====
  if (!_sseSubscribed) {
    _sseSubscribed = true;
    
    try {
      const eventStream = useEventStream();
      
      eventStream.subscribe('symbol_index_ready', async (data) => {
        console.log('[SymbolIndex] 📋 收到更新通知', {
          total: data.total_count,
          strategy: data.strategy
        });
        
        try {
          console.log('[SymbolIndex] 🔄 自动刷新中...');
          await ensureIndexFresh(true);
          console.log('[SymbolIndex] ✅ 自动刷新完成');
        } catch (e) {
          console.error('[SymbolIndex] ❌ 自动刷新失败', e);
        }
      });
      
      console.log('[SymbolIndex] 📡 已订阅 symbol_index_ready 事件');
    } catch (e) {
      console.warn('[SymbolIndex] ⚠️ SSE订阅失败（可能在服务端渲染环境）', e);
    }
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
  
  return { 
    ready, 
    search, 
    findBySymbol, 
    ensureIndexFresh
  };
}