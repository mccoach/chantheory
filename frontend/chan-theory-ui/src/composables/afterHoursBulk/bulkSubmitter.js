// src/composables/afterHoursBulk/bulkSubmitter.js
// ==============================
// AfterHoursBulk 模块：Bulk 入队器（职责单一）
// - 只负责调用 POST /api/ensure-data/bulk 并返回响应
// - 不做 SSE，不做统计，不做重试
// ==============================

export function createBulkSubmitter({ declareEnsureDataBulk }) {
  if (typeof declareEnsureDataBulk !== "function") {
    throw new Error("[AfterHoursBulk] declareEnsureDataBulk is required");
  }

  async function submit(payload) {
    const body = payload && typeof payload === "object" ? payload : {};
    return declareEnsureDataBulk(body);
  }

  return { submit };
}
