// src/composables/useRefreshStatus.js
// ==============================
// 说明：刷新状态管理器（单一职责）
// 职责：管理"已刷新"提示的显示逻辑
// 设计：独立的响应式状态，供展示组件纯消费
//
// 拆分理由：
//   - 从 MainChartPanel.vue 提取业务逻辑
//   - 组件简化为纯展示层
// ==============================

import { ref, computed, watch } from "vue";
import { pad2 } from "@/utils/timeFormat";

/**
 * 刷新状态管理器
 *
 * @param {Ref<boolean>} loadingRef - 加载中状态（外部传入）
 * @param {Ref<string>} errorRef - 错误信息（外部传入）
 * @returns {Object}
 */
export function useRefreshStatus(loadingRef, errorRef) {
  const lastRefreshedAt = ref(null);
  const showRefreshed = ref(false);

  // 监听加载完成事件
  watch(loadingRef, (isLoading, wasLoading) => {
    if (wasLoading === true && isLoading === false) {
      // 任何一次刷新结束，都记录“结论发生时间”
      lastRefreshedAt.value = new Date();

      // 仅在无错误时，短暂点亮“更新完成”提示
      if (!errorRef.value) {
        showRefreshed.value = true;

        // 2秒后自动隐藏
        setTimeout(() => {
          showRefreshed.value = false;
        }, 2000);
      }
    }
  });

  // 格式化时间（HH:MM:SS）
  const refreshedAtHHMMSS = computed(() => {
    if (!lastRefreshedAt.value) return "";

    const d = lastRefreshedAt.value;
    return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(
      d.getSeconds()
    )}`;
  });

  return {
    showRefreshed,
    refreshedAtHHMMSS,
  };
}
