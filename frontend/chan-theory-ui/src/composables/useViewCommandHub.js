// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useViewCommandHub.js
// ==============================
// V5.6 - 清理 markerWidthPx/hostWidthPx 旧宽度体系（去冗余）
//
// 本轮修复（tooltip 基点持久化）：
//   - 新增 tipTs：最后一次“显示 tooltip”的 bar.ts（独立于 rightTs 窗口锚点）
//   - 唯一写入语义：由图表 showTip 事件触发 SyncTipTs（立即持久化）
//   - 键盘左右移动只读取 tipTs 作为基点（映射到 idx），并通过 showTip 推进，
//     持久化仍由 showTip 监听完成，保证单入口。
// ==============================

import { ref, computed } from "vue";
import { useUserSettings } from "@/composables/useUserSettings";
import {
  pickPresetByBarsCountDown,
  presetToBars,
  PERSIST_DEBOUNCE_MS,
} from "@/constants";

let _hubSingleton = null;

export function useViewCommandHub() {
  if (_hubSingleton) return _hubSingleton;

  const settings = useUserSettings();

  const barsCount = ref(1);
  const rightTs = ref(null);

  // NEW: 最后一次显示 tooltip 的 bar.ts（键盘移动基点）
  const tipTs = ref(null);

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

  let _persistTimer = null;

  function _doRealPersist() {
    try {
      const symbol = String(currentSymbol.value || "").trim();
      const freq = String(currentFreq.value || "").trim() || "1d";

      // 窗口锚点（原语义）
      settings.setViewBars(symbol, freq, barsCount.value);
      settings.setRightTs(symbol, freq, rightTs.value);

      // tooltip 基点（新语义，独立于窗口锚点）
      settings.setTipTs(symbol, freq, tipTs.value);

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

    const savedTipTs = settings.getTipTs(currentSymbol.value, currentFreq.value);

    barsCount.value = Math.max(1, Number(savedBars || 1));
    rightTs.value = Number.isFinite(+savedTs) ? +savedTs : null;
    tipTs.value = Number.isFinite(+savedTipTs) ? +savedTipTs : null;

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

    // tipTs 只做边界钳制（不主动改语义）
    if (tipTs.value != null) {
      if (minTsRef.value != null && tipTs.value < +minTsRef.value) tipTs.value = +minTsRef.value;
      if (maxTsRef.value != null && tipTs.value > +maxTsRef.value) tipTs.value = +maxTsRef.value;
    }

    _persistImmediate();
    _scheduleNotify();
  }

  function setMarketView(vm) {
    _vmRef.vm = vm;
  }

  function getState() {
    return {
      barsCount: Math.max(1, Number(barsCount.value || 1)),
      rightTs: rightTs.value != null ? Number(rightTs.value) : null,
      tipTs: tipTs.value != null ? Number(tipTs.value) : null,
      leftTs: leftTs.value,
      atRightEdge: atRightEdge.value,
      allRows: Math.max(0, Number(allRows.value || 0)),
      presetKey: currentPresetKey.value,
      freq: String(currentFreq.value || "1d"),
      symbol: String(currentSymbol.value || ""),
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

        _persistDebounced();

        if (!p.silent) {
          _scheduleNotify();
        }
        break;
      }

      // NEW: tooltip 基点同步（唯一语义入口：由 chart 的 showTip 事件驱动）
      case "SyncTipTs": {
        const next = Number.isFinite(+p.tipTs) ? +p.tipTs : null;
        if (next == null) break;

        let v = next;
        if (minTsRef.value != null && v < +minTsRef.value) v = +minTsRef.value;
        if (maxTsRef.value != null && v > +maxTsRef.value) v = +maxTsRef.value;

        if (tipTs.value != null && Number(tipTs.value) === Number(v)) break;

        tipTs.value = v;

        // 你要求：只要显示了 tooltip 的 bar，就立即持久化
        _persistImmediate();

        if (!p.silent) {
          _scheduleNotify();
        }
        break;
      }

      case "ChangeFreq": {
        const freqOld = String(currentFreq.value || "1d");
        const freqNew = String(p.freq || freqOld);

        if (freqOld === freqNew) {
          _scheduleNotify();
          break;
        }

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
          barsNew =
            total > 0 ? Math.min(barsTheoretical, total) : barsTheoretical;
        }

        barsCount.value = Math.max(1, barsNew);

        if (rightTs.value != null && !autoAll) {
          if (Number.isFinite(+p.minTs) && rightTs.value < +p.minTs)
            rightTs.value = +p.minTs;
          if (Number.isFinite(+p.maxTs) && rightTs.value > +p.maxTs)
            rightTs.value = +p.maxTs;
        }

        // tipTs 不改变语义，仅钳制
        if (tipTs.value != null) {
          if (minTsRef.value != null && tipTs.value < +minTsRef.value) tipTs.value = +minTsRef.value;
          if (maxTsRef.value != null && tipTs.value > +maxTsRef.value) tipTs.value = +maxTsRef.value;
        }

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
    setMarketView,
    execute,
    barsCount,
    rightTs,
    tipTs,
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
