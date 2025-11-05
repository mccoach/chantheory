import akshare as ak
import time
import pandas as pd
from datetime import datetime, timedelta

# ==============================================================================
#  全局设置
# ==============================================================================
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_rows', None)

# 极限测试时间窗口
START_DATE_EXTREME = "19910101"
END_DATE_EXTREME = "20251101"
START_DATETIME_EXTREME = "1991-01-01 09:30:00"
END_DATETIME_EXTREME = "2025-11-01 15:00:00"

# 为涨跌停股池提供一个固定的近期交易日，以提高测试成功率
ZT_POOL_DATE = "20241011"


def run_test(title, func, show_full=False):
    """一个包装器，用于执行测试、计时并按标准格式打印"""
    print(f"\n\n{'='*80}\n{title}\n{'='*80}")
    try:
        start_time = time.monotonic()
        df = func()
        end_time = time.monotonic()
        elapsed_ms = (end_time - start_time) * 1000

        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            print(f"  \033[91m失败或返回为空\033[0m")
            print(f"  响应时间: {elapsed_ms:.2f} ms")
            return

        print("  \033[92m成功!\033[0m")
        print(f"  响应时间: {elapsed_ms:.2f} ms")
        print(f"  信息总条目数: {len(df)}")
        print(f"  所有字段: {df.columns.tolist()}")

        if show_full:
            print(f"  完整数据内容:\n{df}")
        else:
            date_col = next((col for col in ['日期', 'date', '时间', 'day', '上市日期', '终止上市日期', '暂停上市日期', '日期时间', '发行日期', 'trade_date'] if col in df.columns), None)
            if date_col:
                try:
                    date_series = pd.to_datetime(df[date_col], errors='coerce').dropna().astype(str)
                    if not date_series.empty:
                        print(f"  数据时间跨度: {date_series.min()} - {date_series.max()}")
                    else:
                        print("  数据时间跨度: N/A (日期列为空或无法解析)")
                except Exception:
                    print("  数据时间跨度: N/A (解析时出错)")

            print(f"  样例数据:", df.head(2).to_dict(orient='records'))

    except Exception as e:
        print(f"  \033[91m发生错误\033[0m: {e}")
    finally:
        time.sleep(2)


