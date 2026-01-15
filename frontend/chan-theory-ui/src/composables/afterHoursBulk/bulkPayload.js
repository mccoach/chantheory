// src/composables/afterHoursBulk/bulkPayload.js
// ==============================
// AfterHoursBulk 模块：Bulk payload 纯构造器（纯函数）
//
// v1.1 契约改造：
// - payload 新增 batch 字段（batch_id/client_instance_id/started_at/selected_symbols/planned_total_tasks）
// - batch_id 与 client_instance_id 由前端生成并注入
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
 * 客户端 job_id：批次内稳定唯一（契约要求）
 * - 后端不解析，仅回传
 */
export function makeJobId(job) {
  const type = asStr(job?.type);
  const symbol = asStr(job?.symbol);
  if (!type || !symbol) return "";

  if (type === "current_kline") {
    const freq = asStr(job?.freq);
    const adjust = asStr(job?.adjust || "none") || "none";
    return `${type}|${symbol}|${freq}|${adjust}`;
  }

  return `${type}|${symbol}`;
}

/**
 * 将“下载队列（你现有 downloadQueue 的元素）”转换为 bulk jobs[]
 * @param {Array<object>} queue
 * @returns {{ jobs: Array<object>, jobByJobId: Map<string, object> }}
 */
export function buildJobsFromQueue(queue) {
  const list = Array.isArray(queue) ? queue : [];

  const jobs = [];
  const seen = new Set();
  const jobByJobId = new Map();

  for (const j of list) {
    const job_id = makeJobId(j);
    if (!job_id) continue;

    // 批次内去重（契约必须唯一）
    if (seen.has(job_id)) continue;
    seen.add(job_id);

    const type = asStr(j?.type);
    const symbol = asStr(j?.symbol);
    const freq = j?.freq == null ? null : asStr(j?.freq);
    const adjust = asStr(j?.adjust || "none") || "none";

    if (!type || !symbol) continue;

    const params = {};
    if (Object.prototype.hasOwnProperty.call(j, "force_fetch")) {
      params.force_fetch = !!j.force_fetch;
    }

    const job = {
      job_id,
      type,
      scope: "symbol",
      symbol,
      freq: freq || null,
      adjust,
      params,
    };

    jobs.push(job);
    jobByJobId.set(job_id, job);
  }

  return { jobs, jobByJobId };
}

/**
 * 构造 bulk payload（契约 v1.1 格式）
 * @param {object} args
 * @param {Array<object>} args.jobs
 * @param {boolean} args.force_fetch
 * @param {number|null} args.priority
 * @param {object} args.batch - v1.1 批次信息（必须注入）
 * @returns {object}
 */
export function buildAfterHoursBulkPayload({ jobs, force_fetch, priority, batch }) {
  const b = batch && typeof batch === "object" ? batch : {};

  return {
    purpose: AFTER_HOURS_PURPOSE,

    // v1.1: batch
    batch: {
      batch_id: asStr(b.batch_id),
      client_instance_id: asStr(b.client_instance_id),
      started_at: asStr(b.started_at) || nowIso(),
      selected_symbols: Number.isFinite(+b.selected_symbols) ? +b.selected_symbols : 0,
      planned_total_tasks: Number.isFinite(+b.planned_total_tasks) ? +b.planned_total_tasks : 0,
    },

    force_fetch: !!force_fetch,
    priority: priority == null ? null : Number(priority),
    jobs: Array.isArray(jobs) ? jobs : [],
    client_meta: {
      feature: "after_hours_download",
      submitted_at: nowIso(),
    },
  };
}
