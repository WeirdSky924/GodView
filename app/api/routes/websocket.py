"""
WebSocket 路由 - 实时交互接口
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.models.agent_template import AgentType
from app.services.director import DirectorSystem
from app.services.model_router import create_model_factory
from app.services.workflow import DirectorWorkflow
from app.services.workflow_node_registry import (
    get_workflow_node_profile,
    normalize_workflow_agent_type,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.client_data: Dict[WebSocket, Dict[str, Any]] = {}
        self.director_sessions: Dict[str, DirectorSystem] = {}
        # 客户端当前的工作流执行ID
        self.client_executions: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.client_data[websocket] = {
            "client_id": client_id,
            "connected_at": asyncio.get_event_loop().time(),
        }
        logger.info(f"客户端 {client_id} 已连接")

    def disconnect(self, websocket: WebSocket):
        client = self.client_data.get(websocket, {})
        client_id = client.get("client_id")
        self.active_connections.discard(websocket)
        self.client_data.pop(websocket, None)
        if client_id:
            # 取消该客户端的工作流执行
            execution_id = self.client_executions.get(client_id)
            if execution_id:
                # 异步取消工作流（在事件循环中执行）
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self._cancel_workflow_async(execution_id, client_id))
                except Exception as e:
                    logger.warning(f"取消工作流失败: {e}")
            self.director_sessions.pop(client_id, None)
            self.client_executions.pop(client_id, None)
        logger.info("客户端断开连接")

    async def _cancel_workflow_async(self, execution_id: str, client_id: str):
        """异步取消工作流"""
        try:
            from app.services.workflow_engine import get_workflow_engine
            engine = get_workflow_engine()
            success = await engine.cancel_workflow(execution_id)
            if success:
                logger.info(f"已取消客户端 {client_id} 的工作流执行: {execution_id}")
            # 清理干预队列
            await engine.clear_interventions(execution_id)
        except Exception as e:
            logger.warning(f"取消工作流异常: {e}")

    def set_execution(self, client_id: str, execution_id: str):
        """设置客户端当前的工作流执行ID"""
        self.client_executions[client_id] = execution_id

    def get_execution(self, client_id: str) -> Optional[str]:
        """获取客户端当前的工作流执行ID"""
        return self.client_executions.get(client_id)

    def clear_execution(self, client_id: str):
        """清除客户端的工作流执行ID"""
        self.client_executions.pop(client_id, None)


manager = ConnectionManager()


async def create_agent_provider(director: DirectorSystem):
    """
    创建 Agent 提供器

    这个函数返回一个能够动态获取 Agent 的 provider，
    支持系统 Agent 和动态创建的角色 Agent。

    支持的角色获取格式：
    - 'character:char_001' - 获取指定角色
    - 'character:char_001:memory' - 获取角色的回忆形态
    - 'character:char_001:spirit' - 获取角色的灵魂形态
    - 'characters:present' - 获取所有在场角色
    - 'characters:memory' - 获取可出现在回忆中的角色

    Args:
        director: 导演系统实例

    Returns:
        Callable: Agent provider 函数
    """
    # 获取数据库连接（用于记忆加载）
    from app.api.app import postgres_db

    async def _resolve_runtime_state(agent_type_value: str, project_id: str) -> Optional[Dict[str, Any]]:
        if not postgres_db or not project_id:
            return None

        try:
            from app.services.agent_config_service import get_agent_config_service

            config_service = get_agent_config_service()
            return await config_service.resolve_agent_runtime_state(project_id, agent_type_value)
        except Exception as e:
            logger.warning(
                f"读取 Agent 运行时状态失败: project={project_id}, agent={agent_type_value}, error={e}"
            )
            return None

    async def _is_agent_disabled(agent_type_value: str, project_id: str) -> tuple[bool, Optional[str]]:
        runtime_state = await _resolve_runtime_state(agent_type_value, project_id)
        if runtime_state and runtime_state.get("enabled") is False:
            return True, runtime_state.get("reason", "Agent 已禁用")
        return False, None

    async def _build_runtime_world(project_id: str):
        from app.models.world import World

        world = None

        if hasattr(director, "world_data") and director.world_data:
            try:
                world = World(**director.world_data)
                logger.info(f"从 director.world_data 创建 World: {world.name}")
            except Exception as e:
                logger.warning(f"从 world_data 创建 World 失败: {e}")

        if not world and postgres_db and director.project_id:
            try:
                project = await postgres_db.get_project(director.project_id)
                if project and project.get("world_id"):
                    world_data = await postgres_db.get_world(project["world_id"])
                    if world_data:
                        world = World(**world_data)
                        logger.info(f"从数据库获取 World: {world.name}")
            except Exception as e:
                logger.warning(f"获取世界数据失败: {e}")

        if not world and postgres_db and project_id:
            try:
                project = await postgres_db.get_project(project_id)
                if project:
                    world_payload = {
                        "id": project.get("world_id") or f"world_{project_id}",
                        "project_id": project_id,
                        "name": project.get("name") or "项目世界",
                        "description": project.get("description") or project.get("premise") or "",
                        "world_type": project.get("world_type") or "unknown",
                        "tone": project.get("tone") or "serious",
                    }
                    world = World(**world_payload)
                    logger.info(f"从项目信息构建 World: {world.name}")
            except Exception as e:
                logger.warning(f"从项目信息构建 World 失败: {e}")

        return world

    async def _prepare_runtime_agent(agent):
        if agent and hasattr(agent, 'load_memory') and not getattr(agent, '_memory_loaded', False):
            await agent.load_memory(postgres_db)
        return agent

    async def _create_isolated_runtime_agent(
        agent_type_lower: str,
        normalized_agent_type: str,
        project_id: str,
    ):
        model = director._model_factory() if director._model_factory else None

        if agent_type_lower == "summarizer" or normalized_agent_type == AgentType.SUMMARIZER.value:
            from app.agents.director.summarizer import SummarizerAgent
            return await _prepare_runtime_agent(
                SummarizerAgent(model=model, project_id=project_id)
            )

        if agent_type_lower in ["master_plotter", "plotter"] or normalized_agent_type == AgentType.MASTER_PLOTTER.value:
            from app.agents.director.master_plotter import MasterPlotterAgent
            return await _prepare_runtime_agent(
                MasterPlotterAgent(model=model, project_id=project_id)
            )

        if agent_type_lower == "hook_manager" or normalized_agent_type == AgentType.HOOK_MANAGER.value:
            from app.agents.director.hook_manager import HookManagerAgent
            return await _prepare_runtime_agent(
                HookManagerAgent(model=model, project_id=project_id)
            )

        if agent_type_lower == "writer" or normalized_agent_type == AgentType.WRITER.value:
            from app.agents.director.writer import WriterAgent
            return await _prepare_runtime_agent(
                WriterAgent(model=model, project_id=project_id)
            )

        if agent_type_lower == "evaluator" or normalized_agent_type == AgentType.EVALUATOR.value:
            from app.agents.evaluator import EvaluatorAgent
            return await _prepare_runtime_agent(
                EvaluatorAgent(model=model, project_id=project_id)
            )

        if agent_type_lower == "setting" or normalized_agent_type == AgentType.SETTING.value:
            from app.agents.setting_agent import SettingAgent
            return await _prepare_runtime_agent(
                SettingAgent(model=model, project_id=project_id)
            )

        return None

    async def _create_runtime_character_agent(character_agent, runtime_project_id: str):
        from app.agents.character_agent import CharacterAgent

        model = director._model_factory() if director._model_factory else None
        runtime_agent = CharacterAgent(
            character=character_agent.character.model_copy(deep=True),
            model=model,
            project_id=runtime_project_id,
            agent_id=character_agent.character.id,
        )
        return await _prepare_runtime_agent(runtime_agent)

    async def agent_provider(agent_type: str, project_id: str):
        """
        获取 Agent 实例（并加载记忆）

        Args:
            agent_type: Agent 类型
            project_id: 项目 ID

        Returns:
            Agent 实例或 None
        """
        from app.models.character import CharacterPresence

        normalized_agent_type = normalize_workflow_agent_type(agent_type)
        profile = get_workflow_node_profile(agent_type)
        agent_type_lower = normalized_agent_type.lower().replace(" ", "_").replace("-", "_")

        agent_type_enum: Optional[AgentType] = None
        try:
            agent_type_enum = AgentType(normalized_agent_type)
        except ValueError:
            agent_type_enum = None

        if agent_type_enum is not None:
            disabled, reason = await _is_agent_disabled(agent_type_enum.value, project_id)
            if disabled:
                logger.info(
                    f"Agent 在当前项目已禁用，provider 返回 None: type={agent_type_enum.value}, project_id={project_id}, reason={reason}"
                )
                return None

        if profile and profile.kind == "service_adapter":
            logger.info(
                f"工作流节点 {agent_type} 注册为 service_adapter，跳过 agent_provider 实例化"
            )
            return None

        # 系统内置 Agent（workflow/runtime 路径统一按需创建独立实例，避免共享状态串扰）
        isolated_runtime_agent = await _create_isolated_runtime_agent(
            agent_type_lower,
            normalized_agent_type,
            project_id,
        )
        if isolated_runtime_agent:
            logger.info(
                f"为 workflow/runtime 创建独立 Agent 实例: type={normalized_agent_type}, "
                f"instance_id={id(isolated_runtime_agent)}, project_id={project_id}"
            )
            return isolated_runtime_agent

        if agent_type_lower == "event_generator":
            from app.agents.event_generator import EventGeneratorAgent
            model = director._model_factory() if director._model_factory else None
            agent_instance = EventGeneratorAgent(
                model=model,
                project_id=project_id,
                agent_id="event_generator",
            )
            logger.info(f"EventGeneratorAgent 实例已创建: project_id={project_id}")
            await agent_instance.load_memory(postgres_db)
            return agent_instance

        if agent_type_lower == "world_map_manager":
            from app.agents.world_map_manager import WorldMapManagerAgent
            model = director._model_factory() if director._model_factory else None
            agent_instance = WorldMapManagerAgent(
                model=model,
                project_id=project_id,
                agent_id="world_map_manager",
            )
            logger.info(f"WorldMapManagerAgent 实例已创建: project_id={project_id}")
            await agent_instance.load_memory(postgres_db)
            return agent_instance

        if agent_type_lower in ["procgen", "proc_gen"]:
            from app.agents.procgen import ProcGenAgent
            model = director._model_factory() if director._model_factory else None

            logger.info(f"创建新的 ProcGenAgent 实例，类型: {agent_type}, 模型: {type(model) if model else None}")
            world = await _build_runtime_world(project_id)
            if not world:
                raise ValueError(f"项目 {project_id} 缺少世界观信息，无法执行 {normalized_agent_type}")

            agent_instance = ProcGenAgent(
                world=world,
                model=model,
                project_id=project_id,
                agent_id=agent_type_lower,
            )
            logger.info(
                f"ProcGenAgent 实例已创建: 类型={agent_type}, 实例ID={id(agent_instance)}, 世界={world.name}, 模型={type(model).__name__ if model else 'None'}"
            )
            await agent_instance.load_memory(postgres_db)
            return agent_instance

        if agent_type_lower == "scene_coordinator" or normalized_agent_type == "scene_coordinator":
            from app.agents.scene_coordinator import SceneCoordinatorAgent
            model = director._model_factory() if director._model_factory else None
            return SceneCoordinatorAgent(model=model, project_id=project_id)

        if agent_type_lower == "dungeon_generator" or normalized_agent_type == "dungeon_generator":
            from app.agents.procgen import ProcGenAgent
            model = director._model_factory() if director._model_factory else None
            logger.info(f"获取 DungeonGenerator Agent (使用 procgen): project_id={project_id}")
            world = await _build_runtime_world(project_id)
            if not world:
                raise ValueError(f"项目 {project_id} 缺少世界观信息，无法执行 dungeon_generator")
            agent_instance = ProcGenAgent(
                world=world,
                model=model,
                project_id=project_id,
                agent_id="dungeon_generator",
                agent_type=AgentType.DUNGEON_GENERATOR.value,
            )
            await agent_instance.load_memory(postgres_db)
            return agent_instance

        if agent_type.startswith("characters:"):
            presence_type = agent_type.split(":", 1)[1]
            agents = director.get_character_by_presence(presence_type)
            if agents:
                runtime_agents = []
                for character_agent in agents:
                    runtime_agents.append(await _create_runtime_character_agent(character_agent, project_id))
                return runtime_agents
            logger.warning(f"未找到在场形式为 '{presence_type}' 的角色")
            return None

        if agent_type.startswith("character:"):
            parts = agent_type.split(":")
            char_id = parts[1]

            char_agent = director.get_character_agent(char_id)
            if not char_agent:
                logger.warning(f"角色 {char_id} 不存在")
                return None

            if len(parts) > 2:
                presence_type = parts[2]
                try:
                    presence = CharacterPresence(presence_type)
                    if presence not in char_agent.character.available_presence_types:
                        logger.warning(f"角色 {char_id} 不支持在场形式 '{presence_type}'，可用: {[p.value for p in char_agent.character.available_presence_types]}")
                        return await _create_runtime_character_agent(char_agent, project_id)
                except ValueError:
                    logger.warning(f"未知的在场形式: {presence_type}")

            return await _create_runtime_character_agent(char_agent, project_id)

        char_agent = director.get_character_agent(agent_type)
        if char_agent:
            return await _create_runtime_character_agent(char_agent, project_id)

        if normalized_agent_type.lower() in ["character", "characteragent"]:
            active_chars = director.get_active_character_agents()
            if active_chars:
                first_active_agent = list(active_chars.values())[0]
                return await _create_runtime_character_agent(first_active_agent, project_id)

        logger.warning(f"未知的 Agent 类型: {agent_type}")
        return None

    return agent_provider


def setup_workflow_engine_callbacks(director: DirectorSystem, broadcast_callback=None):
    """
    设置工作流引擎的回调函数

    Args:
        director: 导演系统实例
        broadcast_callback: WebSocket 广播回调
    """
    from app.services.workflow_engine import get_workflow_engine

    engine = get_workflow_engine()

    # 设置 Agent provider
    async def _agent_provider_wrapper(agent_type: str, project_id: str):
        provider = await create_agent_provider(director)
        return await provider(agent_type, project_id)

    engine.set_agent_provider(_agent_provider_wrapper)

    # 设置广播回调
    if broadcast_callback:
        engine.set_broadcast_callback(broadcast_callback)

    logger.info("工作流引擎回调已设置")


async def send_log(websocket: WebSocket, message: str, level: str = "info"):
    await websocket.send_json({"type": "log", "level": level, "message": message})


def _serialize_for_json(obj: Any) -> Any:
    """递归序列化对象，处理 UUID 等非 JSON 类型"""
    import uuid
    from datetime import datetime

    if isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return _serialize_for_json(obj.__dict__)
    else:
        return obj


async def send_agent_update(websocket: WebSocket, agent: str, status: str, message: str, progress: int | None = None, output: Any = None):
    payload = {"type": "agent_status", "agent": agent, "status": status, "message": message}
    if progress is not None:
        payload["progress"] = progress
    if output is not None:
        payload["output"] = _serialize_for_json(output)
    await websocket.send_json(payload)


async def _load_characters(present_characters: list[str] | None = None) -> list[dict[str, Any]]:
    from app.api.app import postgres_db

    if not postgres_db:
        return []

    if present_characters:
        characters = []
        for character_id in present_characters:
            data = await postgres_db.get_character(character_id)
            if data:
                characters.append(data)
        return characters

    return await postgres_db.get_all_characters()


async def _persist_runtime_state(director: DirectorSystem):
    from app.api.app import postgres_db

    if not postgres_db:
        return

    if director.current_chapter:
        chapter_payload = dict(director.current_chapter)
        chapter_payload.setdefault("world_id", director.world_id)
        chapter_payload.setdefault("title", "未命名章节")
        chapter_payload.setdefault("summary", "")
        chapter_payload.setdefault("content", "")
        chapter_payload.setdefault("word_count", 0)
        chapter_payload.setdefault("status", "in_progress")
        chapter_payload.setdefault("events", [event.get("id") for event in director.chapter_events])
        chapter_payload.setdefault("hooks_planted", director.hooks_planted)
        chapter_payload.setdefault("hooks_resolved", director.hooks_resolved)
        chapter_payload.setdefault("main_plot_progress", director.main_plot_progress)
        chapter_payload.setdefault("reader_scores", None)
        chapter_payload.setdefault("created_at", datetime.utcnow().isoformat())
        chapter_payload["updated_at"] = datetime.utcnow().isoformat()
        chapter_payload.setdefault("completed_at", None)
        await postgres_db.save_chapter(chapter_payload)

    for hook_id in director.hooks_planted:
        await postgres_db.save_hook({
            "id": hook_id,
            "title": hook_id,
            "description": f"运行时生成伏笔 {hook_id}",
            "hook_type": "custom",
            "status": "planted",
            "related_characters": [],
            "related_locations": [],
            "related_objects": [],
            "plant_context": director.current_chapter.get("title", "") if director.current_chapter else "",
            "plant_chapter": director.current_chapter.get("id") if director.current_chapter else None,
            "resolution_hint": None,
            "resolution_context": None,
            "resolution_chapter": None,
            "priority": 1,
            "created_at": datetime.utcnow().isoformat(),
            "resolved_at": None,
        })

    for hook_id in director.hooks_resolved:
        await postgres_db.save_hook({
            "id": hook_id,
            "title": hook_id,
            "description": f"运行时回收伏笔 {hook_id}",
            "hook_type": "custom",
            "status": "resolved",
            "related_characters": [],
            "related_locations": [],
            "related_objects": [],
            "plant_context": director.current_chapter.get("title", "") if director.current_chapter else "",
            "plant_chapter": director.current_chapter.get("id") if director.current_chapter else None,
            "resolution_hint": None,
            "resolution_context": director.current_chapter.get("title", "") if director.current_chapter else None,
            "resolution_chapter": director.current_chapter.get("id") if director.current_chapter else None,
            "priority": 1,
            "created_at": datetime.utcnow().isoformat(),
            "resolved_at": datetime.utcnow().isoformat(),
        })


async def _create_auto_snapshot(director: DirectorSystem, snapshot_type: str, created_by: str = "system", is_branch: bool = False, branch_reason: str | None = None):
    from app.api.app import postgres_db

    if not postgres_db:
        return None

    snapshot = await director.create_snapshot(
        snapshot_type=snapshot_type,
        created_by=created_by,
        is_branch=is_branch,
        branch_reason=branch_reason,
    )
    await postgres_db.save_snapshot(snapshot)
    return snapshot


def get_or_create_director(client_id: str, project_id: Optional[str] = None) -> DirectorSystem:
    director = manager.director_sessions.get(client_id)
    if director:
        return director
    director = DirectorSystem(
        world_data={"id": f"world_{client_id}", "name": "Default World", "regions": [], "relationships": {}},
        config={
            "max_turns_threshold": settings.max_turns_threshold,
            "target_word_count_per_intent": settings.target_word_count_per_intent,
        },
        project_id=project_id,
    )
    manager.director_sessions[client_id] = director
    return director


@router.websocket("/connect/{client_id}")
async def websocket_connect(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    await send_log(websocket, f"会话 {client_id} 已建立连接")

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                message_type = message.get("type", "unknown")

                if message_type == "start_session":
                    await handle_start_session(websocket, message, client_id)
                elif message_type == "generate_dialogue":
                    await handle_generate_dialogue(websocket, message, client_id)
                elif message_type == "generate_narrative":
                    await handle_generate_narrative(websocket, message, client_id)
                elif message_type == "chapter_end_check":
                    await handle_chapter_end_check(websocket, message, client_id)
                elif message_type == "intervention":
                    await handle_intervention(websocket, message, client_id)
                elif message_type == "manage_hooks":
                    await handle_manage_hooks(websocket, message, client_id)
                elif message_type == "agent_command":
                    await handle_agent_command(websocket, message, client_id)
                elif message_type == "workflow_cycle":
                    await handle_workflow_cycle(websocket, message, client_id)
                elif message_type == "generate_region":
                    await handle_create_snapshot(websocket, message, client_id)
                elif message_type == "rollback_snapshot":
                    await handle_rollback_snapshot(websocket, message, client_id)
                elif message_type == "stop_session":
                    await handle_stop_session(websocket, message, client_id)
                elif message_type == "add_character":
                    await handle_add_character(websocket, message, client_id)
                elif message_type == "remove_character":
                    await handle_remove_character(websocket, message, client_id)
                elif message_type == "get_characters":
                    await handle_get_characters(websocket, message, client_id)
                elif message_type == "auto_write_chapter":
                    await handle_auto_write_chapter(websocket, message, client_id)
                elif message_type == "start_auto_mode":
                    await handle_start_auto_mode(websocket, message, client_id)
                elif message_type == "stop_auto_mode":
                    await handle_stop_auto_mode(websocket, message, client_id)
                # v8 工作流控制
                elif message_type == "workflow_start":
                    await handle_workflow_start(websocket, message, client_id)
                elif message_type == "workflow_pause":
                    await handle_workflow_pause(websocket, message, client_id)
                elif message_type == "workflow_resume":
                    await handle_workflow_resume(websocket, message, client_id)
                elif message_type == "workflow_step":
                    await handle_workflow_step(websocket, message, client_id)
                elif message_type == "workflow_user_input":
                    await handle_workflow_user_input(websocket, message, client_id)
                elif message_type == "workflow_status":
                    await handle_workflow_status(websocket, message, client_id)
                # v8 Agent 通信
                elif message_type == "agent_message":
                    await handle_agent_message(websocket, message, client_id)
                elif message_type == "intervention_request":
                    await handle_intervention_request(websocket, message, client_id)
                # 集体讨论
                elif message_type == "discussion_message":
                    await handle_discussion_message(websocket, message, client_id)
                elif message_type == "end_discussion":
                    await handle_end_discussion(websocket, message, client_id)
                elif message_type == "discussion_confirm":
                    await handle_discussion_confirm(websocket, message, client_id)
                else:
                    await send_error(websocket, f"未知消息类型：{message_type}")
            except json.JSONDecodeError:
                await send_error(websocket, "无效的 JSON 格式")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"客户端 {client_id} 断开连接")


@router.get("/workflow/{client_id}")
async def get_workflow_graph(client_id: str):
    director = manager.director_sessions.get(client_id)
    if not director:
        return {"nodes": [], "edges": []}
    workflow = DirectorWorkflow(director)
    return workflow.describe_graph()


@router.get("/snapshots/{client_id}")
async def get_session_state(client_id: str):
    director = manager.director_sessions.get(client_id)
    if not director:
        return {"success": False, "message": "session not found"}
    return {"success": True, "data": director.export_runtime_state()}


async def handle_start_session(websocket: WebSocket, message: dict, client_id: str):
    # 从消息中获取 project_id
    project_id = message.get("project_id")
    director = get_or_create_director(client_id, project_id=project_id)
    await send_log(websocket, "正在初始化 DirectorSystem...")

    characters = await _load_characters(message.get("present_characters"))
    model_factory = create_model_factory()
    await director.initialize(model_factory, characters=characters)
    await director.start_chapter(
        title=message.get("title", "未命名章节"),
        goal=message.get("goal", "推进剧情"),
    )
    await _persist_runtime_state(director)
    snapshot = await _create_auto_snapshot(director, snapshot_type="manual", created_by="system")

    # 设置工作流引擎回调（支持动态获取 Agent）
    async def _broadcast_callback(execution_id: str, event_type: str, data: dict):
        """广播工作流事件到 WebSocket"""
        try:
            # 检查 WebSocket 连接状态
            if websocket.client_state.name == "DISCONNECTED":
                logger.warning(f"WebSocket 已断开，跳过广播: {event_type}")
                return
            await websocket.send_json({
                "type": event_type,
                "execution_id": execution_id,
                "data": data,
            })
        except Exception as e:
            logger.warning(f"广播回调失败（连接可能已断开）: {e}")

    setup_workflow_engine_callbacks(director, _broadcast_callback)
    await send_log(websocket, "工作流引擎已就绪")

    # 初始化所有Agent为idle状态（等待工作流执行）
    for agent in ["Summarizer", "Master Plotter", "Hook Manager", "Writer", "Evaluator", "Character Agent", "ProcGen"]:
        await send_agent_update(websocket, agent, "idle", f"{agent} 已就绪", 0)

    await websocket.send_json({
        "type": "session_started",
        "status": "success",
        "data": {
            "session_id": client_id,
            "world_id": director.world_id,
            "snapshot_id": snapshot.get("id") if snapshot else None,
            "characters_count": len(director.character_agents),
        },
    })
    await send_log(websocket, "DirectorSystem 初始化完成")


async def handle_generate_dialogue(websocket: WebSocket, message: dict, client_id: str):
    director = get_or_create_director(client_id)
    await send_agent_update(websocket, "Character Agent", "working", "正在生成角色对话", 40)
    result = await director.process_dialogue_turn(
        speaker_id=message.get("speaker_id", "narrator"),
        context=message.get("context", "当前场景推进中"),
        present_characters=message.get("present_characters", []),
    )
    await _persist_runtime_state(director)
    await websocket.send_json({"type": "dialogue_generated", "status": "success", "data": result})
    await send_agent_update(websocket, "Character Agent", "completed", "对话生成完成", 100)


async def handle_generate_narrative(websocket: WebSocket, message: dict, client_id: str):
    director = get_or_create_director(client_id)
    await send_agent_update(websocket, "Writer", "working", "正在生成叙事文本", 45)
    result = await director.generate_narrative(
        intents=message.get("intents", ["推进场景"]),
        environment=message.get("environment", "夜晚，房间安静"),
        character_moods=message.get("character_moods", {}),
    )
    await _persist_runtime_state(director)
    await websocket.send_json({"type": "narrative_generated", "status": "success", "data": result})
    await send_agent_update(websocket, "Writer", "completed", "叙事生成完成", 100)


async def handle_chapter_end_check(websocket: WebSocket, message: dict, client_id: str):
    director = get_or_create_director(client_id)
    await send_agent_update(websocket, "Evaluator", "working", "正在评估章节是否可收尾", 50)
    result = await director.check_chapter_end(chapter_content=message.get("chapter_content"))
    await _persist_runtime_state(director)
    snapshot = None
    if result.get("should_end"):
        snapshot = await _create_auto_snapshot(director, snapshot_type="auto", created_by="system")
    await websocket.send_json({
        "type": "chapter_end_result",
        "status": "success",
        "data": result,
        "snapshot_id": snapshot.get("id") if snapshot else None,
    })
    await send_agent_update(websocket, "Evaluator", "completed", "章节评估完成", 100)


async def handle_intervention(websocket: WebSocket, message: dict, client_id: str):
    """
    处理Agent干预消息

    消息格式:
    {
        "type": "intervention",
        "agent": "Agent名称",
        "message": "干预消息内容"
    }
    """
    from app.api.app import postgres_db

    director = get_or_create_director(client_id)
    agent_name = message.get("agent", "unknown")
    # 使用前端传来的 agent_type，用于工作流匹配
    agent_type = message.get("agent_type", agent_name.lower().replace(" ", "_"))
    user_message = message.get("message", "")

    if not user_message:
        await send_error(websocket, "干预消息不能为空")
        return

    await send_log(websocket, f"💬 向 {agent_name} 发送干预: {user_message}")

    # ========== 优先检查是否有活跃的工作流执行 ==========
    execution_id = manager.get_execution(client_id)
    if execution_id:
        from app.services.workflow_engine import get_workflow_engine
        engine = get_workflow_engine()

        # 检查工作流是否仍在运行
        execution = await engine.get_execution_state(execution_id)
        if execution and execution.status in ["running", "paused"]:
            # 添加干预到工作流队列（使用 agent_type 进行匹配）
            success = await engine.add_intervention(
                execution_id=execution_id,
                agent_type=agent_type,
                message=user_message,
            )

            if success:
                await send_log(websocket, f"✅ 干预已加入队列，将在 {agent_name} 下一次执行时生效")

                # 确认消息
                await websocket.send_json({
                    "type": "intervention_queued",
                    "status": "success",
                    "data": {
                        "agent": agent_name,
                        "message": user_message,
                        "execution_id": execution_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                })
                return

    # ========== 无活跃工作流，执行直接干预 ==========
    await send_agent_update(websocket, agent_name, "working", "处理干预消息...", 50)

    try:
        # 根据不同的Agent类型处理干预
        response_text = ""
        agent_instance = None

        # 获取对应的Agent实例
        agent_mapping = {
            "Summarizer": director.summarizer,
            "Master Plotter": director.master_plotter,
            "Hook Manager": director.hook_manager,
            "Writer": director.writer,
            "Evaluator": director.evaluator,
            "ProcGen": director.procgen,
        }

        agent_instance = agent_mapping.get(agent_name)

        if agent_instance:
            # 调用Agent处理干预消息
            from langchain_core.messages import HumanMessage
            result = await agent_instance._call_llm(
                messages=[
                    HumanMessage(content=f"""用户干预指令：{user_message}

