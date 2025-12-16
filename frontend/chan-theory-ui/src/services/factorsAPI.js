// src/services/factorsAPI.js
// ==============================
// 说明：复权因子服务（V2.1 - timeout 调整版）
// 职责：纯 API 查询，不做复权计算
// 改动：
//   - 将 GET /api/factors 的超时时间从 10000ms 提升到 30000ms，
//     以适配首次拉取较长历史因子的耗时场景。
// ==============================

import { api } from "@/api/client";

/**
 * 查询复权因子
 * 
 * @param {string} symbol - 标的代码
 * @param {Object} options - 可选参数 {startDate, endDate}
 * @returns {Promise<Array>} 因子数组
 */
export async function fetchFactors(symbol, options = {}) {
  const params = new URLSearchParams();
  params.set("symbol", symbol);

  if (options.startDate) {
    params.set("start_date", options.startDate);
  }
  if (options.endDate) {
    params.set("end_date", options.endDate);
  }

  // NOTE: timeout 提升到 30000ms，避免首拉较长历史因子时被前端掐断。
  const { data } = await api.get(`/api/factors?${params.toString()}`, {
    timeout: 30000,
  });

  return data.factors || [];
}

// ===== 删除：applyAdjustment 函数（已移至 engines/adjustment.js）=====