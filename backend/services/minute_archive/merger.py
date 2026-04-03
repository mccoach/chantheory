# backend/services/minute_archive/merger.py
# ==============================
# 分钟线累积归档 - 通用拼接写入模块（双端超出全集版）
#
# 核心职责：
#   - 接收统一逻辑分钟记录
#   - 标准化清洗（去重 + 排序 + 最后一天占位清洗）
#   - 仅解析旧归档首尾两条记录，不解析中间旧数据
#   - 旧归档只做 old_last 尾部完整性保护
#   - 以“新数据超出旧数据边界的部分”为唯一拼接原则
#
# 最终规则：
#   1) 新数据先去重排序，并删除“最后一天全零占位日”
#   2) 旧归档只读取：
#        - old_first
#        - trimmed_old_last
#      中间旧数据不解析
#   3) 新超出旧的截取：
#        - left_part  = new[key < old_first_key]
#        - right_part = new[key > old_last_key]
#   4) 写入策略：
#        - 左空右空：noop
#        - 左空右非空：append
#        - 左非空右空：原子重建 left + old
#        - 左非空右非空：原子重建 left + old + right
#   5) 缺口 warning：
#        - 左侧普通缺口：
#            next(new_left_part_last) != old_first_key
#            -> MINUTE_ARCHIVE_GAP_LEFT
#        - 右侧普通缺口：
#            old_last 未修剪，且 next(old_last) != new_right_part_first
#            -> MINUTE_ARCHIVE_GAP_RIGHT
#        - 右侧修剪后仍未补齐：
#            old_last 已修剪，且：
#              * right_part 为空，或
#              * next(trimmed_old_last) != new_right_part_first
#            -> MINUTE_ARCHIVE_TRIMMED_GAP_RIGHT
#
# 本轮修复：
#   - final_total_rows 统一由本模块负责返回
#   - 对分钟线来说，无论 created / appended / rewritten / noop，
#     只要任务成功完成，都返回处理后的最终总条数
# ==============================

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from backend.utils.logger import get_logger
from backend.utils.minute_bucket import next_minute_bucket_key
from backend.services.minute_archive.codec import (
    normalize_minute_record,
    decode_record_from_bytes,
    encode_records_to_bytes,
)
from backend.services.minute_archive.store import (
    resolve_minute_archive_path,
    append_archive_bytes,
    atomic_write_archive_bytes,
    read_archive_bytes,
    protect_and_read_archive_boundaries,
)

_LOG = get_logger("minute_archive.merger")

_WARNING_GAP_LEFT = "MINUTE_ARCHIVE_GAP_LEFT"
_WARNING_GAP_RIGHT = "MINUTE_ARCHIVE_GAP_RIGHT"
_WARNING_TRIMMED_GAP_RIGHT = "MINUTE_ARCHIVE_TRIMMED_GAP_RIGHT"

_RECORD_SIZE = 32


def _record_key(rec: Dict[str, Any]) -> Tuple[int, str]:
    return int(rec["date"]), str(rec["time"])


def _is_finite_number(v: Any) -> bool:
    try:
        x = float(v)
    except Exception:
        return False
    return math.isfinite(x)


def _is_valid_decoded_record(rec: Dict[str, Any]) -> bool:
    try:
        low = float(rec["low"])
        high = float(rec["high"])
        open_v = float(rec["open"])
        close_v = float(rec["close"])
        amount_v = float(rec["amount"])
        volume_v = float(rec["volume"])
    except Exception:
        return False

    if not all(_is_finite_number(x) for x in [low, high, open_v, close_v, amount_v, volume_v]):
        return False
    if volume_v < 0:
        return False
    if low > high:
        return False
    if not (low <= open_v <= high):
        return False
    if not (low <= close_v <= high):
        return False
    return True


def _tail_validator_factory(
    *,
    market: str,
    symbol: str,
    freq: str,
):
    def _validator(raw: bytes) -> bool:
        try:
            rec = decode_record_from_bytes(
                raw,
                market=market,
                symbol=symbol,
                freq=freq,
            )
        except Exception:
            return False
        return _is_valid_decoded_record(rec)
    return _validator


