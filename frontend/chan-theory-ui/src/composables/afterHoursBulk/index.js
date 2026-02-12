// src/composables/afterHoursBulk/index.js
// ==============================
// AfterHoursBulk 文件包入口（契约 v2.1.2-FINAL+，并对齐新 SSE type 命名）
//
// V2.2 - BREAKING: 状态码表对齐（skipped 计入 done；done 达到 total 判定完成）
// - progress.done = success + failed + cancelled + skipped
// - 规范化 batch_snapshot.progress.skipped
// ==============================

import { computed } from "vue";
import { createAfterHoursBulkState } from "./state";
import { buildBulkTasksFromQueue, buildAfterHoursBulkStartPayload } from "./bulkPayload";
import { createSseBatchSnapshotTracker } from "./sseTracker";
import { exportSelectedSymbolsToCsv } from "./exportList";

import { useEventStream } from "@/composables/useEventStream";
import {
  fetchServerIdentity,
  bulkStart,
  bulkStatus,
  bulkStatusActive,
  bulkCancel,
  bulkResume,
  bulkRetryFailed,
  fetchBulkFailures,
} from "@/services/afterHoursBulkService";

import { AFTER_HOURS_PURPOSE, AFTER_HOURS_BULK_MAX_JOBS_DEFAULT } from "@/constants";

let _singleton = null;

const LS_CLIENT_INSTANCE_ID = "chan_after_hours_client_instance_id_v1";
const LS_LAST_BATCH_ID = "chan_after_hours_last_batch_id_v1";

function nowIso() {
  return new Date().toISOString();
}

function nowMs() {
  return Date.now();
}

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function readLs(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLs(key, val) {
  try {
    localStorage.setItem(key, String(val || ""));
  } catch {}
}

function genUuidV4() {
  try {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }
  } catch {}
  const s4 = () => Math.floor((1 + Math.random()) * 0x10000).toString(16).slice(1);
  return `${s4()}${s4()}-${s4()}-${s4()}-${s4()}-${s4()}${s4()}${s4()}`;
}

// v2.1.2 推荐 batch_id 字符集：[A-Za-z0-9._:-]，长度<=64
function genBatchId() {
  const d = new Date();
  const pad2 = (n) => String(n).padStart(2, "0");
  const Y = d.getFullYear();
  const M = pad2(d.getMonth() + 1);
  const D = pad2(d.getDate());
  const h = pad2(d.getHours());
  const m = pad2(d.getMinutes());
  const s = pad2(d.getSeconds());
  const rand = Math.random().toString(16).slice(2, 8);
  return `AH_${Y}${M}${D}_${h}${m}${s}_${rand}`.slice(0, 64);
}

function normalizeBatchSnapshot(batch) {
  const b = batch && typeof batch === "object" ? batch : null;
  if (!b) return null;

  const progress = b.progress && typeof b.progress === "object" ? b.progress : {};
  const version = Number(progress.version);

  const success = Number(progress.success);
  const failed = Number(progress.failed);
  const cancelled = Number(progress.cancelled);
  const skipped = Number(progress.skipped);

  // NEW: done 计入 skipped（按你确认的 B 方案）
  const doneCalc =
    (Number.isFinite(success) ? success : 0) +
    (Number.isFinite(failed) ? failed : 0) +
    (Number.isFinite(cancelled) ? cancelled : 0) +
    (Number.isFinite(skipped) ? skipped : 0);

  return {
    ...b,
    batch_id: asStr(b.batch_id),
    client_instance_id: asStr(b.client_instance_id),
    purpose: asStr(b.purpose),
    state: asStr(b.state),

    started_at: b.started_at == null ? null : asStr(b.started_at),
    server_received_at: asStr(b.server_received_at),

    queue_ts: b.queue_ts == null ? null : asStr(b.queue_ts),
    queue_position:
      b.queue_position == null || b.queue_position === ""
        ? null
        : Number(b.queue_position),

    progress: {
      ...progress,
      version: Number.isFinite(version) ? version : 0,
      updated_at: asStr(progress.updated_at),
      total: Number.isFinite(+progress.total) ? +progress.total : 0,
      success: Number.isFinite(success) ? success : 0,
      failed: Number.isFinite(failed) ? failed : 0,
      cancelled: Number.isFinite(cancelled) ? cancelled : 0,
      skipped: Number.isFinite(skipped) ? skipped : 0,
      done: Number.isFinite(+progress.done) ? +progress.done : doneCalc,
    },
  };
}

function isTerminalBatchState(state) {
  const s = asStr(state);
  return s === "failed" || s === "success" || s === "cancelled";
}

