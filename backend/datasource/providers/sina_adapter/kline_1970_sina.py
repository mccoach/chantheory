# backend/datasource/providers/sina_adapter/kline_1970_sina.py
# ==============================
# 说明：新浪行情适配器 - K 线原子接口（V1.2 · quotes 通道版 · 市场优先从 DB 判定）
#
# 职责：
#   - 封装对新浪 CN_MarketDataService.getKLineData 接口的 HTTP 调用；
#   - 支持 A 股 / ETF 的多种频率：
#       * 1 分钟：  freq='1m'  → scale=1
#       * 5 分钟：  freq='5m'  → scale=5
#       * 15 分钟： freq='15m' → scale=15
#       * 30 分钟： freq='30m' → scale=30
#       * 60 分钟： freq='60m' → scale=60
#       * 日线：    freq='1d'  → scale=240（新浪约定：240 分钟 = 1 日）
#       * 周线：    freq='1w'  → scale=1680（新浪约定：1680 分钟 = 1 周）
#   - 固定拉取“不复权”的原始价量数据（不做前后复权计算），MA 字段关闭（ma=no）；
#   - 输出结构化的 pandas.DataFrame，不做业务级字段重命名（由 normalizer 层处理）。
#
# 远程接口（你已经实测的 URL 示例）：
#
#   https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData
#
#   关键参数：
#     - symbol: 带市场前缀代码：
#                  'sh510130', 'sh600159', 'sz002873',...
#                本适配器对外仍接收“无前缀 symbol”（如 '510130'），
#                **优先从本地 symbol_index.market 判定市场（SH/SZ/BJ），
#                  未命中时再退回 ak_symbol_with_prefix 的旧逻辑。**
#
#     - scale:  K 线周期（分钟）：
#                  1   → 1 分钟  K
#                  5   → 5 分钟  K
#                  15  → 15 分钟 K
#                  30  → 30 分钟 K
#                  60  → 60 分钟 K
#                  240 → 日 K（新浪用 240 分钟表示 1 日）
#                  1680→ 周 K（新浪用 1680 分钟表示 1 周）
#
#     - ma:     均线周期：
#                  这里统一传 'no'，只要原始 K 线数据。
#
#     - datalen: 最大条数：
#                  实测 1970 为 AkShare 默认值，意味着最多返回约 2000 根。
#
#   响应：
#     - JSONP 格式：
#         =([...]);  或  var _sh600519_1_...=( [... ] );
#       本适配器通过 backend.utils.spider_toolkit.strip_jsonp
#       统一进行 JSON/JSONP 脱壳，不再依赖本地实现或回调名，
#       仅关注提取出的首个 JSON 数组作为 K 线记录列表。
#
#   数组元素示例：
#
#     {
#       "day": "2025-12-02 09:35:00",  # 分钟线：YYYY-MM-DD HH:MM:SS
#       "open": "7.020",
#       "high": "7.020",
#       "low":  "7.020",
#       "close":"7.020",
#       "volume":"2000",
#       "amount":"123456.78"           # 分钟线场景下可能出现的成交额（单位：元，字段“时有时无”）
#     }
#
#     日线（scale=240）或周线（scale=1680）时：
#
#       "day": "2025-07-25",            # 仅日期 YYYY-MM-DD
#       "open"/"high"/"low"/"close"/"volume" 存在，
#       一般不会包含 "amount" 字段。
#
#   解析与输出 DataFrame 字段：
#
#     - 对于分钟线（1m/5m/15m/30m/60m）：
#         'time'        : str  (YYYY-MM-DD HH:MM:SS)
#         'open'        : float
#         'close'       : float
#         'high'        : float
#         'low'         : float
#         'volume'      : float (单位：股，原始为整数字符串)
#         'amount'      : float 或 None
#                         - 若返回中存在 'amount' 字段，则安全转为 float；
#                         - 若字段缺失或格式异常，则置为 None（防止返回结构变更时崩溃）。
#         'amplitude'   : None  （当前接口不返回该字段，统一置 None）
#         'pct_change'  : None
#         'change'      : None
#         'turnover'    : None
#
#     - 对于日/周线（1d / scale=240，1w / scale=1680）：
#         'date'        : str  (YYYY-MM-DD)
#         其他列同上；'amount' 同样采用“有则解析，无则 None”的容错策略。
#
#   与 normalizer 的契合点：
#     - normalizer.normalize_bars_df 的字段映射会识别：
#         * 'date' / 'time' → 时间列；
#         * 'open'/'high'/'low'/'close' → 价格列；
#         * 'volume' → 成交量；
#         * 'amount' → 成交额（若不为 None）；
#       从而得到统一的 ts/open/high/low/close/volume/... 结构。
#
# 设计风格：
#   - 与 eastmoney_adapter.kline 完全对齐：
#       * async def + limit_async_network_io + async_retry_call；
#       * 使用 spider_toolkit 生成 UA / Accept-Language / Connection / sec-ch-ua；
#       * 使用 spider_toolkit.strip_jsonp 统一 JSON/JSONP 脱壳；
#       * 不做 DB 写入、不做复权、不做缺口判断，仅负责“把远端 JSON → DataFrame”。
# ==============================

