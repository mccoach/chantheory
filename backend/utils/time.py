# backend/utils/time.py
# ==============================
# 说明：时间工具（V4.0 - 统一时间戳体系·唯一源头）
# 设计原则：
#   1. 系统唯一时间基准：毫秒时间戳（int，表示epoch milliseconds）
#   2. 明确时间点语义：函数名直接表达时间点（日初/收盘/日末/自定义）
#   3. 类型转换单向流：YYYYMMDD → date → datetime → timestamp_ms
#   4. 统一时区：所有时间默认 Asia/Shanghai
#
# 核心函数：
#   - ms_at_day_start：日期 → 日初时间戳（00:00:00）
#   - ms_at_market_close：日期 → 收盘时间戳（15:00:00）
#   - ms_at_day_end：日期 → 日末时间戳（23:59:59）
#   - ms_at_time：日期+时分秒 → 自定义时间戳
#   - query_range_ms：日期范围 → 查询用时间戳范围（包含边界）
# ==============================

from __future__ import annotations

from datetime import datetime, date, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, Union

from backend.settings import settings

# 统一时区常量
TZ_SHANGHAI = settings.timezone

# 时区对象缓存
_tz_cache: dict[str, ZoneInfo] = {}


def get_tz(tz_name: str = TZ_SHANGHAI) -> ZoneInfo:
    """
    获取时区对象（带缓存）
    
    Args:
        tz_name: 时区名称（默认 Asia/Shanghai）
    
    Returns:
        ZoneInfo: 时区对象
    """
    if tz_name not in _tz_cache:
        _tz_cache[tz_name] = ZoneInfo(tz_name)
    return _tz_cache[tz_name]


# ==============================================================================
# 一、基础类型转换（YYYYMMDD ↔ date 对象）
# ==============================================================================


def parse_yyyymmdd(value: Union[str, int, date, datetime]) -> int:
    """
    通用日期解析器 → YYYYMMDD整数
    
    支持输入：
      - 字符串：'2024-11-01', '2024/11/01', '20241101'
      - 整数：20241101
      - date对象：date(2024, 11, 1)
      - datetime对象：datetime(2024, 11, 1, 15, 0)
    
    Returns:
        int: YYYYMMDD整数
    
    Raises:
        ValueError: 无法解析时
    
    Examples:
        >>> parse_yyyymmdd('2024-11-01')
        20241101
        >>> parse_yyyymmdd(20241101)
        20241101
        >>> parse_yyyymmdd(date(2024, 11, 1))
        20241101
    """
    if isinstance(value, int):
        # 验证范围
        if 19000101 <= value <= 21001231:
            return value
        raise ValueError(f"整数超出有效日期范围: {value}")

    if isinstance(value, (date, datetime)):
        return value.year * 10000 + value.month * 100 + value.day

    if isinstance(value, str):
        # 移除分隔符
        clean = value.replace('-', '').replace('/', '').replace('.',
                                                                '').strip()

        if len(clean) == 8 and clean.isdigit():
            return int(clean)

        # 尝试ISO解析
        try:
            dt = datetime.fromisoformat(value)
            return dt.year * 10000 + dt.month * 100 + dt.day
        except Exception:
            pass

    raise ValueError(f"无法解析为日期: {value}")


