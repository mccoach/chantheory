# backend/db/tasks.py
# ==============================
# 说明：同步任务管理表操作模块
# - 职责：sync_tasks, task_cursor, sync_failures 三张表的操作
# ==============================

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.db.connection import get_conn

# ==============================================================================
# sync_tasks 表操作
# ==============================================================================

def bulk_insert_sync_tasks(tasks: List[Dict[str, Any]]) -> int:
    """
    批量插入同步任务。
    
    Args:
        tasks: 字典列表，每个字典包含：
              task_id, symbol, freq, priority
    
    Returns:
        int: 插入的行数
    """
    if not tasks:
        return 0
    
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    
    for task in tasks:
        task['created_at'] = task.get('created_at', now)
    
    sql = """
    INSERT OR REPLACE INTO sync_tasks (task_id, symbol, freq, priority, created_at)
    VALUES (:task_id, :symbol, :freq, :priority, :created_at);
    """
    
    cur.executemany(sql, tasks)
    conn.commit()
    return cur.rowcount


def clear_all_tasks() -> None:
    """清空所有任务表（用于重新生成任务）。"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM task_cursor;")
    cur.execute("DELETE FROM sync_tasks;")
    conn.commit()


def get_total_task_count() -> int:
    """获取任务总数。"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sync_tasks;")
    result = cur.fetchone()
    return result[0] if result else 0


# ==============================================================================
# task_cursor 表操作
# ==============================================================================

def populate_task_cursor() -> int:
    """
    根据 sync_tasks 表的内容，生成有序的执行游标。
    
    排序规则：
    1. 优先级升序（数值越小越优先）
    2. 标的代码升序
    
    Returns:
        int: 生成的游标总数
    """
    conn = get_conn()
    cur = conn.cursor()
    
    # 清空旧游标
    cur.execute("DELETE FROM task_cursor;")
    
    # 按优先级和标的代码排序，插入游标
    cur.execute("""
    INSERT INTO task_cursor (task_id)
    SELECT task_id FROM sync_tasks
    ORDER BY priority ASC, symbol ASC;
    """)
    
    conn.commit()
    return cur.rowcount


def get_task_by_cursor(cursor_id: int) -> Optional[Dict[str, Any]]:
    """
    根据游标ID获取对应的任务详情。
    
    Args:
        cursor_id: 游标ID（从1开始的整数）
    
    Returns:
        Optional[Dict]: 任务字典，不存在则返回 None
    """
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
    SELECT t.* FROM sync_tasks t
    JOIN task_cursor c ON t.task_id = c.task_id
    WHERE c.cursor_id = ?;
    """, (cursor_id,))
    
    row = cur.fetchone()
    return dict(row) if row else None


# ==============================================================================
# sync_failures 表操作
# ==============================================================================

def record_sync_failure(task: Dict[str, Any], error_message: str) -> None:
    """
    记录同步失败事件。
    
    Args:
        task: 任务字典
        error_message: 错误信息
    """
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    
    cur.execute("""
    INSERT INTO sync_failures (task_id, symbol, freq, priority, error_message, failed_at)
    VALUES (?, ?, ?, ?, ?, ?);
    """, (
        task['task_id'],
        task['symbol'],
        task['freq'],
        task.get('priority', 100),
        error_message,
        now
    ))
    
    conn.commit()


def get_recent_failures(limit: int = 100) -> List[Dict[str, Any]]:
    """
    获取最近的失败记录。
    
    Returns:
        List[Dict]: 失败记录列表，按时间倒序
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"SELECT * FROM sync_failures ORDER BY failed_at DESC LIMIT ?;",
        (limit,)
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows]
