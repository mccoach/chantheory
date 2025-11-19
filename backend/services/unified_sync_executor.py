# backend/services/unified_sync_executor.py
# ==============================
# V10.0 - 去冗余因子版（K线任务不再写入因子）
# 说明：
#   - K线任务(_fetch_kline) 只负责拉取K线与因子来源标识，不再展开或返回因子数据。
#   - 因子任务(_fetch_factors) 负责拉取并合并前/后复权因子，写库前在 async_writer 中统一压缩。
# ==============================

from __future__ import annotations
import asyncio
import pandas as pd
from typing import Optional, Any
from datetime import datetime

from backend.settings import settings, GAP_CHECK_METHODS, DATA_TYPE_DEFINITIONS
from backend.services.priority_queue import get_priority_queue, PrioritizedTask
from backend.datasource import dispatcher
from backend.services.symbol_sync import sync_all_symbols
from backend.db.async_writer import get_async_writer
from backend.db.symbols import upsert_symbol_profile
from backend.db.calendar import upsert_trade_calendar
from backend.utils.sse_manager import get_sse_manager
from backend.utils.events import publish as publish_event
from backend.utils.logger import get_logger
from backend.utils.async_limiter import limit_async_network_io
from backend.utils.time import today_ymd

_LOG = get_logger("sync_executor")