def to_date_object(yyyymmdd: int) -> date:
    """
    YYYYMMDD整数 → date对象
    
    Args:
        yyyymmdd: YYYYMMDD格式的整数
    
    Returns:
        date: Python标准日期对象
    
    Examples:
        >>> to_date_object(20241101)
        date(2024, 11, 1)
    """
    year = yyyymmdd // 10000
    month = (yyyymmdd // 100) % 100
    day = yyyymmdd % 100
    return date(year, month, day)


# ==============================================================================
# 二、时间戳构造（明确时间点语义）
# ==============================================================================


def ms_at_day_start(yyyymmdd: int, tz_name: str = TZ_SHANGHAI) -> int:
    """
    日期 → 日初时间戳（00:00:00.000）
    
    用途：查询范围的起始边界
    语义：当日最早时刻，WHERE ts >= start
    
    Args:
        yyyymmdd: 日期（YYYYMMDD整数）
        tz_name: 时区名称
    
    Returns:
        int: 日初时刻的毫秒时间戳
    
    Examples:
        >>> ms_at_day_start(20241101)
        1730390400000  # 2024-11-01 00:00:00 +08:00
    """
    d = to_date_object(yyyymmdd)
    tz = get_tz(tz_name)
    dt = datetime.combine(d, dt_time(0, 0, 0), tzinfo=tz)
    return int(dt.timestamp() * 1000)


def ms_at_day_end(yyyymmdd: int, tz_name: str = TZ_SHANGHAI) -> int:
    """
    日期 → 日末时间戳（23:59:59.999）
    
    用途：查询范围的结束边界
    语义：当日最晚时刻，WHERE ts <= end
    
    Args:
        yyyymmdd: 日期（YYYYMMDD整数）
        tz_name: 时区名称
    
    Returns:
        int: 日末时刻的毫秒时间戳
    
    Examples:
        >>> ms_at_day_end(20241101)
        1730476799999  # 2024-11-01 23:59:59.999 +08:00
    """
    d = to_date_object(yyyymmdd)
    tz = get_tz(tz_name)
    dt = datetime.combine(d, dt_time(23, 59, 59, 999999), tzinfo=tz)
    return int(dt.timestamp() * 1000)


def ms_at_market_close(yyyymmdd: int, tz_name: str = TZ_SHANGHAI) -> int:
    """
    日期 → 市场收盘时间戳（15:00:00.000）
    
    用途：
      1. 日K线的标准时间戳
      2. 周K线的标准时间戳
      3. 月K线的标准时间戳
      4. 缺口判断的理论最新时间戳
    
    语义：
      中国A股市场统一收盘时间 = 15:00
    
    Args:
        yyyymmdd: 日期（YYYYMMDD整数）
        tz_name: 时区名称
    
    Returns:
        int: 收盘时刻的毫秒时间戳
    
    Examples:
        >>> ms_at_market_close(20241101)
        1730448000000  # 2024-11-01 15:00:00 +08:00
    """
    d = to_date_object(yyyymmdd)
    tz = get_tz(tz_name)
    dt = datetime.combine(d, dt_time(15, 0, 0), tzinfo=tz)
    return int(dt.timestamp() * 1000)


def ms_at_market_open(yyyymmdd: int, tz_name: str = TZ_SHANGHAI) -> int:
    """
    日期 → 市场开盘时间戳（09:30:00.000）
    
    用途：
      计算日内时间范围
    
    Args:
        yyyymmdd: 日期（YYYYMMDD整数）
        tz_name: 时区名称
    
    Returns:
        int: 开盘时刻的毫秒时间戳
    
    Examples:
        >>> ms_at_market_open(20241101)
        1730428200000  # 2024-11-01 09:30:00 +08:00
    """
    d = to_date_object(yyyymmdd)
    tz = get_tz(tz_name)
    dt = datetime.combine(d, dt_time(9, 30, 0), tzinfo=tz)
    return int(dt.timestamp() * 1000)


def ms_at_time(yyyymmdd: int,
               hour: int,
               minute: int = 0,
               second: int = 0,
               tz_name: str = TZ_SHANGHAI) -> int:
    """
    日期+时分秒 → 毫秒时间戳（通用构造器）
    
    用途：构造任意时刻的时间戳
    
    Args:
        yyyymmdd: 日期（YYYYMMDD整数）
        hour: 小时（0-23）
        minute: 分钟（0-59）
        second: 秒（0-59）
        tz_name: 时区名称
    
    Returns:
        int: 指定时刻的毫秒时间戳
    
    Examples:
        >>> ms_at_time(20241101, 14, 35)
        1730441700000  # 2024-11-01 14:35:00 +08:00
    """
    d = to_date_object(yyyymmdd)
    tz = get_tz(tz_name)
    dt = datetime.combine(d, dt_time(hour, minute, second), tzinfo=tz)
    return int(dt.timestamp() * 1000)


# ==============================================================================
# 三、反向转换（毫秒时间戳 → 日期/时间对象）
# ==============================================================================


def to_yyyymmdd(ts_ms: int, tz_name: str = TZ_SHANGHAI) -> int:
    """
    毫秒时间戳 → YYYYMMDD整数（按指定时区解释）
    
    Args:
        ts_ms: 毫秒时间戳
        tz_name: 时区名称
    
    Returns:
        int: YYYYMMDD整数
    
    Examples:
        >>> to_yyyymmdd(1730448000000)
        20241101
    """
    tz = get_tz(tz_name)
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=tz)
    return int(dt.strftime('%Y%m%d'))


