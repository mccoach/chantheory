# backend/datasource/local_files/tdxzs3_cfg.py
# ==============================
# TDX 本地 tdxzs3.cfg 文件解析器
#
# 职责：
#   - 解析 hq_cache/tdxzs3.cfg
#   - 返回板块定义原始表
#
# 输出字段：
#   - block_name
#   - block_code
#   - category_type
#   - sub_type
#   - level_flag
#   - extra_code
#
# 说明：
#   - 其中：
#       * category_type='2'  表示通达信行业
#       * category_type='12' 表示中证行业
#       * category_type='3'  表示地域
#
# 明确不做：
#   - 不与 tdxhy.cfg / base.dbf 合并
#   - 不做业务分类
#   - 不写 DB
# ==============================

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from backend.settings import settings
from backend.utils.logger import get_logger

_LOG = get_logger("local_files.tdxzs3_cfg")


def _hq_cache_dir() -> Path:
    return Path(settings.tdx_hq_cache_dir).resolve()


def _tdxzs3_cfg_file_path() -> Path:
    return _hq_cache_dir() / "tdxzs3.cfg"


def load_tdxzs3_cfg_df() -> pd.DataFrame:
    """
    解析 tdxzs3.cfg，返回板块定义原始表。

    文件格式（GBK 文本，| 分隔）：
      板块名称|板块代码|分类体系|子类型|层级标志|关联编码
      例如：
        银行|880471|2|1|1|T1001
        股份行|881388|12|1|1|X500102
        深圳板块|880218|3|1|0|18
    """
    path = _tdxzs3_cfg_file_path()
    if not path.exists():
        raise FileNotFoundError(f"tdxzs3.cfg not found: {path}")

    text = path.read_text(encoding="gbk", errors="ignore")
    rows: List[Dict[str, Any]] = []

    for raw_line in text.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue

        parts = line.split("|")
        if len(parts) < 6:
            continue

        rows.append({
            "block_name": str(parts[0] or "").strip(),
            "block_code": str(parts[1] or "").strip(),
            "category_type": str(parts[2] or "").strip(),
            "sub_type": str(parts[3] or "").strip(),
            "level_flag": str(parts[4] or "").strip(),
            "extra_code": str(parts[5] or "").strip(),
        })

    if not rows:
        return pd.DataFrame(columns=[
            "block_name", "block_code", "category_type",
            "sub_type", "level_flag", "extra_code"
        ])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["category_type", "extra_code", "block_code"], keep="last").reset_index(drop=True)

    _LOG.info("[TDX][TDXZS3_CFG] parsed rows=%s file=%s", len(df), str(path))
    return df
