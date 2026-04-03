// src/composables/useFoundationDataCenter.js
// ==============================
// 基础数据中心（终局版）
//
// 职责：
//   - 基础数据四大件唯一调度中心
//   - 统一发命令
//   - 统一等待完成
//   - 统一维护前端状态
//   - 基础任务最近成功/失败时间统一以后端状态真相源为准
//
// 四大任务：
//   - symbol_index
//   - profile_snapshot
//   - trade_calendar
//   - factor_events_snapshot
//
// 边界：
//   - 页面层 / 启动链只发意图
//   - 本模块负责把意图变成后台任务命令
//   - 业务模块只读/等/查
//   - lastSuccessAt / lastFailureAt / lastErrorMessage 的真相源是：
//       GET /api/system/basic-data-status
// ==============================

import { reactive, readonly } from "vue";
import { useEventStream } from "@/composables/useEventStream";
import {
  declareSymbolIndex,
  declareProfileSnapshot,
  declareTradeCalendar,
  declareFactorEventsSnapshot,
} from "@/services/ensureDataAPI";
import { fetchBasicDataStatus } from "@/services/basicDataStatusService";
import { waitTasksDone } from "@/composables/useTaskWaiter";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useProfileSnapshot } from "@/composables/useProfileSnapshot";
import { useTradeCalendar } from "@/composables/useTradeCalendar";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

const TASK_KEYS = [
  "symbol_index",
  "profile_snapshot",
  "trade_calendar",
  "factor_events_snapshot",
];

function createTaskState() {
  return {
    status: "idle", // idle | running | success | failed
    taskId: "",
    lastSuccessAt: "",
    lastFailureAt: "",
    lastErrorMessage: "",
  };
}

let _singleton = null;

export function useFoundationDataCenter() {
  if (_singleton) return _singleton;

  const state = reactive({
    symbol_index: createTaskState(),
    profile_snapshot: createTaskState(),
    trade_calendar: createTaskState(),
    factor_events_snapshot: createTaskState(),
  });

  const es = useEventStream();
  let _subscribed = false;

  function getTaskState(taskType) {
    const k = asStr(taskType);
    return TASK_KEYS.includes(k) ? state[k] : null;
  }

  function markRunning(taskType, taskId) {
    const s = getTaskState(taskType);
    if (!s) return;
    s.status = "running";
    s.taskId = asStr(taskId);
    s.lastErrorMessage = "";
  }

  function applyStatusSnapshotItem(item) {
    const taskType = asStr(item?.task_type || item?.type);
    const s = getTaskState(taskType);
    if (!s) return;

    const status = asStr(item?.status || s.status || "idle");
    const lastSuccessAt = asStr(item?.last_success_at || item?.lastSuccessAt);
    const lastFailureAt = asStr(item?.last_failure_at || item?.lastFailureAt);
    const lastErrorMessage = asStr(
      item?.last_error_message ||
        item?.lastErrorMessage ||
        item?.failure_summary ||
        item?.message
    );

    s.status = status || s.status || "idle";
    s.lastSuccessAt = lastSuccessAt || "";
    s.lastFailureAt = lastFailureAt || "";
    s.lastErrorMessage = lastErrorMessage || "";
  }

  async function refreshTaskStatusSnapshot() {
    try {
      const resp = await fetchBasicDataStatus();
      const items = Array.isArray(resp?.items) ? resp.items : [];
      for (const item of items) {
        applyStatusSnapshotItem(item);
      }
      return { ok: true };
    } catch (e) {
      return {
        ok: false,
        message: e?.message || "refresh basic data status failed",
      };
    }
  }

  async function syncAfterSuccess(taskType) {
    if (taskType === "symbol_index") {
      const si = useSymbolIndex();
      await si.ensureLoaded();
      return;
    }

    if (taskType === "profile_snapshot") {
      const ps = useProfileSnapshot();
      ps.markReady();
      await ps.ensureLoaded();
      return;
    }

    if (taskType === "trade_calendar") {
      const tc = useTradeCalendar();
      await tc.ensureLoaded();
      return;
    }

    if (taskType === "factor_events_snapshot") {
      return;
    }
  }

  function ensureSseSubscription() {
    if (_subscribed) return;
    _subscribed = true;

    es.subscribe("task.finished", async (data) => {
      const type = asStr(data?.task_type);
      if (!TASK_KEYS.includes(type)) return;

      // 任务完成后，统一以后端状态真相源为准收口
      try {
        await syncAfterSuccess(type);
      } catch {}

      try {
        await refreshTaskStatusSnapshot();
      } catch {}

      // 若状态接口暂未及时更新，做最小兜底：
      // 仅更新 status / error，不伪造 success/failure 时间。
      const s = getTaskState(type);
      if (!s) return;

      const ok = asStr(data?.overall_status) === "success";
      if (ok) {
        if (s.status === "running") {
          s.status = "success";
          s.lastErrorMessage = "";
        }
      } else {
        const msg =
          asStr(data?.summary?.message) ||
          asStr(data?.message) ||
          "任务失败";

        if (s.status === "running" || s.status === "idle") {
          s.status = "failed";
          s.lastErrorMessage = msg;
        }
      }
    });
  }

  async function runOne(taskType) {
    ensureSseSubscription();

    const t = asStr(taskType);
    const runnerMap = {
      symbol_index: declareSymbolIndex,
      profile_snapshot: declareProfileSnapshot,
      trade_calendar: () => declareTradeCalendar({ force_fetch: false }),
      factor_events_snapshot: declareFactorEventsSnapshot,
    };

    const runner = runnerMap[t];
    if (typeof runner !== "function") {
      return { ok: false, message: `unknown foundation task: ${t}` };
    }

    try {
      const task = await runner();
      markRunning(t, task?.task_id || "");

      const tid = asStr(task?.task_id);
      if (tid) {
        await waitTasksDone({
          taskIds: [tid],
          timeoutMs: 60000,
        });
      }

      await syncAfterSuccess(t);

      // 完成后只以后端状态真相源收口
      await refreshTaskStatusSnapshot();

      // 若状态接口暂未返回该项，则只兜底 status，不补时间
      const cur = getTaskState(t);
      if (cur && cur.status === "running") {
        cur.status = "success";
        cur.lastErrorMessage = "";
      }

      return { ok: true };
    } catch (e) {
      const s = getTaskState(t);
      if (s) {
        s.status = "failed";
        s.lastErrorMessage = e?.message || `${t} failed`;
      }

      // 失败后也以后端状态真相源为准收口
      try {
        await refreshTaskStatusSnapshot();
      } catch {}

      return { ok: false, message: e?.message || `${t} failed` };
    }
  }

  async function runAll() {
    const out = {};
    for (const t of TASK_KEYS) {
      out[t] = await runOne(t);
    }
    return out;
  }

  _singleton = {
    state: readonly(state),
    runOne,
    runAll,
    ensureSseSubscription,
    refreshTaskStatusSnapshot,
  };

  return _singleton;
}
