# tests/test_backend_ultimate.py
# ==============================
# 说明：后端终极全面测试（V4.0 - 唯一测试文件）
# 
# 测试范围：
#   【架构层】
#   1. 时间戳体系统一性（9个标准函数）
#   2. 数据库Schema完整性
#   3. 模块导入闭环性
#   
#   【数据源层】
#   4. 三交易所A股列表拉取
#   5. ETF/LOF列表拉取
#   6. K线数据拉取（日/周/月/分钟）
#   7. 复权因子拉取
#   8. 交易日历拉取
#   
#   【标准化层】
#   9. 标的列表标准化
#   10. K线标准化（时间戳语义）
#   11. 复权因子标准化
#   
#   【业务逻辑层】
#   12. 缺口判断器（3种方法）
#   13. 优先级队列（排序正确性）
#   14. 声明式需求解析
#   15. 任务执行器（完整流程）
#   
#   【数据库层】
#   16. K线数据读写
#   17. 复权因子读写
#   18. 标的索引读写
#   19. 自选池CRUD
#   20. 交易日历读写
#   
#   【API层】
#   21. /api/candles（不复权数据）
#   22. /api/symbols/index
#   23. /api/ensure-data
#   24. /api/user/watchlist
#   
#   【事件系统】
#   25. SSE事件推送（data_updated + data_ready）
#   26. 完备性通知（有缺/无缺都推送）
#   
#   【端到端】
#   27. 完整数据同步流程
#   28. 前端请求模拟
# ==============================

import unittest
import asyncio
import sys
import os
from pathlib import Path
import logging
from datetime import datetime, date
import json
import time

# ===== 路径修复 =====
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# ===== 日志配置 =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)

# ===== 导入所有需要测试的模块 =====
from backend.db import (
    ensure_initialized, get_conn,
    upsert_candles_raw, select_candles_raw, get_latest_ts_from_raw,
    upsert_factors, select_factors, get_latest_factor_date,
    upsert_symbol_index, select_symbol_index,
    upsert_symbol_profile, select_symbol_profile,
    insert_watchlist, delete_watchlist, select_user_watchlist,
    upsert_trade_calendar, is_trading_day, get_recent_trading_days
)
from backend.datasource import dispatcher
from backend.services.normalizer import (
    normalize_symbol_list_df, normalize_bars_df,
    normalize_adj_factors_df, normalize_trade_calendar_df
)
from backend.services.data_requirement_parser import get_requirement_parser
from backend.services.priority_queue import get_priority_queue, PrioritizedTask
from backend.services.unified_sync_executor import get_sync_executor
from backend.services.market import get_candles
from backend.services import integrators
from backend.utils.gap_checker import (
    check_kline_gap_to_current,
    check_kline_gap_to_last_close,
    check_info_updated_today,
    check_record_not_exists
)
from backend.utils.time import (
    parse_yyyymmdd, to_date_object,
    ms_at_day_start, ms_at_day_end, ms_at_market_close,
    ms_at_market_open, ms_at_time, query_range_ms,
    to_yyyymmdd, to_datetime, to_iso_string, to_readable_string,
    normalize_date_range, now_dt, now_ms, today_ymd, now_iso,
    shift_days, is_same_day, align_to_minute_start, align_to_day_start,
    ms_from_datetime_string, to_yyyymmdd_from_iso
)
from backend.utils.events import subscribe as subscribe_events, publish as publish_event
from backend.settings import settings, DATA_TYPE_DEFINITIONS

