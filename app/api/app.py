"""
FastAPI 应用创建
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.postgres import PostgresDatabase
from app.database.nebulagraph import NebulaGraphDatabase
from app.database.qdrant import QdrantDatabase
from app.services.embedding_service import EmbeddingService, create_embedding_service

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# 全局数据库实例
postgres_db: Optional[PostgresDatabase] = None
nebula_db: Optional[NebulaGraphDatabase] = None
qdrant_db: Optional[QdrantDatabase] = None
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> Optional[EmbeddingService]:
    """获取全局 Embedding 服务实例"""
    return _embedding_service


def set_embedding_service(service: EmbeddingService):
    """设置全局 Embedding 服务实例"""
    global _embedding_service
    _embedding_service = service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    应用生命周期管理

    Args:
        app: FastAPI 应用实例

    Yields:
        None
    """
    global postgres_db, nebula_db, qdrant_db, _embedding_service

    # 启动时初始化
    logger.info("正在初始化数据库连接...")

    # PostgreSQL
    if settings.database_url:
        try:
            postgres_db = PostgresDatabase(settings.database_url)
            await postgres_db.connect()
            await postgres_db.init_tables()
            logger.info("PostgreSQL 初始化完成")
        except Exception as e:
            logger.warning(f"PostgreSQL 连接失败：{e}")
            postgres_db = None
    else:
        logger.info("PostgreSQL 未配置，跳过初始化")

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
            nebula_db = None
    else:
        logger.info("NebulaGraph 未配置，跳过初始化")

    # Embedding Service - 使用分 provider 配置
    embedding_config = settings.get_embedding_config(settings.embedding_provider)
    try:
        _embedding_service = create_embedding_service(
            provider=settings.embedding_provider,
            model=embedding_config.get("model", ""),
            api_key=embedding_config.get("api_key", ""),
            base_url=embedding_config.get("base_url", ""),
        )
        logger.info(f"Embedding 服务初始化：{settings.embedding_provider} ({embedding_config.get('model')})")
    except Exception as e:
        logger.warning(f"Embedding 服务初始化失败：{e}")

    # Qdrant - 使用默认维度 384，实际维度由 embedding service 决定
    if settings.qdrant_url:
        qdrant_db = QdrantDatabase(
            url=settings.qdrant_url,
            vector_size=384,  # 默认维度，实际由 embedding service 决定
            embedding_service=_embedding_service,
        )
        try:
            await qdrant_db.connect()
            await qdrant_db.init_collection()
            logger.info("Qdrant 初始化完成")
        except Exception as e:
            logger.warning(f"Qdrant 连接失败：{e}")
            qdrant_db = None
    else:
        logger.info("Qdrant 未配置，跳过初始化")

    # 初始化系统 Prompt 模板（从 MD 文件同步）
    try:
        from app.api.routes.prompts import set_prompt_service
        from app.services.prompt_template_service import PromptTemplateService
        prompt_service = PromptTemplateService(db=postgres_db)

        # 先从数据库加载已有数据
        await prompt_service._ensure_cache()

        # 尝试从 MD 文件同步（覆盖数据库中的旧数据）
        try:
            sync_result = await prompt_service.sync_md_files_to_db()
            logger.info(f"从 MD 文件同步 Prompts: {sync_result}")
        except Exception as sync_error:
            logger.warning(f"MD 文件同步失败，使用数据库中的数据: {sync_error}")

        set_prompt_service(prompt_service)
        logger.info(f"系统 Prompt 模板初始化完成: {len(prompt_service._templates)} 个模板")
    except Exception as e:
        logger.warning(f"系统 Prompt 模板初始化失败：{e}")

    # 初始化系统 Agent 模板
    try:
        from app.api.routes.agent_templates import set_agent_template_service, set_prompt_service as set_agent_prompt_service
        from app.services.agent_template_service import AgentTemplateService
        from app.services.agent_prompt_service import set_agent_prompt_service as set_runtime_agent_prompt_service
        from app.data.system_agent_templates import SYSTEM_AGENT_TEMPLATES
        agent_template_service = AgentTemplateService(db=postgres_db)
        await agent_template_service.initialize_system_templates(SYSTEM_AGENT_TEMPLATES)
        set_agent_template_service(agent_template_service)
        # 共享 prompt_service 给 agent_templates
        set_agent_prompt_service(prompt_service)
        set_runtime_agent_prompt_service(prompt_service, agent_template_service)
        logger.info(f"系统 Agent 模板初始化完成: {len(SYSTEM_AGENT_TEMPLATES)} 个模板")
    except Exception as e:
        logger.warning(f"系统 Agent 模板初始化失败：{e}")

    # 初始化项目级 Agent 配置服务
    try:
        from app.services.agent_config_service import AgentConfigService, set_agent_config_service
        agent_config_service = AgentConfigService(
            db=postgres_db,
            agent_template_service=agent_template_service,
        )
        await agent_config_service._ensure_cache()
        set_agent_config_service(agent_config_service)
        logger.info(f"项目 Agent 配置服务初始化完成: {len(agent_config_service._configs)} 个配置")
    except Exception as e:
        logger.warning(f"项目 Agent 配置服务初始化失败：{e}")

    # 初始化 Skill 服务（从 MD 文件同步）
    try:
        from app.services.skill_service import set_skill_service, SkillService
        skill_service = SkillService(db=postgres_db)

        # 先从数据库加载已有数据
        await skill_service._ensure_cache()

        # 尝试从 MD 文件同步（覆盖数据库中的旧数据）
        try:
            sync_result = await skill_service.sync_md_files_to_db()
            logger.info(f"从 MD 文件同步 Skills: {sync_result}")
        except Exception as sync_error:
            logger.warning(f"MD 文件同步失败，使用数据库中的数据: {sync_error}")

        set_skill_service(skill_service)
        logger.info(f"系统 Skills 初始化完成: {len(skill_service._skills_cache)} 个技能")
    except Exception as e:
        logger.warning(f"系统 Skills 初始化失败：{e}")

    logger.info("应用初始化完成，开始服务...")

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
        description="AI 驱动的小说生成系统 - 上帝模式",
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

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        try:
            request_body = await request.body()
            request_body_text = request_body.decode("utf-8", errors="ignore")
        except Exception:
            request_body_text = "<unavailable>"

        if len(request_body_text) > 2000:
            request_body_text = request_body_text[:2000] + "...<truncated>"

        logger.error(
            "请求校验失败: %s %s detail=%s body=%s",
            request.method,
            request.url.path,
            exc.errors(),
            request_body_text,
        )
        return await request_validation_exception_handler(request, exc)

    # 注册路由
    from app.api.routes import characters, worlds, plots, websocket, config, time, simulation, projects, bootstrap, lore, setting_agent, skills, token_usage, writing_rules, prompts, agent_templates, agent_configs, workflows, interventions, quality_checks, chapter_outlines, villains, memories, volumes, genre_templates, character_depth, golden_three_rules, world_expansion

    app.include_router(characters.router, prefix="/api/characters", tags=["角色管理"])
    app.include_router(worlds.router, prefix="/api/worlds", tags=["世界管理"])
    app.include_router(plots.router, prefix="/api/plots", tags=["剧情管理"])
    app.include_router(lore.router, prefix="/api/lore", tags=["设定管理"])
    app.include_router(websocket.router, prefix="/api/ws", tags=["WebSocket"])
    app.include_router(config.router, prefix="/api/config", tags=["配置管理"])
    app.include_router(time.router, prefix="/api", tags=["时间系统"])
    app.include_router(simulation.router, prefix="/api", tags=["世界模拟"])
    app.include_router(projects.router, prefix="/api/projects", tags=["项目管理"])
    app.include_router(bootstrap.router, prefix="/api/bootstrap", tags=["Bootstrap 流程"])
    app.include_router(setting_agent.router, prefix="/api/setting-agent", tags=["设定 Agent"])
    app.include_router(skills.router, prefix="/api/skills", tags=["Agent Skills"])
    app.include_router(token_usage.router, prefix="/api/token-usage", tags=["Token 统计"])
    app.include_router(writing_rules.router, prefix="/api", tags=["写作规则"])
    app.include_router(prompts.router, prefix="/api", tags=["Prompt 管理"])
    app.include_router(agent_templates.router, prefix="/api", tags=["Agent 模板管理"])
    app.include_router(agent_configs.router, prefix="/api", tags=["Agent 配置管理"])
    app.include_router(workflows.router, prefix="/api/workflows", tags=["工作流管理"])
    app.include_router(interventions.router, prefix="/api/interventions", tags=["干预管理"])
    app.include_router(quality_checks.router, prefix="/api/quality", tags=["质量检测"])
    app.include_router(chapter_outlines.router, prefix="/api/outlines", tags=["章节大纲"])
    app.include_router(villains.router, prefix="/api/villains", tags=["反派管理"])
    app.include_router(memories.router, prefix="/api/memories", tags=["记忆管理"])
    app.include_router(volumes.router, prefix="/api/volumes", tags=["卷规划"])
    app.include_router(genre_templates.router, tags=["题材模板"])
    app.include_router(character_depth.router, tags=["角色深度"])
    app.include_router(golden_three_rules.router, tags=["黄金三章规则"])
    app.include_router(world_expansion.router, tags=["世界观展开"])

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
            "description": "AI 驱动的小说生成系统 - 上帝模式",
        }

    logger.info("FastAPI 应用创建完成")

    return app


# 创建应用实例
app = create_app()