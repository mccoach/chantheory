# backend/datasource/providers/akshare_adapter.py
# ==============================
# 说明: 原子化调用层 - AkShare 适配器 (V6.0 - 全异步化终极版)
# - 职责: 封装所有对 `akshare` 库的直接调用，并将同步阻塞调用转换为异步接口。
# - 核心改造: 所有函数改为 async def，内部通过 asyncio.to_thread 执行同步的 akshare 调用。
# - 设计哲学: 在最底层（适配器层）封装同步到异步的转换，对上层提供统一的异步接口。
# ==============================

from __future__ import annotations

import asyncio
import pandas as pd
from typing import Optional

# 直接导入 akshare
try:
    import akshare as ak
except ImportError as e:
    raise ImportError(
        "akshare library is required but not installed. "
        "Please install it via: pip install akshare"
    ) from e

from backend.utils.common import ak_symbol_with_prefix
from backend.utils.async_limiter import limit_async_network_io

# ==============================================================================
# 核心辅助函数：同步到异步的转换桥梁
# ==============================================================================

async def _run_sync_in_thread(func, *args, **kwargs):
    """
    在独立线程中执行同步阻塞函数，并返回其结果。
    这是整个适配器的核心机制，确保同步的 akshare 调用不会阻塞主事件循环。
    """
    return await asyncio.to_thread(func, *args, **kwargs)


# ==============================================================================
# 1. 标的资产列表 (Asset Universe)
# ==============================================================================

@limit_async_network_io
async def get_stock_list_a_em() -> pd.DataFrame:
    """
    [A股列表] 从东方财富获取A股股票列表 (不含北交所)。
    - 数据源: 东方财富 (沪深京三个交易所)
    - akshare接口: `stock_info_a_code_name`
    ---
    输入参数:
      - (无)
    ---
    返回数据:
      - 字段: ['code', 'name']
      - 示例: [{'code': '000001', 'name': '平安银行'}]
    """
    return await _run_sync_in_thread(ak.stock_info_a_code_name)

@limit_async_network_io
async def get_stock_list_sh() -> pd.DataFrame:
    """
    [A股列表] 从上交所官网获取沪市主板及科创板股票列表。
    - 数据源: 上海证券交易所, 目标地址: https://www.sse.com.cn/assortment/stock/list/share/
    - akshare接口: `stock_info_sh_name_code`
    ---
    输入参数:
      - symbol (str): (内部调用) 选项: '主板A股', '主板B股', '科创板'
    ---
    返回数据:
      - 字段: ['证券代码', '证券简称', '公司全称', '上市日期']
      - 示例: [{'证券代码': '600000', '证券简称': '浦发银行', '公司全称': '上海浦东发展银行股份有限公司', '上市日期': datetime.date(1999, 11, 10)}]
    """
    df_main = await _run_sync_in_thread(ak.stock_info_sh_name_code, symbol="主板A股")
    df_kcb = await _run_sync_in_thread(ak.stock_info_sh_name_code, symbol="科创板")
    return pd.concat([df_main, df_kcb], ignore_index=True)

@limit_async_network_io
async def get_stock_list_sz() -> pd.DataFrame:
    """
    [A股列表] 从深交所官网获取A股列表。
    - 数据源: 深圳证券交易所, 目标地址: https://www.szse.cn/market/product/stock/list/index.html
    - akshare接口: `stock_info_sz_name_code`
    ---
    输入参数:
      - symbol (str): (内部调用) 选项: 'A股列表', 'B股列表', 'CDR列表', 'AB股列表'
    ---
    返回数据:
      - 字段及单位: {'板块': str, 'A股代码': str(不带市场前缀的六位数字编码), 'A股简称': str, 'A股上市日期': str('YYYY-MM-DD'), 'A股总股本': str(带逗号的数字, 股), 'A股流通股本': str(带逗号的数字, 股), '所属行业': str}
      - 示例: [{'板块': '主板', 'A股代码': '000001', 'A股简称': '平安银行', 'A股上市日期': '1991-04-03', 'A股总股本': '19,405,918,198', 'A股流通股本': '19,405,600,653', '所属行业': 'J 金融业'}]
    """
    return await _run_sync_in_thread(ak.stock_info_sz_name_code, symbol="A股列表")

@limit_async_network_io
async def get_stock_list_bj() -> pd.DataFrame:
    """
    [A股列表] 从北交所官网获取北交所股票列表。
    - 数据源: 北京证券交易所, 目标地址: https://www.bse.cn/nq/listedcompany.html
    - akshare接口: `stock_info_bj_name_code`
    ---
    返回数据:
      - 字段及单位: {'证券代码': str(不带市场前缀的六位数字编码), '证券简称': str, '总股本': int(股), '流通股本': int(股), '上市日期': datetime.date, '所属行业': str, '地区': str, '报告日期': datetime.date}
      - 示例: [{'证券代码': '835185', '证券简称': '贝特瑞', '总股本': 1026040186, '流通股本': 539581696, '上市日期': datetime.date(2021, 11, 15), ...}]
    """
    return await _run_sync_in_thread(ak.stock_info_bj_name_code)

