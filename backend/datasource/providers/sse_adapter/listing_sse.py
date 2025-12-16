# backend/datasource/providers/sse_adapter/listing_sse.py
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

_LOG = get_logger("sse_adapter")

# ==============================================================================
# 1. 标的资产列表 (Asset Universe)
# ==============================================================================

# 1.1 上交所股票列表 (官方 JSONP 接口)


@limit_async_network_io
async def get_stock_list_sh_sse() -> pd.DataFrame:
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
      - 每行对应一条指数记录，字段示例（来自实测返回首行数据，实际字段以接口返回为准）:

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

      >>> from backend.datasource.providers.sse_adapter import get_stock_list_sh_sse
      >>> df = await get_stock_list_sh_sse()
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
    params: Dict[str, str] = {
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
    headers: Dict[str, str] = {
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
        "Accept-Encoding": "gzip, deflate",
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
            data = strip_jsonp(resp.text)

            # 提取数据行
            # 上交所此接口当 isPagination=false 时，数据直接在 result 下
            rows: List[Dict[str, Any]] = data.get("result")

            # 兼容性：如果 result 为空，再尝试找 pageHelp.data
            if not rows and isinstance(data.get("pageHelp"), dict):
                rows = data["pageHelp"].get("data")

            # 记录结果
            if not rows:
                _LOG.warning("[上交所] 股票列表响应无数据行",
                             extra={
                                 "data_keys": list(data.keys()),
                                 "has_result": "result" in data,
                                 "has_pageHelp": "pageHelp" in data,
                                 "callback_name": callback_name,
                             })
                return pd.DataFrame()

            _LOG.info(f"[上交所] 股票列表成功获取 {len(rows)} 条记录",
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


# 1.2 上交所基金列表 (官方 JSONP 接口)


@limit_async_network_io
async def get_fund_list_sh_sse() -> pd.DataFrame:
    """
    [基金列表] 从上交所官网获取在上交所上市的场内基金列表 (JSONP 接口 · V2.0 · isPagination=false 全量版)

    数据源:
      - 官网地址 (页面): https://etf.sse.com.cn/fundlist/
      - 接口地址 (API):  https://query.sse.com.cn/commonQuery.do

    V2.0 改动:
      - 接口统一为 COMMON_JJZWZ_JJLB_L（commonQuery.do），与 ETF 子站保持一致。
      - 明确固定 isPagination="false"，依赖服务器一次性返回全量数据，不再做分页聚合。
      - 删除原先 FUND_LIST (commonSoaQuery.do) 相关逻辑，避免两个接口混用。
      - 按抓包结果补全请求头与参数说明，并对每个字段给出语义注释。

    HTTP 方法:
      - GET

    请求参数说明（全部字段逐一说明，均通过 query string 传递）:

      一、核心业务参数:
        - sqlId: "COMMON_JJZWZ_JJLB_L"
            * 类型: str
            * 说明: 上交所内部 SQL 模板 ID，指定“场内基金列表”查询。
            * 要求: 固定值，不可修改。

        - type: "inParams"
            * 类型: str
            * 说明: 与 sqlId 配套的参数类型标记，来自官网 JS。
            * 要求: 固定值，不可修改。

        - isPagination: "false"
            * 类型: str
            * 取值: "true" / "false"
            * 说明: 是否启用分页。
                    - "false": 不分页，服务器直接返回全量结果在 result 下。
                    - "true" : 分页模式，需配合 pageHelp.* 使用（本函数不使用）。
            * 本实现: 固定为 "false"，依赖服务器一次性返回全量基金列表。

      二、过滤参数（全部留空表示“不过滤，取全量”）:
        - FUND_CODE: ""
            * 类型: str
            * 说明: 基金代码筛选，支持精确或模糊，留空表示不过滤所有代码。

        - COMPANY_NAME: ""
            * 类型: str
            * 说明: 基金管理人名称筛选，支持关键字模糊匹配。

        - INDEX_NAME: ""
            * 类型: str
            * 说明: 跟踪指数名称筛选，支持关键字模糊匹配。

        - START_DATE: ""
            * 类型: str
            * 格式: "YYYY-MM-DD"
            * 说明: 上市日期起始，留空表示不限制起始日期。

        - END_DATE: ""
            * 类型: str
            * 格式: "YYYY-MM-DD"
            * 说明: 上市日期结束，留空表示不限制结束日期。

        - CATEGORY: "F000"
            * 类型: str
            * 说明: 基金大类编码。
                    - 实测 "F000" 对应 ETF 类产品；
                    - 其他编码对应其他类型场内基金（具体以官网为准）。
            * 本实现: 固定为 "F000"，仅获取 ETF 类场内基金。

        - SUBCLASS: ""
            * 类型: str
            * 说明: 基金子类编码过滤（如行业 / 主题子类），留空=全部子类。

        - SWING_TRADE: ""
            * 类型: str
            * 取值: "" / "是" / "否"
            * 说明: “当日回转交易基金”（T+0）过滤参数。
                    - "" : 不过滤，返回全部；
                    - "是": 仅返回支持当日回转的基金；
                    - "否": 排除当日回转基金。

        - CATEGORY_ASC: "1"
            * 类型: str
            * 说明: 分类排序开关，来自官网预设，留作兼容使用。
            * 本实现: 固定为 "1"。

      三、分页参数（本函数关闭分页，仅为兼容预留，不参与逻辑）:
        - pageHelp.cacheSize: "1"
            * 类型: str
            * 说明: 分页缓存大小，isPagination="false" 时无效，保留以兼容服务端解析。

        - pageHelp.pageSize: "2000"
            * 类型: str
            * 说明: 单页条数。仅 isPagination="true" 时生效；
                    isPagination="false" 时通常被服务器忽略。
            * 本实现: 设为 "2000" 以保持与其他接口习惯一致，不影响实际行为。

        - pageHelp.pageNo: "1"
            * 类型: str
            * 说明: 当前页码。仅分页模式时使用，本实现固定为 "1"。

        - pageHelp.beginPage: "1"
            * 类型: str
            * 说明: 起始页码。分页模式下有效，本实现固定为 "1"。

        - pageHelp.endPage: "1"
            * 类型: str
            * 说明: 结束页码。分页模式下有效，本实现固定为 "1"。

      四、动态参数（JSONP / 防缓存）:
        - jsonCallBack:
            * 类型: str
            * 示例: "jsonpCallback12345678"
            * 说明: JSONP 回调函数名，服务器会返回 "jsonCallBack( {...} )" 形式的响应。
                    需要在客户端用同名回调或自行去壳解析。
            * 本实现: 通过 generate_jsonp_callback("jsonpCallback") 动态生成。

        - _: 
            * 类型: str
            * 示例: "1764422561953"
            * 说明: 13 位毫秒时间戳，作为防缓存参数，避免浏览器 / 中间缓存命中旧结果。
            * 本实现: 通过 generate_cache_buster() 动态生成。

    请求头字段说明（本函数中设置的所有 Header）:

      - Referer: "https://etf.sse.com.cn/"
          * 说明: 来源页面 URL，与浏览器抓包保持一致，有助于降低被误判为机器人。

      - Accept: "*/*"
          * 说明: 接受任意类型的响应内容。

      - Host: "query.sse.com.cn"
          * 说明: 目标主机名，HTTP/1.1 必需。

      - Sec-Fetch-Dest: "script"
          * 说明: 表示这是一个 script（JSONP）请求。

      - Sec-Fetch-Mode: "no-cors"
          * 说明: 跨域模式设置，与官网行为一致。

      - Sec-Fetch-Site: "same-site"
          * 说明: 表示请求来源与目标同属一个站点族 (sse.com.cn → query.sse.com.cn)。

      - User-Agent: <从 spider_config.user_agents 池中随机选择>
          * 说明: 模拟真实浏览器 UA，支持多种版本的 Chrome/Edge/Firefox。

      - Accept-Language: <从 spider_config.accept_languages 池中随机选择>
          * 说明: 语言偏好头，常见形式如 "zh-CN,zh;q=0.9,en;q=0.8"。

      - Connection: <从 spider_config.connection_types 池中随机选择>
          * 说明: 连接类型，"keep-alive" 为主，"close" 偶尔夹杂。

      - Accept-Encoding: "gzip, deflate, br, zstd"
          * 说明: 支持的压缩编码，减少带宽占用。

      - Cache-Control: "no-cache"
      - Pragma: "no-cache"
          * 说明: 明确要求中间节点不要缓存响应。

      - sec-ch-ua / sec-ch-ua-mobile / sec-ch-ua-platform:
          * 说明: 仅在 UA 为 Chrome/Edge 时设置，用于模拟真实浏览器环境。

    返回数据说明（字段对应响应 JSON 中 result / pageHelp.data 内的每一条记录）:

      每条记录为一个 dict，典型字段如下（根据实测返回，实际字段以接口返回为准）:

        {
          "COMPANY_NAME":        "银河基金管理有限公司",
              - 类型: str
              - 含义: 基金管理人全称。

          "FUND_CODE":           "530880",
              - 类型: str
              - 含义: 基金代码（6 位数字），不带市场前缀。

          "CATEGORY":            "F111",
              - 类型: str
              - 含义: 基金分类代码（大类 + 子类），如 F111 等，具体含义以上交所字典为准。

          "NUM":                 "1",
              - 类型: str（序号）
              - 含义: 行序号，一般按当前排序规则从 1 递增。

          "FUND_ABBR":           "上证红利",
              - 类型: str
              - 含义: 基金简称（展示用名称）。

          "COMPANY_CODE":        "900064",
              - 类型: str
              - 含义: 管理人内部编号。

          "INDEX_NAME":          "上证国有企业红利指数",
              - 类型: str
              - 含义: 基金跟踪的标的指数名称。

          "FUND_EXPANSION_ABBR": "红利ETF国企",
              - 类型: str
              - 含义: 基金扩展简称，一般为更易识别的市场名称。

          "SCALE":               "0.5262",
              - 类型: str
              - 含义: 基金最新规模（单位为“亿”，精确数值含 4 位小数）。
                        例如 "0.5262" 表示 0.5262 亿元。
                        注: 本函数不做类型转换，保持为字符串，由上游统一解析。

          "LISTING_DATE":        "2024-11-12"
              - 类型: str
              - 格式: "YYYY-MM-DD"
              - 含义: 基金在上交所上市交易的日期。
        }

      DataFrame 结构说明:
        - 每一行对应一只基金，上述字段名直接作为 DataFrame 列名。
        - 不做字段重命名或单位换算，保持与原始 JSON 一致。
        - 若接口本身返回更多字段，本函数会一并保留。

    行为说明:
      - 本函数仅负责:
          * 构造请求参数与请求头（基于 spider_toolkit 和抓包结果）；
          * 发起 HTTP 请求（使用 async_retry_call 提供指数退避重试与反爬告警）；
          * 使用 strip_jsonp 去除 JSONP 外壳，得到 Python dict；
          * 从 data["result"] 或 data["pageHelp"]["data"] 中提取记录行，并构造 DataFrame。
      - 不做字段语义解释与标准化，统一交由 normalizer 层处理。
      - 若响应中无有效数据行，则返回空 DataFrame，并输出 warning 日志。

    Returns:
        pandas.DataFrame:
          - 正常情况: 多行基金记录。
          - 接口无数据 / 解析失败: 空 DataFrame。

    使用示例:

      >>> from backend.datasource.providers.sse_adapter import get_fund_list_sh_sse
      >>> df = await get_fund_list_sh_sse()
      >>> df.head()

    注意:
      - 本函数只负责 HTTP 请求 + JSONP 解包 + 分页整合 + DataFrame 构造。
      - 不做字段清洗或业务语义解释（如 ETF/LOF 分类、规模单位转换等）。
      - 若任何一步出现异常或所有页均无数据，将返回空 DataFrame，并在日志中记录详细原因。
    """

    # ---- 基础接口地址 ----
    base_url = "https://query.sse.com.cn/commonQuery.do"

    # ===== 步骤1：生成动态参数（JSONP 回调 & 防缓存时间戳）=====
    callback_name = generate_jsonp_callback("jsonpCallback")  # JSONP 回调名
    timestamp = generate_cache_buster()  # 13 位毫秒时间戳

    # ===== 步骤2：构造查询参数（一次性全量拉取，isPagination=false）=====
    params: Dict[str, str] = {
        # === 核心业务参数（与 ETF 子站抓包保持一致）===
        "sqlId": "COMMON_JJZWZ_JJLB_L",  # str，必填；上交所内部 SQL 模板 ID，固定为“场内基金列表”查询模板
        "type": "inParams",              # str，必填；参数类型标记，来自官网 JS，需与 sqlId 一起使用


        # --- 过滤条件（全部留空表示全量）---
        "FUND_CODE": "",                 # str，可选；基金代码筛选（支持精确或模糊），留空 = 不按代码过滤
        "COMPANY_NAME": "",              # str，可选；基金管理人名称关键字过滤，如 "华夏"、"易方达"，留空 = 不按管理人过滤
        "INDEX_NAME": "",                # str，可选；跟踪指数名称关键字过滤，如 "上证50指数"、"上证红利指数"，留空 = 不按指数过滤
        "START_DATE": "",                # str，可选；上市起始日期过滤，格式 "YYYY-MM-DD"（例如 "2024-01-01"），留空 = 不限制起始日期
        "END_DATE": "",                  # str，可选；上市结束日期过滤，格式 "YYYY-MM-DD"，留空 = 不限制结束日期
        "CATEGORY": "",              # str，可选；基金大类代码：
                                         #   - "F000": ETF 基金（你抓包场景使用的值）
                                         #   - 其他取值对应不同类型的场内基金（具体含义参考上交所基金字典）
                                         # 若希望拉取全部场内基金，可改为 ""（不过滤）

        "SUBCLASS": "01,02,03,04,06,08,09,31,32,33,34,35,36,37,38",          # str，可选；基金子类代码集合，多个值用英文逗号分隔，来自你提供链接中的：
                                         #   - "09": 20% 涨跌幅比例相关子类（实测为“20%涨跌幅基金”配置之一）
                                         #   - "31": 20% 涨跌幅比例相关子类（搭配 09/15 一起筛出 20% 涨跌幅 ETF）
                                         #   - "15": 20% 涨跌幅比例相关子类
                                         # 在原 FUND_LIST 接口语义中，subClass = 09,15,31 代表“20%涨跌幅比例基金”；
                                         # 在 COMMON_JJZWZ_JJLB_L 中，SUBCLASS 延续同一含义：
                                         #   → 当前组合表示：在 CATEGORY=F000 (ETF) 中仅筛选“20% 涨跌幅 ETF”子类
                                         # 若希望不过滤子类，可以改为 ""（留空 = ETF 全部子类）

        "SWING_TRADE": "",             # str，可选；是否为“当日回转交易基金”（T+0）过滤：
                                         #   - "是": 只保留支持当日买入当日卖出的基金（T+0 基金）
                                         #   - "否": 排除所有当日回转基金
                                         #   - "":   不按是否 T+0 过滤（全部保留）
                                         # 你提供的链接使用 SWING_TRADE=是：
                                         #   → 当前组合表示：只要“支持当日回转”的 20% 涨跌幅 ETF

        "CATEGORY_ASC": "",             # str，可选；分类排序开关，实测 ETF 子站默认传 "1"。
                                         # 一般表示按类别字段升序排列，具体排序逻辑由后端控制，保持该默认即可。

        # --- 分页参数（关闭分页，仅保留以兼容服务端解析）---
        "isPagination": "false",
        "pageHelp.cacheSize": "1",
        "pageHelp.pageSize": "2000",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.endPage": "1",

        # 动态参数（JSONP / 防缓存）
        "jsonCallBack": callback_name,  # JSONP 回调名，需与解析时一致
        "_": timestamp,  # 防缓存时间戳（毫秒）
    }

    # ===== 步骤3：生成通用请求头（从配置池随机选择）=====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers: Dict[str, str] = {
        # 个性化头（接口专属，来自 ETF 子站抓包）
        "Referer": "https://etf.sse.com.cn/",  # ETF 子站为主要入口
        "Accept": "*/*",  # 接受类型（与官网一致）
        "Host": "query.sse.com.cn",  # 目标主机

        # === 现代浏览器安全头（Chrome/Edge 必需，固定值）===
        "Sec-Fetch-Dest": "script",  # JSONP 请求固定为 script
        "Sec-Fetch-Mode": "no-cors",  # 跨域模式
        "Sec-Fetch-Site": "same-site",  # 同站请求（sse.com.cn → query.sse.com.cn）

        # 通用头（从 UA 池中随机选择）
        "User-Agent": user_agent,
        "Accept-Language": accept_language,
        "Connection": connection,

        # 压缩支持
        "Accept-Encoding": "gzip, deflate",

        # 显式关闭缓存（与浏览器抓包一致）
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    # 补充 sec-ch-ua 系列（仅 Chrome/Edge 携带）
    if sec_ch_ua:
        headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?0"  # 非移动设备
        headers["sec-ch-ua-platform"] = '"Windows"'  # 操作系统（与 UA 对应）

    _LOG.info(
        "[上交所] 基金列表开始拉取（isPagination=false）",
        extra={
            "sqlId": params["sqlId"],
            "CATEGORY": params["CATEGORY"],
            "isPagination": params["isPagination"],
            "callback": callback_name,
        },
    )

    # ===== 步骤4：执行请求（单次，全量）=====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(base_url, params=params, headers=headers)
            resp.raise_for_status()

            # 解析 JSONP → dict
            data = strip_jsonp(resp.text)

            # 优先从 result 读取，其次回退 pageHelp.data（兼容服务端实现差异）
            rows: List[Dict[str, Any]] = data.get("result") or []
            if not rows and isinstance(data.get("pageHelp"), dict):
                rows = data["pageHelp"].get("data") or []

            # 无数据行时记录 warning
            if not rows:
                _LOG.warning(
                    "[上交所] 基金列表响应无数据行",
                    extra={
                        "sqlId": params["sqlId"],
                        "CATEGORY": params["CATEGORY"],
                        "has_result": isinstance(data.get("result"), list),
                        "has_pageHelp": isinstance(data.get("pageHelp"), dict),
                        "data_keys": list(data.keys())
                        if isinstance(data, dict) else None,
                        "callback": callback_name,
                    },
                )
                return pd.DataFrame()

            # 正常情况：记录成功日志
            _LOG.info(
                "[上交所] 基金列表成功获取 %d 条记录（单次，全量）",
                len(rows),
                extra={
                    "sqlId": params["sqlId"],
                    "CATEGORY": params["CATEGORY"],
                    "callback": callback_name,
                    "user_agent_version": (
                        user_agent.split("Chrome/")[1].split()[0]
                        if "Chrome/" in user_agent else "unknown"
                    ),
                },
            )

            return pd.DataFrame(rows)

    # 使用统一异步重试工具（带反爬告警与指数退避）
    df = await async_retry_call(_do_request)

    # 统一返回 DataFrame（空则返回空表）
    return df if df is not None else pd.DataFrame()


# 1.3 上交所指数列表 (官方 JSONP 接口)


@limit_async_network_io
async def get_index_list_sh_sse() -> pd.DataFrame:
    """
    [指数列表] 从上交所官网获取上证指数列表 (JSONP 接口 · V1.0)

    数据源:
      - 官网地址 (页面): https://www.sse.com.cn/
      - 接口地址 (API):  https://query.sse.com.cn/commonSoaQuery.do

    说明:
      - 基于 DB_SZZSLB_ZSLB 接口的官方 JSONP 调用。
      - 本函数仅负责 HTTP 请求 + JSONP 解包 + DataFrame 构造，
        不做任何字段重命名或业务级清洗（由 normalizer 层处理）。

    返回数据:
      - 类型: pandas.DataFrame
      - 每行对应一条指数记录，字段示例（来自实测返回首行数据，实际字段以接口返回为准）:

        {
          "indexCode": "000001",                # 指数代码（价格指数代码，展示用）
          "indexName": "上证指数",              # 指数名称（中文简称）
          "indexFullName": "上证综合指数",      # 指数中文全称
          "indexNameEn": "SSE Index",           # 指数英文简称
          "indexFullNameEn": "SSE Composite Index",  # 指数英文全称

          "indexBaseDay": "1990-12-19",         # 基点日期（YYYY-MM-DD）
          "indexBasePoint": 100,                # 基点（基准点位）
          "launchDay": "19910715",              # 发布/上线日期（YYYYMMDD）
          "numOfStockes": 2237,                 # 成份证券数量
          "indexDataSourceType": 1,             # 指数数据来源类型
          "indexReleaseChannel": 1,             # 指数发布渠道

          "isPriceIndex": 1,                    # 是否价格指数（1=是）
          "isTotalReturnIndex": 1,              # 是否有总收益指数
          "isNetLncomeIndex": 0,                # 是否有净收益指数

          "tIndexCode": "000888",               # 总收益指数代码
          "tIndexName": "上证收益",              # 总收益指数简称（中文）
          "tIndexFullName": "上证综合全收益指数", # 总收益指数中文全称
          "tIndexNameEn": "SSE TR",             # 总收益指数英文简称
          "tIndexFullNameEn": "SSE Composite Total Return Index",  # 总收益指数英文全称

          "ifIndexCode": "000001",              # 对应价格指数代码（通常与 indexCode 一致）

          "indicsSeq": 0,                       # 指数序列号 / 分类序号
          "indicsSeqDesc": "规模指数",          # 指数类别描述（中文，如“规模指数”）
          "indicsSeqDescEn": "Size Index",      # 指数类别描述英文

          "intro": "上证综合指数由在上海证券交易所上市的符合条件的股票与存托凭证组成样本，反映整体表现。",
                                               # 指数中文简介（省略号代表长文本）
          "introEn": "SSE Composite Index is composed of all eligible stocks and CDRs listed on Shanghai Stock Exchange...",
                                               # 指数英文简介
          "totalReturnIntro": "",               # 总收益指数中文简介（如有）
          "totalReturnIntroEn": "",             # 总收益指数英文简介（如有）
          "netReturnIntro": "",                 # 净收益指数中文简介（如有）
          "netReturnIntroEn": "",               # 净收益指数英文简介（如有）

          "methodologyName": "/market/sseindex/indexlist/indexdetails/indexmethods/c1/000001_000001_CN.pdf",
                                               # 指数编制方案 PDF（中文，站内相对路径）
          "methodologyNameEn": "/indices/indices/list/indexmethods/c/000001_000001en_EN.pdf",
                                               # 指数编制方案 PDF（英文，站内相对路径）
          "handbookUrl": "",                    # 指数手册 PDF（中文，如有）
          "handbookEnUrl": "",                  # 指数手册 PDF（英文，如有）

          "updateTime": "20250901",             # 指数信息更新时间（YYYYMMDD）

          # 以下为备用/预留字段，部分指数可能使用：
          "nIndexCode": "",                     # 净收益指数代码（如有）
          "nIndexName": "",                     # 净收益指数简称（中文）
          "nIndexFullName": "",                 # 净收益指数中文全称
          "nIndexNameEn": "",                   # 净收益指数英文简称
          "nIndexFullNameEn": ""                # 净收益指数英文全称
        }
    """
    # ---- 基础接口地址 ----
    base_url = "https://query.sse.com.cn/commonSoaQuery.do"

    # ===== 步骤1：生成动态参数（防缓存/防冲突）=====
    callback_name = generate_jsonp_callback("jsonpCallback")
    timestamp = generate_cache_buster()

    # ===== 步骤2：构造查询参数（全部在此硬编码，便于后续手工调整）=====
    params: Dict[str, str] = {
        # === 必填业务参数 ===
        # 上交所内部 SQL 模板 ID（固定值，对应“上证指数列表”查询）
        "sqlId": "DB_SZZSLB_ZSLB",

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
        "pagecache":
        "false",  # 是否使用页面缓存的控制参数，false为每次查询都走后端，true可能命中前端缓存（不建议在爬虫中开启）

        # === 动态参数（JSONP/防缓存）===
        "jsonCallBack": callback_name,  # JSONP 回调名
        "_": timestamp,  # 13 位毫秒时间戳
    }

    # ===== 步骤3：生成通用请求头（从配置池随机选择）=====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers: Dict[str, str] = {
        # 个性化参数（接口专属，直接写死）
        "Referer": "https://www.sse.com.cn/",
        "Accept": "*/*",
        "Host": "query.sse.com.cn",

        # 现代浏览器安全头（固定值）
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",

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

    # ===== 步骤4：执行请求 =====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(base_url, params=params, headers=headers)
            resp.raise_for_status()

            # 解析 JSONP → dict
            data = strip_jsonp(resp.text)

            # 提取数据行，兼容解析
            rows: List[Dict[str, Any]] = data.get("result")
            if not rows and isinstance(data.get("pageHelp"), dict):
                rows = data["pageHelp"].get("data")

            if not rows:
                _LOG.warning(
                    "[上交所] 指数列表响应无数据行",
                    extra={
                        "has_pageHelp":
                        isinstance(data.get("pageHelp"), dict),
                        "has_result":
                        isinstance(data.get("result"), list),
                        "data_keys":
                        list(data.keys()) if isinstance(data, dict) else None,
                        "callback_name":
                        callback_name,
                    },
                )
                return pd.DataFrame()

            _LOG.info(
                f"[上交所] 指数列表成功获取 {len(rows)} 条记录",
                extra={
                    "callback_name":
                    callback_name,
                    "user_agent_version":
                    (user_agent.split("Chrome/")[1].split()[0]
                     if "Chrome/" in user_agent else "unknown"),
                },
            )

            return pd.DataFrame(rows)

    # 使用统一异步重试工具（带反爬告警）
    df = await async_retry_call(_do_request)

    return df if df is not None else pd.DataFrame()
