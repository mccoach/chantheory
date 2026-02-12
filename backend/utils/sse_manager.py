# backend/utils/sse_manager.py
# ==============================
# 说明：SSE连接管理器（全异步·每客户端队列版）
#
# 设计原则：
#   1. 每个客户端维护一个独立 asyncio.Queue，用于背压与断连控制；
#   2. SSEManager 仅负责客户端注册/注销与广播分发；
#   3. 业务侧只需 publish 事件，app.py 中的桥接器会转发到 broadcast。
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Optional
from datetime import datetime
from backend.utils.logger import get_logger

_LOG = get_logger("sse_manager")


class SSEClient:
    """SSE客户端封装"""

    def __init__(self, client_id: int, queue: asyncio.Queue):
        self.client_id = client_id
        self.queue = queue  # 每个客户端独立队列
        self.connected_at = datetime.now()

    async def send(self, event: dict):
        """发送事件到客户端队列"""
        await self.queue.put(event)


class SSEManager:
    """SSE连接管理器（单例）"""

    def __init__(self):
        self._clients: Dict[int, SSEClient] = {}
        self._client_id_counter = 0
        self._lock = asyncio.Lock()

    async def register(self) -> tuple[int, SSEClient]:
        """注册新客户端"""
        async with self._lock:
            self._client_id_counter += 1
            client_id = self._client_id_counter

            queue = asyncio.Queue(maxsize=100)
            client = SSEClient(client_id, queue)
            self._clients[client_id] = client

            _LOG.info(
                "[SSE] 客户端已连接 id=%s (总数=%s)",
                client_id,
                len(self._clients),
            )
            return client_id, client

    async def unregister(self, client_id: int):
        """注销客户端"""
        async with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]
                _LOG.info(
                    "[SSE] 客户端已断开 id=%s (总数=%s)",
                    client_id,
                    len(self._clients),
                )

    async def broadcast(self, event: dict):
        """
        广播事件到所有客户端（异步·并发推送）

        核心策略：
          - 并发推送到所有客户端，避免单个慢客户端阻塞；
          - 若某客户端队列满（超时），自动断开该客户端，避免内存堆积。
        """
        async with self._lock:
            clients_snapshot = list(self._clients.items())

        if not clients_snapshot:
            _LOG.debug("[SSE] 无客户端连接，跳过广播 type=%s", event.get("type"))
            return

        # 并发推送到所有客户端
        tasks = [
            self._send_to_client(client_id, client, event)
            for client_id, client in clients_snapshot
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)

        _LOG.debug(
            "[SSE] 广播完成 type=%s 成功=%s/%s",
            event.get("type"),
            success_count,
            len(clients_snapshot),
        )

    async def _send_to_client(self, client_id: int, client: SSEClient, event: dict) -> bool:
        """发送到单个客户端（带超时保护）"""
        try:
            await asyncio.wait_for(client.send(event), timeout=1.0)
            return True
        except asyncio.TimeoutError:
            _LOG.warning("[SSE] 客户端队列满，自动断开 client_id=%s", client_id)
            await self.unregister(client_id)
            return False
        except Exception as e:
            _LOG.warning("[SSE] 推送失败 client_id=%s error=%s", client_id, e)
            await self.unregister(client_id)
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
