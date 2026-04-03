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
// 当前正式契约：
//   - GET  /api/local-import/candidates
//       * 只读取当前已有候选结果
//       * 不触发扫描
//   - POST /api/local-import/candidates/refresh
//       * 显式重新扫描候选
//       * 不返回候选结果本体
//   - POST /api/local-import/start
//   - GET  /api/local-import/status
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

export async function refreshLocalImportCandidates() {
  const { data } = await api.post("/api/local-import/candidates/refresh");
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
