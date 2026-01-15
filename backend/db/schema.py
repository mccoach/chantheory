# backend/db/schema.py
# ==============================
# V4.0 - 精简版（candles_raw 带 adjust 维度 · 无迁移逻辑）
#
# 说明：
#   - 假定数据库从零初始化，不考虑任何历史表结构和数据迁移。
#   - 仅定义当前业务所需的 6 张核心表：
#       1. candles_raw   - K线原始数据（带 adjust）
#       2. adj_factors   - 复权因子
#       3. symbol_index  - 标的索引（主表）
#       4. symbol_profile- 标的档案（外键 → symbol_index）
#       5. user_watchlist- 用户自选股（外键 → symbol_index）
#       6. trade_calendar- 交易日历
#
#   - 其中 candles_raw 的设计为最终版：
#       * 字段：
#           symbol, freq, ts, open, high, low, close,
#           volume, amount, turnover_rate,
#           source, fetched_at,
#           adjust ('none' | 'qfq' | 'hfq')
#       * 主键：
#           (symbol, freq, ts, adjust)
#
# V4.1 - After Hours Bulk v1.1 (新增批次真相源表)
#   - 新增两张表（不影响原6张表的既有职责）：
#       7. bulk_batches  - 盘后批量批次快照（进度真相源）
#       8. bulk_failures - 批次失败明细（分页查询）
#   - 注意：本项目假定“从零初始化”，无迁移逻辑。
#
# V4.2 - After Hours Bulk v1.1 (新增 task_done 去重表)
#   - 新增：
#       9. bulk_task_done - 批次内 task_done 去重表（防止重复统计导致 done>total）
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

    V4.1 追加：
    7. bulk_batches  - 盘后批量批次快照
    8. bulk_failures - 批次失败明细

    V4.2 追加：
    9. bulk_task_done - task_done 去重表
    """
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

    # ===== 表5：用户自选股（V3.0: 增加级联外键）=====
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
    # 表7：盘后批量批次快照（After Hours Bulk v1.1 真相源）
    # ======================================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bulk_batches (
      batch_id           TEXT PRIMARY KEY,
      client_instance_id TEXT,
      purpose            TEXT NOT NULL,

      started_at         TEXT,
      server_received_at TEXT NOT NULL,

      selected_symbols   INTEGER,
      planned_total_tasks INTEGER,

      accepted_tasks     INTEGER NOT NULL DEFAULT 0,
      rejected_tasks     INTEGER NOT NULL DEFAULT 0,

      state              TEXT NOT NULL,  -- 'running' | 'finished'

      progress_version   INTEGER NOT NULL DEFAULT 1,
      progress_updated_at TEXT NOT NULL,

      progress_done      INTEGER NOT NULL DEFAULT 0,
      progress_success   INTEGER NOT NULL DEFAULT 0,
      progress_failed    INTEGER NOT NULL DEFAULT 0,
      progress_total     INTEGER NOT NULL DEFAULT 0
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_bulk_batches_latest
      ON bulk_batches(purpose, state, server_received_at);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_bulk_batches_client
      ON bulk_batches(client_instance_id, purpose, state, server_received_at);
    """)

    # ======================================================================
    # 表8：批次失败明细（After Hours Bulk v1.1）
    # ======================================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bulk_failures (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      batch_id      TEXT NOT NULL,

      task_id       TEXT NOT NULL,
      task_type     TEXT,
      symbol        TEXT,
      freq          TEXT,
      adjust        TEXT,

      overall_status TEXT NOT NULL,  -- 'failed' | 'partial_fail'

      error_code    TEXT,
      error_message TEXT,

      timestamp     TEXT NOT NULL,

      UNIQUE(batch_id, task_id)
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_bulk_failures_batch
      ON bulk_failures(batch_id, id);
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_bulk_failures_batch_task
      ON bulk_failures(batch_id, task_id);
    """)

    # ======================================================================
    # 表9：批次内 task_done 去重表（After Hours Bulk v1.1）
    # 说明：
    #   - 用于保证同一 (batch_id, task_id) 只统计一次，防止重复统计导致 done>total；
    #   - 去重逻辑在业务层实现：插入成功→可计数；冲突→忽略计数。
    # ======================================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bulk_task_done (
      batch_id  TEXT NOT NULL,
      task_id   TEXT NOT NULL,
      counted_at TEXT NOT NULL,
      PRIMARY KEY (batch_id, task_id)
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_bulk_task_done_batch
      ON bulk_task_done(batch_id, counted_at);
    """)

    conn.commit()


def ensure_initialized() -> None:
    """确保数据库已初始化（幂等操作）"""
    init_schema()
