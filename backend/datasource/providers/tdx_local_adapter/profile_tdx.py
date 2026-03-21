# backend/datasource/providers/tdx_local_adapter/profile_tdx.py
# ==============================
# 通达信本地文件适配器 - profile_snapshot
#
# 职责：
#   1. 调用本地文件解析层：
#       - base.dbf（主表）
#       - tnf（补昨收/名称）
#       - tdxhy.cfg
#       - tdxzs3.cfg
#       - infoharbor_block.dat
#   2. 在 provider 层完成“profile 原始快照表”的组装
#   3. 返回统一原始 DataFrame
#
# 关键原则：
#   - profile 必须以 base.dbf 为主线
#   - 只有 base.dbf 中存在的 (symbol, market) 才允许进入 symbol_profile
#   - tnf / cfg / block 全部只是补充信息
#
# 明确不做：
#   - 不做最终字段标准化
#   - 不做行业/地域名称解释（这些属于 normalizer 层）
#   - 不写 DB
#   - 不发 SSE
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, List, Any

import pandas as pd

from backend.datasource.local_files import (
    load_tnf_df,
    load_base_dbf_df_sync,
    load_tdxhy_cfg_df,
    load_tdxzs3_cfg_df,
    load_infoharbor_block_df,
)
from backend.utils.logger import get_logger

_LOG = get_logger("tdx_local_adapter.profile")


def _market_text_to_market_id(market: str) -> str:
    m = str(market or "").strip().upper()
    if m == "SZ":
        return "0"
    if m == "SH":
        return "1"
    if m == "BJ":
        return "2"
    return ""


def _market_id_to_market_text(market_id: str) -> str:
    s = str(market_id or "").strip()
    if s == "0":
        return "SZ"
    if s == "1":
        return "SH"
    if s == "2":
        return "BJ"
    return ""


def _build_concepts_map(df_block: pd.DataFrame) -> Dict[tuple, List[str]]:
    """
    仅提取 GN 概念板块，构建：
      (market, symbol) -> [concept1, concept2, ...]
    """
    result: Dict[tuple, List[str]] = {}

    if df_block is None or df_block.empty:
        return result

    df = df_block.copy()
    df = df[df["block_type"].astype(str).str.upper() == "GN"].copy()
    if df.empty:
        return result

    for _, row in df.iterrows():
        market = _market_id_to_market_text(row.get("market_id"))
        symbol = str(row.get("symbol") or "").strip()
        concept = str(row.get("block_name") or "").strip()

        if not market or not symbol or not concept:
            continue

        key = (market, symbol)
        result.setdefault(key, [])
        if concept not in result[key]:
            result[key].append(concept)

    return result


def _build_tnf_lookup() -> Dict[tuple, Dict[str, Any]]:
    """
    构建：
      (market, symbol) -> {name, prev_close, pinyin, ...}
    """
    df_sh = load_tnf_df("SH")
    df_sz = load_tnf_df("SZ")
    df_bj = load_tnf_df("BJ")

    frames = [df for df in [df_sh, df_sz, df_bj] if df is not None and not df.empty]
    if not frames:
        return {}

    df_tnf = pd.concat(frames, axis=0, ignore_index=True)
    df_tnf = df_tnf.drop_duplicates(subset=["symbol", "market"], keep="last").reset_index(drop=True)

    result: Dict[tuple, Dict[str, Any]] = {}
    for _, row in df_tnf.iterrows():
        market = str(row.get("market") or "").strip().upper()
        symbol = str(row.get("symbol") or "").strip()
        if not market or not symbol:
            continue
        result[(market, symbol)] = dict(row)

    return result


def _build_tdxhy_lookup(df_tdxhy: pd.DataFrame) -> Dict[tuple, Dict[str, Any]]:
    """
    构建：
      (market_id, symbol) -> {tdx_industry_code, csi_industry_code}
    """
    result: Dict[tuple, Dict[str, Any]] = {}

    if df_tdxhy is None or df_tdxhy.empty:
        return result

    for _, row in df_tdxhy.iterrows():
        market_id = str(row.get("market_id") or "").strip()
        symbol = str(row.get("symbol") or "").strip()
        if not market_id or not symbol:
            continue
        result[(market_id, symbol)] = dict(row)

    return result


def _build_profile_snapshot_df_sync() -> pd.DataFrame:
    """
    同步构建全市场 profile 原始快照表。

    关键原则：
      - 以 base.dbf 为唯一主表
      - 只有 base.dbf 中存在的代码，才会进入 profile 原始快照
      - provider 只输出原始字段，不做“代码 -> 中文名”的最终解释
    """
    # 1) 主表：base.dbf
    df_base = load_base_dbf_df_sync()
    if df_base is None or df_base.empty:
        return pd.DataFrame()

    # 2) 其他补充表
    tnf_lookup = _build_tnf_lookup()
    df_tdxhy = load_tdxhy_cfg_df()
    df_tdxzs3 = load_tdxzs3_cfg_df()
    df_block = load_infoharbor_block_df()

    # 3) 原始补充索引
    concepts_map = _build_concepts_map(df_block)
    tdxhy_lookup = _build_tdxhy_lookup(df_tdxhy)

    # 4) 保留 tdxzs3 原始表，交给 normalizer 做最终解释
    #    这里 provider 不再做行业/地域中文解释
    has_tdxzs3 = df_tdxzs3 is not None and not df_tdxzs3.empty

    # 5) 逐条组装
    records: List[Dict[str, Any]] = []
    for _, row in df_base.iterrows():
        market = str(row.get("market") or "").strip().upper()
        symbol = str(row.get("symbol") or "").strip()

        if not market or not symbol:
            continue

        market_id = _market_text_to_market_id(market)
        tnf_item = tnf_lookup.get((market, symbol), {})
        hy_item = tdxhy_lookup.get((market_id, symbol), {})

        prev_close = tnf_item.get("prev_close")
        try:
            prev_close = float(prev_close) if prev_close is not None else None
        except Exception:
            prev_close = None

        t_code = str(hy_item.get("tdx_industry_code") or "").strip()
        x_code = str(hy_item.get("csi_industry_code") or "").strip()
        dbf_hy_code = str(row.get("industry_code_raw") or "").strip()
        region_code = str(row.get("region_code") or "").strip()

        concepts = concepts_map.get((market, symbol), [])

        records.append({
            "symbol": symbol,
            "market": market,
            "market_id": market_id,
            "name": tnf_item.get("name"),
            "listing_date": row.get("listing_date"),
            "prev_close": prev_close,
            "float_shares_raw": row.get("float_shares_raw"),
            "total_shares_raw": row.get("total_shares_raw"),
            "region_code": region_code or None,
            "industry_code_raw": dbf_hy_code or None,
            "industry_t_code": t_code or None,
            "industry_x_code": x_code or None,
            "fund_nav_raw": row.get("fund_nav_raw"),
            "concepts": concepts,
            # 让 normalizer 知道可以从哪套字典解释
            "has_tdxzs3_support": bool(has_tdxzs3),
        })

    if not records:
        return pd.DataFrame()

    out = pd.DataFrame(records)

    # 严格仅保留 base.dbf 主表中的有效代码，不做空白占位补表
    out = out.drop_duplicates(subset=["symbol", "market"], keep="last").reset_index(drop=True)

    _LOG.info("[TDX][PROFILE] built raw snapshot rows=%s (base.dbf as master)", len(out))
    return out


async def get_profile_snapshot_tdx() -> pd.DataFrame:
    return await asyncio.to_thread(_build_profile_snapshot_df_sync)
