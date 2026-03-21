// src/composables/localImport/controller.js
// ==============================
// Local Import 控制器
//
// 职责：
//   - 管理 candidates / status / tasks 的加载
//   - 管理 start / cancel / retry 提交
//   - 管理 SSE 主更新链路
//   - 管理初始化快照与 watchdog 纠偏
//
// 约束：
//   - display_batch / queued_batches / ui_message 只认后端
//   - tasks 只按当前 tasksBatchId 加载
//   - 不基于 tasks 重算 display_batch.progress
// ==============================

import { computed } from "vue";
import { useEventStream } from "@/composables/useEventStream";
import {
  fetchLocalImportCandidates,
  startLocalImport,
  fetchLocalImportStatus,
  fetchLocalImportTasks,
  cancelLocalImport,
  retryLocalImport,
} from "@/services/localImportService";
import { createLocalImportState } from "./state";
import { createLocalImportSseTracker } from "./sseTracker";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function safeArray(x) {
  return Array.isArray(x) ? x : [];
}

function normalizeCandidate(item) {
  const it = item && typeof item === "object" ? item : {};
  return {
    market: asStr(it.market).toUpperCase(),
    symbol: asStr(it.symbol),
    freq: asStr(it.freq),
    name: asStr(it.name),
    class: asStr(it.class),
    type: asStr(it.type),
  };
}

function normalizeBatch(batch) {
  const b = batch && typeof batch === "object" ? batch : null;
  if (!b) return null;

  return {
    batch_id: asStr(b.batch_id),
    state: asStr(b.state),
    created_at: b.created_at == null ? null : asStr(b.created_at),
    started_at: b.started_at == null ? null : asStr(b.started_at),
    finished_at: b.finished_at == null ? null : asStr(b.finished_at),
    progress_total: Number.isFinite(+b.progress_total) ? +b.progress_total : 0,
    progress_done: Number.isFinite(+b.progress_done) ? +b.progress_done : 0,
    progress_success: Number.isFinite(+b.progress_success) ? +b.progress_success : 0,
    progress_failed: Number.isFinite(+b.progress_failed) ? +b.progress_failed : 0,
    progress_cancelled: Number.isFinite(+b.progress_cancelled) ? +b.progress_cancelled : 0,
    retryable: b.retryable === true,
    cancelable: b.cancelable === true,
    ui_message: b.ui_message == null ? null : asStr(b.ui_message),
  };
}

function normalizeQueuedBatch(item) {
  const it = item && typeof item === "object" ? item : {};
  return {
    batch_id: asStr(it.batch_id),
    state: asStr(it.state),
    queue_position: Number.isFinite(+it.queue_position) ? +it.queue_position : 0,
    created_at: it.created_at == null ? null : asStr(it.created_at),
    item_count: Number.isFinite(+it.item_count) ? +it.item_count : 0,
  };
}

function normalizeTask(item) {
  const it = item && typeof item === "object" ? item : {};
  return {
    market: asStr(it.market).toUpperCase(),
    symbol: asStr(it.symbol),
    freq: asStr(it.freq),
    name: asStr(it.name),
    class: asStr(it.class),
    type: asStr(it.type),
    state: asStr(it.state),
    attempts: Number.isFinite(+it.attempts) ? +it.attempts : 0,
    error_code: it.error_code == null ? null : asStr(it.error_code),
    error_message: it.error_message == null ? null : asStr(it.error_message),
    updated_at: it.updated_at == null ? null : asStr(it.updated_at),
  };
}

function taskIdentityKey(task) {
  const t = task && typeof task === "object" ? task : {};
  return `${asStr(t.market).toUpperCase()}:${asStr(t.symbol)}|${asStr(t.freq)}`;
}

let _singleton = null;