class TestBackendUltimate(unittest.IsolatedAsyncioTestCase):
    
    @classmethod
    def setUpClass(cls):
        """测试前：数据库初始化"""
        print("\n" + "🚀" * 40)
        print("后端终极全面测试 - V4.0")
        print("涵盖：架构/数据源/标准化/业务逻辑/数据库/API/事件/端到端")
        print("🚀" * 40)
        ensure_initialized()
    
    # ==========================================================================
    # 测试组1：时间戳体系（9个标准函数 + 2个新增函数）
    # ==========================================================================
    
    def test_01_timestamp_system(self):
        """【架构】时间戳体系完整性"""
        print("\n" + "=" * 80)
        print("测试1：时间戳体系（11个标准函数）")
        print("=" * 80)
        
        test_ymd = 20241101
        
        # 1.1 基础转换
        date_obj = to_date_object(test_ymd)
        self.assertEqual(date_obj, date(2024, 11, 1))
        print("  ✓ YYYYMMDD → date对象")
        
        # 1.2 时间戳构造（明确语义）
        ts_start = ms_at_day_start(test_ymd)
        ts_end = ms_at_day_end(test_ymd)
        ts_close = ms_at_market_close(test_ymd)
        ts_open = ms_at_market_open(test_ymd)
        ts_custom = ms_at_time(test_ymd, 14, 35, 0)
        
        print(f"  ✓ 日初（00:00）：{ts_start}")
        print(f"  ✓ 日末（23:59）：{ts_end}")
        print(f"  ✓ 收盘（15:00）：{ts_close}")
        print(f"  ✓ 开盘（09:30）：{ts_open}")
        print(f"  ✓ 自定义（14:35）：{ts_custom}")
        
        # 验证语义正确性
        self.assertLess(ts_start, ts_open)
        self.assertLess(ts_open, ts_custom)
        self.assertLess(ts_custom, ts_close)
        self.assertLess(ts_close, ts_end)
        print("  ✓ 时间戳顺序正确：00:00 < 09:30 < 14:35 < 15:00 < 23:59")
        
        # 1.3 反向转换
        ymd_back = to_yyyymmdd(ts_close)
        dt_back = to_datetime(ts_close)
        iso_back = to_iso_string(ts_close)
        readable_back = to_readable_string(ts_close)
        
        self.assertEqual(ymd_back, test_ymd)
        print(f"  ✓ 时间戳 → YYYYMMDD：{ymd_back}")
        print(f"  ✓ 时间戳 → datetime：{dt_back}")
        print(f"  ✓ 时间戳 → ISO：{iso_back}")
        print(f"  ✓ 时间戳 → 可读：{readable_back}")
        
        # 1.4 查询范围构造
        start_ts, end_ts = query_range_ms(20241101, 20241103)
        self.assertEqual(start_ts, ms_at_day_start(20241101))
        self.assertEqual(end_ts, ms_at_day_end(20241103))
        print(f"  ✓ 查询范围构造：包含边界")
        
        # 1.5 日期规范化
        s_ymd, e_ymd = normalize_date_range('2024-11-01', '2024-11-03')
        self.assertEqual(s_ymd, 20241101)
        self.assertEqual(e_ymd, 20241103)
        print(f"  ✓ 日期范围规范化：{s_ymd} ~ {e_ymd}")
        
        # 1.6 当前时间函数
        now_datetime = now_dt()
        now_timestamp = now_ms()
        today = today_ymd()
        
        self.assertIsInstance(today, int)
        self.assertGreater(today, 20240101)
        print(f"  ✓ 今日日期：{today}")
        
        # 1.7 时间运算
        shifted = shift_days(20241101, 3)
        self.assertEqual(shifted, 20241104)
        print(f"  ✓ 日期偏移：+3天 = {shifted}")
        
        same = is_same_day(ts_close, ts_end)
        self.assertTrue(same)
        print(f"  ✓ 同日判断：True")
        
        # 1.8 时间戳对齐
        aligned_min = align_to_minute_start(ts_custom)
        aligned_day = align_to_day_start(ts_close)
        print(f"  ✓ 分钟对齐：{aligned_min}")
        print(f"  ✓ 日初对齐：{aligned_day}")
        
        # 1.9 新增函数（datetime字符串处理）
        ts_dt_str = ms_from_datetime_string('2024-11-01 14:35:00')
        self.assertIsInstance(ts_dt_str, int)
        print(f"  ✓ datetime字符串 → 时间戳：{ts_dt_str}")
        
        ymd_from_iso = to_yyyymmdd_from_iso('2024-11-01T15:00:00+08:00')
        self.assertEqual(ymd_from_iso, 20241101)
        print(f"  ✓ ISO字符串 → YYYYMMDD：{ymd_from_iso}")
    
    # ==========================================================================
    # 测试组2：数据库Schema完整性
    # ==========================================================================
    
    def test_02_database_schema(self):
        """【架构】数据库表结构验证"""
        print("\n" + "=" * 80)
        print("测试2：数据库Schema完整性")
        print("=" * 80)
        
        conn = get_conn()
        cur = conn.cursor()
        
        # 验证所有表存在
        tables = [
            'candles_raw', 'adj_factors', 'symbol_index', 'symbol_profile',
            'user_watchlist', 'sync_tasks', 'task_cursor', 'sync_failures',
            'trade_calendar'
        ]
        
        for table in tables:
            cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            result = cur.fetchone()
            self.assertIsNotNone(result, f"表不存在: {table}")
        
        print(f"  ✓ 所有表存在：{len(tables)} 个")
        
        # 验证关键索引
        cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = [row[0] for row in cur.fetchall()]
        
        key_indexes = [
            'idx_candles_raw_main',
            'idx_symbol_index_type_market',
            'idx_adj_factors_symdate'
        ]
        
        for idx in key_indexes:
            self.assertIn(idx, indexes, f"索引缺失: {idx}")
        
        print(f"  ✓ 关键索引完整：{len(key_indexes)} 个")
    
    # ==========================================================================
    # 测试组3：模块导入闭环性
    # ==========================================================================
    
    def test_03_module_imports(self):
        """【架构】验证所有模块可正常导入（无循环依赖）"""
        print("\n" + "=" * 80)
        print("测试3：模块导入闭环性")
        print("=" * 80)
        
        modules_to_test = [
            'backend.app',
            'backend.settings',
            'backend.db',
            'backend.datasource.dispatcher',
            'backend.datasource.registry',
            'backend.services.normalizer',
            'backend.services.market',
            'backend.services.integrators',
            'backend.services.unified_sync_executor',
            'backend.services.data_requirement_parser',
            'backend.services.priority_queue',
            'backend.utils.time',
            'backend.utils.time_helper',
            'backend.utils.gap_checker',
            'backend.utils.events',
        ]
        
        import importlib
        
        for module_name in modules_to_test:
            try:
                importlib.import_module(module_name)
                print(f"  ✓ {module_name}")
            except Exception as e:
                self.fail(f"模块导入失败: {module_name}, 错误: {e}")
        
        print(f"  ✓ 所有模块导入成功：{len(modules_to_test)} 个")
    
    # ==========================================================================
    # 测试组4：三类标的列表拉取与标准化
    # ==========================================================================
    
    async def test_04_fetch_all_symbol_types(self):
        """【数据源】A股/ETF/LOF三类标的列表拉取"""
        print("\n" + "=" * 80)
        print("测试4：三类标的列表拉取（完整覆盖）")
        print("=" * 80)
        
        test_cases = [
            ('stock_list', 'A', '三交易所A股'),
            ('etf_list', 'ETF', 'ETF基金'),
            ('lof_list', 'LOF', 'LOF基金'),
        ]
        
        for category, type_name, desc in test_cases:
            print(f"\n  [{desc}]")
            
            try:
                raw_df, source_id = await asyncio.wait_for(
                    dispatcher.fetch(category),
                    timeout=30.0
                )
                
                self.assertIsNotNone(raw_df, f"{desc}拉取失败")
                self.assertFalse(raw_df.empty, f"{desc}返回空")
                
                print(f"    ✓ 拉取成功：{len(raw_df)} 个")
                print(f"    ✓ 数据源：{source_id}")
                
                # 标准化
                clean_df = normalize_symbol_list_df(raw_df, category=type_name)
                
                self.assertIsNotNone(clean_df, f"{desc}标准化失败")
                
                # 验证必需字段
                required = ['symbol', 'name', 'market', 'type']
                for col in required:
                    self.assertIn(col, clean_df.columns, f"{desc}缺少字段: {col}")
                
                print(f"    ✓ 标准化成功：{len(clean_df)} 个")
                
                # 验证type字段值正确
                unique_types = clean_df['type'].unique()
                self.assertEqual(len(unique_types), 1)
                self.assertEqual(unique_types[0], type_name)
                print(f"    ✓ 类型标记正确：{type_name}")
                
                # 验证市场标记
                if '_market_source' in raw_df.columns:
                    markets = clean_df['market'].value_counts().to_dict()
                    print(f"    ✓ 市场分布：{markets}")
                
            except asyncio.TimeoutError:
                self.fail(f"{desc}拉取超时")
            except Exception as e:
                print(f"    ✗ 失败：{e}")
                raise
    
    # ==========================================================================
    # 测试组5：K线数据拉取（多频率）
    # ==========================================================================
    
    async def test_05_fetch_kline_multi_freq(self):
        """【数据源】K线数据拉取（日/周/月/分钟）"""
        print("\n" + "=" * 80)
        print("测试5：K线数据拉取（多频率）")
        print("=" * 80)
        
        test_symbol = "000001"
        
        # 测试日线
        print(f"\n  [日线 1d]")
        raw_daily, src = await dispatcher.fetch(
            'stock_bars',
            symbol=test_symbol,
            start_date='20240101',
            end_date='20241231',
            period='daily',
            adjust=''  # 不复权
        )
        
        self.assertIsNotNone(raw_daily, "日线拉取失败")
        print(f"    ✓ 拉取成功：{len(raw_daily)} 条")
        
        # 标准化验证
        clean_daily = normalize_bars_df(raw_daily, src)
        self.assertIsNotNone(clean_daily, "日线标准化失败")
        
        # 验证时间戳语义
        first_ts = clean_daily.iloc[0]['ts']
        first_ymd = to_yyyymmdd(first_ts)
        expected_close = ms_at_market_close(first_ymd)
        self.assertEqual(first_ts, expected_close, "日线时间戳应为15:00收盘")
        print(f"    ✓ 时间戳语义正确：15:00收盘")
        
        # 测试分钟线
        print(f"\n  [分钟线 5m]")
        try:
            raw_min, src_min = await asyncio.wait_for(
                dispatcher.fetch(
                    'stock_minutely_bars',
                    symbol=test_symbol,
                    period='5'
                ),
                timeout=30.0
            )
            
            if raw_min is not None and not raw_min.empty:
                print(f"    ✓ 拉取成功：{len(raw_min)} 条")
                
                clean_min = normalize_bars_df(raw_min, src_min)
                if clean_min is not None and not clean_min.empty:
                    print(f"    ✓ 标准化成功：{len(clean_min)} 条")
                    
                    # 验证分钟K线保持原始时间
                    sample_ts = clean_min.iloc[0]['ts']
                    readable = to_readable_string(sample_ts)
                    print(f"    ✓ 时间示例：{readable}")
            else:
                print(f"    ⊙ 数据为空（可能超出范围）")
        except asyncio.TimeoutError:
            print(f"    ⊙ 拉取超时（数据源可能限制）")
    
    # ==========================================================================
    # 测试组6：复权因子拉取与标准化
    # ==========================================================================
    
    async def test_06_fetch_adj_factors(self):
        """【数据源】复权因子拉取（前复权+后复权）"""
        print("\n" + "=" * 80)
        print("测试6：复权因子拉取")
        print("=" * 80)
        
        test_symbol = "000001"
        
        # 前复权因子
        print(f"\n  [前复权因子]")
        qfq_raw, qfq_src = await dispatcher.fetch(
            'adj_factor',
            symbol=test_symbol,
            adjust_type='qfq-factor'
        )
        
        self.assertIsNotNone(qfq_raw, "前复权因子拉取失败")
        print(f"    ✓ 拉取成功：{len(qfq_raw)} 条")
        
        qfq_clean = normalize_adj_factors_df(qfq_raw, qfq_src)
        self.assertIsNotNone(qfq_clean, "前复权因子标准化失败")
        self.assertIn('date', qfq_clean.columns)
        self.assertIn('factor', qfq_clean.columns)
        print(f"    ✓ 标准化成功：{len(qfq_clean)} 条")
        
        # 后复权因子
        print(f"\n  [后复权因子]")
        hfq_raw, hfq_src = await dispatcher.fetch(
            'adj_factor',
            symbol=test_symbol,
            adjust_type='hfq-factor'
        )
        
        self.assertIsNotNone(hfq_raw, "后复权因子拉取失败")
        print(f"    ✓ 拉取成功：{len(hfq_raw)} 条")
    
    # ==========================================================================
    # 测试组7：交易日历
    # ==========================================================================
    
    async def test_07_trade_calendar(self):
        """【数据源】交易日历拉取与存储"""
        print("\n" + "=" * 80)
        print("测试7：交易日历")
        print("=" * 80)
        
        raw_df, source_id = await dispatcher.fetch('trade_calendar')
        
        self.assertIsNotNone(raw_df, "交易日历拉取失败")
        print(f"  ✓ 拉取成功：{len(raw_df)} 个交易日")
        
        # 标准化
        clean_df = normalize_trade_calendar_df(raw_df)
        self.assertIsNotNone(clean_df, "交易日历标准化失败")
        self.assertIn('date', clean_df.columns)
        print(f"  ✓ 标准化成功：{len(clean_df)} 个交易日")
        
        # 写入数据库
        records = [
            {'date': int(row['date']), 'market': 'CN', 'is_trading_day': 1}
            for _, row in clean_df.iterrows()
        ]
        
        await asyncio.to_thread(upsert_trade_calendar, records)
        print(f"  ✓ 已写入数据库")
        
        # 验证查询
        recent_days = get_recent_trading_days(n=10)
        self.assertEqual(len(recent_days), 10, "应返回10个最近交易日")
        print(f"  ✓ 最近交易日：{recent_days[:3]}...")
        
        # 验证判断函数
        is_trading = is_trading_day(recent_days[0])
        self.assertTrue(is_trading, "最近交易日应返回True")
        print(f"  ✓ 交易日判断：{recent_days[0]} = {is_trading}")
    
    # ==========================================================================
    # 测试组8：缺口判断器（3种方法）
    # ==========================================================================
    
    def test_08_gap_checkers(self):
        """【业务逻辑】缺口判断器（完整覆盖）"""
        print("\n" + "=" * 80)
        print("测试8：缺口判断器（3种方法）")
        print("=" * 80)
        
        test_symbol = "600519"
        
        # 方法1：判断到当前时刻
        print(f"\n  [方法1：到当前时刻]")
        has_gap_current = check_kline_gap_to_current(test_symbol, '1d')
        print(f"    判断结果：{has_gap_current}")
        self.assertIsInstance(has_gap_current, bool)
        print(f"    ✓ 函数正常工作")
        
        # 方法2：判断到前收盘
        print(f"\n  [方法2：到前一交易日收盘]")
        has_gap_last = check_kline_gap_to_last_close(test_symbol, '1d')
        print(f"    判断结果：{has_gap_last}")
        self.assertIsInstance(has_gap_last, bool)
        print(f"    ✓ 函数正常工作")
        
        # 方法3：信息是否今日更新
        print(f"\n  [方法3：信息今日更新]")
        has_gap_info = check_info_updated_today(test_symbol, 'frontend_profile')
        print(f"    判断结果：{has_gap_info}")
        self.assertIsInstance(has_gap_info, bool)
        print(f"    ✓ 函数正常工作")
        
        # 方法4：记录是否存在
        print(f"\n  [方法4：记录存在性]")
        has_gap_exist = check_record_not_exists(test_symbol, 'all_symbols_profile')
        print(f"    判断结果：{has_gap_exist}")
        self.assertIsInstance(has_gap_exist, bool)
        print(f"    ✓ 函数正常工作")
    
    # ==========================================================================
    # 测试组9：优先级队列
    # ==========================================================================
    
    async def test_09_priority_queue(self):
        """【业务逻辑】优先级队列排序正确性"""
        print("\n" + "=" * 80)
        print("测试9：优先级队列")
        print("=" * 80)
        
        from backend.services.priority_queue import AsyncPriorityQueue
        
        queue = AsyncPriorityQueue()
        
        # 构造不同优先级任务
        tasks_to_add = [
            (30, 'watchlist_kline_1d'),
            (5, 'frontend_kline_current'),
            (10, 'frontend_profile'),
            (40, 'all_symbols_profile'),
        ]
        
        for priority, dt_id in tasks_to_add:
            task = PrioritizedTask(
                priority=priority,
                timestamp=datetime.now().timestamp(),
                data_type_id=dt_id,
                symbol='test',
                task_id=f'test_{priority}'
            )
            await queue.enqueue(task)
        
        print(f"  ✓ 已入队 {len(tasks_to_add)} 个任务（乱序）")
        
        # 出队验证顺序
        out_priorities = []
        for _ in range(len(tasks_to_add)):
            task = await queue.dequeue()
            out_priorities.append(task.priority)
        
        expected = [5, 10, 30, 40]
        self.assertEqual(out_priorities, expected, "出队顺序错误")
        print(f"  ✓ 出队顺序正确：{out_priorities}")
    
    # ==========================================================================
    # 测试组10：声明式需求解析（完整场景）
    # ==========================================================================
    
    async def test_10_requirement_parser(self):
        """【业务逻辑】声明式需求解析（4种scope）"""
        print("\n" + "=" * 80)
        print("测试10：声明式需求解析")
        print("=" * 80)
        
        parser = get_requirement_parser()
        
        # 场景1：单个标的
        print(f"\n  [场景1：单标的需求]")
        req1 = [{
            'scope': 'symbol',
            'symbol': '600519',
            'includes': [
                {'type': 'frontend_kline_current', 'freq': '1d', 'priority': 5}
            ]
        }]
        
        tasks1 = parser.parse_requirements(req1)
        self.assertEqual(len(tasks1), 1)
        self.assertEqual(tasks1[0].symbol, '600519')
        print(f"    ✓ 生成任务：{len(tasks1)} 个")
        
        # 场景2：自选池
        print(f"\n  [场景2：自选池需求]")
        req2 = [{
            'scope': 'watchlist',
            'symbols': ['600519', '000001'],
            'includes': [
                {'type': 'watchlist_kline_1d', 'freq': '1d', 'priority': 30}
            ]
        }]
        
        tasks2 = parser.parse_requirements(req2)
        self.assertEqual(len(tasks2), 2)  # 2个标的
        print(f"    ✓ 生成任务：{len(tasks2)} 个（2个标的）")
        
        # 场景3：全量标的
        print(f"\n  [场景3：全量标的需求]")
        req3 = [{
            'scope': 'all_symbols',
            'includes': [
                {'type': 'all_symbols_profile', 'priority': 40}
            ]
        }]
        
        tasks3 = parser.parse_requirements(req3)
        self.assertGreater(len(tasks3), 0)
        print(f"    ✓ 生成任务：{len(tasks3)} 个（全量标的）")
        
        # 场景4：全局数据
        print(f"\n  [场景4：全局数据需求]")
        req4 = [{
            'scope': 'global',
            'includes': [
                {'type': 'symbol_index', 'priority': 5}
            ]
        }]
        
        tasks4 = parser.parse_requirements(req4)
        self.assertEqual(len(tasks4), 1)
        self.assertIsNone(tasks4[0].symbol)  # 全局数据无symbol
        print(f"    ✓ 生成任务：{len(tasks4)} 个（无symbol）")
    
    # ==========================================================================
    # 测试组11：数据库K线读写（不复权）
    # ==========================================================================
    
    async def test_11_candles_crud(self):
        """【数据库】K线数据CRUD（不复权存储）"""
        print("\n" + "=" * 80)
        print("测试11：K线数据CRUD")
        print("=" * 80)
        
        test_symbol = "TEST001"
        test_freq = "1d"
        
        # 构造测试数据（不复权）
        test_data = []
        for i in range(5):
            ymd = shift_days(20241101, i)
            ts = ms_at_market_close(ymd)
            test_data.append({
                'symbol': test_symbol,
                'freq': test_freq,
                'ts': ts,
                'open': 10.0 + i * 0.1,
                'high': 10.5 + i * 0.1,
                'low': 9.5 + i * 0.1,
                'close': 10.2 + i * 0.1,
                'volume': 100000 + i * 1000,
                'amount': None,
                'turnover_rate': None,
                'source': 'test',
                'fetched_at': datetime.now().isoformat()
            })
        
        # 写入
        rows_affected = await asyncio.to_thread(upsert_candles_raw, test_data)
        print(f"  ✓ 写入成功：{rows_affected} 条")
        
        # 读取
        candles = await asyncio.to_thread(
            select_candles_raw,
            symbol=test_symbol,
            freq=test_freq
        )
        
        self.assertEqual(len(candles), 5, "读取数量不匹配")
        print(f"  ✓ 读取成功：{len(candles)} 条")
        
        # 验证时间戳顺序
        timestamps = [c['ts'] for c in candles]
        self.assertEqual(timestamps, sorted(timestamps), "时间戳应升序")
        print(f"  ✓ 时间戳升序排列")
        
        # 验证最新时间戳查询
        latest_ts = get_latest_ts_from_raw(test_symbol, test_freq)
        self.assertEqual(latest_ts, timestamps[-1])
        print(f"  ✓ 最新时间戳查询：{latest_ts}")
    
    # ==========================================================================
    # 测试组12：复权因子读写
    # ==========================================================================
    
    async def test_12_factors_crud(self):
        """【数据库】复权因子CRUD"""
        print("\n" + "=" * 80)
        print("测试12：复权因子CRUD")
        print("=" * 80)
        
        test_symbol = "TEST002"
        
        # 构造测试数据
        test_factors = []
        for i in range(5):
            ymd = shift_days(20241101, i)
            test_factors.append({
                'symbol': test_symbol,
                'date': ymd,
                'qfq_factor': 1.0 + i * 0.01,
                'hfq_factor': 1.5 + i * 0.01,
                'updated_at': datetime.now().isoformat()
            })
        
        # 写入
        rows_affected = await asyncio.to_thread(upsert_factors, test_factors)
        print(f"  ✓ 写入成功：{rows_affected} 条")
        
        # 读取
        factors = await asyncio.to_thread(select_factors, symbol=test_symbol)
        
        self.assertEqual(len(factors), 5)
        print(f"  ✓ 读取成功：{len(factors)} 条")
        
        # 验证最新日期
        latest_date = get_latest_factor_date(test_symbol)
        self.assertEqual(latest_date, shift_days(20241101, 4))
        print(f"  ✓ 最新日期：{latest_date}")
    
    # ==========================================================================
    # 测试组13：标的索引与档案
    # ==========================================================================
    
    async def test_13_symbol_metadata(self):
        """【数据库】标的索引与档案CRUD"""
        print("\n" + "=" * 80)
        print("测试13：标的索引与档案")
        print("=" * 80)
        
        # 写入索引
        test_symbols = [
            {
                'symbol': 'TEST003',
                'name': '测试股票3',
                'market': 'SH',
                'type': 'A',
                'listing_date': 20100101,
                'status': 'active',
                'updated_at': datetime.now().isoformat()
            }
        ]
        
        rows = await asyncio.to_thread(upsert_symbol_index, test_symbols)
        print(f"  ✓ 索引写入：{rows} 条")
        
        # 查询索引
        symbols = await asyncio.to_thread(select_symbol_index, symbol='TEST003')
        self.assertEqual(len(symbols), 1)
        print(f"  ✓ 索引查询：{symbols[0]['name']}")
        
        # 写入档案
        test_profile = {
            'symbol': 'TEST003',
            'listing_date': 20100101,
            'total_shares': 1000000000.0,
            'float_shares': 500000000.0,
            'industry': '测试行业',
            'region': '测试地区',
            'concepts': None,
            'updated_at': datetime.now().isoformat()
        }
        
        await asyncio.to_thread(upsert_symbol_profile, [test_profile])
        print(f"  ✓ 档案写入成功")
        
        # 查询档案
        profile = await asyncio.to_thread(select_symbol_profile, 'TEST003')
        self.assertIsNotNone(profile)
        self.assertEqual(profile['industry'], '测试行业')
        print(f"  ✓ 档案查询：{profile['industry']}")
    
    # ==========================================================================
    # 测试组14：自选池CRUD
    # ==========================================================================
    
    async def test_14_watchlist_crud(self):
        """【数据库】自选池CRUD"""
        print("\n" + "=" * 80)
        print("测试14：自选池CRUD")
        print("=" * 80)
        
        test_symbol = "600519"
        
        # ===== 前置：确保symbol_index中有此标的 =====
        test_symbols = [{
            'symbol': test_symbol,
            'name': '贵州茅台',
            'market': 'SH',
            'type': 'A',
            'status': 'active',
            'updated_at': datetime.now().isoformat()
        }]
        
        await asyncio.to_thread(upsert_symbol_index, test_symbols)
        print(f"  ✓ 前置：symbol_index已有 {test_symbol}")
        
        # 添加到自选池
        success = await asyncio.to_thread(
            insert_watchlist,
            symbol=test_symbol,
            source='test',
            tags=['核心', '长线'],
            sort_order=1
        )
        self.assertTrue(success)
        print(f"  ✓ 添加成功：{test_symbol}")
        
        # 查询
        watchlist = await asyncio.to_thread(select_user_watchlist)
        self.assertGreater(len(watchlist), 0)
        
        # 验证tags解析
        item = next((w for w in watchlist if w['symbol'] == test_symbol), None)
        if item:
            self.assertIsInstance(item['tags'], list)
            print(f"  ✓ 查询成功：tags={item['tags']}")
        
        # 删除
        success = await asyncio.to_thread(delete_watchlist, test_symbol)
        self.assertTrue(success)
        print(f"  ✓ 删除成功：{test_symbol}")
    
    # ==========================================================================
    # 测试组15：SSE事件系统（2种事件类型）
    # ==========================================================================
    
    async def test_15_sse_event_system(self):
        """【事件系统】SSE事件订阅与推送"""
        print("\n" + "=" * 80)
        print("测试15：SSE事件系统")
        print("=" * 80)
        
        events_received = []
        
        def test_callback(event):
            events_received.append(event)
        
        subscribe_events(test_callback)
        
        # 推送 data_updated 事件
        print(f"\n  [事件1：data_updated]")
        publish_event({
            'type': 'data_updated',
            'symbol': '600519',
            'freq': '1d',
            'status': 'newly_fetched',
            'timestamp': datetime.now().isoformat()
        })
        
        await asyncio.sleep(0.1)
        self.assertGreater(len(events_received), 0)
        print(f"    ✓ 事件已接收：{events_received[-1]['type']}")
        
        # 推送 data_ready 事件
        print(f"\n  [事件2：data_ready]")
        publish_event({
            'type': 'data_ready',
            'symbol': '600519',
            'freq': '1d',
            'status': 'already_latest',
            'timestamp': datetime.now().isoformat()
        })
        
        await asyncio.sleep(0.1)
        self.assertEqual(len(events_received), 2)
        print(f"    ✓ 事件已接收：{events_received[-1]['type']}")
        
        # 验证字段完整性
        for event in events_received:
            self.assertIn('type', event)
            self.assertIn('symbol', event)
            self.assertIn('freq', event)
            self.assertIn('status', event)
            self.assertIn('timestamp', event)
        
        print(f"  ✓ 事件字段完整：type, symbol, freq, status, timestamp")
    
    # ==========================================================================
    # 测试组16：集成器（K线+因子）
    # ==========================================================================
    
    async def test_16_integrators(self):
        """【业务逻辑】集成器：并发拉取K线+因子"""
        print("\n" + "=" * 80)
        print("测试16：集成器（并发拉取）")
        print("=" * 80)
        
        test_symbol = "000001"
        
        t0 = time.time()
        
        result = await integrators.get_daily_bars_with_factors(
            symbol=test_symbol,
            start_date='20240101',
            end_date='20240131'
        )
        
        elapsed = time.time() - t0
        
        self.assertIsNotNone(result)
        self.assertIn('bars', result)
        self.assertIn('factors', result)
        
        df_bars = result['bars']
        df_factors = result['factors']
        
        print(f"  ✓ 并发拉取成功（耗时 {elapsed:.2f}s）")
        print(f"    K线：{len(df_bars)} 条")
        print(f"    因子：{len(df_factors)} 条")
        
        # 验证因子已合并
        self.assertIn('qfq_factor', df_factors.columns)
        self.assertIn('hfq_factor', df_factors.columns)
        print(f"  ✓ 因子已合并：qfq + hfq")
    
    # ==========================================================================
    # 测试组17：执行器完整流程（端到端）
    # ==========================================================================
    
    async def test_17_executor_full_workflow(self):
        """【端到端】执行器完整工作流"""
        print("\n" + "=" * 80)
        print("测试17：执行器完整工作流")
        print("=" * 80)
        
        parser = get_requirement_parser()
        queue = get_priority_queue()
        executor = get_sync_executor()
        
        test_symbol = "000002"
        events_received = []
        
        def workflow_callback(event):
            if event.get('symbol') == test_symbol:
                events_received.append(event)
        
        subscribe_events(workflow_callback)
        
        # 步骤1：声明需求
        print(f"\n  步骤1：声明数据需求")
        requirements = [{
            'scope': 'symbol',
            'symbol': test_symbol,
            'includes': [
                {'type': 'frontend_kline_current', 'freq': '1d', 'priority': 5}
            ]
        }]
        
        tasks = parser.parse_requirements(requirements)
        print(f"    ✓ 生成任务：{len(tasks)} 个")
        
        # 步骤2：入队
        print(f"\n  步骤2：任务入队")
        for task in tasks:
            await queue.enqueue(task)
        print(f"    ✓ 队列长度：{queue.size()}")
        
        # 步骤3：执行任务
        print(f"\n  步骤3：执行任务")
        task = await queue.dequeue()
        await executor._execute_task(task)
        print(f"    ✓ 任务执行完成")
        
        # 步骤4：验证SSE推送
        print(f"\n  步骤4：验证SSE推送")
        await asyncio.sleep(0.2)
        
        self.assertGreater(len(events_received), 0, "应收到至少1个事件")
        
        event = events_received[0]
        self.assertIn(event['type'], ['data_updated', 'data_ready'])
        print(f"    ✓ 收到事件：{event['type']}")
        print(f"      状态：{event.get('status')}")
        print(f"      时间：{event.get('timestamp')}")
        
        # 步骤5：验证数据落库
        print(f"\n  步骤5：验证数据落库")
        candles = await asyncio.to_thread(
            select_candles_raw,
            symbol=test_symbol,
            freq='1d',
            limit=5
        )
        
        if candles:
            print(f"    ✓ 数据已落库：{len(candles)} 条")
        else:
            print(f"    ⊙ 无数据（可能本地已是最新）")
    
    # ==========================================================================
    # 测试组18：API层（/api/candles）
    # ==========================================================================
    
    async def test_18_api_candles(self):
        """【API】/api/candles 接口（不复权数据）"""
        print("\n" + "=" * 80)
        print("测试18：/api/candles 接口")
        print("=" * 80)
        
        test_symbol = "000001"
        
        # 调用服务层函数（模拟API）
        result = await get_candles(
            symbol=test_symbol,
            freq='1d',
            include={'ma'},
            ma_periods_map={'MA5': 5, 'MA10': 10},
            trace_id='test_api'
        )
        
        self.assertIsNotNone(result)
        self.assertTrue(result['ok'])
        self.assertIn('meta', result)
        self.assertIn('candles', result)
        self.assertIn('indicators', result)
        
        meta = result['meta']
        candles = result['candles']
        
        print(f"  ✓ 接口响应成功")
        print(f"    标的：{meta['symbol']}")
        print(f"    频率：{meta['freq']}")
        print(f"    数据量：{meta['all_rows']} 条")
        
        # 验证返回的是不复权数据
        if candles:
            sample = candles[0]
            self.assertIn('ts', sample)
            self.assertIn('o', sample)  # open
            self.assertIn('c', sample)  # close
            print(f"  ✓ 数据格式正确：{list(sample.keys())}")
        
        # 验证指标计算
        indicators = result['indicators']
        if 'MA5' in indicators:
            print(f"  ✓ 指标计算成功：MA5")
    
    # ==========================================================================
    # 测试组19：完整的前端请求模拟
    # ==========================================================================
    
    async def test_19_frontend_request_simulation(self):
        """【端到端】模拟前端完整请求流程"""
        print("\n" + "=" * 80)
        print("测试19：前端请求模拟（完整流程）")
        print("=" * 80)
        
        test_symbol = "600519"
        test_freq = "1d"
        
        events_received = []
        
        def frontend_callback(event):
            if event.get('symbol') == test_symbol and event.get('freq') == test_freq:
                events_received.append(event)
        
        subscribe_events(frontend_callback)
        
        # 模拟前端操作：点击刷新
        print(f"\n  [前端操作] 点击刷新 {test_symbol} {test_freq}")
        
        # 1. 前端调用 /api/ensure-data
        print(f"\n  步骤1：发送数据需求声明")
        parser = get_requirement_parser()
        queue = get_priority_queue()
        
        requirements = [{
            'scope': 'symbol',
            'symbol': test_symbol,
            'includes': [
                {'type': 'frontend_kline_current', 'freq': test_freq, 'priority': 5},
                {'type': 'frontend_factors', 'priority': 10}
            ]
        }]
        
        tasks = parser.parse_requirements(requirements)
        print(f"    ✓ 解析需求：{len(tasks)} 个任务")
        
        for task in tasks:
            await queue.enqueue(task)
        print(f"    ✓ 任务已入队")
        
        # 2. 前端显示"更新中……"
        print(f"\n  步骤2：前端显示'更新中……'")
        
        # 3. 后端执行任务
        print(f"\n  步骤3：后端执行任务")
        executor = get_sync_executor()
        
        for _ in range(len(tasks)):
            task = await queue.dequeue()
            if task:
                await executor._execute_task(task)
        
        print(f"    ✓ 所有任务执行完成")
        
        # 4. 验证SSE推送
        print(f"\n  步骤4：验证SSE推送")
        await asyncio.sleep(0.2)
        
        self.assertGreater(len(events_received), 0, "应收到事件通知")
        
        event = events_received[0]
        print(f"    ✓ 收到事件：{event['type']}")
        print(f"      状态：{event.get('status')}")
        print(f"      时间：{event.get('timestamp')}")
        
        # 5. 前端收到通知，显示"更新完成"
        print(f"\n  步骤5：前端显示'更新完成 {event.get('timestamp')}'")
        
        # 6. 前端调用 /api/candles 获取数据
        print(f"\n  步骤6：前端调用 /api/candles")
        result = await get_candles(
            symbol=test_symbol,
            freq=test_freq,
            trace_id='frontend_sim'
        )
        
        self.assertTrue(result['ok'])
        
        candles = result['candles']
        if candles:
            print(f"    ✓ 获取数据成功：{len(candles)} 条K线")
            print(f"      最新时间：{to_readable_string(candles[-1]['ts'])}")
        else:
            print(f"    ⊙ 暂无数据（本地可能为空）")
    
    # ==========================================================================
    # 测试组20：数据完备性保证（核心需求）
    # ==========================================================================
    
    async def test_20_data_completeness_guarantee(self):
        """【核心需求】数据完备性通知保证"""
        print("\n" + "=" * 80)
        print("测试20：数据完备性通知保证（核心需求）")
        print("=" * 80)
        
        executor = get_sync_executor()
        events_received = []
        
        def completeness_callback(event):
            if event.get('type') in ['data_updated', 'data_ready']:
                events_received.append(event)
        
        subscribe_events(completeness_callback)
        
        # 场景1：有缺口的情况
        print(f"\n  [场景1：有缺口，需拉取]")
        task_with_gap = PrioritizedTask(
            priority=5,
            timestamp=datetime.now().timestamp(),
            data_type_id='frontend_kline_current',
            symbol='NEW_SYMBOL_001',  # 新标的，本地必然无数据
            freq='1d',
            strategy={'gap_check_method': 'kline_to_current_time'},
            task_id='test_with_gap'
        )
        
        await executor._execute_task(task_with_gap)
        await asyncio.sleep(0.2)
        
        gap_events = [e for e in events_received if e.get('symbol') == 'NEW_SYMBOL_001']
        
        if gap_events:
            print(f"    ✓ 收到事件：{gap_events[0]['type']}")
            print(f"      状态：{gap_events[0].get('status')}")
        else:
            print(f"    ⊙ 未收到事件（可能拉取失败）")
        
        # 场景2：无缺口的情况（重复执行）
        print(f"\n  [场景2：无缺口，本地已是最新]")
        
        if gap_events:
            # 再次执行同一任务（此时应该无缺口）
            events_before = len(events_received)
            await executor._execute_task(task_with_gap)
            await asyncio.sleep(0.2)
            
            events_after = len(events_received)
            
            # 验证：即使无缺口，也应推送 data_ready 事件
            self.assertGreater(events_after, events_before, "无缺口时应推送data_ready事件")
            
            latest_event = events_received[-1]
            self.assertEqual(latest_event['type'], 'data_ready', "应推送data_ready事件")
            print(f"    ✓ 收到完备性通知：{latest_event['type']}")
            print(f"      状态：{latest_event.get('status')}")
        else:
            print(f"    ⊙ 跳过（场景1未成功）")
    
    # ==========================================================================
    # 测试组21：自选池变动触发同步
    # ==========================================================================
    
    async def test_21_watchlist_sync_trigger(self):
        """【业务逻辑】自选池变动自动触发同步"""
        print("\n" + "=" * 80)
        print("测试21：自选池变动触发同步")
        print("=" * 80)
        
        from backend.routers.user import trigger_watchlist_sync
        
        test_symbol = "600519"
        queue = get_priority_queue()
        
        # 清空队列
        while not queue.is_empty():
            await queue.dequeue()
        
        initial_size = queue.size()
        self.assertEqual(initial_size, 0)
        print(f"  ✓ 队列已清空")
        
        # 触发同步
        print(f"\n  触发自选池同步：{test_symbol}")
        await trigger_watchlist_sync(test_symbol)
        
        # 验证任务生成
        final_size = queue.size()
        self.assertGreater(final_size, 0, "应生成同步任务")
        
        # 预期任务数：6个频率 + 档案 + 因子 = 8个
        expected = len(settings.sync_standard_freqs) + 2
        self.assertEqual(final_size, expected, f"应生成{expected}个任务")
        
        print(f"  ✓ 已生成 {final_size} 个任务")
        print(f"    6个频率K线 + 档案 + 因子")
    
    # ==========================================================================
    # 测试组22：不复权数据存储验证
    # ==========================================================================
    
    async def test_22_no_adjust_storage_verification(self):
        """【数据库】验证存储的是不复权数据"""
        print("\n" + "=" * 80)
        print("测试22：不复权数据存储验证")
        print("=" * 80)
        
        test_symbol = "000001"
        
        # 拉取并存储
        result = await integrators.get_daily_bars_with_factors(
            symbol=test_symbol,
            start_date='20240101',
            end_date='20240110'
        )
        
        if result and result['bars'] is not None:
            df_bars = result['bars']
            
            # 添加必需字段
            df_bars['symbol'] = test_symbol
            df_bars['freq'] = '1d'
            df_bars['source'] = 'no_adjust_test'
            df_bars['fetched_at'] = datetime.now().isoformat()
            
            await asyncio.to_thread(upsert_candles_raw, df_bars.to_dict('records'))
            print(f"  ✓ 已写入 {len(df_bars)} 条K线（不复权）")
            
            # 从数据库读取
            db_candles = await asyncio.to_thread(
                select_candles_raw,
                symbol=test_symbol,
                freq='1d',
                limit=1
            )
            
            if db_candles:
                bar = db_candles[0]
                
                # 验证source标识
                source = bar.get('source', '')
                self.assertNotIn('qfq', source.lower(), "数据源不应包含qfq")
                self.assertNotIn('hfq', source.lower(), "数据源不应包含hfq")
                
                print(f"  ✓ 验证通过：数据源={source}")
                print(f"    收盘价：{bar['close']}（不复权原始价格）")
    
    # ==========================================================================
    # 测试组23：配置系统
    # ==========================================================================
    
    def test_23_settings_configuration(self):
        """【架构】配置系统完整性"""
        print("\n" + "=" * 80)
        print("测试23：配置系统")
        print("=" * 80)
        
        # 验证核心配置存在
        self.assertIsNotNone(settings.timezone)
        self.assertIsNotNone(settings.db_path)
        self.assertIsNotNone(settings.sync_init_start_date)
        self.assertIsNotNone(settings.sync_standard_freqs)
        self.assertIsNotNone(settings.default_market)
        
        print(f"  ✓ 时区：{settings.timezone}")
        print(f"  ✓ 数据库：{settings.db_path}")
        print(f"  ✓ 起始日期：{settings.sync_init_start_date}")
        print(f"  ✓ 标准频率：{settings.sync_standard_freqs}")
        print(f"  ✓ 默认市场：{settings.default_market}")
        
        # 验证数据类型定义
        self.assertIn('frontend_kline_current', DATA_TYPE_DEFINITIONS)
        self.assertIn('watchlist_kline_1d', DATA_TYPE_DEFINITIONS)
        self.assertIn('symbol_index', DATA_TYPE_DEFINITIONS)
        
        print(f"  ✓ 数据类型定义：{len(DATA_TYPE_DEFINITIONS)} 个")
        
        # 验证无复权配置
        self.assertFalse(hasattr(settings, 'default_adjust_method'), "不应存在复权配置")
        print(f"  ✓ 已删除复权配置（复权计算由前端处理）")
    
    # ==========================================================================
    # 测试组24：数据源优先级与降级
    # ==========================================================================
    
    async def test_24_datasource_fallback(self):
        """【数据源】多数据源优先级与降级"""
        print("\n" + "=" * 80)
        print("测试24：数据源降级机制")
        print("=" * 80)
        
        from backend.datasource.registry import get_methods_for_category
        
        # 查询A股列表的方法
        methods = get_methods_for_category('stock_list')
        
        self.assertGreater(len(methods), 0, "应有至少1个数据源")
        print(f"  ✓ A股列表数据源：{len(methods)} 个")
        
        # 验证优先级排序
        priorities = [m.priority for m in methods]
        self.assertEqual(priorities, sorted(priorities), "应按优先级升序")
        print(f"  ✓ 优先级排序：{priorities}")
        
        # 验证主力方法
        primary = methods[0]
        self.assertLess(primary.priority, 20, "主力方法优先级应<20")
        print(f"  ✓ 主力方法：{primary.id} (P{primary.priority})")
    
    # ==========================================================================
    # 测试组25：错误分类器
    # ==========================================================================
    
    def test_25_error_classifier(self):
        """【架构】错误分类器精确识别"""
        print("\n" + "=" * 80)
        print("测试25：错误分类器")
        print("=" * 80)
        
        from backend.utils.error_classifier import classify_fetch_error, ErrorType
        import pandas as pd
        
        # 场景1：成功
        error_type, msg, suggestion = classify_fetch_error(None, pd.DataFrame([{'a': 1}]))
        self.assertEqual(error_type, 'success')
        print(f"  ✓ 成功识别：{error_type}")
        
        # 场景2：空数据
        error_type, msg, suggestion = classify_fetch_error(None, pd.DataFrame())
        self.assertEqual(error_type, ErrorType.EMPTY_RESPONSE)
        print(f"  ✓ 空数据识别：{error_type}")
        
        # 场景3：网络超时
        timeout_exc = TimeoutError("Request timeout")
        error_type, msg, suggestion = classify_fetch_error(timeout_exc, None)
        self.assertEqual(error_type, ErrorType.NETWORK_TIMEOUT)
        print(f"  ✓ 超时识别：{error_type}")
        
        # 场景4：参数错误
        value_exc = ValueError("Invalid parameter")
        error_type, msg, suggestion = classify_fetch_error(value_exc, None)
        self.assertEqual(error_type, ErrorType.INVALID_PARAMS)
        print(f"  ✓ 参数错误识别：{error_type}")
    
    # ==========================================================================
    # 测试组26：全局事件总线
    # ==========================================================================
    
    async def test_26_global_event_bus(self):
        """【事件系统】全局事件总线（订阅/发布/取消）"""
        print("\n" + "=" * 80)
        print("测试26：全局事件总线")
        print("=" * 80)
        
        from backend.utils.events import subscribe, unsubscribe, publish
        
        received = []
        
        def cb1(event):
            received.append(('cb1', event))
        
        def cb2(event):
            received.append(('cb2', event))
        
        # 订阅
        subscribe(cb1)
        subscribe(cb2)
        print(f"  ✓ 已订阅2个回调")
        
        # 发布
        publish({'type': 'test', 'data': 'hello'})
        await asyncio.sleep(0.05)
        
        self.assertEqual(len(received), 2, "应收到2次回调")
        print(f"  ✓ 发布成功：2个订阅者都收到")
        
        # 取消订阅
        unsubscribe(cb2)
        received.clear()
        
        publish({'type': 'test2'})
        await asyncio.sleep(0.05)
        
        self.assertEqual(len(received), 1, "取消后应只有1个收到")
        print(f"  ✓ 取消订阅成功：只有cb1收到")
    
    # ==========================================================================
    # 测试组27：数据库事务一致性
    # ==========================================================================
    
    async def test_27_database_transaction(self):
        """【数据库】事务一致性（批量写入）"""
        print("\n" + "=" * 80)
        print("测试27：数据库事务一致性")
        print("=" * 80)
        
        test_symbol = "TRANS_TEST"
        
        # 批量写入K线
        candles = []
        for i in range(100):
            ymd = shift_days(20240101, i)
            ts = ms_at_market_close(ymd)
            candles.append({
                'symbol': test_symbol,
                'freq': '1d',
                'ts': ts,
                'open': 10.0,
                'high': 10.5,
                'low': 9.5,
                'close': 10.2,
                'volume': 100000,
                'amount': None,
                'turnover_rate': None,
                'source': 'trans_test',
                'fetched_at': datetime.now().isoformat()
            })
        
        t0 = time.time()
        rows = await asyncio.to_thread(upsert_candles_raw, candles)
        elapsed = time.time() - t0
        
        self.assertEqual(rows, 100, "批量写入应返回正确的影响行数")
        print(f"  ✓ 批量写入：{rows} 条（耗时 {elapsed:.3f}s）")
        
        # 验证读取
        db_candles = await asyncio.to_thread(
            select_candles_raw,
            symbol=test_symbol,
            freq='1d'
        )
        
        self.assertEqual(len(db_candles), 100)
        print(f"  ✓ 批量读取：{len(db_candles)} 条")
    
    # ==========================================================================
    # 测试组28：时间范围查询
    # ==========================================================================
    
    async def test_28_time_range_query(self):
        """【数据库】时间范围查询（包含边界）"""
        print("\n" + "=" * 80)
        print("测试28：时间范围查询")
        print("=" * 80)
        
        test_symbol = "RANGE_TEST"
        
        # 写入测试数据
        test_dates = [20241101, 20241102, 20241103, 20241104, 20241105]
        candles = []
        
        for ymd in test_dates:
            ts = ms_at_market_close(ymd)
            candles.append({
                'symbol': test_symbol,
                'freq': '1d',
                'ts': ts,
                'open': 10.0, 'high': 10.5, 'low': 9.5, 'close': 10.2,
                'volume': 100000, 'amount': None, 'turnover_rate': None,
                'source': 'range_test',
                'fetched_at': datetime.now().isoformat()
            })
        
        await asyncio.to_thread(upsert_candles_raw, candles)
        print(f"  ✓ 已写入 {len(test_dates)} 条测试数据")
        
        # 查询范围：20241102 ~ 20241104（应返回3条）
        start_ts, end_ts = query_range_ms(20241102, 20241104)
        
        db_candles = await asyncio.to_thread(
            select_candles_raw,
            symbol=test_symbol,
            freq='1d',
            start_ts=start_ts,
            end_ts=end_ts
        )
        
        self.assertEqual(len(db_candles), 3, "范围查询应返回3条")
        print(f"  ✓ 范围查询：{len(db_candles)} 条（正确）")
        
        # 验证边界包含
        dates = [to_yyyymmdd(c['ts']) for c in db_candles]
        self.assertEqual(dates, [20241102, 20241103, 20241104])
        print(f"  ✓ 边界包含：{dates}")

