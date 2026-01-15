// src/composables/afterHoursBulk/sseTracker.js
// ==============================
// AfterHoursBulk 模块：SSE task_done 跟踪器（契约 v1.1）
//
// v1.1 核心要求：真相源在后端
// - SSE 仅作为“增量快照推送”通道
// - 前端不再通过 SSE 自行累加 done/failed
// - 统一走 version gate：只接受 progress.version 更大的 batch 快照
// ==============================

export function createSseTaskDoneTracker({ state, eventStream, onBatchSnapshot }) {
  if (!state) throw new Error("[AfterHoursBulk] state is required");
  if (!eventStream || typeof eventStream.subscribe !== "function") {
    throw new Error("[AfterHoursBulk] eventStream.subscribe is required");
  }
  if (typeof onBatchSnapshot !== "function") {
    throw new Error("[AfterHoursBulk] onBatchSnapshot is required");
  }

  let _unsub = null;

  function stop() {
    if (typeof _unsub === "function") {
      try { _unsub(); } catch {}
    }
    _unsub = null;
  }

  function start() {
    stop();

    _unsub = eventStream.subscribe("task_done", (data) => {
      try {
        const b = data?.batch;
        if (!b || typeof b !== "object") return;

        const active = state.activeBatch.value;
        const activeBatchId = active?.batch_id ? String(active.batch_id) : "";
        const batchId = b?.batch_id ? String(b.batch_id) : "";

        if (!activeBatchId || !batchId) return;
        if (batchId !== activeBatchId) return;

        onBatchSnapshot(b, { source: "sse_task_done" });
      } catch {}
    });
  }

  return { start, stop };
}
