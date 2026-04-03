# backend/services/local_import/settings_service.py
# ==============================
# 盘后数据导入路径设置服务
#
# 职责：
#   - 读取当前生效的盘后导入根目录
#   - 打开 Windows 原生文件夹选择窗口
#   - 保存用户确认的新路径到 config.json
#
# 最终真相源收敛（本轮重构）：
#   - local-import 扫描目录唯一真相源：config.json 中的 tdx_vipdoc_dir
#   - 若 config.json 未配置，则回退到 settings.py 中的默认值
#   - 不再依赖“把 config 再同步写回 settings 才算生效”
#
# 本轮改动（候选结果失效规则）：
#   - 一旦根目录设置成功发生变化
#   - 立即删除旧候选结果本地持久化真相源
#   - 之后 GET candidates 应返回 ready=false，等待用户显式 refresh
# ==============================

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from backend.settings import settings
from backend.services.config import get_config, set_config
from backend.services.local_import.snapshot_store import delete_scan_snapshot
from backend.utils.logger import get_logger

_LOG = get_logger("local_import.settings_service")


def _default_local_import_root_dir() -> Path:
    return Path(settings.tdx_vipdoc_dir).expanduser().resolve()


def _configured_local_import_root_dir_text() -> str:
    cfg = get_config()
    return str(cfg.get("tdx_vipdoc_dir") or "").strip()


def get_effective_local_import_root_dir() -> Path:
    configured = _configured_local_import_root_dir_text()
    if configured:
        return Path(configured).expanduser().resolve()
    return _default_local_import_root_dir()


def get_local_import_settings() -> Dict[str, Any]:
    effective = get_effective_local_import_root_dir()

    return {
        "ok": True,
        "tdx_vipdoc_dir": str(effective),
        "message": "",
    }


def _browse_dir_sync(initial_dir: Optional[str] = None) -> Dict[str, Any]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as e:
        return {
            "ok": False,
            "selected_dir": "",
            "message": f"打开文件夹选择窗口失败: {e}",
        }

    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        init_dir = str(initial_dir or "").strip()
        if not init_dir:
            init_dir = str(get_effective_local_import_root_dir())

        selected = filedialog.askdirectory(
            title="请选择通达信盘后数据根目录（vipdoc）",
            initialdir=init_dir,
            mustexist=True,
        )

        try:
            root.destroy()
        except Exception:
            pass

        selected_text = str(selected or "").strip()
        if not selected_text:
            return {
                "ok": False,
                "selected_dir": "",
                "message": "用户取消选择",
            }

        selected_path = str(Path(selected_text).expanduser().resolve())
        return {
            "ok": True,
            "selected_dir": selected_path,
            "message": "",
        }
    except Exception as e:
        return {
            "ok": False,
            "selected_dir": "",
            "message": f"打开文件夹选择窗口失败: {e}",
        }


async def browse_local_import_root_dir(initial_dir: Optional[str] = None) -> Dict[str, Any]:
    return await asyncio.to_thread(_browse_dir_sync, initial_dir)


def _validate_local_import_root_dir(path_text: str) -> str:
    s = str(path_text or "").strip()
    if not s:
        raise ValueError("目录不能为空")

    p = Path(s).expanduser()
    if not p.is_absolute():
        raise ValueError("必须提供绝对路径")

    if not p.exists():
        raise ValueError("目录不存在")

    if not p.is_dir():
        raise ValueError("路径不是文件夹")

    return str(p.resolve())


def save_local_import_root_dir(path_text: str) -> Dict[str, Any]:
    """
    保存新的盘后导入根目录到 config.json。

    规则：
      - 保存成功即代表后续扫描目录已切换
      - 若目录发生变化，旧候选结果立即失效并删除
      - 后续必须由用户显式 refresh 才会生成新的候选结果
    """
    old_effective = str(get_effective_local_import_root_dir())
    normalized = _validate_local_import_root_dir(path_text)

    merged = set_config({
        "tdx_vipdoc_dir": normalized,
    })

    effective = str(merged.get("tdx_vipdoc_dir") or normalized).strip()
    if not effective:
        effective = normalized

    changed = (str(old_effective).strip() != str(effective).strip())
    if changed:
        delete_scan_snapshot()
        _LOG.info(
            "[LOCAL_IMPORT][SETTINGS] root changed old=%s new=%s snapshot invalidated",
            old_effective,
            effective,
        )
        message = "路径保存成功，旧候选结果已失效，请重新刷新候选"
    else:
        _LOG.info("[LOCAL_IMPORT][SETTINGS] saved tdx_vipdoc_dir=%s (unchanged)", effective)
        message = "路径保存成功"

    return {
        "ok": True,
        "tdx_vipdoc_dir": effective,
        "message": message,
    }