def _normalize_and_sort_incoming(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not records:
        return []

    dedup: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for rec in records:
        r = normalize_minute_record(rec)
        dedup[_record_key(r)] = r

    out = list(dedup.values())
    out.sort(key=_record_key)
    return out


def _remove_last_day_placeholder(records: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], bool]:
    """
    只检查最大日期对应的最后一天：
      - 若该日所有记录都满足：
          * volume=0
          * amount=0
        则判为占位整日，全部删除
      - 否则保留该日全部记录
    """
    if not records:
        return [], False

    max_date = max(int(r["date"]) for r in records)
    day_records = [r for r in records if int(r["date"]) == max_date]
    other_records = [r for r in records if int(r["date"]) != max_date]

    if not day_records:
        return records, False

    all_placeholder = True
    for r in day_records:
        try:
            vol_zero = float(r["volume"]) == 0.0
            amt_zero = float(r["amount"]) == 0.0
        except Exception:
            all_placeholder = False
            break

        if not (vol_zero and amt_zero):
            all_placeholder = False
            break

    if not all_placeholder:
        return records, False

    cleaned = other_records
    cleaned.sort(key=_record_key)
    return cleaned, True


def _decode_archive_record(
    *,
    raw: bytes,
    market: str,
    symbol: str,
    freq: str,
    label: str,
) -> Dict[str, Any]:
    rec = decode_record_from_bytes(
        raw,
        market=market,
        symbol=symbol,
        freq=freq,
    )
    if not _is_valid_decoded_record(rec):
        raise ValueError(f"{label} archive record decoded but invalid by structure rules")
    return rec


def _build_gap_left_warning_message(
    *,
    market: str,
    symbol: str,
    freq: str,
    left_last: Dict[str, Any],
    old_first: Dict[str, Any],
    expected_old_first_key: tuple[int, str],
) -> str:
    exp_date, exp_time = expected_old_first_key
    return (
        f"分钟归档左侧拼接存在缺口："
        f"market={market}, symbol={symbol}, freq={freq}, "
        f"new_left_last={left_last['date']} {left_last['time']}, "
        f"expected_old_first={exp_date} {exp_time}, "
        f"old_first={old_first['date']} {old_first['time']}。"
        f"已继续归档，但请人工复核左侧历史窗口完整性。"
    )


def _build_gap_right_warning_message(
    *,
    market: str,
    symbol: str,
    freq: str,
    old_last: Dict[str, Any],
    right_first: Dict[str, Any],
    expected_right_next_key: tuple[int, str],
) -> str:
    exp_date, exp_time = expected_right_next_key
    return (
        f"分钟归档右侧拼接存在缺口："
        f"market={market}, symbol={symbol}, freq={freq}, "
        f"old_last={old_last['date']} {old_last['time']}, "
        f"expected_right_next={exp_date} {exp_time}, "
        f"new_right_first={right_first['date']} {right_first['time']}。"
        f"已继续归档，但请人工复核右侧窗口完整性。"
    )


def _build_trimmed_gap_right_warning_message(
    *,
    market: str,
    symbol: str,
    freq: str,
    old_last: Dict[str, Any],
    expected_right_next_key: tuple[int, str],
    right_first: Optional[Dict[str, Any]],
    trim_reason: Optional[str],
) -> str:
    exp_date, exp_time = expected_right_next_key

    if right_first is None:
        return (
            f"分钟归档旧尾部曾发生异常残留并已自动修剪，但本次没有新的右侧数据补回："
            f"market={market}, symbol={symbol}, freq={freq}, "
            f"trimmed_old_last={old_last['date']} {old_last['time']}, "
            f"expected_right_next={exp_date} {exp_time}, "
            f"trim_reason={trim_reason or 'UNKNOWN'}。"
            f"当前仍存在历史数据不全风险，请人工检查并补全。"
        )

    return (
        f"分钟归档旧尾部曾发生异常残留并已自动修剪，但本次右侧拼接后仍未恢复连续："
        f"market={market}, symbol={symbol}, freq={freq}, "
        f"trimmed_old_last={old_last['date']} {old_last['time']}, "
        f"expected_right_next={exp_date} {exp_time}, "
        f"new_right_first={right_first['date']} {right_first['time']}, "
        f"trim_reason={trim_reason or 'UNKNOWN'}。"
        f"当前仍存在历史数据不全风险，请人工检查并补全。"
    )


