// src/api/client.js
import axios from "axios";

// 生成简短 trace_id（时间戳 + 随机）
function genTraceId() {
  const rand = Math.random().toString(36).slice(2, 8);
  return `web-${Date.now().toString(36)}-${rand}`;
}

// ISO 时间戳
function ts() {
  return new Date().toISOString();
}

export const api = axios.create({
  baseURL: "",
  timeout: 15000,
});

// 请求拦截：统一注入 trace_id / signal
api.interceptors.request.use(
  (config) => {
    const tid = config?.meta?.trace_id || genTraceId();
    config.meta = config.meta || {};
    config.meta.trace_id = tid;

    config.headers = config.headers || {};
    config.headers["x-trace-id"] = tid;

    if (config?.meta?.signal) {
      config.signal = config.meta.signal;
    }

    // 开发环境：统一、扁平的 HTTP 出站日志
    if (import.meta.env.DEV) {
      const method = (config.method || "GET").toUpperCase();
      const url = config.url;
      const paramsStr =
        config.params != null ? JSON.stringify(config.params) : "null";

      // 扁平字符串，避免 Object 需要展开
      console.log(
        `${ts()} [HTTP][req] method=${method} url=${url} trace_id=${tid} params=${paramsStr}`
      );
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
    const status = err?.response?.status;
    const url = err?.config?.url || "";

    if (import.meta.env.DEV) {
      if (!isCanceled) {
        // 扁平字符串错误日志
        console.error(
          `${ts()} [HTTP][err] url=${url} status=${status ?? "null"} code=${code} message=${message} trace_id=${trace_id ?? "null"}`
        );
      } else {
        // 取消类请求降级为 debug
        console.debug(
          `${ts()} [HTTP][canceled] url=${url} code=${code} message=${message} trace_id=${trace_id ?? "null"}`
        );
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