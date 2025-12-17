// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\services\tradeCalendarService.js
// ==============================
// 说明：交易日历服务（前端 HTTP 访问层）
// 职责：从后端读取 trade_calendar 快照
// 
// 后端约定（基于 DB 现状）：
//   - 表中仅存储交易日（is_trading_day=1）；非交易日不入库。
//   - market="CN"。
//   - items 数组应包含所有记录。
// ==============================

import { api } from "@/api/client";

/**
 * 读取交易日历快照
 *
 * 期望的后端响应格式（示例）：
 *   {
 *     ok: true,
 *     items: [
 *       { date: 19901219, market: "CN", is_trading_day: 1 },
 *       { date: 19901220, market: "CN", is_trading_day: 1 },
 *       ... (仅包含交易日)
 *     ]
 *   }
 *
 * @returns {Promise<{ items: Array<{date:number,market:string,is_trading_day:number}> }>}
 */
export async function fetchTradeCalendarSnapshot() {
  // TODO: 如后端实际路径不同，请在此处调整
  const { data } = await api.get("/api/trade-calendar");
  const items = Array.isArray(data?.items) ? data.items : [];
  return { items };
}