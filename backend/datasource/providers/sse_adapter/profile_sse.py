# backend/datasource/providers/sse_adapter/profile_sse.py
# ==============================
# 上交所个股 / 基金档案适配器（Company & Fund Profile · V2.0）
#
# 说明：
#   - 本文件只封装 “上交所官网 JSONP 接口” 的 HTTP 调用与 JSONP 解包，
#   - 对上层暴露 async 函数，返回 pandas.DataFrame，不做字段重命名或业务标准化。
#
# 已实现接口：
#   1) 股票相关
#      1.1 公司基本信息（公司概况）
#          - URL: https://query.sse.com.cn/commonQuery.do
#          - sqlId: COMMON_SSE_CP_GPJCTPZ_GPLB_GPGK_GSGK_C
#          - 参数: COMPANY_CODE=600000
#
#      1.2 成交统计（市值情况）
#          - URL: https://query.sse.com.cn/commonQuery.do
#          - sqlId:
#               * 日度: COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C
#               * 月度: COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_YDGK_C
#               * 年度: COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_NDGK_C
#          - 参数: SEC_CODE=600006, TX_DATE / TX_DATE_MON / TX_DATE_YEAR
#
#      1.3 股本结构（股本情况）
#          - URL: https://query.sse.com.cn/commonQuery.do
#          - sqlId: COMMON_SSE_CP_GPJCTPZ_GPLB_GPGK_GBJG_C
#          - 参数: COMPANY_CODE=600000
#
#   2) 基金相关（ETF/场内基金）
#      2.1 基金基本信息（FUND_LIST 精确过滤）
#          - URL: https://query.sse.com.cn/commonSoaQuery.do
#          - sqlId: FUND_LIST
#          - 参数: fundCode=510300
#
#      2.2 成交统计（市值情况）
#          - URL: https://query.sse.com.cn/commonQuery.do
#          - sqlId 同股票成交统计：
#               * 日度: COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C
#               * 月度: COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_YDGK_C
#               * 年度: COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_NDGK_C
#          - 参数: SEC_CODE=510300, TX_DATE / TX_DATE_MON / TX_DATE_YEAR
#
#      2.3 基金规模（份额情况）
#          - URL: https://query.sse.com.cn/commonQuery.do
#          - sqlId:
#               * 最近 N 日时间序列: COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_MOREN_L
#               * 指定日期精确查询:   COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_SEARCH_L
#          - 参数: SEC_CODE=510300, STAT_DATE=YYYY-MM-DD
#
# 设计原则：
#   - 与 listing.py 风格保持一致：
#       * 使用 spider_toolkit 选择 UA / Accept-Language / Connection
#       * 使用 generate_jsonp_callback + generate_cache_buster 生成 jsonCallBack / _
#       * 使用 strip_jsonp 解析 JSONP 文本
#       * 使用 async_retry_call 做指数退避重试
#       * 使用 limit_async_network_io 做全局异步限流
#   - 单一职责：
#       * 不做字段语义解释与标准化，统一交由 normalizer 层处理
#       * 仅在无数据行时返回空 DataFrame，并打日志；不做“结构变就炸”的强校验
# ==============================

from __future__ import annotations

from typing import Dict, Any, List, Optional

import pandas as pd
import httpx

from backend.utils.async_limiter import limit_async_network_io
from backend.utils.async_retry import async_retry_call
from backend.utils.logger import get_logger
from backend.utils.time import format_date_value

from backend.utils.spider_toolkit import (
    pick_user_agent,
    pick_accept_language,
    pick_connection,
    generate_jsonp_callback,
    generate_cache_buster,
    generate_sec_ch_ua,
    strip_jsonp,
)

_LOG = get_logger("sse_adapter")

BASE_URL = "https://query.sse.com.cn/commonQuery.do"

# ==============================================================================
# 1. 上交所股票档案
# ==============================================================================

# 1.1 上交所股票档案，个股档案基本信息（公司概况）


@limit_async_network_io
async def get_stock_profile_basic_sh_sse(company_code: str) -> pd.DataFrame:
    """
    [公司基本信息] 从上交所官网获取单家公司概况（JSONP 接口 · 公司概况）

    数据源：
      - 页面示例：
          https://www.sse.com.cn/
      - 接口地址：
          https://query.sse.com.cn/commonQuery.do

    抓包参数示例（600000）：
      - sqlId:
          COMMON_SSE_CP_GPJCTPZ_GPLB_GPGK_GSGK_C
      - isPagination: false
      - COMPANY_CODE: 600000
      - jsonCallBack: jsonpCallback28259120
      - _: 1763952355917

    请求方法：
      - GET

    关键业务参数：
      - COMPANY_CODE: 公司代码（通常等于 A 股代码，如 "600000"）

    返回数据结构（result[0] 示例，字段非完整，仅列出关键项，实际以接口为准）：

        {
            "A_LIST_DATE": "19991110",                 # A股上市日期 (YYYYMMDD)
            "COMPANY_CODE": "600000",                  # 公司代码
            "A_STOCK_CODE": "600000",                  # A股代码
            "COMPANY_ABBR": "浦发银行",                 # 公司简称
            "FULL_NAME": "上海浦东发展银行股份有限公司", # 公司全称（中文）
            "FULL_NAME_EN": "Shanghai Pudong Development Bank Co.,Ltd.",  # 英文全称
            "COMPANY_ABBR_EN": "SPD BANK",             # 公司英文简称
            "SEC_TYPE": "主板A",                        # 证券类别
            "STATE_CODE_A_DESC": "上市",                # A股状态描述
            "CSRC_CODE": "J",                          # 证监会行业代码
            "CSRC_CODE_DESC": "金融业",                 # 证监会行业名称
            "CSRC_GREAT_CODE": "66",                   # 证监会大类代码
            "CSRC_GREAT_CODE_DESC": "货币金融服务",     # 证监会大类名称
            "REG_ADDRESS": "上海市黄浦区中山东一路12号", # 注册地址
            "OFFICE_ADDRESS": "上海市中山东一路12号",   # 办公地址
            "OFFICE_ZIP": "200002",                    # 办公地址邮编
            "AREA_NAME": "上海市",                     # 所属地区
            "LEGAL_REPRESENTATIVE": "张为忠",          # 法定代表人
            "NAME": "张健",                            # 董事会秘书
            "INVESTOR_PHONE": "63611226",             # 投资者电话
            "E_MAIL_ADDRESS": "SHAzhdjshbgs@spdb.com.cn",  # 邮箱
            "PROFIT_FLAG": "Y",                        # 是否盈利
            "IS_VOTE_DIFF": "N",                       # 是否存在表决权差异安排
            "SECURITY_30_DESC": "是",                  # 是否 20%/30% 涨跌幅
            ...
        }

    行为说明：
      - 本函数仅负责：
          * 构造请求参数与请求头
          * 发起 HTTP 请求（带 async_retry_call 重试）
          * 使用 strip_jsonp 解析 JSONP 文本
          * 从 data['result'] 提取记录列表，并构造 DataFrame
      - 不做字段标准化或单位换算，保持与原 JSON 一致。

    Args:
        company_code: 公司代码 / A股代码（如 "600000"）

    Returns:
        pandas.DataFrame:
          - 正常情况：一行记录（一家公司概况）
          - 无数据或失败：空 DataFrame
    """
    # ===== 步骤1：动态参数（JSONP 回调 & 防缓存时间戳）=====
    callback_name = generate_jsonp_callback("jsonpCallback")
    timestamp = generate_cache_buster()

    # ===== 步骤2：构造查询参数 =====
    params: Dict[str, str] = {
        "jsonCallBack": callback_name,
        "isPagination": "false",
        "sqlId": "COMMON_SSE_CP_GPJCTPZ_GPLB_GPGK_GSGK_C",
        "COMPANY_CODE": str(company_code or "").strip(),
        "_": timestamp,
    }

    # ===== 步骤3：生成通用请求头 =====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers: Dict[str, str] = {
        # 个性化头（与抓包保持一致）
        "Referer": "https://www.sse.com.cn/",
        "Accept": "*/*",
        "Host": "query.sse.com.cn",

        # 现代浏览器安全头
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",

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
        "[上交所] 公司概况开始拉取",
        extra={
            "company_code": company_code,
            "sqlId": params["sqlId"],
            "callback": callback_name,
        },
    )

    # ===== 步骤4：执行请求（带统一重试）=====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(BASE_URL, params=params, headers=headers)
            resp.raise_for_status()

            # JSONP → dict
            data = strip_jsonp(resp.text)

            rows: List[Dict[str, Any]] = data.get("result") or []

            # 兼容 pageHelp.data（理论上此接口不会用到）
            if not rows and isinstance(data.get("pageHelp"), dict):
                rows = data["pageHelp"].get("data") or []

            if not rows:
                _LOG.warning(
                    "[上交所] 公司概况无数据",
                    extra={
                        "company_code":
                        company_code,
                        "sqlId":
                        params["sqlId"],
                        "data_keys":
                        list(data.keys()) if isinstance(data, dict) else None,
                    },
                )
                return pd.DataFrame()

            _LOG.info(
                "[上交所] 公司概况获取成功 %d 条记录",
                len(rows),
                extra={
                    "company_code":
                    company_code,
                    "sqlId":
                    params["sqlId"],
                    "callback":
                    callback_name,
                    "user_agent_version":
                    (user_agent.split("Chrome/")[1].split()[0]
                     if "Chrome/" in user_agent else "unknown"),
                },
            )

            return pd.DataFrame(rows)

    df = await async_retry_call(_do_request)

    return df if df is not None else pd.DataFrame()