def main():
    print("开始执行最终版全量接口极限测试 (V3.3 - 补全交易日历)...")

    # ================= 1. 标的资产列表 =================
    print("\n\n" + "#"*30 + " 1. 标的资产列表 (Asset Universe) " + "#"*30)
    run_test("1.1. A股列表-通用 (stock_info_a_code_name)", lambda: ak.stock_info_a_code_name())
    run_test("1.2. ETF列表-东财 (fund_etf_spot_em)", lambda: ak.fund_etf_spot_em())
    run_test("1.3. LOF列表-东财 (fund_lof_spot_em)", lambda: ak.fund_lof_spot_em())
    run_test("1.4. ETF列表-新浪(替代方案) (fund_etf_category_sina)", lambda: ak.fund_etf_category_sina(symbol="ETF基金"))
    run_test("1.5. LOF列表-新浪(替代方案) (fund_etf_category_sina)", lambda: ak.fund_etf_category_sina(symbol="LOF基金"))
    run_test("1.6. 股票列表-上证 (stock_info_sh_name_code)", lambda: ak.stock_info_sh_name_code(symbol="主板A股"))
    run_test("1.7. 股票列表-深证 (stock_info_sz_name_code)", lambda: ak.stock_info_sz_name_code(symbol="A股列表"))
    run_test("1.8. 股票列表-北证 (stock_info_bj_name_code)", lambda: ak.stock_info_bj_name_code())
    run_test("1.9. 退市/暂停-上证 (stock_info_sh_delist)", lambda: ak.stock_info_sh_delist(symbol="全部"))
    run_test("1.10. 退市/暂停-深证 (stock_info_sz_delist)", lambda: ak.stock_info_sz_delist(symbol="终止上市公司"))
    run_test("1.11. 两网及退市-东财 (stock_staq_net_stop)", lambda: ak.stock_staq_net_stop())

    # ================= 2. 历史行情数据 =================
    print("\n\n" + "#"*30 + " 2. 历史行情数据 (Historical Bars) " + "#"*30)
    run_test("2.1. A股-日K线-东财 (stock_zh_a_hist)", lambda: ak.stock_zh_a_hist(symbol="000001", start_date=START_DATE_EXTREME, end_date=END_DATE_EXTREME, adjust="qfq"))
    run_test("2.2. A股-日K线-新浪 (stock_zh_a_daily)", lambda: ak.stock_zh_a_daily(symbol="sz000001", start_date=START_DATE_EXTREME, end_date=END_DATE_EXTREME, adjust="qfq"))
    run_test("2.3. A股-日K线-腾讯 (stock_zh_a_hist_tx)", lambda: ak.stock_zh_a_hist_tx(symbol="sz000001", start_date=START_DATE_EXTREME, end_date=END_DATE_EXTREME, adjust="qfq"))
    run_test("2.4. A股-分钟K线-东财 (stock_zh_a_hist_min_em)", lambda: ak.stock_zh_a_hist_min_em(symbol="000001", period="5", start_date=START_DATETIME_EXTREME, end_date=END_DATETIME_EXTREME, adjust="qfq"))
    run_test("2.5. A股-分钟K线-新浪(通用) (stock_zh_a_minute)", lambda: ak.stock_zh_a_minute(symbol='sz000001', period='60', adjust="qfq"))
    run_test("2.6. 科创板-日K线-新浪 (stock_zh_kcb_daily)", lambda: ak.stock_zh_kcb_daily(symbol="sh688399", adjust="qfq"))
    run_test("2.7. ETF-日K线-东财 (fund_etf_hist_em)", lambda: ak.fund_etf_hist_em(symbol="510300", start_date=START_DATE_EXTREME, end_date=END_DATE_EXTREME, adjust="qfq"))
    run_test("2.8. LOF-日K线-东财 (fund_lof_hist_em)", lambda: ak.fund_lof_hist_em(symbol="162411", start_date=START_DATE_EXTREME, end_date=END_DATE_EXTREME, adjust="qfq"))
    run_test("2.9. ETF/LOF-日K线-新浪(通用) (fund_etf_hist_sina)", lambda: ak.fund_etf_hist_sina(symbol="sh510300"))
    run_test("2.10. ETF-分钟K线-东财 (fund_etf_hist_min_em)", lambda: ak.fund_etf_hist_min_em(symbol="510300", period="5", start_date=START_DATETIME_EXTREME, end_date=END_DATETIME_EXTREME, adjust="qfq"))
    run_test("2.11. LOF-分钟K线-东财 (fund_lof_hist_min_em)", lambda: ak.fund_lof_hist_min_em(symbol="162411", period="5", start_date=START_DATETIME_EXTREME, end_date=END_DATETIME_EXTREME, adjust="qfq"))
    run_test("2.12. ETF/LOF-分钟K线-新浪(通用) (stock_zh_a_minute)", lambda: ak.stock_zh_a_minute(symbol='510300', period='60', adjust="qfq"))

    # ================= 3. 指数数据 =================
    print("\n\n" + "#"*30 + " 3. 指数数据 (Index Data) " + "#"*30)
    run_test("3.1. 指数列表-东财 (stock_zh_index_spot_em)", lambda: ak.stock_zh_index_spot_em(symbol="沪深重要指数"))
    run_test("3.2. 指数列表-新浪 (stock_zh_index_spot_sina)", lambda: ak.stock_zh_index_spot_sina())
    run_test("3.3. 指数日线-东财(通用) (index_zh_a_hist)", lambda: ak.index_zh_a_hist(symbol="000300", start_date=START_DATE_EXTREME, end_date=END_DATE_EXTREME))
    run_test("3.4. 指数日线-东财(专用) (stock_zh_index_daily_em)", lambda: ak.stock_zh_index_daily_em(symbol="sz399006", start_date=START_DATE_EXTREME, end_date=END_DATE_EXTREME))
    run_test("3.5. 指数日线-新浪 (stock_zh_index_daily)", lambda: ak.stock_zh_index_daily(symbol="sz399006"))
    run_test("3.6. 指数日线-腾讯 (stock_zh_index_daily_tx)", lambda: ak.stock_zh_index_daily_tx(symbol="sh000300"))
    run_test("3.7. 指数分钟线-东财 (index_zh_a_hist_min_em)", lambda: ak.index_zh_a_hist_min_em(symbol="000300", period="5", start_date=START_DATETIME_EXTREME, end_date=END_DATETIME_EXTREME))

    # ================= 4. 板块数据 =================
    print("\n\n" + "#"*30 + " 4. 板块数据 (Board Data) " + "#"*30)
    run_test("4.1. 行业板块列表-东财 (stock_board_industry_name_em)", lambda: ak.stock_board_industry_name_em())
    run_test("4.2. 概念板块列表-东财 (stock_board_concept_name_em)", lambda: ak.stock_board_concept_name_em())
    run_test("4.3. 行业板块列表-同花顺 (stock_board_industry_summary_ths)", lambda: ak.stock_board_industry_summary_ths())
    run_test("4.4. 行业板块名称-同花顺 (stock_board_industry_name_ths)", lambda: ak.stock_board_industry_name_ths())  # <--- 新增
    try:
        industry_board_name = ak.stock_board_industry_name_em().iloc[0]['板块名称']
        run_test("4.5. 行业板块成分股-东财 (stock_board_industry_cons_em)", lambda: ak.stock_board_industry_cons_em(symbol=industry_board_name))
        run_test("4.6. 行业板块实时行情-东财 (stock_board_industry_spot_em)", lambda: ak.stock_board_industry_spot_em(symbol=industry_board_name), show_full=True)  # <--- 新增
    except Exception as e:
        print(f"\n\n{'='*80}\n4.5 & 4.6. 行业板块相关测试-东财\n{'='*80}")
        print(f"  \033[93m跳过测试\033[0m: 前置的板块列表获取失败，无法进行成分股和实时行情测试。错误: {e}")
    try:
        concept_board_name = ak.stock_board_concept_name_em().iloc[0]['板块名称']
        run_test("4.7. 概念板块成分股-东财 (stock_board_concept_cons_em)", lambda: ak.stock_board_concept_cons_em(symbol=concept_board_name))
    except Exception as e:
        print(f"\n\n{'='*80}\n4.7. 概念板块成分股-东财 (stock_board_concept_cons_em)\n{'='*80}")
        print(f"  \033[93m跳过测试\033[0m: 前置的板块列表获取失败，无法进行成分股测试。错误: {e}")
    run_test("4.8. 行业板块指数-日K线-同花顺 (stock_board_industry_index_ths)", lambda: ak.stock_board_industry_index_ths(symbol="元件", start_date=START_DATE_EXTREME, end_date=END_DATE_EXTREME))
    run_test("4.9. 概念板块指数-日K线-东财 (stock_board_concept_hist_em)", lambda: ak.stock_board_concept_hist_em(symbol="绿色电力", start_date=START_DATE_EXTREME, end_date=END_DATE_EXTREME))
    run_test("4.10. 概念板块指数-分钟K线-东财 (stock_board_concept_hist_min_em)", lambda: ak.stock_board_concept_hist_min_em(symbol="长寿药", period="5"))
    run_test("4.11. 行业板块指数-日K线-东财 (stock_board_industry_hist_em)", lambda: ak.stock_board_industry_hist_em(symbol="小金属", start_date=START_DATE_EXTREME, end_date=END_DATE_EXTREME))
    run_test("4.12. 行业板块指数-分钟K线-东财 (stock_board_industry_hist_min_em)", lambda: ak.stock_board_industry_hist_min_em(symbol="小金属", period="5"))

    # ================= 5. 静态与衍生数据 =================
    print("\n\n" + "#"*30 + " 5. 静态与衍生数据 " + "#"*30)
    run_test("5.1. A股复权因子-新浪 (stock_zh_a_daily)", lambda: ak.stock_zh_a_daily(symbol="sz000001", adjust="qfq-factor"))
    run_test("5.2. 个股档案-东财 (stock_individual_info_em)", lambda: ak.stock_individual_info_em(symbol="000001"), show_full=True)
    run_test("5.3. 个股档案-雪球 (stock_individual_basic_info_xq)", lambda: ak.stock_individual_basic_info_xq(symbol="SH600519"), show_full=True)
    run_test("5.4. 基金档案-雪球 (fund_individual_basic_info_xq)", lambda: ak.fund_individual_basic_info_xq(symbol="000001"), show_full=True)
    run_test("5.5. 指数基金列表-东财 (fund_info_index_em)", lambda: ak.fund_info_index_em(symbol="全部", indicator="全部"))  # <--- 新增

    # ================= 6. 其他特色数据 =================
    print("\n\n" + "#"*30 + " 6. 其他特色数据 " + "#"*30)
    run_test("6.1. 全部公募基金列表-东财 (fund_name_em)", lambda: ak.fund_name_em())
    run_test("6.2. 涨停股池-东财 (stock_zt_pool_em)", lambda: ak.stock_zt_pool_em(date=ZT_POOL_DATE))
    run_test("6.3. 昨日涨停股池-东财 (stock_zt_pool_previous_em)", lambda: ak.stock_zt_pool_previous_em(date=ZT_POOL_DATE))  # <--- 新增
    run_test("6.4. 强势股池-东财 (stock_zt_pool_strong_em)", lambda: ak.stock_zt_pool_strong_em(date=ZT_POOL_DATE))  # <--- 新增
    run_test("6.5. 次新股池-东财 (stock_zt_pool_sub_new_em)", lambda: ak.stock_zt_pool_sub_new_em(date=ZT_POOL_DATE))  # <--- 新增
    run_test("6.6. 炸板股池-东财 (stock_zt_pool_zbgc_em)", lambda: ak.stock_zt_pool_zbgc_em(date=ZT_POOL_DATE))  # <--- 新增
    run_test("6.7. 跌停股池-东财 (stock_zt_pool_dtgc_em)", lambda: ak.stock_zt_pool_dtgc_em(date=ZT_POOL_DATE))  # <--- 新增

    # =================================================================
    #  7. 交易日历 (Trade Calendar)
    # =================================================================
    print("\n\n" + "#"*30 + " 7. 交易日历 (Trade Calendar) " + "#"*30)
    run_test("7.1. 交易日历-新浪 (tool_trade_date_hist_sina)", lambda: ak.tool_trade_date_hist_sina())


    print("\n\n" + "="*80 + "\n所有最终版全量接口极限测试已完成！\n" + "="*80)

if __name__ == "__main__":
    main()
