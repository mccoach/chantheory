# backend/datasource/providers/szse_adapter/profile_szse.py
# ==============================
# 深交所个股 / 基金档案适配器（Company & Fund Profile · SZSE V1.0）
#
# 说明：
#   - 本文件只封装 “深交所官网 JSON 接口” 的 HTTP 调用与 JSON 解析，
#   - 对上层暴露 async 函数，返回 pandas.DataFrame，不做字段重命名或业务标准化。
#
# 已实现接口：
#   1) 股票相关
#      1.1 公司基本信息（公司概况 - 公司总览）
#          - URL: https://www.szse.cn/api/report/index/companyGeneralization
#          - 参数: secCode=000001
#
# 设计原则：
#   - 与 sse_adapter.profile 风格保持一致：
#       * 使用 spider_toolkit 选择 UA / Accept-Language / Connection
#       * 使用 async_retry_call 做指数退避重试
#       * 使用 limit_async_network_io 做全局异步限流
#   - 单一职责：
#       * 不做字段语义解释与标准化，统一交由 normalizer / 上层业务处理
#       * 只在无数据行或 code != "0" 时返回空 DataFrame，并打日志；不做“结构变就炸”的强校验
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional, List

import pandas as pd
import httpx

from backend.utils.async_limiter import limit_async_network_io
from backend.utils.async_retry import async_retry_call
from backend.utils.logger import get_logger

from backend.utils.spider_toolkit import (
    pick_user_agent,
    pick_accept_language,
    pick_connection,
    generate_sec_ch_ua,
)

_LOG = get_logger("szse_adapter.profile")

BASE_URL = "https://www.szse.cn/api/report/index/companyGeneralization"

# ==============================================================================
# 1. 深交所股票档案
# ==============================================================================

# 1.1 深交所股票档案，个股档案基本信息（公司概况）


