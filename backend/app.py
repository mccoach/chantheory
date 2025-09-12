# backend/app.py  # 应用入口文件
# ==============================
# 说明：FastAPI 应用入口（启动即用 + 初始化后台化）
# - 启动：仅做轻量初始化（SQLite 架构 + 配置监听），立即可服务
# - 后台：启动守护线程执行初始化任务（如自选池近窗同步），不阻塞端口监听
# - 健康：/api/health 返回后台任务状态，前端可据此显示“后台初始化进行中”
# - 本次改动：注册 symbols 路由，提供 /api/symbols/index
# ==============================

from __future__ import annotations  # 启用前置注解（便于类型注解前引用）

# 第三方
from fastapi import FastAPI  # FastAPI 应用类
from fastapi.middleware.cors import CORSMiddleware  # CORS 中间件

# 标准库
from typing import Dict, Any  # 类型注解
from datetime import datetime  # 时间

# 项目内
from backend.settings import settings  # 全局配置
from backend.db.sqlite import ensure_initialized  # DB 初始化（建表等）
from backend.routers.candles import router as candles_router  # 蜡烛路由
from backend.routers.user_config import router as user_config_router  # 用户配置路由
from backend.routers.watchlist import router as watchlist_router  # 自选路由
from backend.routers.storage import router as storage_router  # 存储管理路由
from backend.routers.debug import router as debug_router  # 调试路由
from backend.routers.symbols import router as symbols_router  # 符号索引路由（新增）
from backend.services.config import start_watcher  # 配置文件监听线程
from backend.services.tasks import start_background_tasks, get_task_status  # 后台任务管理

# 创建 FastAPI 应用
app = FastAPI(title="ChanTheory API", version="1.0.0")  # 应用元信息

# CORS 配置（仅本地白名单，合规默认不暴露公网）
app.add_middleware(
    CORSMiddleware,  # 使用 CORS 中间件
    allow_origins=settings.cors_origins,  # 允许的来源（白名单）
    allow_credentials=True,  # 是否允许携带 Cookie
    allow_methods=["*"],  # 放开所有方法
    allow_headers=["*"],  # 放开所有请求头
)

# 启动钩子：轻量初始化 + 启动后台任务（不阻塞）
@app.on_event("startup")  # 注册应用启动事件
def _on_startup() -> None:  # 启动回调
    """应用启动时：快速就绪 + 后台化初始化"""  # 文档字符串
    ensure_initialized()  # 确保数据库表结构存在（幂等，快速）
    start_watcher()  # 启动配置文件监听（原子写 + 镜像，后台线程）
    start_background_tasks()  # 启动一次性初始化后台任务（守护线程）

# 探活接口（最小）
@app.get("/api/ping")  # GET /api/ping
def ping() -> Dict[str, Any]:  # 函数声明
    """最小探活（后端是否可用）"""  # 说明
    return {"ok": True, "msg": "pong"}  # 固定返回

# 健康检查接口（包含后台任务状态）
@app.get("/api/health")  # GET /api/health
def health() -> Dict[str, Any]:  # 函数声明
    """健康状态（包含后台任务状态）"""  # 说明
    return {
        "ok": True,  # 应用可用
        "time": datetime.now().isoformat(),  # 当前时间（ISO）
        "timezone": settings.timezone,  # 时区（Asia/Shanghai）
        "db_path": str(settings.db_path),  # DB 路径
        "background_tasks": get_task_status(),  # 后台任务状态快照
    }

# 挂载路由（业务路由分层：路由薄，服务厚）
app.include_router(candles_router)        # /api/candles
app.include_router(user_config_router)    # /api/user/config
app.include_router(watchlist_router)      # /api/watchlist*
app.include_router(storage_router)        # /api/storage*
app.include_router(debug_router)          # /api/debug*
app.include_router(symbols_router)        # /api/symbols*（新增）

# 本地直接运行（调试）
if __name__ == "__main__":  # 判断是否脚本运行
    import uvicorn  # 导入 uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)  # 启动服务
