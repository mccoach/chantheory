# backend/utils/fileio.py
# ==============================
# 说明：文件 I/O 与 JSON 原子写工具
# - atomic_write_json：原子写入 JSON（.tmp 写入 + fsync + 轮换 .bak/.bak2 备份）
# - read_json_safe：读取 JSON，失败返回 (default, error)
# - file_signature：返回 (mtime, size) 用于变更检测（轻量）
# 设计目标：简单、可靠、跨平台
# ==============================

from __future__ import annotations  # 注解前置
# 标准库导入
import json  # JSON 编解码
import os  # 低层文件操作（fsync/rename）
from pathlib import Path  # 跨平台路径
from typing import Any, Tuple, Optional  # 类型提示

def ensure_parent_dir(path: Path) -> None:
    """确保目标文件的父目录存在"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)  # 递归创建目录

def atomic_write_json(path: Path, data: Any, indent: int = 2, rotate_backup: bool = True) -> None:
    """原子写入 JSON 文件，并可选滚动备份
    - 写入流程：path.tmp 写入 → flush+fsync → 滚动备份（.bak2 <- .bak <- path）→ rename tmp->path
    - 发生异常时尽量不破坏现有 path
    """
    path = Path(path).resolve()  # 规范路径
    ensure_parent_dir(path)  # 确保目录存在
    tmp_path = path.with_suffix(path.suffix + ".tmp")  # 临时文件
    bak_path = path.with_suffix(path.suffix + ".bak")  # 第一备份
    bak2_path = path.with_suffix(path.suffix + ".bak2")  # 第二备份
    # 1) 写临时文件
    f = None  # 文件句柄
    try:
        f = open(tmp_path, "w", encoding="utf-8")  # 打开临时文件
        json.dump(data, f, ensure_ascii=False, indent=indent)  # 写 JSON
        f.flush()  # 刷新缓冲
        os.fsync(f.fileno())  # 刷新到磁盘
    finally:
        if f:
            f.close()  # 关闭
    # 2) 滚动备份（可选）
    try:
        if rotate_backup and path.exists():  # 仅当原文件存在才轮换
            if bak_path.exists():
                try:
                    if bak2_path.exists():
                        bak2_path.unlink()  # 删除旧的 bak2
                except Exception:
                    pass  # 忽略
                try:
                    bak_path.rename(bak2_path)  # bak -> bak2
                except Exception:
                    pass  # 忽略
            try:
                path.rename(bak_path)  # path -> bak
            except Exception:
                pass  # 忽略（不可阻塞主流程）
    except Exception:
        # 轮换备份失败不应阻断主写入
        pass
    # 3) tmp -> path 原子替换
    os.replace(tmp_path, path)  # 用新的临时文件覆盖目标文件（原子操作）

def read_json_safe(path: Path, default: Any = None) -> Tuple[Any, Optional[str]]:
    """读取 JSON 文件，失败返回 (default, error_message)"""
    path = Path(path).resolve()  # 规范路径
    if not path.exists():  # 文件不存在
        return default, "file not found"  # 返回默认与错误信息
    try:
        with open(path, "r", encoding="utf-8") as f:  # 打开
            obj = json.load(f)  # 解析
            return obj, None  # 返回对象与无错误
    except Exception as e:
        return default, f"read_json_failed: {e}"  # 返回错误信息

def file_signature(path: Path) -> Tuple[Optional[float], Optional[int]]:
    """返回文件签名 (mtime, size)，用于轻量变更检测
    - 若文件不存在返回 (None, None)
    """
    path = Path(path).resolve()  # 规范路径
    if not path.exists():  # 不存在
        return None, None  # 空签名
    stat = path.stat()  # 文件属性
    return stat.st_mtime, stat.st_size  # 修改时间与大小