class UnifiedSyncExecutor:
    """统一同步执行器（V10.0 - 去冗余因子版）"""
    
    def __init__(self):
        self.queue = get_priority_queue()
        self.running = False
        self._stop_flag = False
        self.db_writer = get_async_writer()
    
    async def start(self):
        """启动执行器"""
        if self.running:
            _LOG.warning("[执行器] 已在运行")
            return
        
        self.running = True
        self._stop_flag = False
        
        # ===== 启动异步写入器 =====
        await self.db_writer.start()
        
        _LOG.info("[执行器] 启动任务循环")
        
        while not self._stop_flag:
            try:
                task = await self.queue.wait_for_task()
                await self._execute_task(task)
            except asyncio.CancelledError:
                _LOG.info("[执行器] 收到取消信号")
                break
            except Exception as e:
                _LOG.error(f"[执行器] 执行任务异常: {e}")
                await asyncio.sleep(1)
        
        self.running = False
        _LOG.info("[执行器] 执行循环已停止")
    
    async def stop(self):
        """停止执行器"""
        self._stop_flag = True
        
        # ===== 停止异步写入器（确保数据落盘）=====
        await self.db_writer.stop()
    
    async def _execute_task(self, task: PrioritizedTask):
        """执行单个任务"""
        
        _LOG.info(
            f"[执行器] 开始 P{task.priority} {task.data_type_id} "
            f"{task.symbol or ''} {task.freq or ''} "
            f"类型={task.symbol_type or 'N/A'}"
        )
        
        try:
            # 1. 判断缺口
            has_gap = await self._call_gap_check(task)
            
            # 2. 判断是否需要推送SSE（只有current_推送）
            should_push = task.data_type_id.startswith('current_')
            
            if not has_gap:
                if should_push:
                    await self._push_event(task, 'already_latest')
                
                _LOG.info(
                    f"[执行器] 已完备 {task.data_type_id} "
                    f"{task.symbol or ''} {task.freq or ''} 推送={should_push}"
                )
                return
            
            # 3. 拉取数据
            data = await self._fetch_data(task)
            
            if data is None:
                _LOG.warning(f"[执行器] 拉取失败: {task.task_id}")
                return
            
            # 4. 落库（使用异步写入器）
            await self._save_data(task, data)
            
            # 5. 推送事件（透传 source_id）
            if should_push:
                await self._push_event(task, 'newly_fetched', data)
            
            _LOG.info(
                f"[执行器] 完成 {task.data_type_id} "
                f"{task.symbol or ''} {task.freq or ''} "
                f"来源={data.get('source_id', 'unknown')} "
                f"推送={should_push}"
            )
        
        except Exception as e:
            _LOG.error(f"[执行器] 失败 {task.task_id}: {e}", exc_info=True)
    
    async def _call_gap_check(self, task: PrioritizedTask) -> bool:
        """调用缺口判断（传递 force_fetch）"""
        strategy = task.strategy or {}
        method_name = strategy.get('gap_check_method', 'always_fetch')
        func_path = GAP_CHECK_METHODS.get(method_name)
        
        if not func_path:
            _LOG.error(f"[执行器] 未知缺口方法: {method_name}")
            return True
        
        if func_path == "lambda **kwargs: True":
            return True
        
        module_path, func_name = func_path.rsplit('.', 1)
        import importlib
        module = importlib.import_module(f"backend.{module_path}")
        func = getattr(module, func_name)
        
        return func(
            symbol=task.symbol, 
            freq=task.freq, 
            data_type_id=task.data_type_id,
            force_fetch=task.force_fetch
        )
    
    async def _push_event(self, task: PrioritizedTask, status: str, data: Any = None):
        """推送SSE事件（透传 source_id）"""
        manager = get_sse_manager()
        category = DATA_TYPE_DEFINITIONS[task.data_type_id].get('category')
        
        event = {
            'type': 'data_ready',
            'category': category,
            'data_type': task.data_type_id,
            'symbol': task.symbol,
            'freq': task.freq,
            'status': status,
            'timestamp': datetime.now().isoformat()
        }
        
        # 透传 source_id
        if data is not None and isinstance(data, dict):
            source_id = data.get('source_id')
            if source_id:
                event['source_id'] = source_id
        
        await manager.broadcast(event)
    
    @limit_async_network_io
    async def _fetch_data(self, task: PrioritizedTask) -> Optional[Any]:
        """拉取数据"""
        category = DATA_TYPE_DEFINITIONS[task.data_type_id].get('category')
        
        if category == 'kline':
            return await self._fetch_kline(task)
        elif category == 'factors':
            return await self._fetch_factors(task)
        elif category == 'profile':
            return await self._fetch_profile(task)
        elif category == 'symbol_index':
            return await self._fetch_symbol_index()
        elif category == 'trade_calendar':
            return await self._fetch_trade_calendar()
        
        return None
    
    async def _fetch_kline(self, task: PrioritizedTask):
        """
        拉取K线（V10.0 - 仅K线，不再返回因子）
        
        设计原则：
          - K线任务专注于行情数据（category='kline'）
          - 因子任务（category='factors'）单独负责复权因子获取与写库
          - 前端在使用时按日期前向填充因子（稀疏存储）
        """
        symbol = task.symbol
        freq = task.freq
        symbol_type = task.symbol_type or 'A'
        
        start_ymd = settings.sync_init_start_date
        end_ymd = today_ymd()
        
        _LOG.info(
            f"[执行器] 拉取K线: {symbol} {freq} (类型={symbol_type})"
        )
        
        # ===== 步骤1：根据标的类型选择基础 category =====
        if symbol_type == 'A':
            base_category_prefix = 'stock'
        elif symbol_type in ['ETF', 'LOF']:
            _LOG.warning(
                f"[执行器] ETF/LOF路由暂未实现，降级到A股: {symbol}"
            )
            base_category_prefix = 'stock'
        elif symbol_type == 'INDEX':
            _LOG.warning(
                f"[执行器] 指数路由暂未实现，降级到A股: {symbol}"
            )
            base_category_prefix = 'stock'
        else:
            _LOG.warning(
                f"[执行器] 未知类型 {symbol_type}，降级到A股: {symbol}"
            )
            base_category_prefix = 'stock'
        
        # ===== 步骤2：根据频率独立路由 =====
        
        # 分支1：分钟线
        if freq in ['1m', '5m', '15m', '30m', '60m']:
            routed_category = f'{base_category_prefix}_minutely_bars'
            
            kwargs = {
                'symbol': symbol,
                'period': freq[:-1],  # '5m' → '5'
            }
            
            _LOG.info(
                f"[路由决策] {symbol} {freq}: "
                f"类型={symbol_type} → category={routed_category} "
                f"(分钟线固定返回最近~2000条)"
            )
        
        # 分支2：日K
        elif freq == '1d':
            routed_category = f'{base_category_prefix}_daily_bars'
            
            kwargs = {
                'symbol': symbol,
                'period': 'daily',
                'start_date': f"{start_ymd:08d}",
                'end_date': f"{end_ymd:08d}",
                'adjust': '',
                'symbol_type': symbol_type,
            }
            
            _LOG.info(
                f"[路由决策] {symbol} 1d: "
                f"类型={symbol_type} → category={routed_category}"
            )
        
        # 分支3：周K
        elif freq == '1w':
            routed_category = f'{base_category_prefix}_weekly_bars'
            
            kwargs = {
                'symbol': symbol,
                'start_date': f"{start_ymd:08d}",
                'end_date': f"{end_ymd:08d}",
                'adjust': '',
                'symbol_type': symbol_type,
            }
            
            _LOG.info(
                f"[路由决策] {symbol} 1w: "
                f"类型={symbol_type} → category={routed_category}"
            )
        
        # 分支4：月K
        elif freq == '1M':
            routed_category = f'{base_category_prefix}_monthly_bars'
            
            kwargs = {
                'symbol': symbol,
                'start_date': f"{start_ymd:08d}",
                'end_date': f"{end_ymd:08d}",
                'adjust': '',
                'symbol_type': symbol_type,
            }
            
            _LOG.info(
                f"[路由决策] {symbol} 1M: "
                f"类型={symbol_type} → category={routed_category}"
            )
        
        else:
            _LOG.error(f"[执行器] 不支持的频率: {freq}")
            return None
        
        # ===== 步骤3：拉取 K线 =====
        raw_bars_df, source_id = await dispatcher.fetch(
            routed_category,
            freq=freq,
            **kwargs
        )
        
        if raw_bars_df is None or raw_bars_df.empty:
            _LOG.warning(
                f"[执行器] K线拉取失败: {symbol} {freq} "
                f"(category={routed_category})"
            )
            return None
        
        _LOG.info(
            f"[数据获取] {symbol} {freq}: "
            f"来源={source_id}, 原始行数={len(raw_bars_df)}"
        )
        
        # ===== 步骤4：标准化K线 =====
        from backend.services.normalizer import normalize_bars_df
        
        df_bars = normalize_bars_df(raw_bars_df, source_id)
        
        if df_bars is None or df_bars.empty:
            _LOG.error(
                f"[执行器] K线标准化失败: {symbol} {freq}"
            )
            return None
        
        result = {
            'bars': df_bars,
            'factors': None,          # 因子交由独立任务处理
            'source_id': source_id or 'unknown'
        }
        
        _LOG.info(
            f"[执行器] K线处理完成: {symbol} {freq} "
            f"K线={len(df_bars)}根, "
            f"因子=独立任务处理, "
            f"来源={result['source_id']}"
        )
        
        return result
    
    async def _fetch_factors(self, task: PrioritizedTask):
        """拉取因子（前后复权），返回稀疏因子表"""
        results = await asyncio.gather(
            dispatcher.fetch('adj_factor', symbol=task.symbol, adjust_type='qfq-factor'),
            dispatcher.fetch('adj_factor', symbol=task.symbol, adjust_type='hfq-factor'),
            return_exceptions=True
        )
        
        raw_qfq_df, qfq_source_id = results[0] if not isinstance(results[0], Exception) else (None, None)
        raw_hfq_df, hfq_source_id = results[1] if not isinstance(results[1], Exception) else (None, None)
        
        if raw_qfq_df is None or raw_hfq_df is None:
            return None
        
        from backend.services.normalizer import normalize_adj_factors_df
        
        df_qfq = normalize_adj_factors_df(raw_qfq_df, qfq_source_id)
        df_hfq = normalize_adj_factors_df(raw_hfq_df, hfq_source_id)
        
        if df_qfq is None or df_hfq is None:
            return None
        
        df_factors = pd.merge(
            df_qfq.rename(columns={'factor': 'qfq_factor'}),
            df_hfq.rename(columns={'factor': 'hfq_factor'}),
            on='date', how='outer'
        )
        
        return df_factors
    
    async def _fetch_profile(self, task: PrioritizedTask):
        """拉取档案"""
        raw_df, source_id = await dispatcher.fetch('stock_profile', symbol=task.symbol)
        
        if raw_df is None or raw_df.empty:
            return None
        
        return {'raw_df': raw_df, 'source': source_id}
    
    async def _fetch_symbol_index(self):
        """拉取标的列表"""
        result = await sync_all_symbols()
        
        publish_event({
            'type': 'symbol_index_ready',
            'status': 'success' if result['success'] else 'failed',
            'summary': result,
            'timestamp': datetime.now().isoformat()
        })
        
        return result
    
    async def _fetch_trade_calendar(self):
        """拉取交易日历"""
        raw_df, source_id = await dispatcher.fetch('trade_calendar')
        
        if raw_df is None or raw_df.empty:
            return None
        
        return {'raw_df': raw_df, 'source': source_id}
    
    async def _save_data(self, task: PrioritizedTask, data: Any):
        """
        落库（V8.0 - 异步队列版）
        
        核心改造：
          - 使用 AsyncDBWriter 异步提交
          - 立即返回（不等待落盘）
          - 批量合并（自动去重）
        """
        category = DATA_TYPE_DEFINITIONS[task.data_type_id].get('category')
        
        if category == 'kline':
            df_bars = data.get('bars')
            df_factors = data.get('factors')  # V10.0：此处始终为 None（因子由独立任务处理）
            source_id = data.get('source_id', 'unknown')
            
            if df_bars is not None and not df_bars.empty:
                df_bars['symbol'] = task.symbol
                df_bars['freq'] = task.freq
                df_bars['source'] = source_id
                df_bars['fetched_at'] = datetime.now().isoformat()
                
                await self.db_writer.write_candles(df_bars.to_dict('records'))
                
                _LOG.debug(
                    f"[落库] 已提交K线到队列: {task.symbol} {task.freq} "
                    f"{len(df_bars)}根"
                )
            
            # df_factors 在 V10.0 不再从 K 线任务写入（因子任务独立处理）
        
        elif category == 'factors':
            # 单独拉取因子的情况（稀疏表）
            if data is not None and not (isinstance(data, pd.DataFrame) and data.empty):
                if isinstance(data, pd.DataFrame):
                    data['symbol'] = task.symbol
                    data['updated_at'] = datetime.now().isoformat()
                    
                    await self.db_writer.write_factors(data.to_dict('records'))
        
        elif category == 'profile':
            from backend.services.normalizer import normalize_stock_profile_df
            
            raw_df = data.get('raw_df')
            profile_dict = normalize_stock_profile_df(raw_df)
            
            if profile_dict:
                try:
                    from backend.db.symbols import ensure_symbol_in_index
                    
                    await asyncio.to_thread(
                        ensure_symbol_in_index,
                        symbol=task.symbol,
                        symbol_type=task.symbol_type or 'A',
                        name=profile_dict.get('name', ''),
                    )
                    
                    _LOG.debug(
                        f"[落库] 已确保symbol在索引表: {task.symbol}"
                    )
                except Exception as e:
                    _LOG.warning(
                        f"[落库] 确保symbol存在失败: {task.symbol}, {e}"
                    )
                
                profile_dict['symbol'] = task.symbol
                profile_dict['updated_at'] = datetime.now().isoformat()
                
                profile_dict.setdefault('listing_date', None)
                profile_dict.setdefault('total_shares', None)
                profile_dict.setdefault('float_shares', None)
                profile_dict.setdefault('industry', None)
                profile_dict.setdefault('region', None)
                profile_dict.setdefault('concepts', None)
                
                await self.db_writer.write_profile(profile_dict)
        
        elif category == 'trade_calendar':
            from backend.services.normalizer import normalize_trade_calendar_df
            
            raw_df = data.get('raw_df')
            clean_df = normalize_trade_calendar_df(raw_df)
            
            if clean_df is not None and not clean_df.empty:
                records = [
                    {'date': int(row['date']), 'market': settings.default_market, 'is_trading_day': 1}
                    for _, row in clean_df.iterrows()
                ]
                
                await asyncio.to_thread(upsert_trade_calendar, records)


# ===== 全局单例 =====
_executor: Optional[UnifiedSyncExecutor] = None


def get_sync_executor() -> UnifiedSyncExecutor:
    global _executor
    if _executor is None:
        _executor = UnifiedSyncExecutor()
    return _executor