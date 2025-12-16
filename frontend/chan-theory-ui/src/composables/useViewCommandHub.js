// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useViewCommandHub.js
// ==============================
// V5.5 - 视图状态与设置系统统一持久化版
//
// 核心改造：
//   1. 移除对 localStorage 的直接读写，改为调用 useUserSettings.viewState 的 setViewBars/setRightTs，
//      再通过 settings.saveAll() 统一写入 LS_KEY。
//   2. 保留原有 PERSIST_DEBOUNCE_MS 防抖机制，仍然只在拖拽/缩放结束后一小段时间内落盘，
//      避免高频 dataZoom 事件导致频繁 I/O。
//   3. 其余逻辑（barsCount/rightTs 计算、ChangeFreq/ChangeWidthPreset 等）保持不变，
//      以保证与原有行为完美回归（除持久化路径外）。
// ==============================

import { ref, computed } from "vue";
import { useUserSettings } from "@/composables/useUserSettings";
import {
  pickPresetByBarsCountDown,
  presetToBars,
  PERSIST_DEBOUNCE_MS,
  BAR_USABLE_RATIO,
} from "@/constants";

let _hubSingleton = null;

export function useViewCommandHub() {
  if (_hubSingleton) return _hubSingleton;

  const settings = useUserSettings();

  const barsCount = ref(1);
  const rightTs = ref(null);
  const markerWidthPx = ref(8);
  const hostWidthPx = ref(800);
  const allRows = ref(0);
  const currentFreq = ref(settings.preferences.freq || "1d");
  const currentSymbol = ref(settings.preferences.lastSymbol || "");

  const minTsRef = ref(null);
  const maxTsRef = ref(null);

  const _vmRef = { vm: null };

  function findEndIdx(arr, ts) {
    if (!Array.isArray(arr) || !arr.length) return 0;
    if (!Number.isFinite(ts)) return arr.length - 1;

    for (let i = arr.length - 1; i >= 0; i--) {
      const barTs = arr[i]?.ts;
      if (Number.isFinite(barTs) && barTs <= ts) {
        return i;
      }
    }
    return arr.length - 1;
  }

  const leftTs = computed(() => {
    const vm = _vmRef.vm;
    if (!vm) return null;

    const arr = vm.candles.value || [];
    if (!arr.length) return null;

    const endIdx = findEndIdx(arr, rightTs.value);
    const startIdx = Math.max(0, endIdx - barsCount.value + 1);

    return arr[startIdx]?.ts || null;
  });

  const atRightEdge = computed(() => {
    if (!Number.isFinite(rightTs.value) || !Number.isFinite(maxTsRef.value)) {
      return false;
    }
    return rightTs.value === maxTsRef.value;
  });

  const currentPresetKey = computed(() => {
    const bars = barsCount.value;
    const total = allRows.value;

    if (total > 0 && bars >= total) {
      return "ALL";
    }

    return pickPresetByBarsCountDown(currentFreq.value, bars, total);
  });

  const _subs = new Map();
  let _nextSubId = 1;
  let _rafScheduled = false;
  let _rafTickCount = 0;
  let _pendingNotify = false;

  function _recalcMarkerWidth() {
    const b = Math.max(1, Number(barsCount.value || 1));
    const w = Math.max(1, Number(hostWidthPx.value || 1));
    const approx = Math.round((w * BAR_USABLE_RATIO) / b);
    markerWidthPx.value = Math.max(1, Math.min(16, approx));
  }

  let _persistTimer = null;

  /**
   * 立即持久化当前视图状态（使用 useUserSettings.viewState + saveAll）
   * - 仅由 _persistImmediate / _persistDebounced 调用
   * - 避免在高频 dataZoom 处理函数中直接触发
   */
  function _doRealPersist() {
    try {
      const symbol = String(currentSymbol.value || "").trim();
      const freq = String(currentFreq.value || "").trim() || "1d";

      // 使用 viewState 子模块的 API 写入配置
      settings.setViewBars(symbol, freq, barsCount.value);
      settings.setRightTs(symbol, freq, rightTs.value);

      // 统一调用 saveAll，将所有域（preferences/viewState/chartDisplay/chanTheory）一并落盘
      settings.saveAll();
    } catch (e) {
      console.error("[CommandHub] persist failed:", e);
    }
  }

  function _persistImmediate() {
    if (_persistTimer) {
      clearTimeout(_persistTimer);
      _persistTimer = null;
    }
    _doRealPersist();
  }

  function _persistDebounced() {
    if (_persistTimer) clearTimeout(_persistTimer);
    _persistTimer = setTimeout(() => {
      _doRealPersist();
      _persistTimer = null;
    }, PERSIST_DEBOUNCE_MS);
  }

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

  function _broadcast() {
    const snapshot = getState();
    _subs.forEach((cb) => {
      try {
        cb(snapshot);
      } catch {}
    });
  }

  function initFromPersist(code, freq) {
    currentSymbol.value = String(code || "").trim();
    currentFreq.value = String(freq || "").trim() || "1d";

    const savedBars = settings.getViewBars(
      currentSymbol.value,
      currentFreq.value
    );
    const savedTs = settings.getRightTs(currentSymbol.value, currentFreq.value);

    barsCount.value = Math.max(1, Number(savedBars || 1));
    rightTs.value = Number.isFinite(+savedTs) ? +savedTs : null;

    _recalcMarkerWidth();
    _scheduleNotify();
  }

  function setDatasetBounds({ minTs, maxTs, totalRows }) {
    allRows.value = Math.max(0, Number(totalRows || 0));
    minTsRef.value = Number.isFinite(+minTs) ? +minTs : null;
    maxTsRef.value = Number.isFinite(+maxTs) ? +maxTs : null;

    if (atRightEdge.value && maxTsRef.value != null) {
      rightTs.value = +maxTsRef.value;
    }

    if (rightTs.value != null) {
      if (minTsRef.value != null && rightTs.value < +minTsRef.value) {
        rightTs.value = +minTsRef.value;
      }
      if (maxTsRef.value != null && rightTs.value > +maxTsRef.value) {
        rightTs.value = +maxTsRef.value;
      }
    }

    // 数据集边界变化通常是低频事件（换标的/换频率），立即持久化
    _persistImmediate();
    _scheduleNotify();
  }

  function setHostWidth(px) {
    hostWidthPx.value = Math.max(1, Number(px || 1));
    _recalcMarkerWidth();
    _scheduleNotify();
  }

  function setMarketView(vm) {
    _vmRef.vm = vm;
  }

  function getState() {
    return {
      barsCount: Math.max(1, Number(barsCount.value || 1)),
      rightTs: rightTs.value != null ? Number(rightTs.value) : null,
      leftTs: leftTs.value,
      markerWidthPx: Math.max(
        1,
        Math.min(16, Number(markerWidthPx.value || 8))
      ),
      atRightEdge: atRightEdge.value,
      allRows: Math.max(0, Number(allRows.value || 0)),
      presetKey: currentPresetKey.value,
      freq: String(currentFreq.value || "1d"),
      symbol: String(currentSymbol.value || ""),
      hostWidthPx: Math.max(1, Number(hostWidthPx.value || 1)),
    };
  }

  function onChange(cb) {
    const id = _nextSubId++;
    _subs.set(id, typeof cb === "function" ? cb : () => {});
    try {
      cb(getState());
    } catch {}
    return id;
  }

  function offChange(id) {
    _subs.delete(id);
  }

  function execute(action, payload = {}) {
    const p = payload || {};

    switch (String(action || "")) {
      case "SyncViewState": {
        const nextBars = Math.max(1, Number(p.barsCount || barsCount.value));
        const nextTs = Number.isFinite(+p.rightTs) ? +p.rightTs : rightTs.value;

        barsCount.value = nextBars;
        rightTs.value = nextTs;

        _recalcMarkerWidth();
        _persistDebounced();

        if (!p.silent) {
          _scheduleNotify();
        }
        break;
      }

      // ===== 系统2：区间套逻辑（独立实现，不依赖预设）=====
      case "ChangeFreq": {
        const freqOld = String(currentFreq.value || "1d");
        const freqNew = String(p.freq || freqOld);

        if (freqOld === freqNew) {
          _scheduleNotify();
          break;
        }

        // ===== 核心：直接计算时间跨度（不依赖预设）=====
        const barsOld = Math.max(1, Number(barsCount.value || 1));

        // 每日柱数表（交易时段：4小时 = 240分钟）
        const BARS_PER_DAY = {
          "1m": 240,
          "5m": 48,
          "15m": 16,
          "30m": 8,
          "60m": 4,
          "1d": 1,
          "1w": 1 / 5,
          "1M": 1 / 22,
        };

        const barsPerDayOld = BARS_PER_DAY[freqOld] || 1;
        const barsPerDayNew = BARS_PER_DAY[freqNew] || 1;

        // 计算时间跨度（天）
        const timeSpanDays = barsOld / barsPerDayOld;

        // 转换为新频率的 bars
        const barsTheoretical = Math.ceil(timeSpanDays * barsPerDayNew);

        currentFreq.value = freqNew;
        const total = Math.max(0, Number(p.allRows || allRows.value || 0));

        // ===== 边界检查：右端超界 → 自动 ALL =====
        const rightTsCurrent = rightTs.value;
        const maxTsAvailable = maxTsRef.value;

        let barsNew;
        let autoAll = false;

        if (
          Number.isFinite(rightTsCurrent) &&
          Number.isFinite(maxTsAvailable) &&
          rightTsCurrent > maxTsAvailable
        ) {
          barsNew = total;
          rightTs.value = maxTsAvailable;
          autoAll = true;
        } else {
          // ===== 智能收缩：限制在实际数据范围内 =====
          barsNew =
            total > 0 ? Math.min(barsTheoretical, total) : barsTheoretical;

          const shortage = Math.max(0, barsTheoretical - total);

          if (shortage > 0) {
            // 数据不足时的内部提示已移除，仅通过行为体现
          }
        }

        barsCount.value = Math.max(1, barsNew);

        if (rightTs.value != null && !autoAll) {
          if (Number.isFinite(+p.minTs) && rightTs.value < +p.minTs)
            rightTs.value = +p.minTs;
          if (Number.isFinite(+p.maxTs) && rightTs.value > +p.maxTs)
            rightTs.value = +p.maxTs;
        }

        _recalcMarkerWidth();
        _persistImmediate();
        _scheduleNotify();
        break;
      }

      // ===== 系统1：窗宽预设逻辑（保持不变）=====
      case "ChangeWidthPreset": {
        const presetKey = String(p.presetKey || "ALL").toUpperCase();
        const total = Math.max(0, Number(p.allRows || allRows.value || 0));

        const nextBars = presetToBars(currentFreq.value, presetKey, total);
        barsCount.value = Math.max(1, Number(nextBars || 1));

        if (presetKey === "ALL") {
          if (Number.isFinite(+maxTsRef.value)) {
            rightTs.value = +maxTsRef.value;
          }
        } else {
          if (rightTs.value != null) {
            if (Number.isFinite(+p.minTs) && rightTs.value < +p.minTs)
              rightTs.value = +p.minTs;
            if (Number.isFinite(+p.maxTs) && rightTs.value > +p.maxTs)
              rightTs.value = +p.maxTs;
          }
        }

        _recalcMarkerWidth();
        _persistDebounced();
        _scheduleNotify();
        break;
      }

      case "Refresh": {
        _scheduleNotify();
        break;
      }

      case "ChangeSymbol": {
        const sym = String(p.symbol || "").trim();
        if (sym) {
          currentSymbol.value = sym;
          _persistImmediate();
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
        // 未知指令：静默忽略
      }
    }
  }

  _hubSingleton = {
    getState,
    onChange,
    offChange,
    initFromPersist,
    setDatasetBounds,
    setHostWidth,
    setMarketView,
    execute,
    barsCount,
    rightTs,
    markerWidthPx,
    leftTs,
    atRightEdge,
    currentPresetKey,
  };

  return _hubSingleton;
}

let _stateAccessor = null;

export function getCommandState() {
  if (!_stateAccessor) {
    const hub = useViewCommandHub();
    _stateAccessor = () => hub.getState();
  }
  return _stateAccessor();
}
