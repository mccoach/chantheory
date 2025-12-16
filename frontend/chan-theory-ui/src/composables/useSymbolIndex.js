// frontend/chan-theory-ui/src/composables/useSymbolIndex.js
// ==============================
// V6.0 - Task/Job + 快照双阶段版（支持档案信息 + 精简日志）
//
// 本版要点：
//   1) 启动时与手动刷新均通过 ensureIndexFresh(force) 触发：
//      - force=false：仅 GET /api/symbols/index（读取最新快照或回退至缓存/内置）；
//      - force=true ：POST /api/ensure-data type='symbol_index' + waitTasksDone，再 GET /api/symbols/index。
//   2) 继续通过 SSE 订阅 task_done(symbol_index)，在任何 symbol_index 任务完成后自动刷新一次快照：
//      - SSE 回调只负责调用 _fetchIndexSnapshot()，不再二次声明任务，避免循环。
//   3) buildIndex/enrichPinyin 中保留 symbol_profile 扩展字段（total_value/nego_value/pe_static/board/updated_at），
//      仅用于搜索与摘要展示；标的档案详情改由 /api/profile/current 提供。
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
  item.totalValue = item.total_value || null;    // 总市值
  item.negoValue = item.nego_value || null;      // 流通市值
  item.peStatic = item.pe_static || null;        // 静态市盈率

  // 索引扩展字段
  item.board = item.board || null;               // 板块
  item.updatedAt = item.updated_at || null;      // 索引/档案更新时间

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
        
        // symbol_profile 字段透传
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
async function _fetchIndexSnapshot() {
  try {
    const { data } = await api.get("/api/symbols/index", { timeout: 20000 });
    if (Array.isArray(data?.items) && data.items.length) {
      idx.value = buildIndex(data.items);
      ready.value = true;
      saveCache(data.items, data.updated_at || new Date().toISOString());

      console.log(
        `${ts()} [SymbolIndex] snapshot-refreshed count=${data.items.length} updated_at=${data.updated_at || "null"}`
      );

      return true;
    }
    console.warn(
      `${ts()} [SymbolIndex] snapshot-empty, fallback-cache-or-builtin`
    );
    return useLocalOrBuiltin();
  } catch (e) {
    console.warn(
      `${ts()} [SymbolIndex] snapshot-fetch-failed, fallback-cache-or-builtin`,
      e
    );
    return useLocalOrBuiltin();
  }
}

// 启动时拉取后端索引，写入本地缓存；
// force=true 用于“手动强制刷新”。
// force=false 用于“启动/普通刷新”，只负责 snapshot，不声明 Task。
export async function ensureIndexFresh(force = false) {
  await ensurePinyinLib();

  if (force) {
    try {
      const task = await declareSymbolIndex({ force_fetch: true });
      const tid = task?.task_id ? String(task.task_id) : null;
      if (tid) {
        await waitTasksDone({ taskIds: [tid], timeoutMs: 60000 });
      }
    } catch (e) {
      console.error(`${ts()} [SymbolIndex] declare-task(force=true)-failed`, e);
      // 即便 Task 声明失败，仍尝试直接读一次 snapshot
    }
  }

  // 无论是否 force，都尝试从快照接口读一次；
  // 若失败再退回缓存/内置。
  return _fetchIndexSnapshot();
}

// 单例初始化标记（避免重复订阅）
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

  // ===== SSE 订阅：任何 symbol_index 任务完成时，自动刷新一次快照 =====
  if (!_sseSubscribed) {
    _sseSubscribed = true;
    
    try {
      const eventStream = useEventStream();

      eventStream.subscribe("task_done", async (data) => {
        try {
          if (!data || data.task_type !== "symbol_index") return;

          if (data.overall_status === "failed") {
            console.warn(
              `${ts()} [SymbolIndex] task_done-failed task_id=${data.task_id || "null"}`
            );
            return;
          }

          console.log(
            `${ts()} [SymbolIndex] task_done-ok task_id=${data.task_id || "null"} -> refreshing snapshot`
          );

          // 这里只刷新 snapshot，不再声明 Task，避免循环
          await _fetchIndexSnapshot();
        } catch (e) {
          console.error(`${ts()} [SymbolIndex] sse-auto-refresh-failed`, e);
        }
      });

      console.log(
        `${ts()} [SymbolIndex] sse-subscribe task_type=symbol_index`
      );
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

  return {
    ready,
    search,
    findBySymbol,
    ensureIndexFresh,
  };
}