export function useLocalImportController() {
  if (_singleton) return _singleton;

  const state = createLocalImportState();
  const eventStream = useEventStream();

  function applyStatusSnapshot(payload) {
    const p = payload && typeof payload === "object" ? payload : {};

    state.displayBatch.value = normalizeBatch(p.display_batch);
    state.queuedBatches.value = safeArray(p.queued_batches).map(normalizeQueuedBatch);
    state.uiMessage.value = p.ui_message == null ? null : asStr(p.ui_message);

    const bid = asStr(state.displayBatch.value?.batch_id);
    if (!bid) {
      state.tasksBatchId.value = null;
      state.tasks.value = [];
    }
  }

  async function loadCandidates() {
    state.loadingCandidates.value = true;
    try {
      const resp = await fetchLocalImportCandidates();
      state.candidates.value = safeArray(resp?.items).map(normalizeCandidate);
      state.candidatesGeneratedAt.value =
        resp?.generated_at == null ? null : asStr(resp.generated_at);
      if (resp?.ui_message != null) {
        state.uiMessage.value = asStr(resp.ui_message);
      }
      return { ok: true };
    } catch (e) {
      return { ok: false, message: e?.message || "加载导入候选失败" };
    } finally {
      state.loadingCandidates.value = false;
    }
  }

  async function loadStatus({ syncTasks = true } = {}) {
    state.loadingStatus.value = true;
    try {
      const resp = await fetchLocalImportStatus();
      applyStatusSnapshot(resp);

      const batchId = asStr(state.displayBatch.value?.batch_id);
      if (syncTasks && batchId) {
        await loadTasks({ batch_id: batchId });
      } else if (syncTasks && !batchId) {
        state.tasksBatchId.value = null;
        state.tasks.value = [];
      }

      return { ok: true };
    } catch (e) {
      return { ok: false, message: e?.message || "加载导入状态失败" };
    } finally {
      state.loadingStatus.value = false;
    }
  }

  async function loadTasks({ batch_id } = {}) {
    const batchId = asStr(batch_id);
    if (!batchId) {
      state.tasksBatchId.value = null;
      state.tasks.value = [];
      return { ok: true };
    }

    state.loadingTasks.value = true;
    try {
      const resp = await fetchLocalImportTasks({ batch_id: batchId });
      state.tasksBatchId.value = asStr(resp?.batch_id || batchId);
      state.tasks.value = safeArray(resp?.items).map(normalizeTask);
      if (resp?.ui_message != null) {
        state.uiMessage.value = asStr(resp.ui_message);
      }
      return { ok: true };
    } catch (e) {
      return { ok: false, message: e?.message || "加载任务列表失败" };
    } finally {
      state.loadingTasks.value = false;
    }
  }

  async function startImport({ items } = {}) {
    state.submittingStart.value = true;
    try {
      const resp = await startLocalImport({ items });
      applyStatusSnapshot(resp);

      const batchId = asStr(state.displayBatch.value?.batch_id);
      if (batchId) {
        await loadTasks({ batch_id: batchId });
      } else {
        state.tasksBatchId.value = null;
        state.tasks.value = [];
      }

      return { ok: true, message: state.uiMessage.value || "" };
    } catch (e) {
      return { ok: false, message: e?.message || "启动导入失败" };
    } finally {
      state.submittingStart.value = false;
    }
  }

  async function cancelImport() {
    const batchId = asStr(state.displayBatch.value?.batch_id);
    if (!batchId) {
      return { ok: false, message: "当前没有可取消的导入批次" };
    }

    state.submittingCancel.value = true;
    try {
      const resp = await cancelLocalImport({ batch_id: batchId });
      applyStatusSnapshot(resp);

      const nextBatchId = asStr(state.displayBatch.value?.batch_id);
      if (nextBatchId) {
        await loadTasks({ batch_id: nextBatchId });
      } else {
        state.tasksBatchId.value = null;
        state.tasks.value = [];
      }

      return { ok: true, message: state.uiMessage.value || "" };
    } catch (e) {
      return { ok: false, message: e?.message || "取消导入失败" };
    } finally {
      state.submittingCancel.value = false;
    }
  }

  async function retryImport() {
    const batchId = asStr(state.displayBatch.value?.batch_id);
    if (!batchId) {
      return { ok: false, message: "当前没有可重试的导入批次" };
    }

    state.submittingRetry.value = true;
    try {
      const resp = await retryLocalImport({ batch_id: batchId });
      applyStatusSnapshot(resp);

      const nextBatchId = asStr(state.displayBatch.value?.batch_id);
      if (nextBatchId) {
        await loadTasks({ batch_id: nextBatchId });
      } else {
        state.tasksBatchId.value = null;
        state.tasks.value = [];
      }

      return { ok: true, message: state.uiMessage.value || "" };
    } catch (e) {
      return { ok: false, message: e?.message || "重试失败任务失败" };
    } finally {
      state.submittingRetry.value = false;
    }
  }

  async function handleStatusEvent(data) {
    applyStatusSnapshot(data);

    const nextBatchId = asStr(state.displayBatch.value?.batch_id);
    const currentTasksBatchId = asStr(state.tasksBatchId.value);

    if (!nextBatchId) {
      state.tasksBatchId.value = null;
      state.tasks.value = [];
      return;
    }

    if (currentTasksBatchId !== nextBatchId) {
      await loadTasks({ batch_id: nextBatchId });
    }
  }

  async function handleTaskChangedEvent(data) {
    const batchId = asStr(data?.batch_id);
    const currentTasksBatchId = asStr(state.tasksBatchId.value);

    if (!batchId || !currentTasksBatchId) return;
    if (batchId !== currentTasksBatchId) return;

    const refreshTasks = data?.refresh_tasks === true;

    if (refreshTasks) {
      await loadTasks({ batch_id: batchId });
      return;
    }

    const taskPatch = normalizeTask(data?.task || {});
    const key = taskIdentityKey(taskPatch);
    if (!key) {
      await loadTasks({ batch_id: batchId });
      return;
    }

    const arr = safeArray(state.tasks.value).slice();
    const idx = arr.findIndex((x) => taskIdentityKey(x) === key);

    if (idx >= 0) {
      arr[idx] = { ...arr[idx], ...taskPatch };
    } else {
      arr.push(taskPatch);
    }

    state.tasks.value = arr;
  }

  const tracker = createLocalImportSseTracker({
    state,
    eventStream,
    onStatusEvent: handleStatusEvent,
    onTaskChangedEvent: handleTaskChangedEvent,
  });

  let watchdogTimer = null;

  function clearWatchdog() {
    if (watchdogTimer) {
      clearInterval(watchdogTimer);
      watchdogTimer = null;
    }
    state.watchdogTimerActive.value = false;
  }

  function startWatchdog() {
    if (watchdogTimer) return;

    state.watchdogTimerActive.value = true;

    watchdogTimer = setInterval(async () => {
      try {
        const batch = state.displayBatch.value;
        const st = asStr(batch?.state);
        if (st !== "running") return;

        const now = Date.now();
        const t1 = state.lastStatusEventAt.value
          ? new Date(state.lastStatusEventAt.value).getTime()
          : 0;
        const t2 = state.lastTaskEventAt.value
          ? new Date(state.lastTaskEventAt.value).getTime()
          : 0;
        const last = Math.max(t1, t2);

        if (!last) return;
        if (now - last < 18000) return;

        await loadStatus({ syncTasks: true });
      } catch {}
    }, 5000);
  }

  async function initialize() {
    tracker.start();
    await loadCandidates();
    await loadStatus({ syncTasks: true });
    startWatchdog();
  }

  async function recoverAfterSseReconnect() {
    await loadStatus({ syncTasks: true });
  }

  const displayBatchId = computed(() => asStr(state.displayBatch.value?.batch_id));
  const displayBatchState = computed(() => asStr(state.displayBatch.value?.state));
  const cancelable = computed(() => state.displayBatch.value?.cancelable === true);
  const retryable = computed(() => state.displayBatch.value?.retryable === true);

  _singleton = {
    state,

    initialize,
    recoverAfterSseReconnect,

    loadCandidates,
    loadStatus,
    loadTasks,

    startImport,
    cancelImport,
    retryImport,

    displayBatchId,
    displayBatchState,
    cancelable,
    retryable,

    dispose() {
      tracker.stop();
      clearWatchdog();
    },
  };

  return _singleton;
}