# 1.2 上交所股票档案，股票市值（成交统计）


@limit_async_network_io
async def get_stock_profile_value_sh_sse(
    sec_code: str,
    date_type: str = "D",
    tx_date: str = "",
    tx_date_mon: str = "",
    tx_date_year: str = "",
) -> pd.DataFrame:
    """
    [成交统计] 从上交所官网获取单只股票的成交统计数据（JSONP 接口 · 成交概况）

    设计用途：
      - 为后续“最新市值 / 流通市值 / 成交活跃度 / 盘子大小”等标准化逻辑提供原始数据
      - 本函数**不做字段重命名或单位换算**，完整保留接口返回的所有字段，由 normalizer 层统一处理

    支持的统计粒度：
      - 日度：date_type="D"
          - sqlId = COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C
          - 请求参数：仅 TX_DATE 生效
      - 月度：date_type="M"
          - sqlId = COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_YDGK_C
          - 请求参数：仅 TX_DATE_MON 生效
      - 年度：date_type="Y"
          - sqlId = COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_NDGK_C
          - 请求参数：仅 TX_DATE_YEAR 生效

    日期参数规范（传入侧）：
      - tx_date:
          * 仅在 date_type="D" 时使用
          * 要求格式："YYYY-MM-DD" 或兼容格式（"YYYYMMDD" / "YYYY/MM/DD" 等）
          * 内部会使用 parse_yyyymmdd 做容错解析，最终转换为 "YYYYMMDD" 传给 TX_DATE
      - tx_date_mon:
          * 仅在 date_type="M" 时使用
          * 要求格式："YYYYMMDD"（任意该月中的一天，例如 "20251001"）
          * 内部会使用 parse_yyyymmdd 做容错解析，解析失败则该参数被忽略
          * 当前实现直接按 "YYYYMMDD" 原样传给 TX_DATE_MON（上交所实际只关心年月部分，留给后续调优）
      - tx_date_year:
          * 仅在 date_type="Y" 时使用
          * 要求格式："YYYY"（如 "2024"）
          * 若不是 4 位数字，则忽略该参数，回退为“最近完整年度”

    容错策略：
      - 日期字符串解析失败或格式不符合要求时：
          * 记录一条 WARNING 日志（包含原始输入与错误信息）
          * 对应 TX_DATE / TX_DATE_MON / TX_DATE_YEAR 将被置为空字符串
          * 上交所接口会退回“最近一日 / 最近一月 / 最近一整年”的统计结果，不会抛异常

    数据源：
      - 页面示例：
          https://www.sse.com.cn/assortment/stock/list/info/company/index.shtml?COMPANY_CODE=600006/
      - 接口地址：
          https://query.sse.com.cn/commonQuery.do

    抓包参数示例（600006）：
      - 请求 URL：
          https://query.sse.com.cn/commonQuery.do
            ?jsonCallBack=jsonpCallback99215048
            &sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C
            &SEC_CODE=600006
            &TX_DATE=
            &TX_DATE_MON=
            &TX_DATE_YEAR=
            &_=1764211243105

      - 关键业务参数：
          sqlId      = COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C   # 每日周期统计模板
                        COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_YDGK_C  # 月度周期统计模板
                        COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_NDGK_C  # 年度周期统计模板
          SEC_CODE   = 600006         # 证券代码（A股代码）
          TX_DATE    = ""             # 交易日期；date_type="D" 且指定 tx_date 时为 YYYYMMDD，留空=最近一日
          TX_DATE_MON= ""             # 交易月份；date_type="M" 且指定 tx_date_mon 时为 YYYYMMDD，留空=最近一月
          TX_DATE_YEAR= ""            # 交易年份；date_type="Y" 且指定 tx_date_year 时为 YYYY，留空=最近一整年
          jsonCallBack = jsonpCallbackXXXXXXXX  # JSONP 回调名
          _           = 13位毫秒时间戳（防缓存）

    返回数据结构（result[0] 字段集合在日/月/年三种粒度下 **完全一致**，仅统计口径不同）：

        {
            "SEC_CODE": "600006",      # 证券代码
            "SEC_NAME": "东风股份",     # 证券简称
            "TX_DATE": "20251126",     # 统计日期/周期：
                                       #   - DATE_TYPE="D" → 当日：YYYYMMDD
                                       #   - DATE_TYPE="M" → 当月：YYYYMM 或近似值
                                       #   - DATE_TYPE="Y" → 年度：通常为该年末所在月份
            "DATE_TYPE": "D"|"M"|"Y",  # 统计粒度：D=日, M=月, Y=年

            "OPEN_PRICE": "7.46",      # 区间首日/当日开盘价（元）
            "HIGH_PRICE": "8.00",      # 区间内最高价（元）
            "LOW_PRICE": "4.10",       # 区间内最低价（元）
            "CLOSE_PRICE": "7.37",     # 区间末日/当日收盘价（元）
            "CHANGE_PRICE": "-0.09",   # 涨跌额（元），部分聚合周期可能返回 "-"（无定义）
            "CHANGE_RATE": "-1.20805", # 涨跌幅（%）
            "SWING_RATE": "101.65631", # 振幅（%）（区间高低价的相对波动）

            "TRADE_VOL": "2580.33",    # 成交量（万股）
            "TRADE_AMT": "19062.73",   # 成交金额（万元）

            "HIGH_VOL": "2580.33",     # 区间内单日最大成交量（万股）
            "HIGH_VOL_DATE": "20251126",    # 区间内单日最大成交量对应日期
            "LOW_VOL": "2580.33",      # 区间内单日最小成交量（万股）
            "LOW_VOL_DATE": "20251126",     # 区间内单日最小成交量对应日期

            "HIGH_AMT": "19062.73",    # 区间内单日最大成交金额（万元）
            "HIGH_AMT_DATE": "20251126",    # 区间内单日最大成交金额对应日期
            "LOW_AMT": "19062.73",     # 区间内单日最小成交金额（万元）
            "LOW_AMT_DATE": "20251126",     # 区间内单日最小成交金额对应日期

            "HIGH_PRICE_DATE": "20251126", # 区间内最高价对应日期
            "LOW_PRICE_DATE": "20251126",  # 区间内最低价对应日期

            "TOTAL_VALUE": "1472000.0",    # 总市值（万元）
            "NEGO_VALUE": "1472000.0",     # 流通市值 / 可流通市值（万元）
            "TO_RATE": "1.29",             # 总换手率（%）
            "PE_RATE": "504.76375",        # 静态市盈率（倍）
            "ACCU_TRADE_DAYS": "0"         # 统计区间内的累计交易天数
                                           #   - 日度：通常为 "0"
                                           #   - 月度/年度：为对应月份/年度内的交易天数
        }

    行为说明：
      - 本函数仅负责：
          * 构造请求参数与请求头（参照浏览器抓包 + spider_toolkit 池）
          * 发起 HTTP 请求（带 async_retry_call 重试）
          * 使用 strip_jsonp 脱掉 JSONP 外壳
          * 从 data['result'] / data['pageHelp']['data'] 提取记录列表，并构造 DataFrame
      - 不做任何字段重命名、单位换算或业务级含义解释：
          * TOTAL_VALUE / NEGO_VALUE / TRADE_VOL / TRADE_AMT / TO_RATE / PE_RATE 等字段全部原样保留
          * “最新市值”、“盘子大小”、“年内最大成交额”等判断逻辑由上层 normalizer / 业务服务实现

    Args:
        sec_code: 证券代码（A股代码，6 位数字，如 "600006"）
        date_type: 统计粒度：
            - "D": 日度（最近一日或指定 tx_date）
            - "M": 月度（最近一月或指定 tx_date_mon）
            - "Y": 年度（最近一整年或指定 tx_date_year）
        tx_date:     日度统计时可选日期（"YYYY-MM-DD" 或兼容格式），解析失败将被忽略。
        tx_date_mon: 月度统计时可选日期（"YYYYMMDD"，任意该月中一天），解析失败将被忽略。
        tx_date_year:年度统计时可选年份（"YYYY"），格式不合法时将被忽略。

    Returns:
        pandas.DataFrame:
          - 正常情况：一行记录（该证券在指定粒度/日期下的成交统计）
          - 接口无数据或异常：空 DataFrame
    """
    # 规范化粒度参数
    dt = (date_type or "D").upper().strip()
    if dt not in ("D", "M", "Y"):
        dt = "D"  # 容错：未知值回退为日度

    # 按粒度选择 sqlId
    if dt == "D":
        sql_id = "COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C"
    elif dt == "M":
        sql_id = "COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_YDGK_C"
    else:  # dt == "Y"
        sql_id = "COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_NDGK_C"

    # ===== 步骤1：动态参数（JSONP 回调 & 防缓存时间戳）=====
    callback_name = generate_jsonp_callback("jsonpCallback")
    timestamp = generate_cache_buster()

    sec_code_clean = str(sec_code or "").strip()

    # ===== 步骤2：根据粒度做日期参数容错解析 =====
    tx_date_norm = ""
    tx_date_mon_norm = ""
    tx_date_year_norm = ""

    # 日度：解析 tx_date → TX_DATE="YYYYMMDD"
    if dt == "D":
        raw = str(tx_date or "").strip()
        if raw:
            try:
                # 日度：输出 'YYYYMMDD'
                tx_date_norm = format_date_value(raw, unit="d", sep="")
            except Exception as e:
                _LOG.warning(
                    "[上交所] 股票成交统计 tx_date 解析失败，回退为上一交易日",
                    extra={
                        "sec_code": sec_code_clean,
                        "raw_tx_date": raw,
                        "error": str(e)
                    },
                )

    # 月度：解析 tx_date_mon → TX_DATE_MON="YYYYMM"（所有月度参数统一使用 YYYYMM）
    elif dt == "M":
        raw = str(tx_date_mon or "").strip()
        if raw:
            try:
                # 月度：宽松解析各种年月/日格式，输出 'YYYYMM'
                tx_date_mon_norm = format_date_value(raw, unit="m", sep="")
            except Exception as e:
                _LOG.warning(
                    "[上交所] 股票成交统计 tx_date_mon 解析失败，回退为上一完整月度",
                    extra={
                        "sec_code": sec_code_clean,
                        "raw_tx_date_mon": raw,
                        "error": str(e)
                    },
                )

    # 年度：校验 tx_date_year → TX_DATE_YEAR="YYYY"
    else:  # dt == "Y"
        raw = str(tx_date_year or "").strip()
        if raw:
            try:
                # 年度：宽松解析年度/月度/日度所有格式，输出 'YYYY'
                tx_date_year_norm = format_date_value(raw, unit="y", sep="")
            except Exception as e:
                _LOG.warning(
                    "[上交所] 股票成交统计 tx_date_year 解析失败，回退为最近一整年",
                    extra={
                        "sec_code": sec_code_clean,
                        "raw_tx_date_year": raw,
                        "error": str(e)
                    },
                )

    # ===== 步骤3：构造查询参数 =====
    params: Dict[str, str] = {
        "jsonCallBack": callback_name,
        "isPagination": "false",
        "sqlId": sql_id,
        "SEC_CODE": sec_code_clean,
        "TX_DATE": tx_date_norm if dt == "D" else "",  # 仅日度使用
        "TX_DATE_MON": tx_date_mon_norm if dt == "M" else "",  # 仅月度使用
        "TX_DATE_YEAR": tx_date_year_norm if dt == "Y" else "",  # 仅年度使用
        "_": timestamp,
    }

    # ===== 步骤4：生成通用请求头 =====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers: Dict[str, str] = {
        # 个性化头（与抓包保持一致）
        "Referer": "https://www.sse.com.cn/",
        "Accept": "*/*",
        "Host": "query.sse.com.cn",

        # 现代浏览器安全头
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",

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
        "[上交所] 成交统计开始拉取",
        extra={
            "sec_code": sec_code_clean,
            "sqlId": sql_id,
            "date_type": dt,
            "TX_DATE": params["TX_DATE"],
            "TX_DATE_MON": params["TX_DATE_MON"],
            "TX_DATE_YEAR": params["TX_DATE_YEAR"],
            "callback": callback_name,
        },
    )

    # ===== 步骤5：执行请求（带统一重试）=====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(BASE_URL, params=params, headers=headers)
            resp.raise_for_status()

            # JSONP → dict
            data = strip_jsonp(resp.text)

            rows: List[Dict[str, Any]] = data.get("result") or []

            # 兼容 pageHelp.data（理论上此接口以 result 为主）
            if not rows and isinstance(data.get("pageHelp"), dict):
                rows = data["pageHelp"].get("data") or []

            if not rows:
                _LOG.warning(
                    "[上交所] 成交统计无数据",
                    extra={
                        "sec_code":
                        sec_code_clean,
                        "sqlId":
                        sql_id,
                        "date_type":
                        dt,
                        "data_keys":
                        list(data.keys()) if isinstance(data, dict) else None,
                    },
                )
                return pd.DataFrame()

            _LOG.info(
                "[上交所] 成交统计获取成功 %d 条记录",
                len(rows),
                extra={
                    "sec_code":
                    sec_code_clean,
                    "sqlId":
                    sql_id,
                    "date_type":
                    dt,
                    "callback":
                    callback_name,
                    "user_agent_version":
                    (user_agent.split("Chrome/")[1].split()[0]
                     if "Chrome/" in user_agent else "unknown"),
                },
            )

            return pd.DataFrame(rows)

    df = await async_retry_call(_do_request)

    return df if df is not None else pd.DataFrame()


