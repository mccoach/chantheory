# backend/utils/time.py
# ==============================
# 说明：时间与时区工具（统一 Asia/Shanghai）
# 重构要点（仅内部结构整合，接口契约保持不变）：
# - 统一内部时区获取与 datetime 构造（_get_tz/_to_dt_ms），避免重复拼装时区/格式逻辑。
# - 所有公开函数签名与返回语义保持不变（get_tz/now_iso/to_iso/.../normalize_yyyymmdd_range）。
# - format_close_time_str：统一使用内部构造，输出“YYYY-MM-DD HH:MM”（Asia/Shanghai，无时区后缀）。
# ==============================

from __future__ import annotations  # 兼容前置注解（Python 3.8+ 友好）

from datetime import datetime, date, time as dt_time, timedelta  # 标准时间
from zoneinfo import ZoneInfo  # 标准时区库（Python 3.9+）
from typing import Optional, Tuple, Union  # 类型注解

# 统一时区常量
TZ_SHANGHAI = "Asia/Shanghai"

# 内部：时区缓存，减少重复创建
_TZ_CACHE: dict[str, ZoneInfo] = {}


def _get_tz(tz_name: str = TZ_SHANGHAI) -> ZoneInfo:
    """内部获取并缓存 ZoneInfo 实例。"""
    t = tz_name or TZ_SHANGHAI
    if t not in _TZ_CACHE:
        _TZ_CACHE[t] = ZoneInfo(t)
    return _TZ_CACHE[t]


def _to_dt_ms(ms: int, tz_name: str = TZ_SHANGHAI) -> datetime:
    """内部：毫秒 → datetime（指定时区）。"""
    tz = _get_tz(tz_name)
    return datetime.fromtimestamp(int(ms) / 1000.0, tz=tz)


def get_tz(sh_tz: str = TZ_SHANGHAI) -> ZoneInfo:
    """
    返回给定名称的时区对象；默认 Asia/Shanghai。
    （公开接口保持不变）
    """
    return _get_tz(sh_tz)


def now_iso(tz_name: str = TZ_SHANGHAI) -> str:
    """
    返回当前时间的 ISO8601 字符串（含时区信息）。
    例如：'2025-08-25T21:03:45.123456+08:00'
    """
    tz = _get_tz(tz_name)
    return datetime.now(tz).isoformat()


def to_iso(dt: datetime, tz_name: str = TZ_SHANGHAI) -> str:
    """
    将 datetime 对象转换为指定时区的 ISO8601 字符串。
    - 若 dt 无 tzinfo，则先按 tz_name 赋予时区，再输出。
    """
    tz = _get_tz(tz_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz).isoformat()


def yyyymmdd_from_str(s: str) -> int:
    """
    解析字符串 'YYYY-MM-DD' 或 'YYYYMMDD' 为整型 YYYMMDD。
    - 传入非法字符串会抛 ValueError。
    """
    s = (s or "").strip()
    if not s:
        raise ValueError("empty date string")
    if "-" in s:  # 形如 YYYY-MM-DD
        parts = s.split("-")
        if len(parts) != 3:
            raise ValueError(f"invalid date: {s}")
        return int(parts[0] + parts[1].zfill(2) + parts[2].zfill(2))
    # 形如 YYYYMMDD（必须为 8 位数字）
    if len(s) != 8 or not s.isdigit():
        raise ValueError(f"invalid yyyymmdd: {s}")
    return int(s)


