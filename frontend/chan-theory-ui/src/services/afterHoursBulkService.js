// src/services/afterHoursBulkService.js
// ==============================
// 盘后批量任务（After Hours Bulk）后端快照服务（契约 v2.1.2-FINAL+）
// 职责：
//   - 只做 HTTP 访问封装（identity / start / status / active / cancel / resume / retry_failed / failures）
//   - 不做状态管理、不做 SSE、不做持久化、不做 version gate
// ==============================

import { api } from "@/api/client";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

export async function fetchServerIdentity() {
  const { data } = await api.get("/api/server/identity");
  return data;
}

export async function bulkStart(payload) {
  const body = payload && typeof payload === "object" ? payload : {};
  const { data } = await api.post("/api/ensure-data/bulk/start", body);
  return data;
}

export async function bulkStatus({ batch_id }) {
  const bid = asStr(batch_id);
  const qs = new URLSearchParams();
  qs.set("batch_id", bid);

  const { data } = await api.get(`/api/ensure-data/bulk/status?${qs.toString()}`);
  return data;
}

export async function bulkStatusActive({ purpose = "after_hours" } = {}) {
  const qs = new URLSearchParams();
  const p = asStr(purpose);
  if (p) qs.set("purpose", p);

  const { data } = await api.get(`/api/ensure-data/bulk/status/active?${qs.toString()}`);
  return data;
}

export async function bulkCancel({ batch_id }) {
  const bid = asStr(batch_id);
  const { data } = await api.post("/api/ensure-data/bulk/cancel", { batch_id: bid });
  return data;
}

export async function bulkResume({ batch_id }) {
  const bid = asStr(batch_id);
  const { data } = await api.post("/api/ensure-data/bulk/resume", { batch_id: bid });
  return data;
}

export async function bulkRetryFailed({ batch_id }) {
  const bid = asStr(batch_id);
  const { data } = await api.post("/api/ensure-data/bulk/retry-failed", { batch_id: bid });
  return data;
}

// 可选扩展能力：失败列表（契约允许后端扩展字段/接口）
export async function fetchBulkFailures({ batch_id, offset = 0, limit = 200 } = {}) {
  const bid = asStr(batch_id);
  const qs = new URLSearchParams();
  qs.set("batch_id", bid);
  qs.set("offset", String(Math.max(0, Number(offset || 0))));
  qs.set("limit", String(Math.max(1, Number(limit || 200))));

  const { data } = await api.get(`/api/ensure-data/bulk/failures?${qs.toString()}`);
  return data;
}
