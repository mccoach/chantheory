# backend/datasource/akshare.py  # AkShare 数据源适配（收口统一归一化）
# ==============================
# 说明：
# - 本版移除本地归一化与纳秒→毫秒工具，改为直接复用 backend.datasource.fetchers 的统一归一化函数，
#   消除重复实现，保证“单一真相源”。
# - 继续提供 fetch_daily_none_and_factors（A 股日线 + 因子）与 fetch_minute_ak（分钟回退）。
# - 结构化日志替代 print，符合 NDJSON/trace_id 规范。
# ==============================

from __future__ import annotations  # 允许前置注解（兼容 3.8+）

from typing import Tuple, Optional  # 类型注解
import pandas as pd  # 数据处理库

# 统一归一化：直接复用 fetchers 的实现（单一真相源）
from backend.datasource.fetchers import _norm_daily_df, _norm_minute_df  # 归一化函数（集中维护）

# 时间工具：用于日期与字符串互转
from backend.utils.time import (
    today_yyyymmdd,        # 今天的 YYYYMMDD（整型）
    ms_from_yyyymmdd,      # YYYYMMDD → 毫秒（当日 00:00:00）
    yyyymmdd_from_ms,      # 毫秒 → YYYYMMDD（整型）
    yyyymmdd_from_str,     # 字符串 → YYYYMMDD（整型）
)

# 结构化日志
from backend.utils.logger import get_logger, log_event
_LOG = get_logger("datasource.akshare")  # 命名 logger

def _lazy_import_ak():
    """延迟导入 akshare，避免冷启动阻塞；由调用方捕获异常。"""
    import importlib
    return importlib.import_module("akshare")

def _normalize_yyyymmdd_range(
    start_yyyymmdd: Optional[int],
    end_yyyymmdd: Optional[int],
    default_start: int = 19900101,
) -> tuple[int, int]:
    """规范化 YYYYMMDD 区间（起点缺省用 default_start，终点缺省用今天；若 start>end 则交换）。"""
    s = int(start_yyyymmdd) if start_yyyymmdd else int(default_start)
    e = int(end_yyyymmdd) if end_yyyymmdd else int(today_yyyymmdd())
    if s > e:
        s, e = e, s
    return s, e

def _ak_symbol_with_prefix(symbol: str) -> str:
    """将代码映射为 ak 的带交易所前缀代码。"""
    s = (symbol or "").strip()
    if not s:
        return s
    if s.startswith("6"):
        return "sh" + s  # 上证
    if s.startswith(("0", "3")):
        return "sz" + s  # 深证
    if s.startswith(("8", "4")):
        return "bj" + s  # 北交
    return "sz" + s  # 默认深证

