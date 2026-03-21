// frontend/src/composables/useEventStream.js
// ==============================
// V11.1 - SSE 心跳日志降噪
//
// 说明：
// - 保留 sse.heartbeat 的连接保活语义；
// - 仍然更新 lastEventTime；
// - 但在 DEV 下不再为 heartbeat 打印逐条日志，避免控制台刷屏；
// - 其它业务事件仍保持原有日志输出。
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
      // 心跳只保留语义，不打印逐条日志，避免刷屏
      if (pType !== "sse.heartbeat") {
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

    // NEW: local import
    listen("local_import.status");
    listen("local_import.task_changed");

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

const _singleton = createEventStreamSingleton();

export function useEventStream() {
  return _singleton;
}
