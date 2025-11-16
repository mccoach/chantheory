// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\utils\backendReady.js
// ==============================
// 说明：后端探活工具（V2.0 - 性能优化版）
// 改动：
//   1. 探活间隔从600ms优化到200ms（更快响应）
//   2. 增加首次立即探活（避免无谓等待）
//   3. 优化日志输出（仅关键信息）
// ==============================

import axios from "axios";

// 读取后端地址：优先环境变量，否则默认本地8000端口
const DEFAULT_ORIGIN =
  import.meta.env.VITE_BACKEND_ORIGIN || "http://localhost:8000";

/**
 * 等待后端服务就绪
 * 
 * @param {Object} options - 配置选项
 * @param {number} options.timeoutMs - 最长等待时间（默认10秒）
 * @param {number} options.intervalMs - 轮询间隔（默认200ms）
 * @param {string} options.origin - 后端地址（默认 http://localhost:8000）
 * @returns {Promise<boolean>} 是否在超时前连接成功
 */
export async function waitBackendAlive({
  timeoutMs = 10000,
  intervalMs = 200,  // ← 优化：从600ms改为200ms
  origin = DEFAULT_ORIGIN,
} = {}) {
  const t0 = Date.now();
  const url = `${origin}/api/ping`;
  
  // ===== 优化点1：首次立即探活（不等待）=====
  try {
    await axios.get(url, { timeout: 1000 });
    console.log('[探活] ✅ 后端已就绪（首次探活成功）');
    return true;
  } catch (e) {
    // 首次失败，打印原因并进入轮询
    console.log(`[探活] ⏳ 等待后端启动... (${e.message})`);
  }
  
  // ===== 优化点2：轮询探活（间隔200ms）=====
  while (Date.now() - t0 < timeoutMs) {
    await new Promise(r => setTimeout(r, intervalMs));
    
    try {
      await axios.get(url, { timeout: 1000 });
      const elapsed = Date.now() - t0;
      console.log(`[探活] ✅ 后端已就绪 (耗时${elapsed}ms)`);
      return true;
    } catch {
      // 静默重试（避免刷屏）
    }
  }
  
  // 超时失败
  console.warn('[探活] ❌ 后端连接超时');
  return false;
}