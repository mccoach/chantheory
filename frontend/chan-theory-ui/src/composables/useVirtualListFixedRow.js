// src/composables/useVirtualListFixedRow.js
// ==============================
// 说明：固定行高虚拟列表（windowing）工具
// 职责：仅根据 scrollTop / viewportHeight / rowHeight / totalCount 计算可视范围与上下占位高度。
// 设计：
//   - 纯 UI 工具，不掺任何业务；
//   - 支持 overscan（多渲染上下若干行，滚动更平滑）。
// ==============================

import { computed, ref } from "vue";

function clampInt(n, min, max) {
  const x = Math.floor(Number(n));
  if (!Number.isFinite(x)) return min;
  return Math.max(min, Math.min(max, x));
}

export function useVirtualListFixedRow({
  totalCountRef,
  rowHeight = 32,
  viewportHeightRef,
  overscan = 6,
}) {
  const scrollTop = ref(0);

  const totalCount = computed(() => {
    const n = Number(totalCountRef?.value ?? 0);
    return Number.isFinite(n) ? Math.max(0, Math.floor(n)) : 0;
  });

  const rowH = Math.max(1, Math.floor(Number(rowHeight || 32)));
  const os = Math.max(0, Math.floor(Number(overscan || 0)));

  const viewportH = computed(() => {
    const n = Number(viewportHeightRef?.value ?? 0);
    return Number.isFinite(n) ? Math.max(0, Math.floor(n)) : 0;
  });

  const visibleCount = computed(() => {
    const vh = viewportH.value;
    if (!vh) return 0;
    return Math.max(1, Math.ceil(vh / rowH));
  });

  const startIndex = computed(() => {
    const n = totalCount.value;
    if (!n) return 0;
    const raw = Math.floor(scrollTop.value / rowH) - os;
    return clampInt(raw, 0, Math.max(0, n - 1));
  });

  const endIndex = computed(() => {
    const n = totalCount.value;
    if (!n) return -1;
    const raw = startIndex.value + visibleCount.value + os * 2 - 1;
    return clampInt(raw, 0, Math.max(0, n - 1));
  });

  const padTop = computed(() => startIndex.value * rowH);
  const padBottom = computed(() => {
    const n = totalCount.value;
    if (!n) return 0;
    const after = n - 1 - endIndex.value;
    return Math.max(0, after * rowH);
  });

  function onScroll(e) {
    try {
      const t = e?.target;
      const st = Number(t?.scrollTop ?? 0);
      scrollTop.value = Number.isFinite(st) ? st : 0;
    } catch {}
  }

  return {
    scrollTop,
    startIndex,
    endIndex,
    padTop,
    padBottom,
    rowHeight: rowH,
    onScroll,
  };
}
