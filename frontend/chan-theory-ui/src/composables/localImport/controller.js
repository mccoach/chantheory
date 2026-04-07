// src/composables/localImport/controller.js
// ==============================
// Local Import 控制器
//
// 最终正式契约：
//   - initialize(): 只做 settings/status/SSE 预热
//   - refreshCandidates(): 只触发后端生成并持久化候选快照；成功返回即 snapshotValid=true
//   - triggerStartupRefresh(): 启动链尾部异步触发 refreshCandidates，不阻塞 app-started
//   - loadCandidates(): 只读候选快照并装入前端内存；前提是 snapshotValid=true
//   - clearCandidates(): 只清理前端候选内存，不改变快照有效性
//
// 唯一业务真相源：
//   - snapshotValid=true：允许显示链触发读取
//   - snapshotValid=false：禁止显示链读取
// ==============================

import { computed } from "vue";
import { useLocalImportEventStream } from "@/composables/useEventStream";
import {
  fetchLocalImportCandidates,
  refreshLocalImportCandidates,
  startLocalImport,
  fetchLocalImportStatus,
  cancelLocalImport,
  retryLocalImport,
} from "@/services/localImportService";
import {
  fetchLocalImportSettings,
  browseLocalImportSettingsDir,
  saveLocalImportSettings,
} from "@/services/localImportSettingsService";
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
    file_datetime:
      it.file_datetime == null ? null : asStr(it.file_datetime),
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

let _singleton = null;

