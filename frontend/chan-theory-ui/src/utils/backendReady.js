// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\utils\backendReady.js
// ==============================
// 说明：在前端应用启动时，先探活后端，避免因后端启动阶段导致前台立即报错。
// 更新点：探活改为“直连后端绝对地址”（默认 http://localhost:8000），绕开 Vite 代理，
// 以避免后端未启动时 Vite 代理输出 ECONNREFUSED 日志。
// 提供：
// - waitBackendAlive({ timeoutMs, intervalMs, origin }): 轮询 origin/api/ping
// ==============================

import axios from "axios"; // HTTP 客户端

// 读取后端地址：优先环境变量 VITE_BACKEND_ORIGIN，否则默认 http://localhost:8000
const DEFAULT_ORIGIN =
  import.meta.env.VITE_BACKEND_ORIGIN || "http://localhost:8000";

// 等待后端活跃：轮询 {origin}/api/ping，直到 200 或超时
export async function waitBackendAlive({
  timeoutMs = 8000, // 最长等待时长
  intervalMs = 500, // 轮询间隔
  origin = DEFAULT_ORIGIN, // 后端地址（绝对 URL）
} = {}) {
  const t0 = Date.now(); // 起点
  while (Date.now() - t0 < timeoutMs) {
    try {
      // 直连后端，不经由 Vite 代理，避免代理层 ECONNREFUSED 日志
      await axios.get(`${origin}/api/ping`, {
        timeout: Math.min(intervalMs, 1000),
      });
      return true; // 探活成功
    } catch (e) {
      await new Promise((r) => setTimeout(r, intervalMs)); // 等待后重试
    }
  }
  return false; // 超时未活跃
}