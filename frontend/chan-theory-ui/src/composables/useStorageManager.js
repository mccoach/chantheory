// src/composables/useStorageManager.js
// ==============================
// 说明：存储管理组合式
// - 状态：usage, loading, error
// - 行为：refreshUsage, cleanupRange, migrateDb, doVacuum, doIntegrity
// - 本轮变更：cleanupRange 收口为“按 freq 单值循环调用”，传 table='cache'；汇总 deleted。
// ==============================

import { ref } from "vue"; // 响应式
import * as api from "@/services/storageService"; // 存储服务

export function useStorageManager() {
  // 状态：数据库用量、加载、错误
  const usage = ref({}); // 用量快照
  const loading = ref(false); // 加载标识
  const error = ref(""); // 错误消息

  // 刷新用量
  async function refreshUsage() {
    loading.value = true; // 置加载态
    error.value = ""; // 清空错误
    try {
      usage.value = await api.getUsage(); // 请求用量
    } catch (e) {
      error.value = e?.message || "读取失败"; // 记录错误
    } finally {
      loading.value = false; // 复位加载态
    }
  }

  // 清理区间（支持 freqs 多选：循环调用单次 cleanup）
  async function cleanupRange({ symbol, freqs, start_ms, end_ms }) {
    loading.value = true; // 置加载态
    error.value = ""; // 清空错误
    try {
      // 规范 freqs：若未传则空数组；逐一调用 cleanup（table 固定 'cache'）
      const list = Array.isArray(freqs) ? freqs : [];
      let totalDeleted = 0; // 汇总删除行数
      for (const f of list) {
        const resp = await api.cleanup({
          table: "cache", // 本面板仅清理缓存分区
          symbol, // 标的代码
          freq: f, // 单个频率
          start_ms, // 开始毫秒（可空）
          end_ms, // 结束毫秒（可空）
        });
        // 汇总 deleted；忽略单次错误以提升容错（也可按需中断）
        if (resp && typeof resp.deleted === "number") {
          totalDeleted += resp.deleted;
        }
      }
      return { ok: true, deleted: totalDeleted }; // 返回聚合结果
    } catch (e) {
      // 统一错误消息
      error.value = e?.message || "清理失败";
      return { ok: false, error: error.value };
    } finally {
      loading.value = false; // 复位加载态
      await refreshUsage(); // 清理后刷新用量快照
    }
  }

  // 迁移数据库
  async function migrateDb(db_path) {
    loading.value = true; // 置加载态
    error.value = ""; // 清空错误
    try {
      return await api.migrate({ db_path }); // 调用迁移
    } catch (e) {
      error.value = e?.message || "迁移失败"; // 记录错误
      return { ok: false, error: error.value };
    } finally {
      loading.value = false; // 复位加载态
      await refreshUsage(); // 迁移后刷新用量
    }
  }

  // VACUUM
  async function doVacuum() {
    try {
      return await api.vacuum(); // 执行 VACUUM
    } catch (e) {
      return { ok: false, error: e?.message || "vacuum 失败" }; // 错误返回
    } finally {
      await refreshUsage(); // 完成后刷新用量
    }
  }

  // 完整性检查
  async function doIntegrity() {
    try {
      return await api.integrity(); // 调用完整性检查
    } catch (e) {
      return { ok: false, error: e?.message || "校验失败" }; // 错误返回
    }
  }

  // 暴露状态与操作
  return {
    usage, // 用量响应式
    loading, // 加载态
    error, // 错误文本
    refreshUsage, // 刷新用量
    cleanupRange, // 按频率循环清理
    migrateDb, // 迁移数据库
    doVacuum, // VACUUM
    doIntegrity, // 完整性检查
  };
}
