# backend/datasource/providers/tdx_remote_adapter/hosts.py
# ==============================
# TDX 远程主机统一管理
#
# 职责：
#   1) 解析通达信 connect.cfg
#   2) 同时提取：
#       - [HQHOST]  普通主行情服务器
#       - [DSHOST]  扩展行情服务器
#   3) 对两类服务器分别执行 TCP connect 测速
#   4) 生成统一 tdx_hosts.json
#   5) 对外提供：
#       - 普通 HQ top3
#       - ExHq top3
#
# 设计原则：
#   - connect.cfg 是唯一服务器配置真相源
#   - 不再解析 newhost.lst
#   - 不再保留 pytdx_adapter/host_selector.py
#   - 本模块只负责 host 配置与选优，不负责 socket 协议
# ==============================

from __future__ import annotations

import configparser
import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.settings import settings
from backend.utils.logger import get_logger
from backend.utils.alerts import emit_system_alert

_LOG = get_logger("tdx_remote_adapter.hosts")

def _default_connect_cfg_path() -> Path:
    return Path(r"D:\TDX_new\connect.cfg").expanduser().resolve()

def _read_connect_cfg(path: Path) -> configparser.ConfigParser:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"connect.cfg not found: {p}")

    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(p, encoding="gbk")
    return parser

def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except Exception:
        return int(default)

def _json_read(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}

def _json_write_atomic(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def _ping_tcp(ip: str, port: int, timeout: float) -> Optional[float]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        t0 = time.monotonic()
        sock.connect((ip, port))
        elapsed = time.monotonic() - t0
        sock.close()
        return elapsed
    except Exception:
        return None

def _extract_hosts_from_section(
    parser: configparser.ConfigParser,
    section_name: str,
) -> Dict[str, Any]:
    if not parser.has_section(section_name):
        return {
            "section": section_name,
            "primary_index": None,
            "hosts": [],
        }

    sec = parser[section_name]
    host_num = _safe_int(sec.get("HostNum"), 0)
    primary_index = _safe_int(sec.get("PrimaryHost"), -1)

    items: List[Dict[str, Any]] = []
    seen: set[Tuple[str, int]] = set()

    for idx in range(1, host_num + 1):
        suffix = f"{idx:02d}"
        host_name = str(sec.get(f"HostName{suffix}", "") or "").strip()
        ip = str(sec.get(f"IPAddress{suffix}", "") or "").strip()
        port = _safe_int(sec.get(f"Port{suffix}"), 0)

        if not ip or port <= 0:
            continue

        key = (ip, port)
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "index": idx,
            "name": host_name,
            "ip": ip,
            "port": port,
            "section": section_name,
            "is_primary": bool(idx == primary_index),
        })

    return {
        "section": section_name,
        "primary_index": primary_index if primary_index > 0 else None,
        "hosts": items,
    }

def _compute_top3(hosts: List[Dict[str, Any]], timeout: float) -> List[Dict[str, Any]]:
    results: List[Tuple[float, Dict[str, Any]]] = []

    for h in hosts or []:
        ip = str(h.get("ip") or "").strip()
        port = _safe_int(h.get("port"), 0)
        if not ip or port <= 0:
            continue

        elapsed = _ping_tcp(ip, port, timeout)
        if elapsed is None:
            continue

        results.append((elapsed, h))

    results.sort(key=lambda x: x[0])

    top: List[Dict[str, Any]] = []
    for elapsed, h in results[:3]:
        top.append({
            "index": int(h.get("index") or 0),
            "ip": str(h.get("ip")),
            "port": int(h.get("port")),
            "name": h.get("name"),
            "section": h.get("section"),
            "is_primary": bool(h.get("is_primary")),
            "ms": round(elapsed * 1000, 1),
        })
    return top

def _should_sync_by_mtime(*, cfg_path: Path, current_json: Dict[str, Any]) -> bool:
    if not bool(getattr(settings, "tdx_hosts_sync_check_mtime", True)):
        return True

    try:
        mtime = float(cfg_path.stat().st_mtime)
    except Exception:
        return True

    prev = current_json.get("source_connect_cfg_mtime")
    try:
        prev_mtime = float(prev) if prev is not None else None
    except Exception:
        prev_mtime = None

    return prev_mtime != mtime

def _hosts_json_path() -> Path:
    return Path(settings.tdx_hosts_json_path).expanduser().resolve()