export function useAfterHoursBulkController() {
  if (_singleton) return _singleton;

  const state = createAfterHoursBulkState();
  const eventStream = useEventStream();

  function ensureClientInstanceId() {
    let id = asStr(readLs(LS_CLIENT_INSTANCE_ID));
    if (!id) {
      id = `CI_${genUuidV4()}`;
      writeLs(LS_CLIENT_INSTANCE_ID, id);
    }
    return id;
  }

  function setLastBatchId(batchId) {
    const bid = asStr(batchId);
    if (!bid) return;
    state.lastBatchId.value = bid;
    writeLs(LS_LAST_BATCH_ID, bid);
  }

  function getLastBatchId() {
    const bid = asStr(readLs(LS_LAST_BATCH_ID));
    return bid || null;
  }

  function mergeBatchSnapshot(batch, { source = "unknown" } = {}) {
    const next = normalizeBatchSnapshot(batch);
    if (!next || !next.batch_id) return { accepted: false, reason: "empty" };

    const nextVer = Number(next.progress?.version || 0);

    const cur = state.activeBatch.value;
    const curVer = Number(state.currentVersion.value || 0);
    const curId = cur?.batch_id ? String(cur.batch_id) : "";

    if (!curId) {
      state.activeBatch.value = next;
      state.currentVersion.value = nextVer;

      state.ui.value = {
        ...(state.ui.value || {}),
        lastProgressBumpAtMs: nowMs(),
      };

      return { accepted: true, reason: `adopt@${source}` };
    }

    if (String(next.batch_id) !== curId) {
      return { accepted: false, reason: "batch_mismatch" };
    }

    if (!(nextVer > curVer)) {
      return { accepted: false, reason: `version_gate cur=${curVer} next=${nextVer}` };
    }

    state.activeBatch.value = next;
    state.currentVersion.value = nextVer;

    state.ui.value = {
      ...(state.ui.value || {}),
      lastProgressBumpAtMs: nowMs(),
    };

    return { accepted: true, reason: `merged@${source}` };
  }

  const tracker = createSseBatchSnapshotTracker({
    state,
    eventStream,
    onBatchSnapshot: mergeBatchSnapshot,
  });

  async function refreshServerIdentity() {
    try {
      const r = await fetchServerIdentity();
      if (r && r.ok === true && r.backend_instance_id) {
        state.backendInstanceId.value = String(r.backend_instance_id);
      }
      return { ok: true };
    } catch (e) {
      return { ok: false, message: e?.message || "identity failed" };
    }
  }

  async function restoreFromActive() {
    ensureClientInstanceId();

    state.ui.value = { ...(state.ui.value || {}), transport: "idle" };

    const resp = await bulkStatusActive({ purpose: AFTER_HOURS_PURPOSE });

    if (resp?.backend_instance_id) {
      state.backendInstanceId.value = String(resp.backend_instance_id);
    }

    const active = resp?.active_batch ? normalizeBatchSnapshot(resp.active_batch) : null;
    const queued = Array.isArray(resp?.queued_batches) ? resp.queued_batches : [];

    state.activeBatch.value = active;
    state.currentVersion.value = Number(active?.progress?.version || 0);

    state.queuedBatches.value = queued.map((x) => normalizeBatchSnapshot(x)).filter(Boolean);

    if (active?.batch_id) setLastBatchId(active.batch_id);

    state.ui.value = {
      ...(state.ui.value || {}),
      reconnecting: false,
      pollBackoffSec: 2,
      lastProgressBumpAtMs: active ? nowMs() : 0,
    };

    if (active && !isTerminalBatchState(active.state)) {
      tracker.start();
      state.ui.value = { ...(state.ui.value || {}), transport: "sse" };
      _ensureWatchdog();
    } else {
      tracker.stop();
      state.ui.value = { ...(state.ui.value || {}), transport: "idle" };
      _stopPolling();
      _stopWatchdog();
    }

    return { ok: true, active_batch: active, queued_batches: state.queuedBatches.value };
  }

  // ===== watchdog + polling =====
  let _watchdogTimer = null;
  let _pollTimer = null;

  function _stopWatchdog() {
    if (_watchdogTimer) clearInterval(_watchdogTimer);
    _watchdogTimer = null;
  }

  function _ensureWatchdog() {
    if (_watchdogTimer) return;

    _watchdogTimer = setInterval(() => {
      try {
        const b = state.activeBatch.value;
        if (!b || !b.batch_id) {
          _stopPolling();
          _stopWatchdog();
          return;
        }

        if (isTerminalBatchState(b.state)) {
          _stopPolling();
          _stopWatchdog();
          return;
        }

        const lastBump = Number(state.ui.value?.lastProgressBumpAtMs || 0);
        if (!lastBump) return;

        const elapsed = nowMs() - lastBump;

        if (elapsed >= 10000) {
          _ensurePolling();
        }
      } catch {}
    }, 500);
  }

  function _stopPolling() {
    if (_pollTimer) clearTimeout(_pollTimer);
    _pollTimer = null;
  }

  async function _pollOnce() {
    const b = state.activeBatch.value;
    const bid = asStr(b?.batch_id);
    if (!bid) return;

    try {
      const resp = await bulkStatus({ batch_id: bid });

      if (resp?.backend_instance_id) {
        const nextBe = String(resp.backend_instance_id);
        state.backendInstanceId.value = nextBe;
      }

      const snap = resp?.batch ? normalizeBatchSnapshot(resp.batch) : null;

      if (!snap) {
        state.activeBatch.value = null;
        state.currentVersion.value = 0;
        state.ui.value = { ...(state.ui.value || {}), transport: "idle", reconnecting: false };
        _stopPolling();
        _stopWatchdog();
        return;
      }

      mergeBatchSnapshot(snap, { source: "http_status_poll" });

      state.ui.value = {
        ...(state.ui.value || {}),
        reconnecting: false,
        pollBackoffSec: 2,
        transport: "polling",
      };

      if (isTerminalBatchState(snap.state)) {
        _stopPolling();
        _stopWatchdog();
        state.ui.value = { ...(state.ui.value || {}), transport: "idle" };
      }
    } catch (e) {
      const cur = Number(state.ui.value?.pollBackoffSec || 2);
      const next = cur < 3 ? 3 : cur < 5 ? 5 : 10;

      state.ui.value = {
        ...(state.ui.value || {}),
        reconnecting: true,
        pollBackoffSec: next,
        transport: "polling",
      };
    } finally {
      _scheduleNextPoll();
    }
  }

  function _scheduleNextPoll() {
    _stopPolling();

    const b = state.activeBatch.value;
    if (!b || !b.batch_id) return;
    if (isTerminalBatchState(b.state)) return;

    const sec = Math.max(2, Number(state.ui.value?.pollBackoffSec || 2));
    _pollTimer = setTimeout(() => {
      _pollOnce();
    }, sec * 1000);
  }

  function _ensurePolling() {
    if (_pollTimer) return;
    _scheduleNextPoll();
  }

  // ===== actions =====

  async function startFromQueue(queue, { when_active_exists = "enqueue", force_fetch = false, priority = null, selected_symbols = 0 } = {}) {
    const { bulk_tasks } = buildBulkTasksFromQueue(queue);

    if (!bulk_tasks.length) {
      return { ok: false, message: "当前没有可提交的任务（请先选择标的并勾选频率/复权）" };
    }

    if (bulk_tasks.length > AFTER_HOURS_BULK_MAX_JOBS_DEFAULT) {
      return {
        ok: false,
        message: `任务数过多（${bulk_tasks.length}），超过前端兜底上限 ${AFTER_HOURS_BULK_MAX_JOBS_DEFAULT}，请缩小选择范围或实现分批提交`,
      };
    }

    const client_instance_id = ensureClientInstanceId();
    const batch_id = genBatchId();

    const batch = {
      batch_id,
      client_instance_id,
      started_at: nowIso(),
      selected_symbols: Math.max(0, Number(selected_symbols || 0)),
      planned_total_tasks: bulk_tasks.length,
    };

    const payload = buildAfterHoursBulkStartPayload({
      bulk_tasks,
      force_fetch,
      priority,
      batch,
      submit_policy: { when_active_exists: asStr(when_active_exists) || "enqueue" },
    });

    try {
      const resp = await bulkStart(payload);

      if (resp?.backend_instance_id) state.backendInstanceId.value = String(resp.backend_instance_id);

      const newBatch = resp?.batch ? normalizeBatchSnapshot(resp.batch) : null;
      const activeBatch = resp?.active_batch ? normalizeBatchSnapshot(resp.active_batch) : null;

      try {
        await restoreFromActive();
      } catch {}

      if (newBatch) {
        setLastBatchId(newBatch.batch_id);

        if (newBatch.state !== "queued") {
          state.activeBatch.value = newBatch;
          state.currentVersion.value = Number(newBatch.progress?.version || 0);
          state.ui.value = { ...(state.ui.value || {}), lastProgressBumpAtMs: nowMs(), transport: "sse" };
          tracker.start();
          _ensureWatchdog();
        }
      }

      return {
        ok: true,
        message: "",
        batch: newBatch,
        active_batch: activeBatch,
        queue_position: resp?.queue_position ?? null,
      };
    } catch (e) {
      return {
        ok: false,
        message: e?.message || "批量提交失败",
        code: e?.code || "BULK_ERROR",
        backend_instance_id: e?.backend_instance_id ?? null,
        batch: e?.batch ?? null,
        active_batch: e?.active_batch ?? null,
        queue_position: e?.queue_position ?? null,
      };
    }
  }

  async function cancel({ batch_id }) {
    try {
      const resp = await bulkCancel({ batch_id });
      if (resp?.backend_instance_id) state.backendInstanceId.value = String(resp.backend_instance_id);

      const b = resp?.batch ? normalizeBatchSnapshot(resp.batch) : null;
      const ab = resp?.active_batch ? normalizeBatchSnapshot(resp.active_batch) : null;

      try {
        await restoreFromActive();
      } catch {}

      return { ok: true, batch: b, active_batch: ab, message: "" };
    } catch (e) {
      return { ok: false, code: e?.code || "CANCEL_FAILED", message: e?.message || "取消失败" };
    }
  }

  async function resume({ batch_id }) {
    try {
      const resp = await bulkResume({ batch_id });
      if (resp?.backend_instance_id) state.backendInstanceId.value = String(resp.backend_instance_id);

      const b = resp?.batch ? normalizeBatchSnapshot(resp.batch) : null;

      try {
        await restoreFromActive();
      } catch {}

      return { ok: true, batch: b, message: "" };
    } catch (e) {
      return { ok: false, code: e?.code || "RESUME_FAILED", message: e?.message || "续传失败" };
    }
  }

  async function retryFailed({ batch_id }) {
    try {
      const resp = await bulkRetryFailed({ batch_id });
      if (resp?.backend_instance_id) state.backendInstanceId.value = String(resp.backend_instance_id);

      const b = resp?.batch ? normalizeBatchSnapshot(resp.batch) : null;
      const ab = resp?.active_batch ? normalizeBatchSnapshot(resp.active_batch) : null;

      try {
        await restoreFromActive();
      } catch {}

      return { ok: true, batch: b, active_batch: ab, queue_position: resp?.queue_position ?? null, message: "" };
    } catch (e) {
      return { ok: false, code: e?.code || "RETRY_FAILED", message: e?.message || "重试失败" };
    }
  }

  async function loadFailures({ offset = 0, limit = 200 } = {}) {
    const b = state.activeBatch.value;
    const bid = asStr(b?.batch_id) || asStr(state.lastBatchId.value) || asStr(getLastBatchId());
    if (!bid) return { ok: false, message: "当前无批次" };

    const resp = await fetchBulkFailures({ batch_id: bid, offset, limit });
    const items = Array.isArray(resp?.items) ? resp.items : [];
    const total_failed = Number(resp?.total_failed);
    const tf = Number.isFinite(total_failed) ? total_failed : items.length;

    state.failures.value = {
      batch_id: bid,
      total_failed: tf,
      items,
      offset: Math.max(0, Number(offset || 0)),
      limit: Math.max(1, Number(limit || 200)),
      done: items.length === 0 || items.length < Math.max(1, Number(limit || 200)),
    };

    return { ok: true, message: "" };
  }

  function exportList({ rows, isStarredSet }) {
    return exportSelectedSymbolsToCsv({ rows, isStarredSet });
  }

  const running = computed(() => String(state.activeBatch.value?.state || "") === "running");
  const paused = computed(() => String(state.activeBatch.value?.state || "") === "paused");
  const stopping = computed(() => String(state.activeBatch.value?.state || "") === "stopping");

  const progress = computed(() => {
    const b = state.activeBatch.value;
    const p = b?.progress || {};

    const total = Math.max(0, Number(p.total || 0));
    const success = Math.max(0, Number(p.success || 0));
    const failed = Math.max(0, Number(p.failed || 0));
    const cancelled = Math.max(0, Number(p.cancelled || 0));
    const skipped = Math.max(0, Number(p.skipped || 0));

    // NEW: done 计入 skipped
    const done = Math.max(0, Number(p.done || (success + failed + cancelled + skipped)));

    return {
      version: Math.max(0, Number(p.version || 0)),
      updated_at: asStr(p.updated_at),

      total,
      done,
      success,
      failed,
      cancelled,
      skipped,
    };
  });

  const progressPercent = computed(() => {
    const p = progress.value;
    const total = Math.max(0, Number(p.total || 0));
    const done = Math.max(0, Number(p.done || 0));
    if (!total) return 0;
    return Math.max(0, Math.min(100, (done / total) * 100));
  });

  function dispose() {
    tracker.stop();
    _stopPolling();
    _stopWatchdog();
  }

  _singleton = {
    state,

    ensureClientInstanceId,
    refreshServerIdentity,

    restoreFromActive,

    startFromQueue,
    cancel,
    resume,
    retryFailed,

    loadFailures,

    exportList,

    running,
    paused,
    stopping,
    progress,
    progressPercent,

    dispose,
  };

  return _singleton;
}
