// src/composables/afterHoursBulk/sseTracker.js
// ==============================
// V2.0 - BREAKING: SSE 契约对齐（bulk.batch.snapshot）
//
// 要点：
// - SSE event：bulk.batch.snapshot（通过现有 /api/events/stream 推送）
// - payload：{ type, backend_instance_id, batch }
// - SSE 仅作为“增量快照推送”通道
// - 统一走 version gate：只接受 progress.version 更大的 batch 快照
// ==============================

export function createSseBatchSnapshotTracker({ state, eventStream, onBatchSnapshot }) {
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

    _unsub = eventStream.subscribe("bulk.batch.snapshot", (data) => {
      try {
        if (!data || data.type !== "bulk.batch.snapshot") return;

        const be = data?.backend_instance_id;
        if (be) state.backendInstanceId.value = String(be);

        const b = data?.batch;
        if (!b || typeof b !== "object") return;

        const active = state.activeBatch.value;
        const activeBatchId = active?.batch_id ? String(active.batch_id) : "";
        const batchId = b?.batch_id ? String(b.batch_id) : "";

        // 只消费当前 activeBatch 的快照，避免串批次污染
        if (activeBatchId && batchId !== activeBatchId) return;

        onBatchSnapshot(b, { source: "sse_bulk.batch.snapshot" });
      } catch {}
    });
  }

  return { start, stop };
}
