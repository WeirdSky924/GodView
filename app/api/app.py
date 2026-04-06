"""
FastAPI 应用创建
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.postgres import PostgresDatabase
from app.database.nebulagraph import NebulaGraphDatabase
from app.database.qdrant import QdrantDatabase

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# 全局数据库实例
postgres_db: PostgresDatabase = None
nebula_db: NebulaGraphDatabase = None
qdrant_db: QdrantDatabase = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    应用生命周期管理

    Args:
        app: FastAPI 应用实例

    Yields:
        None
    """
    global postgres_db, nebula_db, qdrant_db

    # 启动时初始化
    logger.info("正在初始化数据库连接...")

    # PostgreSQL
    if settings.database_url:
        postgres_db = PostgresDatabase(settings.database_url)
        await postgres_db.connect()
        await postgres_db.init_tables()
        logger.info("PostgreSQL 初始化完成")

    # NebulaGraph
    if settings.nebula_host:
        nebula_db = NebulaGraphDatabase(
            host=settings.nebula_host,
            port=settings.nebula_port,
            user=settings.nebula_user,
            password=settings.nebula_password,
        )
        try:
            await nebula_db.connect()
            await nebula_db.init_schema()
            logger.info("NebulaGraph 初始化完成")
        except Exception as e:
            logger.warning(f"NebulaGraph 连接失败：{e}")

    # Qdrant
    if settings.qdrant_url:
        qdrant_db = QdrantDatabase(url=settings.qdrant_url)
        try:
            await qdrant_db.connect()
            await qdrant_db.init_collection()
            logger.info("Qdrant 初始化完成")
        except Exception as e:
            logger.warning(f"Qdrant 连接失败：{e}")

    yield

    # 关闭时清理
    logger.info("正在关闭数据库连接...")

    if postgres_db:
        await postgres_db.disconnect()
    if nebula_db:
        await nebula_db.disconnect()
    if qdrant_db:
        await qdrant_db.disconnect()

    logger.info("应用已关闭")


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用实例

    Returns:
        FastAPI: 应用实例
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI 驱动的小说生成系统 - 导演模式",
        lifespan=lifespan,
    )

    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from app.api.routes import characters, worlds, plots, websocket

    app.include_router(characters.router, prefix="/api/characters", tags=["角色管理"])
    app.include_router(worlds.router, prefix="/api/worlds", tags=["世界管理"])
    app.include_router(plots.router, prefix="/api/plots", tags=["剧情管理"])
    app.include_router(websocket.router, prefix="/api/ws", tags=["WebSocket"])

    # 健康检查
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": settings.app_version,
        }

    # 根路径
    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "description": "AI 驱动的小说生成系统 - 导演模式",
        }

    logger.info("FastAPI 应用创建完成")

    return app