# 1.3 上交所股票档案，股本情况（股本结构）


@limit_async_network_io
async def get_stock_profile_share_sh_sse(company_code: str) -> pd.DataFrame:
    """
    [股本结构] 从上交所官网获取单家公司股本结构（JSONP 接口 · 股本结构）

    数据源：
      - 页面示例：
          https://www.sse.com.cn/assortment/stock/list/info/company/index.shtml?COMPANY_CODE=600000
      - 接口地址：
          https://query.sse.com.cn/commonQuery.do

    抓包参数示例（600000）：
      - sqlId:
          COMMON_SSE_CP_GPJCTPZ_GPLB_GPGK_GBJG_C
      - isPagination: false
      - COMPANY_CODE: 600000
      - jsonCallBack: jsonpCallback21348508
      - _: 1763952355932

    请求方法：
      - GET

    关键业务参数：
      - COMPANY_CODE: 公司代码（通常等于 A 股代码，如 "600000"）

    返回数据结构（result[0] 示例，字段非完整，实际以接口为准）：

        {
            "TRADE_DATE": "20251121",        # 股本统计日期 (YYYYMMDD)
            "TOTAL_DOMESTIC_VOL": "3330583.83",   # 境内上市总股本（万股）
            "TOTAL_UNLIMIT_VOL": "3330583.83",    # 无限售流通股本（万股）
            "A_UNLIMIT_VOL": "3330583.83",        # A股流通股本（万股）
            "A_LIMIT_VOL": "0.00",                # A股限售股本（万股）
            "B_VOL": "0.00",                      # B股股本（万股）
            "CDR_VOL": "0.00",                    # CDR 股本（万股）
            "SPECIAL_VOL": "-"                    # 特别表决权股本（万股）
            ...
        }

    行为说明：
      - 本函数仅负责：
          * 构造请求参数与请求头
          * 发起 HTTP 请求（带 async_retry_call 重试）
          * 使用 strip_jsonp 解析 JSONP 文本
          * 从 data['result'] 提取记录列表，并构造 DataFrame
      - 不做字段单位换算（如万股/股），保持与原 JSON 一致。

    Args:
        company_code: 公司代码 / A股代码（如 "600000"）

    Returns:
        pandas.DataFrame:
          - 正常情况：一行记录（最新股本结构）
          - 无数据或失败：空 DataFrame
    """
    # ===== 步骤1：动态参数（JSONP 回调 & 防缓存时间戳）=====
    callback_name = generate_jsonp_callback("jsonpCallback")
    timestamp = generate_cache_buster()

    # ===== 步骤2：构造查询参数 =====
    params: Dict[str, str] = {
        "jsonCallBack": callback_name,
        "isPagination": "false",
        "sqlId": "COMMON_SSE_CP_GPJCTPZ_GPLB_GPGK_GBJG_C",
        "COMPANY_CODE": str(company_code or "").strip(),
        "_": timestamp,
    }

    # ===== 步骤3：生成通用请求头 =====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers: Dict[str, str] = {
        "Referer": "https://www.sse.com.cn/",
        "Accept": "*/*",
        "Host": "query.sse.com.cn",
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": user_agent,
        "Accept-Language": accept_language,
        "Connection": connection,
        "Accept-Encoding": "gzip, deflate",
    }

    if sec_ch_ua:
        headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"'

    _LOG.info(
        "[上交所] 股本结构开始拉取",
        extra={
            "company_code": company_code,
            "sqlId": params["sqlId"],
            "callback": callback_name,
        },
    )

    # ===== 步骤4：执行请求（带统一重试）=====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(BASE_URL, params=params, headers=headers)
            resp.raise_for_status()

            data = strip_jsonp(resp.text)

            rows: List[Dict[str, Any]] = data.get("result") or []

            if not rows and isinstance(data.get("pageHelp"), dict):
                rows = data["pageHelp"].get("data") or []

            if not rows:
                _LOG.warning(
                    "[上交所] 股本结构无数据",
                    extra={
                        "company_code":
                        company_code,
                        "sqlId":
                        params["sqlId"],
                        "data_keys":
                        list(data.keys()) if isinstance(data, dict) else None,
                    },
                )
                return pd.DataFrame()

            _LOG.info(
                "[上交所] 股本结构获取成功 %d 条记录",
                len(rows),
                extra={
                    "company_code":
                    company_code,
                    "sqlId":
                    params["sqlId"],
                    "callback":
                    callback_name,
                    "user_agent_version":
                    (user_agent.split("Chrome/")[1].split()[0]
                     if "Chrome/" in user_agent else "unknown"),
                },
            )

            return pd.DataFrame(rows)

    df = await async_retry_call(_do_request)

    return df if df is not None else pd.DataFrame()


