"""
引导编排服务 (Bootstrap Orchestrator)
v4 核心需求：驱动项目初始化流程，管理 bootstrap 各阶段状态，
            写入 world/characters/agents/snapshot
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.bootstrap import BootstrapSession, BootstrapStage
from app.models.project import ProjectStatus
from app.models.world import World, WorldRule
from app.models.character import Character
from app.models.seed import ProjectSeed, SeedType
from app.services.operation_lifecycle_service import OperationLifecycleService

logger = logging.getLogger(__name__)


class BootstrapOrchestrator:
    """引导编排器 - 负责协调整个项目初始化流程"""

    def __init__(self):
        self._sessions: Dict[str, BootstrapSession] = {}
        self._project_session_locks: Dict[str, asyncio.Lock] = {}
        self._session_run_locks: Dict[str, asyncio.Lock] = {}

    def _session_to_db_row(self, session: BootstrapSession) -> Dict[str, Any]:
        """序列化 Bootstrap session 供 Postgres 持久化。"""
        return {
            "id": session.id,
            "project_id": session.project_id,
            "status": session.status.value if hasattr(session.status, "value") else str(session.status),
            "current_stage": session.current_stage.value if hasattr(session.current_stage, "value") else str(session.current_stage),
            "progress": session.progress,
            "setting_agent_history": session.setting_agent_history,
            "extracted_seed": session.extracted_seed,
            "confirmed_seed": session.confirmed_seed,
            "error_message": session.error_message,
            "retry_count": session.retry_count,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "completed_at": session.completed_at,
        }

    def _session_from_db_row(self, row: Dict[str, Any]) -> BootstrapSession:
        """从 Postgres 行恢复 Bootstrap session。"""
        return BootstrapSession(
            id=row["id"],
            project_id=str(row["project_id"]),
            status=BootstrapStage(row.get("status") or BootstrapStage.DRAFT.value),
            current_stage=BootstrapStage(row.get("current_stage") or BootstrapStage.DRAFT.value),
            progress=float(row.get("progress") or 0),
            setting_agent_history=row.get("setting_agent_history") or [],
            extracted_seed=row.get("extracted_seed") or {},
            confirmed_seed=row.get("confirmed_seed") or {},
            error_message=row.get("error_message"),
            retry_count=int(row.get("retry_count") or 0),
            created_at=row.get("created_at") or datetime.now(),
            updated_at=row.get("updated_at") or datetime.now(),
            completed_at=row.get("completed_at"),
        )

    async def _persist_session(self, session: BootstrapSession) -> None:
        """持久化 Bootstrap session；失败不阻断内存流程。"""
        try:
            from app.api.app import postgres_db
            if postgres_db:
                await postgres_db.save_bootstrap_session(self._session_to_db_row(session))
        except Exception as e:
            logger.warning(f"Persist bootstrap session failed: {session.id}, error={e}")

    async def _load_session_from_db(self, session_id: str) -> Optional[BootstrapSession]:
        try:
            from app.api.app import postgres_db
            if not postgres_db:
                return None
            row = await postgres_db.get_bootstrap_session(session_id)
            if not row:
                return None
            session = self._session_from_db_row(row)
            self._sessions[session.id] = session
            return session
        except Exception as e:
            logger.warning(f"Load bootstrap session failed: {session_id}, error={e}")
            return None

    async def _get_active_project_session_from_db(self, project_id: str) -> Optional[BootstrapSession]:
        try:
            from app.api.app import postgres_db
            if not postgres_db:
                return None
            row = await postgres_db.get_active_bootstrap_session(project_id)
            if not row:
                return None
            session = self._session_from_db_row(row)
            self._sessions[session.id] = session
            return session
        except Exception as e:
            logger.warning(f"Load active bootstrap session failed: {project_id}, error={e}")
            return None

    def _get_active_project_session(self, project_id: str) -> Optional[BootstrapSession]:
        """获取同项目未结束的 Bootstrap 会话，避免重复初始化。"""
        terminal = {BootstrapStage.COMPLETED, BootstrapStage.FAILED}
        for session in self._sessions.values():
            if session.project_id == project_id and session.status not in terminal:
                return session
        return None

    def _get_project_session_lock(self, project_id: str) -> asyncio.Lock:
        """获取项目级 session 创建锁，避免并发 start 竞态。"""
        lock = self._project_session_locks.get(project_id)
        if lock is None:
            lock = asyncio.Lock()
            self._project_session_locks[project_id] = lock
        return lock

    def _get_session_run_lock(self, session_id: str) -> asyncio.Lock:
        """获取 session 级 bootstrap 执行锁，避免并发 run 重复落库。"""
        lock = self._session_run_locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._session_run_locks[session_id] = lock
        return lock

    async def create_session(
        self,
        project_id: str,
        initial_message: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> BootstrapSession:
        """
        创建 Bootstrap 会话

        Args:
            project_id: 项目 ID
            initial_message: 可选的初始消息

        Returns:
            BootstrapSession: Bootstrap 会话
        """
        async with self._get_project_session_lock(project_id):
            existing_session = self._get_active_project_session(project_id)
            if not existing_session:
                existing_session = await self._get_active_project_session_from_db(project_id)
            if existing_session:
                logger.info(f"Reusing active bootstrap session: {existing_session.id}, project_id={project_id}")
                return existing_session

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
            logger.info(f"Created bootstrap session: {session_id}, total sessions: {len(self._sessions)}")

            # 如果有初始消息，进入收集设定阶段
            if initial_message:
                session.current_stage = BootstrapStage.COLLECTING_SETTING
                session.status = BootstrapStage.COLLECTING_SETTING
                session.progress = 0.1

            await self._persist_session(session)
            return session

    async def get_session(self, session_id: str) -> Optional[BootstrapSession]:
        """获取 Bootstrap 会话"""
        session = self._sessions.get(session_id)
        if not session:
            session = await self._load_session_from_db(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found. Available: {list(self._sessions.keys())}")
        return session

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
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.current_stage = stage
        session.status = stage
        session.updated_at = datetime.now()

        await self._persist_session(session)
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
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Debug: 检查 seed_data 类型
        logger.info(f"confirm_seed: seed_data type = {type(seed_data)}, value = {seed_data}")

        # 确保 seed_data 是字典
        if isinstance(seed_data, str):
            logger.error(f"seed_data is a string: {seed_data[:100]}...")
            import json
            try:
                seed_data = json.loads(seed_data)
            except json.JSONDecodeError:
                raise ValueError("seed_data 是字符串但无法解析为 JSON")

        # 保存确认的 seed
        session.confirmed_seed = seed_data
        session.extracted_seed = seed_data

        # 进入等待确认状态
        session.current_stage = BootstrapStage.AWAITING_CONFIRMATION
        session.status = BootstrapStage.AWAITING_CONFIRMATION
        session.progress = 0.5
        await self._persist_session(session)
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
        session = await self.get_session(session_id)
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

        await self._persist_session(session)
        return session

    async def finalize_setting(
        self,
        session_id: str,
        assistant_session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        结束设定阶段并强制提取 Seed

        不依赖对话轮数阈值，直接从当前对话历史中提取结构化 seed

        Args:
            session_id: 会话 ID

        Returns:
            Dict: 包含 seed_data 和 session 的结果
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 检查是否有对话历史
        if not session.setting_agent_history:
            raise ValueError("没有对话历史，无法提取 seed")

        # 强制提取 seed
        from app.services.setting_agent import get_setting_agent
        agent = get_setting_agent()

        context_packet = await agent._build_bootstrap_context_packet(
            session=session,
            task_type="finalize_seed",
            assistant_session_id=assistant_session_id,
            request_id=request_id,
            user_message="结束设定阶段并提取结构化项目 seed",
        )

        # 从有界会话窗口、摘要和项目快照提取 seed
        seed_data = await agent.extract_seed_from_history(
            session,
            context_packet=context_packet,
            assistant_session_id=assistant_session_id,
            request_id=request_id,
        )

        if not seed_data:
            # 如果提取失败，尝试生成一个基础 seed
            seed_data = await self._generate_minimal_seed(session)

        # 更新会话状态
        session.extracted_seed = seed_data
        session.current_stage = BootstrapStage.SEED_EXTRACTED
        session.status = BootstrapStage.SEED_EXTRACTED
        session.progress = 0.4
        session.updated_at = datetime.now()

        await self._persist_session(session)
        return {
            "seed_data": seed_data,
            "session": session.model_dump(mode="json"),
            "assistant_session_id": context_packet.get("session_id") if context_packet else assistant_session_id,
            "context_packet": agent._context_packet_metadata(context_packet),
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

    def _build_completed_result(self, session: BootstrapSession) -> Dict[str, Any]:
        """基于 session 当前 seed 构造幂等完成响应。"""
        seed = session.confirmed_seed or {}
        return {
            "success": True,
            "project_id": session.project_id,
            "world_id": seed.get("world_id"),
            "character_count": len(seed.get("character_ids") or seed.get("main_characters", [])),
            "message": "Bootstrap 执行完成",
        }

    async def run_bootstrap(self, session_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """串行化同一 session 的 Bootstrap 执行，避免并发 run 重复落库。"""
        async with self._get_session_run_lock(session_id):
            return await self._run_bootstrap_locked(session_id, request_id=request_id)

    async def _run_bootstrap_locked(self, session_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        执行 Bootstrap

        Args:
            session_id: 会话 ID

        Returns:
            Dict: Bootstrap 执行结果
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.status == BootstrapStage.COMPLETED:
            return self._build_completed_result(session)

        active_stages = {
            BootstrapStage.BOOTSTRAPPING_WORLD,
            BootstrapStage.BOOTSTRAPPING_AGENTS,
            BootstrapStage.BOOTSTRAPPING_CHARACTERS,
            BootstrapStage.CREATING_SNAPSHOT,
        }
        if session.status in active_stages or session.current_stage in active_stages:
            return {
                "success": True,
                "project_id": session.project_id,
                "world_id": session.confirmed_seed.get("world_id") if isinstance(session.confirmed_seed, dict) else None,
                "character_count": len(session.confirmed_seed.get("character_ids", [])) if isinstance(session.confirmed_seed, dict) else 0,
                "message": "Bootstrap 正在执行中",
                "status": session.status.value,
            }

        # Debug: 检查 confirmed_seed
        logger.info(f"run_bootstrap: confirmed_seed type = {type(session.confirmed_seed)}")

        # 检查是否已确认 seed
        if not session.confirmed_seed:
            raise ValueError("Seed 尚未确认，请先确认 seed 后再执行 Bootstrap")

        # 确保 confirmed_seed 是字典
        if isinstance(session.confirmed_seed, str):
            logger.error(f"confirmed_seed is a string: {session.confirmed_seed[:100]}...")
            import json
            try:
                session.confirmed_seed = json.loads(session.confirmed_seed)
            except json.JSONDecodeError:
                raise ValueError("confirmed_seed 是字符串但无法解析为 JSON")

        operation = None
        from app.api.app import postgres_db
        if postgres_db:
            lifecycle = OperationLifecycleService(db=postgres_db)
            begin = await lifecycle.begin_or_replay(
                operation_type="bootstrap_run",
                project_id=session.project_id,
                resource_type="bootstrap_session",
                resource_id=session.id,
                request_payload={
                    "session_id": session.id,
                    "project_id": session.project_id,
                    "confirmed_seed": session.confirmed_seed,
                },
                request_id=request_id,
            )
            if begin.replayed:
                return begin.operation.get("response_payload") or self._build_completed_result(session)
            operation = await lifecycle.mark_running(begin.operation)

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
            await self._persist_session(session)

            # 阶段 3: 创建角色
            await self._bootstrap_characters(session)
            session.current_stage = BootstrapStage.BOOTSTRAPPING_CHARACTERS
            session.progress = 0.8
            session.updated_at = datetime.now()
            await self._persist_session(session)

            # 阶段 4: 创建初始快照
            await self._create_initial_snapshot(session)
            session.current_stage = BootstrapStage.CREATING_SNAPSHOT
            session.progress = 0.9
            session.updated_at = datetime.now()
            await self._persist_session(session)

            # 完成
            session.current_stage = BootstrapStage.COMPLETED
            session.status = BootstrapStage.COMPLETED
            session.progress = 1.0
            session.completed_at = datetime.now()
            session.updated_at = datetime.now()

            # 更新项目状态
            await self._update_project_status(session.project_id, ProjectStatus.ACTIVE)
            await self._persist_session(session)

            # Debug: 检查返回前的 confirmed_seed
            logger.info(f"Before return: confirmed_seed type = {type(session.confirmed_seed)}, world_id = {session.confirmed_seed.get('world_id', 'N/A')}")

            result = self._build_completed_result(session)
            if postgres_db and operation:
                await OperationLifecycleService(db=postgres_db).complete(operation, result)
            return result

        except Exception as e:
            logger.error(f"Bootstrap 执行失败：{e}")
            session.current_stage = BootstrapStage.FAILED
            session.status = BootstrapStage.FAILED
            session.error_message = str(e)
            session.progress = 0.0
            await self._persist_session(session)
            if postgres_db and operation:
                await OperationLifecycleService(db=postgres_db).fail(operation, str(e))
            raise

    async def _bootstrap_world(self, session: BootstrapSession):
        """创建世界"""
        seed = session.confirmed_seed
        project_id = session.project_id

        # Debug: 检查关键字段类型
        logger.info(f"_bootstrap_world: world_setting type = {type(seed.get('world_setting'))}")
        logger.info(f"_bootstrap_world: world_rules type = {type(seed.get('world_rules'))}")
        logger.info(f"_bootstrap_world: main_characters type = {type(seed.get('main_characters'))}")

        if seed.get("world_id"):
            logger.info(f"Bootstrap world already exists, skip creation: {seed['world_id']}")
            return

        # 获取 world 数据
        world_setting = seed.get("world_setting")
        if not isinstance(world_setting, dict):
            world_setting = {}
        if seed.get("world_name"):
            world_setting.setdefault("name", seed.get("world_name"))
        if seed.get("world_description"):
            world_setting.setdefault("description", seed.get("world_description"))
        if seed.get("genre"):
            world_setting.setdefault("world_type", seed.get("genre"))

        # 使用标准 UUID 格式
        world_id = str(uuid.uuid4())

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
        if not isinstance(world_rules, list):
            logger.error(f"world_rules is not list: {world_rules}")
            world_rules = []

        for idx, rule_data in enumerate(world_rules):
            # 如果是字符串，转换为规则对象
            if isinstance(rule_data, str):
                rule = WorldRule(
                    id=str(uuid.uuid4()),
                    name=f"规则 {idx + 1}",
                    description=rule_data,
                    category="general",
                    priority=0,
                    is_absolute=False,
                )
                world.rules.append(rule)
            elif isinstance(rule_data, dict):
                rule = WorldRule(
                    id=str(uuid.uuid4()),
                    name=rule_data.get("name", f"规则 {idx + 1}"),
                    description=rule_data.get("description", ""),
                    category=rule_data.get("category", "general"),
                    priority=rule_data.get("priority", 0),
                    is_absolute=rule_data.get("is_absolute", False),
                )
                world.rules.append(rule)
            else:
                logger.warning(f"rule_data is unknown type: {type(rule_data)}, skipping")

        # 保存到数据库
        from app.api.app import postgres_db
        if postgres_db:
            world_data = world.model_dump(mode="json")
            await postgres_db.save_world(world_data)
            from app.services.graph_projection_service import enqueue_graph_projection_best_effort
            await enqueue_graph_projection_best_effort("world", world_data)

            # 更新项目的 world_id
            await postgres_db.update_project(project_id, {"world_id": world_id})

        # 更新 seed 中的 world_id
        seed["world_id"] = world_id

        # 创建区域
        await self._bootstrap_regions(session, world_id)

    async def _bootstrap_regions(self, session: BootstrapSession, world_id: str):
        """创建区域"""
        seed = session.confirmed_seed
        if seed.get("region_ids"):
            logger.info(f"Bootstrap regions already exist, skip creation: {seed['region_ids']}")
            return

        regions_data = seed.get("regions") or seed.get("main_regions") or []

        if not isinstance(regions_data, list):
            logger.error(f"regions_data is not list: {regions_data}")
            return

        from app.models.world import Region, RegionType

        created_region_ids = []
        for region_data in regions_data:
            if not isinstance(region_data, dict):
                logger.warning(f"region_data is not dict: {region_data}, skipping")
                continue

            # 安全处理 region_type
            region_type_str = region_data.get("region_type", "custom")
            try:
                region_type = RegionType(region_type_str)
            except ValueError:
                # 尝试匹配部分字符串
                region_type_str_lower = region_type_str.lower()
                if "city" in region_type_str_lower:
                    region_type = RegionType.CITY
                elif "village" in region_type_str_lower:
                    region_type = RegionType.VILLAGE
                elif "wilderness" in region_type_str_lower:
                    region_type = RegionType.WILDERNESS
                elif "dungeon" in region_type_str_lower:
                    region_type = RegionType.DUNGEON
                elif "forest" in region_type_str_lower:
                    region_type = RegionType.FOREST
                elif "mountain" in region_type_str_lower:
                    region_type = RegionType.MOUNTAIN
                elif "water" in region_type_str_lower:
                    region_type = RegionType.WATER
                elif "building" in region_type_str_lower:
                    region_type = RegionType.BUILDING
                else:
                    region_type = RegionType.CUSTOM

            region = Region(
                id=str(uuid.uuid4()),
                name=region_data.get("name", ""),
                world_id=world_id,
                region_type=region_type,
                description=region_data.get("description"),
            )

            from app.api.app import postgres_db
            if postgres_db:
                region_payload = region.model_dump(mode="json")
                await postgres_db.save_region(region_payload)
                from app.services.graph_projection_service import enqueue_graph_projection_best_effort
                await enqueue_graph_projection_best_effort("region", region_payload)
                created_region_ids.append(region.id)

        seed["region_ids"] = created_region_ids

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

        if seed.get("character_ids"):
            logger.info(f"Bootstrap characters already exist, skip creation: {seed['character_ids']}")
            return

        # 获取角色数据
        main_characters = seed.get("main_characters", [])
        supporting_characters = seed.get("supporting_characters", [])

        # 确保是列表
        if not isinstance(main_characters, list):
            logger.error(f"main_characters is not list: {main_characters}")
            main_characters = []
        if not isinstance(supporting_characters, list):
            logger.error(f"supporting_characters is not list: {supporting_characters}")
            supporting_characters = []

        all_characters = main_characters + supporting_characters

        from app.models.character import Character, CharacterStatus

        created_character_ids = []

        for char_data in all_characters:
            if not isinstance(char_data, dict):
                logger.warning(f"char_data is not dict: {char_data}, skipping")
                continue
            character = Character(
                id=str(uuid.uuid4()),
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
                character_payload = character.model_dump(mode="json")
                await postgres_db.save_character(character_payload)
                from app.services.graph_projection_service import enqueue_graph_projection_best_effort
                await enqueue_graph_projection_best_effort("character", character_payload)
                created_character_ids.append(character.id)

        # 更新 seed 中的角色 ID 列表
        seed["character_ids"] = created_character_ids

    async def _create_initial_snapshot(self, session: BootstrapSession):
        """创建初始快照"""
        seed = session.confirmed_seed
        world_id = seed.get("world_id")

        if not world_id:
            raise ValueError("World 尚未创建")

        if seed.get("initial_snapshot_id"):
            logger.info(f"Bootstrap initial snapshot already exists, skip creation: {seed['initial_snapshot_id']}")
            return

        snapshot_data = {
            "id": str(uuid.uuid4()),
            "world_id": world_id,
            "chapter_id": None,  # 初始快照没有章节
            "snapshot_type": "initial",
            "name": "Bootstrap 初始快照",
            "description": "项目初始化时的世界状态快照",
            "characters": {},
            "relationships": {},
            "regions": {},
            "hooks": {},
            "main_plot_progress": 0.0,
            "completed_events": [],
            "character_locations": {},
            "created_at": datetime.now().isoformat(),
            "created_by": "bootstrap",
            "parent_snapshot_id": None,
            "is_branch": False,
            "branch_reason": None,
        }

        from app.api.app import postgres_db
        if postgres_db:
            await postgres_db.save_snapshot(snapshot_data)
            seed["initial_snapshot_id"] = snapshot_data["id"]

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