@limit_async_network_io
async def get_stock_profile_basic_sz_szse(sec_code: str) -> pd.DataFrame:
    """
    [公司基本信息] 从深交所官网获取单家公司概况（JSON 接口 · 公司总览）

    数据源：
      - 页面示例：
          https://www.szse.cn/certificate/individual/index.html?code=000001
      - 接口地址：
          https://www.szse.cn/api/report/index/companyGeneralization

    抓包参数示例（000001 · 平安银行）：

      请求：
        GET /api/report/index/companyGeneralization
          ?random=0.8056412899673531
          &secCode=000001
          HTTP/1.1
        Host: www.szse.cn
        Referer: https://www.szse.cn/certificate/individual/index.html?code=000001
        Accept: application/json, text/javascript, */*; q=0.01
        X-Requested-With: XMLHttpRequest
        X-Request-Type: ajax
        ...

      响应 JSON 示例（字段并不保证完整，仅列出关键结构）：

        {
          "code": "0",
          "data": {
            "gsqc": "平安银行股份有限公司",        # 公司全称
            "ywqc": "Ping An Bank Co., Ltd.",       # 英文全称
            "zcdz": "广东省深圳市罗湖区深南东路5047号",  # 注册地址

            "agdm": "000001",                       # A股代码
            "agjc": "平安银行",                      # A股扩位证券简称
            "agssrq": "1991-04-03",                 # A股上市日期
            "agzgb": "1,940,592",                   # A股总股本（单位：万股，带千分位分隔符）
            "agltgb": "1,940,560",                  # A股流通股本（单位：万股，带千分位分隔符）

            "bgdm": "",                             # B股代码（如有）
            "bgjc": "",                             # B股扩位证券简称
            "bgssrq": "",                           # B股上市日期
            "bgzgb": "0",                           # B股总股本（万股）
            "bgltgb": "0",                          # B股流通股本（万股）

            "dldq": "华南",                         # 地理大区
            "sheng": "广东",                        # 省份
            "shi": "深圳市",                        # 城市
            "sshymc": "金融业",                     # 所属行业名称

            "http": "bank.pingan.com",             # 公司网址

            "ylbz": "",                             # 未盈利标志（空/“-”等）
            "sfjybjqcy": "",                        # 是否具有表决权差异安排
            "gskzjglx": "",                         # 公司控制架构类型（协议控制架构 等）

            "agdjc": "平安银行",                     # A股证券简称
            "bgdjc": null                           # B股证券简称（可能为 null）
          },
          "plate": "XA",
          "message": "成功",
          "cols": {
            "bgdm": "B股代码",
            "gskzjglx": "具有协议控制架构",
            "agdm": "A股代码",
            "agssrq": "A股上市日期",
            "bgzgb": "B股总股本",
            "sshymc": "所属行业",
            "sfjybjqcy": "具有表决权差异安排",
            "zcdz": "注册地址",
            "ywqc": "英文全称",
            "agzgb": "A股总股本",
            "sheng": "省份",
            "agltgb": "A股流通股本",
            "bgdjc": "B股证券简称",
            "gsqc": "公司全称",
            "bgjc": "B股扩位证券简称",
            "agdjc": "A股证券简称",
            "bgltgb": "B股流通股本",
            "agjc": "A股扩位证券简称",
            "ylbz": "未盈利",
            "shi": "城市",
            "bgssrq": "B股上市日期",
            "http": "公司网址",
            "dldq": "地区"
          }
        }

    行为说明：
      - 本函数仅负责：
          * 构造请求参数与请求头（基于 spider_toolkit 通用池）
          * 发起 HTTP 请求（带 async_retry_call 重试）
          * 使用 resp.json() 解析 JSON 文本
          * 从返回的 data 字段构造 DataFrame（单行，公司概况）
      - 不做字段重命名、空值处理或单位换算，保持字段名与原 JSON 完全一致：
          * 即 DataFrame.columns == data.keys()，如 ['gsqc','ywqc','zcdz',...]
          * 上层 normalizer/业务层可根据需要进一步标准化（如拆分地区、转为 YYYYMMDD、换算股本单位等）

    Args:
        sec_code: 证券代码（6 位数字，如 "000001"）

    Returns:
        pandas.DataFrame:
          - 正常情况：一行记录（该证券的公司概况）
          - 若 code != "0" 或无 data 字段或异常：空 DataFrame
    """
    sec_code_clean = str(sec_code or "").strip()

    # ===== 步骤1：构造查询参数（含 random 防缓存）=====
    import random as _random

    params: Dict[str, str] = {
        "secCode": sec_code_clean,
        "random": str(_random.random()),  # 深交所常用 0~1 浮点随机数作为防缓存参数
    }

    # ===== 步骤2：生成通用请求头（从配置池随机选择）=====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    # 深交所实际抓包中包含 X-Requested-With / X-Request-Type 等 Ajax 头，
    # 这里尽量与官网保持一致，以降低被识别为爬虫的概率。
    headers: Dict[str, str] = {
        # 个性化头（接口专属）
        "Referer":
        f"https://www.szse.cn/certificate/individual/index.html?code={sec_code_clean}",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/json",
        "Host": "www.szse.cn",

        # Ajax 相关头（与抓包保持一致）
        "X-Requested-With": "XMLHttpRequest",
        "X-Request-Type": "ajax",

        # 现代浏览器安全头
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",

        # 通用头（从池中随机）
        "User-Agent": user_agent,
        "Accept-Language": accept_language,
        "Connection": connection,

        # 压缩支持
        "Accept-Encoding": "gzip, deflate",
    }

    # 补充 sec-ch-ua 系列（仅 Chrome/Edge 携带）
    if sec_ch_ua:
        headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"'

    _LOG.info(
        "[深交所] 公司概况开始拉取",
        extra={
            "sec_code": sec_code_clean,
            "url": BASE_URL,
            "params": params,
        },
    )

    # ===== 步骤3：执行请求（带统一重试）=====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(BASE_URL, params=params, headers=headers)
            resp.raise_for_status()

            try:
                data: Dict[str, Any] = resp.json()
            except Exception as e:
                _LOG.error(
                    "[深交所] 公司概况 JSON 解析失败",
                    extra={
                        "sec_code": sec_code_clean,
                        "error": str(e),
                        "text_preview": resp.text[:200],
                    },
                )
                return pd.DataFrame()

            # 基础结构校验：要求 code == "0" 且有 data 字段
            code = str(data.get("code", "")).strip()
            payload = data.get("data")

            if code != "0" or not isinstance(payload, dict) or not payload:
                _LOG.warning(
                    "[深交所] 公司概况无有效数据",
                    extra={
                        "sec_code": sec_code_clean,
                        "code": code,
                        "has_data": isinstance(payload, dict),
                    },
                )
                return pd.DataFrame()

            # 将 data 字段直接转为单行 DataFrame，保持原始字段名
            df = pd.DataFrame([payload])

            _LOG.info(
                "[深交所] 公司概况获取成功 1 条记录",
                extra={
                    "sec_code": sec_code_clean,
                    "columns": list(df.columns),
                    "user_agent_version": (
                        user_agent.split("Chrome/")[1].split()[0]
                        if "Chrome/" in user_agent else "unknown"
                    ),
                },
            )

            return df

    df = await async_retry_call(_do_request)

    return df if df is not None else pd.DataFrame()


