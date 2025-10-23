// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useViewCommandHub.js
// ==============================
// 说明（单文件命令中枢 · 奥卡姆剃刀原则 · 不扩展范围）
// - 保持文件结构与函数/变量的前后顺序，如无必要不调整；仅在确有必要时调整并附注释说明顺序变动原因。
// - 变更目标：
//   1) barsCount/rightTs/atRightEdge 为唯一权威显示状态源（持久化 + 恢复 + 统一广播）。
//   2) markerWidthPx 仅由 hostWidthPx 与 barsCount 派生（范围 [1,16]）。
//   3) execute() 动作枚举完整且严格遵守 12 条交互规则；每次主动交互立即持久化，帧级两帧合并后只广播最终态。
//   4) setDatasetBounds() 仅在后端回包落地后应用触底/越界规则，且不会“被动改变 bars”；保存边界 minTs/maxTs 以便后续动作中正确维护 atRightEdge。
// - 不留向后兼容退路：不做旧逻辑的降级回退；改动处均以中枢为唯一来源。
// ==============================

import { ref } from "vue"; // 响应式
import { useUserSettings } from "@/composables/useUserSettings"; // 本地持久化（viewBars/rightTs/atRightEdge）
import { presetToBars, pickPresetByBarsCountDown } from "@/constants"; // 预设→bars 映射/向下就近高亮

// —— 单例缓存（保持原顺序，不调整） —— //
let _hubSingleton = null;

/**
 * useViewCommandHub
 * 返回中枢单例；首次调用时初始化内部状态与方法。
 */
