// src/composables/localImport/state.js
// ==============================
// Local Import 模块：唯一共享状态（Single Source of Truth）
//
// 原则：
//   - display_batch / queued_batches / ui_message 只认后端返回
//   - tasks 只作为“某个 batch_id 的任务列表”快照
//   - 前端不基于 tasks 反算主进度
//   - 前端不自行推导主展示批次
// ==============================

import { ref } from "vue";

export function createLocalImportState() {
  return {
    candidates: ref([]),
    candidatesGeneratedAt: ref(null),

    displayBatch: ref(null),
    queuedBatches: ref([]),
    uiMessage: ref(null),

    tasksBatchId: ref(null),
    tasks: ref([]),

    loadingCandidates: ref(false),
    loadingStatus: ref(false),
    loadingTasks: ref(false),

    submittingStart: ref(false),
    submittingCancel: ref(false),
    submittingRetry: ref(false),

    sseConnected: ref(false),
    lastStatusEventAt: ref(null),
    lastTaskEventAt: ref(null),

    watchdogTimerActive: ref(false),
  };
}
