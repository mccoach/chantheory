// src/api/client.js
import axios from "axios";

// 生成简短 trace_id（时间戳 + 随机）
function genTraceId() {
  const rand = Math.random().toString(36).slice(2, 8);
  return `web-${Date.now().toString(36)}-${rand}`;
}

export const api = axios.create({
  baseURL: "",
  timeout: 15000,
});

// 请求拦截：统一注入 trace_id / signal
api.interceptors.request.use(
  (config) => {
    // 若上层未提供 meta.trace_id，则自动生成一个
    const tid = config?.meta?.trace_id || genTraceId();
    config.meta = config.meta || {};
    config.meta.trace_id = tid;

    config.headers = config.headers || {};
    config.headers["x-trace-id"] = tid;

    if (config?.meta?.signal) {
      config.signal = config.meta.signal;
    }

    // 可选：开发时打印一次出站请求（便于对拍）
    if (import.meta.env.DEV) {
      console.log(
        `[${Date.now()}][frontend/api/client.js] request ${config.method?.toUpperCase()} ${
          config.url
        } trace_id=${tid}`
      );
      // eslint-disable-next-line no-console
      console.debug("[api] req", {
        url: config.url,
        method: config.method,
        params: config.params,
        headers: { "x-trace-id": tid },
      });
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截：统一错误结构 + 调试输出（取消请求静默）
api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const detail = err?.response?.data?.detail || err?.response?.data || {};
    const isCanceled =
      err?.code === "ERR_CANCELED" ||
      err?.name === "CanceledError" ||
      err?.name === "AbortError" ||
      String(err?.message || "")
        .toLowerCase()
        .includes("canceled") ||
      String(err?.message || "")
        .toLowerCase()
        .includes("aborted");

    const code = isCanceled ? "CANCELED" : detail?.code || "HTTP_ERROR";
    const message = isCanceled
      ? "canceled"
      : detail?.message || err?.message || "request failed";
    const trace_id = detail?.trace_id || err?.config?.meta?.trace_id || null;

    // 开发场景打印 trace 片段，便于快速定位（取消类错误静默不打 error）
    if (import.meta.env.DEV) {
      if (!isCanceled) {
        // eslint-disable-next-line no-console
        console.error("[api] err", {
          url: err?.config?.url,
          status: err?.response?.status,
          code,
          message,
          trace_id,
          trace: detail?.trace?.slice?.(0, 800),
        });
      } else {
        // 取消行为仅做 debug 级别输出，避免污染控制台
        // eslint-disable-next-line no-console
        console.debug("[api] canceled", {
          url: err?.config?.url,
          code,
          message,
          trace_id,
        });
      }
    }

    return Promise.reject({
      code,
      message,
      trace_id,
      raw: err,
      trace: detail?.trace,
    });
  }
);