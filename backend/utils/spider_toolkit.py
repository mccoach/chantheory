# backend/utils/spider_toolkit.py
# ==============================
# V4.0
# 说明：爬虫工具包（通用参数选择器 + 动态生成器 + JSON/JSONP 脱壳）
# 职责：
#   1. 从 settings 池中随机选择通用参数（UA/Language/Connection）
#   2. 生成动态参数（JSONP 回调名/时间戳/Nonce）
#   3. 根据 User-Agent 生成匹配的 sec-ch-ua 头
#   4. 提供 **通用的 JSON/JSONP/包裹 JSON 脱壳工具 strip_jsonp(text)**：
#        - 忽略圆括号及 callback 名
#        - 从左到右扫描，找到第一个“括号深度从 0 进入、再回到 0”的最外层 {} 或 []
#        - 把这段子串当作纯 JSON 解析
# ==============================

from __future__ import annotations

import time
import random
import json
import re
from typing import Dict, Any, Optional

from backend.settings import spider_config
from backend.utils.logger import get_logger

# 新增：XLSX 解析依赖（复用全局 pandas，无额外第三方）
import pandas as pd
from io import BytesIO

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
    return spider_config.accept_languages[0] if spider_config.accept_languages else "zh-CN,zh;q=0.9"


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
# JSON / JSONP / 包裹 JSON 解析器（零 callback 版）
# ==============================================================================

def strip_jsonp(text: str) -> Dict[str, Any]:
    """
    从任意“可能带 JSONP 外壳 / 额外噪声”的响应文本中提取**首个完整 JSON 对象或数组**并解析。

    设计原则：
      1. **忽略圆括号与 callback 名**，不再依赖任何回调函数名；
      2. 从左向右扫描，寻找第一个 '{' 或 '['，记为起点；
      3. 以此为起点，记录括号深度：
           - 碰到同类开括号（{ 或 [） depth += 1
           - 碰到对应闭括号（} 或 ]） depth -= 1
           - 进入字符串（"..."）期间忽略括号，并处理反斜杠转义；
         当 depth 从 1 降回 0 的那个闭括号位置，即为**最外层 JSON 的结尾**；
      4. 提取 start..end 这段子串，直接 json.loads。

    适用场景：
      - quote_jp123({...});
      - callback&&callback({...});
      - xxx({...})/**/;
      - 甚至纯 JSON（直接以 { 或 [ 开头）；
      - 只要响应中“确实存在一段合法的 JSON 对象/数组”，就一定能找到。

    若：
      - 文本中完全没有 '{' 或 '['；
      - 或括号不成对 / 嵌套不平衡；
      - 或提取出的子串不是合法 JSON；
    则抛出 ValueError 交由调用方处理。
    """
    s = (text or "")
    if not s:
        raise ValueError("strip_jsonp: empty response")

    # 1) 找到第一个 '{' 或 '['
    start = None
    open_ch = None
    close_ch = None

    for i, ch in enumerate(s):
        if ch == '{' or ch == '[':
            start = i
            open_ch = ch
            close_ch = '}' if ch == '{' else ']'
            break

    if start is None:
        raise ValueError("strip_jsonp: no JSON object/array found")

    # 2) 从 start 起，按 JSON 语法跟踪括号深度与字符串状态
    depth = 0
    in_string = False
    escape = False
    end = None

    for idx in range(start, len(s)):
        ch = s[idx]

        if in_string:
            # 处理字符串内部
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            # 字符串内的所有括号一律忽略
            continue

        # 不在字符串中
        if ch == '"':
            in_string = True
            continue

        # 统计括号深度
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                end = idx
                break

    if end is None or depth != 0:
        raise ValueError("strip_jsonp: unbalanced JSON braces/brackets")

    json_str = s[start:end + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # 这里不做自动修补，由调用方决定如何处理
        raise ValueError(f"strip_jsonp: json decode error: {e}") from e


# ==============================================================================
# XLSX 解析工具（通用）
# ==============================================================================

def xlsx_bytes_to_json_records(
    xlsx_bytes: bytes,
    sheet: int | str = 0
) -> list[dict[str, Any]]:
    """
    将 XLSX 二进制内容解析为“纯净 JSON”记录列表（通用工具）。

    设计原则：
      1. 不做业务字段命名或含义判断，仅负责结构化解析。
      2. 统一将缺失值 / NaN 转换为 None，确保后续 json.dumps 时无 NaN。

    Args:
        xlsx_bytes: HTTP 响应体中的 XLSX 二进制内容（resp.content）。
        sheet: 要解析的工作表，既可为索引（0 表示第一个表），也可为名称。

    Returns:
        list[dict[str, Any]]: 每一行对应一条记录，键为列名（字符串），值为基础类型或 None。

    Raises:
        Exception: 当底层解析失败（文件损坏 / 不是合法 XLSX 等）时抛出原始异常。
    """
    if not xlsx_bytes:
        _LOG.warning("[XLSX解析] 输入为空字节串")
        return []

    try:
        # 使用 pandas.read_excel 做最小职责解析
        df = pd.read_excel(BytesIO(xlsx_bytes), sheet_name=sheet, dtype=object)
    except Exception as e:
        _LOG.error(
            "[XLSX解析] 读取失败",
            extra={"error": str(e)},
        )
        # 直接抛出，让调用方感知失败并记录更上层日志
        raise

    # 将 NaN / NaT 等缺失值统一转换为 None，保证后续 JSON 纯净
    df = df.where(pd.notna(df), None)

    records: list[dict[str, Any]] = df.to_dict(orient="records")

    _LOG.debug(
        "[XLSX解析] 解析成功",
        extra={
            "rows": len(records),
            "columns": list(df.columns),
        },
    )

    return records


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
