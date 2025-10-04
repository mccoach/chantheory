# backend/services/user_history.py
# ==============================
# 说明：标的框历史记录服务
# - 提供追加/查询/清空操作，写入 SQLite.symbol_history
# - 纯服务层，无副作用（除写库）
# ==============================

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.db.sqlite import insert_symbol_history, select_symbol_history, clear_symbol_history

def add_history(symbol: str, freq: Optional[str] = None, source: str = "ui") -> Dict[str, Any]:
    sym = (symbol or "").strip()
    if not sym:
        return {"ok": False, "error": "symbol is required"}
    now_iso = datetime.now().isoformat()
    try:
        insert_symbol_history([(sym, (freq or None), now_iso, source)])
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def list_history(limit: int = 50) -> Dict[str, Any]:
    try:
        rows = select_symbol_history(limit=limit)
        return {"ok": True, "items": rows}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def clear_all() -> Dict[str, Any]:
    try:
        n = clear_symbol_history()
        return {"ok": True, "deleted": int(n)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
