# backend/services/market.py  # 行情服务（服务端一次成型：计算可视切片 s_idx/e_idx）
# ==============================
# 本版要点（相对原实现的根因重构）：
# - 继续保障“近端达标 + 缓存 + 复权/重采样”的数据完整性（ALL 序列）
# - 新增：服务端统一计算“终端可见切片”的索引窗口（右端锚定），并在 meta 返回：
#   * all_rows, view_rows, view_start_idx, view_end_idx, window_preset_effective
#   * start/end（可见切片左右端时间）
# - 前端仅渲染“ALL 序列”并按 meta.view_* 设置 dataZoom；不再参与切片计算
from __future__ import annotations  # 允许前置注解（兼容 3.8+）

from typing import Optional, Dict, Any, List, Tuple, Set  # 类型注解
from collections import Counter  # 计数统计
from datetime import datetime, timedelta  # 时间工具
import time  # 退避/当前时间
import random  # 抖动

import pandas as pd  # DataFrame
import numpy as np  # 数值

from backend.settings import settings  # 全局配置
from backend.db.sqlite import (  # 数据库接口
    select_candles,
    select_cache_candles,
    upsert_cache_candles,
    get_cache_meta,
    touch_cache_meta,
    rebuild_cache_meta,
    get_conn,
    select_factors,
)
from backend.services.storage import ensure_daily_recent  # 保障 1d 近端（供 1w/1M 兜底）
from backend.utils.time import (  # 时间工具
    TZ_SHANGHAI,
    ms_from_yyyymmdd,
    yyyymmdd_from_ms,
)
from backend.services.indicators import ma, macd, kdj, rsi, boll  # 指标
from backend.datasource.fetchers import fetch_period_ms  # 抓取入口
from backend.utils.logger import get_logger, log_event  # 日志（结构化）
from backend.utils.window_preset import preset_to_bars  # NEW: 预设→bars 查表（服务端唯一可信）

_LOG = get_logger("market")  # 命名 logger

MINUTE_GRACE_SEC = 5   # 分钟级宽限（秒）
DAILY_GRACE_SEC = 180  # 日/周/月宽限（秒）
START_1990_MS = ms_from_yyyymmdd(19900101)  # 全窗左端

