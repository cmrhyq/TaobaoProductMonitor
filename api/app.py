"""
FastAPI application instance with lifespan management.

Web API 是本项目对外的**唯一业务入口**：
- 商品的增删查、价格历史与快照查询都在这里；
- 扫码登录由 `POST /session/login` 提供（会拉起有头浏览器）；
- 定时监控由 lifespan 启动的内嵌调度器驱动，随服务启停。

⚠️ 必须以**单 worker** 运行（uvicorn 默认即单 worker）：
SQLite 单文件、进程内轮次锁、进程内调度器、有头浏览器四者都要求单进程，
多 worker 会让同一份调度被重复执行。
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from config.logging_config import setup_logging
from config.settings import get_settings
from data.database import init_db
from task.scheduler import start_scheduler, stop_scheduler

settings = get_settings()
setup_logging(log_level=settings.app.log_level, debug=settings.app.debug)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info("Initializing database")
    init_db()

    scheduler = start_scheduler(settings)
    logger.info(
        "Application started",
        app_name=settings.app.app_name,
        schedule_enabled=settings.monitor.schedule_enabled,
        interval_minutes=settings.monitor.interval_minutes,
        next_run_at=scheduler.next_run_at if scheduler else None,
    )
    yield

    stop_scheduler()
    logger.info("Application shutting down")


app = FastAPI(
    title="TaobaoProductMonitor API",
    version="2.0.0",
    description=(
        "淘宝商品价格监控 REST API。\n\n"
        "- 抓取由 tbmon 承担（PC 详情页 SSR），已实网验证；\n"
        "- 价格语义：`price` = 实付价（优惠后），`original_price` = 优惠前价。"
    ),
    lifespan=lifespan,
)

from api.routes import health, monitor, products, session  # noqa: E402

app.include_router(health.router, tags=["Health"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(monitor.router, prefix="/monitor", tags=["Monitor"])
app.include_router(session.router, prefix="/session", tags=["Session"])