# ==============================================================================
# 2. 上交所基金档案
# ==============================================================================

# 2.1 上交所基金档案，基金档案基本信息（基金概况）


@limit_async_network_io
async def get_fund_profile_basic_sh_sse(fund_code: str) -> pd.DataFrame:
    """
    [基金基本信息] 从上交所官网获取单只场内基金的档案信息（JSONP 接口 · FUND_LIST 精确过滤版）

    设计用途：
      - 为后续“基金档案 / ETF 基本信息 / 指数与管理人信息 / 上市时间 / 托管人”等标准化逻辑提供原始数据
      - 本函数仅按基金代码精确过滤，返回原始字段，不做任何业务级字段重命名或转换

    数据源：
      - 页面示例：
          https://www.sse.com.cn/
      - 接口地址：
          https://query.sse.com.cn/commonSoaQuery.do

    抓包参数示例（510300·沪深300ETF）：

      请求：
        GET /commonSoaQuery.do
          ?jsonCallBack=jsonpCallback40200602
          &isPagination=false
          &sqlId=FUND_LIST
          &fundType=
          &fundCode=510300
          &_=1764204711877

      关键业务参数：
        - sqlId      = "FUND_LIST"      # 上交所基金列表模板 ID
        - isPagination = "false"        # 关闭分页，返回全量
        - fundType  = ""                # 基金大类（留空=不限类别）
        - fundCode  = "510300"          # 基金代码（精确过滤）
        - jsonCallBack = jsonpCallbackXXXXXXXX
        - _         = 13 位毫秒时间戳（防缓存）

    返回数据结构（result[0] 示例，字段来自实测，后续可能扩展，实际以接口为准）：

        {
            "listingDate": "20120528",                       # 上市日期 (YYYYMMDD)
            "LAW_FIRM": "",                                  # 律师事务所
            "CONTACT_MOBILE": "",                            # 联系电话
            "subClass": "03",                                # 基金子类别代码
            "fundManager": "柳军",                           # 基金经理
            "companyName": "华泰柏瑞基金管理有限公司",          # 基金管理人
            "INDEX_NAME": "沪深300指数",                     # 跟踪指数名称
            "fundAbbr": "300ETF",                            # 基金简称
            "fundType": "00",                                # 基金大类代码
            "fundCode": "510300",                            # 基金代码
            "INDEX_CODE": "000300",                          # 指数代码
            "secNameFull": "沪深300ETF",                     # 证券全称
            "TRUSTEE_NAME": "中国工商银行股份有限公司"          # 托管人名称
        }

      注意：
        - 顶层 JSON 同时在 "result" 和 "pageHelp.data" 下提供相同记录，本函数优先使用 result，若为空再回退 pageHelp.data。
        - 该接口本质为“基金列表”，但在此通过 fundCode 精确过滤，用作“单基金基本信息”档案接口。

    行为说明：
      - 本函数仅负责：
          * 构造请求参数与请求头（基于 spider_toolkit 通用池）
          * 发起 HTTP 请求（带 async_retry_call 重试）
          * 使用 strip_jsonp 解析 JSONP 文本
          * 从 data['result'] / data['pageHelp']['data'] 提取记录列表，并构造 DataFrame
      - 不做字段标准化或单位换算，保持字段名与原 JSON 完全一致：
          * 上层 normalizer 层可以根据实际业务将 listingDate 转为 YYYYMMDD 整数、拆分管理人/托管人等信息。

    Args:
        fund_code: 基金代码（6 位数字，如 "510300"）

    Returns:
        pandas.DataFrame:
          - 正常情况：一行记录（该基金的基本档案信息）
          - 若无匹配或失败：空 DataFrame
    """
    # ===== 步骤1：动态参数（JSONP 回调 & 防缓存时间戳）=====
    callback_name = generate_jsonp_callback("jsonpCallback")
    timestamp = generate_cache_buster()

    fund_code_clean = str(fund_code or "").strip()

    # ===== 步骤2：构造查询参数 =====
    params: Dict[str, str] = {
        "jsonCallBack": callback_name,
        "isPagination": "false",
        "sqlId": "FUND_LIST",
        "fundType": "",  # 留空：不限基金大类
        "fundCode": fund_code_clean,
        "_": timestamp,
    }

    # ===== 步骤3：生成通用请求头 =====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers: Dict[str, str] = {
        # 个性化头（与抓包保持一致）
        "Referer": "https://www.sse.com.cn/",
        "Accept": "*/*",
        "Host": "query.sse.com.cn",

        # 现代浏览器安全头
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",

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
        "[上交所] 基金档案开始拉取",
        extra={
            "fund_code": fund_code_clean,
            "sqlId": params["sqlId"],
            "callback": callback_name,
        },
    )

    # ===== 步骤4：执行请求（带统一重试）=====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://query.sse.com.cn/commonSoaQuery.do",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()

            # JSONP → dict
            data = strip_jsonp(resp.text)

            # 优先使用 result，其次回退到 pageHelp.data
            rows: List[Dict[str, Any]] = data.get("result") or []
            if not rows and isinstance(data.get("pageHelp"), dict):
                rows = data["pageHelp"].get("data") or []

            if not rows:
                _LOG.warning(
                    "[上交所] 基金档案无数据",
                    extra={
                        "fund_code":
                        fund_code_clean,
                        "sqlId":
                        params["sqlId"],
                        "data_keys":
                        list(data.keys()) if isinstance(data, dict) else None,
                    },
                )
                return pd.DataFrame()

            _LOG.info(
                "[上交所] 基金档案获取成功 %d 条记录",
                len(rows),
                extra={
                    "fund_code":
                    fund_code_clean,
                    "sqlId":
                    params["sqlId"],
                    "callback":
                    callback_name,
                    "user_agent_version":
                    (user_agent.split("Chrome/")[1].split()[0]
                     if "Chrome/" in user_agent else "unknown"),
                },
            )

            return pd.DataFrame(rows)

    df = await async_retry_call(_do_request)

    return df if df is not None else pd.DataFrame()


