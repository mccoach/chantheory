// src/services/localImportSettingsService.js
// ==============================
// 本地盘后导入路径设置服务（HTTP 访问层）
//
// 职责：
//   - 只做 local-import 路径设置相关 HTTP 封装
//   - 不做状态管理
//   - 不做 UI
//   - 不做业务推导
//
// 后端契约：
//   - GET  /api/local-import/settings
//   - POST /api/local-import/settings/browse
//   - POST /api/local-import/settings
//
// 统一字段：
//   - tdx_vipdoc_dir
//   - selected_dir
// ==============================

import { api } from "@/api/client";

function asStr(x) {
  return String(x == null ? "" : x).trim();
}

/**
 * 读取当前盘后导入根目录设置
 * @returns {Promise<object>}
 */
export async function fetchLocalImportSettings() {
  const { data } = await api.get("/api/local-import/settings");
  return data;
}

/**
 * 请求后端弹出系统文件夹选择窗口
 *
 * @param {object} payload
 * @param {string} [payload.initial_dir]
 * @returns {Promise<object>}
 */
export async function browseLocalImportSettingsDir(payload = {}) {
  const initialDir = asStr(payload?.initial_dir);

  const body = {};
  if (initialDir) {
    body.initial_dir = initialDir;
  }

  const { data } = await api.post("/api/local-import/settings/browse", body, {
    timeout: 30000,
  });
  return data;
}

/**
 * 保存盘后导入根目录设置
 *
 * @param {object} payload
 * @param {string} payload.tdx_vipdoc_dir
 * @returns {Promise<object>}
 */
export async function saveLocalImportSettings(payload = {}) {
  const dir = asStr(payload?.tdx_vipdoc_dir);

  const { data } = await api.post(
    "/api/local-import/settings",
    {
      tdx_vipdoc_dir: dir,
    },
    {
      timeout: 30000,
    }
  );

  return data;
}
