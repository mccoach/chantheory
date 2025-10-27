# backend/services/storage.py  # 存储服务（修复：1d 取数路径兼容 iface_key + 新版 fetch_period_ms）
# ==============================
# 说明：
# - ensure_daily_recent：改为构造“字典行”，与 upsert_candles 的命名占位符一致。
# - ensure_daily_recent：明确返回包含 {ok: bool, ...} 的字典，标志近端保障是否成功。
# ==============================

from __future__ import annotations  # 允许前置注解

from typing import Dict, Any, Optional  # 类型注解
from datetime import datetime  # 时间
import time  # 退避/时间戳
import random  # 退避抖动

import pandas as pd  # DataFrame

from backend.settings import settings  # 全局设置
from backend.db.sqlite import upsert_candles, upsert_factors, get_conn, evict_cache_by_lru  # DB 接口
from backend.datasource.akshare import fetch_daily_none_and_factors  # A 股因子获取
from backend.datasource.fetchers import fetch_period_ms  # 新版抓取入口（返回 df, provider, source_key）
from backend.utils.time import yyyymmdd_from_ms, ms_from_yyyymmdd, format_close_time_str  # 时间工具
from zoneinfo import ZoneInfo  # 时区

def _retry(fn, attempts: int = None, base_ms: int = None):
    """轻量指数退避包装：attempts 次失败后抛出。"""
    a = int(getattr(settings, "retry_max_attempts", 0) if attempts is None else attempts)  # 次数
    base = int(getattr(settings, "retry_base_delay_ms", 500) if base_ms is None else base_ms)  # 基延迟
    last = None  # 记录最后异常
    for i in range(a + 1):  # 最多尝试 a+1 次
        try:
            return fn()  # 执行
        except Exception as e:
            last = e  # 保存异常
            if i >= a:  # 达上限
                break  # 退出
            delay = (base * (2 ** i)) * (0.8 + 0.4 * random.random())  # 指数退避+抖动
            time.sleep(delay / 1000.0)  # 毫秒→秒
    if last:
        raise last  # 抛出最后异常
    return None  # 理论不达

def _prev_trading_day(ymd: int) -> int:
    """简单回退上一交易日（以工作日近似）。"""
    from datetime import datetime as dt, timedelta as td
    d0 = dt(int(str(ymd)[0:4]), int(str(ymd)[4:6]), int(str(ymd)[6:8]))
    for _ in range(1, 8):
        d = d0 - td(days=1)
        if d.weekday() < 5:
            return d.year*10000 + d.month*100 + d.day
        d0 = d
    return ymd

def _expected_latest_trading_day() -> int:
    """若当前为交易日且 >= cutoff_hour 则今天；否则上一个交易日（Asia/Shanghai）。"""
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    ymd = now.year*10000 + now.month*100 + now.day
    if now.weekday() < 5 and now.hour >= int(settings.daily_fresh_cutoff_hour):
        return ymd
    return _prev_trading_day(ymd)

def _infer_symbol_type(symbol: str) -> str:
    """从 symbol_index 解析 type；未命中时弱推断（默认 A，15/16/5 开头 → ETF）。"""
    try:
        conn = get_conn(); cur = conn.cursor()
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

def ensure_daily_recent(symbol: str, iface_key: Optional[str] = None) -> Dict[str, Any]:
    """
    确保“任意标的”的 1d 近端最新。
    - 关键变更: 总是返回一个包含 {ok: bool, ...} 的字典。
    """
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT MAX(ts) AS mx FROM candles WHERE symbol=? AND freq='1d' AND adjust='none';", (symbol,))
    row = cur.fetchone(); mx_ts = row["mx"]

    expected = _expected_latest_trading_day()

    if mx_ts is not None:
        latest = yyyymmdd_from_ms(int(mx_ts))
        if latest >= expected:
            return {"ok": True, "action": "skip", "expected": expected, "latest": latest}

    start_ms = ms_from_yyyymmdd(19900101)
    end_ms = int(datetime.now().timestamp() * 1000)
    sec_type = _infer_symbol_type(symbol)

    try:
        def _fetch_price():
            return fetch_period_ms(symbol, "1d", start_ms, end_ms, sec_type=sec_type, iface_key=iface_key)
        df_price, provider, source_key = _retry(_fetch_price) or (pd.DataFrame(), "", None)
    except Exception as e:
        return {"ok": False, "action": "fetch_fail", "error": str(e)}

    rows: list[Dict[str, Any]] = []
    if df_price is not None and not df_price.empty:
        x = df_price.sort_values("ts").drop_duplicates(subset=["ts"])
        has_tvr = "turnover_rate" in x.columns
        for _, r in x.iterrows():
            ts_val = int(r["ts"])
            rows.append({
                "symbol": symbol, "freq": "1d", "adjust": "none",
                "close_time": format_close_time_str(ts_val, "1d"), "ts": ts_val,
                "open": float(r["open"]), "high": float(r["high"]), "low": float(r["low"]), "close": float(r["close"]),
                "volume": float(r["volume"] if pd.notna(r["volume"]) else 0.0),
                "amount": float(r["amount"]) if "amount" in x.columns and pd.notna(r["amount"]) else None,
                "turnover_rate": float(r["turnover_rate"]) if has_tvr and pd.notna(r["turnover_rate"]) else None,
                "source": (provider or "ak"), "fetched_at": datetime.now().isoformat(), "revision": (source_key or None),
            })
        if rows:
            upsert_candles(rows)

    if _infer_symbol_type(symbol) == "A":
        try:
            _df_none, df_factors = fetch_daily_none_and_factors(symbol, 19900101, expected)
            if df_factors is not None and not df_factors.empty:
                now_iso = datetime.now().isoformat()
                facs = [(symbol, int(r["date"]), float(r["qfq_factor"]), float(r["hfq_factor"]), now_iso) for _, r in df_factors.iterrows()]
                if facs:
                    upsert_factors(facs)
        except Exception:
            pass
    
    # 验证更新后是否达标
    cur.execute("SELECT MAX(ts) AS mx FROM candles WHERE symbol=? AND freq='1d' AND adjust='none';", (symbol,))
    row_after = cur.fetchone(); mx_ts_after = row_after["mx"]
    latest_after = yyyymmdd_from_ms(int(mx_ts_after)) if mx_ts_after is not None else 0
    is_ok_after = latest_after >= expected
    
    return {
        "ok": is_ok_after,
        "action": "update",
        "expected": expected,
        "latest_after": latest_after,
        "provider": provider or "",
        "source_key": source_key or "",
        "rows_written": len(rows)
    }

def cleanup_cache() -> Dict[str, Any]:
    """清理缓存：TTL + LRU 到阈值以内（供 /api/storage/cache/cleanup 使用）。"""
    ttl = max(0, int(settings.cache_ttl_days))
    max_rows = max(0, int(settings.cache_max_rows))
    res = evict_cache_by_lru(max_rows=max_rows, ttl_days=ttl)
    return {"ok": True, "result": res, "ts": datetime.now().isoformat()}
