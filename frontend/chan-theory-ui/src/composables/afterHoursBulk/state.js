// src/composables/afterHoursBulk/state.js
// ==============================
// AfterHoursBulk 模块：唯一共享状态（Single Source of Truth）
// - 由 index.js 创建并持有全局单例 state
// - 子模块只通过注入的 state 读写，不创建第二份真相源
// ==============================

import { ref } from "vue";
import { AFTER_HOURS_BULK_MAX_JOBS_DEFAULT } from "@/constants";

export function createAfterHoursBulkState() {
  return {
    // 当前运行态
    running: ref(false),

    // 进度（SSE 驱动）
    progress: ref({
      active: false,
      done: 0,
      total: 0,
      failed: 0,
      started_at: null,
      ended_at: null,

      batch_id: null,
      accepted: 0,
      rejected: 0,
      max_jobs: AFTER_HOURS_BULK_MAX_JOBS_DEFAULT,
      trace_id: null,
    }),

    // 当前批次：task_id -> job_id（仅用于匹配 SSE task_done）
    taskIdToJobId: ref(new Map()),

    // 去重：已计入完成的 task_id
    doneTaskIds: ref(new Set()),

    // 用于失败重试：失败 job_id 集合
    failedJobIds: ref(new Set()),

    // 入队层 rejected 的 job_id（不会有 SSE）
    rejectedJobIds: ref(new Set()),

    // job_id -> job（用于 retry 重组 jobs[]）
    jobByJobId: ref(new Map()),

    // 最近一次入队的 items（用于诊断/展示；不参与核心逻辑）
    lastEnqueueItems: ref([]),
  };
}
