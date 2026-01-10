// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\composables\viewRenderHub\renderPipeline.js
// ==============================
// 渲染流水线（原 useViewRenderHub 中的核心 compute/publish 逻辑迁移）
//
// 职责：
// - 监听 vm.candles/indicators/meta 与 indicatorPanes 变化，生成主图与副图 option 快照并发布；
// - 维持批处理执行（_executeBatch）语义；
// - 提供 requestRender（rAF 合并）供实例侧最小 patch 对齐；
// - 主图 overlay（Chan overlays + ATR breach overlay）只在此路径生成（单一路径原则）。
//
// V4.0 - 阶段2：设置保存 FULL/PATCH 分流（intent=settings_apply）
// 规则：
//   - SettingsShell 已完成 baseline diff 与 FULL/PATCH 决策；RenderHub 只负责执行。
//   - 单队列：所有业务写图表动作串行化（full/patch 不交错），杜绝竞态。
//   - 每实例单次提交：同一批次对主图最多 setOption 一次（series patch 合并）。
//   - 未实现的 patch facet/kind：自动升级 FULL（正确性优先）。
// ==============================

import { watch, nextTick } from "vue";
import { getCommandState, useViewCommandHub } from "@/composables/useViewCommandHub";
import { useUserSettings } from "@/composables/useUserSettings";
import { useSymbolIndex } from "@/composables/useSymbolIndex";
import { chartBuilderRegistry } from "@/charts/builderRegistry";
import { createFixedTooltipPositioner } from "@/charts/options";
import { CHAN_DEFAULTS } from "@/constants";

import { createTsArrMemo } from "./range/tsArrMemo";
import { calcVisibleRangeByRightTsBars } from "./range/rangeCalc";
import { buildMergedGDByOrigIdx } from "./chanEngine/mergedGD";
import { createChanCacheEngine } from "./chanEngine/chanCache";
import { buildChanOverlaySeries } from "./mainOverlay/chanOverlay";
import { buildAtrStopBreachSeries } from "./mainOverlay/atrBreachOverlay";

