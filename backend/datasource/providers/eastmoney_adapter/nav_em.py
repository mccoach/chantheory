# backend/datasource/providers/eastmoney_adapter/nav_em.py
# ==============================
# 说明：东方财富基金适配器 - 历史净值原子接口（V1.0 · f10/lsjz JSONP 通道版）
#
# 职责：
#   - 封装对东财 F10 历史净值接口 `/f10/lsjz` 的 HTTP 调用；
#   - 支持场内 / 场外基金（含 ETF、LOF 等）的历史净值查询；
#   - 透明处理服务端分页，**对上层表现为“一次调用拿到全量历史净值”**。
#
# 远程接口（基于你提供的抓包）：
#
#   基础 URL：
#     https://api.fund.eastmoney.com/f10/lsjz
#
#   典型请求示例：
#
#     https://api.fund.eastmoney.com/f10/lsjz
#       ?callback=jQuery18301547190755010458_1765181454747
#       &fundCode=510130
#       &pageIndex=1
#       &pageSize=20
#       &startDate=2025-12-01
#       &endDate=
#       &_=1765181467438
#
#   关键 Query 参数：
#     - fundCode : 基金代码（不带市场前缀），如 '510130','159102','000001'；
#     - pageIndex: 页码（从 1 开始）；
#     - pageSize : 每页记录数；
#     - startDate: 起始日期 'YYYY-MM-DD'，留空表示“从最早日期开始”；
#     - endDate  : 截止日期 'YYYY-MM-DD'，留空表示“截止到最新日期”；
#     - callback : JSONP 回调名，浏览器侧以 jQueryxxxx_时间戳 的形式生成；
#     - _        : 13 位毫秒时间戳，用于防缓存。
#
#   响应（JSONP 外壳包裹 JSON 对象）：
#
#     jQuery1830...({
#       "Data": {
#         "LSJZList": [
#           {
#             "FSRQ": "2025-12-05",  # 发生日期（YYYY-MM-DD）
#             "DWJZ": "7.0236",      # 单位净值
#             "LJJZ": "2.4157",      # 累计净值
#             "SDATE": null,
#             "ACTUALSYI": "",
#             "NAVTYPE": "1",
#             "JZZZL": "0.49",       # 净值涨跌幅（百分比数值，不带 % 号）
#             "SGZT": "场内买入",     # 申购状态
#             "SHZT": "场内卖出",     # 赎回状态
#             "FHFCZ": "",           # 分红发放情况
#             "FHFCBZ": "",          # 分红发放备注
#             "DTYPE": null,
#             "FHSP": ""
#           },
#           ...
#         ],
#         "FundType": "001",
#         "SYType": null,
#         "isNewType": false,
#         "Feature": "010,050,051,053"
#       },
#       "ErrCode": 0,
#       "ErrMsg": null,
#       "TotalCount": 56,
#       "Expansion": null,
#       "PageSize": 20,
#       "PageIndex": 1
#     });
#
#   重要字段说明：
#     - Data.LSJZList : 历史净值明细数组；本适配器的主要数据来源；
#     - TotalCount    : 总记录数，用于判断是否需要翻页；
#     - PageSize      : 实际每页条数；
#     - PageIndex     : 当前页码；
#     - ErrCode/ErrMsg: 接口层错误信息（ErrCode=0 表示成功）。
#
#   本适配器的输出 DataFrame 字段：
#
#     - 'date'               : str  ，FSRQ，格式 'YYYY-MM-DD'
#     - 'nav'                : float，DWJZ，单位净值
#     - 'acc_nav'            : float，LJJZ，累计净值
#     - 'pct_change'         : float | None，JZZZL，净值涨跌幅（% 数值）
#     - 'subscribe_status'   : str  | None，SGZT，申购状态
#     - 'redeem_status'      : str  | None，SHZT，赎回状态
#     - 'nav_type'           : str  | None，NAVTYPE，净值类型原始编码
#     - 'actual_return'      : str  | None，ACTUALSYI，实际收益信息原样保留
#     - 'bonus_distribution' : str  | None，FHFCZ，分红发放情况
#     - 'bonus_description'  : str  | None，FHFCBZ，分红备注
#     - 'dtype'              : str  | None，DTYPE，原始类型字段
#     - 'bonus_pay_date'     : str  | None，FHSP，分红发放日期等信息
#
#   与 normalizer 的契合点：
#     - 未来如需做“基金净值标准化”，可以直接基于本适配器输出的 DataFrame 字段进行映射；
#     - 当前本适配器不做日期整数化 / 时间戳转换，保持输入 JSON 的日期粒度与文本格式。
#
# 设计风格：
#   - 完全对齐 eastmoney_adapter.kline：
#       * async def + limit_async_network_io + async_retry_call；
#       * 使用 spider_toolkit 生成 UA / Accept-Language / Connection / sec-ch-ua；
#       * 使用 spider_toolkit.strip_jsonp 统一 JSON/JSONP 脱壳；
#       * 不做 DB 写入、不做业务推断、不做复权/估值计算。
#   - 分页透明：
#       * 自动根据 TotalCount / PageSize 计算应请求的页数；
#       * 逐页发起请求并拼接 Data.LSJZList，**对上层表现为一次性全量返回**。
# ==============================

