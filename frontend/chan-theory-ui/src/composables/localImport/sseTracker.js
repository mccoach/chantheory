// src/composables/localImport/sseTracker.js
// ==============================
// Local Import SSE 跟踪器
//
// 契约：
//   - type = local_import.status
//   - type = local_import.task_changed
//
// 职责：
//   - 订阅全站 SSE 通道中的 local-import 专属事件
//   - 更新 state 中的主状态时间戳
//   - 把 payload 交给 controller 注入的回调处理
//   - 不做业务推导
// ==============================

export function createLocalImportSseTracker({
  state,
  eventStream,
  onStatusEvent,
  onTaskChangedEvent,
}) {
  if (!state) throw new Error("[LocalImport] state is required");
  if (!eventStream || typeof eventStream.subscribe !== "function") {
    throw new Error("[LocalImport] eventStream.subscribe is required");
  }
  if (typeof onStatusEvent !== "function") {
    throw new Error("[LocalImport] onStatusEvent is required");
  }
  if (typeof onTaskChangedEvent !== "function") {
    throw new Error("[LocalImport] onTaskChangedEvent is required");
  }

  let unsubStatus = null;
  let unsubTaskChanged = null;

  function stop() {
    if (typeof unsubStatus === "function") {
      try {
        unsubStatus();
      } catch {}
    }
    if (typeof unsubTaskChanged === "function") {
      try {
        unsubTaskChanged();
      } catch {}
    }

    unsubStatus = null;
    unsubTaskChanged = null;
    state.sseConnected.value = false;
  }

  function start() {
    stop();

    unsubStatus = eventStream.subscribe("local_import.status", (data) => {
      try {
        if (!data || data.type !== "local_import.status") return;
        state.sseConnected.value = true;
        state.lastStatusEventAt.value = new Date().toISOString();
        onStatusEvent(data);
      } catch {}
    });

    unsubTaskChanged = eventStream.subscribe("local_import.task_changed", (data) => {
      try {
        if (!data || data.type !== "local_import.task_changed") return;
        state.sseConnected.value = true;
        state.lastTaskEventAt.value = new Date().toISOString();
        onTaskChangedEvent(data);
      } catch {}
    });
  }

  return { start, stop };
}
