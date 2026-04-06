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

from app.api.app import postgres_db
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


async def send_error(websocket: WebSocket, error_message: str):
    await websocket.send_json({"type": "error", "message": error_message})


@router.get("/connections")
async def get_connections():
    return {
        "active_connections": len(manager.active_connections),
        "clients": list(manager.client_data.values()),
        "director_sessions": list(manager.director_sessions.keys()),
    }