export function useViewCommandHub() {
  if (_hubSingleton) return _hubSingleton;

  // 引用用户设置（Local-first）
  const settings = useUserSettings();

  // —— 权威状态（refs） —— //
  const barsCount = ref(1); // 可见根数（权威持久化源）
  const rightTs = ref(null); // 切片右端锚点（毫秒，权威持久化源）
  const atRightEdge = ref(false); // 触底状态（最新一条）
  const markerWidthPx = ref(8); // 符号宽度（派生，1..16）
  const hostWidthPx = ref(800); // 宿主宽度（由主窗上报）
  const allRows = ref(0); // 当前 ALL 序列总根数（数据落地时设置）
  const currentPresetKey = ref(settings.windowPreset.value || "ALL"); // 当前窗宽高亮预设
  const currentFreq = ref(settings.freq.value || "1d"); // 当前频率（用于查表）
  const currentSymbol = ref(settings.lastSymbol.value || ""); // 当前标的代码（仅记录）

  // —— 新增：数据集边界缓存（必要的顺序变更说明）
  // 说明：为了在“主动交互动作中”正确维护 atRightEdge（判断 rightTs 是否在最右端），需要在中枢缓存 minTs/maxTs。
  // 这是对原文件的“新增状态”且放置在权威状态段，以便后续函数（setDatasetBounds/execute）使用。
  const minTsRef = ref(null); // 数据集左端毫秒（后端回包落地后设置）
  const maxTsRef = ref(null); // 数据集右端毫秒（后端回包落地后设置）

  // —— 订阅者管理（广播中心） —— //
  const _subs = new Map(); // id -> callback
  let _nextSubId = 1; // 自增订阅ID
  let _rafScheduled = false; // 帧级合并标记（2帧内合并同类指令，避免抖动）
  let _rafTickCount = 0; // 帧计数（最多2帧）
  let _pendingNotify = false; // 是否有待广播

  /**
   * 计算符号宽度（派生项）
   * - 简化：统一用 (hostWidth * 0.88) / barsCount，限制在 [1,16]。
   * - 奥卡姆剃刀原则：不引入 barPercent 等差异；统一估算即可满足一致性与体验要求。
   */
  function _recalcMarkerWidth() {
    const b = Math.max(1, Number(barsCount.value || 1));
    const w = Math.max(1, Number(hostWidthPx.value || 1));
    const approx = Math.round((w * 0.88) / b);
    markerWidthPx.value = Math.max(1, Math.min(16, approx));
  }

  /**
   * 更新 atRightEdge 状态（新增辅助函数）
   * - 目的：当 rightTs 改变或数据集边界更新后，自动维护 atRightEdge = (rightTs == maxTs)。
   * - 位置：新增函数放在持久化/_scheduleNotify 之前，确保调用顺序合理（不改变原函数前后顺序）。
   */
  function _updateEdgeFlag() {
    try {
      const max = Number.isFinite(+maxTsRef.value) ? +maxTsRef.value : null;
      const rt = Number.isFinite(+rightTs.value) ? +rightTs.value : null;
      if (max != null && rt != null) {
        atRightEdge.value = rt === max;
      }
    } catch {
      // 容错：不中断主流程
    }
  }

  /**
   * 持久化当前 bars/rightTs/atRightEdge（统一入口）
   * - 重要：任何主动交互一旦改变 bars 或 rightTs，必须立即调用本方法持久化。
   * - 顺序：保持与原文件一致（persist → scheduleNotify）。
   */
  function _persist() {
    try {
      settings.setViewBars(
        currentSymbol.value,
        currentFreq.value,
        barsCount.value
      );
      if (rightTs.value != null) {
        settings.setRightTs(
          currentSymbol.value,
          currentFreq.value,
          rightTs.value
        );
      }
      settings.setAtRightEdge(
        currentSymbol.value,
        currentFreq.value,
        atRightEdge.value
      );
    } catch (e) {
      // 容错：LocalStorage 写失败不阻断流程
    }
  }

  /**
   * 帧级合并（最多2帧）：避免高频滚轮/拖拽导致抖动，统一在 2 帧内合并并广播一次最终状态。
   * - 覆盖防抖思路：若期间又有新指令到达，则旧的待广播“中间态”不落地，最终只广播最后一次状态。
   * - 前后顺序：保持与原文件一致，不调整。
   */
  function _scheduleNotify() {
    _pendingNotify = true;
    if (_rafScheduled) return;
    _rafScheduled = true;
    _rafTickCount = 0;
    const tick = () => {
      _rafTickCount++;
      if (_rafTickCount < 2) {
        requestAnimationFrame(tick);
        return;
      }
      _rafScheduled = false;
      if (_pendingNotify) {
        _pendingNotify = false;
        _broadcast();
      }
    };
    requestAnimationFrame(tick);
  }

  /**
   * 广播最终状态到所有订阅者（单次 · 最终值）
   */
  function _broadcast() {
    const snapshot = getState();
    _subs.forEach((cb) => {
      try {
        cb(snapshot);
      } catch {}
    });
  }

  /**
   * 从本地持久化恢复 bars/rightTs/atRightEdge（刷新或重启时立即应用）
   * - 仅恢复，不做回表重置；任何“被动改变”不允许发生。
   * - 顺序：保持与原文件一致（init → recalcWidth → scheduleNotify）。
   */
  function initFromPersist(code, freq) {
    currentSymbol.value = String(code || "").trim();
    currentFreq.value = String(freq || "").trim() || "1d";
    const savedBars = settings.getViewBars(
      currentSymbol.value,
      currentFreq.value
    );
    const savedTs = settings.getRightTs(currentSymbol.value, currentFreq.value);
    const savedEdge = settings.getAtRightEdge(
      currentSymbol.value,
      currentFreq.value
    );
    barsCount.value = Math.max(1, Number(savedBars || 1));
    rightTs.value = Number.isFinite(+savedTs) ? +savedTs : null;
    atRightEdge.value = !!savedEdge;
    _recalcMarkerWidth();
    _scheduleNotify();
  }

  /**
   * 设置当前数据集的边界与总根数（后端回包落地后调用）
   * - 规则：禁止“被动改变 bars”；rightTs 遵循“触底保持”与“越界就近夹取”；之后维护 atRightEdge。
   * - 新增：缓存 minTs/maxTs 供后续动作判断触底（必要的顺序调整：在落地计算之前先保存边界值）。
   */
  function setDatasetBounds({ minTs, maxTs, totalRows }) {
    // —— 新增顺序说明 —— //
    // 原文件仅设置 allRows；本次为保证 atRightEdge 正确维护，先缓存边界值，再应用触底/越界规则。
    allRows.value = Math.max(0, Number(totalRows || 0));
    minTsRef.value = Number.isFinite(+minTs) ? +minTs : null; // 新增：缓存左端
    maxTsRef.value = Number.isFinite(+maxTs) ? +maxTs : null; // 新增：缓存右端

    // 触底保持：atRightEdge=true 时，自动锚到最新一条
    if (atRightEdge.value && maxTsRef.value != null) {
      rightTs.value = +maxTsRef.value;
    }
    // 越界就近夹取：若 rightTs 超出边界，则夹取到 [minTs,maxTs]
    if (rightTs.value != null) {
      if (minTsRef.value != null && rightTs.value < +minTsRef.value) {
        rightTs.value = +minTsRef.value;
      }
      if (maxTsRef.value != null && rightTs.value > +maxTsRef.value) {
        rightTs.value = +maxTsRef.value;
      }
    }
    // 维护 atRightEdge
    _updateEdgeFlag();

  // MOD: 数据集边界落地后，基于当前 barsCount + totalRows 重算窗宽高亮（由 bars 决定）
  currentPresetKey.value = pickPresetByBarsCountDown(
    currentFreq.value,
    Math.max(1, Number(barsCount.value || 1)),
    Math.max(0, Number(allRows.value || 0))
  );

    // 持久化 + 广播
    _persist();
    _scheduleNotify();
  }

  /**
   * 上报宿主宽度（主窗 resize 时调用）；仅重算 markerWidthPx，不改变 bars/rightTs。
   */
  function setHostWidth(px) {
    hostWidthPx.value = Math.max(1, Number(px || 1));
    _recalcMarkerWidth();
    _scheduleNotify();
  }

  /**
   * 获取当前状态快照（供订阅者使用）
   */
  function getState() {
    // FIX: 在返回的快照中增加 hostWidthPx
    return {
      barsCount: Math.max(1, Number(barsCount.value || 1)),
      rightTs: rightTs.value != null ? Number(rightTs.value) : null,
      markerWidthPx: Math.max(
        1,
        Math.min(16, Number(markerWidthPx.value || 8))
      ),
      atRightEdge: !!atRightEdge.value,
      allRows: Math.max(0, Number(allRows.value || 0)),
      presetKey: String(currentPresetKey.value || "ALL"),
      freq: String(currentFreq.value || "1d"),
      symbol: String(currentSymbol.value || ""),
      hostWidthPx: Math.max(1, Number(hostWidthPx.value || 1)), // FIX: 新增 hostWidthPx
    };
  }

  /**
   * 订阅状态变化（返回订阅ID）；在 2 帧内合并后广播最终值，避免抖动。
   */
  function onChange(cb) {
    const id = _nextSubId++;
    _subs.set(id, typeof cb === "function" ? cb : () => {});
    try {
      cb(getState());
    } catch {}
    return id;
  }

  /**
   * 取消订阅
   */
  function offChange(id) {
    _subs.delete(id);
  }

  // —— 交互指令统一入口（execute） —— //
  // - 枚举完整：ChangeFreq / ChangeWidthPreset / ScrollZoom / Pan / KeyMove / SetBarsManual / SetDatesManual / Refresh / ChangeSymbol / ResizeHost
  // - 每次主动交互：更新状态 → 维护 atRightEdge → 持久化 → 两帧合并广播（只落地最后一次状态）。
  function execute(action, payload = {}) {
    const p = payload || {};
    switch (String(action || "")) {
      case "ChangeFreq": {
        const freqNew = String(p.freq || currentFreq.value || "1d");
        currentFreq.value = freqNew;
        const total = Math.max(0, Number(p.allRows || allRows.value || 0));
        const nextBars =
          currentPresetKey.value === "ALL"
            ? total
            : presetToBars(freqNew, currentPresetKey.value, total);
        barsCount.value = Math.max(1, Number(nextBars || 1));
        // 右端不变；若提供边界则按越界夹取
        if (rightTs.value != null) {
          if (Number.isFinite(+p.minTs) && rightTs.value < +p.minTs)
            rightTs.value = +p.minTs;
          if (Number.isFinite(+p.maxTs) && rightTs.value > +p.maxTs)
            rightTs.value = +p.maxTs;
        }
        // bars>=allRows → 高亮 ALL
        if (total > 0 && barsCount.value >= total) {
          currentPresetKey.value = "ALL";
        }
        _recalcMarkerWidth();
        _updateEdgeFlag(); // 新增：维护 atRightEdge
        _persist();
        _scheduleNotify();
        break;
      }

      case "ChangeWidthPreset": {
        const presetKey = String(p.presetKey || "ALL").toUpperCase();
        currentPresetKey.value = presetKey;
        const total = Math.max(0, Number(p.allRows || allRows.value || 0));
        const nextBars = presetToBars(currentFreq.value, presetKey, total);
        barsCount.value = Math.max(1, Number(nextBars || 1));

        // —— 变更点（满足“点击 ALL 完全覆盖全量”）：当点击 ALL 时，除 bars=ALL 外，还应将 rightTs 主动锚到数据集右端 —— //
        // 说明：若 maxTsRef 已知，则将 rightTs 设为 maxTs，并置 atRightEdge=true，以保证“完全覆盖全量”的语义；
        //       若尚未知（初次加载阶段），保持 rightTs 不变，后续 setDatasetBounds 落地时会触底保持到最右。
        if (presetKey === "ALL") {
          if (Number.isFinite(+maxTsRef.value)) {
            rightTs.value = +maxTsRef.value;
            atRightEdge.value = true;
          }
        } else {
          // 非 ALL：右端不变；若提供边界则按越界夹取（与原语义一致）
        if (rightTs.value != null) {
          if (Number.isFinite(+p.minTs) && rightTs.value < +p.minTs)
            rightTs.value = +p.minTs;
          if (Number.isFinite(+p.maxTs) && rightTs.value > +p.maxTs)
            rightTs.value = +p.maxTs;
        }
        }

        _recalcMarkerWidth();
        _updateEdgeFlag(); // 新增：维护 atRightEdge
        _persist();
        _scheduleNotify();
        break;
      }

      case "ScrollZoom": {
        const nb = Math.max(1, Number(p.nextBars || barsCount.value || 1));
        const rt = Number.isFinite(+p.nextRightTs)
          ? +p.nextRightTs
          : rightTs.value;
        barsCount.value = nb;
        rightTs.value = rt;
        const total = Math.max(0, Number(allRows.value || 0));
        currentPresetKey.value = pickPresetByBarsCountDown(
          currentFreq.value,
          nb,
          total
        );
        _recalcMarkerWidth();
        _updateEdgeFlag(); // 新增：维护 atRightEdge
        _persist();
        _scheduleNotify();
        break;
      }

      case "Pan":
      case "KeyMove": {
        const rt = Number.isFinite(+p.nextRightTs)
          ? +p.nextRightTs
          : rightTs.value;
        rightTs.value = rt;
        // 越界夹取（若集已有边界）
        const minTs = Number.isFinite(+p.minTs) ? +p.minTs : minTsRef.value;
        const maxTs = Number.isFinite(+p.maxTs) ? +p.maxTs : maxTsRef.value;
        if (rightTs.value != null) {
          if (minTs != null && rightTs.value < +minTs) rightTs.value = +minTs;
          if (maxTs != null && rightTs.value > +maxTs) rightTs.value = +maxTs;
        }
        _updateEdgeFlag(); // 新增：维护 atRightEdge
        _persist();
        _scheduleNotify();
        break;
      }

      case "SetBarsManual": {
        const nb = Math.max(1, Number(p.nextBars || barsCount.value || 1));
        barsCount.value = nb;
        const total = Math.max(0, Number(allRows.value || 0));
        currentPresetKey.value = pickPresetByBarsCountDown(
          currentFreq.value,
          nb,
          total
        );
        _recalcMarkerWidth();
        _updateEdgeFlag(); // 新增：维护 atRightEdge（rightTs 未变，此调用不会误改 atRightEdge）
        _persist();
        _scheduleNotify();
        break;
      }

      case "SetDatesManual": {
        const nb = Math.max(1, Number(p.nextBars || barsCount.value || 1));
        const rt = Number.isFinite(+p.nextRightTs)
          ? +p.nextRightTs
          : rightTs.value;
        barsCount.value = nb;
        rightTs.value = rt;
        const total = Math.max(0, Number(allRows.value || 0));
        currentPresetKey.value = pickPresetByBarsCountDown(
          currentFreq.value,
          nb,
          total
        );
        // 越界夹取（若边界给定或已有缓存）
        const minTs = Number.isFinite(+p.minTs) ? +p.minTs : minTsRef.value;
        const maxTs = Number.isFinite(+p.maxTs) ? +p.maxTs : maxTsRef.value;
        if (rightTs.value != null) {
          if (minTs != null && rightTs.value < +minTs) rightTs.value = +minTs;
          if (maxTs != null && rightTs.value > +maxTs) rightTs.value = +maxTs;
        }
        _recalcMarkerWidth();
        _updateEdgeFlag(); // 新增：维护 atRightEdge
        _persist();
        _scheduleNotify();
        break;
      }

      case "Refresh": {
        // bars/rightTs 不变；后端处理后再由 setDatasetBounds 落地触底/越界规则。
        _scheduleNotify();
        break;
      }

      case "ChangeSymbol": {
        const sym = String(p.symbol || "").trim();
        if (sym) {
          currentSymbol.value = sym;
          _updateEdgeFlag(); // 新增：维护 atRightEdge（不改 rightTs，仅确认状态）
          _persist();
          _scheduleNotify();
        }
        break;
      }

      case "ResizeHost": {
        const w = Math.max(1, Number(p.widthPx || hostWidthPx.value || 1));
        hostWidthPx.value = w;
        _recalcMarkerWidth();
        _scheduleNotify();
        break;
      }

      default: {
        // 未知指令：保持静默（不做任何改变）
      }
    }
  }

  // —— 单例导出（保持原字段顺序，与原文件一致） —— //
  _hubSingleton = {
    getState,
    onChange,
    offChange,
    initFromPersist,
    setDatasetBounds,
    setHostWidth,
    execute,
    // 公开 refs 的当前值（满足不变量令牌与订阅者需求）
    barsCount,
    rightTs,
    markerWidthPx,
    atRightEdge,
  };
  return _hubSingleton;
}
