# backend/db/schema.py
# ==============================
# V3.0 - 精简版（删除冗余表 + 增加级联外键）
# 
# 改动：
#   1. 删除表：sync_tasks, task_cursor, sync_failures（已被内存队列替代）
#   2. 外键增加：ON DELETE CASCADE, ON UPDATE CASCADE（symbol_profile, user_watchlist）
#   3. 删除废弃表：symbol_history, symbol_index_summary, candles（保持原有逻辑）
# ==============================

from __future__ import annotations

from backend.db.connection import get_conn

def init_schema() -> None:
    """
    初始化数据库Schema（V3.0 - 精简版）
    
    核心表（6个）：
    1. candles_raw - K线原始数据
    2. adj_factors - 复权因子
    3. symbol_index - 标的索引（主表）
    4. symbol_profile - 标的档案（外键 → symbol_index）
    5. user_watchlist - 用户自选股（外键 → symbol_index）
    6. trade_calendar - 交易日历
    """
    conn = get_conn()
    cur = conn.cursor()

    # ===== 表1：K线原始数据 =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS candles_raw (
      symbol TEXT NOT NULL,
      freq TEXT NOT NULL,
      ts INTEGER NOT NULL,
      open REAL NOT NULL,
      high REAL NOT NULL,
      low REAL NOT NULL,
      close REAL NOT NULL,
      volume REAL NOT NULL,
      amount REAL,
      turnover_rate REAL,
      source TEXT NOT NULL,
      fetched_at TEXT NOT NULL,
      PRIMARY KEY (symbol, freq, ts)
    );""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_candles_raw_main ON candles_raw(symbol, freq, ts);")

    # ===== 表2：复权因子 =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS adj_factors (
      symbol TEXT NOT NULL,
      date INTEGER NOT NULL,
      qfq_factor REAL NOT NULL,
      hfq_factor REAL NOT NULL,
      updated_at TEXT,
      PRIMARY KEY (symbol, date)
    );""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_adj_factors_symdate ON adj_factors(symbol, date);")

    # ===== 表3：标的索引（主表）=====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_index (
      symbol TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      market TEXT,
      type TEXT,
      listing_date INTEGER,
      status TEXT DEFAULT 'active',
      updated_at TEXT NOT NULL
    );""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_symbol_index_type_market ON symbol_index(type, market);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_symbol_index_listing ON symbol_index(listing_date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_symbol_index_status ON symbol_index(status);")

    # ===== 表4：标的档案（V3.0: 增加级联外键）=====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_profile (
      symbol TEXT PRIMARY KEY,
      listing_date INTEGER,
      total_shares REAL,
      float_shares REAL,
      industry TEXT,
      region TEXT,
      concepts TEXT,
      updated_at TEXT,
      FOREIGN KEY (symbol) REFERENCES symbol_index (symbol) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
    );""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_profile_industry ON symbol_profile(industry);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_profile_region ON symbol_profile(region);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_profile_listing ON symbol_profile(listing_date);")

    # ===== 表5：用户自选股（V3.0: 增加级联外键）=====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_watchlist (
      symbol TEXT PRIMARY KEY,
      added_at TEXT NOT NULL,
      source TEXT,
      note TEXT,
      tags TEXT,
      sort_order INTEGER DEFAULT 0,
      updated_at TEXT,
      FOREIGN KEY (symbol) REFERENCES symbol_index (symbol) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
    );""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_sort ON user_watchlist(sort_order);")

    # ===== 表6：交易日历 =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trade_calendar (
      date INTEGER PRIMARY KEY,
      market TEXT NOT NULL,
      is_trading_day INTEGER NOT NULL
    );""")

    # ===== 清理废弃表（V1.0遗留）=====
    cur.execute("DROP TABLE IF EXISTS symbol_history;")
    cur.execute("DROP TABLE IF EXISTS symbol_index_summary;")
    cur.execute("DROP TABLE IF EXISTS candles;")
    
    # ===== 清理冗余表（V2.0遗留）=====
    cur.execute("DROP TABLE IF EXISTS sync_tasks;")
    cur.execute("DROP TABLE IF EXISTS task_cursor;")
    cur.execute("DROP TABLE IF EXISTS sync_failures;")

    conn.commit()


def ensure_initialized() -> None:
    """确保数据库已初始化（幂等操作）"""
    init_schema()