# backend/services/normalizer/factors.py
# ==============================
# 复权因子标准化
#
# 职责：
#   - 将 TDX 本地 gbbq category=1 原始事件表
#   - 结合本地原始日线 candles_day_raw
#   - 标准化为 adj_factors ready-to-write DataFrame
#
# 输出字段：
#   - date
#   - qfq_factor
#   - hfq_factor
#
# 说明：
#   - 这里只服务最终正式因子链路
#   - 不再承载 baostock 因子标准化
# ==============================

from __future__ import annotations

from typing import Optional, Dict, List

import pandas as pd

from backend.utils.logger import get_logger
from backend.utils.dataframe import normalize_dataframe
from backend.utils.time import parse_yyyymmdd, to_yyyymmdd

_LOG = get_logger("normalizer.factors")

def normalize_tdx_gbbq_adj_factors_df(
    events_df: pd.DataFrame,
    day_df: pd.DataFrame,
    *,
    symbol: str,
    market: str,
) -> Optional[pd.DataFrame]:
    """
    将 TDX 本地 gbbq category=1 原始事件表 + 本地日线收盘价
    标准化为 adj_factors ready-to-write DataFrame。

    强规则：
      - 若某个事件找不到事件日前最近一根日线收盘价，则直接抛错
      - 不猜值，不静默跳过
    """
    if events_df is None or events_df.empty:
        return pd.DataFrame(columns=["date", "qfq_factor", "hfq_factor"])

    if day_df is None or day_df.empty:
        raise ValueError(f"LOCAL_PRICE_DEPENDENCY_MISSING: day bars empty for {market}.{symbol}")

    e = normalize_dataframe(events_df)
    d = normalize_dataframe(day_df)

    if e is None or e.empty:
        return pd.DataFrame(columns=["date", "qfq_factor", "hfq_factor"])
    if d is None or d.empty:
        raise ValueError(f"LOCAL_PRICE_DEPENDENCY_MISSING: day bars empty for {market}.{symbol}")

    required_event_cols = [
        "market",
        "symbol",
        "date",
        "cash_dividend_per_10",
        "rights_price",
        "bonus_share_per_10",
        "rights_share_per_10",
    ]
    missing_event = [c for c in required_event_cols if c not in e.columns]
    if missing_event:
        raise ValueError(f"tdx gbbq factor normalize missing event columns: {missing_event}")

    required_day_cols = ["ts", "close"]
    missing_day = [c for c in required_day_cols if c not in d.columns]
    if missing_day:
        raise ValueError(f"tdx gbbq factor normalize missing day columns: {missing_day}")

    market_u = str(market or "").strip().upper()
    symbol_s = str(symbol or "").strip()

    e = e.copy()
    e["market"] = e["market"].astype(str).str.strip().str.upper()
    e["symbol"] = e["symbol"].astype(str).str.strip()
    e = e[(e["market"] == market_u) & (e["symbol"] == symbol_s)].copy()

    if e.empty:
        return pd.DataFrame(columns=["date", "qfq_factor", "hfq_factor"])

    e["date"] = e["date"].apply(parse_yyyymmdd).astype(int)
    e = e.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)

    d = d.copy()
    d["trade_date"] = d["ts"].apply(lambda x: to_yyyymmdd(int(x)))
    d = d.drop_duplicates(subset=["trade_date"], keep="last").sort_values("trade_date").reset_index(drop=True)

    if d.empty:
        raise ValueError(f"LOCAL_PRICE_DEPENDENCY_MISSING: no valid day rows for {market_u}.{symbol_s}")

    records: List[Dict[str, float | int]] = []
    hfq_cum = 1.0

    day_dates = d["trade_date"].tolist()
    day_closes = d["close"].tolist()

    for _, row in e.iterrows():
        event_date = int(row["date"])

        prev_close = None
        for i in range(len(day_dates) - 1, -1, -1):
            if int(day_dates[i]) < event_date:
                try:
                    prev_close = float(day_closes[i])
                except Exception:
                    prev_close = None
                break

        if prev_close is None:
            raise ValueError(
                f"LOCAL_PRICE_DEPENDENCY_MISSING: previous close not found before event_date={event_date} "
                f"for {market_u}.{symbol_s}"
            )

        cash_dividend_per_share = float(row.get("cash_dividend_per_10") or 0.0) / 10.0
        rights_price = float(row.get("rights_price") or 0.0)
        bonus_share_per_share = float(row.get("bonus_share_per_10") or 0.0) / 10.0
        rights_share_per_share = float(row.get("rights_share_per_10") or 0.0) / 10.0

        denominator = 1.0 + bonus_share_per_share + rights_share_per_share
        if denominator <= 0:
            raise ValueError(
                f"INVALID_ADJ_EVENT_DENOMINATOR: date={event_date} market={market_u} symbol={symbol_s}"
            )

        ex_price = (
            prev_close
            - cash_dividend_per_share
            + rights_price * rights_share_per_share
        ) / denominator

        if ex_price <= 0:
            raise ValueError(
                f"INVALID_ADJ_EVENT_EX_PRICE: date={event_date} market={market_u} symbol={symbol_s} ex_price={ex_price}"
            )

        single_hfq_multiplier = prev_close / ex_price
        hfq_cum *= float(single_hfq_multiplier)

        records.append({
            "date": event_date,
            "hfq_factor": float(hfq_cum),
        })

    if not records:
        return pd.DataFrame(columns=["date", "qfq_factor", "hfq_factor"])

    out = pd.DataFrame(records).sort_values("date").reset_index(drop=True)

    latest_hfq = float(out["hfq_factor"].iloc[-1])
    if latest_hfq <= 0:
        raise ValueError(f"INVALID_LATEST_HFQ_FACTOR: market={market_u} symbol={symbol_s}")

    out["qfq_factor"] = out["hfq_factor"] / latest_hfq
    out = out[["date", "qfq_factor", "hfq_factor"]].copy()

    _LOG.info(
        "[TDX_GBBQ因子标准化] market=%s symbol=%s rows=%s",
        market_u,
        symbol_s,
        len(out),
    )

    return out