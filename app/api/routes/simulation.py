"""
世界模拟API路由
GodView v5 世界模拟系统的API接口
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from app.models.simulation import (
    SimulationControlRequest,
    SimulationInitializeRequest,
    SimulationStatusResponse,
    PerformanceStats,
    WorldStateSnapshot,
    SimulationStatusEnum
)
from app.services.world_simulation import WorldSimulationEngine, SimulationStatus

logger = logging.getLogger(__name__)
router = APIRouter()

# 全局模拟引擎实例管理
simulation_engines: Dict[str, WorldSimulationEngine] = {}

# WebSocket连接管理
simulation_connections: Dict[str, List[WebSocket]] = {}


def get_simulation_engine(world_id: str) -> Optional[WorldSimulationEngine]:
    """获取指定世界的模拟引擎

    Args:
        world_id: 世界ID

    Returns:
        WorldSimulationEngine: 模拟引擎实例，如果不存在则返回None
    """
    return simulation_engines.get(world_id)


def create_simulation_engine(world_id: str, config: Dict[str, Any] = None) -> WorldSimulationEngine:
    """创建世界模拟引擎实例

    Args:
        world_id: 世界ID
        config: 配置参数

    Returns:
        WorldSimulationEngine: 创建的模拟引擎实例
    """
    if world_id in simulation_engines:
        return simulation_engines[world_id]

    engine = WorldSimulationEngine(world_id, config)
    simulation_engines[world_id] = engine
    logger.info(f"为世界 {world_id} 创建模拟引擎")

    # 注册状态更新回调，广播到WebSocket客户端
    async def state_update_callback(update: Dict[str, Any]):
        await broadcast_simulation_update(world_id, update)

    engine.register_state_update_callback(state_update_callback)

    return engine


def remove_simulation_engine(world_id: str):
    """移除模拟引擎实例

    Args:
        world_id: 世界ID
    """
    if world_id in simulation_engines:
        engine = simulation_engines[world_id]
        # 确保停止模拟
        if engine.is_running:
            # 创建后台任务来停止
            import asyncio
            asyncio.create_task(engine.stop_simulation())

        del simulation_engines[world_id]
        logger.info(f"移除世界 {world_id} 的模拟引擎")


async def broadcast_simulation_update(world_id: str, update: Dict[str, Any]):
    """广播模拟更新到所有连接的客户端

    Args:
        world_id: 世界ID
        update: 更新数据
    """
    if world_id not in simulation_connections:
        return

    for connection in simulation_connections[world_id][:]:
        try:
            await connection.send_json(update)
        except Exception as e:
            logger.error(f"发送模拟更新失败: {e}")
            simulation_connections[world_id].remove(connection)


# ===== REST API端点 =====

@router.post("/simulation/initialize", response_model=Dict[str, Any])
async def initialize_simulation(request: SimulationInitializeRequest):
    """初始化世界模拟

    Args:
        request: 初始化请求

    Returns:
        Dict: 初始化结果
    """
    try:
        # 获取或创建模拟引擎
        engine = get_simulation_engine(request.world_id)
        if not engine:
            engine = create_simulation_engine(request.world_id)

        # 初始化模拟引擎
        config = {
            "tick_interval": 1.0,  # 默认1秒
            "time_config": request.time_config or {}
        }

        await engine.initialize(
            time_config=request.time_config,
            entities=request.entities,
            locations=request.locations
        )

        return {
            "success": True,
            "world_id": request.world_id,
            "message": "模拟引擎初始化成功",
            "time_info": engine.get_time_system().get_time_info() if engine.get_time_system() else None
        }
    except Exception as e:
        logger.error(f"初始化模拟引擎失败: {e}")
        raise HTTPException(status_code=500, detail=f"初始化模拟引擎失败: {str(e)}")


@router.post("/simulation/control", response_model=Dict[str, Any])
async def control_simulation(request: SimulationControlRequest):
    """控制世界模拟

    Args:
        request: 控制请求

    Returns:
        Dict: 控制结果
    """
    engine = get_simulation_engine(request.world_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"世界 {request.world_id} 的模拟引擎不存在")

    try:
        result = None

        if request.action == "start":
            success = await engine.start_simulation()
            if success:
                result = {"action": "start", "message": "模拟已启动"}
            else:
                result = {"action": "start", "message": "模拟已在运行中"}

        elif request.action == "stop":
            success = await engine.stop_simulation()
            if success:
                result = {"action": "stop", "message": "模拟已停止"}
            else:
                result = {"action": "stop", "message": "模拟未在运行"}

        elif request.action == "pause":
            success = await engine.pause_simulation()
            if success:
                result = {"action": "pause", "message": "模拟已暂停"}
            else:
                result = {"action": "pause", "message": "模拟无法暂停"}

        elif request.action == "resume":
            success = await engine.resume_simulation()
            if success:
                result = {"action": "resume", "message": "模拟已恢复"}
            else:
                result = {"action": "resume", "message": "模拟无法恢复"}

        elif request.action == "manual_tick":
            success = await engine.manual_tick()
            if success:
                result = {"action": "manual_tick", "message": "手动tick执行成功"}
            else:
                result = {"action": "manual_tick", "message": "手动tick执行失败"}

        elif request.action == "set_interval":
            if request.tick_interval is None:
                raise HTTPException(status_code=400, detail="缺少 tick_interval 参数")
            engine.set_tick_interval(request.tick_interval)
            result = {
                "action": "set_interval",
                "tick_interval": request.tick_interval,
                "message": f"时钟周期间隔已设置为 {request.tick_interval} 秒"
            }

        else:
            raise HTTPException(status_code=400, detail=f"不支持的操作: {request.action}")

        return {
            "success": True,
            "world_id": request.world_id,
            "result": result,
            "performance": engine.get_performance_stats()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"控制模拟失败: {e}")
        raise HTTPException(status_code=500, detail=f"控制模拟失败: {str(e)}")


@router.get("/simulation/status/{world_id}", response_model=SimulationStatusResponse)
async def get_simulation_status(world_id: str):
    """获取世界模拟状态

    Args:
        world_id: 世界ID

    Returns:
        SimulationStatusResponse: 模拟状态
    """
    engine = get_simulation_engine(world_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"世界 {world_id} 的模拟引擎不存在")

    status = engine.get_status()
    time_system = engine.get_time_system()

    performance_stats = PerformanceStats(
        average_tick_duration=engine.get_average_tick_duration(),
        max_tick_duration=engine.get_max_tick_duration(),
        total_ticks=engine.total_ticks,
        error_count=engine.error_count,
        current_tick=engine.current_tick,
        status=status.value,
        is_running=engine.is_running,
        is_paused=engine.is_paused,
        last_tick_time=engine.last_tick_time.isoformat() if engine.last_tick_time else None
    )

    return SimulationStatusResponse(
        world_id=world_id,
        status=SimulationStatusEnum(status.value),
        performance=performance_stats,
        current_time=time_system.get_formatted_time() if time_system else None,
        entity_count=0,  # TODO: 从实体系统获取
        active_events=0,  # TODO: 从事件系统获取
        last_update=datetime.utcnow()
    )


@router.post("/simulation/snapshot/{world_id}", response_model=Dict[str, Any])
async def create_simulation_snapshot(world_id: str, note: str = ""):
    """创建世界模拟快照

    Args:
        world_id: 世界ID
        note: 快照备注

    Returns:
        Dict: 快照创建结果
    """
    engine = get_simulation_engine(world_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"世界 {world_id} 的模拟引擎不存在")

    try:
        snapshot_data = await engine.create_snapshot()
        snapshot_id = f"snapshot_{world_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        snapshot = WorldStateSnapshot(
            world_id=world_id,
            snapshot_id=snapshot_id,
            timestamp=datetime.utcnow(),
            time_system=snapshot_data.get("time_system"),
            entities=snapshot_data.get("entities", []),
            locations=snapshot_data.get("locations", []),
            active_events=snapshot_data.get("active_events", []),
            memory_snapshots=snapshot_data.get("memory_snapshots", {}),
            performance=snapshot_data.get("performance", {})
        )

        # TODO: 将快照保存到数据库
        # await postgres_db.save_simulation_snapshot(snapshot.dict())

        return {
            "success": True,
            "world_id": world_id,
            "snapshot_id": snapshot_id,
            "snapshot": snapshot.dict(),
            "message": "快照创建成功"
        }
    except Exception as e:
        logger.error(f"创建模拟快照失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建模拟快照失败: {str(e)}")


@router.get("/simulation/engines", response_model=Dict[str, Any])
async def list_simulation_engines():
    """列出所有模拟引擎

    Returns:
        Dict: 模拟引擎列表
    """
    engines_info = []
    for world_id, engine in simulation_engines.items():
        engines_info.append({
            "world_id": world_id,
            "status": engine.get_status().value,
            "is_running": engine.is_running,
            "is_paused": engine.is_paused,
            "current_tick": engine.current_tick,
            "total_ticks": engine.total_ticks,
            "performance": engine.get_performance_stats()
        })

    return {
        "success": True,
        "count": len(engines_info),
        "engines": engines_info
    }


# ===== WebSocket端点 =====

@router.websocket("/ws/simulation/{world_id}")
async def simulation_websocket(websocket: WebSocket, world_id: str):
    """世界模拟WebSocket连接

    Args:
        websocket: WebSocket连接
        world_id: 世界ID
    """
    await websocket.accept()

    # 获取或创建模拟引擎
    engine = get_simulation_engine(world_id)
    if not engine:
        engine = create_simulation_engine(world_id)

    # 添加到连接管理器
    if world_id not in simulation_connections:
        simulation_connections[world_id] = []
    simulation_connections[world_id].append(websocket)

    try:
        # 发送初始连接状态
        await websocket.send_json({
            "type": "connected",
            "data": {
                "world_id": world_id,
                "status": engine.get_status().value,
                "performance": engine.get_performance_stats(),
                "message": "模拟系统连接成功"
            }
        })

        # 处理客户端消息
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "get_status":
                status = engine.get_status()
                time_system = engine.get_time_system()

                await websocket.send_json({
                    "type": "status_update",
                    "data": {
                        "world_id": world_id,
                        "status": status.value,
                        "performance": engine.get_performance_stats(),
                        "current_time": time_system.get_formatted_time() if time_system else None,
                        "entity_count": 0,  # TODO: 从实体系统获取
                        "active_events": 0,  # TODO: 从事件系统获取
                    }
                })

            elif data.get("type") == "start_simulation":
                success = await engine.start_simulation()
                await websocket.send_json({
                    "type": "simulation_started",
                    "data": {
                        "success": success,
                        "status": engine.get_status().value
                    }
                })

            elif data.get("type") == "stop_simulation":
                success = await engine.stop_simulation()
                await websocket.send_json({
                    "type": "simulation_stopped",
                    "data": {
                        "success": success,
                        "status": engine.get_status().value
                    }
                })

            elif data.get("type") == "toggle_pause":
                if engine.is_paused:
                    success = await engine.resume_simulation()
                    action = "resumed"
                else:
                    success = await engine.pause_simulation()
                    action = "paused"

                await websocket.send_json({
                    "type": "pause_toggled",
                    "data": {
                        "success": success,
                        "action": action,
                        "status": engine.get_status().value
                    }
                })

            elif data.get("type") == "manual_tick":
                success = await engine.manual_tick()
                await websocket.send_json({
                    "type": "manual_tick_executed",
                    "data": {
                        "success": success,
                        "tick_count": engine.current_tick,
                        "performance": engine.get_performance_stats()
                    }
                })

            elif data.get("type") == "set_tick_interval":
                interval = data.get("interval", 1.0)
                engine.set_tick_interval(interval)
                await websocket.send_json({
                    "type": "interval_set",
                    "data": {
                        "tick_interval": interval,
                        "message": f"时钟周期间隔已设置为 {interval} 秒"
                    }
                })

            elif data.get("type") == "create_snapshot":
                note = data.get("note", "")
                snapshot_id = f"snapshot_{world_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                snapshot_data = await engine.create_snapshot()

                await websocket.send_json({
                    "type": "snapshot_created",
                    "data": {
                        "snapshot_id": snapshot_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": snapshot_data,
                        "note": note
                    }
                })

    except WebSocketDisconnect:
        logger.info(f"模拟WebSocket连接断开: {world_id}")
    except Exception as e:
        logger.error(f"模拟WebSocket错误: {e}")
    finally:
        # 清理连接
        if world_id in simulation_connections:
            if websocket in simulation_connections[world_id]:
                simulation_connections[world_id].remove(websocket)