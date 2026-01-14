// src/composables/afterHoursBulk/index.js
// ==============================
// AfterHoursBulk 文件包入口（完全对照 viewRenderHub 范式）
//
// 特征对照：
// - Folder-as-Module：本目录即模块边界
// - index.js：唯一出口，负责创建并持有唯一 state（Single Source of Truth）
// - 子模块无单例：createXxx 工厂函数通过依赖注入
// - 统一订阅管理：SSE tracker 在此归口启动/停止
// - 对外 API 稳定：useAfterHoursBulkController() 返回固定形状的 controller
// ==============================

import { computed } from "vue";
import { createAfterHoursBulkState } from "./state";
import { buildJobsFromQueue, buildAfterHoursBulkPayload } from "./bulkPayload";
import { createBulkSubmitter } from "./bulkSubmitter";
import { createSseTaskDoneTracker } from "./sseTracker";
import { exportSelectedSymbolsToCsv } from "./exportList";

import { useEventStream } from "@/composables/useEventStream";
import { declareEnsureDataBulk } from "@/services/ensureDataAPI";
import { BULK_ITEM_STATUS, AFTER_HOURS_BULK_MAX_JOBS_DEFAULT } from "@/constants";

let _singleton = null;

function nowIso() {
  return new Date().toISOString();
}

function normalizeReasonText(reason) {
  if (reason == null) return "";
  if (typeof reason === "string") return reason;
  if (reason && typeof reason === "object") {
    const code = String(reason.code || "").trim();
    const msg = String(reason.message || "").trim();
    return msg || code || "";
  }
  return String(reason);
}

