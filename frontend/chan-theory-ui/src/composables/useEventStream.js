// frontend/src/composables/useEventStream.js
// ==============================
// V12.1 - SSE 按类型分流订阅（全局基础流 + local-import 专用流）
//
// 全局基础流用途：
//   - sse.connected
//   - sse.heartbeat
//   - task.finished
//
// 说明：
//   - 基础数据任务中心 useFoundationData 依赖 task.finished 维护实时状态
//   - local-import 继续使用专用流
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

function normalizeTypeList(types) {
  const arr = Array.isArray(types) ? types : [];
  const uniq = new Set();

  for (const t of arr) {
    const v = asStr(t);
    if (!v) continue;
    uniq.add(v);
  }

  return Array.from(uniq.values());
}

function buildSseUrl(types) {
  const list = normalizeTypeList(types);

  if (!list.length) {
    return "/api/events/stream";
  }

  const qs = new URLSearchParams();
  for (const t of list) {
    qs.append("type", t);
  }

  return `/api/events/stream?${qs.toString()}`;
}

function createEventStreamClient({ name, subscribeTypes }) {
  let eventSource = null;
  const eventHandlers = new Map();

  const connected = ref(false);
  const lastEventTime = ref(null);

  const clientName = asStr(name) || "sse-client";
  const subscribedTypes = normalizeTypeList(subscribeTypes);

  function _notifyHandlers(eventType, data) {
    const t = asStr(eventType);
    if (!t) return;

    const handlers = eventHandlers.get(t);
    if (!handlers || handlers.size === 0) return;

    handlers.forEach((handler) => {
      try {
        handler(data);
      } catch (err) {
        console.error(`${ts()} [SSE:${clientName}] handler error (type=${t})`, err);
      }
    });
  }

  function _dispatchByPayloadType(rawEventName, payload) {
    const p = payload && typeof payload === "object" ? payload : null;
    const pType = asStr(p?.type);

    if (!pType) {
      if (import.meta.env.DEV) {
        console.warn(`${ts()} [SSE:${clientName}] drop: missing payload.type (event=${rawEventName})`);
      }
      return;
    }

    lastEventTime.value = new Date().toISOString();

    if (pType === "sse.connected") {
      connected.value = true;
    }

    if (import.meta.env.DEV) {
      if (pType !== "sse.heartbeat") {
        const taskId = asStr(p?.task_id);
        const taskType = asStr(p?.task_type);
        const overall = asStr(p?.overall_status);
        const batchId = asStr(p?.batch?.batch_id);
        const batchState = asStr(p?.batch?.state);
        const ver = p?.batch?.progress?.version;

        console.log(
          `${ts()} [SSE:${clientName}] recv type=${pType}` +
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
    if (eventSource) {
      if (import.meta.env.DEV) {
        console.log(`${ts()} [SSE:${clientName}] already-connected`);
      }
      return;
    }

    const url = buildSseUrl(subscribedTypes);

    if (import.meta.env.DEV) {
      console.log(
        `${ts()} [SSE:${clientName}] connecting... url=${url} types=${JSON.stringify(subscribedTypes)}`
      );
    }

    eventSource = new EventSource(url);

    const listen = (eventName) => {
      eventSource.addEventListener(eventName, (e) => {
        const payload = safeJsonParse(e?.data);
        if (!payload) return;
        _dispatchByPayloadType(eventName, payload);
      });
    };

    for (const eventName of subscribedTypes) {
      listen(eventName);
    }

    eventSource.onerror = (err) => {
      console.warn(`${ts()} [SSE:${clientName}] connection lost`, err);
      connected.value = false;

      if (eventSource) {
        try {
          eventSource.close();
        } catch {}
        eventSource = null;
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
    if (eventSource) {
      try {
        eventSource.close();
      } catch {}
      eventSource = null;
      connected.value = false;

      if (import.meta.env.DEV) {
        console.log(`${ts()} [SSE:${clientName}] disconnected`);
      }
    }
  }

  return {
    connect,
    disconnect,
    connected,
    lastEventTime,
    subscribe,
    subscribedTypes,
  };
}

const _globalSingleton = createEventStreamClient({
  name: "global",
  subscribeTypes: [
    "sse.connected",
    "sse.heartbeat",
    "task.finished",
  ],
});

const _localImportSingleton = createEventStreamClient({
  name: "local-import",
  subscribeTypes: [
    "sse.connected",
    "sse.heartbeat",
    "local_import.status",
  ],
});

export function useEventStream() {
  return _globalSingleton;
}

export function useLocalImportEventStream() {
  return _localImportSingleton;
}
