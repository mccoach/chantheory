// src/services/basicDataStatusService.js
// ==============================
// 基础数据任务状态服务（HTTP 访问层）
//
// 职责：
//   - 只做基础数据任务状态快照读取
//   - 不做状态管理
//   - 不做 UI
//   - 不做业务推导
//
// 后端契约：
//   - GET /api/system/basic-data-status
//
// 说明：
//   - 本服务读取的是“基础数据任务状态真相源”
//   - 适用任务：
//       * symbol_index
//       * profile_snapshot
//       * trade_calendar
//       * factor_events_snapshot
// ==============================

import { api } from "@/api/client";

/**
 * 读取基础数据任务状态快照
 *
 * 期望后端返回：
 * {
 *   ok: true,
 *   items: [
 *     {
 *       task_type: "symbol_index",
 *       status: "success" | "running" | "failed" | "idle",
 *       last_success_at: "...",
 *       last_failure_at: "...",
 *       last_error_message: "..."
 *     },
 *     ...
 *   ]
 * }
 *
 * 兼容：
 *   - items 不存在时，尝试兼容 data.tasks
 *
 * @returns {Promise<{items:Array<object>}>}
 */
export async function fetchBasicDataStatus() {
  const { data } = await api.get("/api/system/basic-data-status");
  const items = Array.isArray(data?.items)
    ? data.items
    : Array.isArray(data?.tasks)
      ? data.tasks
      : [];

  return { items };
}
