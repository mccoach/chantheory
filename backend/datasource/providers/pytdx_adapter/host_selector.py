# backend/datasource/providers/pytdx_adapter/host_selector.py
# ==============================
# 说明：pytdx 主行情站列表管理与选优模块（独立职责 · V1.0）
#
# 职责：
#   1) 从通达信客户端 newhost.lst 解析主行情站列表
#   2) 将列表同步到外置 JSON：settings.tdx_hosts_json_path（全量覆盖写入）
#   3) 使用纯 TCP connect 测速，从 hosts 中挑选 top3（耗时最小的前三）
#   4) 提供“读取 top3 + 失败重测”流程给上层调用
#
# 设计目标（按你的要求）：
#   - 不依赖 pytdx/util/best_ip.py，彻底根除其噪音与误判提示
#   - 不轮询不随机，固定按 top1->top2->top3 的降级顺序
#   - 仅当 newhost.lst mtime 变化时才重新解析转存（减少无谓开销）
#   - 若 json 不存在或 top3 全失败，触发重测
#   - 若 newhost.lst 不存在/解析失败：发 system.alert + 写日志，交由人工处理
# ==============================

from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.settings import settings
from backend.utils.logger import get_logger
from backend.utils.alerts import emit_system_alert

_LOG = get_logger("pytdx.host_selector")


def _read_newhost_lst_text(path: Path) -> str:
    # newhost.lst 是 ANSI 文本，按 gbk 读取更符合中文 Windows
    with open(path, "r", encoding="gbk", errors="ignore") as f:
        return f.read()


def _parse_newhost_lst(text: str) -> List[Dict[str, Any]]:
    """
    解析通达信 newhost.lst

    输出 host 记录：
      { "name": str|None, "ip": str, "port": int }
    """
    lines = (text or "").splitlines()
    kv: Dict[str, str] = {}

    for raw in lines:
        s = str(raw).strip()
        if not s:
            continue
        if s.startswith("[") and s.endswith("]"):
            continue
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        kv[k.strip()] = v.strip()

    items: List[Dict[str, Any]] = []
    seen: set[Tuple[str, int]] = set()

    for idx in range(1, 1000):
        key_name = f"HostName{idx:02d}"
        key_ip = f"IPAddress{idx:02d}"
        key_port = f"Port{idx:02d}"

        if key_ip not in kv and key_port not in kv and key_name not in kv:
            continue

        name = (kv.get(key_name, "") or "").strip() or None
        ip = (kv.get(key_ip, "") or "").strip()
        port_raw = (kv.get(key_port, "") or "").strip()

        try:
            port = int(port_raw or "0")
        except Exception:
            port = 0

        if not ip or port <= 0:
            continue

        key = (ip, port)
        if key in seen:
            continue
        seen.add(key)

        items.append({"name": name, "ip": ip, "port": port})

    return items


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
    # 简单原子写：tmp -> replace
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _ping_tcp(ip: str, port: int, timeout: float) -> Optional[float]:
    """
    返回 TCP connect 耗时（秒）；失败返回 None
    """
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


def _compute_top3(hosts: List[Dict[str, Any]], timeout: float) -> List[Dict[str, Any]]:
    """
    选出 connect 耗时最小的前三。

    返回结构（包含 ms）：
      { "ip": "...", "port": 7709, "name": "...", "ms": 12.3 }
    """
    results: List[Tuple[float, Dict[str, Any]]] = []

    for h in hosts or []:
        ip = str(h.get("ip") or "").strip()
        try:
            port = int(h.get("port") or 0)
        except Exception:
            port = 0
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
            "ip": str(h.get("ip")),
            "port": int(h.get("port")),
            "name": h.get("name"),
            "ms": round(elapsed * 1000, 1),
        })
    return top


def _should_sync_by_mtime(*, lst_path: Path, current_json: Dict[str, Any]) -> bool:
    """
    B 方案：仅当 newhost.lst 的 mtime 变化时才解析转存。
    """
    if not bool(getattr(settings, "tdx_hosts_sync_check_mtime", True)):
        return True

    try:
        mtime = float(lst_path.stat().st_mtime)
    except Exception:
        # 无法拿到 mtime 的情况下，为了稳妥，触发同步
        return True

    prev = current_json.get("source_lst_mtime")
    try:
        prev_mtime = float(prev) if prev is not None else None
    except Exception:
        prev_mtime = None

    return prev_mtime != mtime