export function useAfterHoursBulkController() {
  if (_singleton) return _singleton;

  // ===== 唯一共享 state（单例真相源）=====
  const state = createAfterHoursBulkState();

  // ===== 依赖注入：submitter / tracker =====
  const submitter = createBulkSubmitter({ declareEnsureDataBulk });
  const eventStream = useEventStream();
  const tracker = createSseTaskDoneTracker({ state, eventStream });

  function resetBatchState() {
    tracker.stop();

    state.taskIdToJobId.value = new Map();
    state.doneTaskIds.value = new Set();
    state.failedJobIds.value = new Set();
    state.rejectedJobIds.value = new Set();
    state.lastEnqueueItems.value = [];
  }

  function beginProgress({ total }) {
    state.running.value = true;

    state.progress.value = {
      active: true,
      done: 0,
      total: Math.max(0, Number(total || 0)),
      failed: 0,
      started_at: nowIso(),
      ended_at: null,

      batch_id: `after_hours_${Date.now()}`,
      accepted: 0,
      rejected: 0,
      max_jobs: AFTER_HOURS_BULK_MAX_JOBS_DEFAULT,
      trace_id: null,
    };

    tracker.start();
  }

  function endProgress() {
    state.running.value = false;
    state.progress.value = {
      ...(state.progress.value || {}),
      active: false,
      ended_at: nowIso(),
    };
    tracker.stop();
  }

  async function startFromQueue(queue, { force_fetch = false, priority = null } = {}) {
    const { jobs, jobByJobId } = buildJobsFromQueue(queue);

    if (!jobs.length) {
      return { ok: false, message: "当前没有可提交的任务（请先选择标的并勾选频率/复权）" };
    }

    // 前端兜底：避免一次性提交离谱数量
    if (jobs.length > AFTER_HOURS_BULK_MAX_JOBS_DEFAULT) {
      return {
        ok: false,
        message: `任务数过多（${jobs.length}），超过前端兜底上限 ${AFTER_HOURS_BULK_MAX_JOBS_DEFAULT}，请缩小选择范围或实现分批提交`,
      };
    }

    resetBatchState();
    state.jobByJobId.value = jobByJobId;

    beginProgress({ total: jobs.length });

    try {
      const payload = buildAfterHoursBulkPayload({ jobs, force_fetch, priority });
      const resp = await submitter.submit(payload);

      if (resp?.ok !== true) {
        state.progress.value = { ...(state.progress.value || {}), trace_id: resp?.trace_id ?? null };
        endProgress();
        return { ok: false, message: "批量入队失败（后端未正常处理请求）" };
      }

      // 记录响应 items（诊断用）
      const items = Array.isArray(resp?.items) ? resp.items : [];
      state.lastEnqueueItems.value = items;

      const maxJobs = Number(resp?.max_jobs);
      if (Number.isFinite(maxJobs) && maxJobs > 0) {
        state.progress.value = { ...(state.progress.value || {}), max_jobs: maxJobs };
      }
      state.progress.value = { ...(state.progress.value || {}), trace_id: resp?.trace_id ?? null };

      const acceptedItems = items.filter((it) => String(it?.status || "") === BULK_ITEM_STATUS.ACCEPTED);
      const rejectedItems = items.filter((it) => String(it?.status || "") === BULK_ITEM_STATUS.REJECTED);

      // accepted/rejected 统计
      state.progress.value = {
        ...(state.progress.value || {}),
        accepted: acceptedItems.length,
        rejected: rejectedItems.length,
        // total 以 accepted 为准（rejected 不会有 task_done）
        total: acceptedItems.length,
      };

      // 建立 task_id -> job_id 映射
      const map = new Map();
      for (const it of acceptedItems) {
        const jobId = String(it?.job_id || "").trim();
        const taskId = String(it?.task_id || "").trim();
        if (!jobId || !taskId) continue;
        map.set(taskId, jobId);
      }
      state.taskIdToJobId.value = map;

      // 记录 rejected job_id
      const rset = new Set();
      for (const it of rejectedItems) {
        const jobId = String(it?.job_id || "").trim();
        if (jobId) rset.add(jobId);
      }
      state.rejectedJobIds.value = rset;

      // 若 accepted=0：本批次直接结束（不会收到 SSE）
      if (acceptedItems.length === 0) {
        const first = rejectedItems[0] || null;
        const reasonText = normalizeReasonText(first?.reason);
        endProgress();
        return { ok: false, message: reasonText ? `全部任务被拒绝入队：${reasonText}` : "全部任务被拒绝入队" };
      }

      // 成功入队后：不等待，继续由 SSE 推进
      return { ok: true, message: "" };
    } catch (e) {
      endProgress();
      return { ok: false, message: `批量入队失败：${e?.message || "未知错误"}` };
    }
  }

  async function retryFailed({ force_fetch = false, priority = null } = {}) {
    if (state.running.value) {
      return { ok: false, message: "当前仍在执行中，无法重试失败任务" };
    }

    const failed = state.failedJobIds.value;
    const byJob = state.jobByJobId.value;

    if (!(failed instanceof Set) || failed.size === 0) {
      return { ok: false, message: "当前没有失败任务可重试" };
    }
    if (!(byJob instanceof Map)) {
      return { ok: false, message: "内部状态缺失：无法重试（缺少 job 映射）" };
    }

    const jobs = [];
    for (const jobId of failed) {
      const j = byJob.get(jobId);
      if (j) jobs.push(j);
    }

    if (!jobs.length) {
      return { ok: false, message: "失败任务为空，无法重试" };
    }

    // 新批次：只提交失败 jobs
    resetBatchState();

    beginProgress({ total: jobs.length });
    state.progress.value = {
      ...(state.progress.value || {}),
      batch_id: `after_hours_retry_${Date.now()}`,
      total: jobs.length,
    };

    try {
      const payload = buildAfterHoursBulkPayload({ jobs, force_fetch, priority });
      const resp = await submitter.submit(payload);

      if (resp?.ok !== true) {
        state.progress.value = { ...(state.progress.value || {}), trace_id: resp?.trace_id ?? null };
        endProgress();
        return { ok: false, message: "失败任务重试：批量入队失败（后端未正常处理请求）" };
      }

      const items = Array.isArray(resp?.items) ? resp.items : [];
      state.lastEnqueueItems.value = items;

      const maxJobs = Number(resp?.max_jobs);
      if (Number.isFinite(maxJobs) && maxJobs > 0) {
        state.progress.value = { ...(state.progress.value || {}), max_jobs: maxJobs };
      }
      state.progress.value = { ...(state.progress.value || {}), trace_id: resp?.trace_id ?? null };

      const acceptedItems = items.filter((it) => String(it?.status || "") === BULK_ITEM_STATUS.ACCEPTED);
      const rejectedItems = items.filter((it) => String(it?.status || "") === BULK_ITEM_STATUS.REJECTED);

      state.progress.value = {
        ...(state.progress.value || {}),
        accepted: acceptedItems.length,
        rejected: rejectedItems.length,
        total: acceptedItems.length,
      };

      const map = new Map();
      for (const it of acceptedItems) {
        const jobId = String(it?.job_id || "").trim();
        const taskId = String(it?.task_id || "").trim();
        if (!jobId || !taskId) continue;
        map.set(taskId, jobId);
      }
      state.taskIdToJobId.value = map;

      const rset = new Set();
      for (const it of rejectedItems) {
        const jobId = String(it?.job_id || "").trim();
        if (jobId) rset.add(jobId);
      }
      state.rejectedJobIds.value = rset;

      if (acceptedItems.length === 0) {
        endProgress();
        return { ok: false, message: "失败任务重试：全部任务被拒绝入队" };
      }

      return { ok: true, message: "" };
    } catch (e) {
      endProgress();
      return { ok: false, message: `失败任务重试：批量入队失败：${e?.message || "未知错误"}` };
    }
  }

  // ===== 对外：UI 友好 computed =====
  const progressPercent = computed(() => {
    const p = state.progress.value || {};
    const total = Math.max(0, Number(p.total || 0));
    const done = Math.max(0, Number(p.done || 0));
    if (!total) return 0;
    return Math.max(0, Math.min(100, (done / total) * 100));
  });

  const progressText = computed(() => {
    const p = state.progress.value || {};
    const done = Math.max(0, Number(p.done || 0));
    const total = Math.max(0, Number(p.total || 0));
    const failed = Math.max(0, Number(p.failed || 0));
    const rejected = Math.max(0, Number(p.rejected || 0));

    if (rejected > 0) {
      return failed > 0 ? `${done} / ${total}（失败 ${failed}，拒绝 ${rejected}）` : `${done} / ${total}（拒绝 ${rejected}）`;
    }
    return failed > 0 ? `${done} / ${total}（失败 ${failed}）` : `${done} / ${total}`;
  });

  const canRetryFailed = computed(() => {
    if (state.running.value) return false;
    const s = state.failedJobIds.value;
    return s instanceof Set && s.size > 0;
  });

  // ===== 导出（纯函数）=====
  function exportList({ rows, isStarredSet }) {
    return exportSelectedSymbolsToCsv({ rows, isStarredSet });
  }

  // ===== 提供 dispose（可选）：UI 卸载不停止全局跟踪（你要求能关闭继续跟踪）=====
  // 说明：
  // - 由于你要“关闭后继续跟踪”，所以组件卸载时不调用 tracker.stop()；
  // - dispose 仅用于“手动终止跟踪/释放订阅”（当前 UI 不暴露该入口）。
  function dispose() {
    tracker.stop();
  }

  _singleton = {
    state,

    // core actions
    startFromQueue,
    retryFailed,

    // export
    exportList,

    // ui helpers
    progressPercent,
    progressText,
    canRetryFailed,

    // optional
    dispose,
  };

  return _singleton;
}