def to_datetime(ts_ms: int, tz_name: str = TZ_SHANGHAI) -> datetime:
    """
    毫秒时间戳 → datetime对象（带时区）
    
    Args:
        ts_ms: 毫秒时间戳
        tz_name: 时区名称
    
    Returns:
        datetime: 带时区的datetime对象
    
    Examples:
        >>> to_datetime(1730448000000)
        datetime(2024, 11, 1, 15, 0, tzinfo=ZoneInfo('Asia/Shanghai'))
    """
    tz = get_tz(tz_name)
    return datetime.fromtimestamp(ts_ms / 1000, tz=tz)


def to_iso_string(ts_ms: int, tz_name: str = TZ_SHANGHAI) -> str:
    """
    毫秒时间戳 → ISO8601字符串（含时区）
    
    Args:
        ts_ms: 毫秒时间戳
        tz_name: 时区名称
    
    Returns:
        str: ISO格式字符串
    
    Examples:
        >>> to_iso_string(1730448000000)
        '2024-11-01T15:00:00+08:00'
    """
    dt = to_datetime(ts_ms, tz_name)
    return dt.isoformat()


def to_readable_string(ts_ms: int, tz_name: str = TZ_SHANGHAI) -> str:
    """
    毫秒时间戳 → 可读字符串（YYYY-MM-DD HH:MM，无时区后缀）
    
    用途：日志输出、前端显示
    
    Args:
        ts_ms: 毫秒时间戳
        tz_name: 时区名称
    
    Returns:
        str: 可读格式字符串
    
    Examples:
        >>> to_readable_string(1730448000000)
        '2024-11-01 15:00'
    """
    dt = to_datetime(ts_ms, tz_name)
    return dt.strftime("%Y-%m-%d %H:%M")


# ==============================================================================
# 四、范围查询专用函数
# ==============================================================================


def query_range_ms(start_ymd: int,
                   end_ymd: int,
                   tz_name: str = TZ_SHANGHAI) -> Tuple[int, int]:
    """
    日期范围 → 查询用时间戳范围（包含边界）
    
    转换规则：
      start_ymd → 当日 00:00:00（包含起始日全部数据）
      end_ymd   → 当日 23:59:59（包含结束日全部数据）
    
    用途：
      SQL查询 WHERE ts >= start_ts AND ts <= end_ts
    
    Args:
        start_ymd: 起始日期（YYYYMMDD整数）
        end_ymd: 结束日期（YYYYMMDD整数）
        tz_name: 时区名称
    
    Returns:
        (start_ts, end_ts): 时间戳范围（包含边界）
    
    Examples:
        >>> query_range_ms(20241101, 20241103)
        (1730390400000, 1730649599999)
        # 2024-11-01 00:00:00 ~ 2024-11-03 23:59:59
    """
    start_ts = ms_at_day_start(start_ymd, tz_name)
    end_ts = ms_at_day_end(end_ymd, tz_name)
    return start_ts, end_ts