def sync_hosts_from_newhost_if_needed(*, force: bool = False) -> Tuple[bool, Optional[str]]:
    """
    同步 newhost.lst -> tdx_hosts.json（全量覆盖写入）

    Returns:
      (ok, error_message)
    """
    lst_path = Path(getattr(settings, "tdx_newhost_lst_path")).expanduser().resolve()
    json_path = Path(getattr(settings, "tdx_hosts_json_path")).expanduser().resolve()

    current = _json_read(json_path)

    if not force and not _should_sync_by_mtime(lst_path=lst_path, current_json=current):
        return True, None

    if not lst_path.exists():
        err = f"newhost.lst not found: {lst_path}"
        _LOG.error("[tdx.hosts] %s", err)
        emit_system_alert(
            level="error",
            code="TDX_HOSTS_SYNC_FAILED",
            message="通达信主行情服务器列表解析失败：newhost.lst 文件不存在",
            details=err,
            source="pytdx.host_selector",
            trace_id=None,
            extra={"path": str(lst_path)},
        )
        return False, err

    try:
        text = _read_newhost_lst_text(lst_path)
        hosts = _parse_newhost_lst(text)
        if not hosts:
            err = f"parsed hosts empty from {lst_path}"
            _LOG.error("[tdx.hosts] %s", err)
            emit_system_alert(
                level="error",
                code="TDX_HOSTS_SYNC_FAILED",
                message="通达信主行情服务器列表解析失败：解析结果为空",
                details=err,
                source="pytdx.host_selector",
                trace_id=None,
                extra={"path": str(lst_path)},
            )
            return False, err

        try:
            mtime = float(lst_path.stat().st_mtime)
        except Exception:
            mtime = None

        payload = {
            "updated_at": time.time(),
            "source": {
                "type": "newhost.lst",
                "path": str(lst_path),
            },
            "source_lst_mtime": mtime,
            # 全量覆盖：只保留新解析出来的 hosts
            "hosts": hosts,
            # top3 后续会由 ensure_top3 写入
            "top3": [],
        }

        _json_write_atomic(json_path, payload)

        _LOG.info("[tdx.hosts] synced hosts: rows=%d path=%s", len(hosts), str(json_path))
        return True, None

    except Exception as e:
        err = f"sync failed: {type(e).__name__}: {e}"
        _LOG.error("[tdx.hosts] %s", err, exc_info=True)
        emit_system_alert(
            level="error",
            code="TDX_HOSTS_SYNC_FAILED",
            message="通达信主行情服务器列表解析失败：内部异常",
            details=err,
            source="pytdx.host_selector",
            trace_id=None,
            extra={"path": str(lst_path)},
        )
        return False, err


def ensure_top3(*, ping_timeout: float, force_retest: bool = False) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    确保 tdx_hosts.json 中存在 top3；必要时触发同步与重测。

    Returns:
      (top3, error_message)
    """
    json_path = Path(getattr(settings, "tdx_hosts_json_path")).expanduser().resolve()

    if not json_path.exists():
        ok, err = sync_hosts_from_newhost_if_needed(force=True)
        if not ok:
            return [], err

    data = _json_read(json_path)
    hosts = data.get("hosts") if isinstance(data.get("hosts"), list) else []

    if not hosts:
        ok, err = sync_hosts_from_newhost_if_needed(force=True)
        if not ok:
            return [], err
        data = _json_read(json_path)
        hosts = data.get("hosts") if isinstance(data.get("hosts"), list) else []

    if not hosts:
        return [], "tdx_hosts.json has empty hosts list"

    if force_retest or not isinstance(data.get("top3"), list) or not data.get("top3"):
        top3 = _compute_top3(hosts, timeout=float(ping_timeout))
        if not top3:
            return [], "tcp ping failed for all hosts; cannot compute top3"

        data["top3"] = top3
        # updated_at 表示我们更新了 json（同步或重测都算更新）
        data["updated_at"] = time.time()
        _json_write_atomic(json_path, data)
        return top3, None

    # 有 top3 就直接用
    top3 = data.get("top3") if isinstance(data.get("top3"), list) else []
    # 清洗一下 top3（防御）
    cleaned: List[Dict[str, Any]] = []
    for h in top3:
        if not isinstance(h, dict):
            continue
        ip = str(h.get("ip") or "").strip()
        try:
            port = int(h.get("port") or 0)
        except Exception:
            port = 0
        if ip and port > 0:
            cleaned.append({"ip": ip, "port": port, "name": h.get("name"), "ms": h.get("ms")})

    if not cleaned:
        # top3 不可用则重测一次
        top3 = _compute_top3(hosts, timeout=float(ping_timeout))
        if not top3:
            return [], "tcp ping failed for all hosts; cannot compute top3"
        data["top3"] = top3
        data["updated_at"] = time.time()
        _json_write_atomic(json_path, data)
        return top3, None

    return cleaned, None
