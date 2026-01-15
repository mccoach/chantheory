// src/services/afterHoursBulkService.js
// ==============================
// 盘后批量任务（After Hours Bulk）后端快照服务（契约 v1.1）
// 职责：
//   - 只做 HTTP 访问封装（status / latest / failures）
//   - 不做状态管理、不做 SSE、不做持久化
// ==============================

import { api } from "@/api/client";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

export async function fetchBulkStatus({ batch_id }) {
  const bid = asStr(batch_id);
  const qs = new URLSearchParams();
  qs.set("batch_id", bid);

  const { data } = await api.get(`/api/ensure-data/bulk/status?${qs.toString()}`);
  return data;
}

export async function fetchBulkStatusLatest({ purpose, state, client_instance_id } = {}) {
  const qs = new URLSearchParams();

  const p = asStr(purpose);
  const st = asStr(state);
  const ci = asStr(client_instance_id);

  if (p) qs.set("purpose", p);
  if (st) qs.set("state", st);
  if (ci) qs.set("client_instance_id", ci);

  const { data } = await api.get(`/api/ensure-data/bulk/status/latest?${qs.toString()}`);
  return data;
}

export async function fetchBulkFailures({ batch_id, offset = 0, limit = 200 } = {}) {
  const bid = asStr(batch_id);
  const qs = new URLSearchParams();
  qs.set("batch_id", bid);
  qs.set("offset", String(Math.max(0, Number(offset || 0))));
  qs.set("limit", String(Math.max(1, Number(limit || 200))));

  const { data } = await api.get(`/api/ensure-data/bulk/failures?${qs.toString()}`);
  return data;
}
