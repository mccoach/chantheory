# backend/datasource/local_files/infoharbor_block_dat.py
# ==============================
# TDX 本地 infoharbor_block.dat 文件解析器
#
# 职责：
#   - 解析 hq_cache/infoharbor_block.dat
#   - 返回板块成分原始表
#
# 当前输出字段：
#   - block_type   : GN / FG / ZS
#   - block_name   : 板块名称
#   - market_id    : '0'/'1'/'2'
#   - symbol       : 成分证券代码
#
# 明确不做：
#   - 不做 concepts 聚合
#   - 不做业务过滤（是否只取 GN 由上层决定）
#   - 不写 DB
# ==============================

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from backend.settings import settings
from backend.utils.logger import get_logger

_LOG = get_logger("local_files.infoharbor_block_dat")


def _hq_cache_dir() -> Path:
    return Path(settings.tdx_hq_cache_dir).resolve()


def _infoharbor_block_dat_file_path() -> Path:
    return _hq_cache_dir() / "infoharbor_block.dat"


def load_infoharbor_block_df() -> pd.DataFrame:
    """
    解析 infoharbor_block.dat，返回板块成分原始表。

    文件结构（GBK 文本）：
      #TYPE_名称,成分股数,板块代码,起始日期,结束日期,,
      市场#代码,市场#代码,...
      其中：
        TYPE:
          - GN = 概念
          - FG = 风格
          - ZS = 指数成分
        市场编号：
          - 0 = 深
          - 1 = 沪
          - 2 = 北
    """
    path = _infoharbor_block_dat_file_path()
    if not path.exists():
        raise FileNotFoundError(f"infoharbor_block.dat not found: {path}")

    text = path.read_bytes().decode("gbk", errors="ignore")

    rows: List[Dict[str, Any]] = []
    current_block_type = ""
    current_block_name = ""
    current_members: List[str] = []

    def _flush_current():
        nonlocal rows, current_block_type, current_block_name, current_members

        if not current_block_name or not current_members:
            current_members = []
            return

        for member in current_members:
            item = str(member or "").strip()
            if not item or "#" not in item:
                continue
            try:
                market_id, symbol = item.split("#", 1)
            except ValueError:
                continue

            market_id = str(market_id or "").strip()
            symbol = str(symbol or "").strip()
            if not market_id or not symbol:
                continue

            rows.append({
                "block_type": current_block_type or None,
                "block_name": current_block_name or None,
                "market_id": market_id,
                "symbol": symbol,
            })

        current_members = []

    for raw_line in text.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue

        if line.startswith("#"):
            _flush_current()

            header = line[1:]
            header_parts = header.split(",")
            raw_name = str(header_parts[0] or "").strip()

            if "_" in raw_name:
                prefix, name = raw_name.split("_", 1)
            else:
                prefix, name = "", raw_name

            current_block_type = prefix.strip()
            current_block_name = name.strip()
            current_members = []
        else:
            members = [s.strip() for s in line.split(",") if str(s).strip()]
            current_members.extend(members)

    _flush_current()

    if not rows:
        return pd.DataFrame(columns=["block_type", "block_name", "market_id", "symbol"])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(
        subset=["block_type", "block_name", "market_id", "symbol"],
        keep="last",
    ).reset_index(drop=True)

    _LOG.info("[TDX][INFOHARBOR_BLOCK] parsed rows=%s file=%s", len(df), str(path))
    return df
