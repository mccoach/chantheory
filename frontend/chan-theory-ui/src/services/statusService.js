// frontend/src/services/statusService.js
// ==============================
// 说明：与后台状态接口交互的服务 (全新)
// - getStatus: 获取同步进度
// - triggerHistorySync: 触发历史数据同步
// - triggerIntegrityScan: 触发完整性扫描
// ==============================
import { api } from "@/api/client";

export async function getStatus() {
  const { data } = await api.get("/api/status/sync");
  return data;
}

export async function triggerHistorySync() {
  const { data } = await api.post("/api/debug/history-sync/start");
  return data;
}

export async function triggerIntegrityScan(symbols = null) {
  let url = "/api/debug/integrity-scan/start";
  if (symbols && Array.isArray(symbols) && symbols.length > 0) {
    const params = new URLSearchParams();
    symbols.forEach(s => params.append('symbols', s));
    url += `?${params.toString()}`;
  }
  const { data } = await api.post(url);
  return data;
}