def normalize_date_range(
    start_like: Optional[Union[int, str]],
    end_like: Optional[Union[int, str]],
    default_start: int = 19900101,
    default_end: Optional[int] = None,
) -> Tuple[int, int]:
    """
    规范化日期范围输入 → 标准YYYYMMDD整数对
    
    处理规则：
      - 缺省值：start默认19900101，end默认今天
      - 自动交换：确保 start <= end
      - 类型统一：全部转为YYYYMMDD整数
    
    Args:
        start_like: 起始日期（支持多种格式）
        end_like: 结束日期（支持多种格式）
        default_start: 起始缺省值
        default_end: 结束缺省值（None=今天）
    
    Returns:
        (start_ymd, end_ymd): 标准化的日期范围
    
    Examples:
        >>> normalize_date_range('2024-11-01', '2024-11-03')
        (20241101, 20241103)
        >>> normalize_date_range(None, None)
        (19900101, 20241105)  # 默认值
    """
    # 解析起始
    if start_like is None:
        start_ymd = default_start
    else:
        try:
            start_ymd = parse_yyyymmdd(start_like)
        except Exception:
            start_ymd = default_start

    # 解析结束
    if end_like is None:
        end_ymd = default_end if default_end else today_ymd()
    else:
        try:
            end_ymd = parse_yyyymmdd(end_like)
        except Exception:
            end_ymd = default_end if default_end else today_ymd()

    # 确保顺序
    if start_ymd > end_ymd:
        start_ymd, end_ymd = end_ymd, start_ymd

    return start_ymd, end_ymd


# ==============================================================================
# 五、当前时间便捷函数
# ==============================================================================


def now_dt(tz_name: str = TZ_SHANGHAI) -> datetime:
    """
    获取当前时间（datetime对象，带时区）
    
    Returns:
        datetime: 当前时刻
    
    Examples:
        >>> now_dt()
        datetime(2024, 11, 5, 14, 35, tzinfo=ZoneInfo('Asia/Shanghai'))
    """
    return datetime.now(tz=get_tz(tz_name))


def now_ms(tz_name: str = TZ_SHANGHAI) -> int:
    """
    获取当前时刻的毫秒时间戳
    
    Returns:
        int: 当前毫秒时间戳
    
    Examples:
        >>> now_ms()
        1730800000000
    """
    return int(now_dt(tz_name).timestamp() * 1000)


def today_ymd(tz_name: str = TZ_SHANGHAI) -> int:
    """
    获取今日日期（YYYYMMDD整数）
    
    Returns:
        int: 今日日期
    
    Examples:
        >>> today_ymd()
        20241105
    """
    return int(now_dt(tz_name).strftime('%Y%m%d'))


def now_iso(tz_name: str = TZ_SHANGHAI) -> str:
    """
    获取当前时间的ISO8601字符串（含时区）
    
    Returns:
        str: ISO格式时间字符串
    
    Examples:
        >>> now_iso()
        '2024-11-05T14:35:00+08:00'
    """
    return now_dt(tz_name).isoformat()


# ==============================================================================
# 六、时间运算辅助函数
# ==============================================================================


def shift_days(yyyymmdd: int, delta: int) -> int:
    """
    日期偏移（向前/向后N天）
    
    Args:
        yyyymmdd: 原始日期
        delta: 偏移天数（正数=未来，负数=过去）
    
    Returns:
        int: 偏移后的日期
    
    Examples:
        >>> shift_days(20241101, 3)
        20241104
        >>> shift_days(20241101, -7)
        20241025
    """
    d = to_date_object(yyyymmdd)
    new_d = d + timedelta(days=delta)
    return new_d.year * 10000 + new_d.month * 100 + new_d.day