@limit_async_network_io
async def get_etf_list_sina() -> pd.DataFrame:
    """
    [ETF列表 主力] 从新浪财经获取ETF基金列表。
    - 数据源: 新浪财经, 目标地址: http://vip.stock.finance.sina.com.cn/fund_center/index.html#jjhqetf
    - akshare接口: `fund_etf_category_sina`
    ---
    输入参数:
      - symbol (str): (内部调用) 固定为 "ETF基金" (可选参数为: 封闭式基金, ETF基金, LOF基金)
    ---
    返回数据:
      - 字段及单位: {'代码': str(带市场前缀的六位数字编码), '名称': str, '最新价': float(元), '涨跌额': float(元), '涨跌幅': float(%), '成交量': int(股), '成交额': float(元), ...}
      - 示例: [{'代码': 'sz159998', '名称': '计算机ETF', '最新价': 1.087, ...}]
    """
    return await _run_sync_in_thread(ak.fund_etf_category_sina, symbol="ETF基金")

@limit_async_network_io
async def get_lof_list_sina() -> pd.DataFrame:
    """
    [LOF列表 主力] 从新浪财经获取LOF基金列表。
    - 数据源: 新浪财经, 目标地址: (同上)
    - akshare接口: `fund_etf_category_sina`
    ---
    输入参数:
      - symbol (str): (内部调用) 固定为 "LOF基金" (可选参数为: 封闭式基金, ETF基金, LOF基金)
    ---
    返回数据: (同 get_etf_list_sina)
    """
    return await _run_sync_in_thread(ak.fund_etf_category_sina, symbol="LOF基金")

@limit_async_network_io
async def get_etf_list_em() -> pd.DataFrame:
    """
    [ETF列表 失效备用] 从东方财富获取ETF基金列表。
    - !!注意!!: 此接口在集中测试中已被证实极不稳定，会被反爬虫机制阻断。
    - 数据源: 东方财富, 目标地址: http://quote.eastmoney.com/center/gridlist.html#fund_etf
    - akshare接口: `fund_etf_spot_em`
    """
    return await _run_sync_in_thread(ak.fund_etf_spot_em)

@limit_async_network_io
async def get_lof_list_em() -> pd.DataFrame:
    """
    [LOF列表 失效备用] 从东方财富获取LOF基金列表。
    - !!注意!!: 此接口在集中测试中已被证实极不稳定，会被反爬虫机制阻断。
    - 数据源: 东方财富
    - akshare接口: `fund_lof_spot_em`
    """
    return await _run_sync_in_thread(ak.fund_lof_spot_em)

@limit_async_network_io
async def get_delisted_list_sh() -> pd.DataFrame:
    """
    [退市列表] 从上交所官网获取退市/暂停股票列表。
    - 数据源: 上海证券交易所, 目标地址: https://www.sse.com.cn/assortment/stock/list/delisting/
    - akshare接口: `stock_info_sh_delist`
    """
    return await _run_sync_in_thread(ak.stock_info_sh_delist, symbol="全部")

@limit_async_network_io
async def get_delisted_list_sz() -> pd.DataFrame:
    """
    [退市列表] 从深交所官网获取退市/暂停股票列表。
    - 数据源: 深圳证券交易所, 目标地址: https://www.szse.cn/market/stock/suspend/index.html
    - akshare接口: `stock_info_sz_delist`
    """
    return await _run_sync_in_thread(ak.stock_info_sz_delist, symbol="终止上市公司")

@limit_async_network_io
async def get_delisted_list_em() -> pd.DataFrame:
    """
    [退市列表 失效备用] 从东方财富获取两网及退市列表。
    - !!注意!!: 此接口在集中测试中已被证实不稳定。
    - 数据源: 东方财富, 目标地址: https://quote.eastmoney.com/center/gridlist.html#staq_net_board
    - akshare接口: `stock_staq_net_stop`
    """
    return await _run_sync_in_thread(ak.stock_staq_net_stop)


# ==============================================================================
# 1.5 复合方法：三交易所A股列表打包获取（推荐主力）
# ==============================================================================

