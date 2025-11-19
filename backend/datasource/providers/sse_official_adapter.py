# backend/datasource/providers/sse_official_adapter.py
# ==============================
# V3.0 - 完整重构极简版（通用参数从 settings 引入，个性化参数本地定义，基于官网实测请求头重构）
# 改动：
#   1. 通用参数（UA/Language/Connection）调用 toolkit 函数
#   2. 个性化参数（Referer/sqlId）直接在方法内写死
#   1. 删除冗余分页参数
#   2. Accept 修正为 "*/*"（与官网一致）
#   3. 删除 X-Requested-With（官网未携带）
#   4. 新增 Sec-Fetch-* 系列头（Chrome/Edge 必需）
#   5. 新增 sec-ch-ua 系列头（与 UA 版本号匹配）
#   6. 通用参数从 spider_toolkit 获取
#   7. 个性化参数在方法内直接定义
#
# # 说明: 原子化调用层 - 上交所官网自研适配器
# 职责:
#   - 仅封装对 “上交所官网 JSONP 接口” 的直接调用
#   - 提供异步函数，返回 pandas.DataFrame
#   - 不做任何业务逻辑和字段标准化（统一由 normalizer 层处理）
#
# 设计原则:
#   1. 与 akshare_adapter 风格保持一致：
#        - 对上层暴露 async 函数
#        - 底层进行网络访问和解析
#   2. 严格单一职责：
#        - 本文件只负责 HTTP 请求 + JSONP 解包 + DataFrame 构造
#        - 不写 DB、不写日志逻辑、不做结构标准化
#   3. 可扩展：
#        - 后续如需新增 “上交所债券/基金等列表”，在本文件继续添加函数即可
# ==============================

from __future__ import annotations

from typing import Dict, Any, List

import pandas as pd
import httpx

from backend.utils.async_limiter import limit_async_network_io
from backend.utils.async_retry import async_retry_call
from backend.utils.logger import get_logger

# 导入爬虫工具包
from backend.utils.spider_toolkit import (
    pick_user_agent,  # 随机选择 UA
    pick_accept_language,  # 随机选择语言
    pick_connection,  # 随机选择连接方式
    generate_jsonp_callback,  # 生成唯一回调名
    generate_cache_buster,  # 生成时间戳
    generate_sec_ch_ua,  #生成 sec-ch-ua 头
    strip_jsonp,  # 解析 JSONP
)

_LOG = get_logger("sse_official_adapter")

# ==============================================================================
# 1. 上交所股票列表 (官方 JSONP 接口)
# ==============================================================================


