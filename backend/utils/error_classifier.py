# backend/utils/error_classifier.py
# ==============================
# 说明：异常分类器 - 精确识别数据获取失败的原因
# - 职责：
#   1. 区分反爬虫封禁、网络错误、参数错误、空数据等不同失败类型
#   2. 为每种错误类型定义统一的错误码和处理建议
# ==============================

from __future__ import annotations
from typing import Tuple, Optional
import pandas as pd

try:
    import httpx
except ImportError:
    httpx = None

class ErrorType:
    """错误类型枚举。"""
    ANTISPIDER = "antispider"          # 反爬虫封禁
    NETWORK_TIMEOUT = "network_timeout"  # 网络超时
    NETWORK_ERROR = "network_error"    # 其他网络错误
    INVALID_PARAMS = "invalid_params"  # 参数错误
    EMPTY_RESPONSE = "empty_response"  # 返回空数据
    API_CHANGED = "api_changed"        # API变更/下线
    UNKNOWN = "unknown"                # 未知错误

def classify_fetch_error(
    exception: Optional[Exception],
    raw_data: Optional[pd.DataFrame]
) -> Tuple[str, str, str]:
    """
    分类数据获取错误。
    
    Args:
        exception: 捕获的异常对象（如果有）
        raw_data: 返回的原始数据（如果有）
    
    Returns:
        Tuple[str, str, str]: (错误类型, 错误消息, 处理建议)
    """
    # 情况1：没有异常，但返回空数据
    if exception is None:
        if raw_data is None or (isinstance(raw_data, pd.DataFrame) and raw_data.empty):
            return (
                ErrorType.EMPTY_RESPONSE,
                "数据源返回空数据（无异常）",
                "可能原因：参数超出数据范围、该标的无此频率数据。建议：检查参数或切换数据源。"
            )
        else:
            # 有数据且无异常，这不是错误
            return ("success", "成功", "")
    
    # 情况2：有异常，开始分类
    error_msg = str(exception)
    error_type_name = type(exception).__name__
    
    # 2.1 反爬虫特征识别（最高优先级）
    antispider_keywords = [
        "RemoteProtocolError",           # httpx: 远程主机关闭连接
        "Connection reset by peer",      # 连接被重置
        "403",                           # HTTP 403 Forbidden
        "Too Many Requests",             # HTTP 429
        "Captcha",                       # 验证码
        "Access Denied",                 # 访问被拒绝
        "请降低访问频率",                  # 中文提示
        "操作过于频繁",
    ]
    
    if any(keyword in error_msg or keyword in error_type_name for keyword in antispider_keywords):
        return (
            ErrorType.ANTISPIDER,
            f"疑似触发反爬虫机制: {error_type_name} - {error_msg}",
            "紧急建议：立即停止该数据源的调用，切换到备用源，并检查全局限流器配置。"
        )
    
    # 2.2 网络超时
    timeout_keywords = ["timeout", "timed out", "TimeoutError"]
    if any(keyword.lower() in error_msg.lower() for keyword in timeout_keywords):
        return (
            ErrorType.NETWORK_TIMEOUT,
            f"网络请求超时: {error_msg}",
            "建议：重试或切换到备用数据源。如果频繁发生，检查网络连接。"
        )
    
    # 2.3 其他网络错误
    network_keywords = ["ConnectionError", "ConnectError", "NetworkError", "SSLError"]
    if any(keyword in error_type_name for keyword in network_keywords):
        return (
            ErrorType.NETWORK_ERROR,
            f"网络连接错误: {error_type_name} - {error_msg}",
            "建议：检查网络连接或切换到备用数据源。"
        )
    
    # 2.4 参数错误
    param_keywords = ["Invalid", "ValueError", "KeyError", "参数", "不支持"]
    if any(keyword in error_msg or keyword in error_type_name for keyword in param_keywords):
        return (
            ErrorType.INVALID_PARAMS,
            f"参数错误: {error_type_name} - {error_msg}",
            "建议：检查传入参数的格式和范围，或查阅数据源API文档确认参数规范。"
        )
    
    # 2.5 API变更/下线
    api_change_keywords = ["AttributeError", "not found", "deprecated", "已废弃"]
    if any(keyword in error_msg or keyword in error_type_name for keyword in api_change_keywords):
        return (
            ErrorType.API_CHANGED,
            f"API可能已变更或下线: {error_type_name} - {error_msg}",
            "严重警告：该数据源的API可能已失效，建议立即切换到备用源，并检查akshare库是否需要更新。"
        )
    
    # 2.6 未知错误
    return (
        ErrorType.UNKNOWN,
        f"未分类错误: {error_type_name} - {error_msg}",
        "建议：查看完整的异常堆栈，必要时提交issue到akshare项目。"
    )