# 1.2 深交所股票档案，实时状态信息（关键指标）

@limit_async_network_io
async def get_stock_profile_realtime_sz_szse(sec_code: str) -> pd.DataFrame:
    """
    [公司实时关键指标] 从深交所官网获取单只股票的实时/最近关键指标概览
    （JSON 接口 · stockKeyIndexGeneralization）

    数据源：
      - 页面示例：
          https://www.szse.cn/certificate/individual/index.html?code=000001
      - 接口地址：
          https://www.szse.cn/api/report/index/stockKeyIndexGeneralization

    抓包参数示例（000001 · 平安银行）：

      请求：
        GET /api/report/index/stockKeyIndexGeneralization
          ?random=0.8756782340319127
          &secCode=000001
          HTTP/1.1
        Host: www.szse.cn
        Referer: https://www.szse.cn/certificate/individual/index.html?code=000001
        Accept: application/json, text/javascript, */*; q=0.01
        X-Requested-With: XMLHttpRequest
        X-Request-Type: ajax
        ...

      响应 JSON 示例（字段并不保证完整，仅列出关键结构）：

        {
          "code": "0",
          "data": [
            {
              "now_cjbs": "0.88",      # 当日成交笔数（亿笔）
              "now_cjje": "10.28",     # 当日成交金额（亿元）
              "now_syl": "5.41",       # 当日市盈率（倍）
              "now_hsl": "0.46",       # 当日换手率（%）
              "now_sjzz": "2,253.03",  # 当日实际总市值（亿元）
              "now_ltsz": "2,252.99",  # 当日流通市值（亿元）
              "now_zgb": "194.06",     # 当日总股本（亿股）
              "now_ltgb": "194.06"     # 当日流通股本（亿股）
            },
            {
              "last_cjbs": "1.01",      # 前日成交笔数（亿笔）
              "last_cjje": "11.78",     # 前日成交金额（亿元）
              "last_syl": "5.45",       # 前日市盈率（倍）
              "last_hsl": "0.52",       # 前日换手率（%）
              "last_sjzz": "2,272.43",  # 前日实际总市值（亿元）
              "last_ltsz": "2,272.40",  # 前日流通市值（亿元）
              "last_zgb": "194.06",     # 前日总股本（亿股）
              "last_ltgb": "194.06"     # 前日流通股本（亿股）
            },
            {
              "change_cjbs": "-0.13",   # 当日与前日成交笔数差值（亿笔）
              "change_cjje": "-1.50",   # 当日与前日成交金额差值（亿元）
              "change_syl": "-0.04",    # 当日与前日市盈率差值（倍）
              "change_hsl": "-0.06",    # 当日与前日换手率差值（%）
              "change_sjzz": "-19.41",  # 当日与前日实际总市值差值（亿元）
              "change_ltsz": "-19.41",  # 当日与前日流通市值差值（亿元）
              "change_zgb": "0",        # 当日与前日总股本差值（亿股）
              "change_ltgb": "0"        # 当日与前日流通股本差值（亿股）
            }
          ],
          "message": "成功",
          "lastDate": "2025-11-28 00:00:00.0"
        }

    行为说明：
      - 本函数仅负责：
          * 构造请求参数与请求头（基于 spider_toolkit 通用池）
          * 发起 HTTP 请求（带 async_retry_call 重试）
          * 使用 resp.json() 解析 JSON 文本
          * 直接将 data 列表转为 DataFrame（3 行：now / last / change），不做字段语义级处理
      - 不做字段重命名、空值处理或单位换算：
          * DataFrame 的列名完全等于 JSON 对象中的 key，如 'now_cjbs','last_cjbs','change_cjbs' 等
          * 上层 normalizer/业务层可自行根据前缀拆分“当前/上期/变动”三类指标

    Args:
        sec_code: 证券代码（6 位数字，如 "000001"）

    Returns:
        pandas.DataFrame:
          - 正常情况：多行记录（通常为 3 行：now/last/change）
          - 若 code != "0" 或 data 不是非空列表：空 DataFrame
    """
    sec_code_clean = str(sec_code or "").strip()

    # ===== 1. 构造查询参数 =====
    import random as _random

    params: Dict[str, str] = {
        "secCode": sec_code_clean,
        "random": str(_random.random()),
    }

    # ===== 2. 生成通用请求头 =====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers: Dict[str, str] = {
        "Referer":
        f"https://www.szse.cn/certificate/individual/index.html?code={sec_code_clean}",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/json",
        "Host": "www.szse.cn",

        # Ajax 头（与抓包一致）
        "X-Requested-With": "XMLHttpRequest",
        "X-Request-Type": "ajax",

        # 现代浏览器安全头
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",

        # 通用头
        "User-Agent": user_agent,
        "Accept-Language": accept_language,
        "Connection": connection,

        # 压缩
        "Accept-Encoding": "gzip, deflate",
    }

    if sec_ch_ua:
        headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"'

    _LOG.info(
        "[深交所] 公司实时关键指标开始拉取",
        extra={
            "sec_code": sec_code_clean,
            "url": "https://www.szse.cn/api/report/index/stockKeyIndexGeneralization",
            "params": params,
        },
    )

    # ===== 3. 执行请求（统一重试）=====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://www.szse.cn/api/report/index/stockKeyIndexGeneralization",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()

            try:
                data: Dict[str, Any] = resp.json()
            except Exception as e:
                _LOG.error(
                    "[深交所] 公司实时关键指标 JSON 解析失败",
                    extra={
                        "sec_code": sec_code_clean,
                        "error": str(e),
                        "text_preview": resp.text[:200],
                    },
                )
                return pd.DataFrame()

            code = str(data.get("code", "")).strip()
            payload = data.get("data")

            # 要求 code == "0" 且 data 为非空列表
            if code != "0" or not isinstance(payload, list) or not payload:
                _LOG.warning(
                    "[深交所] 公司实时关键指标无有效数据",
                    extra={
                        "sec_code": sec_code_clean,
                        "code": code,
                        "data_type": type(payload).__name__,
                        "data_len": len(payload) if isinstance(payload, list) else None,
                    },
                )
                return pd.DataFrame()

            df = pd.DataFrame(payload)

            _LOG.info(
                "[深交所] 公司实时关键指标获取成功 %d 条记录",
                len(df),
                extra={
                    "sec_code":
                    sec_code_clean,
                    "columns":
                    list(df.columns),
                    "user_agent_version":
                    (user_agent.split("Chrome/")[1].split()[0]
                     if "Chrome/" in user_agent else "unknown"),
                },
            )

            return df

    df = await async_retry_call(_do_request)

    return df if df is not None else pd.DataFrame()