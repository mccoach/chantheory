# backend/services/bars_recipes.py
# ==============================
# 说明：K线动作指令集（Bars Recipes · 统一 dispatcher 版 · 内存推算版 F4）
#
# 职责：
#   - 为 stock/fund 的 K 线与因子提供统一的“动作配方”：
#       * S1: STOCK_DWM_UNADJ       - 股票日/周/月不复权
#       * S2: STOCK_INTRADAY_UNADJ  - 股票分时不复权
#       * S3: STOCK_FACTORS         - 股票因子（Baostock）
#       * F1: FUND_DWM_UNADJ        - 基金日/周/月不复权
#       * F2: FUND_DWM_ADJ          - 基金日/周/月复权
#       * F3: FUND_INTRADAY_UNADJ   - 基金分时不复权
#       * F4: FUND_INTRADAY_ADJ     - 基金分时复权（内存推算 + 复用 F1/F2/F3 逻辑）
#
# 核心变更（F4）：
#   - 不再在 F4 里“调用 F1/F2/F3 → 等写库 → 再读 DB”；
#   - 新增内部 helper _ensure_fund_* 系列：
#       * 若本地无缺口 → 直接从 DB 读取完整数据返回（不发远程）；
#       * 若有缺口     → 远程拉取 + 标准化 + 异步写库，返回最新完整 DataFrame；
#   - F1/F2/F3 与 F4 共享这些 helper：
#       * F1/F2/F3 仍只返回 bool 表示“本次是否确实执行了远程拉取+写库”；
#       * F4 使用 helper 返回的 DataFrame，在内存中完成分时复权推算，只额外写入 D3（分钟复权）。
#   - 不在任意单个 recipe 内调用 flush()，仍只在 Task 末尾统一 flush，保持异步性能。
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

# ==============================================================================
# 公共辅助函数
# ==============================================================================


def _get_symbol_class(symbol: str) -> Optional[str]:
    """
    从 symbol_index 中查询标的 class（'stock'/'fund'/...）

    若查询失败或无记录，返回 None。
    """
    try:
        rows = select_symbol_index(symbol=symbol)
        if not rows:
            return None
        cls = str(rows[0].get("class") or "").strip().lower()
        return cls or None
    except Exception:
        return None


async def _load_bars_from_db(symbol: str, freq: str,
                             adjust: str) -> pd.DataFrame:
    """
    从 DB 中读取已标准化的 K 线（candles_raw）并转换为 DataFrame。
    """
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
    """
    将标准化后的 bars DataFrame 写入 candles_raw（通过 AsyncDBWriter）。

    约束：
      - 业务层不设置时间戳字段（updated_at）；
      - 时间戳统一由写入层在真正落库时覆盖为“当前写入时间”。
    """
    if df_bars is None or df_bars.empty:
        return
    df = df_bars.copy()
    df["symbol"] = symbol
    df["freq"] = freq
    df["source"] = source
    df["adjust"] = adjust
    await _writer.write_candles(df.to_dict("records"))


# ==============================================================================
# 内部 helper：基金 ensure 系列
#   行为：有则读DB，无则拉取并写库，返回 DataFrame + 是否远程拉取
# ==============================================================================