def is_same_day(ts_a: int, ts_b: int, tz_name: str = TZ_SHANGHAI) -> bool:
    """
    判断两个时间戳是否属于同一自然日
    
    Args:
        ts_a: 时间戳A（毫秒）
        ts_b: 时间戳B（毫秒）
        tz_name: 时区名称
    
    Returns:
        bool: 是否同一天
    
    Examples:
        >>> is_same_day(1730448000000, 1730476799999)
        True  # 都是 2024-11-01
    """
    return to_yyyymmdd(ts_a, tz_name) == to_yyyymmdd(ts_b, tz_name)


def align_to_minute_start(ts_ms: int) -> int:
    """
    时间戳对齐到分钟起点（秒和毫秒归零）
    
    Args:
        ts_ms: 毫秒时间戳
    
    Returns:
        int: 对齐后的时间戳
    
    Examples:
        >>> align_to_minute_start(1730448035678)
        1730448000000  # 15:00:35.678 → 15:00:00.000
    """
    return (int(ts_ms) // 60000) * 60000


def align_to_day_start(ts_ms: int, tz_name: str = TZ_SHANGHAI) -> int:
    """
    时间戳对齐到所在日的日初（00:00:00）
    
    Args:
        ts_ms: 毫秒时间戳
        tz_name: 时区名称
    
    Returns:
        int: 日初时间戳
    
    Examples:
        >>> align_to_day_start(1730448000000)
        1730390400000  # 15:00 → 00:00
    """
    ymd = to_yyyymmdd(ts_ms, tz_name)
    return ms_at_day_start(ymd, tz_name)


# ==============================================================================
# 七、datetime字符串处理（补充标准函数）
# ==============================================================================


def ms_from_datetime_string(dt_str: str, tz_name: str = TZ_SHANGHAI) -> int:
    """
    datetime字符串 → 毫秒时间戳（保持原始时间）
    
    支持格式：
      - ISO格式：'2024-11-01T14:35:00'
      - 空格格式：'2024-11-01 14:35:00'
      - 带时区：'2024-11-01T14:35:00+08:00'
    
    Args:
        dt_str: datetime字符串
        tz_name: 时区名称（仅当字符串无时区时使用）
    
    Returns:
        int: 毫秒时间戳
    
    Examples:
        >>> ms_from_datetime_string('2024-11-01 14:35:00')
        1730441700000
    """
    # 统一格式为ISO
    normalized = str(dt_str).strip().replace(' ', 'T')

    # 解析
    dt = datetime.fromisoformat(normalized)

    # 补充时区（如果缺失）
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_tz(tz_name))

    return int(dt.timestamp() * 1000)


def to_yyyymmdd_from_iso(iso_str: str) -> int:
    """
    ISO时间字符串 → YYYYMMDD整数
    
    用途：从ISO格式的updated_at字段提取日期
    
    Args:
        iso_str: ISO格式字符串（如 '2024-11-01T15:00:00+08:00'）
    
    Returns:
        int: YYYYMMDD整数
    
    Examples:
        >>> to_yyyymmdd_from_iso('2024-11-01T15:00:00+08:00')
        20241101
        >>> to_yyyymmdd_from_iso('2024-11-01T15:00:00')
        20241101
    """
    # 提取日期部分（兼容带/不带时区）
    date_part = iso_str.split('T')[0]
    return parse_yyyymmdd(date_part)


# ==============================================================================
# 八、时间格式转换（日期 → 年/月/日）
# ==============================================================================


