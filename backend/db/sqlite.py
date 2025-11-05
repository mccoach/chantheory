# backend/db/sqlite.py
# ==============================
# 说明：SQLite 数据库接口 (REFACTORED for new task scheduling)
# - (MODIFIED) 调整 Schema: `sync_tasks` 简化, 新增 `task_cursor`, `sync_failures`
# - (MODIFIED) 相关的CRUD函数进行适配。
# ==============================

from __future__ import annotations

import sqlite3
import asyncio
from pathlib import Path
from typing import Iterable, Tuple, List, Optional, Dict, Any
from datetime import datetime
import threading
import json
import pandas as pd

from backend.settings import settings
from backend.utils.time import now_iso

_LOCAL = threading.local()
_GEN: int = 0

def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row

def get_conn() -> sqlite3.Connection:
    global _LOCAL, _GEN
    conn: Optional[sqlite3.Connection] = getattr(_LOCAL, "conn", None)
    gen: Optional[int] = getattr(_LOCAL, "gen", None)
    if conn is not None and gen == _GEN:
        return conn
    if conn is not None:
        try: conn.close()
        except Exception: pass
        setattr(_LOCAL, "conn", None)
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(settings.db_path),
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False
    )
    _apply_pragmas(conn)
    setattr(_LOCAL, "conn", conn)
    setattr(_LOCAL, "gen", _GEN)
    return conn

def init_schema() -> None:
    """初始化数据库所有表的Schema和索引。"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS candles_raw (
      symbol TEXT NOT NULL, freq TEXT NOT NULL, ts INTEGER NOT NULL,
      open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
      volume REAL NOT NULL, amount REAL, turnover_rate REAL,
      source TEXT NOT NULL, fetched_at TEXT NOT NULL,
      PRIMARY KEY (symbol, freq, ts)
    );""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_candles_raw_main ON candles_raw(symbol, freq, ts);")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS adj_factors (
      symbol TEXT NOT NULL, date INTEGER NOT NULL, qfq_factor REAL NOT NULL,
      hfq_factor REAL NOT NULL, updated_at TEXT, PRIMARY KEY (symbol, date)
    );""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_adj_factors_symdate ON adj_factors(symbol,date);")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_index (
      symbol TEXT PRIMARY KEY, name TEXT NOT NULL, market TEXT, type TEXT, updated_at TEXT NOT NULL
    );""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_watchlist (
      symbol TEXT PRIMARY KEY, added_at TEXT NOT NULL, source TEXT, note TEXT, updated_at TEXT
    );""")
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_profile (
        symbol TEXT PRIMARY KEY, listing_date INTEGER, total_shares REAL, float_shares REAL,
        industry TEXT, region TEXT, concepts TEXT, intro TEXT, updated_at TEXT,
        FOREIGN KEY (symbol) REFERENCES symbol_index (symbol)
    );""")
    
    # (MODIFIED) 简化 sync_tasks 表，只存任务定义
    cur.execute("DROP TABLE IF EXISTS sync_tasks;")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sync_tasks (
        task_id TEXT PRIMARY KEY,
        symbol TEXT NOT NULL,
        freq TEXT NOT NULL,
        priority INTEGER NOT NULL,
        created_at TEXT NOT NULL
    );""")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sync_tasks_uniq ON sync_tasks(symbol, freq);")

    # (NEW) 新增 task_cursor 表，作为稳定执行清单
    cur.execute("DROP TABLE IF EXISTS task_cursor;")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS task_cursor (
        cursor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL UNIQUE,
        FOREIGN KEY (task_id) REFERENCES sync_tasks (task_id) ON DELETE CASCADE
    );
    """)

    # (NEW) 新增 sync_failures 表，记录失败任务
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sync_failures (
        failure_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        freq TEXT NOT NULL,
        priority INTEGER,
        error_message TEXT,
        failed_at TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_failures_time ON sync_failures(failed_at);")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trade_calendar (
        date INTEGER PRIMARY KEY, market TEXT NOT NULL, is_trading_day INTEGER NOT NULL
    );""")

    cur.execute("DROP TABLE IF EXISTS symbol_history;")
    cur.execute("DROP TABLE IF EXISTS symbol_index_summary;")
    cur.execute("DROP TABLE IF EXISTS candles;")

    conn.commit()

