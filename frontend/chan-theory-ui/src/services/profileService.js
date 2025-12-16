// src/services/profileService.js
// ==============================
// 说明：标的档案快照服务
// 职责：从 /api/profile/current 读取单一标的的最新档案快照。
// 设计：
//   - 与 candles/factors 服务风格统一：纯查询，不做 Task 声明；
//   - Task 声明通过 ensureDataAPI.declareCurrentProfile 完成；
//   - 上层在 declare + waitTasksDone 之后调用本函数读取快照。
// ==============================

import { api } from "@/api/client";

/**
 * 读取单一标的的档案快照（不触发 Task）
 *
 * @param {string} symbol - 标的代码
 * @returns {Promise<object|null>} - 若存在档案则返回 item 对象，否则返回 null
 *
 * 响应约定（后端已对齐）：
 *   {
 *     ok: true,
 *     item: {
 *       symbol, name, market, class, type, board, listing_date, updated_at,
 *       total_shares, float_shares, total_value, nego_value, pe_static,
 *       industry, region, concepts: [...]
 *     } | null,
 *     trace_id: "..."
 *   }
 */
export async function fetchProfile(symbol) {
  const params = new URLSearchParams();
  params.set("symbol", symbol);

  const { data } = await api.get(`/api/profile/current?${params.toString()}`);

  // 只返回 item，由上层决定如何用（null 表示当前无档案）
  return data?.item ?? null;
}