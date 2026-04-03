# backend/services/bars_recipes.py
# ==============================
# 说明：K线动作指令集（Bars Recipes · 日线收尾优化阶段）
#
# 本阶段改动：
#   - 日线真相源已切到 candles_day_raw
#   - 当前阶段只保证日线 DB 链路稳定
#   - 分钟线后续将切换为“归档 + 实时拼接”独立链路
#
# 本轮改动（复权因子本地化）：
#   - 股票复权因子真相源已切到：
#       * TDX 本地 gbbq category=1
#       * 本地原始日线 candles_day_raw
#   - 不再依赖 Baostock 远程因子
# ==============================

from __future__ import annotations

from typing import Optional

import asyncio
import pandas as pd

from backend.datasource import dispatcher
from backend.services.normalizer import (
    normalize_bars_df,
    normalize_tdx_gbbq_adj_factors_df,
)
from backend.db.async_writer import get_async_writer
from backend.db.candles import select_candles_day_raw
from backend.db.symbols import select_symbol_index
from backend.utils.common import get_symbol_market_from_db
from backend.utils.gap_checker import check_kline_gap_to_current
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("bars_recipes")
_writer = get_async_writer()


class RemoteEmptyDataError(RuntimeError):
    """远程/本地真实拉取但返回空数据（强规则：应视为失败）。"""


def _get_symbol_class(symbol: str) -> Optional[str]:
    try:
        rows = select_symbol_index(symbol=symbol)
        if not rows:
            return None
        cls = str(rows[0].get("class") or "").strip().lower()
        return cls or None
    except Exception:
        return None


def _get_symbol_market(symbol: str) -> Optional[str]:
    try:
        return get_symbol_market_from_db(symbol)
    except Exception:
        return None


async def _load_day_bars_from_db(market: str, symbol: str) -> pd.DataFrame:
    rows = await asyncio.to_thread(
        select_candles_day_raw,
        market=market,
        symbol=symbol,
        start_ts=None,
        end_ts=None,
        limit=None,
        offset=0,
    )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


async def _save_day_bars_df(
    df_bars: pd.DataFrame,
    market: str,
    symbol: str,
) -> None:
    if df_bars is None or df_bars.empty:
        return
    df = df_bars.copy()
    df["market"] = str(market or "").strip().upper()
    df["symbol"] = symbol
    await _writer.write_candles(df.to_dict("records"))


async def run_stock_dwm_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    """
    当前阶段仅稳定支持股票日线（1d）同步入库。
    """
    cls = _get_symbol_class(symbol)
    if cls != "stock":
        _LOG.info(f"[S1] 跳过：{symbol} class={cls} 非 stock")
        return False

    if freq != "1d":
        _LOG.warning(f"[S1] 当前阶段仅支持股票日线 1d，收到 freq={freq}")
        return False

    market = _get_symbol_market(symbol) or ""
    has_gap = check_kline_gap_to_current(
        symbol=symbol,
        freq=freq,
        market=market,
        force_fetch=force_fetch,
    )
    if not has_gap:
        _LOG.info(f"[S1] 无缺口：{market} {symbol} {freq} 本地已最新")
        return False

    category = "stock_daily_bars"

    log_event(
        logger=_LOG,
        service="bars_recipes",
        level="INFO",
        file=__file__,
        func="run_stock_dwm_unadj",
        line=0,
        trace_id=trace_id,
        event="S1.fetch.start",
        message=f"S1 拉取股票日线原始K线 {symbol} {freq}",
        extra={
            "symbol": symbol,
            "market": market,
            "freq": freq,
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

    df_bars = normalize_bars_df(raw_df, source_id or "eastmoney.stock_daily_kline")
    if df_bars is None or df_bars.empty:
        raise RemoteEmptyDataError(f"normalized empty for {category} symbol={symbol} freq={freq}")

    await _save_day_bars_df(
        df_bars=df_bars,
        market=market,
        symbol=symbol,
    )

    _LOG.info(f"[S1] 完成：{market} {symbol} {freq} 行数={len(df_bars)}")
    return True


async def run_stock_intraday_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    _LOG.warning(f"[S2] 当前阶段未启用股票分钟线链路 symbol={symbol} freq={freq}")
    return False


async def run_stock_factors(
    symbol: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    """
    股票复权因子本地化主链：

      TDX 本地 gbbq(category=1)
      + 本地原始日线 candles_day_raw
      -> qfq_factor / hfq_factor
      -> adj_factors
    """
    sym = (symbol or "").strip()
    if not sym:
        _LOG.warning("[S3] 空 symbol，跳过")
        return False

    market = _get_symbol_market(sym) or ""
    cls = _get_symbol_class(sym)
    if cls != "stock":
        _LOG.info("[S3] 跳过：%s class=%s 非 stock", sym, cls)
        return False

    if not market:
        raise ValueError(f"LOCAL_SYMBOL_MARKET_MISSING: symbol={sym}")

    log_event(
        logger=_LOG,
        service="bars_recipes",
        level="INFO",
        file=__file__,
        func="run_stock_factors",
        line=0,
        trace_id=trace_id,
        event="S3.fetch.start",
        message=f"S3 拉取本地股票复权事件 {symbol}",
        extra={"symbol": symbol, "market": market},
    )

    raw_df, source_id = await dispatcher.fetch(
        "adj_factor",
        symbol=sym,
    )

    if raw_df is None:
        raise RemoteEmptyDataError(f"local empty for adj_factor symbol={sym}")

    if isinstance(raw_df, pd.DataFrame) and raw_df.empty:
        _LOG.info("[S3] 本地无复权事件：%s", sym)
        return False

    day_df = await _load_day_bars_from_db(market=market, symbol=sym)
    if day_df is None or day_df.empty:
        raise ValueError(f"LOCAL_PRICE_DEPENDENCY_MISSING: no local day bars for {market}.{sym}")

    df = normalize_tdx_gbbq_adj_factors_df(
        raw_df,
        day_df,
        symbol=sym,
        market=market,
    )

    if df is None or df.empty:
        _LOG.info("[S3] 复权事件存在，但标准化后无有效因子：%s", sym)
        return False

    df["symbol"] = sym
    await _writer.write_factors(df.to_dict("records"))

    _LOG.info(f"[S3] 完成：{market} {sym} 本地因子行数={len(df)} source_id={source_id}")
    return True


async def run_fund_dwm_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    _LOG.warning(f"[F1] 当前阶段未启用基金日线链路 symbol={symbol} freq={freq}")
    return False


async def run_fund_dwm_adj(
    symbol: str,
    freq: str,
    adjust: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    _LOG.warning(f"[F2] 当前阶段未启用基金复权日线链路 symbol={symbol} freq={freq} adjust={adjust}")
    return False


async def run_fund_intraday_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    _LOG.warning(f"[F3] 当前阶段未启用基金分钟线链路 symbol={symbol} freq={freq}")
    return False


async def run_fund_intraday_adj(
    symbol: str,
    freq: str,
    adjust: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    _LOG.warning(f"[F4] 当前阶段未启用基金分钟复权链路 symbol={symbol} freq={freq} adjust={adjust}")
    return False
