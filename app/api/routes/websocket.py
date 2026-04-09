"""
WebSocket 路由 - 实时交互接口
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Set

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
        logger.info("客户端断开连接")


manager = ConnectionManager()


async def send_log(websocket: WebSocket, message: str, level: str = "info"):
    await websocket.send_json({"type": "log", "level": level, "message": message})


async def send_agent_update(websocket: WebSocket, agent: str, status: str, message: str, progress: int | None = None):
    payload = {"type": "agent_status", "agent": agent, "status": status, "message": message}
    if progress is not None:
        payload["progress"] = progress
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


def get_or_create_director(client_id: str) -> DirectorSystem:
    director = manager.director_sessions.get(client_id)
    if director:
        return director
    director = DirectorSystem(
        world_data={"id": f"world_{client_id}", "name": "Default World", "regions": [], "relationships": {}},
        config={
            "max_turns_threshold": settings.max_turns_threshold,
            "target_word_count_per_intent": settings.target_word_count_per_intent,
        },
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
                elif message_type == "advance_plot":
                    await handle_advance_plot(websocket, message, client_id)
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
    director = get_or_create_director(client_id)
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

    for idx, agent in enumerate(["Summarizer", "Master Plotter", "Hook Manager", "Writer", "Evaluator", "Character Agent", "ProcGen"], start=1):
        await send_agent_update(websocket, agent, "completed", f"{agent} 已就绪", min(idx * 14, 100))

    await websocket.send_json({
        "type": "session_started",
        "status": "success",
        "data": {
            "session_id": client_id,
            "world_id": director.world_id,
            "snapshot_id": snapshot.get("id") if snapshot else None,
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
    from app.api.app import postgres_db

    director = get_or_create_director(client_id)
    await send_log(websocket, f"正在执行干预：{message.get('intervention_type', 'unknown')}...")
    snapshot = await _create_auto_snapshot(
        director,
        snapshot_type="pre_intervention",
        created_by="user",
        is_branch=True,
        branch_reason=message.get("description") or message.get("intervention_type"),
    )
    intervention_record = await director.create_intervention_record(
        snapshot_id=snapshot.get("id") if snapshot else "",
        intervention_type=message.get("intervention_type", "unknown"),
        description=message.get("description", "手动干预"),
        details=message.get("details", {}),
        affected_hooks=message.get("affected_hooks", []),
        affected_relationships=message.get("affected_relationships", []),
        affected_characters=message.get("affected_characters", []),
    )
    if postgres_db:
        await postgres_db.log_intervention(intervention_record)
    await asyncio.sleep(0.1)
    await websocket.send_json({
        "type": "intervention_result",
        "status": "success",
        "data": {
            "snapshot_id": snapshot.get("id") if snapshot else None,
            "intervention_logged": True,
            "intervention_id": intervention_record.get("id"),
        },
    })


async def handle_advance_plot(websocket: WebSocket, message: dict, client_id: str):
    director = get_or_create_director(client_id)
    await send_agent_update(websocket, "Master Plotter", "working", "正在推进主线剧情", 40)
    result = await director.advance_plot()
    await _persist_runtime_state(director)
    await websocket.send_json({"type": "plot_advanced", "status": "success", "data": result})
    await send_agent_update(websocket, "Master Plotter", "completed", "主线推进完成", 100)


async def handle_manage_hooks(websocket: WebSocket, message: dict, client_id: str):
    director = get_or_create_director(client_id)
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

    # 生成角色 ID
    character_id = character_data.get("id") or f"char_{uuid.uuid4().hex[:12]}"

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
    自动写作完整章节

    消息格式:
    {
        "type": "auto_write_chapter",
        "chapter_title": "章节标题",
        "chapter_goal": "章节目标/大纲",
        "target_word_count": 2000,  // 可选，默认2000
        "style_reference": "风格参考文本"  // 可选
    }
    """
    from app.api.app import postgres_db

    director = get_or_create_director(client_id)

    chapter_title = message.get("chapter_title", "未命名章节")
    chapter_goal = message.get("chapter_goal", "推进剧情")
    target_word_count = message.get("target_word_count", 2000)
    style_reference = message.get("style_reference")

    await send_agent_update(websocket, "Writer", "working", f"正在自动写作章节: {chapter_title}", 20)
    await send_log(websocket, f"开始自动写作章节: {chapter_title}")
    await send_log(websocket, f"章节目标: {chapter_goal}")
    await send_log(websocket, f"目标字数: {target_word_count}")

    try:
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
    启动全自动创作模式

    消息格式:
    {
        "type": "start_auto_mode",
        "initial_plot": "初始剧情设定/大纲",
        "chapter_count": 3,  // 可选，默认3
        "words_per_chapter": 2000,  // 可选，默认2000
        "style_reference": "风格参考文本"  // 可选
    }
    """
    director = get_or_create_director(client_id)

    initial_plot = message.get("initial_plot", "一个精彩的冒险故事")
    chapter_count = message.get("chapter_count", 3)
    words_per_chapter = message.get("words_per_chapter", 2000)
    style_reference = message.get("style_reference")

    await send_log(websocket, "🚀 启动全自动创作模式")
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
        elif event_type == "plot_advanced":
            await send_agent_update(websocket, "Master Plotter", "completed", "剧情推进完成", 60)
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
            initial_plot=initial_plot,
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


async def send_error(websocket: WebSocket, error_message: str):
    await websocket.send_json({"type": "error", "message": error_message})


@router.get("/connections")
async def get_connections():
    return {
        "active_connections": len(manager.active_connections),
        "clients": list(manager.client_data.values()),
        "director_sessions": list(manager.director_sessions.keys()),
    }
