// src/composables/localImport/sseTracker.js
// ==============================
// Local Import SSE 跟踪器
//
// 当前正式契约：
//   - type = local_import.status
//
// 职责：
//   - 订阅 local-import 专用 SSE 通道中的 local_import.status
//   - 更新 state 中的主状态时间戳
//   - 把 payload 交给 controller 注入的回调处理
//   - 不做业务推导
// ==============================

export function createLocalImportSseTracker({
  state,
  eventStream,
  onStatusEvent,
}) {
  if (!state) throw new Error("[LocalImport] state is required");
  if (!eventStream || typeof eventStream.subscribe !== "function") {
    throw new Error("[LocalImport] eventStream.subscribe is required");
  }
  if (typeof onStatusEvent !== "function") {
    throw new Error("[LocalImport] onStatusEvent is required");
  }

  let unsubStatus = null;

  function stop() {
    if (typeof unsubStatus === "function") {
      try {
        unsubStatus();
      } catch {}
    }

    unsubStatus = null;
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
  }

  return { start, stop };
}