def sync_hosts_from_connect_cfg_if_needed(*, force: bool = False) -> Tuple[bool, Optional[str]]:
    cfg_path = _default_connect_cfg_path()
    json_path = _hosts_json_path()

    current = _json_read(json_path)

    if not force and not _should_sync_by_mtime(cfg_path=cfg_path, current_json=current):
        return True, None

    if not cfg_path.exists():
        err = f"connect.cfg not found: {cfg_path}"
        _LOG.error("[tdx.remote.hosts] %s", err)
        emit_system_alert(
            level="error",
            code="TDX_CONNECT_CFG_SYNC_FAILED",
            message="通达信服务器配置解析失败：connect.cfg 文件不存在",
            details=err,
            source="tdx_remote_adapter.hosts",
            trace_id=None,
            extra={"path": str(cfg_path)},
        )
        return False, err

    try:
        parser = _read_connect_cfg(cfg_path)

        hq = _extract_hosts_from_section(parser, "HQHOST")
        dshost = _extract_hosts_from_section(parser, "DSHOST")

        if not hq["hosts"] and not dshost["hosts"]:
            err = f"parsed HQHOST and DSHOST both empty from {cfg_path}"
            _LOG.error("[tdx.remote.hosts] %s", err)
            emit_system_alert(
                level="error",
                code="TDX_CONNECT_CFG_SYNC_FAILED",
                message="通达信服务器配置解析失败：HQHOST/DSHOST 结果为空",
                details=err,
                source="tdx_remote_adapter.hosts",
                trace_id=None,
                extra={"path": str(cfg_path)},
            )
            return False, err

        try:
            mtime = float(cfg_path.stat().st_mtime)
        except Exception:
            mtime = None

        payload = {
            "updated_at": time.time(),
            "source": {
                "type": "connect.cfg",
                "path": str(cfg_path),
            },
            "source_connect_cfg_mtime": mtime,
            "hq": {
                "primary_index": hq["primary_index"],
                "hosts": hq["hosts"],
                "top3": [],
            },
            "exhq": {
                "primary_index": dshost["primary_index"],
                "hosts": dshost["hosts"],
                "top3": [],
            },
        }

        _json_write_atomic(json_path, payload)
        _LOG.info(
            "[tdx.remote.hosts] synced connect.cfg hq_rows=%s exhq_rows=%s path=%s",
            len(hq["hosts"]),
            len(dshost["hosts"]),
            str(json_path),
        )
        return True, None

    except Exception as e:
        err = f"sync failed: {type(e).__name__}: {e}"
        _LOG.error("[tdx.remote.hosts] %s", err, exc_info=True)
        emit_system_alert(
            level="error",
            code="TDX_CONNECT_CFG_SYNC_FAILED",
            message="通达信服务器配置解析失败：内部异常",
            details=err,
            source="tdx_remote_adapter.hosts",
            trace_id=None,
            extra={"path": str(cfg_path)},
        )
        return False, err

def ensure_host_pool(
    *,
    pool_type: str,
    ping_timeout: float,
    force_retest: bool = False,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    pool_type:
      - 'hq'
      - 'exhq'
    """
    pool = str(pool_type or "").strip().lower()
    if pool not in ("hq", "exhq"):
        return [], f"invalid pool_type: {pool_type}"

    json_path = _hosts_json_path()

    if not json_path.exists():
        ok, err = sync_hosts_from_connect_cfg_if_needed(force=True)
        if not ok:
            return [], err

    data = _json_read(json_path)
    block = data.get(pool) if isinstance(data.get(pool), dict) else {}
    hosts = block.get("hosts") if isinstance(block.get("hosts"), list) else []

    if not hosts:
        ok, err = sync_hosts_from_connect_cfg_if_needed(force=True)
        if not ok:
            return [], err
        data = _json_read(json_path)
        block = data.get(pool) if isinstance(data.get(pool), dict) else {}
        hosts = block.get("hosts") if isinstance(block.get("hosts"), list) else []

    if not hosts:
        return [], f"{pool} hosts empty in connect.cfg parsed result"

    top3 = block.get("top3") if isinstance(block.get("top3"), list) else []

    if force_retest or not top3:
        top3 = _compute_top3(hosts, timeout=float(ping_timeout))
        if not top3:
            return [], f"tcp ping failed for all {pool} hosts; cannot compute top3"

        block["top3"] = top3
        data[pool] = block
        data["updated_at"] = time.time()
        _json_write_atomic(json_path, data)
        return top3, None

    cleaned: List[Dict[str, Any]] = []
    for h in top3:
        if not isinstance(h, dict):
            continue
        ip = str(h.get("ip") or "").strip()
        port = _safe_int(h.get("port"), 0)
        if ip and port > 0:
            cleaned.append({
                "index": _safe_int(h.get("index"), 0),
                "ip": ip,
                "port": port,
                "name": h.get("name"),
                "section": h.get("section"),
                "is_primary": bool(h.get("is_primary")),
                "ms": h.get("ms"),
            })

    if not cleaned:
        top3 = _compute_top3(hosts, timeout=float(ping_timeout))
        if not top3:
            return [], f"tcp ping failed for all {pool} hosts; cannot compute top3"
        block["top3"] = top3
        data[pool] = block
        data["updated_at"] = time.time()
        _json_write_atomic(json_path, data)
        return top3, None

    return cleaned, None