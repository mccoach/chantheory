// src/composables/viewRenderHub/range/tsArrMemo.js
// ==============================
// tsArr 记忆化（避免每次 candles.map(ts)）
// 迁移自原 useViewRenderHub 的 _tsArrMemo + _getTsArr。
// ==============================

export function createTsArrMemo() {
  const memo = {
    candlesRef: null,
    len: 0,
    firstTs: null,
    lastTs: null,
    tsArr: null,
  };

  function getTsArr(candles) {
    const arr = Array.isArray(candles) ? candles : [];
    const len = arr.length;

    if (!len) {
      memo.candlesRef = null;
      memo.len = 0;
      memo.firstTs = null;
      memo.lastTs = null;
      memo.tsArr = [];
      return [];
    }

    const firstTs = arr[0]?.ts;
    const lastTs = arr[len - 1]?.ts;

    if (
      memo.candlesRef === arr &&
      memo.len === len &&
      memo.firstTs === firstTs &&
      memo.lastTs === lastTs &&
      Array.isArray(memo.tsArr) &&
      memo.tsArr.length === len
    ) {
      return memo.tsArr;
    }

    const tsArr = new Array(len);
    for (let i = 0; i < len; i++) tsArr[i] = arr[i]?.ts;

    memo.candlesRef = arr;
    memo.len = len;
    memo.firstTs = firstTs;
    memo.lastTs = lastTs;
    memo.tsArr = tsArr;

    return tsArr;
  }

  return { getTsArr };
}
