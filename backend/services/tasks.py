# backend/services/tasks.py
# ==============================
# 说明：后台任务（简化版）
# - watchlist_bootstrap：可选，启动后对自选池仅做 ensure_daily_recent（不做分钟拉取）
# - cache_cleanup_daemon：周期性执行缓存 LRU/TTL 清理
# ==============================

from __future__ import annotations
import threading
from datetime import datetime
from typing import Dict, Any
import time

from backend.settings import settings
from backend.services.storage import ensure_daily_recent, cleanup_cache
from backend.services.watchlist import get_watchlist  # 仅取自选池列表

_TASKS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
_BG_THREAD: threading.Thread | None = None
_CLEANUP_THREAD: threading.Thread | None = None
_STOP_EVENT = threading.Event()  # 后台守护线程停止信号

def _set_task(name: str, **patch: Any) -> None:
    with _LOCK:
        st = _TASKS.get(name, {})
        st.update(patch); _TASKS[name] = st

def get_task_status() -> Dict[str, Dict[str, Any]]:
    with _LOCK:
        return {k: dict(v) for k, v in _TASKS.items()}

def _task_watchlist_bootstrap() -> None:
    name = "watchlist_bootstrap"
    _set_task(name, running=True, started_at=datetime.now().isoformat(), finished_at=None, error=None)
    try:
        if settings.autostart_watchlist_sync:
            # 仅保证 1d 近端最新（不做分钟）
            lst = get_watchlist()
            for sym in lst:
                try: ensure_daily_recent(sym)
                except Exception as e: pass
        _set_task(name, running=False, finished_at=datetime.now().isoformat(), error=None)
    except Exception as e:
        _set_task(name, running=False, finished_at=datetime.now().isoformat(), error=str(e))

def _task_cache_cleanup_daemon() -> None:
    name = "cache_cleanup"
    _set_task(name, running=True, started_at=datetime.now().isoformat(), last_run=None, error=None)
    try:
        interval = max(1, int(settings.cache_cleanup_interval_min))
        while not _STOP_EVENT.is_set():  # NEW
            try:
                res = cleanup_cache()
                _set_task(name, last_run=datetime.now().isoformat(), last_result=res)
            except Exception as e:
                _set_task(name, error=str(e))
            _STOP_EVENT.wait(interval * 60)  # NEW: 可中断等待
    except Exception as e:
        _set_task(name, running=False, finished_at=datetime.now().isoformat(), error=str(e))

def start_background_tasks() -> None:
    global _BG_THREAD, _CLEANUP_THREAD
    _STOP_EVENT.clear()  # NEW
    if _BG_THREAD is None or not _BG_THREAD.is_alive():
        t = threading.Thread(target=_task_watchlist_bootstrap, name="init-tasks", daemon=True)
        t.start(); _BG_THREAD = t
    if _CLEANUP_THREAD is None or not _CLEANUP_THREAD.is_alive():
        c = threading.Thread(target=_task_cache_cleanup_daemon, name="cache-cleanup", daemon=True)
        c.start(); _CLEANUP_THREAD = c

def stop_background_tasks() -> None:  # NEW: 可用于测试/热重载场景
    _STOP_EVENT.set()
