# backend/services/local_import/snapshot_store.py
# ==============================
# 盘后数据导入 import - 候选扫描结果持久化真相源
#
# 职责：
#   - 持久化保存“当前唯一一份”候选扫描结果
#   - 读取当前候选扫描结果
#   - 覆盖写入新扫描结果
#   - 删除失效候选扫描结果
#
# 设计原则：
#   - 正式真相源 = 本地持久化快照文件
#   - 不保留历史版本
#   - 新扫描结果直接覆盖旧结果
#   - 不负责扫描，不负责执行，只负责持久化读写
# ==============================

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from backend.settings import settings
from backend.utils.fileio import atomic_write_json, read_json_safe
from backend.utils.time import now_iso
from backend.utils.logger import get_logger

_LOG = get_logger("local_import.snapshot_store")


def _snapshot_file_path() -> Path:
    return Path(settings.data_dir).resolve() / "local_import_candidates_snapshot.json"


def _item_to_json_dict(item: Any) -> Dict[str, Any]:
    return {
        "market": str(item.market or "").strip().upper(),
        "symbol": str(item.symbol or "").strip(),
        "freq": str(item.freq or "").strip(),
        "ext": str(item.ext or "").strip().lower(),
        "file_path": str(item.file_path or "").strip(),
        "file_name": str(item.file_name or "").strip(),
        "file_datetime": item.file_datetime,
    }


def _json_dict_to_item_tuple(d: Dict[str, Any]) -> Tuple[str, str, str, str, str, str, Optional[str]]:
    return (
        str(d.get("market") or "").strip().upper(),
        str(d.get("symbol") or "").strip(),
        str(d.get("freq") or "").strip(),
        str(d.get("ext") or "").strip().lower(),
        str(d.get("file_path") or "").strip(),
        str(d.get("file_name") or "").strip(),
        d.get("file_datetime"),
    )


def save_scan_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    覆盖保存当前唯一候选扫描结果。

    入参 snapshot 预期包含：
      - generated_at
      - items: List[LocalImportFileItem]
      - root_dir
    """
    items = snapshot.get("items") or []
    payload_items: List[Dict[str, Any]] = [_item_to_json_dict(x) for x in items]

    payload = {
        "generated_at": snapshot.get("generated_at") or now_iso(),
        "root_dir": str(snapshot.get("root_dir") or "").strip(),
        "items": payload_items,
        "saved_at": now_iso(),
    }

    path = _snapshot_file_path()
    atomic_write_json(path, payload, indent=2, rotate_backup=False)

    _LOG.info(
        "[LOCAL_IMPORT][SNAPSHOT_STORE] saved snapshot file=%s items=%s generated_at=%s",
        str(path),
        len(payload_items),
        payload["generated_at"],
    )
    return payload


def load_scan_snapshot() -> Optional[Dict[str, Any]]:
    """
    读取当前唯一候选扫描结果。

    返回：
      None -> 当前不存在
      dict -> 已存在
    """
    path = _snapshot_file_path()
    obj, err = read_json_safe(path, default=None)
    if err or not isinstance(obj, dict):
        return None

    raw_items = obj.get("items") if isinstance(obj.get("items"), list) else []
    items: List[Dict[str, Any]] = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        market, symbol, freq, ext, file_path, file_name, file_datetime = _json_dict_to_item_tuple(item)
        if market not in ("SH", "SZ", "BJ"):
            continue
        if not symbol or not freq or not ext:
            continue
        items.append({
            "market": market,
            "symbol": symbol,
            "freq": freq,
            "ext": ext,
            "file_path": file_path,
            "file_name": file_name,
            "file_datetime": file_datetime,
        })

    return {
        "generated_at": obj.get("generated_at"),
        "root_dir": str(obj.get("root_dir") or "").strip(),
        "items": items,
        "saved_at": obj.get("saved_at"),
    }


def delete_scan_snapshot() -> bool:
    """
    删除当前唯一候选扫描结果真相源。
    """
    path = _snapshot_file_path()
    if not path.exists():
        return False

    try:
        path.unlink()
        _LOG.info("[LOCAL_IMPORT][SNAPSHOT_STORE] deleted snapshot file=%s", str(path))
        return True
    except Exception as e:
        _LOG.warning("[LOCAL_IMPORT][SNAPSHOT_STORE] delete failed file=%s error=%s", str(path), e)
        return False


def has_scan_snapshot() -> bool:
    return _snapshot_file_path().exists()