async def _ensure_fund_minutely_unadj_df(
    symbol: str,
    freq: str,
    force_fetch: bool,
    trace_id: Optional[str],
) -> Tuple[pd.DataFrame, bool]:
    """
    确保基金分钟不复权数据（D0）就绪，并返回完整 DataFrame。

    返回：
      (df, from_remote)
        - df          : 分钟不复权 DataFrame（可能为空）
        - from_remote : True 表示本次做了远程拉取并写库，False 表示直接从 DB 读取
    """
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

    # 有缺口：远程拉取
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

    if raw_df is None or (isinstance(raw_df, pd.DataFrame)
                          and raw_df.empty):
        _LOG.warning(
            f"[ensure] F3 分钟不复权原始数据为空：{symbol} {freq} category={category}"
        )
        return pd.DataFrame(), False

    df_bars = normalize_bars_df(raw_df, source_id or "sina.fund_minutely_kline")
    if df_bars is None or df_bars.empty:
        _LOG.warning(
            f"[ensure] F3 分钟不复权标准化后无数据：{symbol} {freq}"
        )
        return pd.DataFrame(), False

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
    """
    确保基金日线不复权数据（D1）就绪，并返回完整 DataFrame（freq='1d', adjust='none'）。

    返回：
      (df, from_remote)
        - df          : 日线不复权 DataFrame（可能为空）
        - from_remote : True 表示本次做了远程拉取并写库，False 表示直接从 DB 读取
    """
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

    # 有缺口：远程拉取
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

    if raw_df is None or (isinstance(raw_df, pd.DataFrame)
                          and raw_df.empty):
        _LOG.warning(
            f"[ensure] F1 日线不复权原始数据为空：{symbol} category={category}"
        )
        return pd.DataFrame(), False

    df_bars = normalize_bars_df(raw_df, source_id or "eastmoney.fund_kline")
    if df_bars is None or df_bars.empty:
        _LOG.warning(f"[ensure] F1 日线不复权标准化后无数据：{symbol}")
        return pd.DataFrame(), False

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
    """
    确保基金日线复权数据（D2）就绪，并返回完整 DataFrame（freq='1d', adjust='qfq/hfq'）。

    返回：
      (df, from_remote)
        - df          : 日线复权 DataFrame（可能为空）
        - from_remote : True 表示本次做了远程拉取并写库，False 表示直接从 DB 读取
    """
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

    # 有缺口：远程拉取
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

    if raw_df is None or (isinstance(raw_df, pd.DataFrame)
                          and raw_df.empty):
        _LOG.warning(
            f"[ensure] F2 日线复权原始数据为空：{symbol} adjust={adjust} category={category}"
        )
        return pd.DataFrame(), False

    df_bars = normalize_bars_df(raw_df, source_id or "eastmoney.fund_kline")
    if df_bars is None or df_bars.empty:
        _LOG.warning(
            f"[ensure] F2 日线复权标准化后无数据：{symbol} adjust={adjust}"
        )
        return pd.DataFrame(), False

    await _save_bars_df(
        df_bars=df_bars,
        symbol=symbol,
        freq=freq,
        adjust=adjust,
        source=source_id or "eastmoney.fund_kline",
    )

    return df_bars, True


# ==============================================================================
# S1: STOCK_DWM_UNADJ - 股票日/周/月不复权（保持原逻辑）
# ==============================================================================


async def run_stock_dwm_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    """
    股票日/周/月不复权 K 线配方（S1）

    返回：
      True  → 本次实际执行了远程拉取并写入 DB
      False → 无缺口 / 非 stock / 不支持 freq / 异常
    """
    cls = _get_symbol_class(symbol)
    if cls != "stock":
        _LOG.info(f"[S1] 跳过：{symbol} class={cls} 非 stock", )
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
        _LOG.info(f"[S1] 无缺口：{symbol} {freq} adjust=none，本地已最新", )
        return False

    # 选择 category
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

    try:
        raw_df, source_id = await dispatcher.fetch(
            category,
            freq=freq,
            symbol=symbol,
            fqt=0,
        )

        if raw_df is None or (isinstance(raw_df, pd.DataFrame)
                              and raw_df.empty):
            _LOG.warning(f"[S1] 原始数据为空：{symbol} {freq} category={category}")
            return False

        df_bars = normalize_bars_df(raw_df, source_id
                                    or "eastmoney.stock_kline")

        if df_bars is None or df_bars.empty:
            _LOG.warning(f"[S1] 标准化后无数据：{symbol} {freq}")
            return False

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

    except Exception as e:
        _LOG.error(f"[S1] 执行异常：{symbol} {freq}, error={e}", exc_info=True)
        return False


# ==============================================================================
# S2: STOCK_INTRADAY_UNADJ - 股票分时不复权（保持原逻辑）
# ==============================================================================


