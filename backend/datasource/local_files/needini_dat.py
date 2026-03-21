# backend/datasource/local_files/needini_dat.py
# ==============================
# TDX 本地 needini.dat 文件解析器
#
# 职责：
#   - 解析 hq_cache/needini.dat 中 [Holiday] 段
#   - 返回“除周六周日以外的节假日休市日期”原始表
#   - 提供文件中包含的最晚年份
#
# 输出字段：
#   - date : YYYYMMDD 整数
#
# 明确不做：
#   - 不构建完整自然日历
#   - 不判断周六周日
#   - 不写 DB
# ==============================

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

from backend.settings import settings
from backend.utils.logger import get_logger

_LOG = get_logger("local_files.needini_dat")


def _hq_cache_dir() -> Path:
    return Path(settings.tdx_hq_cache_dir).resolve()


def _needini_dat_file_path() -> Path:
    return _hq_cache_dir() / "needini.dat"


def _parse_holiday_lines(lines: List[str]) -> tuple[List[Dict[str, Any]], Optional[int]]:
    rows: List[Dict[str, Any]] = []
    latest_year: Optional[int] = None

    for raw_line in lines:
        line = str(raw_line or "").strip()
        if not line:
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = str(key or "").strip()
        value = str(value or "").strip()

        # 只解析 Y1=..., Y2=... 这种年度定义
        if not key.startswith("Y"):
            continue

        parts = [s.strip() for s in value.split(",") if str(s).strip()]
        if not parts:
            continue

        year_text = parts[0]
        if not year_text.isdigit() or len(year_text) != 4:
            continue

        year = int(year_text)
        if latest_year is None or year > latest_year:
            latest_year = year

        for mmdd in parts[1:]:
            s = str(mmdd or "").strip()
            if not s or not s.isdigit() or len(s) != 4:
                continue

            month = int(s[:2])
            day = int(s[2:4])

            if not (1 <= month <= 12 and 1 <= day <= 31):
                continue

            ymd = year * 10000 + month * 100 + day
            rows.append({"date": ymd})

    return rows, latest_year


def load_needini_holidays_df() -> pd.DataFrame:
    """
    解析 needini.dat 的 [Holiday] 段，返回节假日休市日期原始表。

    文件格式示例：
      [Holiday]
      NUM=36
      Y1=1991,0101,0215,0218,0501,1001,1002,
      ...
      Y36=2026,0101,0102,0216,...

    返回：
      DataFrame(columns=['date'])
      - date 为 YYYYMMDD 整数
      - 仅包含 needini.dat 中显式记录的“非周末节假日休市日”
    """
    path = _needini_dat_file_path()
    if not path.exists():
        raise FileNotFoundError(f"needini.dat not found: {path}")

    text = path.read_text(encoding="gbk", errors="ignore")

    in_holiday = False
    holiday_lines: List[str] = []

    for raw_line in text.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue

        if line.startswith("[") and line.endswith("]"):
            in_holiday = (line.lower() == "[holiday]")
            continue

        if in_holiday:
            holiday_lines.append(line)

    rows, latest_year = _parse_holiday_lines(holiday_lines)

    if not rows:
        return pd.DataFrame(columns=["date"])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)

    _LOG.info(
        "[TDX][NEEDINI_DAT] parsed holidays rows=%s latest_year=%s file=%s",
        len(df),
        latest_year,
        str(path),
    )
    return df


def get_needini_latest_year() -> int:
    """
    获取 needini.dat [Holiday] 段中定义的最晚年份。

    Returns:
        int: 最晚年份

    Raises:
        ValueError: 文件中未解析出任何有效年度定义
    """
    path = _needini_dat_file_path()
    if not path.exists():
        raise FileNotFoundError(f"needini.dat not found: {path}")

    text = path.read_text(encoding="gbk", errors="ignore")

    in_holiday = False
    holiday_lines: List[str] = []

    for raw_line in text.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue

        if line.startswith("[") and line.endswith("]"):
            in_holiday = (line.lower() == "[holiday]")
            continue

        if in_holiday:
            holiday_lines.append(line)

    _, latest_year = _parse_holiday_lines(holiday_lines)
    if latest_year is None:
        raise ValueError(f"needini.dat contains no valid holiday year definitions: {path}")

    return latest_year
