# backend/services/bars_recipes.py
# ==============================
# 说明：K线动作指令集（Bars Recipes · 统一 dispatcher 版 · 内存推算版 F4）
#
# 本次改动：
#   - 强规则落地：凡发生真实远程拉取，若远端返回空数据 => 抛异常（由上层标记 failed）
#   - 目的：禁止“远端空但 job 仍 success”的漂移
# ==============================

from __future__ import annotations

from typing import Optional, Any, Dict, List, Tuple

import asyncio
import pandas as pd

from backend.datasource import dispatcher
from backend.services.normalizer import (
    normalize_bars_df,
    normalize_baostock_adj_factors_df,
)
from backend.db.async_writer import get_async_writer
from backend.db.candles import select_candles_raw
from backend.db.symbols import select_symbol_index
from backend.utils.gap_checker import check_kline_gap_to_current
from backend.utils.logger import get_logger, log_event
from backend.utils.time import to_yyyymmdd

_LOG = get_logger("bars_recipes")
_writer = get_async_writer()


class RemoteEmptyDataError(RuntimeError):
    """远程真实拉取但返回空数据（强规则：应视为失败）。"""


def _get_symbol_class(symbol: str) -> Optional[str]:
    try:
        rows = select_symbol_index(symbol=symbol)
        if not rows:
            return None
        cls = str(rows[0].get("class") or "").strip().lower()
        return cls or None
    except Exception:
        return None


async def _load_bars_from_db(symbol: str, freq: str, adjust: str) -> pd.DataFrame:
    rows = await asyncio.to_thread(
        select_candles_raw,
        symbol=symbol,
        freq=freq,
        start_ts=None,
        end_ts=None,
        limit=None,
        offset=0,
        adjust=adjust,
    )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


async def _save_bars_df(
    df_bars: pd.DataFrame,
    symbol: str,
    freq: str,
    adjust: str,
    source: str,
) -> None:
    if df_bars is None or df_bars.empty:
        return
    df = df_bars.copy()
    df["symbol"] = symbol
    df["freq"] = freq
    df["source"] = source
    df["adjust"] = adjust
    await _writer.write_candles(df.to_dict("records"))


async def _ensure_fund_minutely_unadj_df(
    symbol: str,
    freq: str,
    force_fetch: bool,
    trace_id: Optional[str],
) -> Tuple[pd.DataFrame, bool]:
    has_gap = check_kline_gap_to_current(
        symbol=symbol,
        freq=freq,
        adjust="none",
        force_fetch=force_fetch,
    )

    category = "fund_minutely_bars"

    if not has_gap:
        df = await _load_bars_from_db(symbol, freq, adjust="none")
        return df, False

    log_event(
        logger=_LOG,
        service="bars_recipes",
        level="INFO",
        file=__file__,
        func="_ensure_fund_minutely_unadj_df",
        line=0,
        trace_id=trace_id,
        event="F3.fetch.start",
        message=f"[ensure] F3 拉取基金分时不复权 {symbol} {freq}",
        extra={
            "symbol": symbol,
            "freq": freq,
            "adjust": "none",
            "category": category,
        },
    )

    raw_df, source_id = await dispatcher.fetch(
        category,
        freq=freq,
        symbol=symbol,
        ma="no",
    )

    # 强规则：真实远程拉取且返回空 => failed
    if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
        raise RemoteEmptyDataError(f"remote empty for {category} symbol={symbol} freq={freq}")

    df_bars = normalize_bars_df(raw_df, source_id or "sina.fund_minutely_kline")
    if df_bars is None or df_bars.empty:
        raise RemoteEmptyDataError(f"normalized empty for {category} symbol={symbol} freq={freq}")

    await _save_bars_df(
        df_bars=df_bars,
        symbol=symbol,
        freq=freq,
        adjust="none",
        source=source_id or "sina.fund_minutely_kline",
    )

    return df_bars, True


