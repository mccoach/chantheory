// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\settings\common\useTriMasterToggle.js
// ==============================
// 说明：总控两态/三态切换控制器（适配 SettingsGrid 的 tri 复选 UI）
// - 参数：{ items: Array<{get():boolean,set(v:boolean):void}> }
// - 输出：masterUi.checked/indeterminate、cycleOnce()、updateSnapshot()
// - 规则：
//   * 当前状态为“全选/全不选” → 两态循环（全选 ⇄ 全不选）
//   * 否则 → 三态循环（全选 → 全不选 → 快照）
//   * snapshot 仅在“非总控操作”时更新（调用 updateSnapshot），总控自身循环不改变 snapshot。
// ==============================

import { ref, computed } from "vue";

export function useTriMasterToggle({ items = [] } = {}) {
  const lastSnapshot = ref(readFlags());          // 初始快照（可能是部分/全选/全不选）

  function readFlags() {
    return items.map((it) => (typeof it.get === "function" ? !!it.get() : false));
  }
  function writeAll(v) {
    items.forEach((it) => {
      try { it.set(!!v); } catch {}
    });
  }
  function writeSnapshot(flags) {
    const fs = Array.isArray(flags) ? flags : [];
    items.forEach((it, i) => {
      try { it.set(!!fs[i]); } catch {}
    });
  }

  const allOn = computed(() => readFlags().every((v) => v === true));
  const allOff = computed(() => readFlags().every((v) => v === false));
  const masterUi = {
    checked: computed(() => allOn.value),
    indeterminate: computed(() => !allOn.value && !allOff.value),
  };

  // 当前总控性质：两态或三态（仅在“非总控操作”后通过 updateSnapshot 重新判定）
  const masterMode = ref(determineMode());
  function determineMode() {
    const flags = readFlags();
    const isAllOn = flags.every((v) => v === true);
    const isAllOff = flags.every((v) => v === false);
    return isAllOn || isAllOff ? "two" : "tri";
  }

  // —— 修复点：总控循环不再更新 lastSnapshot，仅依据现有 masterMode 执行 —— //
  function cycleOnce() {
    const mode = masterMode.value;

    if (mode === "two") {
      // 两态：全选 ⇄ 全不选
      if (allOn.value) writeAll(false);
      else writeAll(true);
      // 不更新 lastSnapshot（避免把“快照”污染为全选/全不选）
      return;
    }

    // 三态：全选 → 全不选 → 快照
    const seq = ["allOn", "allOff", "snapshot"];
    const curKey = masterUi.checked.value
      ? "allOn"
      : masterUi.indeterminate.value
      ? "snapshot"
      : "allOff";
    const idx = seq.indexOf(curKey);
    const nextKey = seq[(idx + 1) % seq.length];

    if (nextKey === "allOn") writeAll(true);
    else if (nextKey === "allOff") writeAll(false);
    else writeSnapshot(lastSnapshot.value); // 仅使用“非总控时刻的快照”，不在这里更新快照

    // 不更新 lastSnapshot（保持“部分选择快照”仅来源于非总控变更）
  }

  // 非总控操作：刷新快照并即时重判总控性质（两态/三态）
  function updateSnapshot() {
    lastSnapshot.value = readFlags();
    masterMode.value = determineMode();
  }

  return { masterUi, cycleOnce, updateSnapshot };
}
