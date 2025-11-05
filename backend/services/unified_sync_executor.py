# backend/services/unified_sync_executor.py
# ==============================
# 说明：统一同步执行器（V4.0 - 完备性通知版）
# 核心改造：
#   1. 无缺口时也推送SSE（'data_ready'事件）
#   2. 使用标准时间函数
#   3. 拉取时固定使用不复权数据
# ==============================

from __future__ import annotations

import asyncio
import pandas as pd
from typing import Optional, Any, Dict
from datetime import datetime

from backend.settings import settings, GAP_CHECK_METHODS, REFRESH_STRATEGIES, DATA_TYPE_DEFINITIONS
from backend.services.priority_queue import get_priority_queue, PrioritizedTask
from backend.datasource import dispatcher
from backend.services import integrators
from backend.services.symbol_sync import sync_all_symbols
from backend.db.candles import upsert_candles_raw
from backend.db.factors import upsert_factors
from backend.db.symbols import upsert_symbol_profile
from backend.db.calendar import upsert_trade_calendar
from backend.utils.events import publish as publish_event
from backend.utils.logger import get_logger, log_event
from backend.utils.async_limiter import limit_async_network_io
from backend.utils.time import today_ymd

_LOG = get_logger("sync_executor")

class UnifiedSyncExecutor:
    """统一同步执行器"""
    
    def __init__(self):
        self.queue = get_priority_queue()
        self.running = False
        self._stop_flag = False
    
    async def start(self):
        """启动执行器（消费队列）"""
        if self.running:
            _LOG.warning("[执行器] 已在运行，跳过重复启动")
            return
        
        self.running = True
        self._stop_flag = False
        
        _LOG.info("[执行器] 启动任务执行循环")
        
        while not self._stop_flag:
            try:
                # 等待任务（阻塞）
                task = await self.queue.wait_for_task()
                
                # 执行任务
                await self._execute_task(task)
                
            except asyncio.CancelledError:
                _LOG.info("[执行器] 收到取消信号")
                break
            except Exception as e:
                _LOG.error(f"[执行器] 执行任务时异常: {e}")
                await asyncio.sleep(1)
        
        self.running = False
        _LOG.info("[执行器] 执行循环已停止")
    
    async def stop(self):
        """停止执行器"""
        self._stop_flag = True
    
    async def _execute_task(self, task: PrioritizedTask):
        """执行单个任务（统一工作流）"""
        
        log_event(
            logger=_LOG,
            service="sync_executor",
            level="INFO",
            file=__file__,
            func="_execute_task",
            line=0,
            trace_id=task.task_id,
            event="task.start",
            message=f"开始执行任务 P{task.priority}",
            extra={
                "task_id": task.task_id,
                "data_type": task.data_type_id,
                "symbol": task.symbol,
                "freq": task.freq
            }
        )
        
        try:
            # ===== 步骤1: 判断缺口 =====
            strategy = task.strategy or {}
            gap_check_method_name = strategy.get('gap_check_method', 'always_fetch')
            gap_check_func_path = GAP_CHECK_METHODS.get(gap_check_method_name)
            
            if not gap_check_func_path:
                _LOG.error(f"[执行器] 未知缺口判断方法: {gap_check_method_name}")
                return
            
            # 动态导入函数
            has_gap = await self._call_gap_check(
                gap_check_func_path,
                task.symbol,
                task.freq,
                task.data_type_id
            )
            
            if not has_gap:
                # ===== 核心修改：无缺口时也推送完备性通知 =====
                log_event(
                    logger=_LOG,
                    service="sync_executor",
                    level="INFO",
                    file=__file__,
                    func="_execute_task",
                    line=0,
                    trace_id=task.task_id,
                    event="task.already_latest",
                    message="数据已完备，无需拉取",
                    extra={"task_id": task.task_id}
                )
                
                # 推送"数据已完备"事件（前端据此更新UI）
                publish_event({
                    'type': 'data_ready',
                    'symbol': task.symbol,
                    'freq': task.freq,
                    'data_type': task.data_type_id,
                    'status': 'already_latest',
                    'message': '本地数据已是最新',
                    'timestamp': datetime.now().isoformat()
                })
                
                return
            
            # ===== 步骤2: 拉取数据 =====
            data = await self._fetch_data(task)
            
            if data is None:
                _LOG.warning(f"[执行器] 数据拉取失败: {task.task_id}")
                return
            
            # ===== 步骤3: 落库 =====
            await self._save_data(task, data)
            
            # ===== 步骤4: 推送"数据已更新"事件 =====
            publish_event({
                'type': 'data_updated',
                'symbol': task.symbol,
                'freq': task.freq,
                'data_type': task.data_type_id,
                'status': 'newly_fetched',
                'message': '数据已更新',
                'timestamp': datetime.now().isoformat()
            })
            
            log_event(
                logger=_LOG,
                service="sync_executor",
                level="INFO",
                file=__file__,
                func="_execute_task",
                line=0,
                trace_id=task.task_id,
                event="task.done",
                message="任务执行成功",
                extra={"task_id": task.task_id}
            )
        
        except Exception as e:
            log_event(
                logger=_LOG,
                service="sync_executor",
                level="ERROR",
                file=__file__,
                func="_execute_task",
                line=0,
                trace_id=task.task_id,
                event="task.error",
                message=f"任务执行失败: {e}",
                extra={"task_id": task.task_id, "error": str(e)}
            )
    
    async def _call_gap_check(
        self,
        func_path: str,
        symbol: Optional[str],
        freq: Optional[str],
        data_type_id: str
    ) -> bool:
        """调用缺口判断函数"""
        
        # 特殊处理：always_fetch
        if func_path == "lambda **kwargs: True":
            return True
        
        # 解析函数路径
        module_path, func_name = func_path.rsplit('.', 1)
        
        # 动态导入
        import importlib
        module = importlib.import_module(f"backend.{module_path}")
        func = getattr(module, func_name)
        
        # 调用函数
        return func(
            symbol=symbol,
            freq=freq,
            data_type_id=data_type_id
        )
    
    async def _fetch_data(self, task: PrioritizedTask) -> Optional[Any]:
        """拉取数据（根据数据类型调用对应方法）"""
        
        category = self.definitions.get(task.data_type_id, {}).get('category')
        
        if category == 'kline':
            return await self._fetch_kline(task)
        elif category == 'profile':
            return await self._fetch_profile(task)
        elif category == 'factors':
            return await self._fetch_factors(task)
        elif category == 'symbol_index':
            return await self._fetch_symbol_index(task)
        elif category == 'trade_calendar':
            return await self._fetch_trade_calendar(task)
        else:
            _LOG.error(f"[执行器] 未知数据类别: {category}")
            return None
    
    @limit_async_network_io
    async def _fetch_kline(self, task: PrioritizedTask) -> Optional[Dict[str, Any]]:
        """拉取K线数据（固定使用不复权）"""
        
        start_ymd = settings.sync_init_start_date
        
        # 判断结束时间
        if 'frontend' in task.data_type_id:
            end_ymd = today_ymd()
        else:
            from backend.db.calendar import get_recent_trading_days
            recent = get_recent_trading_days(n=1)
            end_ymd = recent[0] if recent else today_ymd()
        
        # ===== 关键：固定使用不复权数据 =====
        raw_df, source_id = await dispatcher.fetch(
            'stock_bars',
            symbol=task.symbol,
            start_date=f"{start_ymd:08d}",
            end_date=f"{end_ymd:08d}",
            period=self._freq_to_period(task.freq),
            adjust=''  # ← 固定不复权
        )
        
        if raw_df is None or raw_df.empty:
            return None
        
        return {'raw_df': raw_df, 'source': source_id}
    
    @limit_async_network_io
    async def _fetch_profile(self, task: PrioritizedTask) -> Optional[Dict[str, Any]]:
        """拉取档案数据"""
        
        raw_df, source_id = await dispatcher.fetch(
            'stock_profile',
            symbol=task.symbol
        )
        
        if raw_df is None or raw_df.empty:
            return None
        
        return {'raw_df': raw_df, 'source': source_id}
    
    @limit_async_network_io
    async def _fetch_factors(self, task: PrioritizedTask) -> Optional[Dict[str, Any]]:
        """拉取复权因子"""
        
        start_ymd = settings.sync_init_start_date
        
        # 判断结束时间
        if 'frontend' in task.data_type_id:
            end_ymd = today_ymd()
        else:
            from backend.db.calendar import get_recent_trading_days
            recent = get_recent_trading_days(n=1)
            end_ymd = recent[0] if recent else today_ymd()
        
        # 调用integrators获取因子
        result = await integrators.get_daily_bars_with_factors(
            symbol=task.symbol,
            start_date=f"{start_ymd:08d}",
            end_date=f"{end_ymd:08d}"
        )
        
        if result is None:
            return None
        
        return result.get('factors')
    
    @limit_async_network_io
    async def _fetch_symbol_index(self, task: PrioritizedTask) -> Optional[Dict[str, Any]]:
        """拉取标的列表"""
        
        success = await sync_all_symbols()
        return {'success': success}
    
    @limit_async_network_io
    async def _fetch_trade_calendar(self, task: PrioritizedTask) -> Optional[Dict[str, Any]]:
        """拉取交易日历"""
        
        raw_df, source_id = await dispatcher.fetch('trade_calendar')
        
        if raw_df is None or raw_df.empty:
            return None
        
        return {'raw_df': raw_df, 'source': source_id}
    
    async def _save_data(self, task: PrioritizedTask, data: Any):
        """落库（根据数据类别）"""
        
        category = self.definitions.get(task.data_type_id, {}).get('category')
        
        if category == 'kline':
            # K线数据
            from backend.services.normalizer import normalize_bars_df
            
            raw_df = data.get('raw_df')
            source = data.get('source')
            
            # 标准化
            clean_df = normalize_bars_df(raw_df, source)
            
            if clean_df is None or clean_df.empty:
                return
            
            # 补充字段
            clean_df['symbol'] = task.symbol
            clean_df['freq'] = task.freq
            clean_df['source'] = source
            clean_df['fetched_at'] = datetime.now().isoformat()
            
            # 落库（UPSERT）
            await asyncio.to_thread(
                upsert_candles_raw,
                clean_df.to_dict('records')
            )
        
        elif category == 'profile':
            # 档案数据
            from backend.services.normalizer import normalize_stock_profile_df
            
            raw_df = data.get('raw_df')
            
            # 标准化（长表转宽表）
            profile_dict = normalize_stock_profile_df(raw_df)
            
            if not profile_dict:
                return
            
            profile_dict['symbol'] = task.symbol
            profile_dict['updated_at'] = datetime.now().isoformat()
            
            # 落库
            await asyncio.to_thread(
                upsert_symbol_profile,
                [profile_dict]
            )
        
        elif category == 'factors':
            # 复权因子
            if data is None or (isinstance(data, pd.DataFrame) and data.empty):
                return
            
            # 补充symbol列
            if isinstance(data, pd.DataFrame):
                data['symbol'] = task.symbol
                data['updated_at'] = datetime.now().isoformat()
                
                # 落库
                await asyncio.to_thread(
                    upsert_factors,
                    data.to_dict('records')
                )
        
        elif category == 'symbol_index':
            # 标的列表（已在sync_all_symbols内部落库）
            pass
        
        elif category == 'trade_calendar':
            # 交易日历
            from backend.services.normalizer import normalize_trade_calendar_df
            
            raw_df = data.get('raw_df')
            clean_df = normalize_trade_calendar_df(raw_df)
            
            if clean_df is None or clean_df.empty:
                return
            
            # 转为记录格式
            records = [
                {
                    'date': int(row['date']),
                    'market': settings.default_market,
                    'is_trading_day': 1
                }
                for _, row in clean_df.iterrows()
            ]
            
            # 落库
            await asyncio.to_thread(
                upsert_trade_calendar,
                records
            )
    
    def _freq_to_period(self, freq: str) -> str:
        """频率转period参数"""
        if freq == '1d':
            return 'daily'
        elif freq == '1w':
            return 'weekly'
        elif freq == '1M':
            return 'monthly'
        else:
            return 'daily'
    
    @property
    def definitions(self) -> Dict[str, Any]:
        """获取数据类型定义"""
        return DATA_TYPE_DEFINITIONS

# 全局单例
_executor: Optional[UnifiedSyncExecutor] = None

def get_sync_executor() -> UnifiedSyncExecutor:
    """获取执行器单例"""
    global _executor
    if _executor is None:
        _executor = UnifiedSyncExecutor()
    return _executor
