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

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

/**
 * 读取 client_instance_id（AfterHoursBulk v2.1.2 要求：必须持久化）
 *
 * 说明：
 * - 该值由 AfterHoursBulk controller 生成并写入 localStorage；
 * - axios 层只负责“按需读取并注入 header”，不负责生成（职责一致性）。
 */
function readClientInstanceIdFromLocalStorage() {
  try {
    // 与 afterHoursBulk/index.js 内的 key 保持一致（单一真相源）
    const k = "chan_after_hours_client_instance_id_v1";
    return asStr(localStorage.getItem(k));
  } catch {
    return "";
  }
}

/**
 * 判断是否为 bulk/identity 相关接口
 * - 仅这些接口要求必须带 x-client-instance-id
 * - 避免污染其它 API（严控范围）
 */
function shouldAttachClientInstanceId(url) {
  const u = asStr(url);
  if (!u) return false;
  // bulk APIs
  if (u.startsWith("/api/ensure-data/bulk")) return true;
  // identity
  if (u.startsWith("/api/server/identity")) return true;
  return false;
}

export const api = axios.create({
  baseURL: "",
  timeout: 15000,
});

// 请求拦截：统一注入 trace_id / signal / x-client-instance-id（bulk only）
api.interceptors.request.use(
  (config) => {
    const tid = config?.meta?.trace_id || genTraceId();
    config.meta = config.meta || {};
    config.meta.trace_id = tid;

    config.headers = config.headers || {};
    config.headers["x-trace-id"] = tid;

    // NEW: AfterHoursBulk v2.1.2 - bulk 请求必须带 x-client-instance-id
    try {
      const url = config?.url;
      if (shouldAttachClientInstanceId(url)) {
        const ci = readClientInstanceIdFromLocalStorage();
        if (ci) {
          config.headers["x-client-instance-id"] = ci;
        }
      }
    } catch {}

    if (config?.meta?.signal) {
      config.signal = config.meta.signal;
    }

    // 开发环境：统一、扁平的 HTTP 出站日志
    if (import.meta.env.DEV) {
      const method = (config.method || "GET").toUpperCase();
      const url = config.url;
      const paramsStr =
        config.params != null ? JSON.stringify(config.params) : "null";

      console.log(
        `${ts()} [HTTP][req] method=${method} url=${url} trace_id=${tid} params=${paramsStr}`
      );
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截：
// 1) HTTP 错误：仍走原有 reject 结构
// 2) NEW: bulk v2.1.2 业务失败（HTTP200 + ok=false）：统一转换为 Promise.reject({...})
api.interceptors.response.use(
  (resp) => {
    // NEW: 兼容 bulk v2.1.2 业务失败：HTTP 200 但 ok=false
    // 说明：
    // - 契约要求 bulk 业务失败统一 HTTP200 + 顶层 ok=false（不包 detail）
    // - 为保持调用端一致性（try/catch），这里将 ok=false 也变为 reject
    try {
      const data = resp?.data;
      const url = resp?.config?.url || "";

      if (data && typeof data === "object" && data.ok === false) {
        const code = String(data.code || "BULK_ERROR");
        const message = String(data.message || "request failed");
        const trace_id = data.trace_id || resp?.config?.meta?.trace_id || null;

        if (import.meta.env.DEV) {
          console.warn(
            `${ts()} [HTTP][biz_err] url=${url} code=${code} message=${message} trace_id=${trace_id ?? "null"}`
          );
        }

        return Promise.reject({
          code,
          message,
          trace_id,
          raw: { response: resp },
          // 透传后端补充字段（对 bulk controller 有用）
          backend_instance_id: data.backend_instance_id ?? null,
          batch: data.batch ?? null,
          active_batch: data.active_batch ?? null,
          queue_position: data.queue_position ?? null,
        });
      }
    } catch {}

    return resp;
  },
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
        console.error(
          `${ts()} [HTTP][err] url=${url} status=${status ?? "null"} code=${code} message=${message} trace_id=${trace_id ?? "null"}`
        );
      } else {
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