def _pick_warning(
    *,
    market: str,
    symbol: str,
    freq: str,
    old_first: Dict[str, Any],
    old_last: Dict[str, Any],
    left_part: List[Dict[str, Any]],
    right_part: List[Dict[str, Any]],
    tail_trimmed: bool,
    tail_trim_reason: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """
    按最终连续性决定 warning。
    仅返回一个主 warning（保持现有返回结构简单稳定）。
    优先级：
      1) 修剪后右缺口
      2) 左缺口
      3) 普通右缺口
    """
    expected_right_next = next_minute_bucket_key(
        last_date=int(old_last["date"]),
        last_time=str(old_last["time"]),
        freq=freq,
    )

    if tail_trimmed:
        if not right_part:
            return (
                _WARNING_TRIMMED_GAP_RIGHT,
                _build_trimmed_gap_right_warning_message(
                    market=market,
                    symbol=symbol,
                    freq=freq,
                    old_last=old_last,
                    expected_right_next_key=expected_right_next,
                    right_first=None,
                    trim_reason=tail_trim_reason,
                ),
            )

        right_first = right_part[0]
        if _record_key(right_first) != expected_right_next:
            return (
                _WARNING_TRIMMED_GAP_RIGHT,
                _build_trimmed_gap_right_warning_message(
                    market=market,
                    symbol=symbol,
                    freq=freq,
                    old_last=old_last,
                    expected_right_next_key=expected_right_next,
                    right_first=right_first,
                    trim_reason=tail_trim_reason,
                ),
            )

    if left_part:
        left_last = left_part[-1]
        expected_old_first = next_minute_bucket_key(
            last_date=int(left_last["date"]),
            last_time=str(left_last["time"]),
            freq=freq,
        )
        if expected_old_first != _record_key(old_first):
            return (
                _WARNING_GAP_LEFT,
                _build_gap_left_warning_message(
                    market=market,
                    symbol=symbol,
                    freq=freq,
                    left_last=left_last,
                    old_first=old_first,
                    expected_old_first_key=expected_old_first,
                ),
            )

    if (not tail_trimmed) and right_part:
        right_first = right_part[0]
        if _record_key(right_first) != expected_right_next:
            return (
                _WARNING_GAP_RIGHT,
                _build_gap_right_warning_message(
                    market=market,
                    symbol=symbol,
                    freq=freq,
                    old_last=old_last,
                    right_first=right_first,
                    expected_right_next_key=expected_right_next,
                ),
            )

    return None, None


def _rows_from_bytes(raw: bytes) -> int:
    size = len(raw or b"")
    if size <= 0:
        return 0
    return size // _RECORD_SIZE


def merge_and_write_minute_archive(
    *,
    market: str,
    symbol: str,
    freq: str,
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    通用分钟线拼接归档入口（同步版）。

    Returns:
        {
          "archive_path": str,
          "existing_rows": int,
          "incoming_rows": int,
          "appended_rows": int,
          "final_total_rows": int,
          "written_bytes": int,
          "status": "created" | "appended" | "rewritten" | "noop",
          "warning_code": str | None,
          "warning_message": str | None,
          "placeholder_removed": bool,
        }
    """
    m = str(market or "").strip().upper()
    s = str(symbol or "").strip()
    f = str(freq or "").strip()

    if f not in ("1m", "5m"):
        raise ValueError(f"minute archive only supports 1m/5m, got: {freq}")
    if m not in ("SH", "SZ", "BJ"):
        raise ValueError(f"invalid market for minute archive: {market}")
    if not s or not s.isdigit():
        raise ValueError(f"invalid symbol for minute archive: {symbol}")
    if not records:
        raise ValueError("minute archive incoming records is empty")

    incoming_sorted = _normalize_and_sort_incoming(records)
    incoming_sorted, placeholder_removed = _remove_last_day_placeholder(incoming_sorted)

    archive_path = resolve_minute_archive_path(
        market=m,
        symbol=s,
        freq=f,
    )

    if not incoming_sorted:
        final_raw = read_archive_bytes(archive_path)
        return {
            "archive_path": str(Path(archive_path).resolve()),
            "existing_rows": _rows_from_bytes(final_raw),
            "incoming_rows": 0,
            "appended_rows": 0,
            "final_total_rows": _rows_from_bytes(final_raw),
            "written_bytes": 0,
            "status": "noop",
            "warning_code": None,
            "warning_message": None,
            "placeholder_removed": bool(placeholder_removed),
        }

    for r in incoming_sorted:
        if r["market"] != m or r["symbol"] != s or r["freq"] != f:
            raise ValueError(
                f"incoming minute record key mismatch: expected ({m},{s},{f}) got ({r['market']},{r['symbol']},{r['freq']})"
            )

    tail_validator = _tail_validator_factory(
        market=m,
        symbol=s,
        freq=f,
    )

    boundary = protect_and_read_archive_boundaries(
        archive_path,
        tail_validator=tail_validator,
    )

    if not bool(boundary.get("exists")):
        payload = encode_records_to_bytes(incoming_sorted)
        atomic_write_archive_bytes(archive_path, payload)
        final_total_rows = _rows_from_bytes(payload)
        return {
            "archive_path": str(Path(archive_path).resolve()),
            "existing_rows": 0,
            "incoming_rows": len(incoming_sorted),
            "appended_rows": len(incoming_sorted),
            "final_total_rows": final_total_rows,
            "written_bytes": len(payload),
            "status": "created",
            "warning_code": None,
            "warning_message": None,
            "placeholder_removed": bool(placeholder_removed),
        }

    first_raw = boundary.get("first_raw")
    last_raw = boundary.get("last_raw")

    if not first_raw or not last_raw:
        payload = encode_records_to_bytes(incoming_sorted)
        atomic_write_archive_bytes(archive_path, payload)
        final_total_rows = _rows_from_bytes(payload)
        return {
            "archive_path": str(Path(archive_path).resolve()),
            "existing_rows": 0,
            "incoming_rows": len(incoming_sorted),
            "appended_rows": len(incoming_sorted),
            "final_total_rows": final_total_rows,
            "written_bytes": len(payload),
            "status": "created",
            "warning_code": None,
            "warning_message": None,
            "placeholder_removed": bool(placeholder_removed),
        }

    old_first = _decode_archive_record(
        raw=first_raw,
        market=m,
        symbol=s,
        freq=f,
        label="first",
    )
    old_last = _decode_archive_record(
        raw=last_raw,
        market=m,
        symbol=s,
        freq=f,
        label="last",
    )

    old_first_key = _record_key(old_first)
    old_last_key = _record_key(old_last)

    left_part = [r for r in incoming_sorted if _record_key(r) < old_first_key]
    right_part = [r for r in incoming_sorted if _record_key(r) > old_last_key]

    warning_code, warning_message = _pick_warning(
        market=m,
        symbol=s,
        freq=f,
        old_first=old_first,
        old_last=old_last,
        left_part=left_part,
        right_part=right_part,
        tail_trimmed=bool(boundary.get("tail_trimmed")),
        tail_trim_reason=boundary.get("tail_trim_reason"),
    )

    old_raw = read_archive_bytes(archive_path)
    existing_rows = _rows_from_bytes(old_raw)

    if not left_part and not right_part:
        _LOG.info(
            "[MINUTE_ARCHIVE] noop archive market=%s symbol=%s freq=%s old_first=%s %s old_last=%s %s incoming_rows=%s",
            m,
            s,
            f,
            old_first["date"],
            old_first["time"],
            old_last["date"],
            old_last["time"],
            len(incoming_sorted),
        )
        return {
            "archive_path": str(Path(archive_path).resolve()),
            "existing_rows": existing_rows,
            "incoming_rows": len(incoming_sorted),
            "appended_rows": 0,
            "final_total_rows": existing_rows,
            "written_bytes": 0,
            "status": "noop",
            "warning_code": warning_code,
            "warning_message": warning_message,
            "placeholder_removed": bool(placeholder_removed),
        }

    if not left_part and right_part:
        payload = encode_records_to_bytes(right_part)
        written = append_archive_bytes(
            archive_path,
            payload,
            tail_validator=tail_validator,
        )
        final_total_rows = existing_rows + len(right_part)

        _LOG.info(
            "[MINUTE_ARCHIVE] appended archive market=%s symbol=%s freq=%s right_rows=%s warning_code=%s",
            m,
            s,
            f,
            len(right_part),
            warning_code,
        )

        return {
            "archive_path": str(Path(archive_path).resolve()),
            "existing_rows": existing_rows,
            "incoming_rows": len(incoming_sorted),
            "appended_rows": len(right_part),
            "final_total_rows": final_total_rows,
            "written_bytes": written,
            "status": "appended",
            "warning_code": warning_code,
            "warning_message": warning_message,
            "placeholder_removed": bool(placeholder_removed),
        }

    rebuilt = bytearray()

    if left_part:
        rebuilt.extend(encode_records_to_bytes(left_part))

    rebuilt.extend(old_raw)

    if right_part:
        rebuilt.extend(encode_records_to_bytes(right_part))

    payload = bytes(rebuilt)
    atomic_write_archive_bytes(archive_path, payload)
    final_total_rows = _rows_from_bytes(payload)

    _LOG.info(
        "[MINUTE_ARCHIVE] rewritten archive market=%s symbol=%s freq=%s left_rows=%s right_rows=%s warning_code=%s",
        m,
        s,
        f,
        len(left_part),
        len(right_part),
        warning_code,
    )

    return {
        "archive_path": str(Path(archive_path).resolve()),
        "existing_rows": existing_rows,
        "incoming_rows": len(incoming_sorted),
        "appended_rows": len(left_part) + len(right_part),
        "final_total_rows": final_total_rows,
        "written_bytes": len(payload),
        "status": "rewritten",
        "warning_code": warning_code,
        "warning_message": warning_message,
        "placeholder_removed": bool(placeholder_removed),
    }
