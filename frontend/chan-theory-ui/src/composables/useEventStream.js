// frontend/src/composables/useEventStream.js
// ==============================
// V9.2 - SSE 日志精简版（扁平单行 + 时间戳）
// ==============================

import { ref } from "vue";

let globalEventSource = null;
const eventHandlers = new Map();

function ts() {
  return new Date().toISOString();
}

export function useEventStream() {
  const connected = ref(false);
  const lastEventTime = ref(null);

  function connect() {
    if (globalEventSource) {
      console.log(`${ts()} [SSE] already-connected`);
      return;
    }

    console.log(`${ts()} [SSE] connecting...`);
    globalEventSource = new EventSource("/api/events/stream");

    // 连接建立
    globalEventSource.addEventListener("connected", (e) => {
      const data = JSON.parse(e.data || "{}");
      console.log(
        `${ts()} [SSE][connected] client_id=${data.client_id || "null"}`
      );
      connected.value = true;
    });

    // 单个 Job 完成
    globalEventSource.addEventListener("job_done", (e) => {
      const data = JSON.parse(e.data || "{}");
      if (import.meta.env.DEV) {
        console.log(
          `${ts()} [SSE][job_done] task_id=${data.task_id || "null"} task_type=${data.task_type || "null"} job_type=${data.job_type || "null"} status=${data.status || "null"} symbol=${data.symbol || data.result?.symbol || "null"}`
        );
      }
      lastEventTime.value = new Date().toISOString();
      _notifyHandlers("job_done", data);
    });

    // 整个 Task 完成
    globalEventSource.addEventListener("task_done", (e) => {
      const data = JSON.parse(e.data || "{}");
      if (import.meta.env.DEV) {
        console.log(
          `${ts()} [SSE][task_done] task_id=${data.task_id || "null"} task_type=${data.task_type || "null"} overall_status=${data.overall_status || "null"} symbol=${data.symbol || "null"} freq=${data.freq || "null"}`
        );
      }
      lastEventTime.value = new Date().toISOString();
      _notifyHandlers("task_done", data);
    });

    // 系统告警
    globalEventSource.addEventListener("system_alert", (e) => {
      const data = JSON.parse(e.data || "{}");
      const code = data.code || "UNKNOWN";
      const message = data.message || "";
      console.error(`${ts()} [SSE][system_alert] code=${code} message=${message}`);
      _notifyHandlers("system_alert", data);
    });

    // 心跳
    globalEventSource.addEventListener("heartbeat", () => {
      lastEventTime.value = new Date().toISOString();
    });

    // 错误处理
    globalEventSource.onerror = (err) => {
      console.warn(`${ts()} [SSE] connection lost`, err);
      connected.value = false;

      if (globalEventSource) {
        globalEventSource.close();
        globalEventSource = null;
      }

      setTimeout(connect, 5000);
    };
  }

  function subscribe(eventType, handler) {
    if (!eventHandlers.has(eventType)) {
      eventHandlers.set(eventType, new Set());
    }
    eventHandlers.get(eventType).add(handler);

    return () => {
      const handlers = eventHandlers.get(eventType);
      if (handlers) {
        handlers.delete(handler);
      }
    };
  }

  function _notifyHandlers(eventType, data) {
    const handlers = eventHandlers.get(eventType);
    if (!handlers || handlers.size === 0) return;

    handlers.forEach((handler) => {
      try {
        handler(data);
      } catch (err) {
        console.error(`${ts()} [SSE] handler error (${eventType})`, err);
      }
    });
  }

  function disconnect() {
    if (globalEventSource) {
      globalEventSource.close();
      globalEventSource = null;
      connected.value = false;
      console.log(`${ts()} [SSE] disconnected`);
    }
  }

  return { connect, disconnect, connected, lastEventTime, subscribe };
}