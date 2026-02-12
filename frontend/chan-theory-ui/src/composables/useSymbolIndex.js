// frontend/chan-theory-ui/src/composables/useSymbolIndex.js
// ==============================
// V8.0 - BREAKING: SSE 契约对齐（task.finished）
//
// 变更：
// - SSE 订阅：从 task_done 切换到 task.finished（新契约）
// - 自动刷新：任何 symbol_index 任务成功完成时，触发一次 snapshot 刷新（不声明任务）
// - 不做旧版兼容
// ==============================

import { ref } from "vue";
import { api } from "@/api/client";
import RAW from "@/assets/symbols.index.json";
import { useEventStream } from "./useEventStream";
import { declareSymbolIndex } from "@/services/ensureDataAPI";
import { waitTasksDone } from "@/composables/useTaskWaiter";

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

function ts() {
  return new Date().toISOString();
}

// 为条目补齐拼音字段 + 档案摘要字段
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

  // ===== 档案字段（驼峰命名，仅做摘要使用）=====
  item.totalShares = item.total_shares || null;
  item.floatShares = item.float_shares || null;
  item.listingDate = item.listing_date || null;
  item.industry = item.industry || null;
  item.region = item.region || null;
  item.concepts = Array.isArray(item.concepts) ? item.concepts : [];

  // 扩展 symbol_profile 字段
  item.totalValue = item.total_value || null;
  item.negoValue = item.nego_value || null;
  item.peStatic = item.pe_static || null;

  // 索引扩展字段
  item.board = item.board || null;
  item.updatedAt = item.updated_at || null;

  return item;
}

// 从 /api/symbols/index 原始 items 构建前端索引
function buildIndex(raw) {
  const arr = Array.isArray(raw) ? raw : [];
  return arr
    .filter((x) => x && x.symbol && x.name)
    .map((x) =>
      enrichPinyin({
        symbol: String(x.symbol).trim(),
        name: String(x.name).trim(),
        market: String(x.market || "").toUpperCase(),
        class: x.class || null,
        type: String(x.type || "").toUpperCase(),
        board: x.board || null,
        listing_date: x.listing_date || null,
        updated_at: x.updated_at || null,
        pinyin: x.pinyin || "",
        pinyin_abbr: x.pinyin_abbr || "",

        total_shares: x.total_shares || null,
        float_shares: x.float_shares || null,
        total_value: x.total_value || null,
        nego_value: x.nego_value || null,
        pe_static: x.pe_static || null,
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
    console.log(`${ts()} [SymbolIndex] load-cache count=${idx.value.length}`);
    return true;
  }
  idx.value = buildIndex(RAW);
  ready.value = true;
  console.log(`${ts()} [SymbolIndex] use-builtin count=${idx.value.length}`);
  return false;
}

/**
 * 从后端快照接口读取全量索引，更新 idx 与缓存
 */
async function fetchIndexSnapshot() {
  try {
    const { data } = await api.get("/api/symbols/index", { timeout: 20000 });
    if (Array.isArray(data?.items) && data.items.length) {
      idx.value = buildIndex(data.items);
      ready.value = true;
      saveCache(data.items, data.updated_at || new Date().toISOString());

      console.log(
        `${ts()} [SymbolIndex] snapshot-refreshed count=${data.items.length} updated_at=${data.updated_at || "null"}`
      );

      return { ok: true };
    }
    console.warn(`${ts()} [SymbolIndex] snapshot-empty fallback-cache-or-builtin`);
    useLocalOrBuiltin();
    return { ok: false, message: "snapshot empty" };
  } catch (e) {
    console.warn(`${ts()} [SymbolIndex] snapshot-fetch-failed fallback-cache-or-builtin`, e);
    useLocalOrBuiltin();
    return { ok: false, message: e?.message || "snapshot fetch failed" };
  }
}

function normalizeMode(mode) {
  const m = String(mode || "").toLowerCase();
  if (m === "startup") return "startup";
  if (m === "force") return "force";
  if (m === "snapshot") return "snapshot";
  return "startup";
}

/**
 * 唯一对外入口：保证 symbol_index 已就绪（两入口统一）
 *
 * @param {{mode:'startup'|'force'|'snapshot'}} options
 * @returns {Promise<{ok:boolean, mode:string, message?:string}>}
 */
async function ensureIndexReady(options = {}) {
  const mode = normalizeMode(options?.mode);

  await ensurePinyinLib();

  // snapshot-only：只读快照（用于 SSE 回调/极简刷新）
  if (mode === "snapshot") {
    const r = await fetchIndexSnapshot();
    return { ok: r.ok, mode, message: r.message };
  }

  // startup / force：统一先声明任务（由后端做缺口判断），等 task.finished 后读快照
  try {
    const force_fetch = mode === "force";
    const task = await declareSymbolIndex({ force_fetch });
    const tid = task?.task_id ? String(task.task_id) : null;

    if (tid) {
      await waitTasksDone({ taskIds: [tid], timeoutMs: 60000 });
    }
  } catch (e) {
    // declare 失败：继续尝试读 snapshot（DB 可能已有）
    console.error(`${ts()} [SymbolIndex] declare-task-failed mode=${mode}`, e);
  }

  const r = await fetchIndexSnapshot();
  return { ok: r.ok, mode, message: r.message };
}

// 单例初始化标记（避免重复订阅）
let _sseSubscribed = false;

export function useSymbolIndex() {
  if (!ready.value) {
    // 启动时先用本地/内置，避免首屏空白
    useLocalOrBuiltin();
    // 异步尝试加载拼音库并重建索引
    ensurePinyinLib().then((ok) => {
      if (ok) {
        const cached = loadCache();
        if (cached && cached.length) idx.value = buildIndex(cached);
        else idx.value = buildIndex(RAW);
      }
    });
  }

  // ===== SSE 订阅：任何 symbol_index 任务完成时，自动刷新一次快照（不声明任务）=====
  if (!_sseSubscribed) {
    _sseSubscribed = true;

    try {
      const eventStream = useEventStream();

      // NEW: task.finished（新契约）
      eventStream.subscribe("task.finished", async (data) => {
        try {
          if (!data || data.type !== "task.finished") return;
          if (data.task_type !== "symbol_index") return;

          const st = String(data.overall_status || "");
          if (st !== "success") {
            console.warn(`${ts()} [SymbolIndex] task.finished non-success overall_status=${st} task_id=${data.task_id || "null"}`);
            return;
          }

          console.log(`${ts()} [SymbolIndex] task.finished success -> snapshot refresh task_id=${data.task_id || "null"}`);

          await ensureIndexReady({ mode: "snapshot" });
        } catch (e) {
          console.error(`${ts()} [SymbolIndex] sse-auto-refresh-failed`, e);
        }
      });

      console.log(`${ts()} [SymbolIndex] sse-subscribe type=task.finished (task_type=symbol_index)`);
    } catch (e) {
      console.warn(`${ts()} [SymbolIndex] sse-subscribe-failed`, e);
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

  function listAll({ clone = true } = {}) {
    const arr = Array.isArray(idx.value) ? idx.value : [];
    return clone === false ? arr : arr.slice();
  }

  return {
    ready,
    search,
    findBySymbol,

    // NEW: 唯一入口
    ensureIndexReady,

    // read-only
    listAll,
  };
}
