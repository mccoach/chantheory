// src/composables/useTaskWaiter.js
// ==============================
// 说明：Task 等待工具（集中式 TaskStore 版 · 模块加载即订阅）
// 职责：
//   - 基于 SSE task_done 事件，按 task_id 集合等待一批任务完成；
//   - 使用全局 TaskStore：统一订阅 SSE，一处缓存与分发所有 task_done；
//   - waitTasksDone 本身只与 TaskStore 交互。
// ==============================

import { useEventStream } from "@/composables/useEventStream";

const doneCache = new Map(); // Map<string, any>
const waiterMap = new Map(); // Map<string, Set<Function>>

let _subscribed = false;

function initTaskStoreSubscription() {
  if (_subscribed) return;
  _subscribed = true;

  try {
    const eventStream = useEventStream();

    eventStream.subscribe("task_done", (data) => {
      try {
        const tid = String(data?.task_id || "").trim();
        if (!tid) return;

        // 写入/更新完成结果缓存
        doneCache.set(tid, data);

        // 控制缓存体积
        const MAX_CACHE_SIZE = 500;
        if (doneCache.size > MAX_CACHE_SIZE) {
          const firstKey = doneCache.keys().next().value;
          if (firstKey) {
            doneCache.delete(firstKey);
          }
        }

        // 唤醒所有正在等待该 task_id 的回调
        const waitSet = waiterMap.get(tid);
        if (waitSet && waitSet.size > 0) {
          const callbacks = Array.from(waitSet);
          waiterMap.delete(tid);
          for (const cb of callbacks) {
            try {
              cb(data);
            } catch (err) {
              console.error(
                "[waitTasksDone/TaskStore] 回调执行失败:",
                tid,
                err
              );
            }
          }
        }
      } catch (e) {
        console.error("[waitTasksDone/TaskStore] 处理 task_done 事件失败:", e);
      }
    });
  } catch (e) {
    console.warn(
      "[waitTasksDone] 无法订阅 task_done（可能在非浏览器环境）",
      e
    );
  }
}

// 模块加载时立即初始化订阅
initTaskStoreSubscription();

/**
 * 等待一批 Task 全部完成（task_done 收到）
 *
 * @param {Object} options
 * @param {Array<string>} options.taskIds
 * @param {number} [options.timeoutMs=30000]
 * @returns {Promise<Object>} - { [taskId]: taskDonePayload }
 */
export async function waitTasksDone({ taskIds, timeoutMs = 30000 } = {}) {
  const ids = (Array.isArray(taskIds) ? taskIds : [])
    .map((x) => String(x || "").trim())
    .filter(Boolean);

  if (!ids.length) {
    return {};
  }

  const results = {};
  const pending = new Set();

  // 先从缓存中扣除已完成任务
  for (const id of ids) {
    if (doneCache.has(id)) {
      results[id] = doneCache.get(id);
    } else {
      pending.add(id);
    }
  }

  if (pending.size === 0) {
    return results;
  }

  return new Promise((resolve, reject) => {
    let settled = false;
    const callbacks = new Map();
    let timerId = null;

    const cleanup = () => {
      if (settled) return;
      settled = true;

      callbacks.forEach((cb, tid) => {
        const set = waiterMap.get(tid);
        if (set) {
          set.delete(cb);
          if (set.size === 0) {
            waiterMap.delete(tid);
          }
        }
      });
      callbacks.clear();

      if (timerId != null) {
        clearTimeout(timerId);
        timerId = null;
      }
    };

    // 为 pending 的每个 task_id 注册一次性回调
    for (const tid of pending) {
      const cb = (payload) => {
        if (settled) return;

        results[tid] = payload;
        pending.delete(tid);

        if (pending.size === 0) {
          cleanup();
          resolve(results);
        }
      };

      callbacks.set(tid, cb);
      const set = waiterMap.get(tid) || new Set();
      set.add(cb);
      waiterMap.set(tid, set);
    }

    // 注册后再检查一次缓存，防止竞态
    for (const tid of Array.from(pending)) {
      if (doneCache.has(tid)) {
        const payload = doneCache.get(tid);
        const cb = callbacks.get(tid);
        if (cb) {
          cb(payload);
        }
      }
    }

    if (pending.size === 0 && !settled) {
      cleanup();
      resolve(results);
      return;
    }

    // 超时保护
    timerId = setTimeout(() => {
      if (settled) return;
      const still = Array.from(pending);
      cleanup();
      const err = new Error(
        `[waitTasksDone] timeout after ${timeoutMs}ms, pending task_ids=${still.join(
          ","
        )}`
      );
      reject(err);
    }, timeoutMs);
  });
}