export function createRenderPipeline({ state, registry }) {
  const settings = useUserSettings();
  const symbolIndex = useSymbolIndex();
  state.settings = settings;
  state.symbolIndex = symbolIndex;

  const tsMemo = createTsArrMemo();
  const chanEngine = createChanCacheEngine({ settings, symbolIndex });

  function getTipPositioner() {
    if (state.tipMode.value === "fixed") return createFixedTooltipPositioner("left");
    return undefined;
  }

  function publish(snapshot) {
    state.lastSnapshot.value = snapshot;
    state.subs.forEach((cb) => {
      try {
        cb(snapshot);
      } catch {}
    });
  }

  function onRender(cb) {
    const id = state.nextSubId++;
    state.subs.set(id, typeof cb === "function" ? cb : () => {});
    if (state.lastSnapshot.value) cb(state.lastSnapshot.value);
    return id;
  }

  function offRender(id) {
    state.subs.delete(id);
  }

  async function getIndicatorOption(kind, ui) {
    const vm = state.vmRef.vm;
    if (!vm) return null;

    const key = String(kind || "").toUpperCase();
    const builder = await chartBuilderRegistry.get(key);
    if (!builder) return null;

    const commonParams = {
      candles: vm.candles.value,
      indicators: vm.indicators.value,
      freq: vm.freq.value,
    };

    if (key === "VOL" || key === "AMOUNT") {
      const volCfg = settings.chartDisplay.volSettings || {};
      const finalVolCfg = { ...volCfg, mode: key === "AMOUNT" ? "amount" : "vol" };
      return builder({ ...commonParams, volCfg: finalVolCfg }, ui);
    }

    if (key === "MACD") {
      const macdCfg = settings.chartDisplay.macdSettings || {};
      return builder({ ...commonParams, macdCfg }, ui);
    }

    if (key === "KDJ") return builder({ ...commonParams, useKDJ: true }, ui);
    if (key === "RSI") return builder({ ...commonParams, useRSI: true }, ui);

    return builder(commonParams, ui);
  }

  async function buildIndicatorOptions(context) {
    const { initialRange, tipPositioner, hoveredKey } = context;
    const indicatorOptions = {};

    for (const pane of state.indicatorPanes.value) {
      if (!pane || !pane.id || pane.kind === "OFF") continue;
      const paneKey = `indicator:${pane.id}`;

      try {
        const kind = String(pane.kind || "").toUpperCase();

        const ui =
          kind === "VOL" || kind === "AMOUNT"
            ? {
                initialRange,
                tooltipPositioner: tipPositioner,
                isHovered: hoveredKey === paneKey,
                paneId: pane.id,
              }
            : {
                initialRange,
                tooltipPositioner: tipPositioner,
                isHovered: hoveredKey === paneKey,
              };

        const option = await getIndicatorOption(pane.kind, ui);
        if (option) indicatorOptions[pane.id] = option;
      } catch {}
    }

    return indicatorOptions;
  }

  async function buildMainOption(vm, chanCache, context) {
    const { initialRange, tipPositioner, hoveredKey, st, bars, mergedGDByOrigIdx } = context;

    const buildMain = await chartBuilderRegistry.get("MAIN");
    if (!buildMain) return { series: [] };

    const anyMarkers =
      (settings.chanTheory.chanSettings.showUpDownMarkers ?? true) &&
      chanCache?.reduced?.length > 0;

    const markerHeight = Number(CHAN_DEFAULTS.markerHeightPx);
    const markerYOffset = Number(CHAN_DEFAULTS.markerYOffsetPx);
    const offsetDownPx = markerHeight + markerYOffset;

    const baseMainOption = buildMain(
      {
        candles: vm.candles.value,
        indicators: vm.indicators.value,
        chartType: vm.chartType.value,
        maConfigs: settings.chartDisplay.maConfigs,
        freq: vm.freq.value,
        klineStyle: settings.chartDisplay.klineStyle,
        adjust: vm.adjust.value,
        reducedBars: chanCache.reduced,
        mapOrigToReduced: chanCache.map,
        anchorPolicy: settings.chanTheory.chanSettings.anchorPolicy,
        mergedGDByOrigIdx,
        atrStopSettings: settings.chartDisplay.atrStopSettings,
        atrBasePrice: settings.preferences.atrBasePrice,
      },
      {
        initialRange,
        tooltipPositioner: tipPositioner,
        isHovered: hoveredKey === "main",
        mainAxisLabelSpacePx: 28,
        xAxisLabelMargin: anyMarkers ? offsetDownPx + 12 : 12,
        mainBottomExtraPx: anyMarkers ? offsetDownPx : 0,
      }
    );

    const overlaySeries = buildChanOverlaySeries({
      settings,
      chanCache,
      candles: vm.candles.value,
      hostW: st.hostWidthPx,
      visCount: bars,
    });

    const atrBreachSeries = buildAtrStopBreachSeries({
      candles: vm.candles.value,
      indicators: vm.indicators.value,
      atrStopSettings: settings.chartDisplay.atrStopSettings,
      atrBreachSettings: settings.chartDisplay.atrBreachSettings,
    });

    return {
      ...baseMainOption,
      series: [...(baseMainOption.series || []), ...overlaySeries, ...atrBreachSeries],
    };
  }

  async function computeAndPublish() {
    const vm = state.vmRef.vm;
    if (!vm) return;

    const candles = vm.candles.value;
    const len = Array.isArray(candles) ? candles.length : 0;

    const st = getCommandState();
    const bars = Math.max(1, Number(st.barsCount || 1));

    const tsArr = tsMemo.getTsArr(candles);
    const { sIdx, eIdx } = calcVisibleRangeByRightTsBars({
      candlesLen: len,
      tsArr,
      rightTs: st.rightTs,
      bars,
    });

    const chanCache = chanEngine.calculateChanStructures(candles);
    state.chanCache.value = chanCache;

    const mergedGDByOrigIdx = buildMergedGDByOrigIdx({
      candles,
      reducedBars: chanCache?.reduced,
      mapOrigToReduced: chanCache?.map,
    });

    const context = {
      initialRange: { startValue: sIdx, endValue: eIdx },
      tipPositioner: getTipPositioner(),
      hoveredKey: state.hoveredPanelKey.value,
      st,
      bars,
      mergedGDByOrigIdx,
    };

    const mainOption = await buildMainOption(vm, chanCache, context);
    const indicatorOptions = await buildIndicatorOptions(context);

    const snapshot = {
      seq: ++state.renderSeq,
      core: {
        code: vm.code.value,
        freq: vm.freq.value,
        adjust: vm.adjust.value,
        barsCount: bars,
        rightTs: st.rightTs,
        leftTs: st.leftTs,
        sIdx,
        eIdx,
        allRows: len,
        atRightEdge: !!st.atRightEdge,
        hoveredPanelKey: context.hoveredKey,
      },
      main: {
        option: mainOption,
        range: context.initialRange,
      },
      indicatorOptions,
      metaLink: {
        generated_at: vm.meta.value?.generated_at || "",
        source: vm.meta.value?.source || "",
        downsample_from: vm.meta.value?.downsample_from || null,
      },
    };

    publish(snapshot);
  }

  async function executeBatch(asyncTask) {
    state.batchFlag.value = true;
    state.pendingCompute.value = false;

    try {
      await asyncTask();
    } finally {
      state.batchFlag.value = false;

      if (state.pendingCompute.value) {
        await nextTick();
        computeAndPublish();
      }
    }
  }

  // ==============================
  // 单队列（业务写入串行化）
  // ==============================
  let _queue = Promise.resolve();

  function enqueue(job) {
    _queue = _queue.then(() => Promise.resolve(job()).catch(() => {}));
    return _queue;
  }

  // ==============================
  // PATCH 执行器（阶段2首批：atr param/style + display style）
  // ==============================

  const ATR_SERIES_IDS = [
    "ATR_FIXED_LONG",
    "ATR_FIXED_SHORT",
    "ATR_CHAN_LONG",
    "ATR_CHAN_SHORT",
  ];
  const ATR_BREACH_SERIES_IDS = [
    "ATR_BREACH_FIXED_LONG",
    "ATR_BREACH_FIXED_SHORT",
    "ATR_BREACH_CHAN_LONG",
    "ATR_BREACH_CHAN_SHORT",
  ];

  // 用于等待 indicators 更新（param patch）
  let _lastPatchedIndicatorsRef = null;

  function buildMainSeriesPatchForAtr({ needParam, needStyle } = {}) {
    const vm = state.vmRef.vm;
    if (!vm) return { ready: false, series: [] };

    const inds = vm.indicators.value;

    // param：必须等 indicators ref 变化（代表 computeIndicators 已完成）
    if (needParam) {
      if (inds === _lastPatchedIndicatorsRef) {
        return { ready: false, series: [] };
      }
    }

    const series = [];

    // ATR_stop 数据/样式
    const s = settings.chartDisplay.atrStopSettings || {};
    const fixedLong = s.fixed?.long || {};
    const fixedShort = s.fixed?.short || {};
    const chanLong = s.chandelier?.long || {};
    const chanShort = s.chandelier?.short || {};

    const styleMap = {
      ATR_FIXED_LONG: fixedLong,
      ATR_FIXED_SHORT: fixedShort,
      ATR_CHAN_LONG: chanLong,
      ATR_CHAN_SHORT: chanShort,
    };

    for (const id of ATR_SERIES_IDS) {
      const patch = { id };

      if (needParam) {
        patch.data = Array.isArray(inds?.[id]) ? inds[id] : [];
      }

      if (needStyle) {
        const cfg = styleMap[id] || {};
        patch.lineStyle = {
          width: Number(cfg.lineWidth),
          type: String(cfg.lineStyle || "solid"),
          color: String(cfg.color || "#fff"),
        };
        patch.itemStyle = { color: String(cfg.color || "#fff") };
        patch.color = String(cfg.color || "#fff");
      }

      series.push(patch);
    }

    // breach series：param 变更时数据也会变；style 变更时 symbol/itemStyle 变
    const breachSeries = buildAtrStopBreachSeries({
      candles: vm.candles.value,
      indicators: inds,
      atrStopSettings: settings.chartDisplay.atrStopSettings,
      atrBreachSettings: settings.chartDisplay.atrBreachSettings,
    });

    const byId = new Map();
    for (const ss of breachSeries || []) {
      const id = String(ss?.id || "");
      if (id) byId.set(id, ss);
    }

    for (const id of ATR_BREACH_SERIES_IDS) {
      const s2 = byId.get(id);
      if (s2) {
        // s2 已包含 data/symbol/itemStyle/symbolRotate 等必要字段
        series.push(s2);
      } else {
        // 不显示时清空数据，避免残留
        series.push({ id, data: [] });
      }
    }

    if (needParam) {
      _lastPatchedIndicatorsRef = inds;
    }

    return { ready: true, series };
  }

  function buildMainSeriesPatchForMaStyle() {
    const ma = settings.chartDisplay.maConfigs || {};
    const series = [];

    for (const [key, conf] of Object.entries(ma)) {
      if (!conf) continue;

      // buildMainChartOption 中 MA series 的 id 使用 key（MA5/MA10...）
      const id = String(key);
      const color = String(conf.color || "#fff");
      const width = Number(conf.width ?? 1);
      const style = String(conf.style || "solid");

      series.push({
        id,
        lineStyle: { width, type: style, color },
        itemStyle: { color },
        color,
      });
    }

    return series;
  }

  async function applyPatchPlan(patchPlan) {
    const vm = state.vmRef.vm;
    if (!vm) return;

    const chart = registry.getChart("main");
    if (!chart) return;

    const plan = patchPlan && typeof patchPlan === "object" ? patchPlan : {};

    // 阶段2支持的 patch 范围（不在此范围内 => FULL，已在调用侧保证）
    const needAtrParam = Array.isArray(plan.atr) && plan.atr.includes("param");
    const needAtrStyle = Array.isArray(plan.atr) && plan.atr.includes("style");
    const needDispStyle = Array.isArray(plan.display) && plan.display.includes("style");

    const allSeriesPatch = [];

    if (needAtrParam || needAtrStyle) {
      const { ready, series } = buildMainSeriesPatchForAtr({
        needParam: needAtrParam,
        needStyle: needAtrStyle,
      });

      if (!ready) {
        // indicators 未更新：等待下一帧再试（由 requestRender 重新触发）
        return { done: false };
      }

      allSeriesPatch.push(...series);
    }

    if (needDispStyle) {
      allSeriesPatch.push(...buildMainSeriesPatchForMaStyle());
    }

    if (!allSeriesPatch.length) {
      return { done: true };
    }

    // 每实例单次提交：合并为一次 setOption
    try {
      chart.setOption({ series: allSeriesPatch }, { notMerge: false, silent: true });
    } catch {}

    return { done: true };
  }

  // ==============================
  // requestRender（rAF 合并）+ intent 分流
  // ==============================
  let requestRenderRaf = null;
  let _pending = null;

  function requestRender(payload = {}) {
    // 只接受两类：默认（对齐/全量）与 settings_apply（外部已决策）
    const p = payload && typeof payload === "object" ? payload : {};
    _pending = p;

    if (requestRenderRaf != null) return;

    requestRenderRaf = requestAnimationFrame(() => {
      requestRenderRaf = null;

      const req = _pending;
      _pending = null;

      enqueue(async () => {
        // settings_apply：严格按 mode 执行
        if (req?.intent === "settings_apply") {
          const mode = String(req?.mode || "full");

          if (mode === "full") {
            await computeAndPublish();
            return;
          }

          if (mode === "patch") {
            const patchPlan = req?.patchPlan || {};
            const supportedFacets = new Set(["atr", "display"]);
            for (const k of Object.keys(patchPlan || {})) {
              if (!supportedFacets.has(k)) {
                // 未支持 facet => 正确性优先：升级 FULL
                await computeAndPublish();
                return;
              }
            }

            const done = await applyPatchPlan(patchPlan);

            // 未完成（等待 indicators 更新）=> 重新排队一次 patch（下一帧）
            if (done && done.done === false) {
              requestRender({ intent: "settings_apply", mode: "patch", patchPlan });
            }
            return;
          }

          await computeAndPublish();
          return;
        }

        // 默认行为：full 对齐（保持原语义）
        await computeAndPublish();
      });
    });
  }

  function setIndicatorPanes(panes) {
    state.indicatorPanes.value = Array.isArray(panes) ? [...panes] : [];
  }

  function setMarketView(vm) {
    state.vmRef.vm = vm;

    const hub = useViewCommandHub();
    hub.setMarketView(vm);

    watch(
      () => [
        vm.candles.value,
        vm.indicators.value,
        vm.meta.value,
        state.indicatorPanes.value,
      ],
      () => {
        if (state.batchFlag.value) {
          state.pendingCompute.value = true;
          return;
        }
        computeAndPublish();
      }
    );
  }

  return {
    setMarketView,
    onRender,
    offRender,

    getTipPositioner,

    setIndicatorPanes,

    requestRender,
    executeBatch,

    computeAndPublish,
  };
}
