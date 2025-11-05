# backend/services/data_requirement_parser.py
# ==============================
# 说明：数据需求解析器（前端声明→后端任务）
# 职责：
#   1. 解析前端的数据需求声明
#   2. 解析目标范围（current_symbol/watchlist/all_symbols）
#   3. 生成标准化任务对象
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
            scope = req.get('scope')  # 'symbol' / 'watchlist' / 'global'
            includes = req.get('includes', [])
            
            # 解析目标范围
            targets = self._resolve_targets(scope, req)
            
            # 为每个目标 × 每个数据类型生成任务
            for target in targets:
                for item in includes:
                    task = self._create_task(item, target)
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
    
    def _create_task(self, item: Dict[str, Any], target: Dict[str, Any]) -> Optional[PrioritizedTask]:
        """创建单个任务"""
        
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
        
        # 创建任务
        task = PrioritizedTask(
            priority=priority,
            timestamp=datetime.now().timestamp(),
            data_type_id=data_type,
            symbol=target.get('symbol') or item.get('symbol'),
            freq=item.get('freq'),
            strategy=strategy,
            task_id=self._generate_task_id(data_type, target, item)
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
