# backend/datasource/fetchers.py  # 数据源统一适配（重构：方法注册表 + 稳定 iface_key）
# ==============================
# 说明（本次关键改动）：
# - 调整 _norm_daily_df：将日/周/月序列的 ts 由“当天 00:00:00”改为“当天 15:00:00”（Asia/Shanghai）。
#   这样保证“结束时间”与真实收盘时间一致，近端判定可直接精确比对，不再需要近似或对齐。
# - 其他逻辑保持不变（方法注册、分钟归一化等）。
# ==============================

from __future__ import annotations  # 允许前置注解

from typing import Tuple, Callable, List, Optional  # 类型
from datetime import datetime  # 时间
import pandas as pd  # DataFrame
import contextlib  # 静默上下文
import io  # 缓冲
import importlib  # 动态导入 akshare
from zoneinfo import ZoneInfo  # 时区
from dataclasses import dataclass  # 方法描述结构

# --- 工具：静默第三方输出 ---------------------------------------------------------

@contextlib.contextmanager  # 上下文管理器
def _silence():
    """with 作用域内静默 stdout/stderr，避免第三方库杂乱打印。"""
    out, err = io.StringIO(), io.StringIO()  # 输出缓冲
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):  # 重定向
        yield  # 执行体

def _ak():
    """延迟导入 akshare。"""
    return importlib.import_module("akshare")  # 动态导入

# --- 工具：时间格式与 DataFrame 归一化 -------------------------------------------

def _fmt_dt(ms: int) -> str:
    """毫秒 -> 'YYYY-MM-DD HH:MM:SS' 字符串（分钟接口要求；Asia/Shanghai）。"""
    dt = datetime.fromtimestamp(ms / 1000.0, tz=ZoneInfo("Asia/Shanghai"))  # 毫秒转 datetime（含时区）
    return dt.strftime("%Y-%m-%d %H:%M:%S")  # 格式化输出

