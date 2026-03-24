# backend/services/local_import/runtime.py
# ==============================
# 盘后数据导入 import - 运行时缓存与串行锁
#
# 最优模型：
#   - 扫描快照由 scan 层统一生成
#   - runtime 只负责：
#       1) 持有扫描快照缓存
#       2) 提供 TTL 复用能力
#       3) 提供执行期 file_path 查询
#       4) 提供 orchestrator 串行锁
#
# 设计原则：
#   - candidates / orchestrator 都只消费 snapshot
#   - 不允许各层私自重复递归扫描目录
# ==============================

from __future__ import annotations

import asyncio
import threading
import time
from typing import Dict, Any, Optional, Tuple, List

from backend.services.local_import.scan import (
    build_scan_snapshot,
    LocalImportFileItem,
)
from backend.utils.logger import get_logger

_LOG = get_logger("local_import.runtime")


class LocalImportRuntime:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._scan_lock = threading.RLock()

        self._scan_snapshot: Optional[Dict[str, Any]] = None
        self._scan_snapshot_monotonic: float = 0.0

        # 短 TTL：用于“打开弹窗后马上点击开始/重试”的高频复用场景
        self._scan_snapshot_ttl_seconds: int = 30

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
    # 扫描快照缓存
    # ==========================================================
    def _is_snapshot_fresh(self, max_age_seconds: Optional[int] = None) -> bool:
        ttl = int(max_age_seconds if max_age_seconds is not None else self._scan_snapshot_ttl_seconds)
        if not self._scan_snapshot:
            return False
        if self._scan_snapshot_monotonic <= 0:
            return False
        age = time.monotonic() - self._scan_snapshot_monotonic
        return age <= ttl

    def refresh_scan_snapshot(self) -> Dict[str, Any]:
        """
        强制重新扫描并覆盖缓存。
        """
        with self._scan_lock:
            snapshot = build_scan_snapshot()
            self._scan_snapshot = snapshot
            self._scan_snapshot_monotonic = time.monotonic()

            items_count = len(snapshot.get("items") or [])
            _LOG.info(
                "[LOCAL_IMPORT][RUNTIME] refreshed scan snapshot items=%s generated_at=%s",
                items_count,
                snapshot.get("generated_at"),
            )
            return snapshot

    def get_or_refresh_scan_snapshot(self, max_age_seconds: Optional[int] = None) -> Dict[str, Any]:
        """
        若缓存存在且未过期，则直接复用；
        否则重新扫描一次。
        """
        with self._scan_lock:
            if self._is_snapshot_fresh(max_age_seconds=max_age_seconds):
                snapshot = self._scan_snapshot or {}
                items_count = len(snapshot.get("items") or [])
                _LOG.info(
                    "[LOCAL_IMPORT][RUNTIME] reuse fresh scan snapshot items=%s generated_at=%s",
                    items_count,
                    snapshot.get("generated_at"),
                )
                return snapshot

        return self.refresh_scan_snapshot()

    def get_scan_snapshot(self) -> Optional[Dict[str, Any]]:
        with self._scan_lock:
            return self._scan_snapshot

    def get_scan_items(self) -> List[LocalImportFileItem]:
        with self._scan_lock:
            snapshot = self._scan_snapshot or {}
            return list(snapshot.get("items") or [])

    def get_file_path(self, market: str, symbol: str, freq: str) -> Optional[str]:
        m = str(market or "").strip().upper()
        s = str(symbol or "").strip()
        f = str(freq or "").strip()
        if not m or not s or not f:
            return None

        with self._scan_lock:
            snapshot = self._scan_snapshot or {}
            index = snapshot.get("file_index") or {}
            return index.get((m, s, f))

    def get_snapshot_generated_at(self) -> Optional[str]:
        with self._scan_lock:
            snapshot = self._scan_snapshot or {}
            return snapshot.get("generated_at")

    def clear_scan_snapshot(self) -> None:
        with self._scan_lock:
            self._scan_snapshot = None
            self._scan_snapshot_monotonic = 0.0
            _LOG.info("[LOCAL_IMPORT][RUNTIME] cleared scan snapshot")


_RUNTIME: Optional[LocalImportRuntime] = None


def get_local_import_runtime() -> LocalImportRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = LocalImportRuntime()
    return _RUNTIME
