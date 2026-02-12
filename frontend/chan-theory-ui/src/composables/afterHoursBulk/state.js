// src/composables/afterHoursBulk/state.js
// ==============================
// AfterHoursBulk 模块：唯一共享状态（Single Source of Truth）
//
// v2.1.2-FINAL+：
// - 真相源在后端：activeBatch/queuedBatches 都是 batch_snapshot（只读展示）
// - 增加 backendInstanceId：用于识别后端重启
// - 增加 UI 状态：reconnecting / transport（仅 UI，不映射后端 state）
// ==============================

import { ref } from "vue";

export function createAfterHoursBulkState() {
  return {
    // ===== 后端身份（契约要求：所有响应/SSE必须带）=====
    backendInstanceId: ref(null),

    // ===== 当前 active 批次快照（后端真相源）=====
    activeBatch: ref(null), // batch_snapshot|null

    // ===== queued 批次列表（UI-B：展示排队列表）=====
    queuedBatches: ref([]), // Array<batch_snapshot_with_queue_position>

    // ===== 当前已接受的最新 version（单调递增门槛）=====
    currentVersion: ref(0),

    // ===== watchdog / reconnecting（仅 UI 状态，不修改 batch.state）=====
    ui: ref({
      reconnecting: false,
      // 当前使用的进度更新通道（仅展示）：'sse'|'polling'|'idle'
      transport: "idle",
      // 最近一次观测到 progress.version 增长的本地时间（ms）
      lastProgressBumpAtMs: 0,
      // polling 退避（秒）
      pollBackoffSec: 2,
    }),

    // 最近一次提交/关注的 batch_id（可选：UI 快速定位）
    lastBatchId: ref(null),

    // failures 列表缓存（按需拉取；不参与进度真相源）
    failures: ref({
      batch_id: null,
      total_failed: 0,
      items: [],
      offset: 0,
      limit: 200,
      done: false,
    }),
  };
}
