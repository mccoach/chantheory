# backend/utils/spider_toolkit.py
# ==============================
# V3.0
# 说明：爬虫工具包（通用参数选择器 + 动态生成器）
# 职责：
#   1. 从 settings 池中随机选择通用参数（UA/Language/Connection）
#   2. 生成动态参数（JSONP 回调名/时间戳/Nonce）
#   3. 根据 User-Agent 生成匹配的 sec-ch-ua 头
#   4. 提供 JSONP 解析工具
# 设计原则：
#   - 纯函数，无状态
#   - 不管理业务逻辑参数（Referer/sqlId 等）
# ==============================

from __future__ import annotations

import time
import random
import json
import re
from typing import Dict, Any, Optional

from backend.settings import spider_config
from backend.utils.logger import get_logger

_LOG = get_logger("spider_toolkit")

# ==============================================================================
# 核心工具：通用参数选择器
# ==============================================================================


def pick_user_agent() -> str:
    """
    从 User-Agent 池中随机选择一个
    
    Returns:
        str: User-Agent 字符串
    
    Examples:
        >>> ua = pick_user_agent()
        >>> 'Chrome/140.0.0.0' in ua
        True
    """
    if spider_config.enable_header_randomization and spider_config.user_agents:
        return random.choice(spider_config.user_agents)
    return spider_config.user_agents[0] if spider_config.user_agents else ""


def pick_accept_language() -> str:
    """
    从 Accept-Language 池中随机选择一个
    
    Returns:
        str: Accept-Language 字符串
    
    Examples:
        >>> lang = pick_accept_language()
        >>> 'zh-CN' in lang
        True
    """
    if spider_config.enable_header_randomization and spider_config.accept_languages:
        return random.choice(spider_config.accept_languages)
    return spider_config.accept_languages[
        0] if spider_config.accept_languages else "zh-CN,zh;q=0.9"


def pick_connection() -> str:
    """
    从 Connection 池中随机选择（95% 权重 keep-alive）
    
    Returns:
        str: Connection 类型
    
    Examples:
        >>> conn = pick_connection()
        >>> conn in ['keep-alive', 'close']
        True
    """
    if not spider_config.enable_header_randomization:
        return "keep-alive"

    # 95% 概率使用 keep-alive（符合真实行为分布）
    return "keep-alive" if random.random() < 0.95 else "close"


# ==============================================================================
# 动态生成器
# ==============================================================================


def generate_jsonp_callback(prefix: str = "jsonpCallback") -> str:
    """
    生成唯一的 JSONP 回调名（模拟官网格式）
    
    格式：{prefix}{8位随机数}
    
    官网规律（基于实测样本）：
      - jsonpCallback21630768
      - jsonpCallback96438358
      - jsonpCallback30418896
      - 规律：固定前缀 + 8位纯随机数（10000000 ~ 99999999）
    
    Args:
        prefix: 回调名前缀（默认 'jsonpCallback' 与官网保持一致）
    
    Returns:
        str: 唯一回调名
    
    Examples:
        >>> cb = generate_jsonp_callback()
        >>> cb.startswith('jsonpCallback') and len(cb) == 24
        True
    """
    # 生成 8 位随机数（10000000 ~ 99999999）
    random_suffix = random.randint(10000000, 99999999)

    return f"{prefix}{random_suffix}"


def generate_cache_buster() -> str:
    """
    生成防缓存时间戳（毫秒）
    
    官网格式：13位毫秒时间戳
    
    Returns:
        str: 毫秒时间戳字符串
    
    Examples:
        >>> ts = generate_cache_buster()
        >>> len(ts) == 13
        True
    """
    return str(int(time.time() * 1000))


