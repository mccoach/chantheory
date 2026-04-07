// src/composables/localImport/state.js
// ==============================
// Local Import 模块：唯一共享状态（Single Source of Truth）
//
// 最终规则：
//   - refresh 只负责请求后端生成并持久化候选快照
//   - display 只负责只读候选快照并装入前端内存
//   - 快照是否可用于显示，只认 snapshotValid
//   - 目录变更会立即让 snapshotValid 失效
// ==============================

import { ref } from "vue";

export function createLocalImportState() {
  return {
    // ===== candidates 内存态（只在允许显示时装入）=====
    candidatesReady: ref(false),
    candidates: ref([]),
    candidatesGeneratedAt: ref(null),

    // ===== local-import 主状态 =====
    displayBatch: ref(null),
    queuedBatches: ref([]),
    uiMessage: ref(null),

    // ===== candidates 专用显示提示 =====
    candidatesDisplayMessage: ref("候选尚未就绪，请刷新后等待完成。"),

    // ===== loading / submitting =====
    loadingCandidates: ref(false),
    refreshingCandidates: ref(false),
    loadingStatus: ref(false),

    submittingStart: ref(false),
    submittingCancel: ref(false),
    submittingRetry: ref(false),

    // ===== SSE =====
    sseConnected: ref(false),
    lastStatusEventAt: ref(null),

    watchdogTimerActive: ref(false),

    // ===== 源目录 =====
    importRootDir: ref(""),
    importRootDirLoaded: ref(false),
    importRootDirLoading: ref(false),
    importRootDirBrowsing: ref(false),
    importRootDirSaving: ref(false),

    // ===== 唯一业务真相源：当前是否存在有效候选快照 =====
    snapshotValid: ref(false),
  };
}
