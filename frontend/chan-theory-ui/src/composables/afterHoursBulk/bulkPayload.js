// src/composables/afterHoursBulk/bulkPayload.js
// ==============================
// AfterHoursBulk 模块：Bulk payload 纯构造器（纯函数）
// - 只负责把“队列 job 定义”转为契约 jobs[] 与 payload
// - 不做网络、不做 SSE、不做状态管理
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
 * 构造 bulk payload（契约格式）
 * @param {object} args
 * @param {Array<object>} args.jobs
 * @param {boolean} args.force_fetch
 * @param {number|null} args.priority
 * @returns {object}
 */
export function buildAfterHoursBulkPayload({ jobs, force_fetch, priority }) {
  return {
    purpose: AFTER_HOURS_PURPOSE,
    force_fetch: !!force_fetch,
    priority: priority == null ? null : Number(priority),
    jobs: Array.isArray(jobs) ? jobs : [],
    client_meta: {
      feature: "after_hours_download",
      submitted_at: nowIso(),
    },
  };
}
