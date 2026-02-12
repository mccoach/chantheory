// frontend/src/composables/useEventStream.js
// ==============================
// V11.0 - BREAKING: SSE 契约全面对齐（点分事件名 + 以 data.type 精确分发）
//
// 变更说明（按后端新标准彻底切换，不做旧版兼容）：
// - SSE endpoint：GET /api/events/stream（不变）
// - 监听事件名：
//     sse.connected / sse.heartbeat
//     task.job.finished / task.finished
//     bulk.batch.snapshot
//     system.alert
//     runtime.metrics
// - 分发规则：
//     * 前端以 payload.type 为准（精确匹配），不做 contains 猜测
// - connected.value：仅由 sse.connected 驱动
// - lastEventTime：收到任意已解析事件即更新
// ==============================

import { ref } from "vue";

function ts() {
  return new Date().toISOString();
}

function safeJsonParse(s) {
  try {
    return JSON.parse(s || "{}");
  } catch {
    return null;
  }
}

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function createEventStreamSingleton() {
  let globalEventSource = null;
  const eventHandlers = new Map(); // key: payload.type, val: Set<fn>

  const connected = ref(false);
  const lastEventTime = ref(null);

  function _notifyHandlers(eventType, data) {
    const t = asStr(eventType);
    if (!t) return;

    const handlers = eventHandlers.get(t);
    if (!handlers || handlers.size === 0) return;

    handlers.forEach((handler) => {
      try {
        handler(data);
      } catch (err) {
        console.error(`${ts()} [SSE] handler error (type=${t})`, err);
      }
    });
  }

  function _dispatchByPayloadType(rawEventName, payload) {
    const p = payload && typeof payload === "object" ? payload : null;
    const pType = asStr(p?.type);

    // 契约：必须以 payload.type 精确分发；不允许猜测
    if (!pType) {
      if (import.meta.env.DEV) {
        console.warn(`${ts()} [SSE] drop: missing payload.type (event=${rawEventName})`);
      }
      return;
    }

    lastEventTime.value = new Date().toISOString();

    if (pType === "sse.connected") {
      connected.value = true;
    }

    if (import.meta.env.DEV) {
      // 扁平日志：只打印关键字段，避免 console 展开大对象
      const taskId = asStr(p?.task_id);
      const taskType = asStr(p?.task_type);
      const overall = asStr(p?.overall_status);
      const batchId = asStr(p?.batch?.batch_id);
      const batchState = asStr(p?.batch?.state);
      const ver = p?.batch?.progress?.version;

      console.log(
        `${ts()} [SSE] recv type=${pType}` +
          (taskId ? ` task_id=${taskId}` : "") +
          (taskType ? ` task_type=${taskType}` : "") +
          (overall ? ` overall_status=${overall}` : "") +
          (batchId ? ` batch_id=${batchId}` : "") +
          (batchState ? ` batch_state=${batchState}` : "") +
          (ver != null ? ` version=${ver}` : "")
      );
    }

    _notifyHandlers(pType, p);
  }

  function connect() {
    if (globalEventSource) {
      if (import.meta.env.DEV) {
        console.log(`${ts()} [SSE] already-connected`);
      }
      return;
    }

    if (import.meta.env.DEV) {
      console.log(`${ts()} [SSE] connecting...`);
    }

    globalEventSource = new EventSource("/api/events/stream");

    // ===== 新契约：点分事件名 =====
    const listen = (eventName) => {
      globalEventSource.addEventListener(eventName, (e) => {
        const payload = safeJsonParse(e?.data);
        if (!payload) return;
        _dispatchByPayloadType(eventName, payload);
      });
    };

    listen("sse.connected");
    listen("sse.heartbeat");

    listen("task.job.finished");
    listen("task.finished");

    listen("bulk.batch.snapshot");

    listen("system.alert");
    listen("runtime.metrics");

    globalEventSource.onerror = (err) => {
      console.warn(`${ts()} [SSE] connection lost`, err);
      connected.value = false;

      if (globalEventSource) {
        try {
          globalEventSource.close();
        } catch {}
        globalEventSource = null;
      }

      setTimeout(connect, 5000);
    };
  }

  function subscribe(eventType, handler) {
    const t = asStr(eventType);
    if (!t || typeof handler !== "function") {
      return () => {};
    }

    if (!eventHandlers.has(t)) {
      eventHandlers.set(t, new Set());
    }
    eventHandlers.get(t).add(handler);

    return () => {
      const handlers = eventHandlers.get(t);
      if (handlers) handlers.delete(handler);
    };
  }

  function disconnect() {
    if (globalEventSource) {
      try {
        globalEventSource.close();
      } catch {}
      globalEventSource = null;
      connected.value = false;

      if (import.meta.env.DEV) {
        console.log(`${ts()} [SSE] disconnected`);
      }
    }
  }

  return { connect, disconnect, connected, lastEventTime, subscribe };
}

// ===== 显式单例 =====
const _singleton = createEventStreamSingleton();

export function useEventStream() {
  return _singleton;
}
