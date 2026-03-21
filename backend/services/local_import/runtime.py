# backend/services/local_import/runtime.py
# ==============================
# 盘后数据导入 import - 运行时状态容器
#
# 职责：
#   - 维护进程内运行时状态
#   - 维护扫描结果缓存与内部路径索引
#   - 提供串行调度锁，保证同一时刻只有一个调度循环在推进
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Tuple, List, Optional

from backend.services.local_import.scan import (
    LocalImportFileItem,
    scan_importable_files,
    build_file_index,
)


class LocalImportRuntime:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._scanned_items: List[LocalImportFileItem] = []
        self._file_index: Dict[Tuple[str, str, str], str] = {}
        self._last_refresh_ok: bool = False

    async def lock(self) -> None:
        await self._lock.acquire()

    def unlock(self) -> None:
        if self._lock.locked():
            self._lock.release()

    def is_locked(self) -> bool:
        return self._lock.locked()

    def refresh_scan_cache(self) -> None:
        items = scan_importable_files()
        index = build_file_index(items)

        self._scanned_items = items
        self._file_index = index
        self._last_refresh_ok = True

    def get_scanned_items(self) -> List[LocalImportFileItem]:
        return list(self._scanned_items)

    def get_file_index(self) -> Dict[Tuple[str, str, str], str]:
        return dict(self._file_index)

    def get_file_path(self, market: str, symbol: str, freq: str) -> Optional[str]:
        key = (
            str(market or "").strip().upper(),
            str(symbol or "").strip(),
            str(freq or "").strip(),
        )
        return self._file_index.get(key)

    def has_refreshed(self) -> bool:
        return bool(self._last_refresh_ok)


_runtime: Optional[LocalImportRuntime] = None


def get_local_import_runtime() -> LocalImportRuntime:
    global _runtime
    if _runtime is None:
        _runtime = LocalImportRuntime()
    return _runtime
