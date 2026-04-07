# backend/datasource/providers/tdx_remote_adapter/client.py
# ==============================
# TDX 普通 HQ socket 客户端（正式收口版）
#
# 职责：
#   - 建立普通 HQ socket 连接
#   - setup 握手
#   - 发送请求包
#   - 接收响应头/响应体
#   - 普通 HQ host failover
#
# 设计原则：
#   - host 来源统一改为 connect.cfg -> HQHOST
#   - 不再依赖 pytdx_adapter.host_selector
# ==============================

from __future__ import annotations

import socket
from typing import Optional, List, Tuple

from backend.datasource.providers.tdx_remote_adapter.protocol import (
    all_setup_pkgs,
    parse_rsp_header,
    maybe_unzip_body,
    RSP_HEADER_LEN,
)
from backend.datasource.providers.tdx_remote_adapter.hosts import ensure_host_pool
from backend.settings import settings
from backend.utils.logger import get_logger

_LOG = get_logger("tdx_remote_adapter.client")

class TdxRemoteClientError(RuntimeError):
    pass

class TdxRemoteClient:
    def __init__(
        self,
        *,
        connect_timeout: Optional[float] = None,
        ping_timeout: Optional[float] = None,
        recv_timeout: Optional[float] = None,
    ) -> None:
        self.connect_timeout = float(
            connect_timeout
            if connect_timeout is not None
            else settings.tdx_remote_connect_timeout_seconds
        )
        self.ping_timeout = float(
            ping_timeout
            if ping_timeout is not None
            else settings.tdx_remote_ping_timeout_seconds
        )
        self.recv_timeout = float(
            recv_timeout
            if recv_timeout is not None
            else settings.tdx_remote_recv_timeout_seconds
        )

        self._sock: Optional[socket.socket] = None
        self._connected_host: Optional[Tuple[str, int]] = None

    @property
    def connected_host(self) -> Optional[Tuple[str, int]]:
        return self._connected_host

    def close(self) -> None:
        sock = self._sock
        self._sock = None
        self._connected_host = None

        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

    def __enter__(self) -> "TdxRemoteClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        if self._sock is not None:
            return

        top3, err = ensure_host_pool(
            pool_type="hq",
            ping_timeout=self.ping_timeout,
            force_retest=False,
        )
        if err or not top3:
            raise TdxRemoteClientError(f"tdx hq host selection failed: {err}")

        last_error: Optional[Exception] = None

        for h in top3:
            ip = str(h.get("ip") or "").strip()
            port = int(h.get("port") or 0)
            if not ip or port <= 0:
                continue

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.connect_timeout)
                sock.connect((ip, port))
                sock.settimeout(self.recv_timeout)

                self._sock = sock
                self._connected_host = (ip, port)

                _LOG.info("[TDX_REMOTE] connected hq host=%s:%s", ip, port)

                self._run_setup()
                return

            except Exception as e:
                last_error = e
                try:
                    sock.close()
                except Exception:
                    pass
                self._sock = None
                self._connected_host = None
                _LOG.warning("[TDX_REMOTE] connect/setup failed hq host=%s:%s error=%s", ip, port, e)

        raise TdxRemoteClientError(f"tdx hq connect failed: {last_error}")

    def _run_setup(self) -> None:
        for idx, pkg in enumerate(all_setup_pkgs(), start=1):
            _ = self.request_raw(pkg)
            _LOG.info("[TDX_REMOTE] hq setup step=%s ok", idx)

    def request_raw(self, request_pkg: bytes) -> bytes:
        if self._sock is None:
            raise TdxRemoteClientError("tdx remote socket not connected")
        if not request_pkg:
            raise TdxRemoteClientError("empty request pkg")

        sock = self._sock

        try:
            sent = sock.send(request_pkg)
        except Exception as e:
            raise TdxRemoteClientError(f"send failed: {e}") from e

        if sent != len(request_pkg):
            raise TdxRemoteClientError(
                f"send incomplete: actual={sent} expected={len(request_pkg)}"
            )

        header = self._recv_exact(RSP_HEADER_LEN)
        header_info = parse_rsp_header(header)

        zip_size = int(header_info["zip_size"])
        unzip_size = int(header_info["unzip_size"])

        body = self._recv_exact(zip_size)
        return maybe_unzip_body(body, zip_size=zip_size, unzip_size=unzip_size)

    def _recv_exact(self, size: int) -> bytes:
        if self._sock is None:
            raise TdxRemoteClientError("socket not connected")
        if size <= 0:
            return b""

        chunks: List[bytes] = []
        total = 0

        while total < size:
            try:
                chunk = self._sock.recv(size - total)
            except Exception as e:
                raise TdxRemoteClientError(f"recv failed: {e}") from e

            if not chunk:
                raise TdxRemoteClientError(
                    f"recv broken stream: expected={size} actual={total}"
                )

            chunks.append(chunk)
            total += len(chunk)

        return b"".join(chunks)