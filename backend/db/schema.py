# backend/db/schema.py
# ==============================
# Schema 初始化
#
# 本轮改动（最终收口）：
#   - symbol_index 删除逐行 updated_at
#   - symbol_profile 删除逐行 updated_at
#   - 批量快照表的同步时间统一由 data_task_status 承担
#
# 本轮改动（watchlist 双主键升级）：
#   - user_watchlist 从旧 symbol 单主键升级为 (symbol, market) 联合主键
#   - watchlist 只允许引用 symbol_index 中真实存在的联合键标的
#   - 彻底废弃 symbol-only 旧语义
#
# 说明：
#   - 只对批量快照表做去冗余收口
#   - 逐行/分批写入表保留各自时间字段
# ==============================

from __future__ import annotations

from backend.db.connection import get_conn

def init_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()

    # ===== 表1：日线原始数据（专用真相源表）=====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS candles_day_raw (
      market TEXT NOT NULL,
      symbol TEXT NOT NULL,
      ts     INTEGER NOT NULL,
      open   REAL NOT NULL,
      high   REAL NOT NULL,
      low    REAL NOT NULL,
      close  REAL NOT NULL,
      volume REAL NOT NULL,
      amount REAL,
      PRIMARY KEY (market, symbol, ts)
    ) WITHOUT ROWID;
    """)

    # ===== 表2：复权因子 =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS adj_factors (
      symbol     TEXT NOT NULL,
      date       INTEGER NOT NULL,
      qfq_factor REAL NOT NULL,
      hfq_factor REAL NOT NULL,
      updated_at TEXT,
      PRIMARY KEY (symbol, date)
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_adj_factors_symdate
      ON adj_factors(symbol, date);
    """)

    # ===== 表3：标的索引（批量快照表，删除逐行 updated_at）=====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_index (
      symbol       TEXT NOT NULL,
      name         TEXT NOT NULL,
      market       TEXT NOT NULL,
      class        TEXT,
      type         TEXT,
      listing_date INTEGER,
      PRIMARY KEY (symbol, market)
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_symbol_index_market_class
      ON symbol_index(market, class);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_symbol_index_market_type
      ON symbol_index(market, type);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_symbol_index_listing
      ON symbol_index(listing_date);
    """)

    # ===== 表4：标的档案（批量快照表，删除逐行 updated_at）=====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_profile (
      symbol       TEXT NOT NULL,
      market       TEXT NOT NULL,
      float_shares REAL,
      float_value  REAL,
      industry     TEXT,
      region       TEXT,
      concepts     TEXT,
      PRIMARY KEY (symbol, market),
      FOREIGN KEY (symbol, market) REFERENCES symbol_index (symbol, market)
        ON DELETE CASCADE
        ON UPDATE CASCADE
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_profile_market_industry
      ON symbol_profile(market, industry);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_profile_market_region
      ON symbol_profile(market, region);
    """)

    # ===== 表5：用户自选股（双主键版，保留逐行 updated_at）=====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_watchlist (
      symbol     TEXT NOT NULL,
      market     TEXT NOT NULL,
      added_at   TEXT NOT NULL,
      source     TEXT,
      note       TEXT,
      tags       TEXT,
      sort_order INTEGER DEFAULT 0,
      updated_at TEXT,
      PRIMARY KEY (symbol, market),
      FOREIGN KEY (symbol, market) REFERENCES symbol_index (symbol, market)
        ON DELETE CASCADE
        ON UPDATE CASCADE
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_watchlist_sort
      ON user_watchlist(sort_order, added_at);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_watchlist_market_sort
      ON user_watchlist(market, sort_order, added_at);
    """)

    # ===== 表6：交易日历 =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trade_calendar (
      date           INTEGER PRIMARY KEY,
      market         TEXT NOT NULL,
      is_trading_day INTEGER NOT NULL
    );
    """)

    # ===== 表7：gbbq 原始事件真相源 =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS gbbq_events_raw (
      market   TEXT NOT NULL,
      symbol   TEXT NOT NULL,
      date     INTEGER NOT NULL,
      category INTEGER NOT NULL,
      field1   REAL,
      field2   REAL,
      field3   REAL,
      field4   REAL,
      PRIMARY KEY (market, symbol, date, category)
    ) WITHOUT ROWID;
    """)

    # ==========================================================
    # 表8：盘后数据导入批次（保留 started/finished 语义字段）
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS local_import_batches (
      batch_id            TEXT PRIMARY KEY,
      state               TEXT NOT NULL,
      created_at          TEXT NOT NULL,
      started_at          TEXT,
      finished_at         TEXT,
      retryable           INTEGER NOT NULL DEFAULT 0,
      cancelable          INTEGER NOT NULL DEFAULT 0,
      ui_message          TEXT,
      selection_signature TEXT
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_local_import_batches_state_created
      ON local_import_batches(state, created_at);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_local_import_batches_signature_state
      ON local_import_batches(selection_signature, state, created_at);
    """)

    # ==========================================================
    # 表9：盘后数据导入任务（保留 started/finished 语义字段）
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS local_import_tasks (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      batch_id         TEXT NOT NULL,
      market           TEXT NOT NULL,
      symbol           TEXT NOT NULL,
      freq             TEXT NOT NULL,
      state            TEXT NOT NULL,
      attempts         INTEGER NOT NULL DEFAULT 0,
      signal_code      TEXT,
      signal_message   TEXT,
      appended_rows    INTEGER,
      source_file_path TEXT,
      started_at       TEXT,
      finished_at      TEXT,
      UNIQUE(batch_id, market, symbol, freq),
      FOREIGN KEY (batch_id) REFERENCES local_import_batches (batch_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_local_import_tasks_batch_state
      ON local_import_tasks(batch_id, state, id);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_local_import_tasks_batch_symbol
      ON local_import_tasks(batch_id, market, symbol, freq);
    """)

    # ==========================================================
    # 表10：批量任务稳定状态真相源（保留 updated_at）
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS data_task_status (
      task_type          TEXT PRIMARY KEY,
      task_status        TEXT NOT NULL,
      idle_reason        TEXT,
      last_success_at    TEXT,
      last_failure_at    TEXT,
      last_error_message TEXT,
      updated_at         TEXT NOT NULL
    );
    """)

    conn.commit()

def ensure_initialized() -> None:
    init_schema()