# 2.2 上交所基金档案，基金市值（基金成交统计）


@limit_async_network_io
async def get_fund_profile_value_sh_sse(
    sec_code: str,
    date_type: str = "D",
    tx_date: str = "",
    tx_date_mon: str = "",
    tx_date_year: str = "",
) -> pd.DataFrame:
    """
    [基金成交统计] 从上交所官网获取单只场内基金的成交 / 市值统计数据（JSONP 接口 · 日/月/年）

    设计用途：
      - 为后续“最新场内市值 / 成交活跃度 / ETF 盘子大小”等标准化逻辑提供原始数据
      - 本函数按基金代码精确过滤，支持日度/月度/年度三个粒度，返回原始字段，不做任何业务级字段重命名或转换

    支持的统计粒度（与股票成交统计接口完全一致，仅对象为基金）：
      - 日度：date_type="D"
          - sqlId = COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C
      - 月度：date_type="M"
          - sqlId = COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_YDGK_C
      - 年度：date_type="Y"
          - sqlId = COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_NDGK_C

    日期参数规范（传入侧，与股票版保持一致）：
      - tx_date:
          * 仅在 date_type="D" 时使用
          * 要求格式："YYYY-MM-DD" 或兼容格式（"YYYYMMDD" / "YYYY/MM/DD" 等）
          * 内部使用 parse_yyyymmdd 做容错解析，最终转换为 "YYYYMMDD" 传给 TX_DATE
      - tx_date_mon:
          * 仅在 date_type="M" 时使用
          * 要求格式："YYYYMMDD"（任意该月中的一天）
          * 内部使用 parse_yyyymmdd 做容错解析，解析失败则该参数被忽略（留空=最近一月）
      - tx_date_year:
          * 仅在 date_type="Y" 时使用
          * 要求格式："YYYY"（如 "2024"）
          * 若不是 4 位数字，则忽略该参数，回退为“最近完整年度”

    容错策略：
      - 日期字符串解析失败或格式不符合要求时：
          * 记录一条 WARNING 日志（包含原始输入与错误信息）
          * 对应 TX_DATE / TX_DATE_MON / TX_DATE_YEAR 将被置为空字符串
          * 上交所接口会退回“最近一日 / 最近一月 / 最近一整年”的统计结果，不会抛异常

    数据源：
      - 页面示例：
          https://www.sse.com.cn/
      - 接口地址：
          https://query.sse.com.cn/commonQuery.do

    基金日度样本（510300·300ETF，当日）：
        sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C, SEC_CODE=510300, DATE_TYPE="D"
        {
            "CLOSE_PRICE":   "4.626",        # 区间末日 / 当日收盘价（元）
            "LOW_VOL_DATE":  "20251126",     # 区间内单日最小成交量对应日期（YYYYMMDD）
            "LOW_AMT":       "422834.94",    # 区间内单日最小成交金额（万元）
            "SEC_CODE":      "510300",       # 证券代码 / 基金代码
            "HIGH_PRICE":    "4.65",         # 区间内最高价（元）
            "HIGH_AMT":      "422834.94",    # 区间内单日最大成交金额（万元）
            "HIGH_PRICE_DATE":"20251126",    # 区间内最高价对应日期（YYYYMMDD）
            "HIGH_VOL_DATE": "20251126",     # 区间内单日最大成交量对应日期（YYYYMMDD）
            "HIGH_VOL":      "91407.93",     # 区间内单日最大成交量（万股）
            "TOTAL_VALUE":   "42008931.61",  # 期末总市值（万元）
            "SWING_RATE":    "1.13191",      # 区间振幅（%），基于最高价与最低价
            "LOW_AMT_DATE":  "20251126",     # 区间内单日最小成交金额对应日期（YYYYMMDD）
            "TX_DATE":       "20251126",     # 统计日期（YYYYMMDD，日度=具体交易日）
            "SEC_NAME":      "300ETF",       # 证券简称 / 基金简称
            "LOW_PRICE_DATE":"20251126",     # 区间内最低价对应日期（YYYYMMDD）
            "TO_RATE":       "1.01",         # 区间换手率（%）
            "CHANGE_PRICE":  "0.03",         # 涨跌额（元），收盘价相对前一周期的变动金额
            "ACCU_TRADE_DAYS":"0",           # 统计区间内累计交易天数（日度一般为 0）
            "TRADE_AMT":     "422834.94",    # 区间累计成交金额（万元）
            "LOW_PRICE":     "4.59",         # 区间内最低价（元）
            "DATE_TYPE":     "D",            # 统计粒度标记：D=日度，M=月度，Y=年度
            "TRADE_VOL":     "91407.93",     # 区间累计成交量（万股）
            "LOW_VOL":       "91407.93",     # 区间内单日最小成交量（万股）
            "CHANGE_RATE":   "0.63085",      # 涨跌幅（%），收盘价相对前一周期的变动比例
            "NEGO_VALUE":    "42008931.61",  # 期末流通市值 / 可流通市值（万元）
            "HIGH_AMT_DATE": "20251126",     # 区间内单日最大成交金额对应日期（YYYYMMDD）
            "OPEN_PRICE":    "4.6",          # 区间首日 / 当日开盘价（元）
            "PE_RATE":       "-"             # 市盈率（倍）；无有效数值时为 "-"（如货基/部分 ETF）
        }

    基金月度样本（510300·300ETF，当月聚合）：
        sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_YDGK_C, SEC_CODE=510300, DATE_TYPE="M"
        {
            "CLOSE_PRICE":   "4.756",        # 月度区间末日收盘价（元）
            "LOW_VOL_DATE":  "20251022",     # 区间内单日最小成交量对应日期（YYYYMMDD）
            "LOW_AMT":       "260150.64",    # 区间内单日最小成交金额（万元）
            "SEC_CODE":      "510300",       # 证券代码 / 基金代码
            "HIGH_PRICE":    "4.874",        # 区间内最高价（元）
            "HIGH_AMT":      "685175.12",    # 区间内单日最大成交金额（万元）
            "HIGH_PRICE_DATE":"20251030",    # 区间内最高价对应日期（YYYYMMDD）
            "HIGH_VOL_DATE": "20251031",     # 区间内单日最大成交量对应日期（YYYYMMDD）
            "HIGH_VOL":      "143256.86",    # 区间内单日最大成交量（万股）
            "TOTAL_VALUE":   "42539703.23",  # 期末总市值（万元）
            "SWING_RATE":    "6.04874",      # 区间振幅（%），基于整月最高/最低价
            "LOW_AMT_DATE":  "20251022",     # 区间内单日最小成交金额对应日期（YYYYMMDD）
            "TX_DATE":       "202510",       # 统计月份（YYYYMM，月度聚合周期标识）
            "SEC_NAME":      "300ETF",       # 证券简称 / 基金简称
            "LOW_PRICE_DATE":"20251013",     # 区间内最低价对应日期（YYYYMMDD）
            "TO_RATE":       "16.83514",     # 月内累计换手率（%）
            "CHANGE_PRICE":  "-",            # 区间涨跌额（元）；月度/年度通常为 "-"（无单一参考价）
            "ACCU_TRADE_DAYS":"17",          # 当月累计交易日数量
            "TRADE_AMT":     "7151937.73",   # 区间累计成交金额（万元）
            "LOW_PRICE":     "4.596",        # 区间内最低价（元）
            "DATE_TYPE":     "M",            # 统计粒度标记：M=月度
            "TRADE_VOL":     "1510560.15",   # 区间累计成交量（万股）
            "LOW_VOL":       "55448.42",     # 区间内单日最小成交量（万股）
            "CHANGE_RATE":   "0.31639",      # 区间涨跌幅（%），通常为期末价相对期初价的变化比例
            "NEGO_VALUE":    "42539703.23",  # 期末流通市值 / 可流通市值（万元）
            "HIGH_AMT_DATE": "20251031",     # 区间内单日最大成交金额对应日期（YYYYMMDD）
            "OPEN_PRICE":    "4.754",        # 区间首日开盘价（元）
            "PE_RATE":       "-"             # 区间市盈率（倍）；ETF 多为 "-"，由上层自行处理
        }

    基金年度样本（510300·300ETF，当年聚合）：
        sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_NDGK_C, SEC_CODE=510300, DATE_TYPE="Y"
        {
            "CLOSE_PRICE":   "4.022",        # 年度区间末期收盘价（元）
            "LOW_VOL_DATE":  "20240617",     # 区间内单日最小成交量对应日期（YYYYMMDD）
            "LOW_AMT":       "139312.78",    # 区间内单日最小成交金额（万元）
            "SEC_CODE":      "510300",       # 证券代码 / 基金代码
            "HIGH_PRICE":    "4.656",        # 区间内最高价（元）
            "HIGH_AMT":      "3830371.73",   # 区间内单日最大成交金额（万元）
            "HIGH_PRICE_DATE":"20241008",    # 区间内最高价对应日期（YYYYMMDD）
            "HIGH_VOL_DATE": "20241008",     # 区间内单日最大成交量对应日期（YYYYMMDD）
            "HIGH_VOL":      "862982.24",    # 区间内单日最大成交量（万股）
            "TOTAL_VALUE":   "36231860.29",  # 期末总市值（万元）
            "SWING_RATE":    "50.09671",     # 年度振幅（%），基于全年最高/最低价
            "LOW_AMT_DATE":  "20240617",     # 区间内单日最小成交金额对应日期（YYYYMMDD）
            "TX_DATE":       "202412",       # 统计年度末期标识（通常为该年末所在月份 YYYYMM）
            "SEC_NAME":      "300ETF",       # 证券简称 / 基金简称
            "LOW_PRICE_DATE":"20240202",     # 区间内最低价对应日期（YYYYMMDD）
            "TO_RATE":       "533.47331",    # 年度累计换手率（%）
            "CHANGE_PRICE":  "-",            # 区间涨跌额（元）；年度聚合常为 "-"（无需单个涨跌额）
            "ACCU_TRADE_DAYS":"242",         # 年度内累计交易日数量
            "TRADE_AMT":     "129552308.85", # 年度累计成交金额（万元）
            "LOW_PRICE":     "3.102",        # 区间内最低价（元）
            "DATE_TYPE":     "Y",            # 统计粒度标记：Y=年度
            "TRADE_VOL":     "35320194.63",  # 年度累计成交量（万股）
            "LOW_VOL":       "39301.72",     # 区间内单日最小成交量（万股）
            "CHANGE_RATE":   "17.40807",     # 年度涨跌幅（%），期末价相对年初价的变动比例
            "NEGO_VALUE":    "36231860.29",  # 期末流通市值 / 可流通市值（万元）
            "HIGH_AMT_DATE": "20241008",     # 区间内单日最大成交金额对应日期（YYYYMMDD）
            "OPEN_PRICE":    "3.502",        # 区间首日开盘价（元）
            "PE_RATE":       "-"             # 年度市盈率（倍）；ETF 通常为 "-"，留待上层按需处理
        }

    字段说明（与股票成交统计完全一致，但 TOTAL_VALUE / NEGO_VALUE 为基金市值）：
      - SEC_CODE / SEC_NAME: 基金代码 / 名称
      - TX_DATE:
          * DATE_TYPE="D" → 交易日 YYYYMMDD
          * DATE_TYPE="M" → 统计月份 YYYYMM
          * DATE_TYPE="Y" → 年度统计末期（通常为该年末所在月份，格式 YYYYMM）
      - DATE_TYPE: "D" 日度, "M" 月度, "Y" 年度
      - OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE: 开高低收价格
      - CHANGE_PRICE, CHANGE_RATE, SWING_RATE: 涨跌额 / 涨跌幅(%) / 振幅(%)
      - TRADE_VOL, TRADE_AMT: 成交量 / 成交金额（单位后续在标准化阶段统一）
      - HIGH_VOL, LOW_VOL 及对应 *_DATE: 区间内单日最大/最小成交量及日期
      - HIGH_AMT, LOW_AMT 及对应 *_DATE: 区间内单日最大/最小成交额及日期
      - HIGH_PRICE_DATE, LOW_PRICE_DATE: 区间内最高/最低价对应日期
      - TOTAL_VALUE, NEGO_VALUE: 总市值 / 流通市值（用于 ETF 盘子大小判断）
      - TO_RATE: 换手率(%)
      - PE_RATE: 市盈率（部分基金返回 "-"）
      - ACCU_TRADE_DAYS: 统计区间内的累计交易日（D 通常为 "0"，M/Y 为该月/年度的交易天数）

    行为说明：
      - 本函数仅负责 HTTP 请求 + JSONP 解析 + DataFrame 构造：
          * 构造请求参数与请求头（使用 spider_toolkit 提供的 UA/Language/Connection 池）
          * 使用 async_retry_call 做指数退避重试与反爬告警
          * 使用 strip_jsonp 脱壳 JSONP 文本
          * 从 data['result'] / data['pageHelp']['data'] 提取记录列表，并构造 DataFrame
      - 不做任何字段标准化或单位换算，保持字段名与原 JSON 完全一致，由 normalizer 层做后续处理。

    Args:
        sec_code: 基金代码（如 "510300"）
        date_type: 统计粒度：
            - "D": 日度（最近一日或指定 tx_date）
            - "M": 月度（最近一月或指定 tx_date_mon）
            - "Y": 年度（最近一整年或指定 tx_date_year）
        tx_date:      日度统计时可选日期（"YYYY-MM-DD" 或兼容格式），解析失败将被忽略。
        tx_date_mon:  月度统计时可选日期（"YYYYMMDD"，任意该月中一天），解析失败将被忽略。
        tx_date_year: 年度统计时可选年份（"YYYY"），格式不合法时将被忽略。

    Returns:
        pandas.DataFrame:
          - 正常情况：一行记录（该基金在指定粒度/日期下的成交 / 市值统计）
          - 接口无数据或异常：空 DataFrame
    """
    # 规范化粒度参数
    dt = (date_type or "D").upper().strip()
    if dt not in ("D", "M", "Y"):
        dt = "D"  # 容错：未知值回退为日度

    # 按粒度选择 sqlId（与股票成交统计相同）
    if dt == "D":
        sql_id = "COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C"
    elif dt == "M":
        sql_id = "COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_YDGK_C"
    else:  # dt == "Y"
        sql_id = "COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_NDGK_C"

    # ===== 步骤1：动态参数（JSONP 回调 & 防缓存时间戳）=====
    callback_name = generate_jsonp_callback("jsonpCallback")
    timestamp = generate_cache_buster()

    sec_code_clean = str(sec_code or "").strip()

    # ===== 步骤2：根据粒度做日期参数容错解析（统一使用 format_date_value）=====
    tx_date_norm = ""
    tx_date_mon_norm = ""
    tx_date_year_norm = ""

    if dt == "D":
        raw = str(tx_date or "").strip()
        if raw:
            try:
                # 日度：输出 'YYYYMMDD'
                tx_date_norm = format_date_value(raw, unit="d", sep="")
            except Exception as e:
                _LOG.warning(
                    "[上交所] 基金成交统计 tx_date 解析失败，回退为最近一日",
                    extra={
                        "sec_code": sec_code_clean,
                        "raw_tx_date": raw,
                        "error": str(e)
                    },
                )

    elif dt == "M":
        raw = str(tx_date_mon or "").strip()
        if raw:
            try:
                # 月度：宽松解析各种年月/日格式，输出 'YYYYMM'
                tx_date_mon_norm = format_date_value(raw, unit="m", sep="")
            except Exception as e:
                _LOG.warning(
                    "[上交所] 基金成交统计 tx_date_mon 解析失败，回退为最近一月",
                    extra={
                        "sec_code": sec_code_clean,
                        "raw_tx_date_mon": raw,
                        "error": str(e)
                    },
                )

    else:  # dt == "Y"
        raw = str(tx_date_year or "").strip()
        if raw:
            try:
                # 年度：宽松解析年度/月度/日度所有格式，输出 'YYYY'
                tx_date_year_norm = format_date_value(raw, unit="y", sep="")
            except Exception as e:
                _LOG.warning(
                    "[上交所] 基金成交统计 tx_date_year 解析失败，回退为最近一整年",
                    extra={
                        "sec_code": sec_code_clean,
                        "raw_tx_date_year": raw,
                        "error": str(e)
                    },
                )

    # ===== 步骤3：构造查询参数 =====
    params: Dict[str, str] = {
        "jsonCallBack": callback_name,
        "isPagination": "false",
        "sqlId": sql_id,
        "SEC_CODE": sec_code_clean,
        "TX_DATE": tx_date_norm if dt == "D" else "",
        "TX_DATE_MON": tx_date_mon_norm if dt == "M" else "",
        "TX_DATE_YEAR": tx_date_year_norm if dt == "Y" else "",
        "_": timestamp,
    }

    # ===== 步骤4：生成通用请求头 =====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers: Dict[str, str] = {
        # 个性化头（与抓包保持一致）
        "Referer": "https://www.sse.com.cn/",
        "Accept": "*/*",
        "Host": "query.sse.com.cn",

        # 现代浏览器安全头
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",

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
        "[上交所] 基金成交统计开始拉取",
        extra={
            "sec_code": sec_code_clean,
            "sqlId": sql_id,
            "date_type": dt,
            "TX_DATE": params["TX_DATE"],
            "TX_DATE_MON": params["TX_DATE_MON"],
            "TX_DATE_YEAR": params["TX_DATE_YEAR"],
            "callback": callback_name,
        },
    )

    # ===== 步骤5：执行请求（带统一重试）=====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(BASE_URL, params=params, headers=headers)
            resp.raise_for_status()

            # JSONP → dict
            data = strip_jsonp(resp.text)

            rows: List[Dict[str, Any]] = data.get("result") or []

            # 兼容 pageHelp.data（理论上此接口以 result 为主）
            if not rows and isinstance(data.get("pageHelp"), dict):
                rows = data["pageHelp"].get("data") or []

            if not rows:
                _LOG.warning(
                    "[上交所] 基金成交统计无数据",
                    extra={
                        "sec_code":
                        sec_code_clean,
                        "sqlId":
                        sql_id,
                        "date_type":
                        dt,
                        "data_keys":
                        list(data.keys()) if isinstance(data, dict) else None,
                    },
                )
                return pd.DataFrame()

            _LOG.info(
                "[上交所] 基金成交统计获取成功 %d 条记录",
                len(rows),
                extra={
                    "sec_code":
                    sec_code_clean,
                    "sqlId":
                    sql_id,
                    "date_type":
                    dt,
                    "callback":
                    callback_name,
                    "user_agent_version":
                    (user_agent.split("Chrome/")[1].split()[0]
                     if "Chrome/" in user_agent else "unknown"),
                },
            )

            return pd.DataFrame(rows)

    df = await async_retry_call(_do_request)

    return df if df is not None else pd.DataFrame()


