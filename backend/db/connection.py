# backend/db/connection.py
# ==============================
# 说明：数据库连接管理模块（V3.0 - 日线专用库优化版）
#
# 改动：
#   - 继续保留全局写锁
#   - SQLite PRAGMA 按“新库重建”策略优化
#   - 目标服务于新的日线专用表结构：
#       * candles_day_raw
# ==============================

from __future__ import annotations
import sqlite3
import threading
from typing import Optional

from backend.settings import settings

_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()

# 全局写锁
_db_write_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    """
    获取全局单例的 SQLite 数据库连接。

    特性：
    - 线程安全的单例模式
    - 自动应用性能优化配置（PRAGMA）

    Returns:
        sqlite3.Connection: 数据库连接对象
    """
    global _conn
    with _lock:
        if _conn is None:
            settings.db_path.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(
                str(settings.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            _conn.row_factory = sqlite3.Row
            _apply_pragmas(_conn)
        return _conn


def get_write_lock() -> threading.Lock:
    """
    获取全局写锁（用于需要原子性的写操作）

    Returns:
        threading.Lock: 全局写锁对象
    """
    return _db_write_lock


def _apply_pragmas(conn: sqlite3.Connection):
    """
    应用 SQLite 性能与存储优化配置。

    配置说明（小白版）：
    - journal_mode=WAL:
        写日志模式，读写更稳，更适合服务进程
    - synchronous=NORMAL:
        安全性和性能折中
    - foreign_keys=ON:
        启用外键约束
    - temp_store=MEMORY:
        临时数据尽量走内存
    - cache_size=10000:
        增大缓存（约40MB）
    - auto_vacuum=INCREMENTAL:
        允许后续更可控地回收已删除数据占用的空间
    """
    cur = conn.cursor()

    # 先设置持久化/结构类参数
    # 说明：
    #   - page_size 最适合在新库创建前设定；
    #   - 你本次明确会删除旧库重建，因此这里直接按新机制固化即可。
    cur.execute("PRAGMA page_size=8192;")
    cur.execute("PRAGMA auto_vacuum=INCREMENTAL;")

    # 再设置运行期参数
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.execute("PRAGMA temp_store=MEMORY;")
    cur.execute("PRAGMA cache_size=10000;")

    cur.close()


def close_all_connections():
    """关闭所有数据库连接（用于应用关闭时的清理）。"""
    global _conn
    with _lock:
        if _conn:
            _conn.close()
            _conn = None