async def run_stock_intraday_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    """
    股票分时不复权 K 线配方（S2）

    返回：
      True  → 实际拉取并写入
      False → 无缺口 / 非 stock / 不支持 freq / 异常
    """
    cls = _get_symbol_class(symbol)
    if cls != "stock":
        _LOG.info(f"[S2] 跳过：{symbol} class={cls} 非 stock", )
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
        _LOG.info(f"[S2] 无缺口：{symbol} {freq} adjust=none，本地已最新", )
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

    try:
        raw_df, source_id = await dispatcher.fetch(
            category,
            freq=freq,
            symbol=symbol,
            ma="no",
        )

        if raw_df is None or (isinstance(raw_df, pd.DataFrame)
                              and raw_df.empty):
            _LOG.warning(f"[S2] 原始数据为空：{symbol} {freq} category={category}")
            return False

        df_bars = normalize_bars_df(raw_df, source_id
                                    or "sina.stock_minutely_kline")

        if df_bars is None or df_bars.empty:
            _LOG.warning(f"[S2] 标准化后无数据：{symbol} {freq}")
            return False

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

    except Exception as e:
        _LOG.error(f"[S2] 执行异常：{symbol} {freq}, error={e}", exc_info=True)
        return False


# ==============================================================================
# S3: STOCK_FACTORS - 股票因子（Baostock）（保持原逻辑）
# ==============================================================================