def generate_nonce(length: int = 16) -> str:
    """
    生成随机 Nonce（用于签名/防重放）
    
    Args:
        length: 字符串长度（默认16）
    
    Returns:
        str: 十六进制随机字符串
    
    Examples:
        >>> nonce = generate_nonce(16)
        >>> len(nonce) == 16
        True
    """
    import secrets
    return secrets.token_hex(length // 2)


# ==============================================================================
# 高级功能：sec-ch-ua 头生成器
# ==============================================================================
def generate_sec_ch_ua(user_agent: str) -> str:
    """
    根据 User-Agent 生成匹配的 sec-ch-ua 头
    
    规则（基于官网实测）：
      - Edge 140: "Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"
      - Chrome 137: "Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"
      - 版本号必须与 User-Agent 严格匹配
    
    Args:
        user_agent: User-Agent 字符串
    
    Returns:
        str: sec-ch-ua 字符串
    
    Examples:
        >>> ua = "Mozilla/5.0 (...) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
        >>> ch_ua = generate_sec_ch_ua(ua)
        >>> 'v="140"' in ch_ua
        True
    """
    # 提取版本号
    chrome_match = re.search(r'Chrome/(\d+)', user_agent)
    edge_match = re.search(r'Edg/(\d+)', user_agent)
    firefox_match = re.search(r'Firefox/(\d+)', user_agent)

    # Edge 浏览器
    if edge_match:
        version = edge_match.group(1)
        return f'"Chromium";v="{version}", "Not=A?Brand";v="24", "Microsoft Edge";v="{version}"'

    # Chrome 浏览器
    elif chrome_match and not edge_match:
        version = chrome_match.group(1)
        # Chrome 的 Not Brand 字符串有多种变体
        not_brand = random.choice(
            ['"Not/A)Brand"', '"Not_A Brand"', '"Not;A=Brand"'])
        return f'"Google Chrome";v="{version}", "Chromium";v="{version}", {not_brand};v="24"'

    # Firefox（不发送 sec-ch-ua）
    elif firefox_match:
        return ""

    # 降级：使用通用值
    else:
        return '"Chromium";v="140", "Not=A?Brand";v="24"'


# ==============================================================================
# JSONP 解析器
# ==============================================================================


def strip_jsonp(text: str,
                callback_name: Optional[str] = None) -> Dict[str, Any]:
    """
    将 JSONP 文本解析为 Python dict
    
    Args:
        text: JSONP 响应文本
        callback_name: 已知回调名（可选，提升解析速度）
    
    Returns:
        Dict: 解析后的 JSON 对象
    
    Raises:
        ValueError: 解析失败时
    
    Examples:
        >>> data = strip_jsonp('jsonpCallback123({"ok": true})', 'jsonpCallback123')
        >>> data['ok']
        True
    """
    s = (text or "").strip()
    if not s:
        raise ValueError("Empty response when stripping JSONP")

    # 快速路径：已知回调名
    if callback_name:
        prefix = f"{callback_name}("
        suffix = ");"
        if s.startswith(prefix):
            # 兼容两种结尾：); 或 )
            if s.endswith(suffix):
                json_str = s[len(prefix):-len(suffix)]
            elif s.endswith(")"):
                json_str = s[len(prefix):-1]
            else:
                json_str = s[len(prefix):]

            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass  # 降级到标准路径

    # 标准路径：查找括号
    try:
        l = s.index("(")
        r = s.rfind(")")
        if l >= 0 and r > l:
            json_str = s[l + 1:r]
        else:
            json_str = s
    except ValueError:
        # 降级：当作纯 JSON 解析
        _LOG.debug("[JSONP解析] 响应非标准JSONP格式，降级为纯JSON解析",
                   extra={"response_preview": s[:200]})
        json_str = s

    return json.loads(json_str)


# ==============================================================================
# 延迟控制
# ==============================================================================


async def apply_random_delay() -> None:
    """
    应用随机延迟（模拟人工操作间隔）
    
    规则：
      - 仅在 spider_config.enable_random_delay=True 时生效
      - 延迟范围来自 spider_config.random_delay_range
    
    用途：
      - 在连续请求间插入随机间隔
      - 降低被识别为机器行为的概率
    """
    if not spider_config.enable_random_delay:
        return

    import asyncio

    min_delay, max_delay = spider_config.random_delay_range
    delay = random.uniform(min_delay, max_delay)

    _LOG.debug(f"[反爬延迟] 等待 {delay:.2f}秒")
    await asyncio.sleep(delay)