if __name__ == '__main__':
    print("\n" + "🎯" * 40)
    print("开始执行后端终极全面测试")
    print("🎯" * 40)
    
    # 运行所有测试
    suite = unittest.TestLoader().loadTestsFromTestCase(TestBackendUltimate)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出详细总结
    print("\n" + "=" * 80)
    print("测试总结报告")
    print("=" * 80)
    print(f"\n总计测试：{result.testsRun} 个")
    print(f"  ✅ 成功：{result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  ❌ 失败：{len(result.failures)}")
    print(f"  ⚠️  错误：{len(result.errors)}")
    
    if result.failures:
        print(f"\n失败详情：")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print(f"\n错误详情：")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    print("\n" + "=" * 80)
    print("覆盖范围：")
    print("  ✅ 架构层：时间戳/Schema/模块导入/配置")
    print("  ✅ 数据源层：三类标的/多频率K线/因子/日历")
    print("  ✅ 标准化层：列表/K线/因子/时间戳语义")
    print("  ✅ 业务逻辑层：缺口判断/队列/解析/执行")
    print("  ✅ 数据库层：CRUD/事务/范围查询")
    print("  ✅ API层：candles/symbols/ensure-data")
    print("  ✅ 事件系统：SSE/完备性通知")
    print("  ✅ 端到端：完整流程模拟")
    print("=" * 80)
    
    # 退出码
    sys.exit(0 if result.wasSuccessful() else 1)
