# backend/db/__init__.py
# ==============================
# V4.0 - After Hours Bulk v2.1.2 (project edition)
#   - bulk 真相源：bulk_batches + bulk_tasks
#   - 不再导出 bulk_failures/bulk_task_done（你已手动删除表）
# ==============================

from backend.db.connection import get_conn, close_all_connections
from backend.db.schema import init_schema, ensure_initialized

# K线数据操作
from backend.db.candles import (
    upsert_candles_raw,
    select_candles_raw,
    get_latest_ts_from_raw,
)

# 复权因子操作
from backend.db.factors import (
    upsert_factors,
    select_factors,
    get_latest_factor_date,
)

# 标的元数据操作
from backend.db.symbols import (
    upsert_symbol_index,
    select_symbol_index,
    get_listing_date,
    upsert_symbol_profile,
    select_symbol_profile,
)

# 自选池操作
from backend.db.watchlist import (
    insert_watchlist,
    delete_watchlist,
    select_user_watchlist,
    update_watchlist_tags,
    update_watchlist_sort_order,
)

# 交易日历操作
from backend.db.calendar import (
    upsert_trade_calendar,
    is_trading_day,
    get_recent_trading_days,
    select_trading_days_in_range,
)

# bulk v2.1.2
from backend.db.bulk_batches import (
    get_batch_snapshot,
    get_batch_snapshot_for_client,
    get_active_batch_for_client,
    list_queued_batches_for_client,
    get_queue_position,
    start_batch_idempotent,
    list_queued_tasks_for_batch,
    mark_task_running,
    finalize_task_terminal,
    enter_stopping,
    apply_stopping_sweep,
    resume_batch,
    retry_failed_reset,
    tick_pick_next_queued,
    list_failed_tasks,
    recover_incomplete_batches_to_paused,
    gc_delete_terminal_tasks,
)

__all__ = [
    # 连接与Schema
    "get_conn",
    "close_all_connections",
    "init_schema",
    "ensure_initialized",

    # K线
    "upsert_candles_raw",
    "select_candles_raw",
    "get_latest_ts_from_raw",

    # 因子
    "upsert_factors",
    "select_factors",
    "get_latest_factor_date",

    # 标的
    "upsert_symbol_index",
    "select_symbol_index",
    "get_listing_date",
    "upsert_symbol_profile",
    "select_symbol_profile",

    # 自选池
    "insert_watchlist",
    "delete_watchlist",
    "select_user_watchlist",
    "update_watchlist_tags",
    "update_watchlist_sort_order",

    # 日历
    "upsert_trade_calendar",
    "is_trading_day",
    "get_recent_trading_days",
    "select_trading_days_in_range",

    # bulk
    "get_batch_snapshot",
    "get_batch_snapshot_for_client",
    "get_active_batch_for_client",
    "list_queued_batches_for_client",
    "get_queue_position",
    "start_batch_idempotent",
    "list_queued_tasks_for_batch",
    "mark_task_running",
    "finalize_task_terminal",
    "enter_stopping",
    "apply_stopping_sweep",
    "resume_batch",
    "retry_failed_reset",
    "tick_pick_next_queued",
    "list_failed_tasks",
    "recover_incomplete_batches_to_paused",
    "gc_delete_terminal_tasks",
]
