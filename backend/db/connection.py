# backend/db/connection.py
# ==============================
# 说明：数据库连接管理模块（V2.0 - 添加全局写锁）
# 改动：
#   - 新增 _db_write_lock 全局锁
#   - 新增 get_write_lock 函数供外部使用
# ==============================

from __future__ import annotations
import sqlite3
import threading
from typing import Optional

from backend.settings import settings

_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()

# ===== 新增：全局写锁（解决并发冲突）=====
_db_write_lock = threading.Lock()

def get_conn() -> sqlite3.Connection:
    """
    获取全局单例的SQLite数据库连接。
    
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
    
    用途：
      - upsert_symbol_index（标的列表并发写入）
      - 其他需要串行化的数据库写操作
    
    Returns:
        threading.Lock: 全局写锁对象
    """
    return _db_write_lock

def _apply_pragmas(conn: sqlite3.Connection):
    """
    应用SQLite性能优化配置。
    
    配置说明：
    - journal_mode=WAL: 写前日志模式，提升并发性能
    - synchronous=NORMAL: 平衡安全性和性能
    - foreign_keys=ON: 启用外键约束
    - temp_store=MEMORY: 临时数据存内存
    - cache_size=10000: 增大缓存（约40MB）
    """
    cur = conn.cursor()
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