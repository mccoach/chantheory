# backend/utils/sse_manager.py
# ==============================
# 说明：SSE连接管理器（全异步·零队列版）
# 设计原则：
#   1. 直接推送，无中间队列
#   2. 客户端管理器独立于事件总线
#   3. 异步原生支持（asyncio）
# ==============================

from __future__ import annotations

import asyncio
import json
from typing import Dict, Set, Optional
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
                f"[SSE] 客户端已连接 id={client_id} "
                f"(总数={len(self._clients)})"
            )
            return client_id, client
    
    async def unregister(self, client_id: int):
        """注销客户端"""
        async with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]
                _LOG.info(f"[SSE] 客户端已断开 id={client_id} (总数={len(self._clients)})")
    
    async def broadcast(self, event: dict):
        """
        广播事件到所有客户端（异步·并发推送）
        
        核心优化：
          - 使用 asyncio.gather 并发推送
          - 自动清理失败的客户端
        """
    
        # 增加详细日志
        _LOG.info(
            f"[SSE] 📡 广播事件 "
            f"type={event.get('type')} "
            f"category={event.get('category')} "
            f"symbol={event.get('symbol')} "
            f"status={event.get('status')} "
            f"当前连接数={len(self._clients)}"
        )
        
        async with self._lock:
            clients_snapshot = list(self._clients.items())
        
        if not clients_snapshot:
            _LOG.warning("[SSE] 无客户端连接，事件丢弃")
            return
        
        # 并发推送到所有客户端
        tasks = []
        for client_id, client in clients_snapshot:
            tasks.append(self._send_to_client(client_id, client, event))
        
        # 等待所有推送完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计成功率
        success_count = sum(1 for r in results if r is True)
        
        _LOG.debug(
            f"[SSE] 广播完成 type={event.get('type')} "
            f"成功={success_count}/{len(clients_snapshot)}"
        )
    
    async def _send_to_client(self, client_id: int, client: SSEClient, event: dict) -> bool:
        """发送到单个客户端（带超时保护）"""
        try:
            # 超时保护：避免慢客户端阻塞
            await asyncio.wait_for(client.send(event), timeout=1.0)
            return True
        except asyncio.TimeoutError:
            _LOG.warning(f"[SSE] 客户端 {client_id} 队列满，自动断开")
            await self.unregister(client_id)
            return False
        except Exception as e:
            _LOG.warning(f"[SSE] 推送失败 client_id={client_id}: {e}")
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