# ---- K线数据读写 ----
def upsert_candles_raw(rows: Iterable[Dict[str, Any]]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    sql = """
    INSERT INTO candles_raw (symbol,freq,ts,open,high,low,close,volume,amount,turnover_rate,source,fetched_at)
    VALUES (:symbol,:freq,:ts,:open,:high,:low,:close,:volume,:amount,:turnover_rate,:source,:fetched_at)
    ON CONFLICT(symbol,freq,ts) DO UPDATE SET
      open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
      volume=excluded.volume, amount=excluded.amount, turnover_rate=excluded.turnover_rate,
      source=excluded.source, fetched_at=excluded.fetched_at;
    """
    def _prep(r: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(r or {})
        for key, value in d.items():
            if pd.isna(value): d[key] = None
        d['fetched_at'] = d.get('fetched_at') or now_iso()
        return d
    
    list_rows = list(rows)
    if not list_rows: return 0
        
    cur.executemany(sql, [_prep(r) for r in list_rows])
    conn.commit()
    return cur.rowcount

async def upsert_candles_raw_async(rows: Iterable[Dict[str, Any]]) -> int:
    return await asyncio.to_thread(upsert_candles_raw, rows)

def select_candles_raw_for_stitch(symbol: str, freq: str, ts_begin: Optional[int], ts_end: Optional[int]) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    conds = ["symbol=? AND freq=?"]
    args: List[Any] = [symbol, freq]
    if ts_begin is not None: conds.append("ts>=?"); args.append(int(ts_begin))
    if ts_end is not None: conds.append("ts<=?"); args.append(int(ts_end))
    sql = f"SELECT ts, open, high, low, close, volume, amount, turnover_rate, source, freq FROM candles_raw WHERE {' AND '.join(conds)} ORDER BY ts ASC;"
    cur.execute(sql, tuple(args))
    return [dict(r) for r in cur.fetchall()]

async def select_candles_raw_for_stitch_async(symbol: str, freq: str, ts_begin: Optional[int], ts_end: Optional[int]) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(select_candles_raw_for_stitch, symbol, freq, ts_begin, ts_end)

def get_latest_ts_from_raw(symbol: str, freq: str) -> Optional[int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT MAX(ts) FROM candles_raw WHERE symbol=? AND freq=?;", (symbol, freq))
    row = cur.fetchone()
    return int(row[0]) if row and row[0] is not None else None

# ---- (REFACTORED) 任务调度相关 CRUD ----
def clear_all_tasks():
    """清空所有任务相关表，用于重新生成执行计划。"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM task_cursor;")
    cur.execute("DELETE FROM sync_tasks;")
    conn.commit()

def bulk_insert_sync_tasks(tasks: List[Dict[str, Any]]):
    """批量插入任务定义。"""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    rows = [(t['task_id'], t['symbol'], t['freq'], t['priority'], now) for t in tasks]
    cur.executemany("INSERT INTO sync_tasks (task_id, symbol, freq, priority, created_at) VALUES (?, ?, ?, ?, ?)", rows)
    conn.commit()
    return cur.rowcount

def populate_task_cursor():
    """根据 sync_tasks 的优先级，生成有序的执行清单到 task_cursor。"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO task_cursor (task_id) SELECT task_id FROM sync_tasks ORDER BY priority ASC, symbol ASC, freq ASC;")
    conn.commit()
    return cur.rowcount

def get_task_by_cursor(cursor_id: int) -> Optional[Dict[str, Any]]:
    """通过游标ID获取任务详情。"""
    conn = get_conn()
    cur = conn.cursor()
    sql = """
    SELECT t.* FROM sync_tasks t
    JOIN task_cursor c ON t.task_id = c.task_id
    WHERE c.cursor_id = ?;
    """
    cur.execute(sql, (cursor_id,))
    row = cur.fetchone()
    return dict(row) if row else None

def get_total_task_count() -> int:
    """获取执行清单中的任务总数。"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM task_cursor;")
    row = cur.fetchone()
    return row[0] if row else 0

def record_sync_failure(task: Dict[str, Any], error_message: str):
    """记录任务失败信息。"""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO sync_failures (task_id, symbol, freq, priority, error_message, failed_at) VALUES (?, ?, ?, ?, ?, ?)",
        (task['task_id'], task['symbol'], task['freq'], task.get('priority'), error_message, now)
    )
    conn.commit()

def get_failures_summary() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT symbol, freq, COUNT(1) as count, MAX(failed_at) as last_failed FROM sync_failures GROUP BY symbol, freq ORDER BY last_failed DESC;")
    return [dict(r) for r in cur.fetchall()]
    
# ---- 标的档案表CRUD ----
def upsert_symbol_profile(profiles: List[Dict[str, Any]]):
    conn = get_conn()
    cur = conn.cursor()
    sql = """
    INSERT INTO symbol_profile (symbol, listing_date, total_shares, float_shares, industry, region, concepts, intro, updated_at)
    VALUES (:symbol, :listing_date, :total_shares, :float_shares, :industry, :region, :concepts, :intro, :updated_at)
    ON CONFLICT(symbol) DO UPDATE SET
        listing_date=excluded.listing_date, total_shares=excluded.total_shares, float_shares=excluded.float_shares,
        industry=excluded.industry, region=excluded.region, concepts=excluded.concepts,
        intro=excluded.intro, updated_at=excluded.updated_at;
    """
    now = datetime.now().isoformat()
    for p in profiles:
        p['updated_at'] = now
        p['concepts'] = json.dumps(p.get('concepts'), ensure_ascii=False) if p.get('concepts') else None
    cur.executemany(sql, profiles)
    conn.commit()

def get_listing_date(symbol: str) -> Optional[int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT listing_date FROM symbol_profile WHERE symbol = ?;", (symbol,))
    row = cur.fetchone()
    return int(row[0]) if row and row[0] else None

# ---- 交易日历表CRUD ----
def upsert_trade_calendar(dates: List[Tuple[int, str, int]]):
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany("INSERT OR REPLACE INTO trade_calendar (date, market, is_trading_day) VALUES (?, ?, ?);", dates)
    conn.commit()
    return cur.rowcount
    
# ---- (保持不变的函数) ----
def upsert_factors(rows: Iterable[Tuple[str, int, float, float, str]]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany("INSERT INTO adj_factors(symbol, date, qfq_factor, hfq_factor, updated_at) VALUES (?,?,?,?,?) ON CONFLICT(symbol,date) DO UPDATE SET qfq_factor=excluded.qfq_factor, hfq_factor=excluded.hfq_factor, updated_at=excluded.updated_at;", list(rows))
    conn.commit()
    return cur.rowcount

def select_factors(symbol: str, start_ymd: int, end_ymd: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT date, qfq_factor, hfq_factor FROM adj_factors WHERE symbol=? AND date BETWEEN ? AND ? ORDER BY date ASC;", (symbol, start_ymd, end_ymd))
    return [dict(r) for r in cur.fetchall()]

def select_latest_factor_date(symbol: str) -> Optional[int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) FROM adj_factors WHERE symbol=?;", (symbol,))
    row = cur.fetchone()
    return int(row[0]) if row and row[0] is not None else None

def upsert_symbol_index(rows: Iterable[Tuple[str, str, str, str, str]]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany("INSERT INTO symbol_index(symbol,name,market,type,updated_at) VALUES (?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET name=excluded.name, market=excluded.market, type=excluded.type, updated_at=excluded.updated_at;", list(rows))
    conn.commit()
    return cur.rowcount

def select_symbol_index() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT symbol,name,market,type,updated_at FROM symbol_index ORDER BY symbol ASC;")
    return [dict(r) for r in cur.fetchall()]

def upsert_user_watchlist(rows: Iterable[Tuple[str, str, Optional[str], Optional[str], Optional[str]]]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany("INSERT INTO user_watchlist(symbol, added_at, source, note, updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(symbol) DO UPDATE SET added_at=excluded.added_at, source=excluded.source, note=excluded.note, updated_at=excluded.updated_at;", list(rows))
    conn.commit()
    return cur.rowcount

def delete_user_watchlist(symbol: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_watchlist WHERE symbol=?;", (symbol,))
    conn.commit()
    return cur.rowcount

def select_user_watchlist() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT symbol, added_at, source, note, updated_at FROM user_watchlist ORDER BY symbol ASC;")
    return [dict(r) for r in cur.fetchall()]

def ensure_initialized() -> None:
    init_schema()

def get_usage() -> Dict[str, Any]:
    db_path = Path(settings.db_path)
    size_bytes = db_path.stat().st_size if db_path.exists() else 0
    conn = get_conn()
    cur = conn.cursor()
    table_counts = {}
    tables = ["candles_raw", "adj_factors", "symbol_index", "user_watchlist", "symbol_profile", "sync_tasks", "task_cursor", "sync_failures", "trade_calendar"]
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(1) AS r FROM {table};")
            table_counts[table] = int(cur.fetchone()["r"])
        except sqlite3.OperationalError:
            table_counts[table] = 0
            
    return {
        "db_path": str(db_path),
        "size_bytes": size_bytes,
        "tables": table_counts,
        "checked_at": datetime.now().isoformat(),
    }
