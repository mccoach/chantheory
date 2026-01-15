// src/composables/afterHoursBulk/index.js
// ==============================
// AfterHoursBulk 文件包入口（对照 viewRenderHub 范式）
//
// v1.1 契约改造要点（必须）：
// - 进度真相源在后端：前端只做“恢复快照 + SSE 增量快照 + version gate 覆盖展示”
// - 不再用 SSE 计数累加 done/failed，不再依赖 task_id -> job_id 映射做进度
// - 本地持久化：client_instance_id（稳定）+ batch_id（用于重启恢复）
// - status/latest 兜底恢复（latest 需提示可能非本设备发起）
// - retryFailed：v1.1 明确本期不提供 retryable 与重试执行链路，因此移除重试语义入口（避免旧包袱）
// ==============================

import { computed } from "vue";
import { createAfterHoursBulkState } from "./state";
import { buildJobsFromQueue, buildAfterHoursBulkPayload } from "./bulkPayload";
import { createBulkSubmitter } from "./bulkSubmitter";
import { createSseTaskDoneTracker } from "./sseTracker";
import { exportSelectedSymbolsToCsv } from "./exportList";

import { useEventStream } from "@/composables/useEventStream";
import { declareEnsureDataBulk } from "@/services/ensureDataAPI";
import {
  fetchBulkStatus,
  fetchBulkStatusLatest,
  fetchBulkFailures,
} from "@/services/afterHoursBulkService";
import { AFTER_HOURS_PURPOSE, BULK_ITEM_STATUS, AFTER_HOURS_BULK_MAX_JOBS_DEFAULT } from "@/constants";

let _singleton = null;

const LS_CLIENT_INSTANCE_ID = "chan_after_hours_client_instance_id_v1";
const LS_BATCH_ID = "chan_after_hours_batch_id_v1";

function nowIso() {
  return new Date().toISOString();
}

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

// 最小 UUID 生成（无需新依赖）
function genUuidV4() {
  try {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }
  } catch {}
  // fallback：非严格 UUID，但足够用于实例标识
  const s4 = () => Math.floor((1 + Math.random()) * 0x10000).toString(16).slice(1);
  return `${s4()}${s4()}-${s4()}-${s4()}-${s4()}-${s4()}${s4()}${s4()}`;
}

// v1.1 推荐 batch_id 字符集：[A-Za-z0-9._:-]，长度<=64
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

function removeLs(key) {
  try {
    localStorage.removeItem(key);
  } catch {}
}

function normalizeBatchSnapshot(batch) {
  const b = batch && typeof batch === "object" ? batch : null;
  if (!b) return null;

  const progress = b.progress && typeof b.progress === "object" ? b.progress : {};
  const version = Number(progress.version);
  const total = Number(progress.total);

  return {
    ...b,
    batch_id: asStr(b.batch_id),
    client_instance_id: asStr(b.client_instance_id),
    purpose: asStr(b.purpose),

    state: asStr(b.state),

    selected_symbols: Number.isFinite(+b.selected_symbols) ? +b.selected_symbols : 0,
    planned_total_tasks: Number.isFinite(+b.planned_total_tasks) ? +b.planned_total_tasks : 0,
    accepted_tasks: Number.isFinite(+b.accepted_tasks) ? +b.accepted_tasks : 0,
    rejected_tasks: Number.isFinite(+b.rejected_tasks) ? +b.rejected_tasks : 0,

    progress: {
      ...progress,
      version: Number.isFinite(version) ? version : 0,
      seq: Number.isFinite(+progress.seq) ? +progress.seq : 0,
      done: Number.isFinite(+progress.done) ? +progress.done : 0,
      success: Number.isFinite(+progress.success) ? +progress.success : 0,
      failed: Number.isFinite(+progress.failed) ? +progress.failed : 0,
      total: Number.isFinite(total) ? total : (Number.isFinite(+b.accepted_tasks) ? +b.accepted_tasks : 0),
      updated_at: asStr(progress.updated_at),
    },
  };
}

