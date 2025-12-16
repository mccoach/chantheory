# backend/utils/http_sessions.py
# ==============================
# 说明：站点级 HTTP 会话管理（预热 + 复用 httpx.AsyncClient · V3 · 纯拿来主义版）
#
# 设计原则：
#   - 不在本模块里配置任何静态“站点表”或 URL 归一化逻辑；
#   - 调用方（各 adapter）在各自方法中“写死并测试好”预热 URL，
#     然后将这个 URL 直接传进 http_sessions 使用；
#   - http_sessions 只做：
#       1. 针对“同一个预热 URL”维护一个 AsyncClient + UA + last_preheat_ymd；
#       2. 按自然日判断是否需要预热（调用方可强制预热）；
#       3. 管理 Cookie / 连接池 / TLS Session；
#   - 预热结果（Cookie/UA）仅存于内存中，不做磁盘持久化；
#     进程重启后重新预热一次即可。
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

_LOG = get_logger("http_sessions")


@dataclass
class _SiteSession:
    """
    针对单个“预热 URL”的会话状态。

    这里的 key 直接使用调用方传入的 preheat_url 字符串（strip 后），
    不做任何归一化或自动替换。

    字段：
      - preheat_url      : 用于预热的完整 URL（如 'https://quote.eastmoney.com/'）
      - client           : 长期复用的 AsyncClient 实例
      - ua               : 为该预热 URL 所在站点选定的 UA（client 创建时确定）
      - last_preheat_ymd : 上次成功预热的自然日（YYYYMMDD）
      - lock             : 针对该 URL 的异步锁，保护 client 初始化与预热流程
    """
    preheat_url: str
    client: Optional[httpx.AsyncClient] = None
    ua: Optional[str] = None
    last_preheat_ymd: Optional[int] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# 全局：预热 URL → Session 槽
_SESSIONS: Dict[str, _SiteSession] = {}
_SESSIONS_LOCK = asyncio.Lock()


async def _create_client_for_preheat(preheat_url: str) -> httpx.AsyncClient:
    """
    为指定预热 URL 创建一个新的 AsyncClient 实例，并选定 UA。
    """
    ua = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(ua)

    headers = {
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": accept_language,
        "Connection": connection,
        # 明确不接受 br/zstd，避免环境未安装解压库时出问题
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


async def _preheat(session: _SiteSession, *, force: bool = False) -> None:
    """
    对指定 Session 执行预热请求（访问 session.preheat_url）。

    规则：
      - 若 force=True 或 last_preheat_ymd != today，则执行预热；
      - 成功则更新 last_preheat_ymd；
      - 失败不抛异常，仅写日志（业务请求仍会继续发起，并由 async_retry 处理）。
    """
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
            resp = await client.get(session.preheat_url)
            resp.raise_for_status()

            session.last_preheat_ymd = today

            # 调试：打印预热使用的请求头 & 预热后的 Cookie（缩减为 DEBUG + 关键信息）
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
    """
    获取或创建指定预热 URL 对应的 Session 槽（不触发预热）。
    """
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


async def get_site_session(preheat_url: str, *, force_preheat: bool = False) -> _SiteSession:
    """
    获取指定预热 URL 对应的 Session，并按需执行预热。
    """
    session = await _get_or_create_session(preheat_url)

    need_preheat = force_preheat or session.last_preheat_ymd != today_ymd() or session.client is None
    if need_preheat:
        await _preheat(session, force=force_preheat)

    if session.client is None:
        async with session.lock:
            if session.client is None:
                client, ua = await _create_client_for_preheat(session.preheat_url)
                session.client = client
                session.ua = ua

    return session


async def get_site_client(preheat_url: str, *, force_preheat: bool = False) -> httpx.AsyncClient:
    """
    获取指定预热 URL 对应的 AsyncClient（按需预热）。

    Args:
        preheat_url: 预热用 URL（由调用方显式指定并事先验证）
        force_preheat: 是否强制预热（例如业务请求失败重试时）

    Returns:
        httpx.AsyncClient: 可复用的 HTTP Client（含 Cookie/连接池）
    """
    session = await get_site_session(preheat_url, force_preheat=force_preheat)
    return session.client  # 在 get_site_session 内已保证不为 None


async def get_site_ua(preheat_url: str) -> Optional[str]:
    """
    获取指定预热 URL 对应 Session 的 UA 字符串（可能触发预热）。
    """
    session = await get_site_session(preheat_url, force_preheat=False)
    return session.ua


async def close_all_site_clients() -> None:
    """
    关闭所有 Session 的 AsyncClient（应用关闭时调用）。
    """
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
                    extra={"preheat_url": sess.preheat_url, "error": str(e)},
                )