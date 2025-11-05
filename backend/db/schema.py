# backend/db/schema.py
# ==============================
# 说明：数据库Schema管理模块（V2.0版）
# - 职责：定义和初始化所有表的结构
# ==============================

from __future__ import annotations

from backend.db.connection import get_conn

def init_schema() -> None:
    """
    初始化数据库所有表的Schema和索引（V2.0版）。
    
    包含表：
    1. candles_raw - K线原始数据
    2. adj_factors - 复权因子
    3. symbol_index - 标的基础索引
    4. symbol_profile - 标的详细档案
    5. user_watchlist - 用户自选池
    6. sync_tasks - 同步任务定义
    7. task_cursor - 任务执行游标
    8. sync_failures - 同步失败记录
    9. trade_calendar - 交易日历
    """
    conn = get_conn()
    cur = conn.cursor()

    # 表1：K线原始数据
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

    # 表2：复权因子
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

    # 表3：标的基础索引（V2.0: 新增 listing_date, status）
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

    # 表4：标的详细档案（V2.0: 移除 intro 字段）
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
    );""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_profile_industry ON symbol_profile(industry);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_profile_region ON symbol_profile(region);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_profile_listing ON symbol_profile(listing_date);")

    # 表5：用户自选池（V2.0: 新增 tags, sort_order）
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
    );""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_sort ON user_watchlist(sort_order);")

    # 表6：同步任务定义
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sync_tasks (
      task_id TEXT PRIMARY KEY,
      symbol TEXT NOT NULL,
      freq TEXT NOT NULL,
      priority INTEGER NOT NULL,
      created_at TEXT NOT NULL
    );""")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sync_tasks_uniq ON sync_tasks(symbol, freq);")

    # 表7：任务执行游标
    cur.execute("""
    CREATE TABLE IF NOT EXISTS task_cursor (
      cursor_id INTEGER PRIMARY KEY AUTOINCREMENT,
      task_id TEXT NOT NULL UNIQUE,
      FOREIGN KEY (task_id) REFERENCES sync_tasks (task_id) ON DELETE CASCADE
    );""")

    # 表8：同步失败记录
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sync_failures (
      failure_id INTEGER PRIMARY KEY AUTOINCREMENT,
      task_id TEXT NOT NULL,
      symbol TEXT NOT NULL,
      freq TEXT NOT NULL,
      priority INTEGER,
      error_message TEXT,
      failed_at TEXT NOT NULL
    );""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_failures_time ON sync_failures(failed_at);")

    # 表9：交易日历
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trade_calendar (
      date INTEGER PRIMARY KEY,
      market TEXT NOT NULL,
      is_trading_day INTEGER NOT NULL
    );""")

    # 清理废弃表
    cur.execute("DROP TABLE IF EXISTS symbol_history;")
    cur.execute("DROP TABLE IF EXISTS symbol_index_summary;")
    cur.execute("DROP TABLE IF EXISTS candles;")

    conn.commit()


def ensure_initialized() -> None:
    """确保数据库已初始化（幂等操作）。"""
    init_schema()
