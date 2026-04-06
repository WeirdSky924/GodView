"""
WebSocket 路由 - 实时交互接口
"""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.client_data: Dict[WebSocket, Dict] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """接受连接"""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.client_data[websocket] = {
            "client_id": client_id,
            "connected_at": asyncio.get_event_loop().time(),
        }
        logger.info(f"客户端 {client_id} 已连接")

    def disconnect(self, websocket: WebSocket):
        """断开连接"""
        self.active_connections.discard(websocket)
        self.client_data.pop(websocket, None)
        logger.info("客户端断开连接")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """发送个人消息"""
        await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """广播消息"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/connect/{client_id}")
async def websocket_connect(websocket: WebSocket, client_id: str):
    """
    WebSocket 连接端点

    用于前端与导演系统的实时交互
    """
    await manager.connect(websocket, client_id)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                message_type = message.get("type", "unknown")

                # 处理不同类型的消息
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
                else:
                    await send_error(websocket, f"未知消息类型：{message_type}")

            except json.JSONDecodeError:
                await send_error(websocket, "无效的 JSON 格式")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"客户端 {client_id} 断开连接")


async def handle_start_session(websocket: WebSocket, message: dict, client_id: str):
    """处理开始会话请求"""
    world_id = message.get("world_id")
    character_ids = message.get("character_ids", [])

    # TODO: 加载世界和角色数据
    response = {
        "type": "session_started",
        "status": "success",
        "data": {
            "world_id": world_id,
            "character_ids": character_ids,
            "session_id": f"session_{client_id}_{asyncio.get_event_loop().time()}",
        },
    }

    await websocket.send_json(response)


async def handle_generate_dialogue(websocket: WebSocket, message: dict, client_id: str):
    """
    处理对话生成请求

    预期输入:
    {
        "type": "generate_dialogue",
        "speaker_id": "角色 ID",
        "context": "情境描述",
        "present_characters": ["在场角色 ID 列表"],
        "dialogue_history": [{"speaker": "...", "content": "..."}],
    }
    """
    speaker_id = message.get("speaker_id")
    context = message.get("context", "")
    present_characters = message.get("present_characters", [])
    dialogue_history = message.get("dialogue_history", [])

    # 发送处理中状态
    await websocket.send_json({
        "type": "status",
        "status": "processing",
        "message": f"正在为 {speaker_id} 生成对话...",
    })

    # TODO: 调用 CharacterAgent 生成对话
    # await character_agent.execute({...})

    # 模拟响应（待实现）
    response = {
        "type": "dialogue_generated",
        "status": "success",
        "data": {
            "speaker_id": speaker_id,
            "dialogue": "（示例）这怎么可能...",
            "action": "她后退一步，难以置信地看着你",
            "emotion": "shock",
        },
    }

    await websocket.send_json(response)


async def handle_generate_narrative(websocket: WebSocket, message: dict, client_id: str):
    """
    处理叙事文本生成请求

    预期输入:
    {
        "type": "generate_narrative",
        "intents": ["需要表达的意图列表"],
        "environment": "环境描述",
        "character_moods": {"角色 ID": "情绪"},
        "hooks": ["伏笔 ID"],
    }
    """
    intents = message.get("intents", [])
    environment = message.get("environment", "")
    character_moods = message.get("character_moods", {})

    # 发送处理中状态
    await websocket.send_json({
        "type": "status",
        "status": "processing",
        "message": "正在生成叙事文本...",
    })

    # TODO: 调用 WriterAgent 生成叙事文本

    # 模拟响应（待实现）
    response = {
        "type": "narrative_generated",
        "status": "success",
        "data": {
            "content": f"(示例) {environment}。{intents[0] if intents else ''}",
            "word_count": 150,
        },
    }

    await websocket.send_json(response)


async def handle_chapter_end_check(
    websocket: WebSocket, message: dict, client_id: str
):
    """
    处理章节结束检查请求

    预期输入:
    {
        "type": "chapter_end_check",
        "events": ["事件摘要列表"],
        "hooks_planted": ["伏笔 ID 列表"],
        "word_count": 字数，
    }
    """
    events = message.get("events", [])
    hooks_planted = message.get("hooks_planted", [])
    word_count = message.get("word_count", 0)

    # 发送处理中状态
    await websocket.send_json({
        "type": "status",
        "status": "processing",
        "message": "正在评估章节是否可收尾...",
    })

    # TODO: 调用 EvaluatorAgent 进行章节结束评估

    # 模拟响应（待实现）
    response = {
        "type": "chapter_end_result",
        "status": "success",
        "data": {
            "should_end": True,
            "reason": "本章已埋设足够悬念，信息增量达标",
            "scores": {
                "info_gain": 0.8,
                "suspense": 0.7,
                "pacing": 0.75,
                "completeness": 0.8,
            },
        },
    }

    await websocket.send_json(response)


async def handle_intervention(websocket: WebSocket, message: dict, client_id: str):
    """
    处理用户干预请求

    预期输入:
    {
        "type": "intervention",
        "intervention_type": "modify_character/modify_plot/force_event",
        "details": {...},
    }
    """
    intervention_type = message.get("intervention_type")
    details = message.get("details", {})

    # 发送处理中状态
    await websocket.send_json({
        "type": "status",
        "status": "processing",
        "message": f"正在执行干预：{intervention_type}...",
    })

    # TODO: 创建快照并记录干预日志

    # 模拟响应（待实现）
    response = {
        "type": "intervention_result",
        "status": "success",
        "data": {
            "snapshot_id": f"snapshot_pre_{int(time.time())}",
            "intervention_logged": True,
        },
    }

    await websocket.send_json(response)


async def send_error(websocket: WebSocket, error_message: str):
    """发送错误消息"""
    await websocket.send_json({
        "type": "error",
        "message": error_message,
    })


@router.get("/connections")
async def get_connections():
    """获取当前活动连接数（用于调试）"""
    return {
        "active_connections": len(manager.active_connections),
        "clients": list(manager.client_data.values()),
    }
