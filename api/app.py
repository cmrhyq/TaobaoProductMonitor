"""
FastAPI application instance with lifespan management.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from config.settings import get_settings
from config.logging_config import setup_logging
from data.database import init_db

settings = get_settings()
setup_logging(log_level=settings.app.log_level, debug=settings.app.debug)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info("Initializing database")
    init_db()
    logger.info("Application started", app_name=settings.app.app_name)
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title="TaobaoProductMonitor API",
    version="2.0.0",
    description="淘宝商品价格监控 REST API",
    lifespan=lifespan,
)

from api.routes import products, monitor, health  # noqa: E402

app.include_router(health.router, tags=["Health"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(monitor.router, prefix="/monitor", tags=["Monitor"])