export function useLocalImportController() {
  if (_singleton) return _singleton;

  const state = createLocalImportState();
  const eventStream = useLocalImportEventStream();

  function applyStatusSnapshot(payload) {
    const p = payload && typeof payload === "object" ? payload : {};

    state.displayBatch.value = normalizeBatch(p.display_batch);
    state.queuedBatches.value = safeArray(p.queued_batches).map(normalizeQueuedBatch);
    state.uiMessage.value = p.ui_message == null ? null : asStr(p.ui_message);
  }

  function clearCandidates() {
    state.candidatesReady.value = false;
    state.candidates.value = [];
    state.candidatesGeneratedAt.value = null;
  }

  function setCandidatesDisplayMessage(message) {
    state.candidatesDisplayMessage.value = asStr(message);
  }

  function invalidateSnapshot(message) {
    state.snapshotValid.value = false;
    clearCandidates();
    setCandidatesDisplayMessage(message);
  }

  function validateSnapshot(message = "") {
    state.snapshotValid.value = true;
    setCandidatesDisplayMessage(message);
  }

  async function loadCandidates() {
    if (state.snapshotValid.value !== true) {
      clearCandidates();
      if (!asStr(state.candidatesDisplayMessage.value)) {
        setCandidatesDisplayMessage("候选尚未就绪，请刷新后等待完成。");
      }
      return {
        ok: false,
        ready: false,
        message: state.candidatesDisplayMessage.value,
      };
    }

    state.loadingCandidates.value = true;
    try {
      const resp = await fetchLocalImportCandidates();
      const ready = resp?.ready === true;
      const items = safeArray(resp?.items).map(normalizeCandidate);

      if (!ready) {
        clearCandidates();
        setCandidatesDisplayMessage("当前还没有可显示的候选结果，请稍候或重新刷新。");
        return {
          ok: false,
          ready: false,
          message: state.candidatesDisplayMessage.value,
        };
      }

      if (items.length === 0) {
        clearCandidates();
        setCandidatesDisplayMessage(
          asStr(resp?.ui_message) || "刷新完成，但未找到可导入的本地盘后数据文件。"
        );
        return {
          ok: true,
          ready: false,
          message: state.candidatesDisplayMessage.value,
        };
      }

      state.candidatesReady.value = true;
      state.candidates.value = items;
      state.candidatesGeneratedAt.value =
        resp?.generated_at == null ? null : asStr(resp.generated_at);
      setCandidatesDisplayMessage("");

      return { ok: true, ready: true };
    } catch (e) {
      clearCandidates();
      setCandidatesDisplayMessage(e?.message || "候选读取失败，请稍后重试。");
      return {
        ok: false,
        ready: false,
        message: state.candidatesDisplayMessage.value,
      };
    } finally {
      state.loadingCandidates.value = false;
    }
  }

  async function refreshCandidates() {
    invalidateSnapshot("候选尚未就绪，请刷新后等待完成。");

    state.refreshingCandidates.value = true;
    try {
      const resp = await refreshLocalImportCandidates();
      const ok = resp?.ok === true;

      if (!ok) {
        invalidateSnapshot(
          asStr(resp?.message || resp?.ui_message) ||
            "候选刷新失败，当前结果不可用，请重试刷新。"
        );
        return { ok: false, message: state.candidatesDisplayMessage.value };
      }

      // 后端已确认：refresh 成功返回即代表新快照已可读
      validateSnapshot(
        asStr(resp?.ui_message) || ""
      );

      return { ok: true, message: asStr(resp?.message || resp?.ui_message || "") };
    } catch (e) {
      invalidateSnapshot(e?.message || "候选刷新失败，当前结果不可用，请重试刷新。");
      return { ok: false, message: state.candidatesDisplayMessage.value };
    } finally {
      state.refreshingCandidates.value = false;
    }
  }

  // 启动链尾部异步触发刷新，不阻塞启动完成
  function triggerStartupRefresh() {
    Promise.resolve()
      .then(() => refreshCandidates())
      .catch(() => {});
  }

  async function loadStatus() {
    state.loadingStatus.value = true;
    try {
      const resp = await fetchLocalImportStatus();
      applyStatusSnapshot(resp);
      return { ok: true };
    } catch (e) {
      return { ok: false, message: e?.message || "加载导入状态失败" };
    } finally {
      state.loadingStatus.value = false;
    }
  }

  async function refreshSettings() {
    state.importRootDirLoading.value = true;
    try {
      const resp = await fetchLocalImportSettings();
      state.importRootDir.value = asStr(resp?.tdx_vipdoc_dir);
      state.importRootDirLoaded.value = true;

      if (resp?.ok !== true) {
        return {
          ok: false,
          tdx_vipdoc_dir: state.importRootDir.value,
          message: resp?.message || "读取目录设置失败",
        };
      }

      return {
        ok: true,
        tdx_vipdoc_dir: state.importRootDir.value,
        message: asStr(resp?.message),
      };
    } catch (e) {
      state.importRootDirLoaded.value = true;
      return {
        ok: false,
        tdx_vipdoc_dir: asStr(state.importRootDir.value),
        message: e?.message || "读取目录设置失败",
      };
    } finally {
      state.importRootDirLoading.value = false;
    }
  }

  async function browseSettingsDir() {
    const latest = await refreshSettings();
    const initialDir = asStr(latest?.tdx_vipdoc_dir);

    state.importRootDirBrowsing.value = true;
    try {
      const resp = await browseLocalImportSettingsDir({
        initial_dir: initialDir,
      });

      return {
        ok: resp?.ok === true,
        selected_dir: asStr(resp?.selected_dir),
        message: resp?.message || (resp?.ok === true ? "" : "用户取消选择"),
      };
    } catch (e) {
      return {
        ok: false,
        selected_dir: "",
        message: e?.message || "打开目录选择窗口失败",
      };
    } finally {
      state.importRootDirBrowsing.value = false;
    }
  }

  async function saveSettingsDir(nextDir) {
    const dir = asStr(nextDir);
    if (!dir) {
      return { ok: false, tdx_vipdoc_dir: "", message: "目录不能为空" };
    }

    state.importRootDirSaving.value = true;
    try {
      const resp = await saveLocalImportSettings({
        tdx_vipdoc_dir: dir,
      });

      const savedDir = asStr(resp?.tdx_vipdoc_dir) || dir;
      state.importRootDir.value = savedDir;
      state.importRootDirLoaded.value = true;

      invalidateSnapshot("源目录已变更，原候选已失效，请重新刷新。");

      return {
        ok: resp?.ok === true,
        tdx_vipdoc_dir: savedDir,
        message:
          resp?.message || "源目录已变更，原候选已失效，请重新刷新。",
      };
    } catch (e) {
      return {
        ok: false,
        tdx_vipdoc_dir: asStr(state.importRootDir.value),
        message: e?.message || "目录设置失败",
      };
    } finally {
      state.importRootDirSaving.value = false;
    }
  }

  async function startImport({ items } = {}) {
    state.submittingStart.value = true;
    try {
      const resp = await startLocalImport({ items });
      applyStatusSnapshot(resp);
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
      return { ok: false, message: "当前没有可停止的导入批次" };
    }

    state.submittingCancel.value = true;
    try {
      const resp = await cancelLocalImport({ batch_id: batchId });
      applyStatusSnapshot(resp);
      return { ok: true, message: state.uiMessage.value || "" };
    } catch (e) {
      return { ok: false, message: e?.message || "停止导入失败" };
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
      return { ok: true, message: state.uiMessage.value || "" };
    } catch (e) {
      return { ok: false, message: e?.message || "重试失败任务失败" };
    } finally {
      state.submittingRetry.value = false;
    }
  }

  async function handleStatusEvent(data) {
    applyStatusSnapshot(data);
  }

  const tracker = createLocalImportSseTracker({
    state,
    eventStream,
    onStatusEvent: handleStatusEvent,
  });

  let watchdogTimer = null;
  let trackerStarted = false;
  let controllerInitialized = false;
  let initPromise = null;

  function ensureTrackerStarted() {
    if (trackerStarted) return;
    tracker.start();
    trackerStarted = true;
  }

  function clearWatchdog() {
    if (watchdogTimer) {
      clearInterval(watchdogTimer);
      watchdogTimer = null;
    }
    state.watchdogTimerActive.value = false;
  }

  function ensureWatchdogStarted() {
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
        const last = t1;

        if (!last) return;
        if (now - last < 18000) return;

        await loadStatus();
      } catch {}
    }, 5000);
  }

  async function doInitialize() {
    ensureTrackerStarted();
    ensureWatchdogStarted();
    eventStream.connect();

    await Promise.all([
      refreshSettings(),
      loadStatus(),
    ]);

    controllerInitialized = true;
  }

  async function initialize() {
    if (controllerInitialized) {
      ensureTrackerStarted();
      ensureWatchdogStarted();
      eventStream.connect();
      return { ok: true };
    }

    if (initPromise) {
      await initPromise;
      return { ok: true };
    }

    initPromise = doInitialize()
      .catch(() => {})
      .finally(() => {
        initPromise = null;
      });

    await initPromise;
    return { ok: true };
  }

  async function recoverAfterSseReconnect() {
    ensureTrackerStarted();
    ensureWatchdogStarted();
    eventStream.connect();
    await loadStatus();
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
    refreshCandidates,
    triggerStartupRefresh,
    clearCandidates,
    loadStatus,

    refreshSettings,
    browseSettingsDir,
    saveSettingsDir,

    startImport,
    cancelImport,
    retryImport,

    displayBatchId,
    displayBatchState,
    cancelable,
    retryable,

    dispose() {
      tracker.stop();
      trackerStarted = false;
      clearWatchdog();
      controllerInitialized = false;
      initPromise = null;
      eventStream.disconnect();
    },
  };

  return _singleton;
}
