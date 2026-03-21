// src/services/localImportService.js
// ==============================
// 本地盘后数据导入服务（HTTP 访问层）
//
// 职责：
//   - 只做 local-import 相关 HTTP 封装
//   - 不做状态管理
//   - 不做 SSE
//   - 不做前端推导
//
// 契约：
//   - GET  /api/local-import/candidates
//   - POST /api/local-import/start
//   - GET  /api/local-import/status
//   - GET  /api/local-import/tasks?batch_id=...
//   - POST /api/local-import/cancel
//   - POST /api/local-import/retry
// ==============================

import { api } from "@/api/client";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

function normalizeSelectionItem(item) {
  const it = item && typeof item === "object" ? item : {};
  const market = asStr(it.market).toUpperCase();
  const symbol = asStr(it.symbol);
  const freq = asStr(it.freq);

  if (!market || !symbol || !freq) return null;

  return { market, symbol, freq };
}

export async function fetchLocalImportCandidates() {
  const { data } = await api.get("/api/local-import/candidates");
  return data;
}

export async function startLocalImport({ items } = {}) {
  const list = Array.isArray(items) ? items : [];
  const normalized = list.map(normalizeSelectionItem).filter(Boolean);

  const { data } = await api.post("/api/local-import/start", {
    items: normalized,
  });

  return data;
}

export async function fetchLocalImportStatus() {
  const { data } = await api.get("/api/local-import/status");
  return data;
}

export async function fetchLocalImportTasks({ batch_id } = {}) {
  const batchId = asStr(batch_id);
  const qs = new URLSearchParams();
  qs.set("batch_id", batchId);

  const { data } = await api.get(`/api/local-import/tasks?${qs.toString()}`);
  return data;
}

export async function cancelLocalImport({ batch_id } = {}) {
  const batchId = asStr(batch_id);

  const { data } = await api.post("/api/local-import/cancel", {
    batch_id: batchId,
  });

  return data;
}

export async function retryLocalImport({ batch_id } = {}) {
  const batchId = asStr(batch_id);

  const { data } = await api.post("/api/local-import/retry", {
    batch_id: batchId,
  });

  return data;
}
