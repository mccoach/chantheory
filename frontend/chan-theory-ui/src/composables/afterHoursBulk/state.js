// src/composables/afterHoursBulk/state.js
// ==============================
// AfterHoursBulk 模块：唯一共享状态（Single Source of Truth）
//
// v1.1 契约改造：
// - 进度真相源在后端：前端不再累计 done/failed
// - state 以“batch snapshot”为核心：activeBatch + version gate
// - 保留少量 UI 辅助字段：fromLatestHint（用于提示可能非本设备发起）
// ==============================

import { ref } from "vue";

export function createAfterHoursBulkState() {
  return {
    // 当前批次快照（后端真相源）
    activeBatch: ref(null), // batch|null

    // 当前已接受的最新 version（单调递增门槛）
    currentVersion: ref(0),

    // 恢复来源提示：当本地 batch_id 缺失，使用 status/latest 拾取时置 true
    fromLatestHint: ref(false),

    // 最近一次入队的 items（用于诊断/展示；不参与进度真相源）
    lastEnqueueItems: ref([]),

    // failures 列表缓存（按需拉取；本期仅提供能力，不强制 UI 展示）
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
