# backend/services/data_requirement_parser.py
# ==============================
# 说明：数据需求解析器（前端声明→后端任务）
# 职责：
#   1. 解析前端的数据需求声明
#   2. 解析目标范围（current_symbol/watchlist/all_symbols）
#   3. 识别标的类型（数据库优先，前缀降级）
#   4. 生成标准化任务对象
# 
# V2.0 改动：
#   - _create_task 中新增类型识别逻辑
#   - 新增 _get_symbol_type_sync 辅助方法
# ==============================

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.settings import settings, DATA_TYPE_DEFINITIONS, REFRESH_STRATEGIES
from backend.db.watchlist import select_user_watchlist
from backend.db.symbols import select_symbol_index
from backend.services.priority_queue import PrioritizedTask
from backend.utils.logger import get_logger

_LOG = get_logger("requirement_parser")

class DataRequirementParser:
    """数据需求解析器"""
    
    def __init__(self):
        self.definitions = DATA_TYPE_DEFINITIONS
        self.strategies = REFRESH_STRATEGIES
    
    def parse_requirements(self, requirements: List[Dict[str, Any]]) -> List[PrioritizedTask]:
        """
        解析前端的数据需求声明，生成任务列表
        
        Args:
            requirements: 前端发送的需求列表
            
        Returns:
            List[PrioritizedTask]: 标准化任务列表
        """
        tasks = []
        
        for req in requirements:
            scope = req.get('scope')
            includes = req.get('includes', [])
            force_fetch = req.get('force_fetch', False)
            
            # 解析目标范围
            targets = self._resolve_targets(scope, req)
            
            # 为每个目标 × 每个数据类型生成任务
            for target in targets:
                for item in includes:
                    task = self._create_task(item, target, force_fetch)
                    if task:
                        tasks.append(task)
        
        _LOG.info(f"[需求解析] 共生成 {len(tasks)} 个任务")
        return tasks
    
    def _resolve_targets(self, scope: str, req: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析目标范围"""
        
        if scope == 'symbol':
            # 单个标的
            symbol = req.get('symbol')
            if not symbol:
                _LOG.warning("[需求解析] scope=symbol 但未提供symbol参数")
                return []
            
            return [{'symbol': symbol}]
        
        elif scope == 'watchlist':
            # 自选池
            symbols = req.get('symbols')
            
            if symbols is None:
                # 未提供列表，从数据库查询
                watchlist_records = select_user_watchlist()
                symbols = [r['symbol'] for r in watchlist_records]
            
            return [{'symbol': s} for s in symbols]
        
        elif scope == 'all_symbols':
            # 全量标的
            all_records = select_symbol_index()
            
            # 过滤：只处理 A股 和 ETF（排除LOF/北交所）
            filtered = [
                r for r in all_records
                if r.get('type') in settings.sync_data_categories
            ]
            
            return [{'symbol': r['symbol']} for r in filtered]
        
        elif scope == 'global':
            # 全局数据（标的列表/交易日历）
            return [{}]  # 空字典表示无具体标的
        
        else:
            _LOG.warning(f"[需求解析] 未知scope: {scope}")
            return []
    
    # ===== V2.0 新增：标的类型识别（同步版本）=====
    def _get_symbol_type_sync(self, symbol: str) -> str:
        """
        获取标的类型（同步方法，供Parser调用）
        
        识别策略：
          1. 优先查询 symbol_index 表的 type 字段（最可靠）
          2. 查询失败则调用 infer_symbol_type 前缀推断（降级）
          3. 推断失败则默认返回 'A'（兜底）
        
        Args:
            symbol: 标的代码
        
        Returns:
            str: 标的类型（'A', 'ETF', 'LOF', 'INDEX' 等）
        
        Examples:
            >>> parser._get_symbol_type_sync('600519')
            'A'
            >>> parser._get_symbol_type_sync('510300')
            'ETF'
        """
        if not symbol:
            return 'A'
        
        symbol = str(symbol).strip()
        
        # 策略1：优先查表（可靠性 99%）
        try:
            records = select_symbol_index(symbol=symbol)
            
            if records and len(records) > 0:
                symbol_type = records[0].get('type')
                
                if symbol_type:
                    _LOG.debug(
                        f"[类型识别] {symbol} → {symbol_type} (来源=数据库)"
                    )
                    return str(symbol_type).strip().upper()
        
        except Exception as e:
            _LOG.warning(
                f"[类型识别] 查表失败: {symbol}, error={e}"
            )
        
        # 策略2：降级推断（可靠性 80%）
        try:
            from backend.utils.common import infer_symbol_type
            
            symbol_type = infer_symbol_type(symbol)
            
            _LOG.debug(
                f"[类型识别] {symbol} → {symbol_type} (来源=前缀推断)"
            )
            
            return str(symbol_type or 'A').strip().upper()
        
        except Exception as e:
            _LOG.warning(
                f"[类型识别] 前缀推断失败: {symbol}, error={e}"
            )
        
        # 策略3：兜底默认
        _LOG.debug(f"[类型识别] {symbol} → A (来源=默认)")
        return 'A'
    
    def _create_task(
        self, 
        item: Dict[str, Any], 
        target: Dict[str, Any],
        force_fetch: bool = False
    ) -> Optional[PrioritizedTask]:
        """
        创建单个任务（V2.0 - 新增类型识别）
        
        改动：
          - 对于有symbol的任务，调用 _get_symbol_type_sync 识别类型
          - 将识别结果填充到 task.symbol_type 字段
        """
        
        data_type = item.get('type')
        
        if not data_type:
            _LOG.warning("[需求解析] 数据项缺少type字段")
            return None
        
        # 获取数据类型定义
        definition = self.definitions.get(data_type)
        if not definition:
            _LOG.warning(f"[需求解析] 未知数据类型: {data_type}")
            return None
        
        # 获取刷新策略
        strategy = self.strategies.get(data_type, {})
        
        # 获取优先级（优先用前端指定，否则用配置默认）
        priority = item.get('priority') or definition.get('priority', 100)
        
        # 提取标的代码
        symbol = target.get('symbol') or item.get('symbol')
        
        # ===== V2.0 新增：识别标的类型 =====
        symbol_type = None
        
        if symbol:
            symbol_type = self._get_symbol_type_sync(symbol)
            
            _LOG.debug(
                f"[需求解析] 任务标的类型: {symbol} → {symbol_type}"
            )
        
        # 创建任务
        task = PrioritizedTask(
            priority=priority,
            timestamp=datetime.now().timestamp(),
            data_type_id=data_type,
            symbol=symbol,
            freq=item.get('freq'),
            strategy=strategy,
            task_id=self._generate_task_id(data_type, target, item),
            force_fetch=force_fetch,
            symbol_type=symbol_type  # ← V2.0 新增字段
        )
        
        return task
    
    def _generate_task_id(self, data_type: str, target: dict, item: dict) -> str:
        """生成任务唯一ID"""
        parts = [data_type]
        
        if target.get('symbol'):
            parts.append(target['symbol'])
        
        if item.get('freq'):
            parts.append(item['freq'])
        
        return '_'.join(parts)

# 全局单例
_parser: Optional[DataRequirementParser] = None

def get_requirement_parser() -> DataRequirementParser:
    """获取解析器单例"""
    global _parser
    if _parser is None:
        _parser = DataRequirementParser()
    return _parser