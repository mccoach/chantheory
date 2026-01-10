// src/composables/viewRenderHub/range/rangeCalc.js
// ==============================
// 可见区间计算工具（基于 rightTs + barsCount）
// 迁移自原 useViewRenderHub：upperBoundLE + sIdx/eIdx 推导逻辑。
// ==============================

function upperBoundLE(arr, target) {
  const n = Array.isArray(arr) ? arr.length : 0;
  if (!n) return -1;

  let lo = 0;
  let hi = n - 1;
  let ans = -1;

  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const v = Number(arr[mid]);
    if (!Number.isFinite(v)) {
      hi = mid - 1;
      continue;
    }
    if (v <= target) {
      ans = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }

  return ans;
}

/**
 * @param {object} args
 * @param {number} args.candlesLen
 * @param {Array<number>} args.tsArr
 * @param {number|null} args.rightTs
 * @param {number} args.bars
 * @returns {{sIdx:number,eIdx:number}}
 */
export function calcVisibleRangeByRightTsBars({ candlesLen, tsArr, rightTs, bars }) {
  const len = Math.max(0, Number(candlesLen || 0));
  if (!len) return { sIdx: 0, eIdx: 0 };

  const b = Math.max(1, Number(bars || 1));

  let eIdx = len - 1;
  if (Number.isFinite(rightTs)) {
    const pos = upperBoundLE(tsArr, rightTs);
    eIdx = pos >= 0 ? pos : 0;
  }

  let sIdx = Math.max(0, eIdx - b + 1);
  if (sIdx === 0 && eIdx - sIdx + 1 < b) {
    eIdx = Math.min(len - 1, b - 1);
  }

  return { sIdx, eIdx };
}