async def _ensure_fund_daily_unadj_df(
    symbol: str,
    force_fetch: bool,
    trace_id: Optional[str],
) -> Tuple[pd.DataFrame, bool]:
    freq = "1d"
    has_gap = check_kline_gap_to_current(
        symbol=symbol,
        freq=freq,
        adjust="none",
        force_fetch=force_fetch,
    )

    category = "fund_bars"

    if not has_gap:
        df = await _load_bars_from_db(symbol, freq, adjust="none")
        return df, False

    log_event(
        logger=_LOG,
        service="bars_recipes",
        level="INFO",
        file=__file__,
        func="_ensure_fund_daily_unadj_df",
        line=0,
        trace_id=trace_id,
        event="F1.fetch.start",
        message=f"[ensure] F1 拉取基金日线不复权 {symbol} 1d",
        extra={
            "symbol": symbol,
            "freq": freq,
            "adjust": "none",
            "category": category,
        },
    )

    raw_df, source_id = await dispatcher.fetch(
        category,
        freq=freq,
        symbol=symbol,
        fqt=0,
    )

    if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
        raise RemoteEmptyDataError(f"remote empty for {category} symbol={symbol} freq={freq} fqt=0")

    df_bars = normalize_bars_df(raw_df, source_id or "eastmoney.fund_kline")
    if df_bars is None or df_bars.empty:
        raise RemoteEmptyDataError(f"normalized empty for {category} symbol={symbol} freq={freq} fqt=0")

    await _save_bars_df(
        df_bars=df_bars,
        symbol=symbol,
        freq=freq,
        adjust="none",
        source=source_id or "eastmoney.fund_kline",
    )

    return df_bars, True


async def _ensure_fund_daily_adj_df(
    symbol: str,
    adjust: str,
    force_fetch: bool,
    trace_id: Optional[str],
) -> Tuple[pd.DataFrame, bool]:
    freq = "1d"
    has_gap = check_kline_gap_to_current(
        symbol=symbol,
        freq=freq,
        adjust=adjust,
        force_fetch=force_fetch,
    )

    category = "fund_bars"
    fqt = 1 if adjust == "qfq" else 2

    if not has_gap:
        df = await _load_bars_from_db(symbol, freq, adjust=adjust)
        return df, False

    log_event(
        logger=_LOG,
        service="bars_recipes",
        level="INFO",
        file=__file__,
        func="_ensure_fund_daily_adj_df",
        line=0,
        trace_id=trace_id,
        event="F2.fetch.start",
        message=f"[ensure] F2 拉取基金日线复权 {symbol} 1d adjust={adjust}",
        extra={
            "symbol": symbol,
            "freq": freq,
            "adjust": adjust,
            "category": category,
            "fqt": fqt,
        },
    )

    raw_df, source_id = await dispatcher.fetch(
        category,
        freq=freq,
        symbol=symbol,
        fqt=fqt,
    )

    if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
        raise RemoteEmptyDataError(f"remote empty for {category} symbol={symbol} freq={freq} fqt={fqt}")

    df_bars = normalize_bars_df(raw_df, source_id or "eastmoney.fund_kline")
    if df_bars is None or df_bars.empty:
        raise RemoteEmptyDataError(f"normalized empty for {category} symbol={symbol} freq={freq} fqt={fqt}")

    await _save_bars_df(
        df_bars=df_bars,
        symbol=symbol,
        freq=freq,
        adjust=adjust,
        source=source_id or "eastmoney.fund_kline",
    )

    return df_bars, True


