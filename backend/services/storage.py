# backend/services/storage.py  # 存储服务（修复：1d 取数��路兼容 iface_key + 新版 fetch_period_ms）
# ==============================
# 说明：
# - ensure_daily_recent(symbol, iface_key=None)：支持“方法键”选择具体数据源方法；
#   使用新版 fetch_period_ms 返回 (df, provider, source_key)，写入永久表 candles：
#     * source  = provider（em/sina/ak/tx）
#     * revision= source_key（如 'A_1d_a'）
# - 其余接口（cleanup_cache 等）保持不变。
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
from backend.utils.time import yyyymmdd_from_ms, ms_from_yyyymmdd  # 时间工具
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
    确保“任意标的”的 1d 近端最新（永久库 candles）：
    - 判定 candles 中该 symbol 的 1d 最新日 >= expected 则跳过
    - 否则：通过新版 fetch_period_ms 取 [19900101, expected] 的 1d（可按 iface_key 选择方法），UPSERT 到 candles
    - 若该标的为 A 股：同时拉取并 UPSERT 复权因子（ak 因子接口）
    返回：简要动作信息
    """
    conn = get_conn(); cur = conn.cursor()  # DB 连接
    # 查询现有最新日线 ts
    cur.execute("SELECT MAX(ts) AS mx FROM candles WHERE symbol=? AND freq='1d' AND adjust='none';", (symbol,))
    row = cur.fetchone(); mx_ts = row["mx"]  # 可能为 None

    # 计算“应更新到的自然日”（Asia/Shanghai）
    expected = _expected_latest_trading_day()

    # 若已有最新记录日期 >= 目标日期 → 跳过更新
    if mx_ts is not None:
        latest = yyyymmdd_from_ms(int(mx_ts))
        if latest >= expected:
            return {"ok": True, "action": "skip", "expected": expected, "latest": latest}

    # 准备取数窗口（整窗）
    start_ms = ms_from_yyyymmdd(19900101)  # 左端：1990-01-01
    end_ms = int(datetime.now().timestamp() * 1000)  # 右端：当前时刻
    sec_type = _infer_symbol_type(symbol)  # 品类：'A'|'ETF'|'LOF'

    # 抓取 1d（新版：返回 df, provider, source_key）
    def _fetch_price():
        return fetch_period_ms(symbol, "1d", start_ms, end_ms, sec_type=sec_type, iface_key=iface_key)
    df_price, provider, source_key = _retry(_fetch_price) or (pd.DataFrame(), "", None)

    rows = []  # 待写入
    if df_price is not None and not df_price.empty:
        x = df_price.sort_values("ts").drop_duplicates(subset=["ts"])  # 时间升序 + 去重
        has_tvr = "turnover_rate" in x.columns  # 是否包含换手率
        for _, r in x.iterrows():
            rows.append((
                symbol, "1d", "none", int(r["ts"]),              # 维度键
                float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),  # OHLC
                float(r["volume"] if pd.notna(r["volume"]) else 0.0),                    # volume
                float(r["amount"]) if "amount" in x.columns and pd.notna(r["amount"]) else None,  # amount
                float(r["turnover_rate"]) if has_tvr and pd.notna(r["turnover_rate"]) else None,  # turnover_rate
                (provider or "ak"),                    # source ← 提供方（默认回退 ak）
                datetime.now().isoformat(),            # fetched_at
                (source_key or None)                   # revision ← 方法键（如 'A_1d_a'）
            ))
        if rows:
            upsert_candles(rows)  # 批量 UPSERT

    # A 股：同步复权因子（qfq/hfq）
    if _infer_symbol_type(symbol) == "A":
        try:
            _df_none, df_factors = fetch_daily_none_and_factors(symbol, 19900101, expected)  # 拉取因子
            if df_factors is not None and not df_factors.empty:
                now_iso = datetime.now().isoformat()
                facs = []
                for _, r in df_factors.iterrows():
                    facs.append((
                        symbol, int(r["date"]), float(r["qfq_factor"]), float(r["hfq_factor"]), now_iso
                    ))
                if facs:
                    upsert_factors(facs)  # UPSERT 因子表
        except Exception:
            # 因子失败不可阻断主流程（保持静默）
            pass

    # 返回摘要（便于日志与 API 调试查看）
    return {
        "ok": True,
        "action": "update" if rows else "noop",
        "expected": expected,
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
