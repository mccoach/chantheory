# backend/services/minute_archive/store.py
# ==============================
# 分钟线累积归档 - 存储路径与文件读写
#
# 职责：
#   - 解析分钟归档文件路径
#   - 读取归档原始二进制
#   - 原子写入新归档文件
#   - 归档文件尾部完整性保护
#   - 直接追加新增分钟记录
#
# 当前目录结构：
#   {archive_root}/{market_lower}/{lc1|lc5}/{market_lower}{symbol}.{lc1|lc5}
#
# 示例：
#   var/minute_archive/sh/lc1/sh600519.lc1
#   var/minute_archive/sz/lc5/sz000001.lc5
#
# 设计原则（最终版）：
#   - 归档一旦成功写入，即视为连续且可信
#   - 更新归档时不全量解析旧文件，只读取首条/尾条记录与必要原始 bytes
#   - 右补采用 append，风险仅存在于文件尾部
#   - 因此只保留 old_last 尾部完整性保护，不做 old_first 完整性校验
#   - 若发现文件尾部存在不完整残片或尾记录结构异常：
#       * 自动回退到上一条合法记录
#       * 截断非法尾部
# ==============================

from __future__ import annotations

from pathlib import Path
from typing import Optional, Callable, Dict, Any

from backend.settings import settings
from backend.utils.logger import get_logger
from backend.services.minute_archive.codec import get_suffix_by_freq

_LOG = get_logger("minute_archive.store")

_RECORD_SIZE = 32


def _market_lower(market: str) -> str:
    m = str(market or "").strip().upper()
    if m not in ("SH", "SZ", "BJ"):
        raise ValueError(f"invalid market for minute archive path: {market}")
    return m.lower()


def _subdir_by_freq(freq: str) -> str:
    suffix = get_suffix_by_freq(freq)
    if suffix == ".lc1":
        return "lc1"
    if suffix == ".lc5":
        return "lc5"
    raise ValueError(f"invalid minute archive freq: {freq}")


def resolve_minute_archive_path(
    *,
    market: str,
    symbol: str,
    freq: str,
) -> Path:
    m_lower = _market_lower(market)
    s = str(symbol or "").strip()
    if not s or not s.isdigit():
        raise ValueError(f"invalid symbol for minute archive path: {symbol}")

    suffix = get_suffix_by_freq(freq)
    subdir = _subdir_by_freq(freq)

    root = Path(settings.tdx_minute_archive_dir).resolve()
    out_dir = root / m_lower / subdir
    file_name = f"{m_lower}{s}{suffix}"
    return out_dir / file_name


def read_archive_bytes(path: Path) -> bytes:
    p = Path(path).resolve()
    if not p.exists():
        return b""
    raw = p.read_bytes()
    return raw or b""


def atomic_write_archive_bytes(path: Path, raw: bytes) -> None:
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "wb") as f:
        f.write(raw or b"")
        f.flush()

    tmp.replace(p)
    _LOG.info("[MINUTE_ARCHIVE] wrote file=%s bytes=%s", str(p), len(raw or b""))


def _truncate_file(path: Path, valid_size: int) -> None:
    p = Path(path).resolve()
    with open(p, "r+b") as f:
        f.truncate(valid_size)
        f.flush()