export function useAfterHoursBulkController() {
  if (_singleton) return _singleton;

  const state = createAfterHoursBulkState();

  const submitter = createBulkSubmitter({ declareEnsureDataBulk });
  const eventStream = useEventStream();

  // ===== 统一快照合并（version gate）=====
  function mergeBatchSnapshot(batch, { source = "unknown" } = {}) {
    const next = normalizeBatchSnapshot(batch);
    if (!next || !next.batch_id) return { accepted: false, reason: "empty" };

    const nextVer = Number(next.progress?.version || 0);

    const cur = state.activeBatch.value;
    const curVer = Number(state.currentVersion.value || 0);
    const curId = cur?.batch_id ? String(cur.batch_id) : "";

    // 若当前没有 active batch：直接接管
    if (!curId) {
      state.activeBatch.value = next;
      state.currentVersion.value = nextVer;
      return { accepted: true, reason: `adopt@${source}` };
    }

    // batch_id 不同：不接管（避免误覆盖）
    if (String(next.batch_id) !== curId) {
      return { accepted: false, reason: "batch_mismatch" };
    }

    // v1.1：version 硬门槛，只接收更大的
    if (!(nextVer > curVer)) {
      return { accepted: false, reason: `version_gate cur=${curVer} next=${nextVer}` };
    }

    state.activeBatch.value = next;
    state.currentVersion.value = nextVer;

    return { accepted: true, reason: `merged@${source}` };
  }

  const tracker = createSseTaskDoneTracker({
    state,
    eventStream,
    onBatchSnapshot: mergeBatchSnapshot,
  });

  function ensureClientInstanceId() {
    let id = asStr(readLs(LS_CLIENT_INSTANCE_ID));
    if (!id) {
      id = `CI_${genUuidV4()}`;
      writeLs(LS_CLIENT_INSTANCE_ID, id);
    }
    return id;
  }

  function getLocalBatchId() {
    return asStr(readLs(LS_BATCH_ID));
  }

  function setLocalBatchId(batchId) {
    const bid = asStr(batchId);
    if (!bid) return;
    writeLs(LS_BATCH_ID, bid);
  }

  function clearLocalBatchId() {
    removeLs(LS_BATCH_ID);
  }

  // ===== 恢复：优先本地 batch_id，缺失则 latest 兜底 =====
  async function restoreFromLocalOrLatest() {
    const clientInstanceId = ensureClientInstanceId();

    const localBatchId = getLocalBatchId();
    state.fromLatestHint.value = false;

    // 1) 有本地 batch_id：status 恢复
    if (localBatchId) {
      const resp = await fetchBulkStatus({ batch_id: localBatchId });
      const b = resp?.batch || null;
      if (b) {
        mergeBatchSnapshot(b, { source: "http_status" });
        tracker.start();
        return { ok: true, source: "local_batch_id", batch: state.activeBatch.value };
      }

      // status 返回 batch=null：本地记录失效，清掉再走 latest
      clearLocalBatchId();
    }

    // 2) 没有本地 batch_id：latest 兜底（带 client_instance_id）
    const resp2 = await fetchBulkStatusLatest({
      purpose: AFTER_HOURS_PURPOSE,
      state: "running",
      client_instance_id: clientInstanceId,
    });

    const b2 = resp2?.batch || null;
    if (b2) {
      state.fromLatestHint.value = true;
      mergeBatchSnapshot(b2, { source: "http_latest" });
      setLocalBatchId(b2.batch_id);
      tracker.start();
      return { ok: true, source: "latest", batch: state.activeBatch.value };
    }

    return { ok: false, source: "none", batch: null };
  }

  // ===== failures 按需拉取（分页）=====
  async function loadFailures({ offset = 0, limit = 200 } = {}) {
    const b = state.activeBatch.value;
    const bid = asStr(b?.batch_id);
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

  // ===== startFromQueue（发起批次）=====
  async function startFromQueue(queue, { force_fetch = false, priority = null, selected_symbols = 0 } = {}) {
    const { jobs } = buildJobsFromQueue(queue);

    if (!jobs.length) {
      return { ok: false, message: "当前没有可提交的任务（请先选择标的并勾选频率/复权）" };
    }

    if (jobs.length > AFTER_HOURS_BULK_MAX_JOBS_DEFAULT) {
      return {
        ok: false,
        message: `任务数过多（${jobs.length}），超过前端兜底上限 ${AFTER_HOURS_BULK_MAX_JOBS_DEFAULT}，请缩小选择范围或实现分批提交`,
      };
    }

    const client_instance_id = ensureClientInstanceId();
    const batch_id = genBatchId();

    // v1.1：开始就持久化 batch_id，确保“POST 成功但页面刷新”也能恢复
    setLocalBatchId(batch_id);

    // 清理 failures 缓存（新批次）
    state.failures.value = {
      batch_id: null,
      total_failed: 0,
      items: [],
      offset: 0,
      limit: 200,
      done: false,
    };

    try {
      const batch = {
        batch_id,
        client_instance_id,
        started_at: nowIso(),
        selected_symbols: Math.max(0, Number(selected_symbols || 0)),
        planned_total_tasks: jobs.length,
      };

      const payload = buildAfterHoursBulkPayload({ jobs, force_fetch, priority, batch });

      const resp = await submitter.submit(payload);

      // submitter 直接返回后端 data（opaque）
      if (resp?.ok !== true) {
        return { ok: false, message: "批量入队失败（后端未正常处理请求）" };
      }

      // 记录入队层 items（仅诊断）
      const items = Array.isArray(resp?.items) ? resp.items : [];
      state.lastEnqueueItems.value = items;

      // 直接用后端回显 batch 快照作为真相源初始化
      const b = resp?.batch || null;
      if (b && b.batch_id) {
        state.fromLatestHint.value = false;
        state.activeBatch.value = null;
        state.currentVersion.value = 0;
        mergeBatchSnapshot(b, { source: "post_reply" });

        // SSE 增量跟踪开始
        tracker.start();
      }

      // 409/400 这类错误后端会走 axios interceptor 的 detail 格式，submitter 会 throw 到 catch
      const acceptedItems = items.filter((it) => String(it?.status || "") === BULK_ITEM_STATUS.ACCEPTED);
      const rejectedItems = items.filter((it) => String(it?.status || "") === BULK_ITEM_STATUS.REJECTED);

      // 若 accepted=0：根据契约，进度 total=accepted_tasks=0；此时应视为 finished（但后端可能直接 finished）
      // 前端这里不再自行判定，只展示后端 batch 快照即可。
      void acceptedItems;
      void rejectedItems;

      return { ok: true, message: "" };
    } catch (e) {
      // POST 失败：清掉本地 batch_id，避免下次恢复误指向一个不存在/未创建成功的批次
      clearLocalBatchId();
      return { ok: false, message: `批量入队失败：${e?.message || "未知错误"}` };
    }
  }

  // ===== 导出（纯函数）=====
  function exportList({ rows, isStarredSet }) {
    return exportSelectedSymbolsToCsv({ rows, isStarredSet });
  }

  // ===== UI 友好 computed（全部基于后端 batch 快照）=====
  const running = computed(() => {
    const b = state.activeBatch.value;
    if (!b) return false;
    return String(b.state || "") === "running";
  });

  const progress = computed(() => {
    const b = state.activeBatch.value;
    const p = b?.progress || {};
    const accepted = Math.max(0, Number(b?.accepted_tasks || 0));
    const rejected = Math.max(0, Number(b?.rejected_tasks || 0));

    // v1.1：total=accepted_tasks
    const total = Math.max(0, Number(p.total || accepted));
    const success = Math.max(0, Number(p.success || 0));
    const failed = Math.max(0, Number(p.failed || 0));
    const done = Math.max(0, Number(p.done || (success + failed)));

    const finished = total > 0 ? done >= total : String(b?.state || "") === "finished";

    return {
      version: Math.max(0, Number(p.version || 0)),
      updated_at: asStr(p.updated_at),

      accepted_tasks: accepted,
      rejected_tasks: rejected,

      total,
      done,
      success,
      failed,
      seq: Math.max(0, Number(p.seq || done)),

      finished,
    };
  });

  const progressPercent = computed(() => {
    const p = progress.value;
    const total = Math.max(0, Number(p.total || 0));
    const done = Math.max(0, Number(p.done || 0));
    if (!total) return 0;
    return Math.max(0, Math.min(100, (done / total) * 100));
  });

  const progressText = computed(() => {
    const p = progress.value;
    const done = Math.max(0, Number(p.done || 0));
    const total = Math.max(0, Number(p.total || 0));
    const failed = Math.max(0, Number(p.failed || 0));
    const rejected = Math.max(0, Number(p.rejected_tasks || 0));

    if (rejected > 0) {
      return failed > 0
        ? `${done} / ${total}（失败 ${failed}，拒绝 ${rejected}）`
        : `${done} / ${total}（拒绝 ${rejected}）`;
    }
    return failed > 0 ? `${done} / ${total}（失败 ${failed}）` : `${done} / ${total}`;
  });

  // v1.1：本期不提供 retryable/重试执行接口，所以不提供 canRetryFailed
  const canRetryFailed = computed(() => false);

  // 可选：手动停止 SSE 订阅（UI 目前不暴露）
  function dispose() {
    tracker.stop();
  }

  // ===== 对外 controller =====
  _singleton = {
    state,

    // restore
    ensureClientInstanceId,
    restoreFromLocalOrLatest,

    // core actions
    startFromQueue,

    // failures
    loadFailures,

    // export
    exportList,

    // ui helpers
    running,
    progress,
    progressPercent,
    progressText,
    canRetryFailed,

    // optional
    dispose,
  };

  return _singleton;
}
