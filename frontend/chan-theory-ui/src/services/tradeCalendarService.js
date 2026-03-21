// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\services\tradeCalendarService.js
// ==============================
// 说明：交易日历服务（前端 HTTP 访问层）
// 职责：从后端读取 trade_calendar 快照
//
// 后端现约定（已变更）：
//   - 表为“完整自然日历表”，不是“仅交易日表”
//   - 从 19901219 到本地日历文件最晚年份的 12 月 31 日
//   - market 固定为 "CN"
//   - items 同时包含：
//       * is_trading_day = 1 交易日
//       * is_trading_day = 0 非交易日
//
// 前端注意：
//   - 本服务层只负责原样读取快照，不在此处做过滤；
//   - 若调用方只需要交易日，必须在上层自行按 is_trading_day === 1 过滤。
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
 *       { date: 19901221, market: "CN", is_trading_day: 0 },
 *       ...
 *     ]
 *   }
 *
 * @returns {Promise<{ items: Array<{date:number,market:string,is_trading_day:number}> }>}
 */
export async function fetchTradeCalendarSnapshot() {
  const { data } = await api.get("/api/trade-calendar");
  const items = Array.isArray(data?.items) ? data.items : [];
  return { items };
}
