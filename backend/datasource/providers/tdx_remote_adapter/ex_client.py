# backend/datasource/providers/tdx_remote_adapter/ex_client.py
# ==============================
# TDX 扩展行情（ExHq）socket 客户端（修正版）
#
# 本轮关键修正：
#   - host 来源统一改为 connect.cfg -> DSHOST
#   - 使用真实 ExSetupCmd1 握手包
# ==============================

from __future__ import annotations

import socket
from typing import Optional, Tuple, List

from backend.datasource.providers.tdx_remote_adapter.protocol import (
    parse_rsp_header,
    maybe_unzip_body,
)
from backend.datasource.providers.tdx_remote_adapter.ex_protocol import (
    all_ex_setup_pkgs,
    EXHQ_RSP_HEADER_LEN,
)
from backend.datasource.providers.tdx_remote_adapter.hosts import ensure_host_pool
from backend.settings import settings
from backend.utils.logger import get_logger

_LOG = get_logger("tdx_remote_adapter.ex_client")

class TdxExRemoteClientError(RuntimeError):
    pass

class TdxExRemoteClient:
    def __init__(
        self,
        *,
        host: Optional[str] = None,
        port: int = 7727,
        connect_timeout: Optional[float] = None,
        recv_timeout: Optional[float] = None,
        ping_timeout: Optional[float] = None,
    ) -> None:
        self.host = str(host or "").strip() if host else None
        self.port = int(port)
        self.connect_timeout = float(
            connect_timeout
            if connect_timeout is not None
            else settings.tdx_remote_connect_timeout_seconds
        )
        self.recv_timeout = float(
            recv_timeout
            if recv_timeout is not None
            else settings.tdx_remote_recv_timeout_seconds
        )
        self.ping_timeout = float(
            ping_timeout
            if ping_timeout is not None
            else settings.tdx_remote_ping_timeout_seconds
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

    def __enter__(self) -> "TdxExRemoteClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        if self._sock is not None:
            return

        if self.host:
            self._connect_one(self.host, self.port)
            return

        top3, err = ensure_host_pool(
            pool_type="exhq",
            ping_timeout=self.ping_timeout,
            force_retest=False,
        )
        if err or not top3:
            raise TdxExRemoteClientError(f"tdx exhq host selection failed: {err}")

        last_error: Optional[Exception] = None

        for h in top3:
            ip = str(h.get("ip") or "").strip()
            port = int(h.get("port") or 0)
            if not ip or port <= 0:
                continue

            try:
                self._connect_one(ip, port)
                return
            except Exception as e:
                last_error = e
                self.close()
                _LOG.warning("[TDX_EX_REMOTE] connect/setup failed host=%s:%s error=%s", ip, port, e)

        raise TdxExRemoteClientError(f"tdx exhq connect failed: {last_error}")

    def _connect_one(self, host: str, port: int) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.connect_timeout)
        sock.connect((host, port))
        sock.settimeout(self.recv_timeout)

        self._sock = sock
        self._connected_host = (host, port)

        _LOG.info("[TDX_EX_REMOTE] connected host=%s:%s", host, port)
        self._run_setup()

    def _run_setup(self) -> None:
        for idx, pkg in enumerate(all_ex_setup_pkgs(), start=1):
            _ = self.request_raw(pkg)
            _LOG.info("[TDX_EX_REMOTE] setup step=%s ok", idx)

    def request_raw(self, request_pkg: bytes) -> bytes:
        if self._sock is None:
            raise TdxExRemoteClientError("tdx exhq socket not connected")
        if not request_pkg:
            raise TdxExRemoteClientError("empty request pkg")

        sock = self._sock

        try:
            sent = sock.send(request_pkg)
        except Exception as e:
            raise TdxExRemoteClientError(f"send failed: {e}") from e

        if sent != len(request_pkg):
            raise TdxExRemoteClientError(
                f"send incomplete: actual={sent} expected={len(request_pkg)}"
            )

        header = self._recv_exact(EXHQ_RSP_HEADER_LEN)
        header_info = parse_rsp_header(header)

        zip_size = int(header_info["zip_size"])
        unzip_size = int(header_info["unzip_size"])

        body = self._recv_exact(zip_size)
        return maybe_unzip_body(body, zip_size=zip_size, unzip_size=unzip_size)

    def _recv_exact(self, size: int) -> bytes:
        if self._sock is None:
            raise TdxExRemoteClientError("socket not connected")
        if size <= 0:
            return b""

        chunks: List[bytes] = []
        total = 0

        while total < size:
            try:
                chunk = self._sock.recv(size - total)
            except Exception as e:
                raise TdxExRemoteClientError(f"recv failed: {e}") from e

            if not chunk:
                raise TdxExRemoteClientError(
                    f"recv broken stream: expected={size} actual={total}"
                )

            chunks.append(chunk)
            total += len(chunk)

        return b"".join(chunks)