// src/composables/afterHoursBulk/bulkPayload.js
// ==============================
// AfterHoursBulk 模块：Bulk payload 纯构造器（纯函数）
//
// v2.1.2-FINAL+ 契约改造：
// - payload 使用 bulk_tasks[]（不再是 jobs[]）
// - 批次内幂等键：client_task_key（替代 job_id）
// - start payload 需要 submit_policy.when_active_exists（replace/enqueue/abort）
// - 本文件仍保持：不做网络、不做 SSE、不做持久化
// ==============================

import { AFTER_HOURS_PURPOSE } from "@/constants";

function nowIso() {
  return new Date().toISOString();
}

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

/**
 * 客户端 client_task_key：批次内稳定唯一（契约要求）
 * - 后端以 (batch_id, client_task_key) 做唯一性约束
 */
export function makeClientTaskKey(task) {
  const type = asStr(task?.type);
  const symbol = asStr(task?.symbol);
  if (!type || !symbol) return "";

  if (type === "current_kline") {
    const freq = asStr(task?.freq);
    const adjust = asStr(task?.adjust || "none") || "none";
    return `${type}|${symbol}|${freq}|${adjust}`;
  }

  // current_factors / current_profile 等：只需要 type|symbol
  return `${type}|${symbol}`;
}

/**
 * 将“下载队列（你现有 downloadQueue 的元素）”转换为 bulk_tasks[]
 * @param {Array<object>} queue
 * @returns {{ bulk_tasks: Array<object>, taskByKey: Map<string, object> }}
 */
export function buildBulkTasksFromQueue(queue) {
  const list = Array.isArray(queue) ? queue : [];

  const bulk_tasks = [];
  const seen = new Set();
  const taskByKey = new Map();

  for (const t of list) {
    const client_task_key = makeClientTaskKey(t);
    if (!client_task_key) continue;

    // 批次内去重（契约必须唯一）
    if (seen.has(client_task_key)) continue;
    seen.add(client_task_key);

    const type = asStr(t?.type);
    const scope = asStr(t?.scope || "symbol") || "symbol";
    const symbol = asStr(t?.symbol);

    const freq = t?.freq == null ? null : asStr(t?.freq);
    const adjust = asStr(t?.adjust || "none") || "none";

    if (!type || !scope || !symbol) continue;

    const params = {};
    if (Object.prototype.hasOwnProperty.call(t, "force_fetch")) {
      params.force_fetch = !!t.force_fetch;
    }
    // 允许未来扩展其它 params（严格透传；本文件不做解释）

    const task = {
      client_task_key,
      type,
      scope,
      symbol,
      freq: freq || null,
      adjust,
      params,
    };

    bulk_tasks.push(task);
    taskByKey.set(client_task_key, task);
  }

  return { bulk_tasks, taskByKey };
}

/**
 * 构造 bulk/start payload（契约 v2.1.2-FINAL+ 格式）
 * @param {object} args
 * @param {Array<object>} args.bulk_tasks
 * @param {boolean} args.force_fetch
 * @param {number|null} args.priority
 * @param {object} args.batch - v2.1.2 批次信息（必须注入）
 * @param {object} args.submit_policy - { when_active_exists: 'replace'|'enqueue'|'abort' }
 * @returns {object}
 */
export function buildAfterHoursBulkStartPayload({ bulk_tasks, force_fetch, priority, batch, submit_policy }) {
  const b = batch && typeof batch === "object" ? batch : {};
  const sp = submit_policy && typeof submit_policy === "object" ? submit_policy : {};

  return {
    purpose: AFTER_HOURS_PURPOSE,

    batch: {
      batch_id: asStr(b.batch_id),
      client_instance_id: asStr(b.client_instance_id),
      started_at: asStr(b.started_at) || nowIso(),
      selected_symbols: Number.isFinite(+b.selected_symbols) ? +b.selected_symbols : 0,
      planned_total_tasks: Number.isFinite(+b.planned_total_tasks) ? +b.planned_total_tasks : 0,
    },

    force_fetch: !!force_fetch,
    priority: priority == null ? null : Number(priority),

    bulk_tasks: Array.isArray(bulk_tasks) ? bulk_tasks : [],

    submit_policy: {
      when_active_exists: asStr(sp.when_active_exists) || "enqueue",
    },
  };
}
