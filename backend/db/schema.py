# backend/db/schema.py
# ==============================
# Schema 初始化
#
# 本轮改动（盘后数据导入 import 第一阶段）：
#   - 删除旧 bulk 表定义（由你手动删旧表，本文件不再创建旧表）
#   - 新建：
#       * local_import_batches
#       * local_import_tasks
#
# 本次重构：
#   - candles_raw 已按 market+symbol+freq+ts 联合键重构
#   - local_import_batches 新增 selection_signature
#   - local_import_tasks 的语义改为：
#       * 只承载当前/最近有效 running(or recovered paused) 批次的任务
#       * queued 批次不提前展开为 tasks
#
# 说明：
#   - 本文件只负责“新建当前正式表结构”
#   - 不承担旧表删除 / 字段迁移逻辑
# ==============================

from __future__ import annotations

from backend.db.connection import get_conn


def init_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()

    # ===== 表1：K线原始数据（联合键修正版）=====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS candles_raw (
      market TEXT NOT NULL,
      symbol TEXT NOT NULL,
      freq   TEXT NOT NULL,
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
      PRIMARY KEY (market, symbol, freq, ts)
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_candles_raw_main
      ON candles_raw(market, symbol, freq, ts);
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

    # ===== 表3：标的索引 =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_index (
      symbol       TEXT NOT NULL,
      name         TEXT NOT NULL,
      market       TEXT NOT NULL,
      class        TEXT,
      type         TEXT,
      listing_date INTEGER,
      updated_at   TEXT NOT NULL,
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

    # ===== 表4：标的档案（联合主键极简版）=====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_profile (
      symbol       TEXT NOT NULL,
      market       TEXT NOT NULL,
      float_shares REAL,
      float_value  REAL,
      industry     TEXT,
      region       TEXT,
      concepts     TEXT,
      updated_at   TEXT,
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

    # ==========================================================
    # 表7：盘后数据导入批次（local_import_batches）
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS local_import_batches (
      batch_id             TEXT PRIMARY KEY,
      state                TEXT NOT NULL,
      created_at           TEXT NOT NULL,
      started_at           TEXT,
      finished_at          TEXT,
      progress_total       INTEGER NOT NULL DEFAULT 0,
      progress_done        INTEGER NOT NULL DEFAULT 0,
      progress_success     INTEGER NOT NULL DEFAULT 0,
      progress_failed      INTEGER NOT NULL DEFAULT 0,
      progress_cancelled   INTEGER NOT NULL DEFAULT 0,
      retryable            INTEGER NOT NULL DEFAULT 0,
      cancelable           INTEGER NOT NULL DEFAULT 0,
      ui_message           TEXT,
      selection_signature  TEXT
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
    # 表8：盘后数据导入任务（local_import_tasks）
    # ==========================================================
    # 设计语义：
    #   - 只为“当前/最近有效 running(or recovered paused)”批次展开任务
    #   - queued 批次不提前写入 tasks
    cur.execute("""
    CREATE TABLE IF NOT EXISTS local_import_tasks (
      id             INTEGER PRIMARY KEY AUTOINCREMENT,
      batch_id       TEXT NOT NULL,
      market         TEXT NOT NULL,
      symbol         TEXT NOT NULL,
      freq           TEXT NOT NULL,
      state          TEXT NOT NULL,
      attempts       INTEGER NOT NULL DEFAULT 0,
      error_code     TEXT,
      error_message  TEXT,
      updated_at     TEXT NOT NULL,
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

    conn.commit()


def ensure_initialized() -> None:
    init_schema()