async def run_stock_factors(
    symbol: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    """
    股票复权因子配方（S3）

    注意：
      - 本配方不再内部做缺口判断；
      - 由上层任务配方（run_current_factors）在调用前统一使用 gap_checker；
      - 该函数被调用时，默认视为“确实需要刷新一次因子”，因此总是尝试：
          1) dispatcher.fetch('adj_factor')
          2) normalize_baostock_adj_factors_df
          3) AsyncDBWriter.write_factors

    返回：
      True  → 实际写入了因子数据
      False → 无数据 / 标准化失败 / 异常
    """
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

    try:
        raw_df, source_id = await dispatcher.fetch(
            "adj_factor",
            symbol=symbol,
        )

        if raw_df is None or (isinstance(raw_df, pd.DataFrame)
                              and raw_df.empty):
            _LOG.warning(f"[S3] 原始因子数据为空：{symbol}")
            return False

        df = normalize_baostock_adj_factors_df(
            raw_df,
            source_id=source_id or "baostock.get_adj_factors",
        )

        if df is None or df.empty:
            _LOG.warning(f"[S3] 标准化因子后无数据：{symbol}")
            return False

        df["symbol"] = symbol
        await _writer.write_factors(df.to_dict("records"))

        _LOG.info(f"[S3] 完成：{symbol} 因子行数={len(df)}", )
        return True

    except Exception as e:
        _LOG.error(f"[S3] 执行异常：{symbol}, error={e}", exc_info=True)
        return False


# ==============================================================================
# F1: FUND_DWM_UNADJ - 基金日/周/月不复权（复用 ensure helper）
# ==============================================================================


async def run_fund_dwm_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    """
    基金日/周/月不复权 K 线配方（F1）

    返回：
      True  → 实际写入（本次进行了远程拉取+写库）
      False → 无缺口 / 非 fund / 不支持 freq / 异常
    """
    cls = _get_symbol_class(symbol)
    if cls != "fund":
        _LOG.info(f"[F1] 跳过：{symbol} class={cls} 非 fund", )
        return False

    if freq not in ("1d", "1w", "1M"):
        _LOG.warning(f"[F1] 不支持的 freq={freq}，仅支持 1d/1w/1M")
        return False

    # 对于 1d，复用 ensure helper；对于 1w/1M 保持原逻辑
    if freq == "1d":
        df, from_remote = await _ensure_fund_daily_unadj_df(
            symbol=symbol,
            force_fetch=force_fetch,
            trace_id=trace_id,
        )
        if df is None or df.empty:
            return False
        if not from_remote:
            _LOG.info(
                f"[F1] 无缺口：{symbol} 1d adjust=none，本地已最新（通过 ensure）",
            )
        else:
            _LOG.info(
                f"[F1] 完成：{symbol} 1d 行数={len(df)} adjust=none（通过 ensure）",
            )
        return from_remote

    # 1w / 1M：沿用原先实现（如未来需要，也可以抽象 weekly/monthly ensure）
    has_gap = check_kline_gap_to_current(
        symbol=symbol,
        freq=freq,
        adjust="none",
        force_fetch=force_fetch,
    )
    if not has_gap:
        _LOG.info(f"[F1] 无缺口：{symbol} {freq} adjust=none，本地已最新", )
        return False

    category = "fund_bars"

    log_event(
        logger=_LOG,
        service="bars_recipes",
        level="INFO",
        file=__file__,
        func="run_fund_dwm_unadj",
        line=0,
        trace_id=trace_id,
        event="F1.fetch.start",
        message=f"F1 拉取基金日/周/月不复权 {symbol} {freq}",
        extra={
            "symbol": symbol,
            "freq": freq,
            "adjust": "none",
            "category": category
        },
    )

    try:
        raw_df, source_id = await dispatcher.fetch(
            category,
            freq=freq,
            symbol=symbol,
            fqt=0,
        )

        if raw_df is None or (isinstance(raw_df, pd.DataFrame)
                              and raw_df.empty):
            _LOG.warning(f"[F1] 原始数据为空：{symbol} {freq} category={category}")
            return False

        df_bars = normalize_bars_df(raw_df, source_id
                                    or "eastmoney.fund_kline")

        if df_bars is None or df_bars.empty:
            _LOG.warning(f"[F1] 标准化后无数据：{symbol} {freq}")
            return False

        await _save_bars_df(
            df_bars=df_bars,
            symbol=symbol,
            freq=freq,
            adjust="none",
            source=source_id or "eastmoney.fund_kline",
        )

        _LOG.info(
            f"[F1] 完成：{symbol} {freq} 行数={len(df_bars)} adjust=none category={category}",
        )
        return True

    except Exception as e:
        _LOG.error(f"[F1] 执行异常：{symbol} {freq}, error={e}", exc_info=True)
        return False


# ==============================================================================
# F2: FUND_DWM_ADJ - 基金日/周/月复权（复用 ensure helper）
# ==============================================================================


async def run_fund_dwm_adj(
    symbol: str,
    freq: str,
    adjust: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    """
    基金日/周/月复权 K 线配方（F2）

    返回：
      True  → 实际写入（本次进行了远程拉取+写库）
      False → 无缺口 / 非 fund / 不支持 freq/adjust / 异常
    """
    cls = _get_symbol_class(symbol)
    if cls != "fund":
        _LOG.info(f"[F2] 跳过：{symbol} class={cls} 非 fund", )
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
        if df is None or df.empty:
            return False
        if not from_remote:
            _LOG.info(
                f"[F2] 无缺口：{symbol} 1d adjust={adjust}，本地已最新（通过 ensure）",
            )
        else:
            _LOG.info(
                f"[F2] 完成：{symbol} 1d 行数={len(df)} adjust={adjust}（通过 ensure）",
            )
        return from_remote

    # 1w / 1M：沿用原先实现
    has_gap = check_kline_gap_to_current(
        symbol=symbol,
        freq=freq,
        adjust=adjust,
        force_fetch=force_fetch,
    )
    if not has_gap:
        _LOG.info(
            f"[F2] 无缺口：{symbol} {freq} adjust={adjust}，本地已最新", )
        return False

    category = "fund_bars"
    fqt = 1 if adjust == "qfq" else 2

    log_event(
        logger=_LOG,
        service="bars_recipes",
        level="INFO",
        file=__file__,
        func="run_fund_dwm_adj",
        line=0,
        trace_id=trace_id,
        event="F2.fetch.start",
        message=f"F2 拉取基金日/周/月复权 {symbol} {freq} adjust={adjust}",
        extra={
            "symbol": symbol,
            "freq": freq,
            "adjust": adjust,
            "category": category,
            "fqt": fqt,
        },
    )

    try:
        raw_df, source_id = await dispatcher.fetch(
            category,
            freq=freq,
            symbol=symbol,
            fqt=fqt,
        )

        if raw_df is None or (isinstance(raw_df, pd.DataFrame)
                              and raw_df.empty):
            _LOG.warning(
                f"[F2] 原始数据为空：{symbol} {freq} adjust={adjust} category={category}"
            )
            return False

        df_bars = normalize_bars_df(raw_df, source_id
                                    or "eastmoney.fund_kline")

        if df_bars is None or df_bars.empty:
            _LOG.warning(f"[F2] 标准化后无数据：{symbol} {freq} adjust={adjust}")
            return False

        await _save_bars_df(
            df_bars=df_bars,
            symbol=symbol,
            freq=freq,
            adjust=adjust,
            source=source_id or "eastmoney.fund_kline",
        )

        _LOG.info(
            f"[F2] 完成：{symbol} {freq} 行数={len(df_bars)} adjust={adjust} category={category}",
        )
        return True

    except Exception as e:
        _LOG.error(
            f"[F2] 执行异常：{symbol} {freq} adjust={adjust}, error={e}",
            exc_info=True,
        )
        return False


# ==============================================================================
# F3: FUND_INTRADAY_UNADJ - 基金分时不复权（复用 ensure helper）
# ==============================================================================


async def run_fund_intraday_unadj(
    symbol: str,
    freq: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    """
    基金分时不复权 K 线配方（F3）

    返回：
      True  → 实际写入（本次进行了远程拉取+写库）
      False → 无缺口 / 非 fund / 不支持 freq / 异常
    """
    cls = _get_symbol_class(symbol)
    if cls != "fund":
        _LOG.info(f"[F3] 跳过：{symbol} class={cls} 非 fund", )
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
    if df is None or df.empty:
        return False

    if not from_remote:
        _LOG.info(
            f"[F3] 无缺口：{symbol} {freq} adjust=none，本地已最新（通过 ensure）",
        )
    else:
        _LOG.info(
            f"[F3] 完成：{symbol} {freq} 行数={len(df)} adjust=none（通过 ensure）",
        )

    return from_remote


# ==============================================================================
# F4: FUND_INTRADAY_ADJ - 基金分时复权（内存推算 + 复用 ensure helper）
# ==============================================================================


async def run_fund_intraday_adj(
    symbol: str,
    freq: str,
    adjust: str,
    force_fetch: bool = False,
    trace_id: Optional[str] = None,
) -> bool:
    """
    基金分时复权 K 线配方（F4 · 复用 ensure helper + 内存推算）

    行为：
      1) 仅对最终产物 D3 (symbol, freq, adjust) 做缺口判断；
      2) 若有缺口：
           - 通过 _ensure_fund_minutely_unadj_df 确保 D0（分钟不复权）就绪；
           - 通过 _ensure_fund_daily_unadj_df 确保 D1（日线不复权）就绪；
           - 通过 _ensure_fund_daily_adj_df   确保 D2（日线复权）就绪；
         这三个 helper：
           - 本地已完备 → 直接从 DB 读取 DataFrame；
           - 本地不完备 → 远程拉取 + 标准化 + 异步写库，并返回完整 DataFrame。
      3) 在内存中：
           - D1_unadj + D2_adj → 按 date 对齐 → ratio = close_adj / close_unadj；
           - 将 ratio 映射到 D0 的每一根分钟线 → 推算分钟复权价；
      4) 仅将 D3（分钟复权）写入 DB（不在此处 flush），保持异步写入模型。

    返回：
      True  → 本次确实做了推算并写入分钟复权数据
      False → 非 fund / 无缺口 / 依赖数据为空 / 推算异常
    """
    cls = _get_symbol_class(symbol)
    if cls != "fund":
        _LOG.info(f"[F4] 跳过：{symbol} class={cls} 非 fund", )
        return False

    if freq not in ("1m", "5m", "15m", "30m", "60m"):
        _LOG.warning(f"[F4] 不支持的 freq={freq}，仅支持 1m/5m/15m/30m/60m")
        return False

    if adjust not in ("qfq", "hfq"):
        _LOG.warning(f"[F4] 不支持的 adjust={adjust}，仅支持 qfq/hfq")
        return False

    # 先对最终产物 D3（分钟复权）做缺口判断
    has_gap = check_kline_gap_to_current(
        symbol=symbol,
        freq=freq,
        adjust=adjust,
        force_fetch=force_fetch,
    )
    if not has_gap:
        _LOG.info(
            f"[F4] 无缺口：{symbol} {freq} adjust={adjust} 本地已最新，跳过分时复权推算",
        )
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
        extra={
            "symbol": symbol,
            "freq": freq,
            "adjust": adjust,
        },
    )

    try:
        # ============ 1) 准备三类依赖数据（全部在内存） ============
        df_min_unadj, _ = await _ensure_fund_minutely_unadj_df(
            symbol=symbol,
            freq=freq,
            force_fetch=force_fetch,
            trace_id=trace_id,
        )
        df_d_unadj, _ = await _ensure_fund_daily_unadj_df(
            symbol=symbol,
            force_fetch=force_fetch,
            trace_id=trace_id,
        )
        df_d_adj, _ = await _ensure_fund_daily_adj_df(
            symbol=symbol,
            adjust=adjust,
            force_fetch=force_fetch,
            trace_id=trace_id,
        )

        if df_min_unadj is None or df_min_unadj.empty:
            _LOG.warning(f"[F4] 分时不复权数据为空，无法推算复权：{symbol} {freq}")
            return False
        if df_d_unadj is None or df_d_unadj.empty:
            _LOG.warning(f"[F4] 日线不复权数据为空，无法推算复权：{symbol}")
            return False
        if df_d_adj is None or df_d_adj.empty:
            _LOG.warning(
                f"[F4] 日线复权数据为空，无法推算复权：{symbol} adjust={adjust}"
            )
            return False

        # ============ 2) 在内存中推算日线比值 ratio(date) ============
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

        df_ratio = df_ratio[
            (df_ratio["close_unadj"] > 0)
            & df_ratio["close_adj"].notna()
        ].copy()

        if df_ratio.empty:
            _LOG.warning(f"[F4] 无有效日线比值记录，无法推算分时复权价：{symbol}")
            return False

        df_ratio["ratio"] = df_ratio["close_adj"] / df_ratio["close_unadj"]
        ratio_map = {
            int(row["date"]): float(row["ratio"])
            for _, row in df_ratio.iterrows()
        }

        # ============ 3) 将日线比值映射到分钟线，推算分时复权 D3 ============
        df_min_unadj = df_min_unadj.copy()
        df_min_unadj["date"] = df_min_unadj["ts"].apply(to_yyyymmdd)
        df_min_unadj["ratio"] = df_min_unadj["date"].map(ratio_map).fillna(1.0)

        df_min_adj = df_min_unadj.copy()
        for col in ("open", "high", "low", "close"):
            df_min_adj[col] = df_min_adj[col] * df_min_adj["ratio"]

        df_min_adj = df_min_adj.drop(columns=["date", "ratio"],
                                     errors="ignore")

        if df_min_adj.empty:
            _LOG.warning(f"[F4] 分时复权推算结果为空：{symbol} {freq} adjust={adjust}")
            return False

        # ============ 4) 仅写入分钟复权 D3（依赖数据已由 ensure 写库）===========
        await _save_bars_df(
            df_bars=df_min_adj,
            symbol=symbol,
            freq=freq,
            adjust=adjust,
            source="derived.fund_intraday_adj",
        )

        _LOG.info(
            f"[F4] 完成基金分时复权推算：{symbol} {freq} adjust={adjust} "
            f"分时行数={len(df_min_adj)}",
        )
        return True

    except Exception as e:
        _LOG.error(
            f"[F4] 执行异常：{symbol} {freq} adjust={adjust}, error={e}",
            exc_info=True,
        )
        return False