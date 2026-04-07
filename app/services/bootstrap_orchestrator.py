"""
引导编排服务 (Bootstrap Orchestrator)
v4 核心需求：驱动项目初始化流程，管理 bootstrap 各阶段状态，
            写入 world/characters/agents/snapshot
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.bootstrap import BootstrapSession, BootstrapStage
from app.models.project import ProjectStatus
from app.models.world import World, WorldRule
from app.models.character import Character
from app.models.seed import ProjectSeed, SeedType

logger = logging.getLogger(__name__)


class BootstrapOrchestrator:
    """引导编排器 - 负责协调整个项目初始化流程"""

    def __init__(self):
        self._sessions: Dict[str, BootstrapSession] = {}

    async def create_session(
        self,
        project_id: str,
        initial_message: Optional[str] = None,
    ) -> BootstrapSession:
        """
        创建 Bootstrap 会话

        Args:
            project_id: 项目 ID
            initial_message: 可选的初始消息

        Returns:
            BootstrapSession: Bootstrap 会话
        """
        # 生成会话 ID
        session_id = f"bootstrap_{uuid.uuid4().hex[:12]}"

        # 创建会话
        session = BootstrapSession(
            id=session_id,
            project_id=project_id,
            status=BootstrapStage.DRAFT,
            current_stage=BootstrapStage.DRAFT,
            progress=0.0,
        )

        self._sessions[session_id] = session

        # 如果有初始消息，进入收集设定阶段
        if initial_message:
            session.current_stage = BootstrapStage.COLLECTING_SETTING
            session.status = BootstrapStage.COLLECTING_SETTING
            session.progress = 0.1

        return session

    async def get_session(self, session_id: str) -> Optional[BootstrapSession]:
        """获取 Bootstrap 会话"""
        return self._sessions.get(session_id)

    async def update_session_stage(
        self,
        session_id: str,
        stage: BootstrapStage,
    ) -> BootstrapSession:
        """
        更新会话阶段

        Args:
            session_id: 会话 ID
            stage: 新阶段

        Returns:
            BootstrapSession: 更新后的会话
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.current_stage = stage
        session.status = stage
        session.updated_at = datetime.now()

        # 更新进度
        session.progress = self._calculate_progress(stage)

        return session

    def _calculate_progress(self, stage: BootstrapStage) -> float:
        """根据阶段计算进度"""
        progress_map = {
            BootstrapStage.DRAFT: 0.0,
            BootstrapStage.COLLECTING_SETTING: 0.1,
            BootstrapStage.OUTLINE_INGESTED: 0.2,
            BootstrapStage.SEED_EXTRACTED: 0.4,
            BootstrapStage.AWAITING_CONFIRMATION: 0.5,
            BootstrapStage.BOOTSTRAPPING_WORLD: 0.6,
            BootstrapStage.BOOTSTRAPPING_AGENTS: 0.7,
            BootstrapStage.BOOTSTRAPPING_CHARACTERS: 0.8,
            BootstrapStage.CREATING_SNAPSHOT: 0.9,
            BootstrapStage.COMPLETED: 1.0,
            BootstrapStage.FAILED: 0.0,
            BootstrapStage.NEEDS_REVISION: 0.3,
        }
        return progress_map.get(stage, 0.0)

    async def confirm_seed(
        self,
        session_id: str,
        seed_data: Dict[str, Any],
    ) -> BootstrapSession:
        """
        确认 Seed

        Args:
            session_id: 会话 ID
            seed_data: 用户确认的 seed 数据

        Returns:
            BootstrapSession: 更新后的会话
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 保存确认的 seed
        session.confirmed_seed = seed_data
        session.extracted_seed = seed_data

        # 进入等待确认状态
        session.current_stage = BootstrapStage.AWAITING_CONFIRMATION
        session.status = BootstrapStage.AWAITING_CONFIRMATION
        session.progress = 0.5
        session.updated_at = datetime.now()

        return session

    async def revise_seed(
        self,
        session_id: str,
        feedback: str,
    ) -> BootstrapSession:
        """
        修订 Seed

        Args:
            session_id: 会话 ID
            feedback: 用户修订反馈

        Returns:
            BootstrapSession: 更新后的会话
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 标记需要修订
        session.current_stage = BootstrapStage.NEEDS_REVISION
        session.status = BootstrapStage.NEEDS_REVISION
        session.progress = 0.3
        session.error_message = feedback
        session.retry_count += 1
        session.updated_at = datetime.now()

        # 清空已提取的 seed，要求重新生成
        session.extracted_seed = {}

        return session

    async def finalize_setting(
        self,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        结束设定阶段并强制提取 Seed

        不依赖对话轮数阈值，直接从当前对话历史中提取结构化 seed

        Args:
            session_id: 会话 ID

        Returns:
            Dict: 包含 seed_data 和 session 的结果
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 检查是否有对话历史
        if not session.setting_agent_history:
            raise ValueError("没有对话历史，无法提取 seed")

        # 强制提取 seed
        from app.services.setting_agent import get_setting_agent
        agent = get_setting_agent()

        # 从历史提取 seed
        seed_data = await agent.extract_seed_from_history(session)

        if not seed_data:
            # 如果提取失败，尝试生成一个基础 seed
            seed_data = await self._generate_minimal_seed(session)

        # 更新会话状态
        session.extracted_seed = seed_data
        session.current_stage = BootstrapStage.SEED_EXTRACTED
        session.status = BootstrapStage.SEED_EXTRACTED
        session.progress = 0.4
        session.updated_at = datetime.now()

        return {
            "seed_data": seed_data,
            "session": session.model_dump(mode="json"),
        }

    async def _generate_minimal_seed(self, session: BootstrapSession) -> Dict[str, Any]:
        """
        生成最小化 Seed

        当无法从对话中提取完整 seed 时，生成一个基础的 seed 结构
        """
        return {
            "world_setting": {
                "name": "新世界",
                "description": "待完善的世界设定",
                "world_type": "fantasy",
                "tone": "serious",
            },
            "world_rules": [],
            "power_system": "",
            "main_characters": [],
            "supporting_characters": [],
            "regions": [],
            "plot_hooks": [],
            "narrative_tone": "第三人称叙事",
            "seed_type": "minimal",
        }

    async def run_bootstrap(self, session_id: str) -> Dict[str, Any]:
        """
        执行 Bootstrap

        Args:
            session_id: 会话 ID

        Returns:
            Dict: Bootstrap 执行结果
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 检查是否已确认 seed
        if not session.confirmed_seed:
            raise ValueError("Seed 尚未确认，请先确认 seed 后再执行 Bootstrap")

        try:
            # 阶段 1: 创建世界
            await self._bootstrap_world(session)
            session.current_stage = BootstrapStage.BOOTSTRAPPING_WORLD
            session.progress = 0.6
            session.updated_at = datetime.now()

            # 阶段 2: 初始化 Agents
            await self._bootstrap_agents(session)
            session.current_stage = BootstrapStage.BOOTSTRAPPING_AGENTS
            session.progress = 0.7
            session.updated_at = datetime.now()

            # 阶段 3: 创建角色
            await self._bootstrap_characters(session)
            session.current_stage = BootstrapStage.BOOTSTRAPPING_CHARACTERS
            session.progress = 0.8
            session.updated_at = datetime.now()

            # 阶段 4: 创建初始快照
            await self._create_initial_snapshot(session)
            session.current_stage = BootstrapStage.CREATING_SNAPSHOT
            session.progress = 0.9
            session.updated_at = datetime.now()

            # 完成
            session.current_stage = BootstrapStage.COMPLETED
            session.status = BootstrapStage.COMPLETED
            session.progress = 1.0
            session.completed_at = datetime.now()
            session.updated_at = datetime.now()

            # 更新项目状态
            await self._update_project_status(session.project_id, ProjectStatus.ACTIVE)

            return {
                "success": True,
                "project_id": session.project_id,
                "world_id": session.confirmed_seed.get("world_id"),
                "character_count": len(session.confirmed_seed.get("main_characters", [])),
                "message": "Bootstrap 执行完成",
            }

        except Exception as e:
            logger.error(f"Bootstrap 执行失败：{e}")
            session.current_stage = BootstrapStage.FAILED
            session.status = BootstrapStage.FAILED
            session.error_message = str(e)
            session.progress = 0.0
            raise

    async def _bootstrap_world(self, session: BootstrapSession):
        """创建世界"""
        seed = session.confirmed_seed
        project_id = session.project_id

        # 获取 world 数据
        world_setting = seed.get("world_setting", {})
        world_id = f"world_{uuid.uuid4().hex[:12]}"

        # 创建 World 对象
        world = World(
            id=world_id,
            name=world_setting.get("name", "新世界"),
            description=world_setting.get("description"),
            world_type=world_setting.get("world_type", "fantasy"),
            tone=world_setting.get("tone", "serious"),
            power_system=seed.get("power_system"),
            technology_level=seed.get("technology_level"),
            history=seed.get("history"),
            geography=seed.get("geography"),
            factions=seed.get("factions", []),
            project_id=project_id,  # 关联项目 ID
        )

        # 添加世界规则
        world_rules = seed.get("world_rules", [])
        for rule_data in world_rules:
            rule = WorldRule(
                id=f"rule_{uuid.uuid4().hex[:8]}",
                name=rule_data.get("name", ""),
                description=rule_data.get("description", ""),
                category=rule_data.get("category", "general"),
                priority=rule_data.get("priority", 0),
                is_absolute=rule_data.get("is_absolute", False),
            )
            world.rules.append(rule)

        # 保存到数据库
        from app.api.app import postgres_db
        if postgres_db:
            await postgres_db.save_world(world.model_dump(mode="json"))

            # 更新项目的 world_id
            await postgres_db.update_project(project_id, {"world_id": world_id})

        # 更新 seed 中的 world_id
        seed["world_id"] = world_id

        # 创建区域
        await self._bootstrap_regions(session, world_id)

    async def _bootstrap_regions(self, session: BootstrapSession, world_id: str):
        """创建区域"""
        seed = session.confirmed_seed
        regions_data = seed.get("regions", [])

        from app.models.world import Region, RegionType

        for region_data in regions_data:
            region = Region(
                id=f"region_{uuid.uuid4().hex[:12]}",
                name=region_data.get("name", ""),
                world_id=world_id,
                region_type=RegionType(region_data.get("region_type", "custom")),
                description=region_data.get("description"),
            )

            from app.api.app import postgres_db
            if postgres_db:
                await postgres_db.save_region(region.model_dump(mode="json"))

    async def _bootstrap_agents(self, session: BootstrapSession):
        """初始化 Agents"""
        # TODO: 实现 Agent 注册
        # 需要在数据库中创建 agent registry 记录
        pass

    async def _bootstrap_characters(self, session: BootstrapSession):
        """创建角色"""
        seed = session.confirmed_seed
        world_id = seed.get("world_id")
        project_id = session.project_id

        if not world_id:
            raise ValueError("World 尚未创建")

        # 获取角色数据
        main_characters = seed.get("main_characters", [])
        supporting_characters = seed.get("supporting_characters", [])
        all_characters = main_characters + supporting_characters

        from app.models.character import Character, CharacterStatus

        created_character_ids = []

        for char_data in all_characters:
            character = Character(
                id=f"char_{uuid.uuid4().hex[:12]}",
                name=char_data.get("name", ""),
                description=char_data.get("description"),
                role=char_data.get("role", "supporting"),
                status=CharacterStatus.ACTIVE,
                appearance=char_data.get("appearance"),
                background_story=char_data.get("background_story"),
                speech_pattern=char_data.get("speech_pattern"),
                goals=char_data.get("goals", []),
                current_location=char_data.get("current_location"),
                world_id=world_id,  # 关联世界 ID
                project_id=project_id,  # 关联项目 ID
            )

            from app.api.app import postgres_db
            if postgres_db:
                await postgres_db.save_character(character.model_dump(mode="json"))
                created_character_ids.append(character.id)

        # 更新 seed 中的角色 ID 列表
        seed["character_ids"] = created_character_ids

    async def _create_initial_snapshot(self, session: BootstrapSession):
        """创建初始快照"""
        seed = session.confirmed_seed
        world_id = seed.get("world_id")

        if not world_id:
            raise ValueError("World 尚未创建")

        snapshot_data = {
            "id": f"snapshot_{uuid.uuid4().hex[:12]}",
            "world_id": world_id,
            "name": "Bootstrap 初始快照",
            "description": "项目初始化时的世界状态快照",
            "snapshot_type": "initial",
            "world_state": {},
            "created_at": datetime.now().isoformat(),
        }

        from app.api.app import postgres_db
        if postgres_db:
            await postgres_db.save_snapshot(snapshot_data)

    async def _update_project_status(self, project_id: str, status: ProjectStatus):
        """更新项目状态"""
        from app.api.app import postgres_db
        if postgres_db:
            await postgres_db.update_project(project_id, {"status": status.value})


# 全局单例
_orchestrator: Optional[BootstrapOrchestrator] = None


def get_bootstrap_orchestrator() -> BootstrapOrchestrator:
    """获取 Bootstrap 编排器单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = BootstrapOrchestrator()
    return _orchestrator


def set_bootstrap_orchestrator(orchestrator: BootstrapOrchestrator):
    """设置 Bootstrap 编排器实例（用于测试）"""
    global _orchestrator
    _orchestrator = orchestrator