def format_date_value(
    value: Union[str, int, date, datetime],
    unit: str = "d",
    sep: str = "",
) -> str:
    """
    通用日期格式化工具（高内聚版）

    功能：
      - 宽松解析各种日期/年月/年度字符串或 date/datetime，然后按指定“粒度 + 连接符”输出。
      - 统一入口，覆盖三种粒度：
          * 日(d/D/日)  → YYYY[sep]MM[sep]DD
          * 月(m/M/月)  → YYYY[sep]MM
          * 年(y/Y/年)  → YYYY

    参数：
      value:
        - 任意可表示日期/时间的输入：
          * 字符串：'2024-11-26', '20241126', '2024/11/26', '2024.11.26'
          * 字符串：'2024-11', '202411', '2024/11', '2024.11'（用于月度/年度）
          * 字符串：'2024'（用于年度）
          * int：20241126
          * date / datetime 对象
      unit:
        - 指定输出粒度，取值集合（不区分大小写）：
          * 'd', 'D', '日' → 日度（默认）
          * 'm', 'M', '月' → 月度
          * 'y', 'Y', '年' → 年度
      sep:
        - 连接符字符串，任意内容，默认空字符串：
          * 日度：
              sep=''    → '20241126'
              sep='-'   → '2024-11-26'
              sep='/'   → '2024/11/26'
              sep='.'   → '2024.11.26'
          * 月度：
              sep=''    → '202411'
              sep='-'   → '2024-11'
              sep='/'   → '2024/11'
          * 年度：
              始终返回 'YYYY'，sep 不参与拼接

    解析规则（按 unit 不同）：
      - 日度：
          * 直接调用 parse_yyyymmdd(value) → YYYYMMDD 整数
      - 月度：
          1) 将字符串中的 '-', '/', '.' 去除得到 clean
          2) 若 clean[:6] 是合法 YYYYMM，则直接使用
          3) 否则回退 parse_yyyymmdd(value) → YYYYMMDD，再取前 6 位 YYYYMM
      - 年度：
          1) 从字符串中提取所有数字，若前 4 位可构成年份则直接使用
          2) 否则回退 parse_yyyymmdd(value) → YYYYMMDD，再取年份部分

    Raises:
        ValueError: 当无法解析为合法日期 / 年月 / 年度时。
    """
    # 规范 unit → 内部模式
    u = (unit or "d")
    if u in ("d", "D", "日"):
        mode = "d"
    elif u in ("m", "M", "月"):
        mode = "m"
    elif u in ("y", "Y", "年"):
        mode = "y"
    else:
        mode = "d"  # 容错：未知类型按“日”处理

    # ---- 日度：完全托管给 parse_yyyymmdd ----
    if mode == "d":
        ymd = parse_yyyymmdd(value)
        s = f"{ymd:08d}"  # YYYYMMDD
        if not sep:
            return s
        return f"{s[:4]}{sep}{s[4:6]}{sep}{s[6:]}"

    # 统一转字符串做轻量处理（仅用于月/年）
    s = str(value).strip()
    clean = s.replace("-", "").replace("/", "").replace(".", "")

    # ---- 年度：优先从数字串抽取 YYYY，再回退到 parse_yyyymmdd ----
    if mode == "y":
        digits = "".join(ch for ch in clean if ch.isdigit())
        if len(digits) >= 4:
            year = int(digits[:4])
            if 1900 <= year <= 2100:
                return f"{year:04d}"
        # 回退到完整日期解析
        ymd = parse_yyyymmdd(value)
        year = ymd // 10000
        return f"{year:04d}"

    # ---- 月度：优先从 clean 中抽取 YYYYMM，再回退到 parse_yyyymmdd ----
    if mode == "m":
        if len(clean) >= 6 and clean[:6].isdigit():
            ym = int(clean[:6])
            year = ym // 100
            month = ym % 100
            if 1900 <= year <= 2100 and 1 <= month <= 12:
                s_ym = f"{ym:06d}"  # YYYYMM
                if not sep:
                    return s_ym
                return f"{s_ym[:4]}{sep}{s_ym[4:]}"
        # 回退到完整日期解析
        ymd = parse_yyyymmdd(value)
        ym = ymd // 100  # YYYYMM
        s_ym = f"{ym:06d}"
        if not sep:
            return s_ym
        return f"{s_ym[:4]}{sep}{s_ym[4:]}"
