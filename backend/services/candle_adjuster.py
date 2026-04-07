# backend/services/candle_adjuster.py
# ==============================
# 统一复权应用层
#
# 职责：
#   - 接收基础 bars 与本地 factor
#   - 输出最终复权 bars
#   - 支持安全降级：
#       * 请求 qfq/hfq 但 factor 不可用时
#       * 返回原始 bars
#       * actual_adjust=none
# ==============================

from __future__ import annotations

from typing import Dict, Any, Tuple, Optional
import pandas as pd

from backend.db.factors import select_factors
from backend.utils.time import to_yyyymmdd


def apply_adjustment(
    *,
    market: str,
    code: str,
    bars_df: pd.DataFrame,
    request_adjust: str,
) -> Tuple[pd.DataFrame, str, str]:
    """
    Returns:
        (result_df, actual_adjust, message)
    """
    req = str(request_adjust or "none").strip().lower()
    if req not in ("none", "qfq", "hfq"):
        req = "none"

    if bars_df is None or bars_df.empty:
        return pd.DataFrame(), "none", ""

    if req == "none":
        return bars_df.copy(), "none", ""

    factor_rows = select_factors(symbol=code, start_date=None, end_date=None)
    if not factor_rows:
        return (
            bars_df.copy(),
            "none",
            "复权因子不可用，已安全降级返回不复权数据",
        )

    fdf = pd.DataFrame(factor_rows)
    if fdf.empty or "date" not in fdf.columns:
        return (
            bars_df.copy(),
            "none",
            "复权因子不可用，已安全降级返回不复权数据",
        )

    factor_map = {}
    for _, row in fdf.iterrows():
        d = int(row["date"])
        factor_map[d] = {
            "qfq_factor": row.get("qfq_factor"),
            "hfq_factor": row.get("hfq_factor"),
        }

    df = bars_df.copy()
    if "ts" not in df.columns:
        return (
            bars_df.copy(),
            "none",
            "复权因子不可用，已安全降级返回不复权数据",
        )

    factors = []
    for ts in df["ts"].tolist():
        ymd = to_yyyymmdd(int(ts))
        f_item = _pick_latest_factor_not_after(factor_map, ymd)
        factors.append(f_item)

    factor_col = "qfq_factor" if req == "qfq" else "hfq_factor"

    usable = True
    numeric_factors = []
    for item in factors:
        if not item or item.get(factor_col) in (None, "", "-", "--"):
            usable = False
            numeric_factors.append(None)
        else:
            try:
                numeric_factors.append(float(item[factor_col]))
            except Exception:
                usable = False
                numeric_factors.append(None)

    if not usable:
        return (
            bars_df.copy(),
            "none",
            "复权因子不完整，已安全降级返回不复权数据",
        )

    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = [
                float(v) * float(fa) if v is not None and fa is not None else v
                for v, fa in zip(df[col].tolist(), numeric_factors)
            ]

    return df, req, ""


def _pick_latest_factor_not_after(factor_map: Dict[int, Dict[str, Any]], ymd: int) -> Optional[Dict[str, Any]]:
    if not factor_map:
        return None
    candidates = [d for d in factor_map.keys() if int(d) <= int(ymd)]
    if not candidates:
        return None
    latest = max(candidates)
    return factor_map.get(latest)
