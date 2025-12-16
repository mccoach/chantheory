# backend/datasource/providers/szse_adapter/listing_szse.py
# ==============================
# V2.0 - 深交所股票列表适配器（精准 TABKEY 版 · 结构变更即报错）
#
# 说明:
#   - 职责：封装对“深交所官网 JSON 接口”的直接调用。
#   - 风格：严格对齐 sse_adapter.py 的实现风格与职责边界：
#       * 对上层暴露 async 函数
#       * 底层使用 httpx.AsyncClient 发起 HTTP 请求
#       * 使用全局异步限流器 limit_async_network_io
#       * 使用 async_retry_call 实现指数退避重试与反爬告警
#       * User-Agent / Accept-Language / Connection / sec-ch-ua 均通过 spider_toolkit 统一管理
#   - 不做的事：
#       * 不做字段标准化（交由 normalizer 层处理）
#       * 不做任何 DB 写入（交由 db / async_writer 处理）
#       * 不合并业务逻辑（仅针对一个“标的列表”原子接口）
#       * 不做 JSONP 脱壳，直接 resp.json()（实测为纯 JSON）
#
# 数据源（基于浏览器抓包实测）:
#   页面: https://www.szse.cn
#
# “参数包络”设计（本实现的唯一 params 模板）:
#   - 将以上所有请求中出现过的参数键名统一纳入同一个 params 字典中：
#       * SHOWTYPE
#       * CATALOGID
#       * loading
#       * TABKEY
#       * random
#   - 值的具体取值可以后续根据业务手工调整，本实现只给出一个合理的默认组合：
#       * SHOWTYPE="JSON"
#       * CATALOGID="1110"
#       * loading="first"     （默认视为“主板/首次加载”；如需切 TAB 可手工改为 ""）
#       * TABKEY=""           （默认主 TAB；如需 tab2/tab3 可手工改值）
#       * random=<0~1随机数>  （每次请求动态生成）
#   - 这样，后续你只需改动 params 内的具体值，即可重放任意一个抓包场景，
#     而无需再修改代码结构。
# ==============================

from __future__ import annotations

from typing import Dict, Any, List, Optional

import pandas as pd
import httpx
import random

from backend.utils.async_limiter import limit_async_network_io
from backend.utils.async_retry import async_retry_call
from backend.utils.logger import get_logger, log_event

# 导入爬虫工具包
from backend.utils.spider_toolkit import (
    pick_user_agent,  # 随机选择 UA
    pick_accept_language,  # 随机选择语言
    pick_connection,  # 随机选择连接方式
    generate_sec_ch_ua,  #生成 sec-ch-ua 头
    xlsx_bytes_to_json_records,  # 新增：XLSX → JSON 解析
)

_LOG = get_logger("szse_adapter")

# ==============================================================================
# 1. 标的资产列表 (Asset Universe)
# ==============================================================================

# 1.1 深交所股票列表 (官方 JSON 接口)


