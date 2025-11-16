# backend/datasource/__init__.py
# ==============================
# datasource 模块导出接口
# ==============================

from backend.datasource import dispatcher
from backend.datasource.registry import (
    get_methods_for_category,
    find_method_by_id,
    METHOD_CATALOG,
    MethodDescriptor
)

__all__ = [
    'dispatcher',
    'get_methods_for_category',
    'find_method_by_id',
    'METHOD_CATALOG',
    'MethodDescriptor'
]