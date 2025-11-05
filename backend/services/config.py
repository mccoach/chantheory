# backend/services/config.py
# ==============================
# 说明：用户配置管理服务 (REFACTORED - Simplified)
# - (FIX) 移除了对 migrate_db_file 和 close_conn 的依赖。
# - (SIMPLIFIED) 不再支持运行时动态更改数据库路径。
#   用户如需更改数据库路径，应修改环境变量或配置文件后重启应用。
# ==============================

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from backend.settings import settings

def get_config() -> Dict[str, Any]:
    """从配置文件读取用户配置。"""
    try:
        if not settings.user_config_path.exists():
            return {}
        with open(settings.user_config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def set_config(data: Dict[str, Any]) -> None:
    """将用户配置写入配置文件。"""
    try:
        settings.user_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # (REMOVED) 数据库路径变更逻辑已移除
        # 用户需要更改数据库路径时，应：
        # 1. 修改环境变量 CHAN_DB_PATH 或直接修改 settings.py
        # 2. 重启应用
        
        with open(settings.user_config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise RuntimeError(f"Failed to save config: {e}")
