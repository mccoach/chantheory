// E:\AppProject\ChanTheory\frontend\chan-theory-ui\src\charts\chan\layers\pivots.js
// ==============================
// 缠论图层：笔中枢 (Pen Pivots)
// - 从 layers.js 拆分而来。
// - 核心职责：将笔中枢数据转换为ECharts的标记区域（markArea）和边框线系列。
// ==============================
import { CHAN_PEN_PIVOT_DEFAULTS } from "@/constants";
import { useUserSettings } from "@/composables/useUserSettings";
import { hexToRgba } from "@/utils/colorUtils";
import { sampleSeriesByBarriers } from "./sampler"; // NEW

/**
 * 笔中枢矩形绘制（markArea + markLine 四边）
 * - 每个中枢使用一个独立 series 以便设置独立颜色与 z。
 * - 边框颜色与填充颜色一致，填充透明度按 alphaPercent。
 * - buildPenPivotAreas 改为“静态框线”绘制（保留 markArea 填充；新增四条边以 line series 绘制）。
 */
export function buildPenPivotAreas(pivots, env = {}) {
  const settings = useUserSettings();
  const pvCfg = Object.assign(
    {},
    CHAN_PEN_PIVOT_DEFAULTS,
    (settings.chanTheory &&
      settings.chanTheory.chanSettings &&
      settings.chanTheory.chanSettings.penPivot) ||
      {}
  );
  if (!(pvCfg.enabled ?? true)) return { series: [] };

  const z = Number.isFinite(+pvCfg.z) ? +pvCfg.z : CHAN_PEN_PIVOT_DEFAULTS.z;
  const lineWidth = Number.isFinite(+pvCfg.lineWidth)
    ? +pvCfg.lineWidth
    : CHAN_PEN_PIVOT_DEFAULTS.lineWidth;
  const lineStyle = String(
    pvCfg.lineStyle || CHAN_PEN_PIVOT_DEFAULTS.lineStyle
  );
  const alpha =
    Math.max(0, Math.min(100, Number(pvCfg.alphaPercent || CHAN_PEN_PIVOT_DEFAULTS.alphaPercent))) /
    100;

  const barrierIdxSet = new Set(
    Array.isArray(env.barrierIdxList) ? env.barrierIdxList.map((x) => +x) : []
  );

  // 顶/底边按 x 从 left..right 逐一采点；遇屏障断开为独立 series
  function sampleEdgeToChunks(left, right, yConst) {
    const yResolver = () => yConst;
    return sampleSeriesByBarriers({
      xStart: left,
      xEnd: right,
      yResolver,
      barriersSet: barrierIdxSet,
    });
  }

  const out = [];
  let seqCounter = 0;

  for (let idx = 0; idx < (pivots || []).length; idx++) {
    const p = pivots[idx];
    const left = Number(p.left_idx_orig);
    const right = Number(p.right_idx_orig);
    const upper = Number(p.upper);
    const lower = Number(p.lower);
    if (![left, right, upper, lower].every((v) => Number.isFinite(v))) continue;
    if (!(upper > lower)) continue; // 零厚度不呈现

    const isUp = String(p.dir_enum || "").toUpperCase() === "UP";
    const color = isUp
      ? pvCfg.upColor || CHAN_PEN_PIVOT_DEFAULTS.upColor
      : pvCfg.downColor || CHAN_PEN_PIVOT_DEFAULTS.downColor;

    // 保留内部填充（淡显）
    out.push({
      id: `CHAN_PIVOT_AREA_${p.seq_id}_${left}_${right}_${idx}`,
      name: "CHAN_PIVOT_AREA",
      type: "line",
      yAxisIndex: 0,
      data: [],
      markArea: {
        silent: true,
        itemStyle: { color: hexToRgba(color, alpha) },
        label: { show: false },
        data: [[{ xAxis: left, yAxis: upper }, { xAxis: right, yAxis: lower }]],
      },
      z,
      tooltip: { show: false },
      emphasis: { disabled: true },
    });

    // 顶边：段落式折线
    const topChunks = sampleEdgeToChunks(left, right, upper);
    for (let k = 0; k < topChunks.length; k++) {
      const data = topChunks[k];
      out.push({
        id: `CHAN_PIVOT_TOP_${p.seq_id}_${left}_${right}_${k}_${seqCounter++}`,
        name: "CHAN_PIVOT_TOP",
        type: "line",
        yAxisIndex: 0,
        data,
        showSymbol: false,
        smooth: false,
        connectNulls: false,
        lineStyle: { color, width: lineWidth, type: lineStyle },
        z,
        tooltip: { show: false },
        emphasis: { disabled: true },
      });
    }

    // 底边：段落式折线
    const bottomChunks = sampleEdgeToChunks(left, right, lower);
    for (let k = 0; k < bottomChunks.length; k++) {
      const data = bottomChunks[k];
      out.push({
        id: `CHAN_PIVOT_BOTTOM_${p.seq_id}_${left}_${right}_${k}_${seqCounter++}`,
        name: "CHAN_PIVOT_BOTTOM",
        type: "line",
        yAxisIndex: 0,
        data,
        showSymbol: false,
        smooth: false,
        connectNulls: false,
        lineStyle: { color, width: lineWidth, type: lineStyle },
        z,
        tooltip: { show: false },
        emphasis: { disabled: true },
      });
    }

    // 垂直边（左/右）
    out.push({
      id: `CHAN_PIVOT_LEFT_${p.seq_id}_${left}_${seqCounter++}`,
      name: "CHAN_PIVOT_LEFT",
      type: "line",
      yAxisIndex: 0,
      data: [
        [left, lower],
        [left, upper],
      ],
      showSymbol: false,
      smooth: false,
      connectNulls: false,
      lineStyle: { color, width: lineWidth, type: lineStyle },
      z,
      tooltip: { show: false },
      emphasis: { disabled: true },
    });
    out.push({
      id: `CHAN_PIVOT_RIGHT_${p.seq_id}_${right}_${seqCounter++}`,
      name: "CHAN_PIVOT_RIGHT",
      type: "line",
      yAxisIndex: 0,
      data: [
        [right, lower],
        [right, upper],
      ],
      showSymbol: false,
      smooth: false,
      connectNulls: false,
      lineStyle: { color, width: lineWidth, type: lineStyle },
      z,
      tooltip: { show: false },
      emphasis: { disabled: true },
    });
  }
  return { series: out };
}