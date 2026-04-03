// src/composables/useProfileSnapshot.js
// ==============================
// 说明：profile_snapshot 领域归口模块（单例）
//
// 当前职责（纯业务执行器）：
//   1) 读取/等待 profile_snapshot 可用
//   2) 维护“是否正在加载快照”的前端读取状态
//
// 命令权收敛：
//   - 本模块不再自行 declareProfileSnapshot
//   - 谁要准备 profile_snapshot，只能由外部显式下命令：
//       1) App 启动链
//       2) 页面按钮路径
// ==============================

import { ref, readonly } from "vue";

let _singleton = null;

const ready = ref(false);
const loading = ref(false);
const error = ref("");

let _loadingPromise = null;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function ensureLoaded() {
  if (ready.value) return { ok: true };
  if (_loadingPromise) return _loadingPromise;

  loading.value = true;
  error.value = "";

  _loadingPromise = Promise.resolve({ ok: true }).finally(() => {
    loading.value = false;
    _loadingPromise = null;
  });

  return _loadingPromise;
}

async function waitUntilIdle({ timeoutMs = 60000, pollMs = 100 } = {}) {
  const deadline = Date.now() + Math.max(1000, Number(timeoutMs || 60000));

  while (loading.value) {
    if (Date.now() > deadline) {
      throw new Error("[useProfileSnapshot] waitUntilIdle timeout");
    }
    await sleep(Math.max(20, Number(pollMs || 100)));
  }

  return { ok: true };
}

async function waitReadable(options = {}) {
  try {
    await waitUntilIdle({ timeoutMs: options?.timeoutMs || 60000 });
    return { ok: true };
  } catch (e) {
    return { ok: false, message: e?.message || "waitReadable failed" };
  }
}

function markReady() {
  ready.value = true;
  error.value = "";
}

function markNotReady(message = "") {
  ready.value = false;
  if (message) {
    error.value = String(message);
  }
}

export function useProfileSnapshot() {
  if (_singleton) return _singleton;

  _singleton = {
    ready: readonly(ready),
    loading: readonly(loading),
    error: readonly(error),

    ensureLoaded,
    waitReadable,
    waitUntilIdle,

    markReady,
    markNotReady,
  };

  return _singleton;
}
