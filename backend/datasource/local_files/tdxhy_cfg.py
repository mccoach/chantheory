# backend/datasource/local_files/tdxhy_cfg.py
# ==============================
# TDX 本地 tdxhy.cfg 文件解析器
#
# 职责：
#   - 解析 hq_cache/tdxhy.cfg
#   - 返回证券 -> 行业代码映射原始表
#
# 输出字段：
#   - market_id   : '0'/'1'/'2'
#   - symbol      : 证券代码
#   - tdx_industry_code : T代码，如 T1001 / T030501
#   - csi_industry_code : X代码，如 X500102 / X210101
#
# 明确不做：
#   - 不与 tdxzs3.cfg 合并
#   - 不做行业名称映射
#   - 不写 DB
# ==============================

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from backend.settings import settings
from backend.utils.logger import get_logger

_LOG = get_logger("local_files.tdxhy_cfg")


def _hq_cache_dir() -> Path:
    return Path(settings.tdx_hq_cache_dir).resolve()


def _tdxhy_cfg_file_path() -> Path:
    return _hq_cache_dir() / "tdxhy.cfg"


def load_tdxhy_cfg_df() -> pd.DataFrame:
    """
    解析 tdxhy.cfg，返回证券 -> 行业代码映射原始表。

    文件格式（GBK 文本，| 分隔）：
      市场ID|证券代码|T代码|空|空|X代码
      例如：
        0|000001|T1001|||X500102
        1|600519|T030501|||X210101
        2|920000|T040202|||X260302

    输出字段：
      - market_id
      - symbol
      - tdx_industry_code
      - csi_industry_code
    """
    path = _tdxhy_cfg_file_path()
    if not path.exists():
        raise FileNotFoundError(f"tdxhy.cfg not found: {path}")

    text = path.read_text(encoding="gbk", errors="ignore")
    rows: List[Dict[str, Any]] = []

    for raw_line in text.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue

        parts = line.split("|")
        if len(parts) < 6:
            continue

        market_id = str(parts[0] or "").strip()
        symbol = str(parts[1] or "").strip()
        t_code = str(parts[2] or "").strip()
        x_code = str(parts[5] or "").strip()

        if not market_id or not symbol:
            continue

        rows.append({
            "market_id": market_id,
            "symbol": symbol,
            "tdx_industry_code": t_code or None,
            "csi_industry_code": x_code or None,
        })

    if not rows:
        return pd.DataFrame(columns=[
            "market_id", "symbol", "tdx_industry_code", "csi_industry_code"
        ])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["market_id", "symbol"], keep="last").reset_index(drop=True)

    _LOG.info("[TDX][TDXHY_CFG] parsed rows=%s file=%s", len(df), str(path))
    return df
