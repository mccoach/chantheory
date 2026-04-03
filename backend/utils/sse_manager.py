# backend/utils/sse_manager.py
# ==============================
# 说明：SSE连接管理器（全异步·每客户端队列版）
#
# 设计原则：
#   1. 每个客户端维护一个独立 asyncio.Queue，用于背压与断连控制；
#   2. SSEManager 仅负责客户端注册/注销与广播分发；
#   3. 业务侧只需 publish 事件，app.py 中的桥接器会转发到 broadcast；
#   4. 本轮新增：支持“按事件类型精确过滤订阅”
#      - 过滤发生在入队前
#      - 未订阅事件不会进入该客户端队列
#      - 不带过滤参数时保持旧行为：全量订阅
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Optional, Iterable, Set
from datetime import datetime
from backend.utils.logger import get_logger

_LOG = get_logger("sse_manager")


class SSEClient:
    """SSE客户端封装"""

    def __init__(self, client_id: int, queue: asyncio.Queue, subscribed_types: Optional[Set[str]] = None):
        self.client_id = client_id
        self.queue = queue  # 每个客户端独立队列
        self.connected_at = datetime.now()
        # None 表示全量订阅；set 表示精确过滤订阅
        self.subscribed_types: Optional[Set[str]] = subscribed_types

    def accepts(self, event_type: str) -> bool:
        """
        判断该客户端是否订阅当前事件类型。

        规则：
          - subscribed_types is None -> 全量订阅
          - 否则严格精确匹配
        """
        if self.subscribed_types is None:
            return True
        return str(event_type or "") in self.subscribed_types

    async def send(self, event: dict):
        """发送事件到客户端队列"""
        await self.queue.put(event)


class SSEManager:
    """SSE连接管理器（单例）"""

    def __init__(self):
        self._clients: Dict[int, SSEClient] = {}
        self._client_id_counter = 0
        self._lock = asyncio.Lock()

    async def register(self, subscribed_types: Optional[Iterable[str]] = None) -> tuple[int, SSEClient]:
        """
        注册新客户端。

        Args:
            subscribed_types:
              - None: 全量订阅
              - Iterable[str]: 精确类型过滤订阅
        """
        async with self._lock:
            self._client_id_counter += 1
            client_id = self._client_id_counter

            queue = asyncio.Queue(maxsize=100)

            sub_set: Optional[Set[str]] = None
            if subscribed_types is not None:
                cleaned = {
                    str(x).strip()
                    for x in subscribed_types
                    if str(x).strip()
                }
                sub_set = cleaned

            client = SSEClient(client_id, queue, subscribed_types=sub_set)
            self._clients[client_id] = client

            _LOG.info(
                "[SSE] 客户端已连接 id=%s subscribe_types=%s all_events=%s (总数=%s)",
                client_id,
                sorted(list(sub_set)) if sub_set is not None else None,
                sub_set is None,
                len(self._clients),
            )
            return client_id, client

    async def unregister(self, client_id: int, reason: str = "normal"):
        """注销客户端"""
        async with self._lock:
            if client_id in self._clients:
                client = self._clients[client_id]
                try:
                    qsize = int(client.queue.qsize())
                except Exception:
                    qsize = -1

                del self._clients[client_id]
                _LOG.info(
                    "[SSE] 客户端已断开 id=%s reason=%s queue_size=%s limit=%s (总数=%s)",
                    client_id,
                    reason,
                    qsize,
                    100,
                    len(self._clients),
                )

    async def broadcast(self, event: dict):
        """
        广播事件到所有客户端（异步·并发推送）

        核心策略：
          - 并发推送到所有客户端，避免单个慢客户端阻塞；
          - 若某客户端队列满（超时），自动断开该客户端，避免内存堆积；
          - 本轮新增：先按客户端订阅类型过滤，未命中的事件不入该客户端队列。
        """
        async with self._lock:
            clients_snapshot = list(self._clients.items())

        if not clients_snapshot:
            _LOG.debug("[SSE] 无客户端连接，跳过广播 type=%s", event.get("type"))
            return

        event_type = str(event.get("type") or "").strip()

        # 先过滤，再推送，确保无关事件不进入客户端队列
        filtered_clients = [
            (client_id, client)
            for client_id, client in clients_snapshot
            if client.accepts(event_type)
        ]

        if not filtered_clients:
            _LOG.debug("[SSE] 无客户端订阅该事件，跳过广播 type=%s", event_type)
            return

        tasks = [
            self._send_to_client(client_id, client, event)
            for client_id, client in filtered_clients
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)

        _LOG.debug(
            "[SSE] 广播完成 type=%s 成功=%s/%s",
            event_type,
            success_count,
            len(filtered_clients),
        )

    async def _send_to_client(self, client_id: int, client: SSEClient, event: dict) -> bool:
        """发送到单个客户端（带超时保护）"""
        try:
            await asyncio.wait_for(client.send(event), timeout=1.0)
            return True
        except asyncio.TimeoutError:
            _LOG.warning("[SSE] 客户端队列满，自动断开 client_id=%s", client_id)
            await self.unregister(client_id, reason="queue_full")
            return False
        except Exception as e:
            _LOG.warning("[SSE] 推送失败 client_id=%s error=%s", client_id, e)
            await self.unregister(client_id, reason="send_error")
            return False

    def get_clients_count(self) -> int:
        """获取当前连接数"""
        return len(self._clients)


# 全局单例
_manager: Optional[SSEManager] = None


def get_sse_manager() -> SSEManager:
    """获取SSE管理器单例"""
    global _manager
    if _manager is None:
        _manager = SSEManager()
    return _manager