def sanitize_archive_tail(
    path: Path,
    *,
    tail_validator: Callable[[bytes], bool],
) -> Dict[str, Any]:
    """
    检查归档文件尾部完整性。
    若尾部不是合法记录，则回退到上一条合法记录并截断。

    Args:
        path: 归档文件路径
        tail_validator: 记录合法性判断函数（仅判断单条32字节记录）

    Returns:
        {
          "valid_size": int,
          "trimmed": bool,
          "trim_reason": str | None,
          "old_size": int,
        }
    """
    p = Path(path).resolve()
    if not p.exists():
        return {
            "valid_size": 0,
            "trimmed": False,
            "trim_reason": None,
            "old_size": 0,
        }

    size = int(p.stat().st_size or 0)
    if size <= 0:
        return {
            "valid_size": 0,
            "trimmed": False,
            "trim_reason": None,
            "old_size": 0,
        }

    old_size = size
    trimmed = False
    trim_reason: Optional[str] = None

    # 先按 32 字节边界去掉显然不完整的尾残片
    valid_size = (size // _RECORD_SIZE) * _RECORD_SIZE
    if valid_size != size:
        _truncate_file(p, valid_size)
        _LOG.warning(
            "[MINUTE_ARCHIVE] truncated incomplete tail residue file=%s old_bytes=%s valid_bytes=%s",
            str(p),
            size,
            valid_size,
        )
        size = valid_size
        trimmed = True
        trim_reason = "INCOMPLETE_TAIL_RESIDUE"

    # 再按记录结构回退到最后一条合法记录
    if size <= 0:
        return {
            "valid_size": 0,
            "trimmed": trimmed,
            "trim_reason": trim_reason,
            "old_size": old_size,
        }

    with open(p, "rb") as f:
        current_size = size
        while current_size >= _RECORD_SIZE:
            f.seek(current_size - _RECORD_SIZE)
            raw = f.read(_RECORD_SIZE)
            if raw and len(raw) == _RECORD_SIZE and tail_validator(raw):
                break
            current_size -= _RECORD_SIZE

    if current_size != size:
        _truncate_file(p, current_size)
        _LOG.warning(
            "[MINUTE_ARCHIVE] truncated invalid tail records file=%s old_bytes=%s valid_bytes=%s",
            str(p),
            size,
            current_size,
        )
        trimmed = True
        trim_reason = "INVALID_TAIL_RECORDS"

    return {
        "valid_size": current_size,
        "trimmed": trimmed,
        "trim_reason": trim_reason,
        "old_size": old_size,
    }


def read_first_record_bytes(path: Path) -> Optional[bytes]:
    """
    读取归档文件第一条完整记录。

    说明：
      - 当前不做 old_first 完整性校验
      - 左补采用原子重建，不直接修改原文件头部
      - 因此这里只做最小职责的首条读取
    """
    p = Path(path).resolve()
    if not p.exists():
        return None

    size = int(p.stat().st_size or 0)
    if size < _RECORD_SIZE:
        return None

    with open(p, "rb") as f:
        raw = f.read(_RECORD_SIZE)

    if not raw or len(raw) != _RECORD_SIZE:
        return None
    return raw


def read_last_record_bytes(
    path: Path,
    *,
    tail_validator: Callable[[bytes], bool],
) -> Optional[bytes]:
    """
    读取归档文件最后一条完整且结构合法的记录。

    说明：
      - 会先做尾部完整性保护
      - 若文件不存在或无合法记录，则返回 None
    """
    p = Path(path).resolve()
    if not p.exists():
        return None

    result = sanitize_archive_tail(p, tail_validator=tail_validator)
    valid_size = int(result.get("valid_size") or 0)
    if valid_size < _RECORD_SIZE:
        return None

    with open(p, "rb") as f:
        f.seek(valid_size - _RECORD_SIZE)
        raw = f.read(_RECORD_SIZE)

    if not raw or len(raw) != _RECORD_SIZE:
        return None
    return raw


def protect_and_read_archive_boundaries(
    path: Path,
    *,
    tail_validator: Callable[[bytes], bool],
) -> Dict[str, Any]:
    """
    对旧归档执行最小保护，并读取首尾边界。

    当前策略：
      - 仅做 old_last 尾部完整性保护
      - 不做 old_first 完整性校验
      - 返回首条、尾条与修剪信息

    Returns:
        {
          "exists": bool,
          "first_raw": bytes | None,
          "last_raw": bytes | None,
          "tail_trimmed": bool,
          "tail_trim_reason": str | None,
          "valid_size": int,
          "old_size": int,
        }
    """
    p = Path(path).resolve()
    if not p.exists():
        return {
            "exists": False,
            "first_raw": None,
            "last_raw": None,
            "tail_trimmed": False,
            "tail_trim_reason": None,
            "valid_size": 0,
            "old_size": 0,
        }

    tail_info = sanitize_archive_tail(p, tail_validator=tail_validator)
    valid_size = int(tail_info.get("valid_size") or 0)

    if valid_size < _RECORD_SIZE:
        return {
            "exists": True,
            "first_raw": None,
            "last_raw": None,
            "tail_trimmed": bool(tail_info.get("trimmed")),
            "tail_trim_reason": tail_info.get("trim_reason"),
            "valid_size": valid_size,
            "old_size": int(tail_info.get("old_size") or 0),
        }

    with open(p, "rb") as f:
        first_raw = f.read(_RECORD_SIZE)
        f.seek(valid_size - _RECORD_SIZE)
        last_raw = f.read(_RECORD_SIZE)

    return {
        "exists": True,
        "first_raw": first_raw if first_raw and len(first_raw) == _RECORD_SIZE else None,
        "last_raw": last_raw if last_raw and len(last_raw) == _RECORD_SIZE else None,
        "tail_trimmed": bool(tail_info.get("trimmed")),
        "tail_trim_reason": tail_info.get("trim_reason"),
        "valid_size": valid_size,
        "old_size": int(tail_info.get("old_size") or 0),
    }


def append_archive_bytes(
    path: Path,
    raw: bytes,
    *,
    tail_validator: Callable[[bytes], bool],
) -> int:
    """
    直接向归档文件末尾追加完整记录 bytes。

    Returns:
        int: 追加字节数
    """
    payload = raw or b""
    if not payload:
        return 0
    if len(payload) % _RECORD_SIZE != 0:
        raise ValueError(
            f"append archive bytes length must be divisible by {_RECORD_SIZE}, got {len(payload)}"
        )

    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    # 追加前先做一次尾部完整性保护
    sanitize_archive_tail(p, tail_validator=tail_validator)

    with open(p, "ab") as f:
        f.write(payload)
        f.flush()

    _LOG.info("[MINUTE_ARCHIVE] appended file=%s bytes=%s", str(p), len(payload))
    return len(payload)
