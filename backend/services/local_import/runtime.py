# backend/services/local_import/runtime.py
# ==============================
# 盘后数据导入 import - 运行时状态与串行锁
#
# 最优模型（本轮刷新/读取拆分版）：
#   - 候选结果正式真相源：本地持久化快照文件
#   - runtime 不再持有独立的扫描快照真相源
#   - runtime 只负责：
#       1) 从本地持久化真相源读取当前候选结果
#       2) 提供执行期 file_path 查询
#       3) 提供 orchestrator 串行锁
#
# 设计原则：
#   - refresh 负责扫描并覆盖本地持久化真相源
#   - get 只读取当前本地持久化真相源
#   - start / retry / pipeline 只消费当前本地持久化真相源
#   - 目录变更后，旧真相源立即失效并删除
# ==============================

from __future__ import annotations

import asyncio
from threading import RLock
from typing import Dict, Any, Optional, Tuple, List

from backend.services.local_import.snapshot_store import (
    load_scan_snapshot,
    has_scan_snapshot,
)
from backend.utils.logger import get_logger

_LOG = get_logger("local_import.runtime")


class LocalImportRuntime:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._io_lock = RLock()

    # ==========================================================
    # 串行调度锁
    # ==========================================================
    async def lock(self) -> None:
        await self._lock.acquire()

    def unlock(self) -> None:
        if self._lock.locked():
            self._lock.release()

    def is_locked(self) -> bool:
        return self._lock.locked()

    # ==========================================================
    # 候选结果真相源读取
    # ==========================================================
    def has_persisted_snapshot(self) -> bool:
        with self._io_lock:
            return has_scan_snapshot()

    def get_persisted_snapshot(self) -> Optional[Dict[str, Any]]:
        with self._io_lock:
            return load_scan_snapshot()

    def require_persisted_snapshot(self) -> Dict[str, Any]:
        with self._io_lock:
            snapshot = load_scan_snapshot()
            if not snapshot:
                raise RuntimeError("persisted scan snapshot is missing; please refresh candidates first")
            return snapshot

    def get_scan_items(self) -> List[Dict[str, Any]]:
        with self._io_lock:
            snapshot = load_scan_snapshot() or {}
            return list(snapshot.get("items") or [])

    def get_file_path(self, market: str, symbol: str, freq: str) -> Optional[str]:
        m = str(market or "").strip().upper()
        s = str(symbol or "").strip()
        f = str(freq or "").strip()
        if not m or not s or not f:
            return None

        with self._io_lock:
            snapshot = load_scan_snapshot() or {}
            items = snapshot.get("items") or []

            for item in items:
                if not isinstance(item, dict):
                    continue
                if (
                    str(item.get("market") or "").strip().upper() == m and
                    str(item.get("symbol") or "").strip() == s and
                    str(item.get("freq") or "").strip() == f
                ):
                    return str(item.get("file_path") or "").strip() or None

            return None

    def get_snapshot_generated_at(self) -> Optional[str]:
        with self._io_lock:
            snapshot = load_scan_snapshot() or {}
            return snapshot.get("generated_at")

    def get_snapshot_root_dir(self) -> Optional[str]:
        with self._io_lock:
            snapshot = load_scan_snapshot() or {}
            root_dir = str(snapshot.get("root_dir") or "").strip()
            return root_dir or None


_RUNTIME: Optional[LocalImportRuntime] = None


def get_local_import_runtime() -> LocalImportRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = LocalImportRuntime()
    return _RUNTIME