# 2.3 上交所基金档案，基金份额（基金规模页）


@limit_async_network_io
async def get_fund_profile_share_sh_sse(
    sec_code: str,
    stat_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    [基金规模（ETF）] 从上交所官网获取单只 ETF 的场内规模时间序列或指定日期规模（JSONP 接口）

    设计用途：
      - 为后续“ETF 最新规模 / 历史规模变化 / 盘子大小趋势”等标准化逻辑提供原始数据
      - 本函数支持两种模式（由 stat_date 是否能成功解析决定）：
          1) stat_date 能被成功解析 → 使用 SEARCH_L 模板，仅查询该日期单条记录
          2) stat_date 为空或解析失败   → 使用 MOREN_L 模板，返回默认配置的最近若干日时间序列
      - 为简化逻辑，isPagination 一律固定为 "false"，不再传递 pageHelp.pageSize 等分页参数。

    日期参数规范与容错：
      - stat_date:
          * 建议格式："YYYY-MM-DD"（与官网参数一致）
          * 也兼容 "YYYYMMDD" / "YYYY/MM/DD" 等格式
          * 内部使用 parse_yyyymmdd 解析：
              - 解析成功：转换为 "YYYY-MM-DD" 格式传给 STAT_DATE，并使用 SEARCH_L 模板
              - 解析失败：记录 WARNING 日志，不传 STAT_DATE，退回 MOREN_L 模板（最近若干日，数量由服务器端缺省决定）

    数据源：
      - 页面示例：
          https://www.sse.com.cn/
      - 接口地址：
          https://query.sse.com.cn/commonQuery.do

    模式一：不指定日期（最近 N 日时间序列）
      - 请求示例：
          GET /commonQuery.do
            ?jsonCallBack=jsonpCallback91533460
            &isPagination=false
            &sqlId=COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_MOREN_L
            &SEC_CODE=510300
            &_=1764226657506

      - 关键参数：
          sqlId             = "COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_MOREN_L"
          isPagination      = "false"
          SEC_CODE          = 基金代码，如 "510300"

      - 返回字段示例（result 中多行，按 STAT_DATE 倒序排列）：

            {
                "STAT_DATE": "2025-11-26",       # 统计日期（YYYY-MM-DD）
                "ETF_TYPE": "跨市",               # ETF 类型（跨市 / 单市场 等）
                "SEC_CODE": "510300",            # 基金代码
                "NUM": "1",                      # 序号（按时间倒序）
                "SEC_NAME": "300ETF",            # 基金简称
                "TOT_VOL": "9026958.77",         # 基金总份额/规模（单位：万份）
                "FUND_EXPANSION_ABBR": "沪深300ETF"  # 基金扩展简称
            }
            # 后续行 STAT_DATE 依次为 T-1, T-2, ...

    模式二：指定日期（单日规模）
      - 请求示例（指定 2025-11-26）：
          GET /commonQuery.do
            ?jsonCallBack=jsonpCallback9892454
            &isPagination=false
            &sqlId=COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_SEARCH_L
            &SEC_CODE=510300
            &STAT_DATE=2025-11-26
            &_=1764226657514

      - 关键参数：
          sqlId        = "COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_SEARCH_L"
          isPagination = "false"
          SEC_CODE     = 基金代码，如 "510300"
          STAT_DATE    = 目标日期（YYYY-MM-DD）

      - 返回字段示例（单行或空）：

            {
                "STAT_DATE": "2025-11-26",
                "ETF_TYPE": "跨市",
                "SEC_CODE": "510300",
                "SEC_NAME": "300ETF",
                "TOT_VOL": "9026958.77",
                "FUND_EXPANSION_ABBR": "沪深300ETF"
            }

      - 若指定的 STAT_DATE 尚无数据（例如当日未更新），则 result 为空列表。

    字段说明：
      - STAT_DATE: 统计日期（字符串，格式 "YYYY-MM-DD"）
      - ETF_TYPE: ETF 类型（如 "跨市"），原样保留
      - SEC_CODE: 基金代码（如 "510300"）
      - SEC_NAME: 基金简称（如 "300ETF"）
      - FUND_EXPANSION_ABBR: 基金扩展简称（如 "沪深300ETF"）
      - TOT_VOL: 基金总份额/规模（数值含义与单位在标准化层统一处理）
      - NUM: 序号（仅在 MOREN_L 模板下存在，按时间倒序排序）

    行为说明：
      - 本函数仅负责：
          * 根据是否提供且成功解析 stat_date 决定 SQL 模板（MOREN_L / SEARCH_L）
          * 构造请求参数与请求头（使用 spider_toolkit 提供的 UA/Language/Connection 池）
          * 发起 HTTP 请求（带 async_retry_call 重试）
          * 使用 strip_jsonp 解析 JSONP 文本
          * 从 data['result'] / data['pageHelp']['data'] 提取记录列表，并构造 DataFrame
      - 不做字段重命名或单位换算，保持字段名与原 JSON 完全一致。

    Args:
        sec_code: 基金代码（如 "510300"）
        stat_date: 目标日期，可为 "YYYY-MM-DD" 或兼容格式。
            - None 或解析失败：使用 MOREN_L 模板，返回最近若干日的规模时间序列（条数由服务器默认）
            - 解析成功：使用 SEARCH_L 模板，仅查询该日期单条记录（或空）

    Returns:
        pandas.DataFrame:
          - 不指定 stat_date 或解析失败：多行时间序列表（按 STAT_DATE 倒序，行数由服务器默认）
          - 指定且解析成功：0 行或 1 行（单日结果）
          - 无数据或失败：空 DataFrame
    """
    # ===== 1. 预处理与解析日期参数（统一使用 format_date_value）=====
    sec_code_clean = str(sec_code or "").strip()
    raw_date = (stat_date or "").strip()

    stat_date_norm = ""
    use_search = False  # 是否使用精确查询模板 SEARCH_L

    if raw_date:
        try:
            # 日度：宽松解析各种日期格式，输出 'YYYY-MM-DD'
            stat_date_norm = format_date_value(raw_date, unit="d", sep="-")
            use_search = True
        except Exception as e:
            _LOG.warning(
                "[上交所] 基金规模 stat_date 解析失败，回退为最近若干日时间序列",
                extra={
                    "sec_code": sec_code_clean,
                    "raw_stat_date": raw_date,
                    "error": str(e)
                },
            )
            stat_date_norm = ""
            use_search = False

    # ===== 2. 根据解析结果选择 SQL 模板（isPagination 始终为 false）=====
    if use_search:
        # 精确日期查询：SEARCH_L
        sql_id = "COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_SEARCH_L"
        is_pagination = "false"
    else:
        # 默认最近若干日时间序列：MOREN_L
        sql_id = "COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_MOREN_L"
        is_pagination = "true"

    # ===== 3. 动态参数（JSONP 回调 & 防缓存时间戳）=====
    callback_name = generate_jsonp_callback("jsonpCallback")
    timestamp = generate_cache_buster()

    # ===== 4. 构造查询参数 =====
    params: Dict[str, str] = {
        "jsonCallBack": callback_name,
        "isPagination": is_pagination,
        "page_size": 1,
        "sqlId": sql_id,
        "SEC_CODE": sec_code_clean,
        "_": timestamp,
    }

    if use_search and stat_date_norm:
        params["STAT_DATE"] = stat_date_norm
        # MOREN_L 模式下，不再传递任何 pageHelp.pageSize 等分页参数

    # ===== 5. 生成通用请求头 =====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers: Dict[str, str] = {
        # 个性化头（与抓包保持一致）
        "Referer": "https://www.sse.com.cn/",
        "Accept": "*/*",
        "Host": "query.sse.com.cn",

        # 现代浏览器安全头
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",

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
        "[上交所] 基金规模开始拉取",
        extra={
            "sec_code": sec_code_clean,
            "sqlId": sql_id,
            "mode": "SEARCH_L" if use_search else "MOREN_L",
            "raw_stat_date": raw_date or None,
            "stat_date_norm": stat_date_norm or None,
            "callback": callback_name,
        },
    )

    # ===== 6. 执行请求（带统一重试）=====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(BASE_URL, params=params, headers=headers)
            resp.raise_for_status()

            # JSONP → dict
            data = strip_jsonp(resp.text)

            # 优先使用 result，其次回退到 pageHelp.data
            rows: List[Dict[str, Any]] = data.get("result") or []
            if not rows and isinstance(data.get("pageHelp"), dict):
                rows = data["pageHelp"].get("data") or []

            if not rows:
                _LOG.warning(
                    "[上交所] 基金规模无数据",
                    extra={
                        "sec_code":
                        sec_code_clean,
                        "sqlId":
                        sql_id,
                        "mode":
                        "SEARCH_L" if use_search else "MOREN_L",
                        "stat_date_norm":
                        stat_date_norm or None,
                        "data_keys":
                        list(data.keys()) if isinstance(data, dict) else None,
                    },
                )
                return pd.DataFrame()

            _LOG.info(
                "[上交所] 基金规模获取成功 %d 条记录",
                len(rows),
                extra={
                    "sec_code":
                    sec_code_clean,
                    "sqlId":
                    sql_id,
                    "mode":
                    "SEARCH_L" if use_search else "MOREN_L",
                    "stat_date_norm":
                    stat_date_norm or None,
                    "callback":
                    callback_name,
                    "user_agent_version":
                    (user_agent.split("Chrome/")[1].split()[0]
                     if "Chrome/" in user_agent else "unknown"),
                },
            )

            return pd.DataFrame(rows)

    df = await async_retry_call(_do_request)

    return df if df is not None else pd.DataFrame()
