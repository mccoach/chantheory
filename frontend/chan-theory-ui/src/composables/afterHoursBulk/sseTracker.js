// src/composables/afterHoursBulk/sseTracker.js
// ==============================
// AfterHoursBulk 模块：SSE task_done 跟踪器
// - 严格按契约：仅统计 task_id ∈ 本批次映射表
// - 去重：同一 task_id 只计一次
// - 失败识别：overall_status !== 'success' 视为失败
// - 订阅/退订归口：tracker.start()/tracker.stop()
// ==============================

import { TASK_DONE_STATUS } from "@/constants";

export function createSseTaskDoneTracker({ state, eventStream }) {
  if (!state) throw new Error("[AfterHoursBulk] state is required");
  if (!eventStream || typeof eventStream.subscribe !== "function") {
    throw new Error("[AfterHoursBulk] eventStream.subscribe is required");
  }

  let _unsub = null;

  function stop() {
    if (typeof _unsub === "function") {
      try { _unsub(); } catch {}
    }
    _unsub = null;
  }

  function start() {
    stop();

    _unsub = eventStream.subscribe("task_done", (data) => {
      try {
        const tid = String(data?.task_id || "").trim();
        if (!tid) return;

        const map = state.taskIdToJobId.value;
        if (!(map instanceof Map) || !map.has(tid)) {
          return;
        }

        const doneSet = state.doneTaskIds.value;
        if (doneSet instanceof Set && doneSet.has(tid)) {
          return;
        }

        if (doneSet instanceof Set) doneSet.add(tid);

        const p0 = state.progress.value || {};
        const nextDone = Math.max(0, Number(p0.done || 0)) + 1;

        let nextFailed = Math.max(0, Number(p0.failed || 0));
        const status = String(data?.overall_status || "").trim();

        if (status !== TASK_DONE_STATUS.SUCCESS) {
          nextFailed += 1;

          const jobId = map.get(tid);
          const fset = state.failedJobIds.value;
          if (jobId && fset instanceof Set) fset.add(jobId);
        }

        state.progress.value = { ...p0, done: nextDone, failed: nextFailed };

        const total = Math.max(0, Number(state.progress.value.total || 0));
        if (total > 0 && nextDone >= total) {
          state.progress.value = {
            ...(state.progress.value || {}),
            active: false,
            ended_at: new Date().toISOString(),
          };
          state.running.value = false;

          // 批次完成：自动停止订阅，避免污染后续批次
          stop();
        }
      } catch {}
    });
  }

  return { start, stop };
}