async def run_stock_dwm_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    cls = _get_symbol_class(symbol)
    if cls != "stock":
        _LOG.info(f"[S1] 跳过：{symbol} class={cls} 非 stock")
        return False

    if freq not in ("1d", "1w", "1M"):
        _LOG.warning(f"[S1] 不支持的 freq={freq}，仅支持 1d/1w/1M")
        return False

    has_gap = check_kline_gap_to_current(
        symbol=symbol,
        freq=freq,
        adjust="none",
        force_fetch=force_fetch,
    )
    if not has_gap:
        _LOG.info(f"[S1] 无缺口：{symbol} {freq} adjust=none，本地已最新")
        return False

    if freq == "1d":
        category = "stock_daily_bars"
    elif freq == "1w":
        category = "stock_weekly_bars"
    else:
        category = "stock_monthly_bars"

    log_event(
        logger=_LOG,
        service="bars_recipes",
        level="INFO",
        file=__file__,
        func="run_stock_dwm_unadj",
        line=0,
        trace_id=trace_id,
        event="S1.fetch.start",
        message=f"S1 拉取股票日/周/月不复权 {symbol} {freq}",
        extra={
            "symbol": symbol,
            "freq": freq,
            "adjust": "none",
            "category": category
        },
    )

    raw_df, source_id = await dispatcher.fetch(
        category,
        freq=freq,
        symbol=symbol,
        fqt=0,
    )

    if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
        raise RemoteEmptyDataError(f"remote empty for {category} symbol={symbol} freq={freq}")

    df_bars = normalize_bars_df(raw_df, source_id or "eastmoney.stock_kline")
    if df_bars is None or df_bars.empty:
        raise RemoteEmptyDataError(f"normalized empty for {category} symbol={symbol} freq={freq}")

    await _save_bars_df(
        df_bars=df_bars,
        symbol=symbol,
        freq=freq,
        adjust="none",
        source=source_id or "eastmoney.stock_kline",
    )

    _LOG.info(
        f"[S1] 完成：{symbol} {freq} 行数={len(df_bars)} adjust=none category={category}",
    )
    return True


async def run_stock_intraday_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    cls = _get_symbol_class(symbol)
    if cls != "stock":
        _LOG.info(f"[S2] 跳过：{symbol} class={cls} 非 stock")
        return False

    if freq not in ("1m", "5m", "15m", "30m", "60m"):
        _LOG.warning(f"[S2] 不支持的 freq={freq}，仅支持 1m/5m/15m/30m/60m")
        return False

    has_gap = check_kline_gap_to_current(
        symbol=symbol,
        freq=freq,
        adjust="none",
        force_fetch=force_fetch,
    )
    if not has_gap:
        _LOG.info(f"[S2] 无缺口：{symbol} {freq} adjust=none，本地已最新")
        return False

    category = "stock_minutely_bars"

    log_event(
        logger=_LOG,
        service="bars_recipes",
        level="INFO",
        file=__file__,
        func="run_stock_intraday_unadj",
        line=0,
        trace_id=trace_id,
        event="S2.fetch.start",
        message=f"S2 拉取股票分时不复权 {symbol} {freq}",
        extra={
            "symbol": symbol,
            "freq": freq,
            "adjust": "none",
            "category": category
        },
    )

    raw_df, source_id = await dispatcher.fetch(
        category,
        freq=freq,
        symbol=symbol,
        ma="no",
    )

    if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
        raise RemoteEmptyDataError(f"remote empty for {category} symbol={symbol} freq={freq}")

    df_bars = normalize_bars_df(raw_df, source_id or "sina.stock_minutely_kline")
    if df_bars is None or df_bars.empty:
        raise RemoteEmptyDataError(f"normalized empty for {category} symbol={symbol} freq={freq}")

    await _save_bars_df(
        df_bars=df_bars,
        symbol=symbol,
        freq=freq,
        adjust="none",
        source=source_id or "sina.stock_minutely_kline",
    )

    _LOG.info(
        f"[S2] 完成：{symbol} {freq} 行数={len(df_bars)} adjust=none category={category}",
    )
    return True