def _retry(fn, attempts: int = None, base_ms: int = None):
    """指数退避：失败 attempts 次后抛出。"""
    a = int(getattr(settings, "retry_max_attempts", 0) if attempts is None else attempts)
    base = int(getattr(settings, "retry_base_delay_ms", 500) if base_ms is None else base_ms)
    last = None
    for i in range(a + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            if i >= a:
                break
            delay = (base * (2 ** i)) * (0.8 + 0.4 * random.random())
            time.sleep(delay / 1000.0)
    if last:
        raise last
    return None

_trade_calendar_cache: Dict[str, set] = {}  # 年→交易日集合缓存

def _lazy_is_trading_day(d: datetime) -> bool:
    """轻量交易日判定：优先 ak 日历，失败回退 Mon–Fri。"""
    y = d.year
    key = f"{y}"
    if key not in _trade_calendar_cache:
        try:
            import akshare as ak
            df = ak.tool_trade_date_hist_sina()
            df = pd.DataFrame(df)
            df.columns = [str(c).strip() for c in df.columns]
            date_col = next((c for c in ["trade_date","日期","date"] if c in df.columns), None)
            st = set()
            if date_col:
                for s in df[date_col].astype(str):
                    if len(s) >= 10 and int(s[:4]) == y:
                        st.add(s[:10])
            _trade_calendar_cache[key] = st
        except Exception:
            _trade_calendar_cache[key] = set()
    s = f"{d.year:04d}-{d.month:02d}-{d.day:02d}"
    if _trade_calendar_cache.get(key):
        return s in _trade_calendar_cache[key]
    return d.weekday() < 5

def _today_shanghai() -> datetime:
    """返回 Asia/Shanghai 的当前时间（与 pandas 时区一致）。"""
    return datetime.now().astimezone(pd.Timestamp.now(tz=TZ_SHANGHAI).tz)

def _ms_from_dt(dt: datetime) -> int:
    """datetime → 毫秒整数。"""
    return int(dt.timestamp() * 1000)

def _session_ranges_for(d: datetime) -> List[Tuple[datetime, datetime]]:
    """返回当天上午/下午会话（带时区）。"""
    tz = pd.Timestamp.now(tz=TZ_SHANGHAI).tz
    s1 = d.replace(hour=9, minute=30, second=0, microsecond=0, tzinfo=tz)
    e1 = d.replace(hour=11, minute=30, second=0, microsecond=0, tzinfo=tz)
    s2 = d.replace(hour=13, minute=0, second=0, microsecond=0, tzinfo=tz)
    e2 = d.replace(hour=15, minute=0, second=0, microsecond=0, tzinfo=tz)
    return [(s1, e1), (s2, e2)]

def _align_right_edge(t: datetime, minutes: int) -> datetime:
    """按步长对齐到“右端”分钟边界（不越界会话）。"""
    tm = t.replace(second=0, microsecond=0)
    minutes_since_midnight = tm.hour * 60 + tm.minute
    k = (minutes_since_midnight // minutes) * minutes
    hh, mm = k // 60, k % 60
    return tm.replace(hour=hh, minute=mm)

def _expected_last_end_ts_for_freq(freq: str, now: Optional[datetime] = None) -> Optional[int]:
    """计算应当已生成的最后一根 K 的结束时刻（毫秒）。"""
    now = now or _today_shanghai()
    if not _lazy_is_trading_day(now):
        if freq in {"1d","1w","1M"}:
            d = now
            for _ in range(7):
                d = d - timedelta(days=1)
                if _lazy_is_trading_day(d):
                    now = d
                    break
        else:
            return None
    if freq in {"1m","5m","15m","30m","60m"}:
        minutes = int(freq.replace("m",""))
        t = now - timedelta(seconds=MINUTE_GRACE_SEC)
        for s, e in _session_ranges_for(now):
            if s <= t <= e:
                edge = _align_right_edge(t, minutes)
                if edge < s: edge = s
                if edge > e: edge = e
                return _ms_from_dt(edge)
        s_am, e_am = _session_ranges_for(now)[0]
        s_pm, e_pm = _session_ranges_for(now)[1]
        if t < s_am:
            prev = now
            while True:
                prev = prev - timedelta(days=1)
                if _lazy_is_trading_day(prev):
                    return _ms_from_dt(_session_ranges_for(prev)[1][1])
        if e_am < t < s_pm:
            return _ms_from_dt(e_am)
        if t > e_pm:
            return _ms_from_dt(e_pm)
        return None
    grace = timedelta(seconds=DAILY_GRACE_SEC)
    today_1500 = now.replace(hour=15, minute=0, second=0, microsecond=0)
    if freq == "1d":
        return _ms_from_dt(today_1500 if (now - grace) >= today_1500 else _last_trading_day_1500(now))
    if freq == "1w":
        weekday = now.weekday()
        days_to_fri = 4 - weekday
        this_fri = now + timedelta(days=days_to_fri)
        d = this_fri
        for _ in range(7):
            if _lazy_is_trading_day(d):
                break
            d = d - timedelta(days=1)
        d_1500 = d.replace(hour=15, minute=0, second=0, microsecond=0)
        if (now - grace) >= d_1500:
            return _ms_from_dt(d_1500)
        prev_week_1500 = _last_week_last_trading_1500(now)
        return _ms_from_dt(prev_week_1500)
    if freq == "1M":
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1, tzinfo=now.tzinfo)
        else:
            next_month = datetime(now.year, now.month + 1, 1, tzinfo=now.tzinfo)
        last_day = next_month - timedelta(days=1)
        d = last_day
        for _ in range(7):
            if _lazy_is_trading_day(d): break
            d = d - timedelta(days=1)
        d_1500 = d.replace(hour=15, minute=0, second=0, microsecond=0)
        if (now - grace) >= d_1500:
            return _ms_from_dt(d_1500)
        last_month_last_day = (now.replace(day=1) - timedelta(days=1))
        d = last_month_last_day
        for _ in range(7):
            if _lazy_is_trading_day(d): break
            d = d - timedelta(days=1)
        return _ms_from_dt(d.replace(hour=15, minute=0, second=0, microsecond=0))
    return None

def _last_trading_day_1500(now: datetime) -> datetime:
    """上一交易日 15:00（datetime）。"""
    d = now
    while True:
        d = d - timedelta(days=1)
        if _lazy_is_trading_day(d):
            return d.replace(hour=15, minute=0, second=0, microsecond=0)

def _prev_week_last_trading_1500(now: datetime) -> int:
    """上周最后交易日 15:00（毫秒）。"""
    d = now - timedelta(days=7)
    weekday = d.weekday()
    days_to_fri = 4 - weekday
    fri = d + timedelta(days=days_to_fri)
    x = fri
    for _ in range(7):
        if _lazy_is_trading_day(x): break
        x = x - timedelta(days=1)
    return _ms_from_dt(x.replace(hour=15, minute=0, second=0, microsecond=0))

def _last_week_last_trading_1500(now: datetime) -> datetime:
    """上周最后一个交易日的 15:00（返回 datetime）。"""
    d = now - timedelta(days=7)
    weekday = d.weekday()
    days_to_fri = 4 - weekday
    fri = d + timedelta(days=days_to_fri)
    x = fri
    for _ in range(7):
        if _lazy_is_trading_day(x):
            break
        x = x - timedelta(days=1)
    return x.replace(hour=15, minute=0, second=0, microsecond=0)

def _to_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    """SQLite 行 → DataFrame（齐列 + 升序）。"""
    if not rows:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","amount","turnover_rate","source"])
    df = pd.DataFrame(rows)
    for c in ["ts","open","high","low","close","volume","amount","turnover_rate","source"]:
        if c not in df.columns:
            df[c] = ("" if c == "source" else np.nan)
    for c in ["open","high","low","close","volume","amount","turnover_rate"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[["ts","open","high","low","close","volume","amount","turnover_rate","source"]].sort_values("ts").reset_index(drop=True)
    return df

def _dominant_source(df: pd.DataFrame) -> str:
    """统计 DF 中最多的 source（provider）。"""
    if df is None or df.empty or "source" not in df.columns:
        return ""
    c = Counter(df["source"].dropna().astype(str).tolist())
    return c.most_common(1)[0][0] if c else ""

def _get_symbol_type(symbol: str) -> str:
    """推断标的品类：优先 symbol_index，否则按代码前缀弱推断。"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT type FROM symbol_index WHERE symbol=? LIMIT 1;", (symbol,))
        r = cur.fetchone()
        if r and r[0]:
            t = str(r[0]).strip().upper()
            if t in {"A","ETF","LOF"}:
                return t
    except Exception:
        pass
    s = (symbol or "").strip()
    if len(s) == 6 and s.startswith(("15","16","5")):
        return "ETF"
    return "A"

def _has_ts_freq(symbol: str, freq: str, ts: int) -> bool:
    """缓存表是否已存在该 (symbol,freq,ts)。"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM candles_cache WHERE symbol=? AND freq=? AND adjust='none' AND ts=? LIMIT 1;", (symbol, freq, int(ts)))
    return bool(cur.fetchone())

def _resample_window(df: pd.DataFrame, window_start_ms: int, window_end_ms: int) -> Optional[Dict[str, float]]:
    """窗口内重采样（开=首、收=尾、高=最大、低=最小、量/额=求和）。"""
    if df is None or df.empty:
        return None
    sub = df[(df["ts"] >= window_start_ms) & (df["ts"] <= window_end_ms)]
    if sub.empty:
        return None
    o = float(sub.iloc[0]["open"])
    c = float(sub.iloc[-1]["close"])
    h = float(sub["high"].max())
    l = float(sub["low"].min())
    v = float(pd.to_numeric(sub["volume"], errors="coerce").fillna(0).sum())
    a = float(pd.to_numeric(sub["amount"], errors="coerce").fillna(0).sum()) if "amount" in sub.columns else None
    return {"o": o, "h": h, "l": l, "c": c, "v": v, "a": a}

def _read_local(symbol: str, freq: str, start_ms: Optional[int], end_ms: Optional[int], sec_type: str) -> pd.DataFrame:
    """从本地 DB 读取目标频率窗口数据。"""
    if freq == "1d":
        return _to_df(select_candles(symbol, "1d", "none", start_ms, end_ms))
    return _to_df(select_cache_candles(symbol, freq, "none", start_ms, end_ms))

def _nn(x):  # NaN→None，否则 float
    return None if pd.isna(x) else float(x)

def _resample_minutes_series(df_1m: pd.DataFrame, target_minutes: int) -> pd.DataFrame:
    """将 1m 序列重采样为 target_minutes（会话切片，右端对齐）。"""
    if df_1m is None or df_1m.empty:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","amount","turnover_rate","source"])
    x = df_1m.copy().sort_values("ts").reset_index(drop=True)
    dt = pd.to_datetime(x["ts"], unit="ms", utc=False).dt.tz_localize(TZ_SHANGHAI, nonexistent="shift_forward", ambiguous="infer")
    hh = dt.dt.hour
    mm = dt.dt.minute
    in_am = (hh > 9) | ((hh == 9) & (mm >= 30))
    in_am &= (hh < 11) | ((hh == 11) & (mm <= 30))
    in_pm = (hh >= 13) & (hh <= 15)
    session = np.where(in_am, "AM", np.where(in_pm, "PM", None))
    x = x[session != None].copy()
    dt = dt[session != None]
    base_minutes = np.where(session == "AM", (9 * 60 + 30), (13 * 60 + 0))
    curr_minutes = hh[session != None] * 60 + mm[session != None]
    rel_minutes = curr_minutes - base_minutes
    win_id = (rel_minutes // target_minutes).astype(int)
    date_str = dt.dt.strftime("%Y-%m-%d")
    key = pd.Series(date_str + "|" + session[session != None] + "|" + win_id.astype(str), index=x.index)
    x["key"] = key
    grp = x.groupby("key", sort=True)
    rows = []
    for _, g in grp:
        g = g.sort_values("ts")
        ts_end = int(g["ts"].iloc[-1])  # 窗口右端（最后一根 1m 的 ts，已是右端）
        rows.append({
            "ts": ts_end,
            "open": float(g["open"].iloc[0]),
            "high": float(pd.to_numeric(g["high"], errors="coerce").max()),
            "low":  float(pd.to_numeric(g["low"], errors="coerce").min()),
            "close": float(g["close"].iloc[-1]),
            "volume": float(pd.to_numeric(g["volume"], errors="coerce").fillna(0).sum()),
            "amount": float(pd.to_numeric(g["amount"], errors="coerce").fillna(0).sum()) if "amount" in g.columns else None,
            "turnover_rate": None,
            "source": "resample",
        })
    out = pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)
    return out

def _fallback_resample_from_1m(symbol: str, target_freq: str, sec_type: str, preferred_key: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """分钟族兜底：全量拉 1m → 重采样为 target_freq（5/15/30/60m）。返回 (provider, source_key)。"""
    if target_freq not in {"5m","15m","30m","60m"}:
        return (None, None)
    start_ms = START_1990_MS
    end_ms = int(time.time() * 1000)
    def _fetch_1m():
        return fetch_period_ms(symbol, "1m", start_ms, end_ms, sec_type=sec_type, iface_key=None)
    df_1m, provider_1m, src_key_1m = _retry(_fetch_1m) or (pd.DataFrame(), "", None)
    if df_1m is None or df_1m.empty:
        return (None, None)
    minutes_map = {"5m":5, "15m":15, "30m":30, "60m":60}
    df_rs = _resample_minutes_series(df_1m, minutes_map[target_freq])
    if df_rs is None or df_rs.empty:
        return (None, None)
    rows = []
    for _, r in df_rs.iterrows():
        rows.append((
            symbol, target_freq, "none", int(r["ts"]),
            float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
            float(r["volume"] if pd.notna(r["volume"]) else 0.0),
            float(r["amount"]) if pd.notna(r.get("amount", np.nan)) else None,
            None,
            "resample",
            datetime.now().isoformat(),
            f"resample_1m_to_{target_freq}",
        ))
    if rows:
        upsert_cache_candles(rows)
        rebuild_cache_meta(symbol, target_freq, "none")
        try:
            log_event(
                _LOG, service="market", level="INFO",
                file=__file__, func="_fallback_resample_from_1m", line=0, trace_id=None,
                event="fallback.resample", message="resampled minutes",
                extra={"category": "resample", "action": "done",
                       "request": {"symbol": symbol, "from": "1m", "target_freq": target_freq},
                       "result": {"rows": len(rows), "summary": f"1m->{target_freq}"}}
            )
        except Exception:
            pass
        return ("resample", f"resample_1m_to_{target_freq}")
    return (None, None)

def _resample_daily_to(df_1d: pd.DataFrame, target_freq: str) -> pd.DataFrame:
    """将 1d 序列重采样为 1w/1M（W-FRI / 月末），ts 为该组最后一天的 15:00。"""
    if df_1d is None or df_1d.empty:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","amount","turnover_rate","source"])
    x = df_1d.copy().sort_values("ts").reset_index(drop=True)
    dt0 = pd.to_datetime(x["ts"], unit="ms", utc=False).dt.tz_localize(TZ_SHANGHAI, nonexistent="shift_forward", ambiguous="infer")
    date_str = dt0.dt.strftime("%Y-%m-%d")
    if target_freq == "1w":
        key = pd.to_datetime(date_str).to_period("W-FRI").astype(str)
    elif target_freq == "1M":
        key = pd.to_datetime(date_str).to_period("M").astype(str)
    else:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","amount","turnover_rate","source"])
    x["key"] = key
    grp = x.groupby("key", sort=True)
    rows = []
    for _, g in grp:
        g = g.sort_values("ts")
        last_ts = int(g["ts"].iloc[-1])
        last_date = pd.to_datetime(last_ts, unit="ms", utc=False).tz_localize(TZ_SHANGHAI, nonexistent="shift_forward", ambiguous="infer")
        last_date_1500 = last_date.normalize() + pd.Timedelta(hours=15)
        ts_end_1500 = int(last_date_1500.value // 10**6)
        rows.append({
            "ts": ts_end_1500,
            "open": float(g["open"].iloc[0]),
            "high": float(pd.to_numeric(g["high"], errors="coerce").max()),
            "low":  float(pd.to_numeric(g["low"], errors="coerce").min()),
            "close": float(g["close"].iloc[-1]),
            "volume": float(pd.to_numeric(g["volume"], errors="coerce").fillna(0).sum()),
            "amount": float(pd.to_numeric(g["amount"], errors="coerce").fillna(0).sum()) if "amount" in g.columns else None,
            "turnover_rate": None,
            "source": "resample",
        })
    out = pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)
    return out

def _fallback_resample_from_1d(symbol: str, target_freq: str) -> Tuple[Optional[str], Optional[str]]:
    """周/月兜底：从本地 1d 重采样为 1w/1M；返回 (provider, source_key)。"""
    if target_freq not in {"1w","1M"}:
        return (None, None)
    try:
        ensure_daily_recent(symbol)
    except Exception:
        pass
    df_1d = _read_local(symbol, "1d", None, None, _get_symbol_type(symbol))
    if df_1d is None or df_1d.empty:
        return (None, None)
    df_rs = _resample_daily_to(df_1d, target_freq)
    if df_rs is None or df_rs.empty:
        return (None, None)
    rows = []
    for _, r in df_rs.iterrows():
        rows.append((
            symbol, target_freq, "none", int(r["ts"]),
            float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
            float(r["volume"] if pd.notna(r["volume"]) else 0.0),
            float(r["amount"]) if pd.notna(r.get("amount", np.nan)) else None,
            None,
            "resample",
            datetime.now().isoformat(),
            f"resample_1d_to_{target_freq}",
        ))
    if rows:
        upsert_cache_candles(rows)
        rebuild_cache_meta(symbol, target_freq, "none")
        try:
            log_event(
                _LOG, service="market", level="INFO",
                file=__file__, func="_fallback_resample_from_1d", line=0, trace_id=None,
                event="fallback.resample", message="resampled daily",
                extra={"category": "resample", "action": "done",
                       "request": {"symbol": symbol, "from": "1d", "target_freq": target_freq},
                       "result": {"rows": len(rows), "summary": f"1d->{target_freq}"}}
            )
        except Exception:
            pass
        return ("resample", f"resample_1d_to_{target_freq}")
    return (None, None)

def _ensure_near_end_for_freq(symbol: str, freq: str, sec_type: str, preferred_iface_key: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """保证非 1d 周期近端达标（整窗拉取，失败时兜底重采样）。"""
    if freq == "1d":
        return (None, None)
    now = _today_shanghai()
    expected_ts = _expected_last_end_ts_for_freq(freq, now)
    meta = get_cache_meta(symbol, freq, "none")
    last_ts = int(meta["last_ts"]) if meta and meta.get("last_ts") is not None else None
    if expected_ts is None:
        return (None, None)
    if last_ts is not None and last_ts >= int(expected_ts):
        return (None, None)
    start_ms = START_1990_MS
    end_ms = int(time.time() * 1000)
    def _fetch():
        return fetch_period_ms(symbol, freq, start_ms, end_ms, sec_type=sec_type, iface_key=preferred_iface_key)
    df_fetch, provider, src_key = _retry(_fetch) or (pd.DataFrame(), "", None)
    if df_fetch is not None and not df_fetch.empty:
        x = df_fetch.drop_duplicates(subset=["ts"]).sort_values("ts").reset_index(drop=True)
        has_amt = "amount" in x.columns
        has_tvr = "turnover_rate" in x.columns
        rows = []
        for _, r in x.iterrows():
            rows.append((
                symbol, freq, "none", int(r["ts"]),
                float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
                float(r["volume"] if pd.notna(r["volume"]) else 0.0),
                float(r["amount"]) if has_amt and pd.notna(r["amount"]) else None,
                float(r["turnover_rate"]) if has_tvr and pd.notna(r["turnover_rate"]) else None,
                provider or "",
                datetime.now().isoformat(),
                src_key or None,
            ))
        if rows:
            upsert_cache_candles(rows)
            rebuild_cache_meta(symbol, freq, "none")
        return (provider or None, src_key)
    if freq in {"5m","15m","30m","60m"}:
        prov, key = _fallback_resample_from_1m(symbol, freq, sec_type, preferred_iface_key)
        if prov:
            return (prov, key)
    if freq in {"1w","1M"}:
        prov, key = _fallback_resample_from_1d(symbol, freq)
        if prov:
            return (prov, key)
    touch_cache_meta(symbol, freq, "none")
    return (None, None)

def _apply_adjustment(df_none: pd.DataFrame, symbol: str, adjust: str) -> pd.DataFrame:
    """对不复权 DataFrame 应用前/后复权。"""
    if df_none.empty or adjust not in ('qfq', 'hfq'):
        return df_none
    start_ymd = yyyymmdd_from_ms(df_none['ts'].min())
    end_ymd = yyyymmdd_from_ms(df_none['ts'].max())
    factors_raw = select_factors(symbol, start_ymd, end_ymd)
    if not factors_raw:
        return df_none
    df_factors = pd.DataFrame(factors_raw).set_index('date')
    factor_col = f'{adjust}_factor'
    df_adj = df_none.copy()
    df_adj['date'] = df_adj['ts'].apply(yyyymmdd_from_ms)
    df_adj[factor_col] = df_adj['date'].map(df_factors[factor_col])
    df_adj[factor_col] = df_adj[factor_col].ffill()
    df_adj[factor_col] = df_adj[factor_col].fillna(1.0)
    for col in ['open','high','low','close']:
        df_adj[col] = df_adj[col] * df_adj[factor_col]
    df_adj['volume'] = df_adj['volume'] / df_adj[factor_col]
    return df_adj.drop(columns=['date', factor_col])

def assemble_response(symbol: str, freq: str, adjust: str, df: pd.DataFrame,
                      include: Set[str], ma_periods_map: Dict[str, int], trace_id: Optional[str],
                      downsample_from: Optional[str] = None,
                      source: Optional[str] = None, source_key: Optional[str] = None,
                      # NEW: 统一可视窗口（索引基于 ALL）
                      view_start_idx: int = 0, view_end_idx: int = -1,
                      window_preset_effective: str = "ALL") -> Dict[str, Any]:
    """组装 /api/candles 响应（返回 ALL 序列 + 可视窗口索引）。"""
    if df is None or df.empty:
        return {
            "meta": {
                "symbol": symbol, "freq": freq, "adjust": adjust, "rows": 0,
                "start": None, "end": None,
                "generated_at": pd.Timestamp.now(tz=TZ_SHANGHAI).isoformat(),
                "algo_version": "market_v2.8",
                "timezone": settings.timezone,
                "source": source or "",
                "source_key": source_key,
                "downsample_from": downsample_from,
                "is_cached": True,
                "trace_id": trace_id,
                # NEW
                "all_rows": 0,
                "view_rows": 0,
                "view_start_idx": 0,
                "view_end_idx": -1,
                "window_preset_effective": "ALL",
            },
            "candles": [],
            "indicators": {"VOLUME": []}
        }

    vol = df["volume"]
    amt = df["amount"] if "amount" in df.columns else pd.Series([pd.NA]*len(df))
    tvr = df["turnover_rate"] if "turnover_rate" in df.columns else pd.Series([pd.NA]*len(df))
    candles_payload = [{
        "t": pd.Timestamp(ms, unit="ms", tz=TZ_SHANGHAI).isoformat(),
        "o": _nn(o), "h": _nn(h), "l": _nn(l), "c": _nn(c),
        "v": _nn(v), "a": _nn(a), "tr": _nn(tr),
    } for ms, o, h, l, c, v, a, tr in zip(df["ts"], df["open"], df["high"], df["low"], df["close"], vol, amt, tvr)]

    inds: Dict[str, List[Optional[float]]] = {}
    inds["VOLUME"] = [None if pd.isna(x) else float(x) for x in vol]
    close = df["close"].astype(float); high = df["high"].astype(float); low = df["low"].astype(float)
    if "ma" in include and ma_periods_map:
        for k, s in ma(close, ma_periods_map).items():
            inds[k] = [None if pd.isna(x) else float(x) for x in s]
    if "macd" in include:
        for k, s in macd(close).items():
            inds[k] = [None if pd.isna(x) else float(x) for x in s]
    if "kdj" in include:
        for k, s in kdj(high, low, close).items():
            inds[k] = [None if pd.isna(x) else float(x) for x in s]
    if "rsi" in include:
        for k, s in rsi(close).items():
            inds[k] = [None if pd.isna(x) else float(x) for x in s]
    if "boll" in include:
        for k, s in boll(close).items():
            inds[k] = [None if pd.isna(x) else float(x) for x in s]

    all_rows = int(len(df))
    v_s = max(0, int(view_start_idx))
    v_e = min(all_rows - 1, int(view_end_idx)) if all_rows > 0 else -1
    if v_s > v_e:
        v_s, v_e = 0, all_rows - 1
    view_rows = max(0, v_e - v_s + 1) if all_rows > 0 else 0

    start_iso = pd.Timestamp(df["ts"].iloc[v_s], unit="ms", tz=TZ_SHANGHAI).isoformat() if view_rows > 0 else None
    end_iso   = pd.Timestamp(df["ts"].iloc[v_e], unit="ms", tz=TZ_SHANGHAI).isoformat() if view_rows > 0 else None

    src = source or _dominant_source(df)
    meta = {
        "symbol": symbol, "freq": freq, "adjust": adjust,
        "rows": int(len(df)),
        "start": start_iso,
        "end": end_iso,
        "generated_at": pd.Timestamp.now(tz=TZ_SHANGHAI).isoformat(),
        "algo_version": "market_v2.8",
        "timezone": settings.timezone,
        "source": src,
        "source_key": source_key,
        "downsample_from": downsample_from,
        "is_cached": True,
        "trace_id": trace_id,
        # NEW：统一视图窗口
        "all_rows": all_rows,
        "view_rows": view_rows,
        "view_start_idx": v_s,
        "view_end_idx": v_e,
        "window_preset_effective": str(window_preset_effective or "ALL"),
    }
    return {"meta": meta, "candles": candles_payload, "indicators": inds}

def get_candles(symbol: str, freq: str, adjust: str = "none",
                start_ms: Optional[int] = None, end_ms: Optional[int] = None,
                include: Optional[Set[str]] = None,
                ma_periods_map: Optional[Dict[str, int]] = None,
                trace_id: Optional[str] = None,
                preferred_iface_key: Optional[str] = None,
                # NEW：统一视窗计算参数
                window_preset: Optional[str] = None,
                bars: Optional[int] = None,
                anchor_ts: Optional[int] = None) -> Dict[str, Any]:
    """
    主入口：继续保障 ALL 数据正确，同时服务端一次成型计算“可视切片”的 v_s/v_e。
    - 返回 ALL candles（不裁剪），meta 中提供 view_*，前端仅应用 dataZoom。
    """
    # 先保障 1d（供 1w/1M 兜底）
    try:
        ensure_daily_recent(symbol, preferred_iface_key)
    except Exception:
        pass

    sec_type = _get_symbol_type(symbol)

    # 保障非 1d 的近端
    src_prov, src_key = (None, None)
    try:
        src_prov, src_key = _ensure_near_end_for_freq(symbol, freq, sec_type, preferred_iface_key)
    except Exception:
        pass

    # 读取 ALL（不裁剪）
    df = _read_local(symbol, freq, None, None, sec_type)
    df_final = _apply_adjustment(df, symbol, adjust)

    all_rows = int(len(df_final))
    if all_rows <= 0:
        return assemble_response(symbol, freq, adjust, df_final,
                                 include or set(), ma_periods_map or {}, trace_id,
                                 downsample_from="1m" if (src_prov == "resample") else None,
                                 source=src_prov, source_key=src_key,
                                 view_start_idx=0, view_end_idx=-1,
                                 window_preset_effective="ALL")

    # 1) bars_target：bars 优先；否则按 window_preset 查表；都无 → ALL
    if bars is not None and int(bars) > 0:
        bars_target = max(1, min(int(bars), all_rows))
        wp_eff = window_preset or "ALL"
    else:
        wp = (window_preset or "ALL").upper()
        bars_target = preset_to_bars(freq, wp, all_rows)
        wp_eff = "ALL" if bars_target >= all_rows else wp

    # 2) e_idx（右端）：按 anchor_ts，否则最右
    if anchor_ts is not None:
        try:
            ts_series = df_final["ts"].astype("int64").tolist()
            e_idx = all_rows - 1
            for i in range(all_rows - 1, -1, -1):
                if int(ts_series[i]) <= int(anchor_ts):
                    e_idx = i
                    break
        except Exception:
            e_idx = all_rows - 1
    else:
        e_idx = all_rows - 1

    # 3) s_idx：右端锚定向左推；如左端越界且不足 bars_target，则反推右端
    s_idx = max(0, e_idx - bars_target + 1)
    if s_idx == 0 and (e_idx - s_idx + 1) < bars_target:
        e_idx = min(all_rows - 1, bars_target - 1)

    view_rows = max(1, min(all_rows, e_idx - s_idx + 1))
    if view_rows >= all_rows:
        wp_eff = "ALL"

    return assemble_response(symbol, freq, adjust, df_final,
                             include or set(), ma_periods_map or {}, trace_id,
                             downsample_from="1m" if (src_prov == "resample") else None,
                             source=src_prov, source_key=src_key,
                             view_start_idx=s_idx, view_end_idx=e_idx,
                             window_preset_effective=wp_eff)