def fetch_daily_none_and_factors(
    symbol: str,
    start_yyyymmdd: Optional[int],
    end_yyyymmdd: Optional[int],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    拉取 A 股 1d 不复权价格（用于永久库）与 前/后复权因子（写入 adj_factors）：
    - 价格：ak.stock_zh_a_hist(adjust="")
    - 因子：ak.stock_zh_a_daily(adjust="qfq-factor"/"hfq-factor")
    返回：
      - df_none: ['ts','open','high','low','close','volume','amount','turnover_rate']
      - factors: ['symbol','date','qfq_factor','hfq_factor']
    """
    # 规范化日期区间
    s_ymd, e_ymd = _normalize_yyyymmdd_range(start_yyyymmdd, end_yyyymmdd, default_start=19900101)
    s_str = f"{s_ymd:08d}"
    e_str = f"{e_ymd:08d}"

    # 结构化日志（最小打点）
    log_event(_LOG, service="datasource.akshare", level="INFO",
              file=__file__, func="fetch_daily_none_and_factors", line=0, trace_id=None,
              event="fetch.start", message=f"daily_none_and_factors symbol={symbol} start={s_ymd} end={e_ymd}")

    ak = _lazy_import_ak()

    # 1) 日线不复权
    try:
        df_none_raw = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=s_str, end_date=e_str, adjust="")
    except Exception:
        df_none_raw = None
    # 使用统一归一化（集中在 fetchers）
    df_none = _norm_daily_df(df_none_raw)

    # 2) 因子表（前/后复权）
    pref = _ak_symbol_with_prefix(symbol)
    try:
        qfq_raw = ak.stock_zh_a_daily(symbol=pref, adjust="qfq-factor")
    except Exception:
        qfq_raw = None
    try:
        hfq_raw = ak.stock_zh_a_daily(symbol=pref, adjust="hfq-factor")
    except Exception:
        hfq_raw = None

    # 解析 qfq/hfq 原始表为两列 DataFrame
    q_df = pd.DataFrame(columns=["date", "qfq_factor"])
    if qfq_raw is not None and isinstance(qfq_raw, pd.DataFrame) and not qfq_raw.empty:
        tmp = pd.DataFrame(qfq_raw).copy()
        tmp.columns = [str(c).strip() for c in tmp.columns]
        c_date = "date" if "date" in tmp.columns else ("日期" if "日期" in tmp.columns else None)
        c_q = "qfq_factor" if "qfq_factor" in tmp.columns else None
        if c_date and c_q:
            q_df = pd.DataFrame({"date": tmp[c_date].astype(str), "qfq_factor": pd.to_numeric(tmp[c_q], errors="coerce")})

    h_df = pd.DataFrame(columns=["date", "hfq_factor"])
    if hfq_raw is not None and isinstance(hfq_raw, pd.DataFrame) and not hfq_raw.empty:
        tmp = pd.DataFrame(hfq_raw).copy()
        tmp.columns = [str(c).strip() for c in tmp.columns]
        c_date = "date" if "date" in tmp.columns else ("日期" if "日期" in tmp.columns else None)
        c_h = "hfq_factor" if "hfq_factor" in tmp.columns else None
        if c_date and c_h:
            h_df = pd.DataFrame({"date": tmp[c_date].astype(str), "hfq_factor": pd.to_numeric(tmp[c_h], errors="coerce")})

    # 汇总全日期
    dates_set = set()
    for src in (q_df, h_df):
        if src is not None and not src.empty and "date" in src.columns:
            for s in src["date"].astype(str).tolist():
                dates_set.add(s)

    # 若无日期，返回空因子表
    if not dates_set:
        return df_none, pd.DataFrame(columns=["symbol","date","qfq_factor","hfq_factor"])

    # 字符串日期 → YYYYMMDD 整型
    def _to_ymd_int(s: str) -> Optional[int]:
        try:
            return int(yyyymmdd_from_str(str(s)))
        except Exception:
            return None

    all_dates = sorted(d for d in (_to_ymd_int(s) for s in dates_set) if d is not None)
    factors = pd.DataFrame({"date": all_dates})

    if not q_df.empty:
        q_df2 = q_df.copy()
        q_df2["date"] = q_df2["date"].apply(_to_ymd_int)
        q_df2 = q_df2.dropna(subset=["date"]).sort_values("date")
        factors = factors.merge(q_df2[["date","qfq_factor"]], on="date", how="left")
    else:
        factors["qfq_factor"] = pd.NA

    if not h_df.empty:
        h_df2 = h_df.copy()
        h_df2["date"] = h_df2["date"].apply(_to_ymd_int)
        h_df2 = h_df2.dropna(subset=["date"]).sort_values("date")
        factors = factors.merge(h_df2[["date","hfq_factor"]], on="date", how="left")
    else:
        factors["hfq_factor"] = pd.NA

    # 过滤到请求区间并排序
    factors = factors[(factors["date"] >= s_ymd) & (factors["date"] <= e_ymd)].copy().sort_values("date").reset_index(drop=True)

    # 因子列：数值化 + 前向填充 + 缺失填 1.0
    for col in ["qfq_factor", "hfq_factor"]:
        if col in factors.columns:
            factors[col] = pd.to_numeric(factors[col], errors="coerce")
            try:
                factors[col] = factors[col].ffill()
            except Exception:
                factors[col] = factors[col].fillna(method="ffill")
            factors[col] = factors[col].fillna(1.0)
        else:
            factors[col] = 1.0

    # 添加 symbol 并统一列顺序
    factors["symbol"] = symbol
    factors = factors[["symbol","date","qfq_factor","hfq_factor"]].copy()
    return df_none, factors

def fetch_minute_ak(symbol: str, period: str = "1") -> pd.DataFrame:
    """回退分钟接口（当日）：返回规范化八字段。"""
    ak = _lazy_import_ak()
    # 结构化日志（最小打点）
    log_event(_LOG, service="datasource.akshare", level="INFO",
              file=__file__, func="fetch_minute_ak", line=0, trace_id=None,
              event="fetch.start", message=f"minute_ak symbol={symbol} period={period}")
    try:
        df_raw = ak.stock_zh_a_minute(symbol=symbol, period=period)
    except Exception:
        df_raw = None
    # 统一归一化（集中在 fetchers）
    return _norm_minute_df(df_raw)
