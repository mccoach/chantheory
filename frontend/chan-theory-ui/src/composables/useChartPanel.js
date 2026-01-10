// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useChartPanel.js
// ==============================
// V8.1 - NEW: ATR breach marker 宽度随缩放变化
//   - 主图 width targets 增加 key=main:atrBreach（percent 来自 chartDisplay.atrBreachSettings.markerPercent）
//   - 主图 refreshSeriesIds 增加 ATR_BREACH_* 四个 series id（受 atrBreachSettings.enabled 控制）
// ==============================

import {
  ref,
  computed,
  onMounted,
  onBeforeUnmount,
  watch,
  nextTick,
} from "vue";
import * as echarts from "echarts";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { useUserSettings } from "@/composables/useUserSettings";

import { createWidthController } from "@/charts/width/widthController";
import {
  FRACTAL_MARKER_WIDTH_PX_LIMITS,
  UPDOWN_MARKER_WIDTH_PX_LIMITS,
  VOL_MARKER_WIDTH_PX_LIMITS,
  ATR_BREACH_MARKER_WIDTH_PX_LIMITS, // NEW
} from "@/constants";
import { COMMON_CHART_LAYOUT } from "@/constants/chartLayout";

function clampInt(n, min, max) {
  const x = Math.round(Number(n));
  if (!Number.isFinite(x)) return min;
  return Math.max(min, Math.min(max, x));
}

