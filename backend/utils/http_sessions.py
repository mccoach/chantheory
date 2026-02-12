# backend/utils/http_sessions.py
# ==============================
# 说明：站点级 HTTP 会话管理（预热 + 复用 httpx.AsyncClient · V3 · 纯拿来主义版）
# 本次改动：
#   - 预热请求也纳入全局限流（统一治理所有出网点）
# ==============================

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional

import httpx

from backend.utils.logger import get_logger
from backend.utils.time import today_ymd
from backend.utils.spider_toolkit import (
    pick_user_agent,
    pick_accept_language,
    pick_connection,
    generate_sec_ch_ua,
)

# NEW: 预热也纳入全局限流
from backend.utils.async_limiter import limit_async_network_io

_LOG = get_logger("http_sessions")


@dataclass
class _SiteSession:
    """
    针对单个“预热 URL”的会话状态。
    """
    preheat_url: str
    client: Optional[httpx.AsyncClient] = None
    ua: Optional[str] = None
    last_preheat_ymd: Optional[int] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_SESSIONS: Dict[str, _SiteSession] = {}
_SESSIONS_LOCK = asyncio.Lock()


async def _create_client_for_preheat(
        preheat_url: str) -> tuple[httpx.AsyncClient, str]:
    ua = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(ua)

    headers = {
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": accept_language,
        "Connection": connection,
        "Accept-Encoding": "gzip, deflate",
    }

    if sec_ch_ua:
        headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"'

    client = httpx.AsyncClient(
        timeout=10.0,
        headers=headers,
    )

    _LOG.info(
        "[http_sessions] 初始化预热 Client",
        extra={
            "preheat_url": preheat_url,
            "user_agent": ua,
        },
    )

    return client, ua


@limit_async_network_io
async def _preheat_request(client: httpx.AsyncClient,
                           url: str) -> httpx.Response:
    """
    单独封装预热请求：纳入全局限流。
    """
    return await client.get(url)


async def _preheat(session: _SiteSession, *, force: bool = False) -> None:
    today = today_ymd()

    async with session.lock:
        if not force and session.last_preheat_ymd == today and session.client is not None:
            return

        if session.client is None:
            client, ua = await _create_client_for_preheat(session.preheat_url)
            session.client = client
            session.ua = ua

        client = session.client

        _LOG.info(
            "[http_sessions] 开始预热",
            extra={
                "preheat_url": session.preheat_url,
                "force": force,
            },
        )

        try:
            resp = await _preheat_request(client, session.preheat_url)
            resp.raise_for_status()

            session.last_preheat_ymd = today

            try:
                req_headers = dict(resp.request.headers)
            except Exception:
                req_headers = {}

            try:
                cookie_list = [str(c) for c in client.cookies.jar]
            except Exception:
                cookie_list = []

            _LOG.debug(
                "[http_sessions] 预热成功",
                extra={
                    "preheat_url": session.preheat_url,
                    "status_code": resp.status_code,
                    "request_headers_keys": list(req_headers.keys()),
                    "cookies_count": len(cookie_list),
                },
            )
        except httpx.HTTPStatusError as e:
            status = e.response.status_code if e.response is not None else None
            _LOG.warning(
                "[http_sessions] 预热 HTTP 状态异常",
                extra={
                    "preheat_url": session.preheat_url,
                    "status_code": status,
                    "error": str(e),
                },
            )
        except Exception as e:
            _LOG.error(
                "[http_sessions] 预热失败",
                extra={
                    "preheat_url": session.preheat_url,
                    "error": str(e),
                },
            )


async def _get_or_create_session(preheat_url: str) -> _SiteSession:
    key = (preheat_url or "").strip()
    if not key:
        raise ValueError("get_site_client: preheat_url is empty")

    async with _SESSIONS_LOCK:
        sess = _SESSIONS.get(key)
        if sess is None:
            sess = _SiteSession(preheat_url=key)
            _SESSIONS[key] = sess
            _LOG.info(
                "[http_sessions] 新建预热 Session 槽",
                extra={"preheat_url": key},
            )
        return sess


async def get_site_session(preheat_url: str,
                           *,
                           force_preheat: bool = False) -> _SiteSession:
    session = await _get_or_create_session(preheat_url)

    need_preheat = force_preheat or session.last_preheat_ymd != today_ymd(
    ) or session.client is None
    if need_preheat:
        await _preheat(session, force=force_preheat)

    if session.client is None:
        async with session.lock:
            if session.client is None:
                client, ua = await _create_client_for_preheat(
                    session.preheat_url)
                session.client = client
                session.ua = ua

    return session


async def get_site_client(preheat_url: str,
                          *,
                          force_preheat: bool = False) -> httpx.AsyncClient:
    session = await get_site_session(preheat_url, force_preheat=force_preheat)
    return session.client


async def get_site_ua(preheat_url: str) -> Optional[str]:
    session = await get_site_session(preheat_url, force_preheat=False)
    return session.ua


async def close_all_site_clients() -> None:
    async with _SESSIONS_LOCK:
        sessions = list(_SESSIONS.values())

    for sess in sessions:
        if sess.client is not None:
            try:
                await sess.client.aclose()
                _LOG.info(
                    "[http_sessions] 已关闭 client",
                    extra={"preheat_url": sess.preheat_url},
                )
            except Exception as e:
                _LOG.warning(
                    "[http_sessions] 关闭 client 失败",
                    extra={
                        "preheat_url": sess.preheat_url,
                        "error": str(e)
                    },
                )
