# backend/db/schema.py
# ==============================
# V5.1 - After Hours Bulk + skipped 支持（真相源扩展）
#
# 说明：
#   - 增加 bulk_batches.progress_skipped
#   - bulk_tasks.status 逻辑上允许 'skipped'（SQLite不做枚举约束）
# ==============================

from __future__ import annotations

from backend.db.connection import get_conn


def init_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()

    # ===== 表1：K线原始数据（带 adjust 维度）=====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS candles_raw (
      symbol TEXT NOT NULL,
      freq   TEXT NOT NULL,
      adjust TEXT NOT NULL DEFAULT 'none',
      ts     INTEGER NOT NULL,
      open   REAL NOT NULL,
      high   REAL NOT NULL,
      low    REAL NOT NULL,
      close  REAL NOT NULL,
      volume REAL NOT NULL,
      amount REAL,
      turnover_rate REAL,
      source TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY (symbol, freq, ts, adjust)
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_candles_raw_main
      ON candles_raw(symbol, freq, ts, adjust);
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

    # ===== 表3：标的索引（主表）=====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_index (
      symbol       TEXT PRIMARY KEY,
      name         TEXT NOT NULL,
      market       TEXT,
      class        TEXT,
      type         TEXT,
      board        TEXT,
      listing_date INTEGER,
      updated_at   TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_symbol_index_type_market
      ON symbol_index(type, market);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_symbol_index_listing
      ON symbol_index(listing_date);
    """)

    # ===== 表4：标的档案 =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_profile (
      symbol       TEXT PRIMARY KEY,
      total_shares REAL,
      float_shares REAL,
      total_value  REAL,
      nego_value   REAL,
      pe_static    REAL,
      industry     TEXT,
      region       TEXT,
      concepts     TEXT,
      updated_at   TEXT,
      FOREIGN KEY (symbol) REFERENCES symbol_index (symbol)
        ON DELETE CASCADE
        ON UPDATE CASCADE
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_profile_industry
      ON symbol_profile(industry);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_profile_region
      ON symbol_profile(region);
    """)

    # ===== 表5：用户自选股 =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_watchlist (
      symbol     TEXT PRIMARY KEY,
      added_at   TEXT NOT NULL,
      source     TEXT,
      note       TEXT,
      tags       TEXT,
      sort_order INTEGER DEFAULT 0,
      updated_at TEXT,
      FOREIGN KEY (symbol) REFERENCES symbol_index (symbol)
        ON DELETE CASCADE
        ON UPDATE CASCADE
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_watchlist_sort
      ON user_watchlist(sort_order);
    """)

    # ===== 表6：交易日历 =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trade_calendar (
      date          INTEGER PRIMARY KEY,
      market        TEXT NOT NULL,
      is_trading_day INTEGER NOT NULL
    );
    """)

    # ======================================================================
    # 表7：bulk_batches（盘后批次真相源 v2.1.2）
    # ======================================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bulk_batches (
      batch_id           TEXT PRIMARY KEY,
      client_instance_id TEXT NOT NULL,
      purpose            TEXT NOT NULL,

      started_at         TEXT,
      server_received_at TEXT NOT NULL,

      -- FIFO 排队真相源
      queue_ts           TEXT NOT NULL,

      -- 展示字段（不参与逻辑）
      selected_symbols   INTEGER,
      planned_total_tasks INTEGER,

      accepted_tasks     INTEGER NOT NULL DEFAULT 0,
      rejected_tasks     INTEGER NOT NULL DEFAULT 0,

      -- queued|running|paused|stopping|failed|success|cancelled
      state              TEXT NOT NULL,

      progress_version   INTEGER NOT NULL DEFAULT 1,
      progress_updated_at TEXT NOT NULL,

      progress_done      INTEGER NOT NULL DEFAULT 0,
      progress_success   INTEGER NOT NULL DEFAULT 0,
      progress_failed    INTEGER NOT NULL DEFAULT 0,
      progress_cancelled INTEGER NOT NULL DEFAULT 0,
      progress_skipped   INTEGER NOT NULL DEFAULT 0,
      progress_total     INTEGER NOT NULL DEFAULT 0
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_bulk_batches_client_state_queue
      ON bulk_batches(client_instance_id, purpose, state, queue_ts);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_bulk_batches_client_latest
      ON bulk_batches(client_instance_id, purpose, server_received_at);
    """)

    # ======================================================================
    # 表8：bulk_tasks（批次任务清单真相源 v2.1.2）
    # ======================================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bulk_tasks (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,

      batch_id         TEXT NOT NULL,
      client_task_key  TEXT NOT NULL,

      type             TEXT NOT NULL,
      scope            TEXT NOT NULL,
      symbol           TEXT,
      freq             TEXT,
      adjust           TEXT,

      params_json      TEXT NOT NULL,

      -- queued|running|success|failed|cancelled
      status           TEXT NOT NULL,

      attempts         INTEGER NOT NULL DEFAULT 0,

      last_error_code    TEXT,
      last_error_message TEXT,

      last_task_id      TEXT,

      updated_at       TEXT NOT NULL,

      UNIQUE(batch_id, client_task_key),
      FOREIGN KEY (batch_id) REFERENCES bulk_batches (batch_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_bulk_tasks_batch_status
      ON bulk_tasks(batch_id, status, id);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_bulk_tasks_batch_key
      ON bulk_tasks(batch_id, client_task_key);
    """)

    conn.commit()


def ensure_initialized() -> None:
    init_schema()