from __future__ import annotations

from typing import List, Dict, Any, Optional

import math

import pandas as pd
import httpx

from backend.utils.async_limiter import limit_async_network_io
from backend.utils.async_retry import async_retry_call
from backend.utils.logger import get_logger
from backend.utils.time import parse_yyyymmdd
from backend.utils.spider_toolkit import (
    pick_user_agent,
    pick_accept_language,
    pick_connection,
    generate_sec_ch_ua,
    generate_jsonp_callback,
    generate_cache_buster,
    strip_jsonp,
)

_LOG = get_logger("eastmoney_adapter.nav")

# 基础 URL：东财 F10 历史净值
EM_FUND_NAV_URL = "https://api.fund.eastmoney.com/f10/lsjz"


# ==============================================================================
# 内部辅助函数
# ==============================================================================


def _safe_float(val: Any) -> Optional[float]:
    """
    安全将字符串/数值转为 float。

    规则：
      - None / "" / "-" → None
      - 其余尝试 float()，失败则返回 None。
    """
    if val in (None, "", "-"):
        return None
    try:
        return float(val)
    except Exception:
        return None


def _normalize_date_str(value: Optional[str]) -> str:
    """
    将任意可被 parse_yyyymmdd 解析的日期值规范化为 'YYYY-MM-DD' 字符串。

    若解析失败则抛出 ValueError，由调用方统一处理。
    """
    ymd = parse_yyyymmdd(value)
    s = f"{ymd:08d}"
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def _parse_lsjz_records(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    将 Data.LSJZList 数组解析为 DataFrame。

    输入：
      - records: 每个元素为形如：
          {
            "FSRQ": "2025-12-05",
            "DWJZ": "7.0236",
            "LJJZ": "2.4157",
            "SDATE": null,
            "ACTUALSYI": "",
            "NAVTYPE": "1",
            "JZZZL": "0.49",
            "SGZT": "场内买入",
            "SHZT": "场内卖出",
            "FHFCZ": "",
            "FHFCBZ": "",
            "DTYPE": null,
            "FHSP": ""
          }

    输出：
      - DataFrame，列：
          'date','nav','acc_nav','pct_change',
          'subscribe_status','redeem_status','nav_type',
          'actual_return','bonus_distribution','bonus_description',
          'dtype','bonus_pay_date'
      - 若 records 为空或全部行解析失败，则返回空 DataFrame。
    """
    out: List[Dict[str, Any]] = []

    for item in records or []:
        try:
            date_str = str(item.get("FSRQ") or "").strip()
            if not date_str:
                # 日期为空的记录直接跳过
                continue

            rec: Dict[str, Any] = {
                "date": date_str,
                "nav": _safe_float(item.get("DWJZ")),
                "acc_nav": _safe_float(item.get("LJJZ")),
                "pct_change": _safe_float(item.get("JZZZL")),
                "subscribe_status": (item.get("SGZT") or None) or None,
                "redeem_status": (item.get("SHZT") or None) or None,
                "nav_type": (item.get("NAVTYPE") or None) or None,
                "actual_return": (item.get("ACTUALSYI") or None) or None,
                "bonus_distribution": (item.get("FHFCZ") or None) or None,
                "bonus_description": (item.get("FHFCBZ") or None) or None,
                "dtype": (item.get("DTYPE") or None) or None,
                "bonus_pay_date": (item.get("FHSP") or None) or None,
            }

            out.append(rec)
        except Exception:
            # 单条解析异常不影响整体，直接跳过
            continue

    if not out:
        return pd.DataFrame()

    df = pd.DataFrame(out)

    # 为了后续可能的时间序列处理，这里按日期升序排序（字符串比较在 YYYY-MM-DD 下等价于时间顺序）
    df = df.sort_values("date").reset_index(drop=True)

    return df


# ==============================================================================
# 对外原子接口
# ==============================================================================


@limit_async_network_io
async def get_fund_nav_em(
    fund_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page_size: int = 200,
) -> pd.DataFrame:
    """
    [基金历史净值 · 东财 F10 /f10/lsjz JSONP 接口 · 自动翻页全量拉取]

    设计用途：
      - 为 ETF / LOF / 普通公募基金提供统一的“历史净值时间序列”；
      - 内部透明处理服务端分页，对上层表现为“一次调用拿到全量”；
      - 不做任何业务级分析，只负责“HTTP 请求 + JSONP 脱壳 + DataFrame 构造”。

    参数：
      - fund_code (str):
          * 基金代码，不带市场前缀，如：
              '510130'（ETF）、'159102'（ETF）、'000001'（场外基金）；
          * 保持与东财 F10 页面上展示的一致即可。

      - start_date (str | None):
          * 起始日期，建议格式 'YYYY-MM-DD'；
          * 也兼容 'YYYYMMDD' / 'YYYY/MM/DD' 等，可被 parse_yyyymmdd 解析的形式；
          * 传 None 或空字符串 → 不限制起始日期（东财默认从最早开始）。

      - end_date (str | None):
          * 截止日期，语义同上；
          * 传 None 或空字符串 → 不限制截止日期（东财默认到最新）。

      - page_size (int):
          * 每页记录条数；
          * 本适配器默认 200 条/页，经测试能有效返回的最大值为200，在 TotalCount 较大时会按需翻页拼接；
          * 你可以根据后续实测调大/调小该值，以平衡“单次响应大小”与“请求次数”。

    返回：
      - pandas.DataFrame，字段：
          * 'date'               : str        FSRQ（'YYYY-MM-DD'）
          * 'nav'                : float      DWJZ（单位净值）
          * 'acc_nav'            : float      LJJZ（累计净值）
          * 'pct_change'         : float|None JZZZL（净值涨跌幅，单位：%）
          * 'subscribe_status'   : str|None   SGZT（申购状态）
          * 'redeem_status'      : str|None   SHZT（赎回状态）
          * 'nav_type'           : str|None   NAVTYPE
          * 'actual_return'      : str|None   ACTUALSYI
          * 'bonus_distribution' : str|None   FHFCZ
          * 'bonus_description'  : str|None   FHFCBZ
          * 'dtype'              : str|None   DTYPE
          * 'bonus_pay_date'     : str|None   FHSP
      - 若请求 / 解析失败，将抛异常（由 async_retry_call 统筹重试）；
      - 若远端返回空 LSJZList，则返回空 DataFrame。

    行为与约束：
      - 本函数不做 DB 写入、不做收益/回撤等指标计算；
      - 不对净值数据进行复权或拆分，仅返回接口自身的“单位净值/累计净值 + 涨跌幅”等原始字段；
      - 不依赖 symbol_index / fund_profile 等本地表，完全以 fund_code 作为 key。
    """
    code = (fund_code or "").strip()
    if not code:
        _LOG.warning("[东财基金净值] 空 fund_code，直接返回空 DataFrame")
        return pd.DataFrame()

    # 规范化日期参数为东财要求的 'YYYY-MM-DD' 字符串或空串
    start_str = ""
    end_str = ""
    if start_date:
        try:
            start_str = _normalize_date_str(start_date)
        except Exception as e:
            _LOG.warning(
                "[东财基金净值] start_date 解析失败，改为不限制起始日期",
                extra={"fund_code": code, "raw": start_date, "error": str(e)},
            )
            start_str = ""
    if end_date:
        try:
            end_str = _normalize_date_str(end_date)
        except Exception as e:
            _LOG.warning(
                "[东财基金净值] end_date 解析失败，改为不限制截止日期",
                extra={"fund_code": code, "raw": end_date, "error": str(e)},
            )
            end_str = ""

    # 基础查询参数（不含 callback/_/pageIndex）
    base_params: Dict[str, Any] = {
        "fundCode": code,
        "pageSize": str(int(page_size) if page_size > 0 else 9999),
        "startDate": start_str,
        "endDate": end_str,
    }

    # ==== 构造通用请求头（与 kline 适配器风格保持一致）====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers: Dict[str, str] = {
        "Accept": "*/*",
        "Host": "api.fund.eastmoney.com",
        "Referer": "https://fundf10.eastmoney.com/",
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": user_agent,
        "Accept-Language": accept_language,
        "Connection": connection,
        # 避免 br/zstd 解压问题
        "Accept-Encoding": "gzip, deflate",
    }

    if sec_ch_ua:
        headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"'

    _LOG.info(
        "[东财基金净值] 开始拉取",
        extra={
            "fund_code": code,
            "start_date": start_str or None,
            "end_date": end_str or None,
            "page_size": base_params["pageSize"],
        },
    )

    async def _fetch_single_page(page_index: int) -> Dict[str, Any]:
        """
        拉取单页数据并返回解析后的 JSON 对象。

        使用 async_retry_call 统一做网络重试和反爬告警。
        """
        async def _do_request() -> Dict[str, Any]:
            # 动态 JSONP 回调名与防缓存时间戳
            callback_name = generate_jsonp_callback("jQuery")
            cache_buster = generate_cache_buster()

            params = dict(base_params)
            params.update({
                "pageIndex": str(page_index),
                "callback": callback_name,
                "_": cache_buster,
            })

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(EM_FUND_NAV_URL,
                                        params=params,
                                        headers=headers)
                resp.raise_for_status()

                try:
                    data = strip_jsonp(resp.text)
                except Exception as e:
                    _LOG.error(
                        "[东财基金净值] JSONP 脱壳失败",
                        extra={
                            "fund_code": code,
                            "page_index": page_index,
                            "error": str(e),
                            "text_preview": resp.text[:300],
                        },
                    )
                    return {}

                if not isinstance(data, dict):
                    _LOG.warning(
                        "[东财基金净值] 顶层结构非对象",
                        extra={
                            "fund_code": code,
                            "page_index": page_index,
                            "type": type(data).__name__,
                        },
                    )
                    return {}

                return data

        return await async_retry_call(_do_request)

    # ==== 拉取首页，判断分页信息 ====
    first_payload = await _fetch_single_page(1)
    if not first_payload:
        _LOG.warning(
            "[东财基金净值] 首次请求返回空 payload",
            extra={"fund_code": code},
        )
        return pd.DataFrame()

    err_code = first_payload.get("ErrCode")
    if err_code not in (0, "0", None):
        _LOG.warning(
            "[东财基金净值] 接口返回错误",
            extra={
                "fund_code": code,
                "ErrCode": first_payload.get("ErrCode"),
                "ErrMsg": first_payload.get("ErrMsg"),
            },
        )
        return pd.DataFrame()

    data_obj = first_payload.get("Data") or {}
    first_list: List[Dict[str, Any]] = data_obj.get("LSJZList") or []

    if not first_list:
        _LOG.warning(
            "[东财基金净值] 首次请求 Data.LSJZList 为空",
            extra={"fund_code": code},
        )
        return pd.DataFrame()

    total_count = first_payload.get("TotalCount")
    page_size_actual = first_payload.get("PageSize") or int(base_params["pageSize"])
    try:
        total = int(total_count) if total_count is not None else len(first_list)
        psize = int(page_size_actual) if page_size_actual else len(first_list)
    except Exception:
        total = len(first_list)
        psize = len(first_list)

    # 计算总页数（至少 1 页）
    page_count = max(1, math.ceil(total / max(psize, 1)))

    all_records: List[Dict[str, Any]] = []
    all_records.extend(first_list)

    _LOG.info(
        "[东财基金净值] 首页拉取成功",
        extra={
            "fund_code": code,
            "rows_first_page": len(first_list),
            "total_count": total,
            "page_size": psize,
            "page_count": page_count,
        },
    )

    # ==== 如有剩余页，依次拉取并拼接 ====
    if page_count > 1:
        for page_idx in range(2, page_count + 1):
            payload = await _fetch_single_page(page_idx)
            if not payload:
                _LOG.warning(
                    "[东财基金净值] 第 %d 页 payload 为空，提前终止翻页",
                    page_idx,
                    extra={"fund_code": code},
                )
                break

            data_obj = payload.get("Data") or {}
            page_list: List[Dict[str, Any]] = data_obj.get("LSJZList") or []

            if not page_list:
                _LOG.warning(
                    "[东财基金净值] 第 %d 页 Data.LSJZList 为空，提前终止翻页",
                    page_idx,
                    extra={"fund_code": code},
                )
                break

            all_records.extend(page_list)

            _LOG.info(
                "[东财基金净值] 第 %d 页拉取成功",
                page_idx,
                extra={
                    "fund_code": code,
                    "rows_this_page": len(page_list),
                    "rows_accumulated": len(all_records),
                },
            )

            # 防御性：若已达到或超过 total_count，则提前退出
            if len(all_records) >= total:
                break

    # ==== 解析为 DataFrame 并返回 ====
    df = _parse_lsjz_records(all_records)

    _LOG.info(
        "[东财基金净值] 全量拉取完成",
        extra={
            "fund_code": code,
            "rows": len(df),
            "start_date": start_str or None,
            "end_date": end_str or None,
        },
    )

    return df