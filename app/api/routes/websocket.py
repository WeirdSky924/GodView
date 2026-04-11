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
from app.services.director import DirectorSystem
from app.services.model_router import create_model_factory
from app.services.workflow import DirectorWorkflow

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
            self.director_sessions.pop(client_id, None)
            self.client_executions.pop(client_id, None)
        logger.info("客户端断开连接")

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
    async def agent_provider(agent_type: str, project_id: str):
        """
        获取 Agent 实例

        Args:
            agent_type: Agent 类型
            project_id: 项目 ID

        Returns:
            Agent 实例或 None
        """
        from app.models.character import CharacterPresence

        # 系统内置 Agent（支持多种命名方式）
        system_agents = {
            "summarizer": director.summarizer,
            "master_plotter": director.master_plotter,
            "plotter": director.master_plotter,  # 别名
            "hook_manager": director.hook_manager,
            "writer": director.writer,
            "evaluator": director.evaluator,
            "procgen": director.procgen,
            "world_map_manager": director.procgen,  # 地图管理复用 ProcGen
            "event_generator": director.procgen,    # 事件生成复用 ProcGen
            "setting": director.summarizer,         # 设定复用 Summarizer
        }

        # 检查是否是系统 Agent
        agent_type_lower = agent_type.lower().replace(" ", "_").replace("-", "_")
        if agent_type_lower in system_agents:
            return system_agents[agent_type_lower]
        if agent_type in system_agents:
            return system_agents[agent_type]

        # 检查是否是批量角色获取（格式：characters:presence_type）
        if agent_type.startswith("characters:"):
            presence_type = agent_type.split(":", 1)[1]
            agents = director.get_character_by_presence(presence_type)
            if agents:
                # 返回角色列表（供工作流处理多角色场景）
                return agents
            logger.warning(f"未找到在场形式为 '{presence_type}' 的角色")
            return None

        # 检查是否是带在场形式的角色 Agent（格式：character:角色ID:presence_type）
        if agent_type.startswith("character:"):
            parts = agent_type.split(":")
            char_id = parts[1]

            # 获取角色 Agent
            char_agent = director.get_character_agent(char_id)
            if not char_agent:
                logger.warning(f"角色 {char_id} 不存在")
                return None

            # 如果指定了在场形式，验证角色是否支持
            if len(parts) > 2:
                presence_type = parts[2]
                try:
                    presence = CharacterPresence(presence_type)
                    if presence not in char_agent.character.available_presence_types:
                        logger.warning(f"角色 {char_id} 不支持在场形式 '{presence_type}'，可用: {[p.value for p in char_agent.character.available_presence_types]}")
                        # 仍然返回，但会在执行上下文中标记
                        return char_agent
                except ValueError:
                    logger.warning(f"未知的在场形式: {presence_type}")

            return char_agent

        # 尝试作为角色 ID 直接查找
        char_agent = director.get_character_agent(agent_type)
        if char_agent:
            return char_agent

        # 检查是否是角色类型（如 "CharacterAgent"）
        if agent_type.lower() in ["character", "characteragent"]:
            # 返回所有活跃角色的代理（用于集体讨论等场景）
            active_chars = director.get_active_character_agents()
            if active_chars:
                return list(active_chars.values())[0]

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
        if execution and execution.get("status") in ["running", "paused"]:
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
    director = get_or_create_director(client_id)
    await _persist_runtime_state(director)
    await _create_auto_snapshot(director, snapshot_type="manual", created_by="system")
    for agent in ["Summarizer", "Master Plotter", "Hook Manager", "Writer", "Evaluator", "Character Agent", "ProcGen"]:
        await send_agent_update(websocket, agent, "idle", f"{agent} 已停止", 0)
    await websocket.send_json({"type": "session_stopped", "status": "success"})
    await send_log(websocket, "导演会话已停止")


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
    chapter_title = message.get("chapter_title", "未命名章节")
    chapter_goal = message.get("chapter_goal", "推进剧情")
    target_word_count = message.get("target_word_count", 2000)
    style_reference = message.get("style_reference")

    await send_agent_update(websocket, "Writer", "working", f"正在自动写作章节: {chapter_title}", 20)
    await send_log(websocket, f"开始自动写作章节: {chapter_title}")
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
                "chapter_num": 1,
                "chapter_title": chapter_title,
                "chapter_goal": chapter_goal,
                "target_word_count": target_word_count,
                "style_reference": style_reference,
            }

            # 执行工作流
            # 获取有效的 project_id
            project_id = director.project_id
            if not project_id:
                # 尝试从当前项目上下文获取
                project_id = message.get("project_id")
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

            # 等待工作流完成
            import asyncio
            max_wait = 300  # 最多等待5分钟
            waited = 0
            execution = None

            while waited < max_wait:
                execution = await engine.get_execution_state(execution_id, postgres_db)
                if execution and execution.status in ["completed", "failed", "cancelled"]:
                    break
                await asyncio.sleep(1)
                waited += 1

            if execution and execution.status == "completed":
                # 获取工作流输出
                chapter_content = execution.context.get("chapter_content", "")
                word_count = len(chapter_content) if chapter_content else 0

                # 保存到数据库
                await _persist_runtime_state(director)

                # 创建快照
                snapshot = await _create_auto_snapshot(director, snapshot_type="auto", created_by="auto_write")

                await send_agent_update(websocket, "Writer", "completed", f"章节写作完成: {word_count} 字", 100)
                await send_log(websocket, f"章节写作完成，实际字数: {word_count}")

                await websocket.send_json({
                    "type": "auto_write_chapter_result",
                    "status": "success",
                    "data": {
                        "chapter_id": execution.context.get("chapter_id"),
                        "title": chapter_title,
                        "content": chapter_content,
                        "word_count": word_count,
                        "goal": chapter_goal,
                        "snapshot_id": snapshot.get("id") if snapshot else None,
                    },
                })
            else:
                error_msg = execution.error if execution else "工作流执行超时"
                await send_agent_update(websocket, "Writer", "error", f"工作流执行失败: {error_msg}", 0)
                await websocket.send_json({
                    "type": "auto_write_chapter_result",
                    "status": "error",
                    "error": error_msg,
                })

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

    await send_log(websocket, "🚀 启动连续创作模式")
    await send_log(websocket, f"📋 使用工作流: {workflow_id}")
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
                "goal": data.get("goal"),
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
    director = get_or_create_director(client_id)
    director.stop_auto_mode()
    await send_log(websocket, "⏹️ 正在停止自动模式...")


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
                "data": execution.model_dump(),
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
    from app.services.director import get_director
    director = get_director(client_id)

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
