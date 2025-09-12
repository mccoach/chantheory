// src/services/storageService.js
// ==============================
// 说明：存储管理服务，对接 /api/storage*
// - getUsage(): 数据库用量
// - cleanup({table,symbol,freq,start_ms,end_ms})  // 收口为“单次清理”调用
// - migrate({db_path})
// - vacuum()
// - integrity()
// ==============================

import { api } from "@/api/client"; // 统一 axios 客户端（含 trace_id 拦截）

/**
 * 获取数据库用量
 * GET /api/storage/usage
 */
export async function getUsage() {
  const { data } = await api.get("/api/storage/usage"); // 请求用量
  return data?.usage || {}; // 返回 usage 对象（兼容空）
}

/**
 * 清理数据（单次调用版）
 * POST /api/storage/cleanup
 * 参数：
 * - table: 'cache' | 'daily'（本项目面板仅用于缓存清理，传 'cache'）
 * - symbol: 标的代码
 * - freq: 单个频率（如 '1m'），对于 cache 分区必填；daily 分支忽略
 * - start_ms/end_ms: 窗口（可空；二者均空则整分区）
 */
export async function cleanup({ table = "cache", symbol, freq, start_ms, end_ms }) {
  // 构造 payload：只发送统一契约字段（不再发送 freqs 数组）
  const payload = {
    table, // 表类型：cache/daily
    symbol, // 标的代码
    freq, // 单个频率（cache 分区清理）
    start_ms, // 开始毫秒（可空）
    end_ms, // 结束毫秒（可空）
  };
  const { data } = await api.post("/api/storage/cleanup", payload); // 发起清理
  return data; // 返回后端响应（{ok, deleted, trace_id}）
}

/**
 * 迁移数据库文件
 * POST /api/storage/migrate
 * 参数：
 * - db_path: 新数据库文件路径
 */
export async function migrate({ db_path }) {
  const { data } = await api.post("/api/storage/migrate", { db_path });
  return data;
}

/**
 * VACUUM 优化
 * POST /api/storage/vacuum
 */
export async function vacuum() {
  const { data } = await api.post("/api/storage/vacuum");
  return data;
}

/**
 * 完整性检查
 * GET /api/storage/integrity
 */
export async function integrity() {
  const { data } = await api.get("/api/storage/integrity");
  return data;
}