async def run_stock_factors(
    symbol: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    sym = (symbol or "").strip()
    if not sym:
        _LOG.warning("[S3] 空 symbol，跳过")
        return False

    log_event(
        logger=_LOG,
        service="bars_recipes",
        level="INFO",
        file=__file__,
        func="run_stock_factors",
        line=0,
        trace_id=trace_id,
        event="S3.fetch.start",
        message=f"S3 拉取股票因子 {symbol}",
        extra={"symbol": symbol},
    )

    raw_df, source_id = await dispatcher.fetch(
        "adj_factor",
        symbol=symbol,
    )

    if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
        raise RemoteEmptyDataError(f"remote empty for adj_factor symbol={symbol}")

    df = normalize_baostock_adj_factors_df(
        raw_df,
        source_id=source_id or "baostock.get_adj_factors",
    )

    if df is None or df.empty:
        raise RemoteEmptyDataError(f"normalized empty for adj_factor symbol={symbol}")

    df["symbol"] = symbol
    await _writer.write_factors(df.to_dict("records"))

    _LOG.info(f"[S3] 完成：{symbol} 因子行数={len(df)}")
    return True


async def run_fund_dwm_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    cls = _get_symbol_class(symbol)
    if cls != "fund":
        _LOG.info(f"[F1] 跳过：{symbol} class={cls} 非 fund")
        return False

    if freq not in ("1d", "1w", "1M"):
        _LOG.warning(f"[F1] 不支持的 freq={freq}，仅支持 1d/1w/1M")
        return False

    if freq == "1d":
        df, from_remote = await _ensure_fund_daily_unadj_df(
            symbol=symbol,
            force_fetch=force_fetch,
            trace_id=trace_id,
        )
        return bool(from_remote)

    has_gap = check_kline_gap_to_current(
        symbol=symbol,
        freq=freq,
        adjust="none",
        force_fetch=force_fetch,
    )
    if not has_gap:
        _LOG.info(f"[F1] 无缺口：{symbol} {freq} adjust=none，本地已最新")
        return False

    category = "fund_bars"

    raw_df, source_id = await dispatcher.fetch(
        category,
        freq=freq,
        symbol=symbol,
        fqt=0,
    )
    if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
        raise RemoteEmptyDataError(f"remote empty for {category} symbol={symbol} freq={freq} fqt=0")

    df_bars = normalize_bars_df(raw_df, source_id or "eastmoney.fund_kline")
    if df_bars is None or df_bars.empty:
        raise RemoteEmptyDataError(f"normalized empty for {category} symbol={symbol} freq={freq} fqt=0")

    await _save_bars_df(df_bars=df_bars, symbol=symbol, freq=freq, adjust="none", source=source_id or "eastmoney.fund_kline")
    return True


async def run_fund_dwm_adj(
    symbol: str,
    freq: str,
    adjust: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    cls = _get_symbol_class(symbol)
    if cls != "fund":
        _LOG.info(f"[F2] 跳过：{symbol} class={cls} 非 fund")
        return False

    if freq not in ("1d", "1w", "1M"):
        _LOG.warning(f"[F2] 不支持的 freq={freq}，仅支持 1d/1w/1M")
        return False

    if adjust not in ("qfq", "hfq"):
        _LOG.warning(f"[F2] 不支持的 adjust={adjust}，仅支持 qfq/hfq")
        return False

    if freq == "1d":
        df, from_remote = await _ensure_fund_daily_adj_df(
            symbol=symbol,
            adjust=adjust,
            force_fetch=force_fetch,
            trace_id=trace_id,
        )
        return bool(from_remote)

    has_gap = check_kline_gap_to_current(symbol=symbol, freq=freq, adjust=adjust, force_fetch=force_fetch)
    if not has_gap:
        return False

    category = "fund_bars"
    fqt = 1 if adjust == "qfq" else 2

    raw_df, source_id = await dispatcher.fetch(category, freq=freq, symbol=symbol, fqt=fqt)
    if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
        raise RemoteEmptyDataError(f"remote empty for {category} symbol={symbol} freq={freq} fqt={fqt}")

    df_bars = normalize_bars_df(raw_df, source_id or "eastmoney.fund_kline")
    if df_bars is None or df_bars.empty:
        raise RemoteEmptyDataError(f"normalized empty for {category} symbol={symbol} freq={freq} fqt={fqt}")

    await _save_bars_df(df_bars=df_bars, symbol=symbol, freq=freq, adjust=adjust, source=source_id or "eastmoney.fund_kline")
    return True


async def run_fund_intraday_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    cls = _get_symbol_class(symbol)
    if cls != "fund":
        _LOG.info(f"[F3] 跳过：{symbol} class={cls} 非 fund")
        return False

    if freq not in ("1m", "5m", "15m", "30m", "60m"):
        _LOG.warning(f"[F3] 不支持的 freq={freq}，仅支持 1m/5m/15m/30m/60m")
        return False

    df, from_remote = await _ensure_fund_minutely_unadj_df(
        symbol=symbol,
        freq=freq,
        force_fetch=force_fetch,
        trace_id=trace_id,
    )
    return bool(from_remote)


async def run_fund_intraday_adj(
    symbol: str,
    freq: str,
    adjust: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    cls = _get_symbol_class(symbol)
    if cls != "fund":
        _LOG.info(f"[F4] 跳过：{symbol} class={cls} 非 fund")
        return False

    if freq not in ("1m", "5m", "15m", "30m", "60m"):
        _LOG.warning(f"[F4] 不支持的 freq={freq}，仅支持 1m/5m/15m/30m/60m")
        return False

    if adjust not in ("qfq", "hfq"):
        _LOG.warning(f"[F4] 不支持的 adjust={adjust}，仅支持 qfq/hfq")
        return False

    has_gap = check_kline_gap_to_current(symbol=symbol, freq=freq, adjust=adjust, force_fetch=force_fetch)
    if not has_gap:
        return False

    log_event(
        logger=_LOG,
        service="bars_recipes",
        level="INFO",
        file=__file__,
        func="run_fund_intraday_adj",
        line=0,
        trace_id=trace_id,
        event="F4.fetch.start",
        message=f"F4 准备基金分时复权所需数据 {symbol} {freq} adjust={adjust}",
        extra={"symbol": symbol, "freq": freq, "adjust": adjust},
    )

    df_min_unadj, _ = await _ensure_fund_minutely_unadj_df(symbol=symbol, freq=freq, force_fetch=force_fetch, trace_id=trace_id)
    df_d_unadj, _ = await _ensure_fund_daily_unadj_df(symbol=symbol, force_fetch=force_fetch, trace_id=trace_id)
    df_d_adj, _ = await _ensure_fund_daily_adj_df(symbol=symbol, adjust=adjust, force_fetch=force_fetch, trace_id=trace_id)

    if df_min_unadj is None or df_min_unadj.empty:
        raise RemoteEmptyDataError(f"missing dependency: fund intraday unadj empty symbol={symbol} freq={freq}")
    if df_d_unadj is None or df_d_unadj.empty:
        raise RemoteEmptyDataError(f"missing dependency: fund daily unadj empty symbol={symbol}")
    if df_d_adj is None or df_d_adj.empty:
        raise RemoteEmptyDataError(f"missing dependency: fund daily adj empty symbol={symbol} adjust={adjust}")

    df_d_unadj = df_d_unadj.copy()
    df_d_adj = df_d_adj.copy()
    df_d_unadj["date"] = df_d_unadj["ts"].apply(to_yyyymmdd)
    df_d_adj["date"] = df_d_adj["ts"].apply(to_yyyymmdd)

    df_ratio = pd.merge(
        df_d_unadj[["date", "close"]],
        df_d_adj[["date", "close"]],
        on="date",
        how="inner",
        suffixes=("_unadj", "_adj"),
    )

    df_ratio = df_ratio[(df_ratio["close_unadj"] > 0) & df_ratio["close_adj"].notna()].copy()
    if df_ratio.empty:
        raise RemoteEmptyDataError(f"no ratio records for intraday adj symbol={symbol} adjust={adjust}")

    df_ratio["ratio"] = df_ratio["close_adj"] / df_ratio["close_unadj"]
    ratio_map = {int(row["date"]): float(row["ratio"]) for _, row in df_ratio.iterrows()}

    df_min_unadj = df_min_unadj.copy()
    df_min_unadj["date"] = df_min_unadj["ts"].apply(to_yyyymmdd)
    df_min_unadj["ratio"] = df_min_unadj["date"].map(ratio_map).fillna(1.0)

    df_min_adj = df_min_unadj.copy()
    for col in ("open", "high", "low", "close"):
        df_min_adj[col] = df_min_adj[col] * df_min_adj["ratio"]

    df_min_adj = df_min_adj.drop(columns=["date", "ratio"], errors="ignore")
    if df_min_adj.empty:
        raise RemoteEmptyDataError(f"derived intraday adj empty symbol={symbol} freq={freq} adjust={adjust}")

    await _save_bars_df(df_bars=df_min_adj, symbol=symbol, freq=freq, adjust=adjust, source="derived.fund_intraday_adj")

    _LOG.info(
        f"[F4] 完成基金分时复权推算：{symbol} {freq} adjust={adjust} 分时行数={len(df_min_adj)}",
    )
    return True