from __future__ import annotations

from typing import List, Dict, Any, Optional

import pandas as pd
import httpx

from backend.utils.async_limiter import limit_async_network_io
from backend.utils.async_retry import async_retry_call
from backend.utils.logger import get_logger
from backend.utils.common import ak_symbol_with_prefix, get_symbol_market_from_db

from backend.utils.spider_toolkit import (
    pick_user_agent,
    pick_accept_language,
    pick_connection,
    generate_sec_ch_ua,
    strip_jsonp,
)

_LOG = get_logger("sina_adapter.kline")

# 新版基础 URL：quotes 通道（JSONP v2）
SINA_KLINE_URL = (
    "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData"
)

# ==============================================================================
# 内部辅助函数
# ==============================================================================


def _map_freq_to_scale(freq: str) -> int:
    """
    将系统内频率字符串映射为新浪 scale 参数（分钟数）。

    支持的输入（不区分大小写）：
      - '1m'  → 1
      - '5m'  → 5
      - '15m' → 15
      - '30m' → 30
      - '60m' → 60
      - '1d'  → 240   （新浪约定：240 分钟 = 1 日）
      - '1w'  → 1680  （新浪约定：1680 分钟 = 1 周）

    若 freq 不在上述范围内，将抛出 ValueError。
    """
    f = (freq or "").strip()
    f_lower = f.lower()

    minute_map = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "60m": 60,
        "1d": 240,
        "1w": 1680,
    }
    if f_lower in minute_map:
        return minute_map[f_lower]

    raise ValueError(f"Unsupported freq for Sina kline: {freq}")


def _build_sina_symbol(symbol: str) -> str:
    """
    构造新浪所需的带市场前缀 symbol（如 'sh510300','sz159102'）。

    规则优先级：
      1. 若本地 symbol_index 中存在该 symbol 且 market 字段非空，则：
           'SH' → 'sh{symbol}'
           'SZ' → 'sz{symbol}'
           'BJ' → 'bj{symbol}'
         这样可以确保像 510xxx（沪市 ETF）、159xxx（深市 ETF）等代码被精确映射；
      2. 若 DB 未命中或 market 非上述值，则退回 ak_symbol_with_prefix 的旧逻辑，
         使用“按首位数字猜测市场”的兜底方案。

    说明：
      - 本次修复的根因：
          * 510300 是沪市 ETF，应映射为 'sh510300'；
          * 旧版直接使用 ak_symbol_with_prefix 会将首位不是 6/0/3/8/4 的代码
            一律当成深市（'sz'），导致 510300 被错误映射为 'sz510300'，
            最终返回空数据。
      - 通过优先使用 symbol_index.market，可与 EastMoney 适配器在“市场归属”上保持一致。
    """
    s = (symbol or "").strip()
    if not s:
        raise ValueError("Sina kline: symbol is empty")

    market = get_symbol_market_from_db(s)
    if market:
        m = str(market).strip().upper()
        if m == "SH":
            return f"sh{s}"
        if m == "SZ":
            return f"sz{s}"
        if m == "BJ":
            return f"bj{s}"
        # 其他未知市场，退回旧逻辑
        _LOG.warning(
            "[新浪K线] symbol_index 中存在未知 market=%s，退回前缀推断逻辑 symbol=%s",
            m,
            s,
        )

    # DB 未命中或 market 不在支持列表，使用 ak_symbol_with_prefix 兜底
    return ak_symbol_with_prefix(s)


