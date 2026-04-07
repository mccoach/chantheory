# backend/datasource/providers/tdx_remote_adapter/__init__.py
# ==============================
# TDX 远程行情适配器包
#
# 当前正式导出：
#   - 普通 HQ socket 客户端与 bars 原子能力
#   - ExHq 相关能力暂保留文件，但不进入当前正式普通行情主链
# ==============================

from __future__ import annotations

from .client import TdxRemoteClient, TdxRemoteClientError
from .bars import (
    get_security_bars_tdx_remote,
    get_index_bars_tdx_remote,
    get_auto_routed_bars_tdx_remote,
)
from .hosts import (
    sync_hosts_from_connect_cfg_if_needed,
    ensure_host_pool,
)
from .ex_client import TdxExRemoteClient, TdxExRemoteClientError

__all__ = [
    "TdxRemoteClient",
    "TdxRemoteClientError",
    "get_security_bars_tdx_remote",
    "get_index_bars_tdx_remote",
    "get_auto_routed_bars_tdx_remote",
    "sync_hosts_from_connect_cfg_if_needed",
    "ensure_host_pool",
    "TdxExRemoteClient",
    "TdxExRemoteClientError",
]