@limit_async_network_io
async def get_stock_list_all_exchanges() -> pd.DataFrame:
    """
    [A股列表 推荐主力] 从三大交易所官网分别获取并合并（V2.0优化版）。
    
    优势:
    - 市场归属明确（来自官方，无需推断）
    - 包含上市日期、股本等档案信息（深交所/北交所提供）
    - 官方第一手数据，稳定性最高
    
    执行流程:
    1. 并发调用三个交易所的接口
    2. 为每个DataFrame添加市场标记
    3. 合并三个DataFrame
    
    Returns:
        pd.DataFrame: 合并后的全市场A股列表
                     核心字段: 代码/证券代码, 名称/证券简称, _market_source
                     扩展字段(深/北): 上市日期, 总股本, 流通股本, 所属行业, 地区
    """
    # 并发执行三个交易所的获取
    results = await asyncio.gather(
        get_stock_list_sh(),
        get_stock_list_sz(),
        get_stock_list_bj(),
        return_exceptions=True
    )
    
    dfs_to_merge = []
    
    # 处理上交所结果
    if not isinstance(results[0], Exception) and results[0] is not None and not results[0].empty:
        df_sh = results[0].copy()
        df_sh['_market_source'] = 'SH'  # 添加市场标记
        dfs_to_merge.append(df_sh)
    
    # 处理深交所结果
    if not isinstance(results[1], Exception) and results[1] is not None and not results[1].empty:
        df_sz = results[1].copy()
        df_sz['_market_source'] = 'SZ'
        dfs_to_merge.append(df_sz)
    
    # 处理北交所结果
    if not isinstance(results[2], Exception) and results[2] is not None and not results[2].empty:
        df_bj = results[2].copy()
        df_bj['_market_source'] = 'BJ'
        dfs_to_merge.append(df_bj)
    
    if not dfs_to_merge:
        # 所有交易所都失败了，返回空DataFrame
        return pd.DataFrame()
    
    # 合并所有结果
    return pd.concat(dfs_to_merge, ignore_index=True)

# ==============================================================================
# 2. 历史行情数据 (Historical Bars)
# ==============================================================================

# ------------------------------------------------------------------------------
# 2.1 A股 (A-Shares)
# ------------------------------------------------------------------------------

@limit_async_network_io
async def get_stock_daily_em(symbol: str, start_date: str, end_date: str, period: str = 'daily', adjust: str = "") -> pd.DataFrame:
    """
    [A股日/周/月K线 主力] 从东方财富获取A股K线。数据质量高，历史悠久。
    - 数据源: 东方财富, 目标地址: https://quote.eastmoney.com/concept/sh603777.html?from=classic
    - akshare接口: `stock_zh_a_hist`
    ---
    输入参数:
      - symbol (str): 股票代码, 不带市场前缀。示例: '000001'
      - start_date (str): 开始日期。格式: 'YYYYMMDD'。示例: '19910101'
      - end_date (str): 结束日期。格式: 'YYYYMMDD'。示例: '20251101'
      - period (str): 周期。选项: 'daily', 'weekly', 'monthly'
      - adjust (str): 复权选项。选项: ''(不复权), 'qfq'(前复权), 'hfq'(后复权)
    ---
    返回数据:
      - 字段及单位: {'日期': date, '开盘': float(元), '收盘': float(元), '最高': float(元), '最低': float(元), '成交量': int(手), '成交额': float(元), '振幅': float(%), '涨跌幅': float(%), '涨跌额': float(元), '换手率': float(%)}
      - 示例: [{'日期': datetime.date(1991, 4, 3), '股票代码': '000001', '开盘': 49.0, '收盘': 49.0, '最高': 49.0, '最低': 49.0, '成交量': 1, '成交额': 5000.0, '振幅': 0.0, '涨跌幅': 22.5, '涨跌额': 9.0, '换手率': 0.0}]
    """
    return await _run_sync_in_thread(
        ak.stock_zh_a_hist,
        symbol=symbol, period=period, start_date=start_date, end_date=end_date, adjust=adjust
    )

@limit_async_network_io
async def get_stock_weekly_em(symbol: str, start_date: str, end_date: str, adjust: str = "") -> pd.DataFrame:
    """
    [A股周K线] 从东方财富获取（使用period='weekly'）
    其余说明同上
    """
    return await _run_sync_in_thread(
        ak.stock_zh_a_hist,
        symbol=symbol, period='weekly', start_date=start_date, end_date=end_date, adjust=adjust
    )

@limit_async_network_io
async def get_stock_monthly_em(symbol: str, start_date: str, end_date: str, adjust: str = "") -> pd.DataFrame:
    """
    [A股月K线] 从东方财富获取（使用period='monthly'）
    其余说明同上
    """
    return await _run_sync_in_thread(
        ak.stock_zh_a_hist,
        symbol=symbol, period='monthly', start_date=start_date, end_date=end_date, adjust=adjust
    )

@limit_async_network_io
async def get_stock_daily_sina(symbol: str, start_date: str, end_date: str, adjust: str = "") -> pd.DataFrame:
    """
    [A股日K线 备用1] 从新浪财经获取A股日K线。
    - 数据源: 新浪财经, 目标地址: https://finance.sina.com.cn/realstock/company/sh600006/nc.shtml
    - akshare接口: `stock_zh_a_daily`
    ---
    输入参数:
      - symbol (str): 股票代码, 带市场前缀。示例: 'sh600006'
      - start_date (str): 开始日期。格式: 'YYYYMMDD'。示例: '19910101'
      - end_date (str): 结束日期。格式: 'YYYYMMDD'。示例: '20251101'
      - adjust (str): 复权选项。选项: ''(不复权), 'qfq'(前复权), 'hfq'(后复权)

    ---
    内部处理:
      - 为 symbol 增加 'sh'/'sz' 前缀。
    ---
    返回数据:
      - 字段及单位: {'date': date, 'open': float(元), 'high': float(元), 'low': float(元), 'close': float(元), 'volume': float(股), 'amount': float(元), 'outstanding_share': float(股), 'turnover': float(无单位, 比率值)}
      - 示例: [{'date': datetime.date(1991, 4, 3), 'open': 49.0, 'high': 49.0, 'low': 49.0, 'close': 49.0, 'volume': 100.0, 'amount': 5000.0, ...}]
    """
    symbol_prefixed = ak_symbol_with_prefix(symbol)
    return await _run_sync_in_thread(
        ak.stock_zh_a_daily,
        symbol=symbol_prefixed, start_date=start_date, end_date=end_date, adjust=adjust
    )
    