@limit_async_network_io
async def get_stock_list_sh_official() -> pd.DataFrame:
    """
    [A股列表] 从上交所官网获取 A 股列表 (JSONP 接口 · V3.0)

    数据源:
      - 官网地址 (页面): https://www.sse.com.cn/assortment/stock/list/share/
      - 接口地址 (API):  https://query.sse.com.cn/sseQuery/commonQuery.do

    V3.0 改动:
      - 基于官网实测请求头完整重构
      - 补充现代浏览器安全头（Sec-Fetch-*, sec-ch-ua）
      - 通用参数从 settings 池中随机选择
      - 个性化参数在方法内直接定义

    HTTP 方法:
      - GET

    请求参数说明:
      - sqlId: 上交所内部 SQL 模板 ID（固定值，不可修改）
      - COMPANY_STATUS: 公司状态码（2=正常,4=暂停,5=退市,7=ST,8=异常）
      - isPagination: 是否分页（false=全量返回）
      - jsonCallBack: JSONP 回调名（格式：jsonpCallback + 8位随机数）
      - _: 防缓存时间戳（13位毫秒）

    返回数据:
      - 类型: pandas.DataFrame
      - 每行对应官网返回的一个记录 (dict)，字段示例 (来自你的实测):

        {
          "COMPANY_ABBR_EN":   "SPD BANK",                 # 公司英文简称
          "STOCK_TYPE":        "1",                        # 股票类别 (1=A股)
          "LIST_BOARD":        "1",                        # 板块类型 (1=主板, 2=科创板 等，具体以官方为准)
          "COMPANY_ABBR":      "浦发银行",                 # 公司简称
          "A_STOCK_CODE":      "600000",                   # A股代码
          "AREA_NAME":         "310000",                   # 地区代码 (行政区划代码)
          "DELIST_DATE":       "-",                        # 退市日期 (未退市为 "-")
          "SEC_NAME_CN":       "浦发银行",                 # 证券简称(中文)
          "AREA_NAME_DESC":    "上海市",                   # 地区名称
          "FULL_NAME_IN_ENGLISH": "Shanghai Pudong Development Bank Co.,Ltd.",  # 公司英文全称
          "SEC_NAME_FULL":     "浦发银行",                 # 证券全称(中文)
          "STATE_CODE":        "2",                        # 公司状态代码 (见 company_status)
          "B_STOCK_CODE":      "-",                        # B股代码 (如有)
          "STATE_CODE_STOCK":  "4",                        # 股票状态代码 (细分状态)
          "LIST_DATE":         "19991110",                 # 上市日期 (YYYYMMDD)
          "CSRC_CODE":         "J",                        # 证监会行业编码 (字母+分类)
          "PRODUCT_STATUS":    "   D  F  N          ",     # 产品状态组合标识 (多位编码)
          "CSRC_CODE_DESC":    "金融业",                   # 证监会行业名称
          "COMPANY_CODE":      "600000",                   # 公司代码
          "FULL_NAME":         "上海浦东发展银行股份有限公司"  # 公司全称(中文)
        }

      DataFrame 结构说明:

        - 列名: 与原始 JSON 字段保持一致，不做重命名或转换
        - 行数: 取决于 page_size 和 page_no (分页参数)
        - 空值: 若字段为 "-" 或不存在，将以原样或 NaN 表示

    使用示例:

      >>> from backend.datasource.providers.sse_official_adapter import get_stock_list_sh_official
      >>> df = await get_stock_list_sh_official()
      >>> df.head()

    注意事项:

      - 本函数只负责“拉取原始数据”，不做任何字段标准化或清洗。
        若需统一转换为 symbol / name / market 等字段，请在 normalizer 层处理。
      - 若需要自动重试，会通过 async_retry_call 对网络错误进行指数退避重试。
      - 该函数已被 limit_async_network_io 装饰，受全局异步令牌桶约束。
    """

    # ---- 构造查询参数 ----
    base_url = "https://query.sse.com.cn/sseQuery/commonQuery.do"

    # ===== 步骤1：生成动态参数（防缓存/防冲突）=====
    callback_name = generate_jsonp_callback("jsonpCallback")
    timestamp = generate_cache_buster()

    # ===== 步骤2：构造查询参数（个性化部分）=====
    params = {
        ""
        # === 必填业务参数 ===
        "STOCK_TYPE": "",  # str ，股票类别过滤， (1=主板A股，2=主板B股，8=创业板，空=全部)
        "REG_PROVINCE": "",  # str ，省份过滤 (六位数字省份编码，空=全部)
        "CSRC_CODE": "",  # str ，证监会行业代码过滤 (空=全部)
        "STOCK_CODE": "",  # 股票代码过滤 (空=全部)
        "COMPANY_STATUS":
        "2,4,5,7,8",  # str ，公司状态过滤（以半角逗号分隔的状态码），"2,4,5,7,8"为官网默认设置，每个数字具体含义待确认，留空""会返回更多

        # === 上交所内部参数（固定值，来源：官网 JS） ===
        "sqlId":
        "COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L",  # （固定不变）上交所内部预设好的 SQL 模板 ID，指示服务器执行哪段预定义查询，保持现状不能随意修改
        "type":
        "inParams",  # （固定不变）上交所预设查询参数类型，配合 sqlId 使用，一般是和后端的 Query 组件强绑定的开关，预先在页面里的 JS 里写死，保持现状不能随意修改

        # === 分页参数 ===，
        "isPagination":
        "false",  # 是否开启分页，true/false，为 true 时，pageHelp.* 参数生效。为 false 时，直接返回全量，不受分页数量限制

        # 以下分页参数仅"isPagination": "true" 时生效，留存备用
        "pageHelp.cacheSize": "1",
        "pageHelp.beginPage": "1",  # str，开始页码
        "pageHelp.pageSize":
        "2000",  # str，单页返回条数，分页生效时，实测最大值为2000，即便设置超过2000的数值，返回数量也被限制为2000
        "pageHelp.pageNo": "1",  # str，当前页码
        "pageHelp.endPage": "1",  # str，结束页码

        # === 动态参数（防缓存）===
        "jsonCallBack":
        callback_name,  # JSONP 回调名，格式：jsonpCallback + 8位随机数，外部函数生成，直接调用
        "_": timestamp,  # 防缓存时间戳 (13位毫秒)，外部函数生成，直接调用
    }

    # ===== 步骤3：生成通用参数（从 settings 池中随机选择）=====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()

    # ===== 步骤4：根据 UA 生成匹配的 sec-ch-ua =====
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    # ===== 步骤5：构造完整请求头 =====
    headers = {
        # === 个性化参数（接口专属，直接写死）===
        "Referer": "https://www.sse.com.cn/",  # 来源页（官网首页）
        "Accept": "*/*",  # 接受类型（与官网一致）
        "Host": "query.sse.com.cn",  # 目标主机

        # === 现代浏览器安全头（Chrome/Edge 必需，固定值）===
        "Sec-Fetch-Dest": "script",  # JSONP 请求固定为 script
        "Sec-Fetch-Mode": "no-cors",  # 跨域模式
        "Sec-Fetch-Site": "same-site",  # 同站请求（sse.com.cn → query.sse.com.cn）

        # === 通用参数（从 settings 池中随机选择）===
        "User-Agent": user_agent,
        "Accept-Language": accept_language,
        "Connection": connection,

        # === 浏览器压缩支持（固定值）===
        "Accept-Encoding": "gzip, deflate, br, zstd",
    }

    # === 补充 sec-ch-ua 系列（仅 Chrome/Edge 携带）===
    if sec_ch_ua:  # Firefox 返回空字符串，不添加
        headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?0"  # 非移动设备
        headers["sec-ch-ua-platform"] = '"Windows"'  # 操作系统

    # ===== 步骤6：执行请求 =====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(base_url, params=params, headers=headers)
            resp.raise_for_status()

            # 解析 JSONP
            data = strip_jsonp(resp.text, callback_name)

            # 提取数据行
            rows: List[Dict[str, Any]] = []

            if isinstance(data, dict):
                # 主路径：pageHelp.data
                if isinstance(data.get("pageHelp"), dict):
                    rows = data["pageHelp"].get(
                        "data") or data["pageHelp"].get("content", [])

                # 兜底路径：result
                if not rows and isinstance(data.get("result"), list):
                    rows = data["result"]

            # 记录结果
            if not rows:
                _LOG.warning("[上交所] 响应无数据行",
                             extra={
                                 "has_pageHelp": "pageHelp" in data,
                                 "has_result": "result" in data,
                                 "data_keys": list(data.keys()),
                                 "callback_name": callback_name,
                             })
                return pd.DataFrame()

            _LOG.info(f"[上交所] 成功获取 {len(rows)} 条记录",
                      extra={
                          "callback_name":
                          callback_name,
                          "user_agent_version":
                          user_agent.split("Chrome/")[1].split()[0]
                          if "Chrome/" in user_agent else "unknown",
                      })

            return pd.DataFrame(rows)

    # 使用统一异步重试工具（带反爬告警）
    df = await async_retry_call(_do_request)

    return df if df is not None else pd.DataFrame()