def _parse_kline_records(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    将新浪返回的 K 线 JSON 数组解析为 DataFrame。

    输入：
      - records: 每个元素形如：
          {
            "day": "2025-11-25 10:45:00" 或 "2025-07-25",
            "open": "6.940",
            "high": "6.940",
            "low":  "6.940",
            "close":"6.940",
            "volume":"7800",
            "amount":"123456.78"   # 仅部分频率/场景存在，可能缺失
          }

    输出：
      - DataFrame，列：
          * 分钟线：'time','open','close','high','low','volume',
                    'amount','amplitude','pct_change','change','turnover'
          * 日/周线：'date', 其余列同上。

      - 若解析失败或 records 为空，则返回空 DataFrame。

    关键容错点：
      - 'amount' 字段“时有时无”，若缺失或值非法则置为 None；
      - 'volume' 若缺失或格式异常，则回退为 0.0，避免因单条异常导致整体崩溃；
      - 其它指标字段（amplitude/pct_change/change/turnover）当前接口不返回，统一置 None。
    """
    out: List[Dict[str, Any]] = []

    for item in records or []:
        try:
            day_str = str(item.get("day") or "").strip()
            if not day_str:
                continue

            has_time = " " in day_str

            rec: Dict[str, Any] = {}
            if has_time:
                rec["time"] = day_str
            else:
                rec["date"] = day_str

            rec["open"] = float(item.get("open"))
            rec["high"] = float(item.get("high"))
            rec["low"] = float(item.get("low"))
            rec["close"] = float(item.get("close"))

            # 成交量：新浪该接口返回的 volume 为“股”数量（字符串），直接转为 float
            vol_raw = item.get("volume")
            try:
                rec["volume"] = (float(vol_raw)
                                 if vol_raw not in (None, "", "-") else 0.0)
            except Exception:
                # 单条 volume 格式异常不应影响整体
                rec["volume"] = 0.0

            # 成交额：仅部分场景返回 'amount'，需安全解析
            amt_raw = item.get("amount")
            if amt_raw in (None, "", "-"):
                rec["amount"] = None
            else:
                try:
                    rec["amount"] = float(amt_raw)
                except Exception:
                    rec["amount"] = None

            # 以下字段新浪未提供，统一置为 None，方便后续 normalizer 统一接入
            rec["amplitude"] = None
            rec["pct_change"] = None
            rec["change"] = None
            rec["turnover"] = None

            out.append(rec)
        except Exception:
            # 单条出错不影响整体，直接跳过
            continue

    if not out:
        return pd.DataFrame()

    return pd.DataFrame(out)


# ==============================================================================
# 对外原子接口
# ==============================================================================


@limit_async_network_io
async def get_kline_sina(
    symbol: str,
    freq: str,
    ma: str = "no",
) -> pd.DataFrame:
    """
    [A股/ETF K 线 · 新浪 CN_MarketData.getKLineData 接口]

    设计用途：
      - 作为 AkShare `stock_zh_a_minute` 等接口的自建替代；
      - 提供分钟/日/周 K 的原始价量数据，不做复权、不做补齐；
      - 可直接交给 normalizer.normalize_bars_df 做统一标准化。

    参数：
      - symbol (str):
          * 不带市场前缀的代码，例如：
              '600159'（上港集团）
              '510130'（ETF）
              '002873'（新天药业）
          * 本函数内部会优先从 symbol_index.market 读取市场信息：
              'SH' → 'sh{symbol}'
              'SZ' → 'sz{symbol}'
              'BJ' → 'bj{symbol}'
            若 DB 未命中或 market 非上述值，则退回 ak_symbol_with_prefix，
            使用“按首位数字猜测市场”的兜底逻辑。

      - freq (str):
          * 支持：
              '1m','5m','15m','30m','60m'  → 对应 scale=1/5/15/30/60 分钟
              '1d'                         → 对应 scale=240（新浪表示 1 日）
              '1w'                         → 对应 scale=1680（新浪表示 1 周）

      - ma (str | int):
          * 均线周期，用于告知新浪返回 ma_priceX / ma_volumeX；
          * 当前适配器**不会使用均线字段**，仅为模拟浏览器行为，默认 "no" 关闭。

    返回：
      - pandas.DataFrame：
          * 分钟线：列 'time','open','close','high','low','volume','amount' 等；
          * 日/周线：列 'date','open','close','high','low','volume','amount' 等；
      - 若请求 / 解析失败，将抛异常（由 async_retry_call 统筹重试）；
      - 若远端返回空数组，则返回空 DataFrame。

    其他约束：
      - 不做复权相关逻辑（始终返回不带复权因子的原始价）；
      - 不做 DB 写入 / 缺口判断，仅为纯数据源；
      - 全程使用 limit_async_network_io + async_retry_call，避免阻塞与临时网络波动。
    """
    sym = (symbol or "").strip()
    if not sym:
        _LOG.warning("[新浪K线] 空 symbol，直接返回空 DataFrame")
        return pd.DataFrame()

    try:
        scale = _map_freq_to_scale(freq)
    except ValueError as e:
        _LOG.error(f"[新浪K线] 频率错误: {e}")
        raise

    # 新浪要求带市场前缀，如 'sh600159'；优先从 symbol_index.market 判定
    sina_symbol = _build_sina_symbol(sym)

    # ===== 构造查询参数 =====
    params: Dict[str, Any] = {
        "symbol": sina_symbol,
        "scale": str(scale),
        "ma": ma or "no",
        "datalen": "1970",  # 新浪接口最大只支持返回1970条，超限就会失败，这里必须写死不能修改。
    }

    # ===== 生成通用请求头（与东财适配器风格保持一致）=====
    user_agent = pick_user_agent()
    accept_language = pick_accept_language()
    connection = pick_connection()
    sec_ch_ua = generate_sec_ch_ua(user_agent)

    headers: Dict[str, str] = {
        # 抓包中使用的 Accept 头（精简后仍保持一致）
        "Accept":
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7",
        "Host":
        "quotes.sina.cn",
        "Referer":
        f"https://finance.sina.com.cn/realstock/company/{sina_symbol}/nc.shtml",
        "Upgrade-Insecure-Requests":
        "1",

        # 通用头（从池中随机）
        "User-Agent":
        user_agent,
        "Accept-Language":
        accept_language,
        "Connection":
        connection,

        # 压缩支持（不包含 br/zstd，避免解压问题）
        "Accept-Encoding":
        "gzip, deflate",
    }

    if sec_ch_ua:
        headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"'

    _LOG.info(
        "[新浪K线] 开始拉取",
        extra={
            "symbol": sym,
            "sina_symbol": sina_symbol,
            "freq": freq,
            "scale": scale,
            "ma": ma,
        },
    )

    # ===== 执行请求（带 async_retry_call 重试）=====
    async def _do_request() -> pd.DataFrame:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(SINA_KLINE_URL,
                                    params=params,
                                    headers=headers)
            resp.raise_for_status()

            try:
                # 统一使用 spider_toolkit.strip_jsonp 做 JSON/JSONP 脱壳
                data = strip_jsonp(resp.text)
            except Exception as e:
                _LOG.error(
                    "[新浪K线] JSON 解析失败",
                    extra={
                        "symbol": sym,
                        "freq": freq,
                        "error": str(e),
                        "text_preview": resp.text[:300],
                    },
                )
                return pd.DataFrame()

            # 该接口按设计应返回 JSON 数组；若为对象则尝试从 data 字段中取列表
            if isinstance(data, list):
                data_list = data
            elif isinstance(data, dict) and isinstance(data.get("data"), list):
                data_list = data.get("data") or []
            else:
                _LOG.warning(
                    "[新浪K线] 响应结构异常（既不是数组也不是含 data 数组的对象）",
                    extra={
                        "symbol": sym,
                        "freq": freq,
                        "type": type(data).__name__,
                    },
                )
                return pd.DataFrame()

            if not data_list:
                _LOG.warning(
                    "[新浪K线] 无 K 线数据",
                    extra={
                        "symbol": sym,
                        "freq": freq,
                    },
                )
                return pd.DataFrame()

            df = _parse_kline_records(data_list)

            _LOG.info(
                "[新浪K线] 拉取成功",
                extra={
                    "symbol": sym,
                    "freq": freq,
                    "rows": len(df),
                },
            )

            return df

    df_result = await async_retry_call(_do_request)

    return df_result if isinstance(df_result, pd.DataFrame) else pd.DataFrame()
