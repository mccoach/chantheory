// frontend/chan-theory-ui/src/composables/useSymbolIndex.js
// ==============================
// V13.0 - REFACTOR: symbol_index 领域职责收口 + 双主键语义彻底化
//
// 职责：
//   1) symbol_index 快照缓存 / 读取 / 查询
//   2) symbol_index 集中导入任务触发与等待确认
//   3) 读取前避让“导入中”状态
//
// 本轮修正（启动重复去重 · 结构性收尾链路统一）：
//   - 删除“模块内部监听 task.finished(symbol_index) 后自动再次 fetch 快照”的副作用路径
//   - 保留唯一业务收尾链路：
//       ensureIndexReady()
//         -> declareSymbolIndex()
//         -> waitTasksDone()
//         -> fetchIndexSnapshot()
//   - 说明：task.finished 仍然是唯一完成真相源；waitTasksDone 只是对该 SSE 事件的 Promise 化封装。
//   - 因此，不应再保留第二条“收到同一完成事件后模块自行再刷快照”的并行收尾链路。
//   - 严格双主键查询继续保留：findBySymbol(symbol, market) 不再允许 symbol-only fallback
// ==============================

import { ref, readonly } from "vue";
import { api } from "@/api/client";
import RAW from "@/assets/symbols.index.json";
import { declareSymbolIndex } from "@/services/ensureDataAPI";
import { waitTasksDone } from "@/composables/useTaskWaiter";

const LS_KEY = "chan_symbol_index_v1";
const LS_TS_KEY = "chan_symbol_index_updated_at";

const ready = ref(false);
const loading = ref(false);
const error = ref("");
const idx = ref([]);
const activeTaskId = ref(null);

let TinyPinyinMod = null;

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
        updatedAt:
          x.updatedAt != null
            ? x.updatedAt
            : x.updated_at != null
              ? x.updated_at
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
    console.log(`${nowTs()} [SymbolIndex] load-cache count=${idx.value.length}`);
    return true;
  }
  idx.value = buildIndex(RAW);
  ready.value = true;
  console.log(`${nowTs()} [SymbolIndex] use-builtin count=${idx.value.length}`);
  return false;
}

async function fetchIndexSnapshot() {
  try {
    const { data } = await api.get("/api/symbols/index", { timeout: 20000 });

    if (Array.isArray(data?.items) && data.items.length) {
      idx.value = buildIndex(data.items);
      ready.value = true;
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

function normalizeMode(mode) {
  const m = String(mode || "").toLowerCase();
  if (m === "startup") return "startup";
  if (m === "force") return "force";
  if (m === "snapshot") return "snapshot";
  return "startup";
}

async function waitUntilIdle({ timeoutMs = 60000, pollMs = 100 } = {}) {
  const deadline = Date.now() + Math.max(1000, Number(timeoutMs || 60000));

  while (loading.value) {
    if (Date.now() > deadline) {
      throw new Error("[SymbolIndex] waitUntilIdle timeout");
    }
    await sleep(Math.max(20, Number(pollMs || 100)));
  }

  return { ok: true };
}

/**
 * 唯一导入入口
 *
 * 语义：
 * - snapshot：只刷新快照，不触发导入任务
 * - startup / force：
 *     * 若当前已有导入任务在跑，则等待它完成
 *     * 否则触发一次 symbol_index 导入并等待完成
 *     * 完成后刷新快照
 *
 * 本轮确认：
 * - “完成”只认 waitTasksDone() 等到的 task.finished
 * - 不再由模块内部另起 SSE 副作用链再次抓快照
 */
async function ensureIndexReady(options = {}) {
  const mode = normalizeMode(options?.mode);
  const timeoutMs = Math.max(1000, Number(options?.timeoutMs || 60000));

  await ensurePinyinLib();

  if (mode === "snapshot") {
    const r = await fetchIndexSnapshot();
    return { ok: r.ok, mode, message: r.message, taskId: null };
  }

  if (loading.value === true) {
    try {
      if (activeTaskId.value) {
        await waitTasksDone({
          taskIds: [String(activeTaskId.value)],
          timeoutMs,
        });
      } else {
        await waitUntilIdle({ timeoutMs });
      }

      const snap = await fetchIndexSnapshot();
      return {
        ok: snap.ok,
        mode,
        message: snap.message,
        taskId: activeTaskId.value ? String(activeTaskId.value) : null,
      };
    } catch (e) {
      error.value = e?.message || "symbol_index wait failed";
      return {
        ok: false,
        mode,
        message: error.value,
        taskId: activeTaskId.value ? String(activeTaskId.value) : null,
      };
    }
  }

  loading.value = true;
  error.value = "";
  ready.value = false;

  let tid = null;

  try {
    const task = await declareSymbolIndex();
    tid = task?.task_id ? String(task.task_id) : null;
    activeTaskId.value = tid;

    if (tid) {
      await waitTasksDone({
        taskIds: [tid],
        timeoutMs,
      });
    }

    const snap = await fetchIndexSnapshot();
    if (snap.ok) ready.value = true;

    return {
      ok: snap.ok,
      mode,
      message: snap.message,
      taskId: tid,
    };
  } catch (e) {
    error.value = e?.message || "symbol_index ensure failed";
    return {
      ok: false,
      mode,
      message: error.value,
      taskId: tid,
    };
  } finally {
    loading.value = false;
    activeTaskId.value = null;
  }
}

/**
 * 读取前避让：
 * - 若导入中，则等待导入完成
 * - 若未导入中，则直接通过
 */
async function waitReadable(options = {}) {
  try {
    await waitUntilIdle({ timeoutMs: options?.timeoutMs || 60000 });
    return { ok: true };
  } catch (e) {
    return { ok: false, message: e?.message || "waitReadable failed" };
  }
}

export function useSymbolIndex() {
  if (!ready.value) {
    useLocalOrBuiltin();

    ensurePinyinLib().then((ok) => {
      if (ok) {
        const cached = loadCache();
        if (cached && cached.length) idx.value = buildIndex(cached);
        else idx.value = buildIndex(RAW);
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

  /**
   * 严格双主键查询：
   * - 必须同时提供 symbol + market
   * - 不再允许 symbol-only fallback
   */
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
    activeTaskId: readonly(activeTaskId),

    search,
    findBySymbol,
    listAll,

    ensureIndexReady,
    waitReadable,
    waitUntilIdle,
  };
}