export function useChartPanel({ panelKey, vm, hub, renderHub, onChartReady, getPanelKind }) {
  const wrapRef = ref(null);
  const hostRef = ref(null);
  const chart = ref(null);

  const { findBySymbol } = useSymbolIndex();
  const settings = useUserSettings();

  let ro = null;

  let _widthCtl = null;

  function safeResize() {
    if (!chart.value || !hostRef.value) return;
    requestAnimationFrame(() => {
      try {
        chart.value.resize({
          width: hostRef.value.clientWidth,
          height: hostRef.value.clientHeight,
        });
      } catch { }
    });
  }

  function scheduleWidthUpdate() {
    try {
      _widthCtl?.scheduleUpdate();
    } catch { }
  }

  function disposeWidthController() {
    if (!_widthCtl) return;
    try {
      _widthCtl.dispose();
    } catch { }
    _widthCtl = null;
  }

  function buildMainRefreshIdsGetter() {
    return () => {
      const out = [];

      const updownOn =
        (settings?.chanTheory?.chanSettings?.showUpDownMarkers ?? true) === true;
      if (updownOn) out.push("CHAN_UP", "CHAN_DOWN");

      const fr = settings?.chanTheory?.fractalSettings || {};
      const frEnabled = (fr.enabled ?? true) === true;
      if (frEnabled) {
        const sb = fr.styleByStrength || {};
        if ((sb.strong?.enabled ?? true) === true) out.push("FR_TOP_strong", "FR_BOT_strong");
        if ((sb.standard?.enabled ?? true) === true) out.push("FR_TOP_standard", "FR_BOT_standard");
        if ((sb.weak?.enabled ?? true) === true) out.push("FR_TOP_weak", "FR_BOT_weak");

        const cs = fr.confirmStyle || {};
        if ((cs.enabled ?? true) === true) out.push("FR_TOP_CONFIRM", "FR_BOT_CONFIRM");
      }

      // NEW: ATR breach marker series（受 atrBreachSettings.enabled 控制）
      const ab = settings?.chartDisplay?.atrBreachSettings || {};
      const abEnabled = (ab.enabled ?? true) === true;
      if (abEnabled) {
        out.push(
          "ATR_BREACH_FIXED_LONG",
          "ATR_BREACH_FIXED_SHORT",
          "ATR_BREACH_CHAN_LONG",
          "ATR_BREACH_CHAN_SHORT"
        );
      }

      return out;
    };
  }

  function buildVolRefreshIdsGetter() {
    return () => {
      const vs = settings?.chartDisplay?.volSettings || {};
      const pumpOn = (vs.markerPump?.enabled ?? true) === true;
      const dumpOn = (vs.markerDump?.enabled ?? true) === true;

      const out = [];
      if (pumpOn) out.push("VOL_PUMP_MARK");
      if (dumpOn) out.push("VOL_DUMP_MARK");
      return out;
    };
  }

  // NEW: 按 panelKey 读取/写入持久化高度
  function getPanelKeyString() {
    return String(panelKey?.value || panelKey || "").trim();
  }

  function clampHeight(px) {
    const minH = Number(COMMON_CHART_LAYOUT.MIN_HEIGHT_PX || 160);
    const maxH = Number(COMMON_CHART_LAYOUT.MAX_HEIGHT_PX || 800);
    const n = Number(px);
    if (!Number.isFinite(n)) return null;
    return Math.max(minH, Math.min(maxH, n));
  }

  function persistHeightNow(px) {
    const key = getPanelKeyString();
    const h = clampHeight(px);
    if (!key || h == null) return;
    try {
      // useUserSettings 已对 setter 自动 saveAll（非 viewState 方法）
      settings.setPanelHeight(key, Math.round(h));
    } catch { }
  }

  // ==============================
  // 拖拽改高（rAF 合并版）
  // ==============================
  let dragging = false;
  let startY = 0;
  let startH = 0;

  let _resizeRafId = null;
  let _pendingHeightPx = null;
  let _lastAppliedHeightPx = null;

  function _applyPendingHeightOnce() {
    _resizeRafId = null;

    const h0 = Number(_pendingHeightPx);
    _pendingHeightPx = null;

    const h = clampHeight(h0);
    if (h == null || !wrapRef.value) return;

    _lastAppliedHeightPx = h;
    wrapRef.value.style.height = `${Math.floor(h)}px`;

    try {
      chart.value?.resize?.({
        width: hostRef.value?.clientWidth,
        height: hostRef.value?.clientHeight,
      });
    } catch { }
  }

  function _scheduleApplyHeight() {
    if (_resizeRafId != null) return;
    _resizeRafId = requestAnimationFrame(_applyPendingHeightOnce);
  }

  function onResizeHandleMove(e) {
    if (!dragging || !wrapRef.value) return;

    const next = startH + (e.clientY - startY);
    _pendingHeightPx = next;
    _scheduleApplyHeight();
  }

  function onResizeHandleUp() {
    dragging = false;
    window.removeEventListener("mousemove", onResizeHandleMove);

    // 确保最终高度已落地后再持久化（“修改完并生效后立即持久化”）
    if (_pendingHeightPx != null) {
      _scheduleApplyHeight();
    }
    requestAnimationFrame(() => {
      if (_lastAppliedHeightPx != null) {
        persistHeightNow(_lastAppliedHeightPx);
      }
    });
  }

  // FIX: 兼容两种调用签名：
  //   - onResizeHandleDown(event)
  //   - onResizeHandleDown('bottom', event)
  function onResizeHandleDown(posOrEvent, maybeEvent) {
    const e =
      posOrEvent && typeof posOrEvent === "object" && typeof posOrEvent.clientY === "number"
        ? posOrEvent
        : maybeEvent;

    if (!e || typeof e.clientY !== "number") return;

    dragging = true;
    startY = e.clientY;
    startH = wrapRef.value?.clientHeight || 0;

    _pendingHeightPx = null;

    window.addEventListener("mousemove", onResizeHandleMove);
    window.addEventListener("mouseup", onResizeHandleUp, { once: true });
  }

  function resetHeightToDefault() {
    const pk = getPanelKeyString();
    const isMain = pk === "main";

    const defH = isMain
      ? Number(COMMON_CHART_LAYOUT.MAIN_DEFAULT_HEIGHT_PX || 520)
      : Number(COMMON_CHART_LAYOUT.INDICATOR_DEFAULT_HEIGHT_PX || 220);

    const next = clampHeight(defH);
    if (next == null) return;

    _pendingHeightPx = next;
    _scheduleApplyHeight();

    // 双击恢复默认：也要求立即持久化
    requestAnimationFrame(() => {
      if (_lastAppliedHeightPx != null) {
        persistHeightNow(_lastAppliedHeightPx);
      }
    });
  }

  // NEW: dataZoom 交互判定缓存（用于区分平移 vs 缩放）
  // 规则：visCount = eIdx - sIdx + 1
  //   - 若 visCount 未变化 => 平移：不触发任何业务侧 patch（宽度不变）
  //   - 若 visCount 变化   => 缩放：仅触发宽度系统更新（marker 宽度随缩放变化）
  let _lastZoomVisCount = null;

  onMounted(() => {
    // 启动时应用持久化窗高（若存在）
    try {
      const key = getPanelKeyString();
      const saved = settings.getPanelHeight(key);
      const h = clampHeight(saved);
      if (h != null && wrapRef.value) {
        _pendingHeightPx = h;
        _scheduleApplyHeight();
      }
    } catch { }

    if (!hostRef.value) return;

    const instance = echarts.init(hostRef.value, null, {
      renderer: "canvas",
      width: hostRef.value.clientWidth,
      height: hostRef.value.clientHeight,
    });

    instance.group = "ct-sync";
    try {
      echarts.connect("ct-sync");
    } catch { }

    chart.value = instance;

    instance.on("dataZoom", handleDataZoom);

    const pk = getPanelKeyString();
    const isMain = pk === "main";
    const isIndicator = pk.startsWith("indicator:");

    if (isMain) {
      const barPercentReader = () => {
        const bp = settings?.chartDisplay?.klineStyle?.barPercent;
        return clampInt(bp, 10, 100) || 88;
      };

      _widthCtl = createWidthController({
        chart: instance,
        getCandlesLen: () => {
          const arr = vm?.candles?.value || [];
          return Array.isArray(arr) ? arr.length : 0;
        },
        getBarPercent: barPercentReader,
        targets: [
          {
            key: "main:fractal",
            percent: () => settings?.chanTheory?.fractalSettings?.markerPercent,
            minPx: FRACTAL_MARKER_WIDTH_PX_LIMITS.minPx,
            maxPx: FRACTAL_MARKER_WIDTH_PX_LIMITS.maxPx,
            capToBar: true,
          },
          {
            key: "main:updown",
            percent: () => settings?.chanTheory?.chanSettings?.upDownMarkerPercent,
            minPx: UPDOWN_MARKER_WIDTH_PX_LIMITS.minPx,
            maxPx: UPDOWN_MARKER_WIDTH_PX_LIMITS.maxPx,
            capToBar: true,
          },
          // NEW: ATR breach marker（主图 overlay）
          {
            key: "main:atrBreach",
            percent: () => settings?.chartDisplay?.atrBreachSettings?.markerPercent,
            minPx: ATR_BREACH_MARKER_WIDTH_PX_LIMITS.minPx,
            maxPx: ATR_BREACH_MARKER_WIDTH_PX_LIMITS.maxPx,
            capToBar: true,
          },
        ],
        refreshSeriesIds: buildMainRefreshIdsGetter(),
      });
    }

    if (isIndicator) {
      const paneId = pk.slice("indicator:".length);

      const barPercentReader = () => {
        const bp = settings?.chartDisplay?.volSettings?.volBar?.barPercent;
        return clampInt(bp, 10, 100) || 88;
      };

      const markerPercentReader = () => {
        const mp = settings?.chartDisplay?.volSettings?.markerPercent;
        return clampInt(mp, 50, 100) || 90;
      };

      const widthKey = `indicator:${paneId}:volMarker`;

      function isVolKindNow() {
        const k =
          typeof getPanelKind === "function"
            ? String(getPanelKind() || "").toUpperCase()
            : "";
        return k === "VOL" || k === "AMOUNT";
      }

      function ensureIndicatorWidthController() {
        if (!isVolKindNow()) {
          disposeWidthController();
          return;
        }

        if (!_widthCtl) {
          _widthCtl = createWidthController({
            chart: instance,
            getCandlesLen: () => {
              const arr = vm?.candles?.value || [];
              return Array.isArray(arr) ? arr.length : 0;
            },
            getBarPercent: barPercentReader,
            targets: [
              {
                key: widthKey,
                percent: markerPercentReader,
                minPx: VOL_MARKER_WIDTH_PX_LIMITS.minPx,
                maxPx: VOL_MARKER_WIDTH_PX_LIMITS.maxPx,
                capToBar: true,
              },
            ],
            refreshSeriesIds: buildVolRefreshIdsGetter(),
          });
        }
      }

      ensureIndicatorWidthController();

      if (typeof getPanelKind === "function") {
        watch(
          () => String(getPanelKind() || "").toUpperCase(),
          () => {
            ensureIndicatorWidthController();
          }
        );
      }
    }

    try {
      ro = new ResizeObserver(() => {
        safeResize();
        // 容器尺寸变化会影响“每根柱体的像素宽度”，因此需要触发宽度系统刷新（这是缩放以外的必要场景）
        scheduleWidthUpdate();
      });
      ro.observe(hostRef.value);
    } catch { }

    requestAnimationFrame(() => {
      safeResize();
      // 首次落地后计算一次宽度（数据加载后 symbolSize 需有初始值）
      scheduleWidthUpdate();
    });

    if (typeof onChartReady === "function") {
      onChartReady(instance);
    }
  });

  onBeforeUnmount(() => {
    if (_resizeRafId != null) {
      try { cancelAnimationFrame(_resizeRafId); } catch { }
      _resizeRafId = null;
    }
    _pendingHeightPx = null;

    disposeWidthController();

    if (ro) {
      ro.disconnect();
      ro = null;
    }
    if (chart.value) {
      try {
        chart.value.dispose();
      } catch { }
      chart.value = null;
    }
  });

  function handleDataZoom(params) {
    try {
      const info = params?.batch?.[0] || params || {};
      const arr = vm.candles.value || [];
      if (!arr.length) return;

      let sIdx, eIdx;

      if (
        typeof info.startValue !== "undefined" &&
        typeof info.endValue !== "undefined"
      ) {
        sIdx = Number(info.startValue);
        eIdx = Number(info.endValue);
      } else if (typeof info.start === "number" && typeof info.end === "number") {
        const maxIdx = arr.length - 1;
        sIdx = Math.round((info.start / 100) * maxIdx);
        eIdx = Math.round((info.end / 100) * maxIdx);
      } else {
        return;
      }

      if (!Number.isFinite(sIdx) || !Number.isFinite(eIdx)) return;
      if (sIdx > eIdx) [sIdx, eIdx] = [eIdx, sIdx];

      sIdx = Math.max(0, sIdx);
      eIdx = Math.min(arr.length - 1, eIdx);

      const visCount = Math.max(1, eIdx - sIdx + 1);
      const isZoom = _lastZoomVisCount != null && visCount !== _lastZoomVisCount;
      _lastZoomVisCount = visCount;

      try {
        _widthCtl?.setZoomRange?.({ sIdx, eIdx });
      } catch { }

      // ===== 核心策略（按需求）=====
      // 平移（visCount不变）：不触发任何业务侧 patch（宽度不变）
      // 缩放（visCount变化）：仅触发宽度系统更新（marker宽度随缩放变化）
      if (isZoom) {
        scheduleWidthUpdate();
      }

      const bars_new = visCount;
      const anchorTs = arr[eIdx]?.ts;

      if (!Number.isFinite(anchorTs)) return;

      // 视图状态仍记录与持久化（用于 UI 与恢复历史视图）
      hub.execute("SyncViewState", {
        barsCount: visCount,
        rightTs: anchorTs,
      });
    } catch { }
  }

  const onMouseEnter = () => renderHub.setHoveredPanel(panelKey.value);
  const onMouseLeave = () => renderHub.setHoveredPanel(null);

  const displayHeader = ref({ name: "", code: "", freq: "" });
  const displayTitle = computed(() => {
    const n = displayHeader.value.name || "",
      c = displayHeader.value.code || vm.code.value || "",
      f = displayHeader.value.freq || vm.freq.value || "";
    const src = (vm.meta.value?.source || "").trim(),
      srcLabel = src ? `（${src}）` : "";
    const adjText =
      { none: "", qfq: " 前复权", hfq: " 后复权" }[
      String(vm.adjust.value || "none")
      ] || "";
    return n
      ? `${n}（${c}）：${f}${srcLabel}${adjText}`
      : `${c}：${f}${srcLabel}${adjText}`;
  });

  function updateHeaderFromCurrent() {
    const sym = (vm.meta.value?.symbol || vm.code.value || "").trim();
    const frq = String(vm.meta.value?.freq || vm.freq.value || "").trim();
    let name = "";
    try {
      name = findBySymbol(sym)?.name?.trim() || "";
    } catch { }
    displayHeader.value = { name, code: sym, freq: frq };
  }

  watch(
    () => vm.meta.value,
    () => {
      nextTick().then(updateHeaderFromCurrent);
    },
    { deep: true, immediate: true }
  );

  return {
    wrapRef,
    hostRef,
    chart,
    displayTitle,
    onResizeHandleDown,
    resetHeightToDefault,
    onMouseEnter,
    onMouseLeave,
    scheduleWidthUpdate,
  };
}
