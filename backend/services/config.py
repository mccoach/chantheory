# backend/services/config.py
# ==============================
# 用户配置管理服务
#
# 说明：
#   - 用户可编辑配置统一落在 config.json
#   - settings.py 仅保留默认值定义角色，不再作为运行期用户配置真相源
#
# 最终收敛（本轮重构）：
#   - config.py 只负责通用配置文件读写
#   - 不再负责把 local-import 目录配置回写到 settings，避免形成“两层皮”
#   - local-import 目录的业务生效解释统一由：
#       backend.services.local_import.settings_service
#     负责
# ==============================

from __future__ import annotations

import json
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


def _normalize_path_text(value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    # 去掉末尾多余斜杠，避免路径显示与 raw string 保存歧义
    s = s.rstrip("\\/")
    return s


def set_config(patch: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并并保存用户配置。

    Args:
        patch: 局部配置补丁

    Returns:
        Dict[str, Any]: 保存后的完整配置
    """
    current = get_config()
    merged = dict(current)

    for k, v in (patch or {}).items():
        merged[str(k)] = v

    # 规范化已知路径项
    if "tdx_vipdoc_dir" in merged:
        merged["tdx_vipdoc_dir"] = _normalize_path_text(merged.get("tdx_vipdoc_dir"))

    settings.user_config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings.user_config_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
        f.flush()

    return merged