@limit_async_network_io
async def get_stock_list_sz_szse(showtype: str = "xlsx") -> pd.DataFrame:
    """
    [股票列表] 从深交所官网获取股票列表 (JSON 接口 · 精准 TABKEY 版 + XLSX 全量版)

    数据源:
      - 官网地址 (页面): https://www.szse.cn/market/product/stock/list/index.html
      - JSON 接口:  https://www.szse.cn/api/report/ShowReport/data
      - XLSX 导出: https://www.szse.cn/api/report/ShowReport  （去掉末尾 /data）

    当前策略：
      - 只拉取 A 股列表，对应 TABKEY="tab1"。
      - 虽然返回结构中包含 4 块（A股/B股/CDR/A+B），但实测只有 TABKEY 对应的那一块有数据，
        其他块的 data 为空。因此本函数只需要从所有块中找到
        metadata.tabkey == "tab1" 的那一块，提取其 data 即可。
      - 默认使用 XLSX 导出接口一次性获取全量数据（showtype='xlsx'）。
      - 如需保留原 JSON 行为，可显式传入 showtype='JSON'。

    行为说明（按你的“结构变就炸”的要求实现）：
      1. 使用 resp.json() 解析响应为 Python 对象（不做 JSONP 脱壳）。
      2. 严格假定顶层结构为 list；否则立刻抛异常。
      3. 在列表中查找 metadata.tabkey == "tab1" 的 block：
           - 若找不到，抛异常（视为接口结构变更或行为异常）。
           - 若找到：
               - 要求 block["data"] 必须是 list，否则抛异常。
               - 若 data 为空列表，也抛异常（正常情况下 A 股列表不应为空）。
               - 对 data 中每一条记录 r，增加字段：
                     r["gplb"] = metadata["name"].replace("列表", "")
                 然后合成为一个 DataFrame 返回。
      4. 不做任何兜底返回空表的逻辑，让问题在日志和调用栈中清晰暴露。
    HTTP 方法:
      - GET

    返回数据:
      - 类型: pandas.DataFrame
      - 每行对应一条指数记录，字段示例（来自实测返回首行数据，实际字段以接口返回为准）:

        {
            "板块": "主板",                 // 股票所属板块 (如主板、创业板、科创板等)
            "公司全称": "平安银行股份有限公司",   // 公司的法定全称
            "英文名称": "Ping An Bank Co., Ltd.",          // 公司的官方英文名称
            "注册地址": "广东省深圳市罗湖区深南东路5047号",   // 公司的法定注册地址
            "A股代码": "000001",               // A 股代码 (深交所 A 股代码，6 位数字)
            "A股简称": "平安银行",              // A 股证券简称 (原始数据含深交所官网跳转链接，实际中文简称为"平安银行")
            "A股上市日期": "1991-04-03",           // A 股上市日期 (格式：YYYY-MM-DD)
            "A股总股本": "19,405,918,198",       // A 股总股本 (单位：股)      
            "A股流通股本": "19,405,600,653",       // A 股流通股本 (单位：股)         
            "B股代码": "",            // B 股代码 (上交所/深交所 B 股代码，通常以 900 或 200 开头)
            "B股简称": "",            // B 股证券简称
            "B股上市日期": "",        // B 股上市日期 (格式：YYYY-MM-DD)
            "B股总股本": "0",         // B 股总股本 (单位：股)
            "B股流通股本": "0",       // B 股流通股本 (单位：股)
            "地区": "华南",             // 公司所属的大区域 (如华北、华东、华南等)
            "省份": "广东",             // 公司注册地址所在的省级行政区
            "城市": "深圳市",           // 公司注册地址所在的城市
            "所属行业": "J 金融业",     // 所属行业信息 (J 为行业编码，"金融业" 为行业名称，对应证监会行业分类)
            "公司网址": "bank.pingan.com",    // 公司官方网站的 URL
            "未盈利": "-",            // 盈利标志 (未披露或无相关标识时显示为 "-")
            "具有表决权差异安排": "-",        // 是否具有表决权差异 (未标注或无相关信息时显示为 "-")
            "具有协议控制架构": "-",        // 公司控制架构类型 (未披露或无相关分类时显示为 "-")
            "股票类别": "A股"          // 股票类别（A股/B股/CDR/A+B股，由metadata字段提取合并）
        }

      DataFrame 结构说明:

        - 列名: 与原始 JSON 字段保持一致，不做重命名或转换
        - 行数: 取决于 page_size 和 page_no (分页参数)
        - 空值: 若字段为 "-" 或不存在，将以原样或 NaN 表示

    使用示例:

      >>> from backend.datasource.providers.szse_adapter import get_stock_list_sz_szse
      >>> df = await get_stock_list_sz_szse()
      >>> df.head()

    注意事项：
      - 本函数只负责“拉取原始数据 + 精准取出某一块 + 把 metadata 中的类别信息下沉到行级”。
        不做字段标准化或进一步业务逻辑。
        若需统一转换为 symbol / name / market 等字段，请在 normalizer 层处理。
      - 若需要自动重试，会通过 async_retry_call 对网络错误进行指数退避重试。
      - 该函数已被 limit_async_network_io 装饰，受全局异步令牌桶约束。
    """

    # ---- 归一化 SHOWTYPE 并决定是否走 XLSX 路径 ----
    showtype_normalized = str(showtype or "xlsx").strip().lower()
    use_xlsx = showtype_normalized != "json"

    # ---- 构造查询参数 ----
    base_url = ("https://www.szse.cn/api/report/ShowReport" if use_xlsx else
                "https://www.szse.cn/api/report/ShowReport/data")

    # ===== 步骤1：生成动态参数（防缓存/防冲突）=====
    # 生成一个 0~1 之间的随机浮点数，作为防缓存随机因子。
    # 注意：并不要求与浏览器的具体数值相同，只需保证每次请求不同即可。
    rand_value = str(random.random())

    # ===== 步骤2：构造查询参数（个性化部分）=====
    params: Dict[str, str] = {
        "SHOWTYPE": "xlsx" if use_xlsx else
        "JSON",  # 告知服务端以 xlsx（默认）/JSON 形式返回数据。JSON会有强制分页限制，无法一次性拉取全量，因此默认以xlsx。
        "CATALOGID": "1110",  # 深交所内部报表模板 ID，"1110" 对应股票列表。
        "loading":
        "first",  # 标记“首次加载”（loading=first），其他 TAB 请求中该参数通常缺失。为了统一参数键名，这里始终携带 loading，可以手工改为 "" 或移除。
        "TABKEY":
        "tab1",  # 指定列表页面中具体的 TAB 页（根据深交所官网实测，tab1=A股列表，tab2=B股列表，tab3=CDR列表，tab4=A+B股列表，除上述四种以外的其他任意参数都会按tab1返回A股列表）
        "txtDMorJC": "",  # 股票代码或简称筛选，关键字模糊查询，留空为全量
        "selectHylb":
        "",  # 行业类别筛选，在官网实测返回数据元信息 pd.["metadata"]["conditions"][1]["options"] 中有详细的全量列表，留空为不筛选的全量
        "selectModule": "",  # 板块筛选（main = 主板, nm = 创业板, 留空 = 全量）
        "txtShengorShi": "",  # 省市或地市名称筛选，关键字模糊查询，留空为全量
        "PAGENO": "",  # 当前页码，与上交所不同，深交所请求参数中未包含分页开关，首次访问页面时请求参数中未包含页码，
        "random":
        rand_value,  # 防缓存随机数，示例: "0.21651426864522294"，每次请求不同（类似浏览器中的 cache buster）。使用 random.random() 动态生成 0~1 之间的浮点数字符串即可。
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
        "Referer":
        "https://www.szse.cn/market/product/stock/list/index.html",  # 来源页（官网首页）
        "Accept":
        "application/json, text/javascript, */*; q=0.01",  # 接受类型（与官网一致）
        "Host": "www.szse.cn",  # 目标主机

        # === 现代浏览器安全头（Chrome/Edge 必需，官网固定值）===
        "Sec-Fetch-Dest": "empty",  # XHR / fetch 请求
        "Sec-Fetch-Mode": "cors",  # cors 模式
        "Sec-Fetch-Site": "same-origin",  # 同站请求

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

    log_event(
        logger=_LOG,
        service="szse_adapter",
        level="INFO",
        file=__file__,
        func="get_stock_list_sz_szse",
        line=0,
        trace_id=None,
        event="szse.stock_list.start",
        message="[深交所] 开始拉取股票列表",
        extra={
            "params": params,
            "use_xlsx": use_xlsx
        },
    )

    # ===== 步骤6：执行请求（结构变化即抛异常） =====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(base_url, params=params, headers=headers)
            resp.raise_for_status()

            # 分支1：XLSX 全量导出路径
            if use_xlsx:
                records = xlsx_bytes_to_json_records(resp.content)
                if not records:
                    _LOG.warning(
                        "[深交所] XLSX 响应无数据行",
                        extra={
                            "tabkey": params["TABKEY"],
                            "showtype": params["SHOWTYPE"],
                        },
                    )
                    return pd.DataFrame()

                # 保持与 JSON enrich 后语义一致：如无 gplb，则补一个“A股”
                if records and all("gplb" not in r for r in records):
                    for r in records:
                        r["股票类别"] = "A股"

                df = pd.DataFrame(records)

                _LOG.info(
                    "[深交所] XLSX 股票列表成功获取 %d 条记录",
                    len(df),
                    extra={
                        "tabkey":
                        params["TABKEY"],
                        "showtype":
                        params["SHOWTYPE"],
                        "user_agent_version":
                        (user_agent.split("Chrome/")[1].split()[0]
                         if "Chrome/" in user_agent else "unknown"),
                    },
                )
                return df

            # 分支2：原 JSON 路径（保持现有“结构变就炸”语义）
            # 实测深交所返回数据未套壳，直接解析 JSON
            data = resp.json()

            # 顶层必须是 list
            if not isinstance(data, list):
                raise ValueError(
                    f"SZSE stock list: unexpected top-level type {type(data).__name__}, expected list"
                )

            target_block: Optional[Dict[str, Any]] = None

            # 在返回数据中查找到与 TABKEY 参数对应的那一块
            for idx, block in enumerate(data):
                if not isinstance(block, dict):
                    raise ValueError(
                        f"SZSE stock list: block[{idx}] type {type(block).__name__}, expected dict"
                    )

                meta = block.get("metadata")
                if not isinstance(meta, dict):
                    raise ValueError(
                        f"SZSE stock list: block[{idx}] missing or invalid metadata: {repr(meta)}"
                    )

                block_tabkey = str(meta.get("tabkey") or "").strip()

                if block_tabkey == params["TABKEY"]:
                    target_block = block
                    break

            if target_block is None:
                # 没找到匹配的 TABKEY，视为结构或行为变化
                raise ValueError(
                    f"SZSE stock list: no block found for TABKEY={params['TABKEY']}"
                )

            meta = target_block["metadata"]  # 若缺失，会立刻抛 KeyError
            rows = target_block["data"]  # 同理，结构变化会立即暴露问题

            if not isinstance(rows, list):
                raise ValueError(
                    f"SZSE stock list: data for TABKEY={params['TABKEY']} is not a list, got {type(rows).__name__}"
                )

            list_name = str(meta.get("name") or "").strip()

            enriched: List[Dict[str, Any]] = []
            for r in rows:
                if not isinstance(r, dict):
                    raise ValueError(
                        f"SZSE stock list: row type in TABKEY={params['TABKEY']} is {type(r).__name__}, expected dict"
                    )
                # 复制一份，避免无意修改原始结构（安全起见）
                rec = dict(r)
                # 把 metadata 中的股票类别信息写入每一条返回数据中
                # 例如 "A股列表" → "A股"
                rec["gplb"] = list_name.replace("列表", "")
                enriched.append(rec)

            # 记录结果
            if not rows:
                _LOG.warning(
                    "[深交所] 响应无数据行（TABKEY=%s）",
                    extra={
                        # 当前请求使用的 TABKEY
                        "tabkey":
                        params["TABKEY"],
                        # 元数据中的名称信息（如 "A股列表"）
                        "list_name":
                        list_name,
                        # 顶层数据结构类型（应为 list）
                        "top_level_type":
                        type(data).__name__,
                        # 返回的块数量（通常为 4：A股/B股/CDR/A+B）
                        "blocks_count":
                        len(data) if isinstance(data, list) else None,
                        # 当前块中 metadata 的键集合，便于诊断结构变化
                        "metadata_keys":
                        list(meta.keys()) if isinstance(meta, dict) else None,
                    },
                )
                return pd.DataFrame()

            _LOG.info(
                "[深交所] 成功获取 %d 条记录（TABKEY=%s, name=%s）",
                len(enriched),
                params["TABKEY"],
                list_name,
                extra={
                    "tabkey":
                    params["TABKEY"],
                    "list_name":
                    list_name,
                    "user_agent_version":
                    (user_agent.split("Chrome/")[1].split()[0]
                     if "Chrome/" in user_agent else "unknown"),
                },
            )

            return pd.DataFrame(enriched)

    # 使用统一异步重试工具（带反爬告警）。若最终仍失败，会抛出最后一个异常，
    # 由上层 dispatcher / 服务捕获并写入日志，不会直接把整个应用干崩。
    df = await async_retry_call(_do_request)

    # 理论上 async_retry_call 失败会抛异常，不会返回 None，这里仅做防御性兜底。
    return df if df is not None else pd.DataFrame()


# 1.2 深交所基金列表 (官方 JSON 接口)


@limit_async_network_io
async def get_fund_list_sz_szse(showtype: str = "xlsx") -> pd.DataFrame:
    """
    [基金列表] 从深交所官网获取基金列表 (JSON 接口 · 精准 TABKEY 版 + XLSX 全量版)

    数据源:
      - 官网地址 (页面): https://fund.szse.cn/marketdata/fundslist/index.html
      - JSON 接口:  https://fund.szse.cn/api/report/ShowReport/data
      - XLSX 导出: https://fund.szse.cn/api/report/ShowReport

    当前策略：
      - 只拉取基金列表，对应 TABKEY="tab1"。
      - 虽然返回结构中包含 2 块（基金列表/20%涨跌幅限制基金列表），但实测只有 TABKEY 对应的那一块有数据，
        其他块的 data 为空。因此本函数只需要从所有块中找到
        metadata.tabkey == "tab1" 的那一块，提取其 data 即可。
      - 默认使用 XLSX 导出接口一次性获取全量数据（showtype='xlsx'）。
      - 如需保留原 JSON 行为，可显式传入 showtype='JSON'。

    行为说明（按你的“结构变就炸”的要求实现）：
      1. 使用 resp.json() 解析响应为 Python 对象（不做 JSONP 脱壳）。
      2. 严格假定顶层结构为 list；否则立刻抛异常。
      3. 在列表中查找 metadata.tabkey == "tab1" 的 block：
           - 若找不到，抛异常（视为接口结构变更或行为异常）。
           - 若找到：
               - 要求 block["data"] 必须是 list，否则抛异常。
               - 若 data 为空列表，也抛异常（正常情况下基金列表不应为空）。
      4. 不做任何兜底返回空表的逻辑，让问题在日志和调用栈中清晰暴露。
    HTTP 方法:
      - GET

    返回数据:
      - 类型: pandas.DataFrame
      - 每行对应一条指数记录，字段示例（来自实测返回首行数据，实际字段以接口返回为准）:

        {
            "基金代码": "159001",               // 基金唯一标识代码（6位数字，ETF类基金通常以159/510等开头）
            "基金简称": "货币ETF",              // 基金的中文简称（便于投资者识别）
            "基金类别": "ETF",                 // 基金产品类型（如ETF、LOF、开放式基金、封闭式基金等）
            "投资类别": "货币市场基金",         // 基金投资方向分类（如货币市场基金、股票型基金、债券型基金等）
            "上市日期": "2014-10-20",           // 基金在交易所上市交易的日期（格式：YYYY-MM-DD）
            "当前规模(份)": "19,327,427",       // 基金当前的总份额（单位：份）
            "基金管理人": "易方达基金管理有限公司", // 负责基金投资管理、运作的专业机构
            "基金发起人": "",                  // 发起设立该基金的机构（未披露或无相关信息时为空）
            "基金托管人": ""                   // 负责保管基金资产、监督管理人运作的金融机构（未披露或无相关信息时为空）
            "净值": "100.0000"              // 基金当前最新净值（单位：元）
        }

      DataFrame 结构说明:

        - 列名: 与原始 JSON 字段保持一致，不做重命名或转换
        - 行数: 取决于 page_size 和 page_no (分页参数)
        - 空值: 若字段为 "-" 或不存在，将以原样或 NaN 表示

    使用示例:

      >>> from backend.datasource.providers.szse_adapter import get_fund_list_sz_szse
      >>> df = await get_fund_list_sz_szse()
      >>> df.head()

    注意事项：
      - 本函数只负责“拉取原始数据 + 精准取出某一块 + 把 metadata 中的类别信息下沉到行级”。
        不做字段标准化或进一步业务逻辑。
        若需统一转换为 symbol / name / market 等字段，请在 normalizer 层处理。
      - 若需要自动重试，会通过 async_retry_call 对网络错误进行指数退避重试。
      - 该函数已被 limit_async_network_io 装饰，受全局异步令牌桶约束。
    """

    # ---- 归一化 SHOWTYPE 并决定是否走 XLSX 路径 ----
    showtype_normalized = str(showtype or "xlsx").strip().lower()
    use_xlsx = showtype_normalized != "json"

    # ---- 构造查询参数 ----
    base_url = ("https://fund.szse.cn/api/report/ShowReport" if use_xlsx else
                "https://fund.szse.cn/api/report/ShowReport/data")

    # ===== 步骤1：生成动态参数（防缓存/防冲突）=====
    # 生成一个 0~1 之间的随机浮点数，作为防缓存随机因子。
    # 注意：并不要求与浏览器的具体数值相同，只需保证每次请求不同即可。
    rand_value = str(random.random())

    # ===== 步骤2：构造查询参数（个性化部分）=====
    params: Dict[str, str] = {
        "SHOWTYPE": "xlsx" if use_xlsx else
        "JSON",  # 告知服务端以 xlsx（默认）/JSON 形式返回数据。JSON会有强制分页限制，无法一次性拉取全量，因此默认以xlsx。
        "CATALOGID": "1000_lf",  # 深交所基金子网内部报表模板 ID，"1000_lf" 对应基金列表。
        "loading":
        "first",  # 标记“首次加载”（loading=first），其他 TAB 请求中该参数通常缺失。为了统一参数键名，这里始终携带 loading，可以手工改为 "" 或移除。
        "TABKEY":
        "tab1",  # 指定列表页面中具体的 TAB 页（根据深交所官网实测，tab1=基金列表，tab2=20%涨跌幅限制基金列表，除上述四种以外的其他任意参数都会按tab1返回基金列表）
        "txtkey1": "",  # 基金代码 / 简称筛选，关键字模糊查询，留空为全量
        "txtkey2": "",  # 基金管理人筛选，关键字模糊查询，留空为全量
        "selectJjlb": "",  # 基金类别筛选（ETF/LOF/封闭式/基础设施基金），留空为全量
        "selectTzlb": "",  # 投资类型筛选（股票型/混合型/债券型/货币型），留空为全量
        "PAGENO": "",  # 当前页码，与上交所不同，深交所请求参数中未包含分页开关，首次访问页面时请求参数中未包含页码，
        "random":
        rand_value,  # 防缓存随机数，示例: "0.21651426864522294"，每次请求不同（类似浏览器中的 cache buster）。使用 random.random() 动态生成 0~1 之间的浮点数字符串即可。
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
        "Referer":
        "https://fund.szse.cn/marketdata/fundslist/index.html",  # 来源页（官网首页，深交所基金子网）
        "Accept":
        "application/json, text/javascript, */*; q=0.01",  # 接受类型（与官网一致）
        "Host": "fund.szse.cn",  # 目标主机

        # === 现代浏览器安全头（Chrome/Edge 必需，官网固定值）===
        "Sec-Fetch-Dest": "empty",  # XHR / fetch 请求
        "Sec-Fetch-Mode": "cors",  # cors 模式
        "Sec-Fetch-Site": "same-origin",  # 同站请求

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

    log_event(
        logger=_LOG,
        service="szse_adapter",
        level="INFO",
        file=__file__,
        func="get_fund_list_sz_szse",
        line=0,
        trace_id=None,
        event="szse.fund_list.start",
        message="[深交所] 开始拉取基金列表",
        extra={
            "params": params,
            "use_xlsx": use_xlsx
        },
    )

    # ===== 步骤6：执行请求（结构变化即抛异常） =====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(base_url, params=params, headers=headers)
            resp.raise_for_status()

            # 分支1：XLSX 全量导出路径
            if use_xlsx:
                records = xlsx_bytes_to_json_records(resp.content)
                if not records:
                    _LOG.warning(
                        "[深交所] XLSX 基金列表响应无数据行",
                        extra={
                            "tabkey": params["TABKEY"],
                            "showtype": params["SHOWTYPE"],
                        },
                    )
                    return pd.DataFrame()

                df = pd.DataFrame(records)

                _LOG.info(
                    "[深交所] XLSX 基金列表成功获取 %d 条记录",
                    len(df),
                    extra={
                        "tabkey":
                        params["TABKEY"],
                        "showtype":
                        params["SHOWTYPE"],
                        "user_agent_version":
                        (user_agent.split("Chrome/")[1].split()[0]
                         if "Chrome/" in user_agent else "unknown"),
                    },
                )
                return df
            # 分支2：原 JSON 路径（保持现有“结构变就炸”语义）
            # 实测深交所返回数据未套壳，直接解析 JSON
            data = resp.json()

            # 顶层必须是 list
            if not isinstance(data, list):
                raise ValueError(
                    f"SZSE fund list: unexpected top-level type {type(data).__name__}, expected list"
                )

            target_block: Optional[Dict[str, Any]] = None

            # 在返回数据中查找到与 TABKEY 参数对应的那一块
            for idx, block in enumerate(data):
                if not isinstance(block, dict):
                    raise ValueError(
                        f"SZSE fund list: block[{idx}] type {type(block).__name__}, expected dict"
                    )

                meta = block.get("metadata")
                if not isinstance(meta, dict):
                    raise ValueError(
                        f"SZSE fund list: block[{idx}] missing or invalid metadata: {repr(meta)}"
                    )

                block_tabkey = str(meta.get("tabkey") or "").strip()

                if block_tabkey == params["TABKEY"]:
                    target_block = block
                    break

            if target_block is None:
                # 没找到匹配的 TABKEY，视为结构或行为变化
                raise ValueError(
                    f"SZSE fund list: no block found for TABKEY={params['TABKEY']}"
                )

            meta = target_block["metadata"]  # 若缺失，会立刻抛 KeyError
            rows = target_block["data"]  # 同理，结构变化会立即暴露问题

            if not isinstance(rows, list):
                raise ValueError(
                    f"SZSE fund list: data for TABKEY={params['TABKEY']} is not a list, got {type(rows).__name__}"
                )

            list_name = str(meta.get("name") or "").strip()

            # 记录结果
            if not rows:
                _LOG.warning(
                    "[深交所] 响应无数据行（TABKEY=%s）",
                    extra={
                        # 当前请求使用的 TABKEY
                        "tabkey":
                        params["TABKEY"],
                        # 元数据中的名称信息（如 "A股列表"）
                        "list_name":
                        list_name,
                        # 顶层数据结构类型（应为 list）
                        "top_level_type":
                        type(data).__name__,
                        # 返回的块数量（通常为 2：基金列表/20%涨跌幅限制基金列表）
                        "blocks_count":
                        len(data) if isinstance(data, list) else None,
                        # 当前块中 metadata 的键集合，便于诊断结构变化
                        "metadata_keys":
                        list(meta.keys()) if isinstance(meta, dict) else None,
                    },
                )
                return pd.DataFrame()

            _LOG.info(
                "[深交所] 成功获取 %d 条记录（TABKEY=%s, name=%s）",
                len(rows),
                params["TABKEY"],
                list_name,
                extra={
                    "tabkey":
                    params["TABKEY"],
                    "list_name":
                    list_name,
                    "user_agent_version":
                    (user_agent.split("Chrome/")[1].split()[0]
                     if "Chrome/" in user_agent else "unknown"),
                },
            )

            return pd.DataFrame(rows)

    # 使用统一异步重试工具（带反爬告警）。若最终仍失败，会抛出最后一个异常，
    # 由上层 dispatcher / 服务捕获并写入日志，不会直接把整个应用干崩。
    df = await async_retry_call(_do_request)

    # 理论上 async_retry_call 失败会抛异常，不会返回 None，这里仅做防御性兜底。
    return df if df is not None else pd.DataFrame()


# 1.3 深交所指数列表 (官方 JSON 接口)


@limit_async_network_io
async def get_index_list_sz_szse(showtype: str = "xlsx") -> pd.DataFrame:
    """
    [指数列表] 从深交所官网获取指数列表 (JSON 接口 · 精准 TABKEY 版 + XLSX 全量版)

    数据源:
      - 官网地址 (页面): https://www.szse.cn/market/exponent/sample/index.html
      - JSON 接口:  https://www.szse.cn/api/report/ShowReport/data
      - XLSX 导出: https://www.szse.cn/api/report/ShowReport

    当前策略：
      - 只拉取指数列表，对应 TABKEY="tab1"。
      - 返回结构中只包含 1 块指数列表。
      - 默认使用 XLSX 导出接口一次性获取全量数据（showtype='xlsx'）。
      - 如需保留原 JSON 行为，可显式传入 showtype='JSON'。

    行为说明（按你的“结构变就炸”的要求实现）：
      1. 使用 resp.json() 解析响应为 Python 对象（不做 JSONP 脱壳）。
      2. 严格假定顶层结构为 list；否则立刻抛异常。
      3. 在列表中查找 metadata.tabkey == "tab1" 的 block：
           - 若找不到，抛异常（视为接口结构变更或行为异常）。
           - 若找到：
               - 要求 block["data"] 必须是 list，否则抛异常。
               - 若 data 为空列表，也抛异常（正常情况下指数列表不应为空）。
      4. 不做任何兜底返回空表的逻辑，让问题在日志和调用栈中清晰暴露。
    HTTP 方法:
      - GET

    返回数据:
      - 类型: pandas.DataFrame
      - 每行对应一条指数记录，字段示例（来自实测返回首行数据，实际字段以接口返回为准）:

        {
            "指数代码": "399001",               // 指数唯一标识代码（6位数字，深证系列指数通常以399开头）
            "指数名称": "深证成份指数",          // 指数的中文名称（反映特定市场或板块的价格走势）
            "基日": "1994-07-20",               // 指数计算的基准日期（格式：YYYY-MM-DD，作为指数点位的参考起点）
            "基日指数": "1000",                 // 基日设定的初始指数值（通常为100、1000等整数，便于后续点位对比）
            "起始计算日": "1995-01-23"          // 指数正式开始计算并发布的日期（格式：YYYY-MM-DD，可能晚于基日）
        }

      DataFrame 结构说明:

        - 列名: 与原始 JSON 字段保持一致，不做重命名或转换
        - 行数: 取决于 page_size 和 page_no (分页参数)
        - 空值: 若字段为 "-" 或不存在，将以原样或 NaN 表示

    使用示例:

      >>> from backend.datasource.providers.szse_adapter import get_index_list_sz_szse
      >>> df = await get_index_list_sz_szse()
      >>> df.head()

    注意事项：
      - 本函数只负责“拉取原始数据 + 精准取出某一块 + 把 metadata 中的类别信息下沉到行级”。
        不做字段标准化或进一步业务逻辑。
        若需统一转换为 symbol / name / market 等字段，请在 normalizer 层处理。
      - 若需要自动重试，会通过 async_retry_call 对网络错误进行指数退避重试。
      - 该函数已被 limit_async_network_io 装饰，受全局异步令牌桶约束。
    """

    # ---- 归一化 SHOWTYPE 并决定是否走 XLSX 路径 ----
    showtype_normalized = str(showtype or "xlsx").strip().lower()
    use_xlsx = showtype_normalized != "json"

    # ---- 构造查询参数 ----
    base_url = ("https://www.szse.cn/api/report/ShowReport" if use_xlsx else
                "https://www.szse.cn/api/report/ShowReport/data")

    # ===== 步骤1：生成动态参数（防缓存/防冲突）=====
    # 生成一个 0~1 之间的随机浮点数，作为防缓存随机因子。
    # 注意：并不要求与浏览器的具体数值相同，只需保证每次请求不同即可。
    rand_value = str(random.random())

    # ===== 步骤2：构造查询参数（个性化部分）=====
    params: Dict[str, str] = {
        "SHOWTYPE": "xlsx" if use_xlsx else
        "JSON",  # 告知服务端以 xlsx（默认）/JSON 形式返回数据。JSON会有强制分页限制，无法一次性拉取全量，因此默认以xlsx。
        "CATALOGID": "1812_zs",  # 深交所内部报表模板 ID，"1812_zs" 对应指数列表。
        "loading":
        "first",  # 标记“首次加载”（loading=first），其他 TAB 请求中该参数通常缺失。为了统一参数键名，这里始终携带 loading，可以手工改为 "" 或移除。
        "TABKEY":
        "tab1",  # 指定列表页面中具体的 TAB 页（根据深交所官网实测，指数列表tabkey只有唯一选项tab1=指数列表，此外其他任意参数都会按tab1返回指数列表）
        "txtQueryDate": "",  # 指数代码 / 名称筛选，关键字模糊查询，留空为全量
        "selectModule": "",  # 指数板块筛选（全部/创业板指数），留空为全量
        "PAGENO": "",  # 当前页码，与上交所不同，深交所请求参数中未包含分页开关，首次访问页面时请求参数中未包含页码，
        "random":
        rand_value,  # 防缓存随机数，示例: "0.21651426864522294"，每次请求不同（类似浏览器中的 cache buster）。使用 random.random() 动态生成 0~1 之间的浮点数字符串即可。
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
        "Referer":
        "https://www.szse.cn/market/exponent/sample/index.html",  # 来源页（官网首页）
        "Accept":
        "application/json, text/javascript, */*; q=0.01",  # 接受类型（与官网一致）
        "Host": "www.szse.cn",  # 目标主机

        # === 现代浏览器安全头（Chrome/Edge 必需，官网固定值）===
        "Sec-Fetch-Dest": "empty",  # XHR / fetch 请求
        "Sec-Fetch-Mode": "cors",  # cors 模式
        "Sec-Fetch-Site": "same-origin",  # 同站请求

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

    log_event(
        logger=_LOG,
        service="szse_adapter",
        level="INFO",
        file=__file__,
        func="get_index_list_sz_szse",
        line=0,
        trace_id=None,
        event="szse.index_list.start",
        message="[深交所] 开始拉取指数列表",
        extra={
            "params": params,
            "use_xlsx": use_xlsx
        },
    )

    # ===== 步骤6：执行请求（结构变化即抛异常） =====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(base_url, params=params, headers=headers)
            resp.raise_for_status()

            # 分支1：XLSX 全量导出路径
            if use_xlsx:
                records = xlsx_bytes_to_json_records(resp.content)
                if not records:
                    _LOG.warning(
                        "[深交所] XLSX 指数列表响应无数据行",
                        extra={
                            "tabkey": params["TABKEY"],
                            "showtype": params["SHOWTYPE"],
                        },
                    )
                    return pd.DataFrame()

                df = pd.DataFrame(records)

                _LOG.info(
                    "[深交所] XLSX 指数列表成功获取 %d 条记录",
                    len(df),
                    extra={
                        "tabkey":
                        params["TABKEY"],
                        "showtype":
                        params["SHOWTYPE"],
                        "user_agent_version":
                        (user_agent.split("Chrome/")[1].split()[0]
                         if "Chrome/" in user_agent else "unknown"),
                    },
                )
                return df
            # 分支2：原 JSON 路径（保持现有“结构变就炸”语义）
            # 实测深交所返回数据未套壳，直接解析 JSON
            data = resp.json()

            # 顶层必须是 list
            if not isinstance(data, list):
                raise ValueError(
                    f"SZSE index list: unexpected top-level type {type(data).__name__}, expected list"
                )

            target_block: Optional[Dict[str, Any]] = None

            # 在返回数据中查找到与 TABKEY 参数对应的那一块
            for idx, block in enumerate(data):
                if not isinstance(block, dict):
                    raise ValueError(
                        f"SZSE index list: block[{idx}] type {type(block).__name__}, expected dict"
                    )

                meta = block.get("metadata")
                if not isinstance(meta, dict):
                    raise ValueError(
                        f"SZSE index list: block[{idx}] missing or invalid metadata: {repr(meta)}"
                    )

                block_tabkey = str(meta.get("tabkey") or "").strip()

                if block_tabkey == params["TABKEY"]:
                    target_block = block
                    break

            if target_block is None:
                # 没找到匹配的 TABKEY，视为结构或行为变化
                raise ValueError(
                    f"SZSE index list: no block found for TABKEY={params['TABKEY']}"
                )

            meta = target_block["metadata"]  # 若缺失，会立刻抛 KeyError
            rows = target_block["data"]  # 同理，结构变化会立即暴露问题

            if not isinstance(rows, list):
                raise ValueError(
                    f"SZSE index list: data for TABKEY={params['TABKEY']} is not a list, got {type(rows).__name__}"
                )

            list_name = str(meta.get("name") or "").strip()

            # 记录结果
            if not rows:
                _LOG.warning(
                    "[深交所] 响应无数据行（TABKEY=%s）",
                    extra={
                        # 当前请求使用的 TABKEY
                        "tabkey":
                        params["TABKEY"],
                        # 元数据中的名称信息（如 "A股列表"）
                        "list_name":
                        list_name,
                        # 顶层数据结构类型（应为 list）
                        "top_level_type":
                        type(data).__name__,
                        # 返回的块数量（通常为 2：基金列表/20%涨跌幅限制基金列表）
                        "blocks_count":
                        len(data) if isinstance(data, list) else None,
                        # 当前块中 metadata 的键集合，便于诊断结构变化
                        "metadata_keys":
                        list(meta.keys()) if isinstance(meta, dict) else None,
                    },
                )
                return pd.DataFrame()

            _LOG.info(
                "[深交所] 成功获取 %d 条记录（TABKEY=%s, name=%s）",
                len(rows),
                params["TABKEY"],
                list_name,
                extra={
                    "tabkey":
                    params["TABKEY"],
                    "list_name":
                    list_name,
                    "user_agent_version":
                    (user_agent.split("Chrome/")[1].split()[0]
                     if "Chrome/" in user_agent else "unknown"),
                },
            )

            return pd.DataFrame(rows)

    # 使用统一异步重试工具（带反爬告警）。若最终仍失败，会抛出最后一个异常，
    # 由上层 dispatcher / 服务捕获并写入日志，不会直接把整个应用干崩。
    df = await async_retry_call(_do_request)

    # 理论上 async_retry_call 失败会抛异常，不会返回 None，这里仅做防御性兜底。
    return df if df is not None else pd.DataFrame()