请根据用户的干预指令，给出你的回应。如果你是角色Agent，请以角色的身份回应。
回应格式为JSON：
{{
    "response": "对干预的回应",
    "actions": ["建议采取的行动"],
    "notes": "其他备注"
}}""")
                ],
                temperature=0.7
            )

            # 解析响应
            parsed = agent_instance._parse_json_response(result) if hasattr(agent_instance, '_parse_json_response') else {"response": result}
            response_text = parsed.get("response", result[:500] if isinstance(result, str) else "已处理")
        else:
            # 对于角色Agent，检查是否在character_agents中
            if "Character" in agent_name or agent_name in director.character_agents:
                response_text = f"角色 [{agent_name}] 收到干预指令，正在思考..."

                # 如果有角色Agent，尝试获取响应
                for char_id, char_agent in director.character_agents.items():
                    if agent_name == "Character Agent" or char_agent.character.name == agent_name:
                        # 简单模拟响应
                        response_text = f"[{char_agent.character.name}]: 我收到了你的指令：'{user_message}'。让我考虑一下该如何行动..."
                        break
            else:
                response_text = f"Agent [{agent_name}] 收到干预指令，但该Agent当前不可用"

        # 记录干预日志
        snapshot = await _create_auto_snapshot(
            director,
            snapshot_type="pre_intervention",
            created_by="user",
            is_branch=True,
            branch_reason=f"干预 {agent_name}: {user_message[:50]}",
        )

        intervention_record = await director.create_intervention_record(
            snapshot_id=snapshot.get("id") if snapshot else "",
            intervention_type="agent_intervention",
            description=f"向 {agent_name} 发送干预: {user_message}",
            details={"agent": agent_name, "user_message": user_message, "response": response_text},
        )

        if postgres_db:
            await postgres_db.log_intervention(intervention_record)

        # 发送响应
        await websocket.send_json({
            "type": "intervention_response",
            "status": "success",
            "data": {
                "agent": agent_name,
                "user_message": user_message,
                "response": response_text,
                "intervention_id": intervention_record.get("id"),
                "timestamp": datetime.utcnow().isoformat(),
            },
        })

        # 更新Agent输出
        await send_agent_update(websocket, agent_name, "completed", "干预处理完成", 100, output=response_text)
        await send_log(websocket, f"✅ {agent_name} 干预响应完成")

    except Exception as e:
        logger.error(f"处理干预消息失败: {e}")
        await send_agent_update(websocket, agent_name, "error", f"干预处理失败: {str(e)}", 0)
        await send_error(websocket, f"干预处理异常: {str(e)}")


async def handle_manage_hooks(websocket: WebSocket, message: dict, client_id: str):
    director = get_or_create_director(client_id)

    # 检查导演系统是否已初始化
    if not director.hook_manager:
        await websocket.send_json({
            "type": "error",
            "status": "error",
            "message": "导演系统未初始化，请先启动会话",
            "hint": "请先点击'启动会话'按钮初始化导演系统",
        })
        return

    await send_agent_update(websocket, "Hook Manager", "working", "正在检查伏笔状态", 50)
    result = await director.manage_hooks()
    await _persist_runtime_state(director)
    await websocket.send_json({"type": "hooks_managed", "status": "success", "data": result})
    await send_agent_update(websocket, "Hook Manager", "completed", "伏笔管理完成", 100)


async def handle_agent_command(websocket: WebSocket, message: dict, client_id: str):
    agent = message.get("agent", "Unknown Agent")
    command = message.get("command", "")
    await send_agent_update(websocket, agent, "working", f"正在执行手动指令: {command}", 30)
    await asyncio.sleep(0.1)
    await websocket.send_json({
        "type": "agent_command_result",
        "status": "success",
        "data": {"agent": agent, "command": command, "result": "指令执行成功"},
    })
    await send_agent_update(websocket, agent, "completed", "手动指令执行完成", 100)


async def handle_workflow_cycle(websocket: WebSocket, message: dict, client_id: str):
    from app.api.app import postgres_db

    director = get_or_create_director(client_id)

    # 检查导演系统是否已初始化
    if not director.writer:
        await websocket.send_json({
            "type": "error",
            "status": "error",
            "message": "导演系统未初始化，请先启动会话",
            "hint": "请先点击'启动会话'按钮初始化导演系统",
        })
        return

    await send_agent_update(websocket, "DirectorWorkflow", "working", "正在执行编排工作流", 25)
    result = await director.run_workflow_cycle(
        speaker_id=message.get("speaker_id", "narrator"),
        context=message.get("context", "当前场景推进中"),
        present_characters=message.get("present_characters", []),
        intents=message.get("intents", ["推进剧情"]),
        environment=message.get("environment", ""),
        character_moods=message.get("character_moods", {}),
    )
    await _persist_runtime_state(director)
    snapshot = result.get("snapshot")
    if snapshot and postgres_db:
        await postgres_db.save_snapshot(snapshot)
    await websocket.send_json({"type": "workflow_cycle_result", "status": "success", "data": result})
    await send_agent_update(websocket, "DirectorWorkflow", "completed", "编排工作流执行完成", 100)


async def handle_create_snapshot(websocket: WebSocket, message: dict, client_id: str):
    director = get_or_create_director(client_id)
    snapshot = await _create_auto_snapshot(
        director,
        snapshot_type=message.get("snapshot_type", "manual"),
        created_by=message.get("created_by", "user"),
        is_branch=message.get("is_branch", False),
        branch_reason=message.get("branch_reason"),
    )
    await websocket.send_json({"type": "snapshot_created", "status": "success", "data": snapshot})


async def handle_rollback_snapshot(websocket: WebSocket, message: dict, client_id: str):
    from app.api.app import postgres_db

    director = get_or_create_director(client_id)
    snapshot_id = message.get("snapshot_id")
    if not snapshot_id:
        await send_error(websocket, "缺少 snapshot_id")
        return
    if not postgres_db:
        await send_error(websocket, "数据库未连接")
        return
    snapshot = await postgres_db.rollback_to_snapshot(snapshot_id)
    rollback_result = await director.apply_snapshot(snapshot)
    await websocket.send_json({"type": "snapshot_rolled_back", "status": "success", "data": rollback_result})


async def handle_stop_session(websocket: WebSocket, message: dict, client_id: str):
    from app.services.workflow_engine import get_workflow_engine
    from app.api.app import postgres_db

    director = get_or_create_director(client_id)

    # 1. 停止自动模式（如果正在运行）
    if director.is_auto_running():
        director.stop_auto_mode()
        await send_log(websocket, "⏹️ 正在停止自动运行模式...")

    # 2. 取消当前工作流执行
    execution_id = manager.get_execution(client_id)
    if execution_id:
        engine = get_workflow_engine()
        success = await engine.cancel_workflow(execution_id, postgres_db)
        if success:
            await send_log(websocket, f"✅ 工作流已取消: {execution_id}")
            # 清理干预队列
            await engine.clear_interventions(execution_id)
        manager.clear_execution(client_id)

    # 3. 持久化状态
    await _persist_runtime_state(director)
    await _create_auto_snapshot(director, snapshot_type="manual", created_by="system")

    # 4. 重置所有 Agent 状态
    for agent in ["Summarizer", "Master Plotter", "Hook Manager", "Writer", "Evaluator", "Character Agent", "ProcGen"]:
        await send_agent_update(websocket, agent, "idle", f"{agent} 已停止", 0)

    await send_log(websocket, "导演会话已停止")
    await websocket.send_json({"type": "session_stopped", "status": "success"})


async def handle_add_character(websocket: WebSocket, message: dict, client_id: str):
    """
    动态添加角色

    消息格式:
    {
        "type": "add_character",
        "character_data": {
            "name": "角色名",
            "description": "角色描述",
            "role": "main/supporting",
            "project_id": "项目ID",
            "world_id": "世界ID",
            ...
        }
    }
    """
    import uuid
    from app.api.app import postgres_db
    from app.models.character import Character, CharacterStatus

    director = get_or_create_director(client_id)
    await send_agent_update(websocket, "Character Agent", "working", "正在添加角色", 30)

    character_data = message.get("character_data", {})
    project_id = character_data.get("project_id")
    world_id = character_data.get("world_id", director.world_id)

    # 生成角色 ID（确保是有效 UUID）
    character_id = character_data.get("id") or str(uuid.uuid4())

    # 创建角色对象
    character = Character(
        id=character_id,
        name=character_data.get("name", "新角色"),
        description=character_data.get("description"),
        role=character_data.get("role", "supporting"),
        status=CharacterStatus.ACTIVE,
        appearance=character_data.get("appearance"),
        background_story=character_data.get("background_story"),
        speech_pattern=character_data.get("speech_pattern"),
        goals=character_data.get("goals", []),
        current_location=character_data.get("current_location"),
        world_id=world_id,
        project_id=project_id,
        personality_traits=character_data.get("personality_traits", []),
        skills=character_data.get("skills", []),
    )

    # 保存到数据库
    if postgres_db:
        await postgres_db.save_character(character.model_dump(mode="json"))

    # 添加到 Director 系统
    director.add_character(character.model_dump(mode="json"))

    await send_agent_update(websocket, "Character Agent", "completed", "角色添加完成", 100)

    await websocket.send_json({
        "type": "character_added",
        "status": "success",
        "data": {
            "character_id": character_id,
            "name": character.name,
            "role": character.role,
        },
    })
    await send_log(websocket, f"角色 '{character.name}' 已添加")


async def handle_remove_character(websocket: WebSocket, message: dict, client_id: str):
    """
    移除角色

    消息格式:
    {
        "type": "remove_character",
        "character_id": "角色ID"
    }
    """
    from app.api.app import postgres_db

    director = get_or_create_director(client_id)
    await send_agent_update(websocket, "Character Agent", "working", "正在移除角色", 30)

    character_id = message.get("character_id")
    if not character_id:
        await send_error(websocket, "缺少 character_id")
        return

    # 从数据库删除
    if postgres_db:
        await postgres_db.delete_character(character_id)

    # 从 Director 系统移除
    director.remove_character(character_id)

    await send_agent_update(websocket, "Character Agent", "completed", "角色移除完成", 100)

    await websocket.send_json({
        "type": "character_removed",
        "status": "success",
        "data": {"character_id": character_id},
    })
    await send_log(websocket, f"角色 {character_id} 已移除")


async def handle_get_characters(websocket: WebSocket, message: dict, client_id: str):
    """
    获取角色列表

    消息格式:
    {
        "type": "get_characters",
        "project_id": "项目ID"  // 可选
    }
    """
    from app.api.app import postgres_db

    director = get_or_create_director(client_id)

    project_id = message.get("project_id")

    # 从数据库获取角色
    if postgres_db and project_id:
        characters = await postgres_db.get_characters(project_id=project_id)
    else:
        characters = director.get_all_characters()

    await websocket.send_json({
        "type": "characters_list",
        "status": "success",
        "data": {"characters": characters, "count": len(characters)},
    })


WRITABLE_OUTLINE_STATUSES = {"draft", "approved", "revision"}


def _outline_value(outline: Any, key: str, default: Any = None) -> Any:
    if isinstance(outline, dict):
        return outline.get(key, default)
    return getattr(outline, key, default)


def _outline_status_value(outline: Any) -> str:
    status = _outline_value(outline, "status", "")
    return getattr(status, "value", status) or ""


def _outline_to_payload(outline: Any) -> Dict[str, Any]:
    if isinstance(outline, dict):
        return outline
    if hasattr(outline, "model_dump"):
        return outline.model_dump(mode="json")
    return dict(outline)


def _outline_goal(outline: Any, fallback: str = "推进剧情") -> str:
    summary = (_outline_value(outline, "summary", "") or "").strip()
    if summary:
        return summary

    goals = _outline_value(outline, "chapter_goals", []) or []
    if goals:
        return "\n".join(str(goal).strip() for goal in goals if str(goal).strip()) or fallback

    return fallback


async def _resolve_message_outline(message: dict, project_id: Optional[str]) -> Any:
    chapter_num = message.get("chapter_num") or message.get("chapter_number")
    outline_id = message.get("chapter_outline_id") or message.get("outline_id")

    if not project_id or (not chapter_num and not outline_id):
        return None

    from app.services.plot_outline_service import get_plot_outline_service

    plot_service = get_plot_outline_service()
    outline = None

    if chapter_num:
        outline = await plot_service.get_outline(str(project_id), int(chapter_num))

    if not outline and outline_id:
        outlines = await plot_service.get_outlines_by_project(str(project_id))
        outline = next(
            (item for item in outlines if str(_outline_value(item, "id")) == str(outline_id)),
            None,
        )

    return outline


def _validate_selected_outline(outline: Any, project_id: Optional[str]) -> Optional[str]:
    if not outline:
        return "未找到选中的章节大纲"

    if project_id and str(_outline_value(outline, "project_id")) != str(project_id):
        return "章节大纲不属于当前项目"

    status = _outline_status_value(outline)
    if status not in WRITABLE_OUTLINE_STATUSES:
        if status == "in_writing":
            return "该章节大纲正在写作中，不能重复启动"
        if status == "completed":
            return "该章节大纲已完成，不能重复生成"
        return f"该章节大纲状态不可写: {status}"

    return None


async def handle_auto_write_chapter(websocket: WebSocket, message: dict, client_id: str):
    """
    自动写作完整章节 - 支持基于工作流执行

    消息格式:
    {
        "type": "auto_write_chapter",
        "workflow_id": "工作流ID",  // 可选，如提供则执行工作流
        "chapter_title": "章节标题",
        "chapter_goal": "章节目标/大纲",
        "target_word_count": 2000,  // 可选，默认2000
        "style_reference": "风格参考文本"  // 可选
    }
    """
    from app.api.app import postgres_db

    director = get_or_create_director(client_id)

    # 检查导演系统是否已初始化
    if not director.writer:
        await websocket.send_json({
            "type": "error",
            "status": "error",
            "message": "导演系统未初始化，请先启动会话",
        })
        return

    workflow_id = message.get("workflow_id")
    project_id = message.get("project_id") or director.project_id
    selected_outline = await _resolve_message_outline(message, project_id)
    outline_error = _validate_selected_outline(selected_outline, project_id) if selected_outline else None
    if outline_error:
        await websocket.send_json({
            "type": "auto_write_chapter_result",
            "status": "error",
            "error": outline_error,
        })
        return

    if selected_outline:
        chapter_num = int(_outline_value(selected_outline, "chapter_number", 1))
        chapter_title = _outline_value(selected_outline, "title", "未命名章节")
        chapter_goal = _outline_goal(selected_outline)
        target_word_count = message.get("target_word_count") or _outline_value(selected_outline, "target_word_count", 2000) or 2000
        chapter_outline_id = _outline_value(selected_outline, "id")
        chapter_outline_payload = _outline_to_payload(selected_outline)
    else:
        chapter_num = int(message.get("chapter_num") or message.get("chapter_number") or 1)
        chapter_title = message.get("chapter_title", "未命名章节")
        chapter_goal = message.get("chapter_goal", "推进剧情")
        target_word_count = message.get("target_word_count", 2000)
        chapter_outline_id = None
        chapter_outline_payload = None

    style_reference = message.get("style_reference")

    await send_agent_update(websocket, "Writer", "working", f"正在自动写作章节: {chapter_title}", 20)
    await send_log(websocket, f"开始自动写作章节: 第 {chapter_num} 章《{chapter_title}》")
    await send_log(websocket, f"章节目标: {chapter_goal}")
    await send_log(websocket, f"目标字数: {target_word_count}")

    try:
        # 如果提供了工作流ID，使用工作流执行
        if workflow_id:
            from app.services.workflow_engine import get_workflow_engine

            await send_log(websocket, f"📋 使用工作流: {workflow_id}")

            engine = get_workflow_engine()
            workflow = await engine.get_workflow(workflow_id, postgres_db)

            if not workflow:
                await websocket.send_json({
                    "type": "auto_write_chapter_result",
                    "status": "error",
                    "error": f"工作流不存在: {workflow_id}",
                })
                return

            # 设置工作流执行上下文
            initial_context = {
                "chapter_num": chapter_num,
                "chapter_title": chapter_title,
                "chapter_goal": chapter_goal,
                "target_word_count": target_word_count,
                "style_reference": style_reference,
            }
            if chapter_outline_payload:
                initial_context.update({
                    "chapter_summary": chapter_outline_payload.get("summary", ""),
                    "chapter_outline_id": chapter_outline_id,
                    "chapter_outline": chapter_outline_payload,
                })

            # 执行工作流
            # 获取有效的 project_id
            if not project_id:
                await send_agent_update(websocket, "Writer", "error", "无法获取项目ID，请确保会话已正确初始化", 0)
                await websocket.send_json({
                    "type": "auto_write_chapter_result",
                    "status": "error",
                    "error": "无法获取项目ID，请确保会话已正确初始化",
                })
                return

            execution_id = await engine.execute_workflow(
                workflow_id,
                project_id,
                initial_context,
                postgres_db,
            )
            manager.set_execution(client_id, execution_id)

            await websocket.send_json({
                "type": "auto_write_chapter_started",
                "status": "success",
                "data": {
                    "execution_id": execution_id,
                    "workflow_id": workflow_id,
                    "chapter_num": chapter_num,
                    "chapter_outline_id": chapter_outline_id,
                    "title": chapter_title,
                    "goal": chapter_goal,
                },
            })
            await send_log(websocket, "🚀 工作流已启动，等待执行结果...")
            return

        else:
            # 无工作流，使用原有方式
            result = await director.auto_write_chapter(
                chapter_title=chapter_title,
                chapter_goal=chapter_goal,
                target_word_count=target_word_count,
                style_reference=style_reference,
            )

            if result.get("success"):
                # 保存到数据库
                await _persist_runtime_state(director)

                # 创建快照
                snapshot = await _create_auto_snapshot(director, snapshot_type="auto", created_by="auto_write")

                await send_agent_update(websocket, "Writer", "completed", f"章节写作完成: {result.get('word_count', 0)} 字", 100)
                await send_log(websocket, f"章节写作完成，实际字数: {result.get('word_count', 0)}")

                await websocket.send_json({
                    "type": "auto_write_chapter_result",
                    "status": "success",
                    "data": {
                        "chapter_id": result.get("chapter_id"),
                        "chapter_num": chapter_num,
                        "chapter_outline_id": chapter_outline_id,
                        "title": result.get("title"),
                        "content": result.get("content"),
                        "word_count": result.get("word_count"),
                        "goal": result.get("goal"),
                        "snapshot_id": snapshot.get("id") if snapshot else None,
                    },
                })
            else:
                await send_agent_update(websocket, "Writer", "error", f"写作失败: {result.get('error')}", 0)
                await websocket.send_json({
                    "type": "auto_write_chapter_result",
                    "status": "error",
                    "error": result.get("error"),
                })

    except Exception as e:
        logger.error(f"自动写作章节失败: {e}")
        await send_agent_update(websocket, "Writer", "error", f"写作异常: {str(e)}", 0)
        await websocket.send_json({
            "type": "auto_write_chapter_result",
            "status": "error",
            "error": str(e),
        })


async def handle_start_auto_mode(websocket: WebSocket, message: dict, client_id: str):
    """
    启动连续创作模式 - 基于选中工作流循环执行

    消息格式:
    {
        "type": "start_auto_mode",
        "workflow_id": "工作流ID",  // 必填
        "chapter_count": 3,  // 可选，默认3
        "words_per_chapter": 2000,  // 可选，默认2000
        "style_reference": "风格参考文本"  // 可选
    }
    """
    director = get_or_create_director(client_id)

    # 检查导演系统是否已初始化
    if not director.writer:
        await websocket.send_json({
            "type": "error",
            "status": "error",
            "message": "导演系统未初始化，请先启动会话",
        })
        return

    # 检查是否选择了工作流
    workflow_id = message.get("workflow_id")
    if not workflow_id:
        await websocket.send_json({
            "type": "error",
            "status": "error",
            "message": "请先选择工作流",
            "hint": "在「自定义工作流」区域选择一个工作流后再开始连续创作",
        })
        return

    chapter_count = message.get("chapter_count", 3)
    words_per_chapter = message.get("words_per_chapter", 2000)
    style_reference = message.get("style_reference")
    project_id = message.get("project_id") or director.project_id
    outline_mode = message.get("outline_mode")
    outline_ids = message.get("outline_ids") or []
    outline_chapter_numbers = message.get("outline_chapter_numbers") or []
    auto_advance_outlines = bool(message.get("auto_advance_outlines"))
    start_chapter_num = message.get("start_chapter_num")

    await send_log(websocket, "🚀 启动连续创作模式")
    await send_log(websocket, f"📋 使用工作流: {workflow_id}")
    if outline_mode == "selected":
        await send_log(websocket, f"📚 将按已选 {len(outline_ids) or len(outline_chapter_numbers)} 个大纲生成章节")
    elif outline_mode == "auto_progression":
        await send_log(websocket, f"📚 将从第 {start_chapter_num} 章起自动推进最多 {chapter_count} 个已有大纲")
    else:
        await send_log(websocket, f"📚 计划生成 {chapter_count} 个章节，每章约 {words_per_chapter} 字")

    # 定义回调函数，用于发送进度更新
    async def callback(event_type: str, data: dict):
        if event_type == "phase":
            await send_log(websocket, f"📋 {data.get('message', '')}")
        elif event_type == "plot_planned":
            await send_log(websocket, "✅ 剧情规划完成")
            await send_agent_update(websocket, "Master Plotter", "completed", "剧情规划完成", 20)
        elif event_type == "chapter_start":
            await send_log(websocket, f"📖 开始写作: {data.get('title', '')}")
            await websocket.send_json({
                "type": "auto_mode_chapter_start",
                "chapter_num": data.get("chapter_num"),
                "title": data.get("title"),
                "chapter_outline_id": data.get("chapter_outline_id"),
            })
        elif event_type == "agent_working":
            agent = data.get("agent", "Agent")
            msg = data.get("message", "")
            await send_agent_update(websocket, agent, "working", msg, 50)
            await send_log(websocket, f"🤖 {agent}: {msg}")
        elif event_type == "hooks_managed":
            await send_agent_update(websocket, "Hook Manager", "completed", "伏笔管理完成", 70)
        elif event_type == "chapter_completed":
            await send_agent_update(websocket, "Writer", "completed", f"章节完成: {data.get('word_count', 0)} 字", 90)
            await send_log(websocket, f"✅ 章节 {data.get('chapter_num')} 完成: {data.get('title')} ({data.get('word_count')} 字)")
            # 保存到数据库
            await _persist_runtime_state(director)
            await websocket.send_json({
                "type": "auto_mode_chapter_completed",
                "chapter_num": data.get("chapter_num"),
                "title": data.get("title"),
                "word_count": data.get("word_count"),
                "content": data.get("content"),
                "chapter_outline_id": data.get("chapter_outline_id"),
            })
        elif event_type == "chapter_error":
            await send_log(websocket, f"❌ 章节 {data.get('chapter_num')} 失败: {data.get('error')}")
        elif event_type == "chapter_evaluated":
            await send_agent_update(websocket, "Evaluator", "completed", "章节评估完成", 95)
        elif event_type == "snapshot_created":
            await send_log(websocket, f"📸 快照已创建: {data.get('snapshot_id', '')}")
        elif event_type == "stopped":
            await send_log(websocket, f"⏹️ 自动模式已停止，完成 {data.get('chapters_completed', 0)} 章")
        elif event_type == "completed":
            await send_log(websocket, f"🎉 全自动创作完成！共 {data.get('total_chapters', 0)} 章，{data.get('total_words', 0)} 字")
            await send_log(websocket, f"📊 伏笔埋设: {data.get('hooks_planted', 0)} 个，回收: {data.get('hooks_resolved', 0)} 个")
        elif event_type == "error":
            await send_log(websocket, f"❌ 错误: {data.get('error', '')}")

    try:
        result = await director.start_auto_mode(
            workflow_id=workflow_id,
            chapter_count=chapter_count,
            words_per_chapter=words_per_chapter,
            style_reference=style_reference,
            callback=callback,
            outline_mode=outline_mode,
            outline_ids=outline_ids,
            outline_chapter_numbers=outline_chapter_numbers,
            auto_advance_outlines=auto_advance_outlines,
            start_chapter_num=start_chapter_num,
            project_id=project_id,
        )

        # 重置所有 Agent 状态
        for agent in ["Summarizer", "Master Plotter", "Hook Manager", "Writer", "Evaluator", "Character Agent", "ProcGen"]:
            await send_agent_update(websocket, agent, "completed", f"{agent} 已完成", 100)

        await websocket.send_json({
            "type": "auto_mode_completed",
            "status": "success",
            "data": {
                "chapters": result.get("chapters", []),
                "total_words": result.get("total_words", 0),
                "total_chapters": len(result.get("chapters", [])),
            },
        })

    except Exception as e:
        logger.error(f"自动模式运行失败: {e}")
        await send_log(websocket, f"❌ 自动模式运行失败: {str(e)}")
        await websocket.send_json({
            "type": "auto_mode_error",
            "error": str(e),
        })


async def handle_stop_auto_mode(websocket: WebSocket, message: dict, client_id: str):
    """停止自动运行模式"""
    from app.services.workflow_engine import get_workflow_engine
    from app.api.app import postgres_db

    director = get_or_create_director(client_id)

    # 1. 停止自动模式标志
    director.stop_auto_mode()

    # 2. 取消当前工作流执行
    execution_id = manager.get_execution(client_id)
    if execution_id:
        engine = get_workflow_engine()
        success = await engine.cancel_workflow(execution_id, postgres_db)
        if success:
            await send_log(websocket, f"✅ 工作流已取消: {execution_id}")
            await engine.clear_interventions(execution_id)
        manager.clear_execution(client_id)

    await send_log(websocket, "⏹️ 自动模式已停止")


# ==================== v8 工作流 WebSocket 处理器 ====================

async def handle_workflow_start(websocket: WebSocket, message: dict, client_id: str):
    """
    启动工作流

    消息格式:
    {
        "type": "workflow_start",
        "workflow_id": "工作流定义ID",
        "project_id": "项目ID",
        "initial_context": {}  // 可选
    }
    """
    from app.services.workflow_engine import get_workflow_engine
    from app.api.app import postgres_db

    workflow_id = message.get("workflow_id")
    project_id = message.get("project_id")
    initial_context = message.get("initial_context", {})

    if not workflow_id or not project_id:
        await send_error(websocket, "缺少 workflow_id 或 project_id")
        return

    await send_log(websocket, f"🚀 正在启动工作流: {workflow_id}")

    try:
        engine = get_workflow_engine()
        execution_id = await engine.execute_workflow(
            workflow_id=workflow_id,
            project_id=project_id,
            initial_context=initial_context,
            db=postgres_db,
        )

        # 保存当前执行ID到客户端映射
        manager.set_execution(client_id, execution_id)

        await websocket.send_json({
            "type": "workflow_started",
            "status": "success",
            "data": {
                "execution_id": execution_id,
                "workflow_id": workflow_id,
                "project_id": project_id,
            },
        })

        # 启动状态广播任务
        asyncio.create_task(_broadcast_workflow_status(websocket, execution_id, client_id))

    except ValueError as e:
        await send_error(websocket, f"工作流启动失败: {str(e)}")
    except Exception as e:
        logger.error(f"启动工作流失败: {e}")
        await send_error(websocket, f"启动工作流异常: {str(e)}")


async def handle_workflow_pause(websocket: WebSocket, message: dict, client_id: str):
    """
    暂停工作流

    消息格式:
    {
        "type": "workflow_pause",
        "execution_id": "执行ID"
    }
    """
    from app.services.workflow_engine import get_workflow_engine
    from app.api.app import postgres_db

    execution_id = message.get("execution_id")
    if not execution_id:
        await send_error(websocket, "缺少 execution_id")
        return

    await send_log(websocket, f"⏸️ 正在暂停工作流: {execution_id}")

    try:
        engine = get_workflow_engine()
        success = await engine.pause_workflow(execution_id, postgres_db)

        if success:
            await websocket.send_json({
                "type": "workflow_paused",
                "status": "success",
                "data": {"execution_id": execution_id},
            })
            await send_log(websocket, "✅ 工作流已暂停")
        else:
            await send_error(websocket, "无法暂停工作流（可能不在运行状态）")

    except Exception as e:
        logger.error(f"暂停工作流失败: {e}")
        await send_error(websocket, f"暂停工作流异常: {str(e)}")


async def handle_workflow_resume(websocket: WebSocket, message: dict, client_id: str):
    """
    恢复工作流

    消息格式:
    {
        "type": "workflow_resume",
        "execution_id": "执行ID"
    }
    """
    from app.services.workflow_engine import get_workflow_engine
    from app.api.app import postgres_db

    execution_id = message.get("execution_id")
    if not execution_id:
        await send_error(websocket, "缺少 execution_id")
        return

    await send_log(websocket, f"▶️ 正在恢复工作流: {execution_id}")

    try:
        engine = get_workflow_engine()
        success = await engine.resume_workflow(execution_id, postgres_db)

        if success:
            await websocket.send_json({
                "type": "workflow_resumed",
                "status": "success",
                "data": {"execution_id": execution_id},
            })
            await send_log(websocket, "✅ 工作流已恢复")
            # 恢复状态广播
            asyncio.create_task(_broadcast_workflow_status(websocket, execution_id, client_id))
        else:
            await send_error(websocket, "无法恢复工作流（可能不在暂停状态）")

    except Exception as e:
        logger.error(f"恢复工作流失败: {e}")
        await send_error(websocket, f"恢复工作流异常: {str(e)}")


async def handle_workflow_step(websocket: WebSocket, message: dict, client_id: str):
    """
    单步执行工作流

    消息格式:
    {
        "type": "workflow_step",
        "execution_id": "执行ID"
    }
    """
    from app.services.workflow_engine import get_workflow_engine
    from app.api.app import postgres_db

    execution_id = message.get("execution_id")
    if not execution_id:
        await send_error(websocket, "缺少 execution_id")
        return

    await send_log(websocket, f"⏭️ 正在执行单步: {execution_id}")

    try:
        engine = get_workflow_engine()
        result = await engine.step_workflow(execution_id, postgres_db)

        if result:
            await websocket.send_json({
                "type": "workflow_step_completed",
                "status": "success",
                "data": result,
            })
        else:
            await websocket.send_json({
                "type": "workflow_step_completed",
                "status": "completed",
                "data": {"message": "工作流已完成"},
            })

    except Exception as e:
        logger.error(f"单步执行失败: {e}")
        await send_error(websocket, f"单步执行异常: {str(e)}")


async def handle_workflow_user_input(websocket: WebSocket, message: dict, client_id: str):
    """提交工作流用户输入节点的内容并继续执行。"""
    from app.services.workflow_engine import get_workflow_engine
    from app.api.app import postgres_db

    execution_id = message.get("execution_id") or manager.get_execution(client_id)
    node_id = message.get("node_id")
    value = message.get("value")

    if not execution_id:
        await send_error(websocket, "缺少 execution_id")
        return
    if not node_id:
        await send_error(websocket, "缺少 node_id")
        return

    await send_log(websocket, "📨 正在提交用户输入并恢复工作流...")

    try:
        engine = get_workflow_engine()
        execution = await engine.get_execution_state(execution_id, postgres_db)
        if execution:
            director = get_or_create_director(client_id, project_id=execution.project_id)
            setup_workflow_engine_callbacks(director)

        result = await engine.submit_user_input(
            execution_id=execution_id,
            node_id=node_id,
            value=value,
            db=postgres_db,
            user_id=client_id,
        )

        if not result.get("success"):
            await send_error(websocket, result.get("error", "提交用户输入失败"))
            return

        await websocket.send_json({
            "type": "workflow_user_input_received",
            "status": "success",
            "data": result,
        })
        await send_log(websocket, "✅ 用户输入已提交，工作流继续执行")
    except Exception as e:
        logger.error(f"提交工作流用户输入失败: {e}")
        await send_error(websocket, f"提交用户输入异常: {str(e)}")

async def handle_workflow_status(websocket: WebSocket, message: dict, client_id: str):
    """
    获取工作流状态

    消息格式:
    {
        "type": "workflow_status",
        "execution_id": "执行ID"
    }
    """
    from app.services.workflow_engine import get_workflow_engine
    from app.api.app import postgres_db

    execution_id = message.get("execution_id")
    if not execution_id:
        await send_error(websocket, "缺少 execution_id")
        return

    try:
        engine = get_workflow_engine()
        execution = await engine.get_execution_state(execution_id, postgres_db)

        if execution:
            await websocket.send_json({
                "type": "workflow_status_response",
                "status": "success",
                "data": engine._serialize_for_json(execution),
            })
        else:
            await send_error(websocket, "执行记录不存在")

    except Exception as e:
        logger.error(f"获取工作流状态失败: {e}")
        await send_error(websocket, f"获取状态异常: {str(e)}")


async def handle_agent_message(websocket: WebSocket, message: dict, client_id: str):
    """
    向特定 Agent 发送消息（私聊干预）

    消息格式:
    {
        "type": "agent_message",
        "execution_id": "执行ID",
        "agent_type": "setting|writer|plotter|...",
        "message": "消息内容"
    }
    """
    from app.services.agent_communication import get_agent_communication_service
    from app.services.intervention_service import get_intervention_service
    from app.api.app import postgres_db

    execution_id = message.get("execution_id")
    agent_type = message.get("agent_type")
    msg_content = message.get("message")

    if not all([execution_id, agent_type, msg_content]):
        await send_error(websocket, "缺少必要参数: execution_id, agent_type, message")
        return

    await send_log(websocket, f"💬 向 Agent [{agent_type}] 发送消息")

    try:
        comm_service = get_agent_communication_service()
        int_service = get_intervention_service()

        # 设置干预服务引用
        comm_service.set_intervention_service(int_service)

        result = await comm_service.send_agent_message(
            execution_id=execution_id,
            agent_type=agent_type,
            message=msg_content,
            db=postgres_db,
        )

        await websocket.send_json({
            "type": "agent_response",
            "status": "success" if result.get("success") else "error",
            "data": {
                "agent_type": agent_type,
                "agent_name": result.get("agent_name"),
                "response": result.get("response"),
                "response_time_ms": result.get("response_time_ms"),
                "intervention_id": result.get("intervention_id"),
            },
        })

        # 同时发送干预记录通知
        if result.get("intervention_id"):
            await websocket.send_json({
                "type": "intervention_logged",
                "data": {
                    "intervention_id": result.get("intervention_id"),
                    "agent_type": agent_type,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            })

    except Exception as e:
        logger.error(f"发送 Agent 消息失败: {e}")
        await send_error(websocket, f"发送消息异常: {str(e)}")


async def handle_intervention_request(websocket: WebSocket, message: dict, client_id: str):
    """
    干预请求（更详细的干预操作）

    消息格式:
    {
        "type": "intervention_request",
        "execution_id": "执行ID",
        "agent_type": "目标Agent类型",
        "message": "干预消息",
        "node_id": "节点ID",  // 可选
        "project_id": "项目ID"  // 可选
    }
    """
    from app.services.agent_communication import get_agent_communication_service
    from app.services.intervention_service import get_intervention_service
    from app.api.app import postgres_db

    execution_id = message.get("execution_id")
    agent_type = message.get("agent_type")
    msg_content = message.get("message")
    node_id = message.get("node_id")
    project_id = message.get("project_id")

    if not all([execution_id, agent_type, msg_content]):
        await send_error(websocket, "缺少必要参数: execution_id, agent_type, message")
        return

    await send_log(websocket, f"🔔 发起干预请求 -> {agent_type}")

    try:
        comm_service = get_agent_communication_service()
        int_service = get_intervention_service()
        comm_service.set_intervention_service(int_service)

        result = await comm_service.send_agent_message(
            execution_id=execution_id,
            agent_type=agent_type,
            message=msg_content,
            project_id=project_id,
            node_id=node_id,
            db=postgres_db,
        )

        await websocket.send_json({
            "type": "intervention_response",
            "status": "success" if result.get("success") else "error",
            "data": {
                "intervention_id": result.get("intervention_id"),
                "agent_type": agent_type,
                "agent_name": result.get("agent_name"),
                "response": result.get("response"),
                "response_time_ms": result.get("response_time_ms"),
            },
        })

        # 广播节点状态更新
        if node_id:
            await websocket.send_json({
                "type": "node_status_update",
                "data": {
                    "node_id": node_id,
                    "status": "intervened",
                    "agent_type": agent_type,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            })

    except Exception as e:
        logger.error(f"干预请求失败: {e}")
        await send_error(websocket, f"干预请求异常: {str(e)}")


async def handle_discussion_message(websocket: WebSocket, message: dict, client_id: str):
    """
    处理讨论消息（用户参与集体讨论）

    消息格式:
    {
        "type": "discussion_message",
        "message": "消息内容",
        "timestamp": "时间戳"
    }
    """
    msg_content = message.get("message", "")
    timestamp = message.get("timestamp", datetime.now().isoformat())

    if not msg_content:
        await send_error(websocket, "消息内容不能为空")
        return

    logger.info(f"用户参与讨论: {msg_content}")

    # 广播用户消息给所有监听者
    await websocket.send_json({
        "type": "discussion_message",
        "data": {
            "character": "你",
            "content": msg_content,
            "timestamp": timestamp,
        },
    })

    # 获取 Director 实例，让 Agent 们回应用户
    director = get_or_create_director(client_id)

    if director:
        # 让角色 Agent 们回应用户的讨论
        try:
            # 模拟角色回应
            responses = [
                f"【角色A】回应：关于这个问题，我同意你的看法...",
                f"【角色B】补充：不过从另一个角度来看...",
                f"【角色C】总结：综合大家的意见，我认为...",
            ]

            for i, response in enumerate(responses):
                await asyncio.sleep(0.5)  # 模拟思考时间
                await websocket.send_json({
                    "type": "discussion_message",
                    "data": {
                        "character": response.split("】")[0].replace("【", ""),
                        "content": response.split("】")[1] if "】" in response else response,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                    },
                })

            # 讨论结束广播
            await websocket.send_json({
                "type": "discussion_ended",
                "data": {
                    "summary": "讨论已完成，各角色达成共识",
                },
            })

        except Exception as e:
            logger.error(f"Agent 回应讨论失败: {e}")


async def handle_end_discussion(websocket: WebSocket, message: dict, client_id: str):
    """
    结束集体讨论

    消息格式:
    {
        "type": "end_discussion"
    }
    """
    logger.info(f"结束集体讨论")

    await websocket.send_json({
        "type": "discussion_ended",
        "data": {
            "summary": "讨论已结束",
            "timestamp": datetime.now().isoformat(),
        },
    })


async def handle_discussion_confirm(websocket: WebSocket, message: dict, client_id: str):
    """
    处理用户确认/拒绝讨论结果

    消息格式:
    {
        "type": "discussion_confirm",
        "approved": true/false,
        "feedback": "反馈意见（拒绝时必填）"
    }

    流程：
    1. 领头人广播结束消息
    2. 同意 -> 工作流继续
    3. 拒绝 -> 带反馈重启工作流
    """
    from app.services.workflow_engine import get_workflow_engine
    from app.api.app import postgres_db

    approved = message.get("approved", True)
    feedback = message.get("feedback", "")

    logger.info(f"用户确认讨论: approved={approved}, feedback={feedback[:50] if feedback else 'None'}...")

    engine = get_workflow_engine()
    execution_id = manager.get_execution(client_id)

    if not execution_id:
        await send_error(websocket, "没有活跃的工作流执行")
        return

    # 调用引擎的确认方法
    result = await engine.confirm_discussion(
        execution_id=execution_id,
        approved=approved,
        feedback=feedback if not approved else None,
        db=postgres_db,
    )

    if result.get("success"):
        await websocket.send_json({
            "type": "discussion_confirmed",
            "data": {
                "approved": approved,
                "message": result.get("message", "确认成功"),
                "retry_count": result.get("retry_count", 0),
            },
        })
    else:
        await send_error(websocket, result.get("error", "确认失败"))


async def _broadcast_workflow_status(websocket: WebSocket, execution_id: str, client_id: str):
    """
    定期广播工作流状态

    Args:
        websocket: WebSocket 连接
        execution_id: 执行ID
        client_id: 客户端ID
    """
    from app.services.workflow_engine import get_workflow_engine
    from app.api.app import postgres_db
    from app.models.workflow_execution import WorkflowStatus

    engine = get_workflow_engine()
    interval = 1.0  # 每秒广播一次

    try:
        while True:
            execution = await engine.get_execution_state(execution_id, postgres_db)
            if not execution:
                break

            # 广播当前节点状态
            if execution.current_node:
                await websocket.send_json({
                    "type": "node_status_update",
                    "data": {
                        "execution_id": execution_id,
                        "current_node": execution.current_node,
                        "status": execution.status,
                        "node_states": {
                            node_id: state.model_dump()
                            for node_id, state in execution.node_states.items()
                        },
                    },
                })

            # 如果工作流结束，停止广播
            if execution.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED]:
                # 清除客户端的执行ID映射
                manager.clear_execution(client_id)
                # 清除干预队列
                await engine.clear_interventions(execution_id)

                await websocket.send_json({
                    "type": "workflow_completed",
                    "data": {
                        "execution_id": execution_id,
                        "status": execution.status,
                        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                        "total_duration_ms": execution.total_duration_ms,
                        "error": execution.error,
                    },
                })
                break

            await asyncio.sleep(interval)

    except WebSocketDisconnect:
        logger.info(f"客户端 {client_id} 断开连接，停止状态广播")
    except Exception as e:
        logger.error(f"状态广播异常: {e}")


async def send_error(websocket: WebSocket, error_message: str):
    await websocket.send_json({"type": "error", "message": error_message})


@router.get("/connections")
async def get_connections():
    return {
        "active_connections": len(manager.active_connections),
        "clients": list(manager.client_data.values()),
        "director_sessions": list(manager.director_sessions.keys()),
    }
