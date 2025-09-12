# backend/services/watchlist.py
# ==============================
# 说明：自选池服务（简化版）
# 本版职责：
# - 维护自选池（读写 config.json 的 watchlist 字段）
# - 后台“同步”仅确保 1d 近端最新（ensure_daily_recent），不做分钟/粗分钟拉取
# - 提供运行状态快照（每个 symbol 最近一次同步结果）
# ==============================

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.settings import settings
from backend.services.config import get_config, set_config
from backend.services.storage import ensure_daily_recent

_executor_lock = threading.Lock()
_executor: Optional[ThreadPoolExecutor] = None

_status_lock = threading.Lock()
_status: Dict[str, Dict[str, Any]] = {}
_tasks: Dict[str, Future] = {}

def _ensure_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None or _executor._shutdown:
            _executor = ThreadPoolExecutor(max_workers=max(1, settings.fetch_concurrency), thread_name_prefix="watchlist")
    return _executor

def _set_status(symbol: str, **patch: Any) -> None:
    with _status_lock:
        s = _status.get(symbol, {})
        s.update(patch)
        _status[symbol] = s

def get_status_snapshot() -> Dict[str, Dict[str, Any]]:
    with _status_lock:
        return {k: dict(v) for k, v in _status.items()}

def get_watchlist() -> List[str]:
    cfg = get_config()
    arr = [str(x).strip() for x in (cfg.get("watchlist") or []) if str(x).strip()]
    seen, out = set(), []
    for s in arr:
        if s not in seen:
            seen.add(s); out.append(s)
    out.sort()
    return out

def add_to_watchlist(symbol: str) -> List[str]:
    lst = get_watchlist()
    if symbol not in lst:
        lst.append(symbol); lst.sort()
        set_config({"watchlist": lst})
    return lst

def remove_from_watchlist(symbol: str) -> List[str]:
    lst = [s for s in get_watchlist() if s != symbol]
    set_config({"watchlist": lst})
    return lst

def _sync_symbol_job(symbol: str) -> Dict[str, Any]:
    _set_status(symbol, running=True, started_at=datetime.now().isoformat(), error=None, last_result=None)
    try:
        res = ensure_daily_recent(symbol)
        _set_status(symbol, running=False, finished_at=datetime.now().isoformat(), last_result=res, error=None)
        return res
    except Exception as e:
        _set_status(symbol, running=False, finished_at=datetime.now().isoformat(), error=str(e))
        return {"ok": False, "error": str(e)}

def sync_symbol_async(symbol: str) -> bool:
    ex = _ensure_executor()
    with _status_lock:
        fut = _tasks.get(symbol)
        if fut and not fut.done():
            return False
        fut = ex.submit(_sync_symbol_job, symbol)
        _tasks[symbol] = fut
        return True

def sync_all_async() -> Dict[str, Any]:
    watch = get_watchlist()
    submitted = skipped = 0
    for sym in watch:
        ok = sync_symbol_async(sym)
        if ok: submitted += 1
        else: skipped += 1
    return {"submitted": submitted, "skipped": skipped, "total": len(watch)}