def _norm_minute_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    归一化分钟 DF -> 标准列：['ts','open','high','low','close','volume','amount','turnover_rate']。
    - ts：该分钟 K 的结束时间（右端），精确至分钟。
    - amount：若上游无则 NA；turnover_rate：若上游存在则解析，否则 NA。
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:  # 空安全
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","amount","turnover_rate"])  # 齐列空 DF
    x = df.copy()  # 拷贝
    x.columns = [str(c).strip() for c in x.columns]  # 列名去空白
    # 兼容常见列名
    c_time = next((c for c in ["时间","time","day","datetime","dt"] if c in x.columns), None)  # 时间
    c_open = next((c for c in ["开盘","open"] if c in x.columns), None)  # 开
    c_high = next((c for c in ["最高","high"] if c in x.columns), None)  # 高
    c_low  = next((c for c in ["最低","low"] if c in x.columns), None)  # 低
    c_close= next((c for c in ["收盘","close"] if c in x.columns), None)  # 收
    c_vol  = next((c for c in ["成交量","volume"] if c in x.columns), None)  # 量
    c_amt  = next((c for c in ["成交额","amount"] if c in x.columns), None)  # 额
    c_tvr  = next((c for c in ["换手率","换手","turnover_rate","turnover"] if c in x.columns), None)  # 换手
    if not all([c_time, c_open, c_high, c_low, c_close, c_vol]):  # 必备列检查
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","amount","turnover_rate"])  # 空骨架
    # 解析时间（分钟右端精确时刻）
    dt = pd.to_datetime(x[c_time], errors="coerce")  # 解析时间
    try:
        dt = dt.dt.tz_localize("Asia/Shanghai", nonexistent="shift_forward", ambiguous="infer")  # 本地化时区
    except TypeError:
        dt = dt.dt.tz_localize("Asia/Shanghai")  # 旧版兼容
    y = pd.DataFrame()  # 输出 DF
    y["ts"] = (dt.astype("int64") // 10**6).astype("int64")  # 纳秒→毫秒（右端时间）
    # 数值化字段
    for src, dst in [(c_open,"open"),(c_high,"high"),(c_low,"low"),(c_close,"close"),(c_vol,"volume")]:
        y[dst] = pd.to_numeric(x[src], errors="coerce")
    # 成交额
    y["amount"] = pd.to_numeric(x[c_amt], errors="coerce") if c_amt else pd.NA
    # 换手率（去掉%）
    if c_tvr:
        y["turnover_rate"] = pd.to_numeric(x[c_tvr].astype(str).str.replace("%","",regex=False), errors="coerce")
    else:
        y["turnover_rate"] = pd.NA
    # 清洗与排序
    y = y.dropna(subset=["ts","open","high","low","close","volume"])
    y = y.sort_values("ts").reset_index(drop=True)
    return y  # 返回结果

def _norm_daily_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    归一化日/周/月 DF -> 标准列：['ts','open','high','low','close','volume','amount','turnover_rate']。
    关键改动：
    - ts 设为该 K 的“结束时刻”Asia/Shanghai 的 15:00:00（收盘时刻），而非当天 00:00:00。
      这样日/周/月序列的“结束时间”与近端判定严格一致，避免“00:00/15:00”错位。
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:  # 空安全
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","amount","turnover_rate"])  # 骨架
    x = df.copy()  # 拷贝
    x.columns = [str(c).strip() for c in x.columns]  # 列名去空白
    # 兼容可能的列名
    c_date = next((c for c in ["日期","date","时间","交易日"] if c in x.columns), None)  # 日期/时间
    c_open = next((c for c in ["开盘","open"] if c in x.columns), None)  # 开
    c_high = next((c for c in ["最高","high"] if c in x.columns), None)  # 高
    c_low  = next((c for c in ["最低","low"] if c in x.columns), None)  # 低
    c_close= next((c for c in ["收盘","close"] if c in x.columns), None)  # 收
    c_vol  = next((c for c in ["成交量","volume"] if c in x.columns), None)  # 量
    c_amt  = next((c for c in ["成交额","amount"] if c in x.columns), None)  # 额
    c_tvr  = next((c for c in ["换手率","换手","turnover_rate","turnover"] if c in x.columns), None)  # 换手
    if not all([c_date, c_open, c_high, c_low, c_close, c_vol]):  # 必备列检查
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","amount","turnover_rate"])  # 骨架

    # 1) 解析日期并本地化到 Asia/Shanghai
    dt_raw = pd.to_datetime(x[c_date], errors="coerce")  # 日期到 datetime（无时分秒）
    try:
        dt_raw = dt_raw.dt.tz_localize("Asia/Shanghai", nonexistent="shift_forward", ambiguous="infer")  # 本地化
    except TypeError:
        dt_raw = dt_raw.dt.tz_localize("Asia/Shanghai")  # 旧版兼容

    # 2) 将时间设为 15:00:00 收盘时刻（精确结束时间）
    dt_1500 = dt_raw.dt.normalize() + pd.Timedelta(hours=15)  # 当天 00:00:00 + 15 小时 = 15:00:00

    # 3) 组装输出
    y = pd.DataFrame()
    y["ts"] = (dt_1500.astype("int64") // 10**6).astype("int64")  # 纳秒 → 毫秒

    # 4) 数值化价格/量/额
    for src, dst in [(c_open,"open"),(c_high,"high"),(c_low,"low"),(c_close,"close"),(c_vol,"volume")]:
        y[dst] = pd.to_numeric(x[src], errors="coerce")  # 数值化
    y["amount"] = pd.to_numeric(x[c_amt], errors="coerce") if c_amt else pd.NA  # 额
    if c_tvr:
        y["turnover_rate"] = pd.to_numeric(x[c_tvr].astype(str).str.replace("%","",regex=False), errors="coerce")
    else:
        y["turnover_rate"] = pd.NA

    # 5) 清洗并排序
    y = y.dropna(subset=["ts","open","high","low","close","volume"])  # 关键列完整
    y = y.sort_values("ts").reset_index(drop=True)  # 升序
    return y  # 返回

# --- 方法描述与注册表 ------------------------------------------------------------

@dataclass  # 方法描述结构
class MethodDesc:
    key: str             # 稳定方法键，如 'A_1m_a'
    provider: str        # 提供方：'em'|'sina'|'ak'|'tx'...
    method: str          # 文档调用名字符串，如 'ak.stock_zh_a_minute'
    call: Callable[[], pd.DataFrame]  # 实际调用闭包（归一化 DF）
    category: str        # 'A'|'E'|'L'
    freq: str            # '1m'|'5m'|...|'1d'|'1w'|'1M'
    attrs: dict | None = None  # 预留扩展

def _with_exchange_prefix(symbol: str) -> str:
    """A 股代码加交易所前缀：'6' 开头→sh；'0'/'3' 开头→sz；'8'/'4' 常见北交→bj。"""
    s = (symbol or "").strip()  # 去空白
    if not s:
        return s
    if s.startswith("6"):
        return "sh" + s  # 上证
    if s.startswith(("0", "3")):
        return "sz" + s  # 深证
    if s.startswith(("8", "4")):
        return "bj" + s  # 北交
    return "sz" + s  # 默认深证

def _build_descriptors(
    symbol: str, freq: str, start_dt: str, end_dt: str, s_ymd: str, e_ymd: str, sec_type: str
) -> List[MethodDesc]:
    """按品类×频率构建候选方法列表（主→备），并以稳定键命名。"""
    ak = _ak()  # 导入 akshare
    ds: List[MethodDesc] = []  # 容器

    # 分钟族（1/5/15/30/60m）
    if freq in {"1m","5m","15m","30m","60m"}:  # 判断分钟族
        per = {"1m":"1","5m":"5","15m":"15","30m":"30","60m":"60"}[freq]  # period 对应表
        if sec_type == "A":  # A 股分钟
            # 主：新浪分钟（多日覆盖更长，开盘价正常；需交易所前缀）
            ds.append(MethodDesc(
                key=f"A_{freq}_a", provider="sina", method="ak.stock_zh_a_minute",
                call=lambda: _norm_minute_df(ak.stock_zh_a_minute(symbol=_with_exchange_prefix(symbol), period=per)),
                category="A", freq=freq
            ))
            # 备：东财历史分钟（1m 近 5 日等）
            ds.append(MethodDesc(
                key=f"A_{freq}_b", provider="em", method="ak.stock_zh_a_hist_min_em",
                call=lambda: _norm_minute_df(ak.stock_zh_a_hist_min_em(symbol=symbol, period=per, start_date=start_dt, end_date=end_dt, adjust="")),
                category="A", freq=freq
            ))
        elif sec_type == "ETF":  # ETF 分钟（东财）
            ds.append(MethodDesc(
                key=f"E_{freq}_a", provider="em", method="ak.fund_etf_hist_min_em",
                call=lambda: _norm_minute_df(ak.fund_etf_hist_min_em(symbol=symbol, period=per, start_date=start_dt, end_date=end_dt, adjust="")),
                category="E", freq=freq
            ))
        elif sec_type == "LOF":  # LOF 分钟（东财）
            ds.append(MethodDesc(
                key=f"L_{freq}_a", provider="em", method="ak.fund_lof_hist_min_em",
                call=lambda: _norm_minute_df(ak.fund_lof_hist_min_em(symbol=symbol, period=per, start_date=start_dt, end_date=end_dt, adjust="")),
                category="L", freq=freq
            ))
        return ds  # 返回分钟候选

    # 日/周/月
    if freq in {"1d","1w","1M"}:  # 判断日/周/月
        period = "daily" if freq == "1d" else ("weekly" if freq == "1w" else "monthly")  # period 映射
        if sec_type == "A":  # A 股
            # 主：AK 日/周/月
            ds.append(MethodDesc(
                key=f"A_{freq}_a", provider="ak", method="ak.stock_zh_a_hist",
                call=lambda: _norm_daily_df(ak.stock_zh_a_hist(symbol=symbol, period=period, start_date=s_ymd, end_date=e_ymd, adjust="")),
                category="A", freq=freq
            ))
            if freq == "1d":  # 仅 1d 提供备选（新浪/腾讯）
                prefix = _with_exchange_prefix(symbol)
                ds.append(MethodDesc(
                    key=f"A_{freq}_b", provider="sina", method="ak.stock_zh_a_daily",
                    call=lambda: _norm_daily_df(ak.stock_zh_a_daily(symbol=prefix, start_date=s_ymd, end_date=e_ymd, adjust="")),
                    category="A", freq=freq
                ))
                ds.append(MethodDesc(
                    key=f"A_{freq}_c", provider="tx", method="ak.stock_zh_a_hist_tx",
                    call=lambda: _norm_daily_df(ak.stock_zh_a_hist_tx(symbol=prefix, start_date=s_ymd, end_date=e_ymd)),
                    category="A", freq=freq
                ))
        elif sec_type == "ETF":  # ETF
            ds.append(MethodDesc(
                key=f"E_{freq}_a", provider="em", method="ak.fund_etf_hist_em",
                call=lambda: _norm_daily_df(ak.fund_etf_hist_em(symbol=symbol, period=period, start_date=s_ymd, end_date=e_ymd, adjust="")),
                category="E", freq=freq
            ))
            if freq == "1d":  # 备选：新浪 ETF 日线
                ds.append(MethodDesc(
                    key=f"E_{freq}_b", provider="sina", method="ak.fund_etf_hist_sina",
                    call=lambda: _norm_daily_df(ak.fund_etf_hist_sina(symbol=symbol, start_date=s_ymd, end_date=e_ymd)),
                    category="E", freq=freq
                ))
        elif sec_type == "LOF":  # LOF
            ds.append(MethodDesc(
                key=f"L_{freq}_a", provider="em", method="ak.fund_lof_hist_em",
                call=lambda: _norm_daily_df(ak.fund_lof_hist_em(symbol=symbol, period=period, start_date=s_ymd, end_date=e_ymd, adjust="")),
                category="L", freq=freq
            ))
        return ds  # 返回日/周/月

    # 其它频率：无候选
    return ds  # 空列表

# --- 主入口：按 iface_key 调用指定方法 -------------------------------------------

def fetch_period_ms(
    symbol: str, freq: str, start_ms: int, end_ms: int,
    sec_type: str = "A", iface_key: Optional[str] = None
) -> Tuple[pd.DataFrame, str, Optional[str]]:
    """
    调用指定 iface_key 的方法（主方法默认 *_a）：
    - 返回 (df, provider, source_key)
    - df：规范化后的 DataFrame（齐列）；provider：'em'|'sina'|'ak'|'tx'；
      source_key：稳定方法键（如 'A_1m_a'），用于落库 revision 与响应 meta。
    """
    # 1) 窗口字符串化（供东财历史分钟/日线家族使用）
    start_dt = _fmt_dt(start_ms)  # 分钟窗口起（字符串）
    end_dt = _fmt_dt(end_ms)      # 分钟窗口止（字符串）
    s_ymd = datetime.fromtimestamp(start_ms / 1000.0, tz=ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")  # 起 YYYYMMDD
    e_ymd = datetime.fromtimestamp(end_ms / 1000.0, tz=ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")    # 止 YYYYMMDD

    # 2) 构造方法列表
    with _silence():  # 静默第三方打印
        cands = _build_descriptors(symbol, freq, start_dt, end_dt, s_ymd, e_ymd, sec_type)  # 候选

    if not cands:  # 无候选（如未知频率）
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","amount","turnover_rate"]), "", None  # 返回空

    # 3) 选择方法键：优先 iface_key；否则默认 *_a
    selected: Optional[MethodDesc] = None  # 选中的描述
    if iface_key:
        selected = next((d for d in cands if d.key == iface_key), None)  # 精确匹配
    if selected is None:
        selected = next((d for d in cands if d.key.endswith("_a")), cands[0])  # 默认主方法

    # 4) 调用方法（不做降级/重试；失败时返回空 DF 但保留 provider 与方法键）
    try:
        df = selected.call()  # 执行调用闭包
    except Exception:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","amount","turnover_rate"]), selected.provider, selected.key  # 失败返回空

    # 5) 返回结果（含 provider 与方法键）
    return df, selected.provider, selected.key
