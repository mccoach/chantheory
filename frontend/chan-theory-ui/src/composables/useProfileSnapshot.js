// src/composables/useProfileSnapshot.js
// ==============================
// 说明：profile_snapshot 领域归口模块（单例）
//
// 职责：
//   1) 触发 profile_snapshot 集中导入
//   2) 等待 task.finished 确认完成
//   3) 维护“是否导入中”的前端领域状态
//   4) 在读取前提供 waitReadable 避让能力
//
// 原则：
//   - 不负责 HTTP 读取 profile（那是 profileService 的职责）
//   - 不负责 UI 触发时机（启动 / 手动按钮）
//   - 只负责 profile 这条任务链路自身
//
// 说明：
//   - 当前以“本地单例运行态”管理导入中状态
//   - 当多个入口同时触发时，后来的入口不会重复 declare，而是等待当前任务完成
// ==============================

import { ref, readonly } from "vue";
import { declareProfileSnapshot } from "@/services/ensureDataAPI";
import { waitTasksDone } from "@/composables/useTaskWaiter";

let _singleton = null;

const ready = ref(false);
const loading = ref(false);
const error = ref("");
const activeTaskId = ref(null);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitUntilIdle({ timeoutMs = 60000, pollMs = 100 } = {}) {
  const deadline = Date.now() + Math.max(1000, Number(timeoutMs || 60000));

  while (loading.value) {
    if (Date.now() > deadline) {
      throw new Error("[useProfileSnapshot] waitUntilIdle timeout");
    }
    await sleep(Math.max(20, Number(pollMs || 100)));
  }

  return { ok: true };
}

/**
 * 唯一导入入口：
 * - 若当前未运行：触发一次 profile_snapshot 并等待完成
 * - 若当前已在运行：不重复声明，直接等待当前任务完成
 *
 * @param {{timeoutMs?:number}} [options]
 * @returns {Promise<{ok:boolean, taskId:string|null, message?:string}>}
 */
async function ensureReady(options = {}) {
  const timeoutMs = Math.max(1000, Number(options?.timeoutMs || 60000));

  // 已有任务在跑：直接等待
  if (loading.value === true) {
    try {
      if (activeTaskId.value) {
        await waitTasksDone({
          taskIds: [String(activeTaskId.value)],
          timeoutMs,
        });
      } else {
        await waitUntilIdle({ timeoutMs });
      }

      ready.value = true;
      return {
        ok: true,
        taskId: activeTaskId.value ? String(activeTaskId.value) : null,
      };
    } catch (e) {
      error.value = e?.message || "profile_snapshot wait failed";
      return {
        ok: false,
        taskId: activeTaskId.value ? String(activeTaskId.value) : null,
        message: error.value,
      };
    }
  }

  loading.value = true;
  error.value = "";
  ready.value = false;

  let tid = null;

  try {
    const task = await declareProfileSnapshot();
    tid = task?.task_id ? String(task.task_id) : null;
    activeTaskId.value = tid;

    if (tid) {
      await waitTasksDone({
        taskIds: [tid],
        timeoutMs,
      });
    }

    ready.value = true;
    return { ok: true, taskId: tid };
  } catch (e) {
    error.value = e?.message || "profile_snapshot ensure failed";
    return { ok: false, taskId: tid, message: error.value };
  } finally {
    loading.value = false;
    activeTaskId.value = null;
  }
}

/**
 * 读取前避让：
 * - 若当前导入中，则等待导入完成
 * - 若未导入中，则直接通过
 *
 * @param {{timeoutMs?:number}} [options]
 * @returns {Promise<{ok:boolean, message?:string}>}
 */
async function waitReadable(options = {}) {
  try {
    await waitUntilIdle({ timeoutMs: options?.timeoutMs || 60000 });
    return { ok: true };
  } catch (e) {
    return { ok: false, message: e?.message || "waitReadable failed" };
  }
}

export function useProfileSnapshot() {
  if (_singleton) return _singleton;

  _singleton = {
    ready: readonly(ready),
    loading: readonly(loading),
    error: readonly(error),
    activeTaskId: readonly(activeTaskId),

    ensureReady,
    waitReadable,
    waitUntilIdle,
  };

  return _singleton;
}
