# backend/datasource/providers/tdx_remote_adapter/bars.py
# ==============================
# TDX 远程 bars 原子接口
#
# 职责：
#   - 对上层提供最小原子拉取函数
#   - 内部负责：
#       * 连接 TDX 远程
#       * 发送 security/index bars 请求
#       * 解析原始 body
#       * 返回 DataFrame
#
# 当前正式 category：
#   - 1d -> 4
#   - 5m -> 0
#   - 1m -> 8
# ==============================

from __future__ import annotations

import asyncio
import pandas as pd

from backend.datasource.providers.tdx_remote_adapter.client import TdxRemoteClient
from backend.datasource.providers.tdx_remote_adapter.protocol import (
    build_security_bars_request,
    build_index_bars_request,
    parse_security_bars_body,
    parse_index_bars_body,
)
from backend.datasource.providers.tdx_remote_adapter.router import decide_tdx_bars_route
from backend.utils.logger import get_logger

_LOG = get_logger("tdx_remote_adapter.bars")


def _market_text_to_tdx_market(market: str) -> int:
    m = str(market or "").strip().upper()
    if m == "SZ":
        return 0
    if m == "SH":
        return 1
    if m == "BJ":
        raise ValueError("BJ market mapping for TDX remote bars is not supported in current stage")
    raise ValueError(f"unsupported market text for TDX remote bars: {market}")


def _fetch_bars_sync(
    *,
    route_kind: str,
    category: int,
    market: str,
    symbol: str,
    start: int,
    count: int,
) -> pd.DataFrame:
    market_int = _market_text_to_tdx_market(market)

    with TdxRemoteClient() as client:
        client.connect()

        if route_kind == "security_bars":
            req = build_security_bars_request(
                category=category,
                market=market_int,
                code=symbol,
                start=start,
                count=count,
            )
            body = client.request_raw(req)
            rows = parse_security_bars_body(body, category=category)
        elif route_kind == "index_bars":
            req = build_index_bars_request(
                category=category,
                market=market_int,
                code=symbol,
                start=start,
                count=count,
            )
            body = client.request_raw(req)
            rows = parse_index_bars_body(body, category=category)
        else:
            raise ValueError(f"unsupported route_kind: {route_kind}")

    return pd.DataFrame(rows) if rows else pd.DataFrame()


async def get_security_bars_tdx_remote(
    *,
    category: int,
    market: str,
    symbol: str,
    start: int,
    count: int,
) -> pd.DataFrame:
    return await asyncio.to_thread(
        _fetch_bars_sync,
        route_kind="security_bars",
        category=category,
        market=market,
        symbol=symbol,
        start=start,
        count=count,
    )


async def get_index_bars_tdx_remote(
    *,
    category: int,
    market: str,
    symbol: str,
    start: int,
    count: int,
) -> pd.DataFrame:
    return await asyncio.to_thread(
        _fetch_bars_sync,
        route_kind="index_bars",
        category=category,
        market=market,
        symbol=symbol,
        start=start,
        count=count,
    )


async def get_auto_routed_bars_tdx_remote(
    *,
    category: int,
    market: str,
    symbol: str,
    start: int,
    count: int,
) -> pd.DataFrame:
    route_kind = decide_tdx_bars_route(symbol=symbol, market=market)
    return await asyncio.to_thread(
        _fetch_bars_sync,
        route_kind=route_kind,
        category=category,
        market=market,
        symbol=symbol,
        start=start,
        count=count,
    )
