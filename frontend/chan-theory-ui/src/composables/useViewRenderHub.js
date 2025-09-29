// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\useViewRenderHub.js
// ==============================
// 说明：统一渲染快照中枢（上游唯一源头）
// - 责任：一次性计算并发布所有窗体所需的渲染参数（统一离散范围 sIdx/eIdx、markerWidthPx、主窗/量窗 option）。
// - 下游：主窗/量窗/技术窗一次订阅一次渲染（不再分散监听 meta/事件、不再使用 zoomSync �� chan:marker-size）。
// - 触发：hub.onChange（两帧合并后的最终态）与 vm 数据落地（candles/indicators/meta）。
// ==============================

import { ref, watch } from "vue";
import { useViewCommandHub } from "@/composables/useViewCommandHub";
import { useUserSettings } from "@/composables/useUserSettings";
import {
  buildMainChartOption,
  buildVolumeOption,
  buildMacdOption,
  buildKdjOrRsiOption,
  createFixedTooltipPositioner,        // MOD: 引入固定定位器
} from "@/charts/options";

let _singleton = null;

export function useViewRenderHub() {
  if (_singleton) return _singleton;

  const hub = useViewCommandHub();
  const settings = useUserSettings();

  // 上游数据句柄（由 App 注入）
  const _vmRef = { vm: null };

  // 订阅者
  const _subs = new Map();
  let _nextId = 1;

  // 最近一次快照与序号
  const _lastSnapshot = ref(null);
  let _renderSeq = 0;

  // MOD: 统一 tooltip 模式（ fixed | follow ），默认固定；提供全局事件切换
  const tipMode = ref("follow"); // 默认固定（与现实现一致）
  try {
    window.addEventListener("chan:set-tooltip-mode", (e) => {
      const m = String(e?.detail?.mode || "").toLowerCase();
      tipMode.value = m === "follow" ? "follow" : "fixed";
      // 可选：立即推送一次快照，促使各窗重绘（避免等待下一次中枢状态变化）
      try { _computeAndPublish(); } catch {}
    });
  } catch {}

  // 统一获取定位器：fixed → 返回固定器；follow → 返回 undefined（让 ECharts 跟随鼠标）
  function _getTipPositioner() {
    if (tipMode.value === "fixed") return createFixedTooltipPositioner("left");
    return undefined; // 不设 position 即默认跟随鼠标
  }

  function setMarketView(vm) {
    _vmRef.vm = vm;
    // 订阅数据变更以触发统一计算
    watch(
      () => [vm.candles.value, vm.indicators.value, vm.meta.value],
      () => {
        _computeAndPublish();
      },
      { deep: true }
    );
  }

  function onRender(cb) {
    const id = _nextId++;
    _subs.set(id, typeof cb === "function" ? cb : () => {});
    // 初次订阅时若已有快照，立即推送一次
    try {
      if (_lastSnapshot.value) cb(_lastSnapshot.value);
    } catch {}
    return id;
  }

  function offRender(id) {
    _subs.delete(id);
  }

  function _publish(snapshot) {
    _lastSnapshot.value = snapshot;
    _subs.forEach((cb) => {
      try {
        cb(snapshot);
      } catch {}
    });
  }

  function _computeAndPublish() {
    const vm = _vmRef.vm;
    if (!vm) return;

    const candles = vm.candles.value || [];
    const indicators = vm.indicators.value || {};
    const freq = vm.freq.value || "1d";

    const len = candles.length;
    if (!len) return;

    // 统一离散范围（基于 hub 快照：barsCount + rightTs）
    const st = hub.getState();
    const bars = Math.max(1, Number(st.barsCount || 1));
    const tsArr = candles.map((d) => {
      try {
        return Date.parse(d.t);
      } catch {
        return NaN;
      }
    });

    let eIdx = len - 1;
    if (Number.isFinite(st.rightTs)) {
      for (let i = len - 1; i >= 0; i--) {
        const tsv = tsArr[i];
        if (Number.isFinite(tsv) && tsv <= st.rightTs) {
          eIdx = i;
          break;
        }
      }
    }
    let sIdx = Math.max(0, eIdx - bars + 1);
    if (sIdx === 0 && eIdx - sIdx + 1 < bars) {
      eIdx = Math.min(len - 1, bars - 1);
    }

    const initialRange = { startValue: sIdx, endValue: eIdx };
    const markerW = st.markerWidthPx; // 统一来源：hub 派生宽度

    // MOD: 统一生成定位器（fixed or follow）
    const tipPositioner = _getTipPositioner();

    // 主窗 option（上游统一位置源写入）
    const mainOption = buildMainChartOption(
      {
        candles,
        indicators,
        chartType: vm.chartType.value || "kline",
        maConfigs: settings.maConfigs.value,
        freq,
        klineStyle: settings.klineStyle.value,
        adjust: vm.adjust.value || "none",
        // CHAN 数据由主窗内现有 computeInclude/computeFractals 继续处理，保持最小改动
        reducedBars: [],
        mapOrigToReduced: [],
      },
      {
        initialRange,
        tooltipPositioner: tipPositioner,       // MOD: 统一注入定位器
      }
    );

    // 构建量窗 option（一次；统一 overrideMarkWidth）
    const volumeOption = buildVolumeOption(
      {
        candles,
        indicators,
        freq,
        volCfg: settings.volSettings.value,
        volEnv: {
          hostWidth: 0, // 由 ECharts 计算，保持 0；真实宽度不影响 initialRange
          visCount: bars,
          overrideMarkWidth: markerW,
        },
      },
      {
        initialRange,
        tooltipPositioner: tipPositioner,       // MOD: 统一注入定位器
      }
    );

    // 构建默认指标窗（提供工具方法获取具体 kind 的 option；此处留空由 IndicatorPanel 请求）
    const dataForIndicators = { candles, indicators, freq, initialRange };

    const snapshot = {
      seq: ++_renderSeq,
      core: {
        code: vm.code.value || "",
        freq,
        adjust: vm.adjust.value || "none",
        barsCount: bars,
        rightTs: st.rightTs,
        sIdx,
        eIdx,
        allRows: len,
        atRightEdge: !!st.atRightEdge,
        markerWidthPx: markerW,
      },
      main: { option: mainOption, range: initialRange },
      volume: { option: volumeOption, range: initialRange },
      indicatorsBase: dataForIndicators,
      metaLink: {
        generated_at: vm.meta.value?.generated_at || "",
        source: vm.meta.value?.source || "",
        downsample_from: vm.meta.value?.downsample_from || null,
      },
    };

    _publish(snapshot);
  }

  // 订阅 hub 的两帧合并广播，统一触发一次计算
  hub.onChange(() => {
    _computeAndPublish();
  });

  function getIndicatorOption(kind) {
    const base = _lastSnapshot.value?.indicatorsBase;
    if (!base) return null;

    // MOD: 指标窗也复用同一定位器
    const tipPositioner = _getTipPositioner();
    const ui = { initialRange: base.initialRange, tooltipPositioner: tipPositioner };

    const K = String(kind || "").toUpperCase();
    if (K === "MACD") {
      return buildMacdOption({ candles: base.candles, indicators: base.indicators, freq: base.freq }, ui);
    }
    if (K === "KDJ") {
      return buildKdjOrRsiOption({ candles: base.candles, indicators: base.indicators, freq: base.freq, useKDJ: true, useRSI: false }, ui);
    }
    if (K === "RSI") {
      return buildKdjOrRsiOption({ candles: base.candles, indicators: base.indicators, freq: base.freq, useKDJ: false, useRSI: true }, ui);
    }
    if (K === "BOLL") {
      return buildKdjOrRsiOption({ candles: base.candles, indicators: base.indicators, freq: base.freq, useKDJ: false, useRSI: true }, ui);
    }
    return buildMacdOption({ candles: base.candles, indicators: base.indicators, freq: base.freq }, ui);
  }

  // 新增：暴露统一源头的 tooltip 位置获取（供主窗订阅使用）
  function getTipPositioner() {
    return _getTipPositioner();
  }

  _singleton = {
    setMarketView,
    onRender,
    offRender,
    getIndicatorOption,
    getTipPositioner,
  };
  return _singleton;
}