@limit_async_network_io
async def get_stock_daily_tx(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    [A股日K线 备用2] 从腾讯财经获取A股日K线。
    - 数据源: 腾讯证券, 目标地址: https://gu.qq.com/sh000919/zs
    - akshare接口: `stock_zh_a_hist_tx`
    ---
    输入参数:
      - symbol (str): 股票代码, 带市场前缀。示例: 'sh000919'
      - start_date (str): 开始日期。格式: 'YYYYMMDD'。示例: '19910101'
      - end_date (str): 结束日期。格式: 'YYYYMMDD'。示例: '20251101'
      - adjust (str): 复权选项。选项: ''(不复权), 'qfq'(前复权), 'hfq'(后复权)

    ---
    内部处理:
      - 为 symbol 增加 'sh'/'sz' 前缀。
    ---
    返回数据:
      - 字段及单位: {'date': date, 'open': float(元), 'close': float(元), 'high': float(元), 'low': float(元), 'amount': float(手)}
      - !!注意!!: 返回的 'amount' 列实为成交量, 单位是 手。
      - 示例: [{'date': datetime.date(1991, 4, 3), 'open': 49.0, 'close': 49.0, 'high': 49.0, 'low': 49.0, 'amount': 1.0}]
    """
    symbol_prefixed = ak_symbol_with_prefix(symbol)
    return await _run_sync_in_thread(
        ak.stock_zh_a_hist_tx,
        symbol=symbol_prefixed, start_date=start_date, end_date=end_date
    )

@limit_async_network_io
async def get_minutely_em(symbol: str, period: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    [A股分钟K线 历史补充] 从东财获取A股分钟K线。
    - !!注意!!: 历史范围受限, 实测仅能获取近期(约1-2个月)数据。
    - 数据源: 东方财富, 目标地址: https://quote.eastmoney.com/concept/sh603777.html
    - akshare接口: `stock_zh_a_hist_min_em`
    ---
    输入参数:
      - symbol (str): 股票代码, 不带前缀。示例: '000001'
      - period (str): 周期。选项: '1', '5', '15', '30', '60'
      - start_date (str): 开始日期时间。格式: 'YYYY-MM-DD HH:mm:ss'
      - end_date (str): 结束日期时间。格式: 'YYYY-MM-DD HH:mm:ss'
    ---
    返回数据:
      - 字段及单位: {'时间': str, '开盘': float(元), ..., '成交量': int(手), '成交额': float(元), ...}
      - 示例: [{'时间': '2025-09-11 09:35:00', '开盘': 11.77, '成交量': 63564, ...}]
    """
    return await _run_sync_in_thread(
        ak.stock_zh_a_hist_min_em,
        symbol=symbol, period=period, start_date=start_date, end_date=end_date, adjust=""
    )

@limit_async_network_io
async def get_kcb_daily_sina(symbol: str, adjust: str = "") -> pd.DataFrame:
    """
    [科创板日K线] 从新浪财经获取科创板日K线。
    - 数据源: 新浪财经, 目标地址: https://finance.sina.com.cn/realstock/company/sh688001/nc.shtml
    - akshare接口: `stock_zh_kcb_daily`
    ---
    输入参数:
      - symbol (str): 科创板代码, 需要 'sh' 前缀。示例: 'sh688399'
      - adjust (str): 复权选项。选项: ''(不复权), 'qfq'(前复权), 'hfq'(后复权)
    ---
    返回数据:
      - 字段及单位: {'date': date, ..., 'volume': float(股), 'after_volume': float(股), 'after_amount': float(元), ...}
      - 示例: [{'date': datetime.date(2019, 12, 5), 'open': 52.33, 'volume': 9880338.0, ...}]
    """
    # 此接口要求带前缀，但我们的标准是不带，所以在适配器内部处理
    symbol_prefixed = ak_symbol_with_prefix(symbol)
    return await _run_sync_in_thread(ak.stock_zh_kcb_daily, symbol=symbol_prefixed, adjust=adjust)

# ------------------------------------------------------------------------------
# 2.2 基金 (ETF & LOF) 及通用分钟线
# ------------------------------------------------------------------------------

@limit_async_network_io
async def get_fund_daily_sina(symbol: str) -> pd.DataFrame:
    """
    [ETF/LOF日K线 主力] 从新浪财经获取基金(ETF/LOF)的日K线。
    - 数据源: 新浪财经, 目标地址: http://vip.stock.finance.sina.com.cn/fund_center/index.html#jjhqetf
    - akshare接口: `fund_etf_hist_sina`
    ---
    输入参数: 
      - symbol (str): 基金代码, 不带市场前缀。示例: '510300' (ETF), '161005' (LOF)
    ---
    内部处理:
      - 为 symbol 增加 'sh'/'sz' 前缀。
    ---
    返回数据:
      - 字段及单位: {'date': date, 'open': float(元), 'high': float(元), 'low': float(元), 'close': float(元), 'volume': int(手)}
      - 示例: [{'date': datetime.date(2012, 5, 28), 'open': 2.551, 'high': 2.607, 'low': 2.544, 'close': 2.604, 'volume': 1277518720}]
    """
    symbol_prefixed = ak_symbol_with_prefix(symbol)
    return await _run_sync_in_thread(ak.fund_etf_hist_sina, symbol=symbol_prefixed)

@limit_async_network_io
async def get_minutely_sina(symbol: str, period: str) -> pd.DataFrame:
    """
    [通用分钟线 主力] 从新浪获取A股/ETF/LOF/指数的分钟K线。
    - 数据源: 新浪财经, 目标地址: http://finance.sina.com.cn/realstock/company/sh600519/nc.shtml
    - akshare接口: `stock_zh_a_minute`
    ---
    输入参数:
      - symbol (str): 代码, 不带市场前缀。将被自动添加 'sh'/'sz'。示例: '000001', '510300', '161005', '000300'
      - period (str): 周期。选项: '1', '5', '15', '30', '60'
    ---
    内部处理:
      - 为 symbol 增加 'sh'/'sz' 前缀。
    ---
    返回数据:
      - 字段及单位: {'day': str('YYYY-MM-DD HH:mm:ss'), 'open': float(元), 'high': float(元), 'low': float(元), 'close': float(元), 'volume': float(股)}
      - 备注: 数据范围固定约2000条，周期越大，时间跨度越长。
      - 示例: [{'day': '2025-10-21 13:53:00', 'open': '11.440', 'high': '11.450', 'low': '11.430', 'close': '11.440', 'volume': '1119700'}]
    """
    # 新浪分钟线接口也需要为指数代码加上前缀
    symbol_prefixed = ak_symbol_with_prefix(symbol)
    return await _run_sync_in_thread(ak.stock_zh_a_minute, symbol=symbol_prefixed, period=period, adjust="")

@limit_async_network_io
async def get_etf_daily_em(symbol: str, start_date: str, end_date: str, period: str = 'daily', adjust: str = "") -> pd.DataFrame:
    """
    [ETF日K线 失效备用] 从东方财富获取。!!注意!!: 接口不稳定。
    - 数据源: 东方财富, 目标地址: http://quote.eastmoney.com/sz159707.html
    - akshare接口: `fund_etf_hist_em`
    """
    return await _run_sync_in_thread(
        ak.fund_etf_hist_em,
        symbol=symbol, period=period, start_date=start_date, end_date=end_date, adjust=adjust
    )

@limit_async_network_io
async def get_lof_daily_em(symbol: str, start_date: str, end_date: str, period: str = 'daily', adjust: str = "") -> pd.DataFrame:
    """
    [LOF日K线 失效备用] 从东方财富获取。!!注意!!: 接口不稳定。
    - 数据源: 东方财富, 目标地址: https://quote.eastmoney.com/sz166009.html
    - akshare接口: `fund_lof_hist_em`
    """
    return await _run_sync_in_thread(
        ak.fund_lof_hist_em,
        symbol=symbol, period=period, start_date=start_date, end_date=end_date, adjust=adjust
    )
    
@limit_async_network_io
async def get_etf_minutely_em(symbol: str, period: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    [ETF分钟K线 失效备用] 从东方财富获取。!!注意!!: 接口不稳定。
    - 数据源: 东方财富, 目标地址: https://quote.eastmoney.com/sz159707.html
    - akshare接口: `fund_etf_hist_min_em`
    """
    return await _run_sync_in_thread(
        ak.fund_etf_hist_min_em,
        symbol=symbol, period=period, start_date=start_date, end_date=end_date, adjust=""
    )

@limit_async_network_io
async def get_lof_minutely_em(symbol: str, period: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    [LOF分钟K线 失效备用] 从东方财富获取。!!注意!!: 接口不稳定。
    - 数据源: 东方财富, 目标地址: https://quote.eastmoney.com/sz166009.html
    - akshare接口: `fund_lof_hist_min_em`
    """
    return await _run_sync_in_thread(
        ak.fund_lof_hist_min_em,
        symbol=symbol, period=period, start_date=start_date, end_date=end_date, adjust=""
    )


# ==============================================================================
# 3. 指数数据 (Index Data)
# ==============================================================================

@limit_async_network_io
async def get_index_list_sina() -> pd.DataFrame:
    """
    [指数列表 主力] 从新浪财经获取指数列表。
    - 数据源: 新浪财经, 目标地址: https://vip.stock.finance.sina.com.cn/mkt/#hs_s
    - akshare接口: `stock_zh_index_spot_sina`
    ---
    输入参数: (无)
    ---
    返回数据:
      - 字段及单位: {'代码': str, '名称': str, '最新价': float, '成交量': float(手), '成交额': float(元), ...}
      - 示例: [{'代码': 'sh000001', '名称': '上证指数', '最新价': 3954.79, ...}]
    """
    return await _run_sync_in_thread(ak.stock_zh_index_spot_sina)

@limit_async_network_io
async def get_index_list_em() -> pd.DataFrame:
    """
    [指数列表 失效备用] 从东方财富获取。!!注意!!: 接口不稳定。
    - 数据源: 东方财富, 目标地址: https://quote.eastmoney.com/center/gridlist.html#index_sz
    - akshare接口: `stock_zh_index_spot_em`
    """
    return await _run_sync_in_thread(ak.stock_zh_index_spot_em, symbol="沪深重要指数")

@limit_async_network_io
async def get_index_daily_em(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    [指数日K线 主力] 从东方财富获取指数日K线。
    - 数据源: 东方财富, 目标地址: http://quote.eastmoney.com/center/hszs.html
    - akshare接口: `stock_zh_index_daily_em`
    ---
    输入参数:
      - symbol (str): 指数代码, 需要带市场前缀。示例: 'sz399006'
      - start_date (str): 开始日期, 格式: 'YYYYMMDD'
      - end_date (str): 结束日期, 格式: 'YYYYMMDD'
    ---
    返回数据:
      - 字段及单位: {'date': str('YYYY-MM-DD'), 'open': float, 'close': float, 'high': float, 'low': float, 'volume': int(手), 'amount': float(元)}
      - 示例: [{'date': '2010-06-01', 'open': 986.02, 'volume': 1356285, ...}]
    """
    return await _run_sync_in_thread(
        ak.stock_zh_index_daily_em,
        symbol=symbol, start_date=start_date, end_date=end_date
    )

@limit_async_network_io
async def get_index_daily_sina(symbol: str) -> pd.DataFrame:
    """
    [指数日K线 备用1] 从新浪财经获取指数日K线。
    - 数据源: 新浪财经, 目标地址: https://finance.sina.com.cn/realstock/company/sz399552/nc.shtml
    - akshare接口: `stock_zh_index_daily`
    ---
    返回数据:
      - 字段及单位: {'date': date, 'open': float, ..., 'volume': int(股)}
    """
    return await _run_sync_in_thread(ak.stock_zh_index_daily, symbol=symbol)

@limit_async_network_io
async def get_index_daily_tx(symbol: str) -> pd.DataFrame:
    """
    [指数日K线 备用2] 从腾讯证券获取指数日K线。
    - 数据源: 腾讯证券, 目标地址: https://gu.qq.com/sh000919/zs
    - akshare接口: `stock_zh_index_daily_tx`
    ---
    返回数据:
      - 字段及单位: {'date': date, ..., 'amount': float(手)}
      - !!注意!!: 'amount'列实为成交量, 单位是手。
    """
    return await _run_sync_in_thread(ak.stock_zh_index_daily_tx, symbol=symbol)

@limit_async_network_io
async def get_index_daily_em_general(symbol: str, start_date: str, end_date: str, period: str = 'daily') -> pd.DataFrame:
    """
    [指数日/周/月K线 失效备用] 从东方财富获取。!!注意!!: 接口不稳定。
    - 数据源: 东方财富, 目标地址: http://quote.eastmoney.com/center/hszs.html
    - akshare接口: `index_zh_a_hist`
    """
    return await _run_sync_in_thread(
        ak.index_zh_a_hist,
        symbol=symbol, period=period, start_date=start_date, end_date=end_date
    )

@limit_async_network_io
async def get_index_minutely_em(symbol: str, period: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    [指数分钟K线 失效备用] 从东方财富获取。!!注意!!: 接口不稳定。
    - 数据源: 东方财富, 目标地址: https://quote.eastmoney.com/center/hszs.html
    - akshare接口: `index_zh_a_hist_min_em`
    """
    return await _run_sync_in_thread(
        ak.index_zh_a_hist_min_em,
        symbol=symbol, period=period, start_date=start_date, end_date=end_date
    )


# ==============================================================================
# 4. 板块数据 (Board Data)
# ==============================================================================

@limit_async_network_io
async def get_industry_board_list_ths() -> pd.DataFrame:
    """
    [行业板块列表 主力] 从同花顺获取。
    - 数据源: 同花顺, 目标地址: https://q.10jqka.com.cn/thshy/
    - akshare接口: `stock_board_industry_summary_ths`
    ---
    返回数据:
      - 字段及单位: {'板块': str, '总成交量': float(万手), '总成交额': float(亿元), '净流入': float(亿元), ...}
    """
    return await _run_sync_in_thread(ak.stock_board_industry_summary_ths)

@limit_async_network_io
async def get_industry_board_list_em() -> pd.DataFrame:
    """
    [行业板块列表 失效备用] 从东方财富获取。!!注意!!: 接口不稳定。
    - 数据源: 东方财富, 目标地址: https://quote.eastmoney.com/center/boardlist.html#industry_board
    - akshare接口: `stock_board_industry_name_em`
    """
    return await _run_sync_in_thread(ak.stock_board_industry_name_em)

@limit_async_network_io
async def get_concept_board_list_em() -> pd.DataFrame:
    """
    [概念板块列表 失效备用] 从东方财富获取。!!注意!!: 接口不稳定。
    - 数据源: 东方财富, 目标地址: http://quote.eastmoney.com/center/boardlist.html#boards-BK06551
    - akshare接口: `stock_board_concept_name_em`
    """
    return await _run_sync_in_thread(ak.stock_board_concept_name_em)

@limit_async_network_io
async def get_board_constituents_em(board_name: str, board_type: str) -> pd.DataFrame:
    """
    [板块成分股 失效备用] 从东方财富获取。!!注意!!: 接口不稳定。
    - 数据源: 东方财富, 目标地址: https://data.eastmoney.com/bkzj/BK1027.html
    - akshare接口: `stock_board_industry_cons_em` 或 `stock_board_concept_cons_em`
    ---
    输入参数:
      - board_name (str): 板块名称。示例: '小金属', '融资融券'
      - board_type (str): 板块类型。选项: 'industry', 'concept'
    """
    if board_type == 'industry':
        return await _run_sync_in_thread(ak.stock_board_industry_cons_em, symbol=board_name)
    elif board_type == 'concept':
        return await _run_sync_in_thread(ak.stock_board_concept_cons_em, symbol=board_name)
    return pd.DataFrame()

@limit_async_network_io
async def get_board_daily_ths(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    [行业板块指数日K线 主力] 从同花顺获取。
    - 数据源: 同花顺, 目标地址: https://q.10jqka.com.cn/thshy/detail/code/881270/
    - akshare接口: `stock_board_industry_index_ths`
    ---
    输入参数:
      - symbol (str): 板块名称。示例: '元件'
      - start_date (str): 'YYYYMMDD'
      - end_date (str): 'YYYYMMDD'
    ---
    返回数据:
      - 字段及单位: {'日期': date, '开盘价': float, ..., '成交量': int(股?), '成交额': float(元?)} 
      - !!注意!!: 文档未明确成交量/额单位, 需要通过量级推断。
    """
    return await _run_sync_in_thread(
        ak.stock_board_industry_index_ths,
        symbol=symbol, start_date=start_date, end_date=end_date
    )

# ==============================================================================
# 5. 静态与衍生数据 (Static & Derived Data)
# ==============================================================================

@limit_async_network_io
async def get_adj_factor(symbol: str, adjust_type: str) -> pd.DataFrame:
    """
    [复权因子 唯一来源] 从新浪财经获取A股复权因子。
    - 数据源: 新浪财经, akshare接口: `stock_zh_a_daily`
    ---
    输入参数:
      - symbol (str): 股票代码, 不带市场前缀。示例: '000001'
      - adjust_type (str): 因子类型。选项: 'qfq-factor', 'hfq-factor'
    ---
    内部处理:
      - 为 symbol 增加 'sh'/'sz' 前缀。
    ---
    返回数据:
      - 字段: ['date', 'qfq_factor'] 或 ['date', 'hfq_factor']
      - 示例: [{'date': Timestamp('2025-10-15 00:00:00'), 'qfq_factor': '1.0'}]
    """
    symbol_prefixed = ak_symbol_with_prefix(symbol)
    return await _run_sync_in_thread(
        ak.stock_zh_a_daily,
        symbol=symbol_prefixed, adjust=adjust_type
    )

@limit_async_network_io
async def get_stock_profile_em(symbol: str) -> pd.DataFrame:
    """
    [个股档案 主力] 从东方财富获取个股档案信息。
    - 数据源: 东方财富, 目标地址: http://quote.eastmoney.com/concept/sh603777.html?from=classic
    - akshare接口: `stock_individual_info_em`
    ---
    输入参数:
      - symbol (str): 股票代码，不带市场前缀。示例: '000001'
    ---
    返回数据:
      - 格式: 长表 (Key-Value Pair), 需要进行数据透视 (pivot) 处理。
      - 字段: ['item', 'value']
      - 部分关键item: '总股本'(股), '流通股'(股), '行业', '上市时间'('YYYYMMDD')
      - 示例: [{'item': '总股本', 'value': 19405918198.0}, {'item': '上市时间', 'value': '19910403'}]
    """
    return await _run_sync_in_thread(ak.stock_individual_info_em, symbol=symbol)

@limit_async_network_io
async def get_stock_profile_xq(symbol: str) -> pd.DataFrame:
    """
    [个股档案 补充/不稳定] 从雪球获取(主要是公司简介)。
    - !!注意!!: 此接口在测试中失败，可能需要Token或已失效。
    - 数据源: 雪球, 目标地址: https://xueqiu.com/snowman/S/SH601127/detail#/GSJJ
    - akshare接口: `stock_individual_basic_info_xq`
    ---
    输入参数:
      - symbol (str): 股票代码, 不带前缀。
    ---
    内部处理:
      - 为 symbol 增加 'SH'/'SZ' 大写前缀。
    ---
    返回数据:
      - 格式: 长表 (Key-Value Pair)
      - 字段: ['item', 'value']
      - 部分关键item: 'org_cn_introduction', 'main_operation_business'
    """
    market = "SH" if symbol.startswith('6') else "SZ"
    symbol_prefixed = f"{market}{symbol}"
    return await _run_sync_in_thread(ak.stock_individual_basic_info_xq, symbol=symbol_prefixed)
    
@limit_async_network_io
async def get_fund_profile_xq(symbol: str) -> pd.DataFrame:
    """
    [基金档案 主力] 从雪球获取基金档案。
    - 数据源: 雪球, 目标地址: https://danjuanfunds.com/funding/000001
    - akshare接口: `fund_individual_basic_info_xq`
    ---
    输入参数:
      - symbol (str): 基金代码，不带市场前缀。示例: '000001'
    ---
    返回数据:
      - 格式: 长表 (Key-Value Pair), 需要数据透视处理。
      - 字段: ['item', 'value']
      - 部分关键item: '基金代码', '基金名称', '成立时间', '最新规模'(带“亿”字), '基金经理'
      - 示例: [{'item': '基金代码', 'value': '000001'}, {'item': '基金名称', 'value': '华夏成长混合'}]
    """
    return await _run_sync_in_thread(ak.fund_individual_basic_info_xq, symbol=symbol)

@limit_async_network_io
async def get_index_fund_list_em() -> pd.DataFrame:
    """
    [指数基金列表] 从东方财富获取指数型基金列表。
    - 数据源: 东方财富, 目标地址: http://fund.eastmoney.com/trade/zs.html
    - akshare接口: `fund_info_index_em`
    ---
    返回数据:
      - 字段: ['基金代码', '基金名称', '单位净值', '跟踪标的', ...]
    """
    return await _run_sync_in_thread(ak.fund_info_index_em, symbol="全部", indicator="全部")

# ==============================================================================
# 6. 交易日历 (Trade Calendar)
# ==============================================================================

@limit_async_network_io
async def get_trade_calendar() -> pd.DataFrame:
    """
    [交易日历 唯一来源] 从新浪财经获取自1990年以来的所有交易日。
    - akshare接口: `tool_trade_date_hist_sina`
    ---
    返回数据:
      - 字段: ['trade_date']
      - 示例: [{'trade_date': datetime.date(1990, 12, 19)}]
    """
    return await _run_sync_in_thread(ak.tool_trade_date_hist_sina)

# ==============================================================================
# 7. 其他特色数据 (暂不纳入核心, 仅供未来探索)
# ==============================================================================

@limit_async_network_io
async def get_zt_pool_em(date: str) -> pd.DataFrame:
    """
    [特色数据] 从东方财富获取指定日期的涨停股池。
    - 数据源: 东方财富, 目标地址: https://quote.eastmoney.com/ztb/detail#type=ztgc
    - akshare接口: `stock_zt_pool_em`
    """
    return await _run_sync_in_thread(ak.stock_zt_pool_em, date=date)

@limit_async_network_io
async def get_all_fund_list_em() -> pd.DataFrame:
    """
    [特色数据] 从东方财富获取全部公募基金列表。
    - 数据源: 东方财富, 目标地址: http://fund.eastmoney.com/fund.html
    - akshare接口: `fund_name_em`
    """
    return await _run_sync_in_thread(ak.fund_name_em)

# ==============================================================================
# 存档: 在测试中完全失效或被取代的接口
# 说明: 这些函数被保留在此处作为记录，但在生产代码中不应被调用。
# ==============================================================================

def get_fund_profile_em(symbol: str):
    """
    [已失效] 获取基金档案。
    - !!注意!!: 测试中 AttributeError, 该接口在当前akshare版本中不存在。
    - akshare接口: `fund_overview_em` (已失效)
    """
    raise NotImplementedError("akshare.fund_overview_em 接口已失效或不存在。")

def get_board_daily_em(symbol: str, start_date: str, end_date: str, period: str = 'daily'):
    """
    [失效备用] 获取板块指数日K线。!!注意!!: 接口不稳定。
    - akshare接口: `stock_board_industry_hist_em` 或 `stock_board_concept_hist_em`
    """
    # 这是一个示例，实际中需要区分行业和概念
    return ak.stock_board_industry_hist_em(symbol=symbol, start_date=start_date, end_date=end_date, period=period)

def get_board_minutely_em(symbol: str, period: str):
    """
    [失效备用] 获取板块指数分钟K线。!!注意!!: 接口不稳定。
    - akshare接口: `stock_board_industry_hist_min_em` 或 `stock_board_concept_hist_min_em`
    """
    return ak.stock_board_industry_hist_min_em(symbol=symbol, period=period)

