# backend/services/__init__.py
# ==============================
# services 模块导出接口
#
# 当前导出：
#   - normalizer
#   - indicators
#   - market
#
# 说明：
#   - local_import 已采用独立包路径按需引用：
#       backend.services.local_import.*
#   - 这里不强行做大而全导出，避免无意义耦合
# ==============================

from backend.services import normalizer
from backend.services import indicators
from backend.services import market

__all__ = [
    "normalizer",
    "indicators",
    "market",
]
