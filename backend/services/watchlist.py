# backend/services/watchlist.py
# ==============================
# 说明：自选池服务（改造版）
# 本版职责：
# - 维护自选池（写入 SQLite 的 user_watchlist 表作为权威；同步更新 config.json.watchlist 兼容历史）
# - 首次调用或启动阶段若 DB 为空且 config.json 有数据，自动迁移到 DB（幂等）
# - 后台“同步”仍仅确保 1d 近端最新（ensure_daily_recent），不做分钟/粗分钟拉取
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
from backend.db.sqlite import (
    select_user_watchlist,
    upsert_user_watchlist,
    delete_user_watchlist,
)

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

# --- 迁移：若 DB 为空但 config.json 存在 watchlist，则迁移入库（幂等） ---
def _migrate_config_watchlist_to_db_if_needed() -> None:
    try:
        db_items = select_user_watchlist()
        if db_items and len(db_items) > 0:
            return
        cfg = get_config()
        arr = [str(x).strip() for x in (cfg.get("watchlist") or []) if str(x).strip()]
        if not arr:
            return
        now_iso = datetime.now().isoformat()
        rows = [(sym, now_iso, "config", None, now_iso) for sym in arr]
        upsert_user_watchlist(rows)
    except Exception:
        # 容错：迁移失败不阻断服务
        pass

def get_watchlist() -> List[str]:
    # 首次使用时尝试迁移
    _migrate_config_watchlist_to_db_if_needed()
    # 从 DB 读取
    items = [str(r.get("symbol", "")).strip() for r in select_user_watchlist() if str(r.get("symbol", "")).strip()]
    items.sort()
    return items

def _sync_config_watchlist(db_list: List[str]) -> None:
    # 同步 config.json.watchlist（保持兼容但不作为权威来源）
    try:
        set_config({"watchlist": list(db_list)})
    except Exception:
        pass

def add_to_watchlist(symbol: str) -> List[str]:
    sym = str(symbol or "").strip()
    if not sym:
        return get_watchlist()
    now_iso = datetime.now().isoformat()
    upsert_user_watchlist([(sym, now_iso, "user", None, now_iso)])
    lst = get_watchlist()
    _sync_config_watchlist(lst)
    return lst

def remove_from_watchlist(symbol: str) -> List[str]:
    sym = str(symbol or "").strip()
    if not sym:
        return get_watchlist()
    try:
        delete_user_watchlist(sym)
    except Exception:
        pass
    lst = get_watchlist()
    _sync_config_watchlist(lst)
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