def date_from_yyyymmdd(yyyymmdd: int) -> date:
    """
    将整型 YYYMMDD 转为 date 对象。
    例如：20250825 -> date(2025, 8, 25)
    """
    n = int(yyyymmdd)
    y = n // 10000
    m = (n // 100) % 100
    d = n % 100
    return date(y, m, d)


def yyyymmdd_from_date(d: date) -> int:
    """
    将 date 对象转为整型 YYYMMDD。
    例如：date(2025, 8, 25) -> 20250825
    """
    return d.year * 10000 + d.month * 100 + d.day


def day_bounds_ms(d: date, tz_name: str = TZ_SHANGHAI) -> Tuple[int, int]:
    """
    返回“自然日 d 在本地时区的起止毫秒”：
    - 起始：当日 00:00:00.000
    - 结束：当日 23:59:59.999（使用 datetime.time.max 表达）
    """
    tz = _get_tz(tz_name)
    begin_dt = datetime.combine(d, dt_time.min).replace(tzinfo=tz)
    end_dt = datetime.combine(d, dt_time.max).replace(tzinfo=tz)
    return int(begin_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)


def ms_from_yyyymmdd(yyyymmdd: int, tz_name: str = TZ_SHANGHAI) -> int:
    """
    将 YYYMMDD 转为“当日 00:00:00.000 的 epoch 毫秒”（本地时区）。
    """
    d = date_from_yyyymmdd(yyyymmdd)
    begin_ms, _ = day_bounds_ms(d, tz_name)
    return begin_ms


def yyyymmdd_from_ms(ms: int, tz_name: str = TZ_SHANGHAI) -> int:
    """
    将 epoch 毫秒（本地时区）转换为整型 YYYMMDD。
    """
    dt = _to_dt_ms(ms, tz_name)
    return yyyymmdd_from_date(dt.date())


def clamp_range_ms(
    begin_ms: Optional[int],
    end_ms: Optional[int],
) -> Tuple[Optional[int], Optional[int]]:
    """
    若 begin_ms 与 end_ms 均非空，确保 begin<=end；否则原样返回。
    """
    if begin_ms is None or end_ms is None:
        return begin_ms, end_ms
    return (begin_ms, end_ms) if begin_ms <= end_ms else (end_ms, begin_ms)


def shift_days_yyyymmdd(yyyymmdd: int, delta: int) -> int:
    """
    将整型 YYYMMDD 向前/向后偏移 delta 天，返回新的 YYYMMDD。
    例如：shift_days_yyyymmdd(20250825, 1) -> 20250826
    """
    d = date_from_yyyymmdd(yyyymmdd)
    return yyyymmdd_from_date(d + timedelta(days=delta))


def is_same_day(ms_a: int, ms_b: int, tz_name: str = TZ_SHANGHAI) -> bool:
    """
    比较两个毫秒时间戳是否处于同一自然日（在 tz_name 时区下的判断）。
    """
    return yyyymmdd_from_ms(ms_a, tz_name) == yyyymmdd_from_ms(ms_b, tz_name)


def align_to_minute(ms: int) -> int:
    """
    将毫秒对齐到分钟起点（向下取整至 00 秒）。
    """
    return (int(ms) // 60000) * 60000


def align_to_day_start(ms: int, tz_name: str = TZ_SHANGHAI) -> int:
    """
    将毫秒对齐到其所在自然日的起始（本地时区 00:00:00.000）。
    """
    ymd = yyyymmdd_from_ms(ms, tz_name)
    return ms_from_yyyymmdd(ymd, tz_name)


def today_yyyymmdd(tz_name: str = TZ_SHANGHAI) -> int:
    """
    返回“今天”的整型 YYYMMDD（本地时区）。
    """
    tz = _get_tz(tz_name)
    d = datetime.now(tz).date()
    return yyyymmdd_from_date(d)


def _parse_yyyymmdd_like(x: Optional[Union[int, str]]) -> Optional[int]:
    """
    解析多种表示为整型 YYYMMDD：
    - 整数：若 >1e8 认为是毫秒，否则认为是 YYYMMDD
    - 字符串：
      * 纯数字：同上规则
      * YYYY-MM-DD：解析为 YYYMMDD
    - 其它/解析失败：返回 None
    """
    if x is None:
        return None
    if isinstance(x, int):
        return yyyymmdd_from_ms(x) if x > 10**8 else x
    s = str(x).strip()
    if not s:
        return None
    if s.isdigit():
        val = int(s)
        return yyyymmdd_from_ms(val) if val > 10**8 else val
    if "-" in s:
        return yyyymmdd_from_str(s)
    return None


def normalize_yyyymmdd_range(
    start_like: Optional[Union[int, str]],
    end_like: Optional[Union[int, str]],
    default_start: int = 19900101,  # 默认最早日期：1990-01-01
    default_end: Optional[int] = None,  # 默认结束为“今天”（若 None）
) -> Tuple[int, int]:
    """
    将 (start_like, end_like) 规范为 (start_yyyymmdd, end_yyyymmdd)：
    - 支持 start/end 三种形态：YYYYMMDD | YYYY-MM-DD | 毫秒
    - 若某一端缺省：
      * start 缺省 -> default_start（默认 19900101）
      * end 缺省   -> 今天（本地时区）
    - 若 start>end 则交换，确保区间有序
    - 返回值均为整型 YYYMMDD
    """
    s = _parse_yyyymmdd_like(start_like)
    e = _parse_yyyymmdd_like(end_like)
    if s is None:
        s = int(default_start)
    if e is None:
        e = int(default_end or today_yyyymmdd())
    if s > e:
        s, e = e, s
    # 工具层保持静默（不打印），观测应由调用方按需记录
    return int(s), int(e)


# 新增：将毫秒时间戳格式化为“自然可读收盘时间”字符串（YYYY-MM-DD HH:MM），统一 Asia/Shanghai，无时区后缀
def format_close_time_str(ms: int, freq: Optional[str] = None, tz_name: str = TZ_SHANGHAI) -> str:
    """
    将毫秒时间戳格式化为“YYYY-MM-DD HH:MM”短文本（统一 Asia/Shanghai，无时区后缀）。
    - freq 参数目前仅为兼容占位；由于 ts 已为真正收盘时刻（分钟族右端、日/周/月为 15:00），统一按 HH:MM 输出。
    """
    dt = _to_dt_ms(ms, tz_name)
    return dt.strftime("%Y-%m-%d %H:%M")
