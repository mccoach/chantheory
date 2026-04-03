# backend/services/local_import/candidates.py
# ==============================
# 盘后数据导入 import - 候选结果读取 / 刷新服务
#
# 职责：
#   - 读取当前已持久化保存的候选结果（轻操作）
#   - 显式重新扫描并覆盖当前唯一候选结果（重操作）
#   - 基于扫描结果 + symbol_index 双控筛选，生成面向前端的候选项列表
#
# 关键规则：
#   - 候选结果正式真相源 = 本地持久化快照文件
#   - GET candidates：只读当前已有结果，不触发重扫描
#   - POST refresh：显式触发一次重扫描，并覆盖当前唯一结果
#   - 新扫描结果覆盖旧结果，不保留历史版本
# ==============================

from __future__ import annotations

from typing import Dict, Any, List, Optional

from backend.services.local_import.runtime import get_local_import_runtime
from backend.services.local_import.scan import build_scan_snapshot
from backend.services.local_import.snapshot_store import (
    save_scan_snapshot,
)
from backend.utils.common import get_symbol_record_from_db
from backend.utils.time import now_iso
from backend.utils.logger import get_logger

_LOG = get_logger("local_import.candidates")


def _build_visible_items_from_snapshot(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    scanned = snapshot.get("items") or []

    items: List[Dict[str, Any]] = []
    for item in scanned:
        if isinstance(item, dict):
            market = str(item.get("market") or "").strip().upper()
            symbol = str(item.get("symbol") or "").strip()
            freq = str(item.get("freq") or "").strip()
            file_datetime = item.get("file_datetime")
        else:
            market = str(item.market or "").strip().upper()
            symbol = str(item.symbol or "").strip()
            freq = str(item.freq or "").strip()
            file_datetime = item.file_datetime

        meta = get_symbol_record_from_db(symbol=symbol, market=market)
        if not meta:
            continue

        name = str(meta.get("name") or "").strip()
        if not name:
            continue

        items.append({
            "market": market,
            "symbol": symbol,
            "freq": freq,
            "name": name,
            "class": meta.get("class"),
            "type": meta.get("type"),
            "file_datetime": file_datetime,
        })

    items.sort(key=lambda x: (str(x.get("market")), str(x.get("symbol")), str(x.get("freq"))))
    return items


def get_import_candidates_snapshot() -> Dict[str, Any]:
    """
    轻操作：
      - 只读取当前已持久化保存的候选结果
      - 不触发重扫描
    """
    runtime = get_local_import_runtime()
    snapshot = runtime.get_persisted_snapshot()

    if not snapshot:
        return {
            "ok": True,
            "ready": False,
            "items": [],
            "generated_at": None,
            "ui_message": "当前还没有候选结果，请先刷新候选",
        }

    items = _build_visible_items_from_snapshot(snapshot)

    ui_message = None
    scanned = snapshot.get("items") or []
    if scanned and not items:
        ui_message = "已有候选扫描结果，但没有可用于展示处理的有效标的信息"

    _LOG.info(
        "[LOCAL_IMPORT][CANDIDATES][GET] ready=true scanned=%s visible=%s generated_at=%s",
        len(scanned),
        len(items),
        snapshot.get("generated_at"),
    )

    return {
        "ok": True,
        "ready": True,
        "items": items,
        "generated_at": snapshot.get("generated_at"),
        "ui_message": ui_message or "",
    }


def refresh_import_candidates_snapshot() -> Dict[str, Any]:
    """
    重操作：
      - 显式重新扫描本地文件
      - 覆盖当前唯一候选结果真相源
      - 只返回轻状态，不返回候选结果本体
    """
    snapshot = build_scan_snapshot()
    saved = save_scan_snapshot(snapshot)

    scanned = saved.get("items") or []
    ui_message = ""
    if not scanned:
        ui_message = "刷新完成，但未扫描到可处理的本地盘后数据文件"

    _LOG.info(
        "[LOCAL_IMPORT][CANDIDATES][REFRESH] scanned=%s generated_at=%s",
        len(scanned),
        saved.get("generated_at"),
    )

    return {
        "ok": True,
        "ready": True,
        "generated_at": saved.get("generated_at"),
        "ui_message": ui_message,
    }
