"""
时间系统API路由
GodView v5 时间流逝系统的API接口
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta

from app.models.time import (
    TimeUpdateModel,
    TimeSystemConfig,
    TimeJumpRequest,
    TimeBranchRequest,
    TimeControlRequest,
    TimeRecordRequest,
    TimeHistoryResponse,
    WorldTimeLogModel
)
from app.services.time_system import TimeSystem, TimeUpdateResult, DayPhase, Season

logger = logging.getLogger(__name__)
router = APIRouter()

# 全局时间系统实例管理
time_systems: Dict[str, TimeSystem] = {}

# WebSocket连接管理
time_connections: Dict[str, List[WebSocket]] = {}


def get_time_system(world_id: str) -> Optional[TimeSystem]:
    """获取指定世界的时间系统

    Args:
        world_id: 世界ID

    Returns:
        TimeSystem: 时间系统实例，如果不存在则返回None
    """
    return time_systems.get(world_id)


def create_time_system(world_id: str, config: Dict[str, Any] = None) -> TimeSystem:
    """创建时间系统实例

    Args:
        world_id: 世界ID
        config: 配置参数

    Returns:
        TimeSystem: 创建的时间系统实例
    """
    if world_id in time_systems:
        return time_systems[world_id]

    time_system = TimeSystem(config or {})
    time_systems[world_id] = time_system
    logger.info(f"为世界 {world_id} 创建时间系统")
    return time_system


def remove_time_system(world_id: str):
    """移除时间系统实例

    Args:
        world_id: 世界ID
    """
    if world_id in time_systems:
        del time_systems[world_id]
        logger.info(f"移除世界 {world_id} 的时间系统")


async def broadcast_time_update(world_id: str, update: Dict[str, Any]):
    """广播时间更新到所有连接的客户端

    Args:
        world_id: 世界ID
        update: 更新数据
    """
    if world_id not in time_connections:
        return

    for connection in time_connections[world_id][:]:
        try:
            await connection.send_json(update)
        except Exception as e:
            logger.error(f"发送时间更新失败: {e}")
            time_connections[world_id].remove(connection)


# ===== REST API端点 =====

@router.post("/time/systems/{world_id}", response_model=Dict[str, Any])
async def create_time_system_endpoint(world_id: str, config: TimeSystemConfig):
    """创建或获取时间系统

    Args:
        world_id: 世界ID
        config: 时间系统配置

    Returns:
        Dict: 创建结果
    """
    try:
        time_system = create_time_system(
            world_id,
            config.dict()
        )

        # 设置时间模式
        time_system.set_time_mode(config.time_mode.value)

        # 注册时间更新回调，广播到WebSocket客户端
        async def time_update_callback(result: TimeUpdateResult):
            update = {
                "type": "time_update",
                "data": {
                    "current_time": result.current_time.isoformat(),
                    "previous_time": result.previous_time.isoformat(),
                    "time_delta_minutes": result.time_delta.total_seconds() / 60,
                    "time_scale": result.time_scale,
                    "tick_count": time_system.tick_count,
                    "day_of_week": result.day_of_week,
                    "day_of_week_name": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][result.day_of_week],
                    "hour": result.hour,
                    "minute": result.current_time.minute,
                    "day_phase": result.day_phase.value,
                    "season": result.season.value,
                    "triggered_events": result.triggered_events
                }
            }
            await broadcast_time_update(world_id, update)

        time_system.register_time_update_callback(time_update_callback)

        return {
            "success": True,
            "world_id": world_id,
            "time_info": time_system.get_time_info(),
            "message": "时间系统创建成功"
        }
    except Exception as e:
        logger.error(f"创建时间系统失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建时间系统失败: {str(e)}")


@router.get("/time/systems/{world_id}", response_model=Dict[str, Any])
async def get_time_system_status(world_id: str):
    """获取时间系统状态

    Args:
        world_id: 世界ID

    Returns:
        Dict: 时间系统状态
    """
    time_system = get_time_system(world_id)
    if not time_system:
        raise HTTPException(status_code=404, detail=f"世界 {world_id} 的时间系统不存在")

    return {
        "success": True,
        "world_id": world_id,
        "time_info": time_system.get_time_info(),
        "time_mode": time_system.get_time_mode(),
        "is_frozen": time_system.is_time_frozen()
    }


@router.post("/time/control", response_model=Dict[str, Any])
async def control_time(request: TimeControlRequest):
    """时间控制操作

    Args:
        request: 时间控制请求

    Returns:
        Dict: 操作结果
    """
    time_system = get_time_system(request.world_id)
    if not time_system:
        raise HTTPException(status_code=404, detail=f"世界 {request.world_id} 的时间系统不存在")

    try:
        result = None

        if request.action == "freeze":
            time_system.freeze_time()
            result = {"action": "freeze", "message": "时间已冻结"}

        elif request.action == "unfreeze":
            time_system.unfreeze_time()
            result = {"action": "unfreeze", "message": "时间已解冻"}

        elif request.action == "set_scale":
            if request.time_scale is None:
                raise HTTPException(status_code=400, detail="缺少 time_scale 参数")
            time_system.set_time_scale(request.time_scale)
            result = {"action": "set_scale", "time_scale": time_system.get_time_scale()}

        elif request.action == "advance":
            if request.advance_minutes is None:
                raise HTTPException(status_code=400, detail="缺少 advance_minutes 参数")
            update_result = await time_system.advance(request.advance_minutes)
            result = {
                "action": "advance",
                "time_info": update_result.__dict__,
                "time_info_formatted": time_system.get_formatted_time()
            }

        elif request.action == "set_mode":
            if request.mode is None:
                raise HTTPException(status_code=400, detail="缺少 mode 参数")
            time_system.set_time_mode(request.mode.value)
            result = {"action": "set_mode", "time_mode": time_system.get_time_mode()}

        else:
            raise HTTPException(status_code=400, detail=f"不支持的操作: {request.action}")

        return {
            "success": True,
            "world_id": request.world_id,
            "result": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"时间控制操作失败: {e}")
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@router.post("/time/jump", response_model=Dict[str, Any])
async def time_jump(request: TimeJumpRequest):
    """时间跳跃操作

    Args:
        request: 时间跳跃请求

    Returns:
        Dict: 跳跃结果
    """
    time_system = get_time_system(request.world_id)
    if not time_system:
        raise HTTPException(status_code=404, detail=f"世界 {request.world_id} 的时间系统不存在")

    try:
        result = None

        if request.jump_type == "forward":
            if request.delta_minutes is None:
                raise HTTPException(status_code=400, detail="缺少 delta_minutes 参数")
            jump_result = time_system.jump_forward(timedelta(minutes=request.delta_minutes))
            result = {
                "action": "forward_jump",
                "delta_minutes": request.delta_minutes,
                "new_time": time_system.get_formatted_time()
            }

        elif request.jump_type == "backward":
            if request.delta_minutes is None:
                raise HTTPException(status_code=400, detail="缺少 delta_minutes 参数")
            jump_result = time_system.jump_backward(timedelta(minutes=request.delta_minutes))
            result = {
                "action": "backward_jump",
                "delta_minutes": request.delta_minutes,
                "new_time": time_system.get_formatted_time()
            }

        elif request.jump_type == "to_absolute":
            if request.target_time is None:
                raise HTTPException(status_code=400, detail="缺少 target_time 参数")
            jump_result = time_system.jump_to_time(target_time=request.target_time)
            result = {
                "action": "absolute_jump",
                "target_time": request.target_time.isoformat(),
                "new_time": time_system.get_formatted_time()
            }

        elif request.jump_type == "to_year":
            if request.target_year is None:
                raise HTTPException(status_code=400, detail="缺少 target_year 参数")
            jump_result = time_system.jump_to_year(year=request.target_year)
            result = {
                "action": "year_jump",
                "target_year": request.target_year,
                "new_time": time_system.get_formatted_time()
            }

        else:
            raise HTTPException(status_code=400, detail=f"不支持的跳跃类型: {request.jump_type}")

        # 如果有备注，记录时间点
        if request.note:
            time_system.record_time_point(request.note)

        return {
            "success": True,
            "world_id": request.world_id,
            "result": result,
            "time_info": time_system.get_time_info()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"时间跳跃失败: {e}")
        raise HTTPException(status_code=500, detail=f"时间跳跃失败: {str(e)}")


@router.post("/time/branches", response_model=Dict[str, Any])
async def create_time_branch(request: TimeBranchRequest):
    """创建时间分支

    Args:
        request: 创建分支请求

    Returns:
        Dict: 创建结果
    """
    time_system = get_time_system(request.world_id)
    if not time_system:
        raise HTTPException(status_code=404, detail=f"世界 {request.world_id} 的时间系统不存在")

    try:
        branch_id = time_system.create_time_branch(request.branch_name)

        return {
            "success": True,
            "world_id": request.world_id,
            "branch_id": branch_id,
            "message": f"时间分支 '{request.branch_name}' 创建成功"
        }
    except Exception as e:
        logger.error(f"创建时间分支失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建时间分支失败: {str(e)}")


@router.get("/time/branches/{world_id}", response_model=Dict[str, Any])
async def get_time_branches(world_id: str):
    """获取时间分支列表

    Args:
        world_id: 世界ID

    Returns:
        Dict: 分支列表
    """
    time_system = get_time_system(world_id)
    if not time_system:
        raise HTTPException(status_code=404, detail=f"世界 {world_id} 的时间系统不存在")

    branches = time_system.get_time_branches()

    return {
        "success": True,
        "world_id": world_id,
        "branches": branches,
        "count": len(branches)
    }


@router.post("/time/branches/{world_id}/switch", response_model=Dict[str, Any])
async def switch_time_branch(world_id: str, branch_id: str):
    """切换到时间分支

    Args:
        world_id: 世界ID
        branch_id: 分支ID

    Returns:
        Dict: 切换结果
    """
    time_system = get_time_system(world_id)
    if not time_system:
        raise HTTPException(status_code=404, detail=f"世界 {world_id} 的时间系统不存在")

    try:
        success = time_system.switch_to_branch(branch_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"分支 {branch_id} 不存在")

        return {
            "success": True,
            "world_id": world_id,
            "branch_id": branch_id,
            "time_info": time_system.get_time_info(),
            "message": "成功切换到时间分支"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换时间分支失败: {e}")
        raise HTTPException(status_code=500, detail=f"切换时间分支失败: {str(e)}")


@router.post("/time/record", response_model=Dict[str, Any])
async def record_time_point(request: TimeRecordRequest):
    """记录时间点

    Args:
        request: 记录请求

    Returns:
        Dict: 记录结果
    """
    time_system = get_time_system(request.world_id)
    if not time_system:
        raise HTTPException(status_code=404, detail=f"世界 {request.world_id} 的时间系统不存在")

    try:
        time_point_id = time_system.record_time_point(request.note)

        return {
            "success": True,
            "world_id": request.world_id,
            "time_point_id": time_point_id,
            "current_time": time_system.get_formatted_time(),
            "message": "时间点记录成功"
        }
    except Exception as e:
        logger.error(f"记录时间点失败: {e}")
        raise HTTPException(status_code=500, detail=f"记录时间点失败: {str(e)}")


@router.get("/time/history/{world_id}", response_model=Dict[str, Any])
async def get_time_history(world_id: str, limit: int = 100):
    """获取时间历史

    Args:
        world_id: 世界ID
        limit: 返回数量限制

    Returns:
        Dict: 时间历史
    """
    time_system = get_time_system(world_id)
    if not time_system:
        raise HTTPException(status_code=404, detail=f"世界 {world_id} 的时间系统不存在")

    time_points = time_system.get_time_history()
    branches = time_system.get_time_branches()

    return {
        "success": True,
        "world_id": world_id,
        "time_points": time_points[-limit:] if time_points else [],
        "branches": branches,
        "current_time": time_system.get_formatted_time(),
        "time_mode": time_system.get_time_mode(),
        "tick_count": time_system.tick_count
    }


# ===== WebSocket端点 =====

@router.websocket("/ws/time/{world_id}")
async def time_websocket(websocket: WebSocket, world_id: str):
    """时间更新WebSocket连接

    Args:
        websocket: WebSocket连接
        world_id: 世界ID
    """
    await websocket.accept()

    # 创建时间系统（如果不存在）
    time_system = get_time_system(world_id)
    if not time_system:
        time_system = create_time_system(world_id)

    # 添加到连接管理器
    if world_id not in time_connections:
        time_connections[world_id] = []
    time_connections[world_id].append(websocket)

    try:
        # 发送当前时间状态
        await websocket.send_json({
            "type": "connected",
            "data": {
                "world_id": world_id,
                "time_info": time_system.get_time_info(),
                "message": "时间系统连接成功"
            }
        })

        # 处理客户端消息
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "get_time_info":
                await websocket.send_json({
                    "type": "time_info",
                    "data": {
                        "time_info": time_system.get_time_info(),
                        "time_mode": time_system.get_time_mode(),
                        "is_frozen": time_system.is_time_frozen()
                    }
                })

            elif data.get("type") == "manual_tick":
                minutes = data.get("minutes", 10)
                update_result = await time_system.advance(minutes)
                await websocket.send_json({
                    "type": "tick_result",
                    "data": {
                        "time_info": update_result.__dict__,
                        "formatted_time": time_system.get_formatted_time()
                    }
                })

            elif data.get("type") == "toggle_freeze":
                if time_system.is_time_frozen():
                    time_system.unfreeze_time()
                    status = "unfrozen"
                else:
                    time_system.freeze_time()
                    status = "frozen"

                await websocket.send_json({
                    "type": "freeze_toggle",
                    "data": {
                        "status": status,
                        "is_frozen": time_system.is_time_frozen()
                    }
                })

            elif data.get("type") == "set_time_scale":
                scale = data.get("scale", 1.0)
                time_system.set_time_scale(scale)
                await websocket.send_json({
                    "type": "scale_set",
                    "data": {
                        "time_scale": time_system.get_time_scale()
                    }
                })

    except WebSocketDisconnect:
        logger.info(f"时间WebSocket连接断开: {world_id}")
    except Exception as e:
        logger.error(f"时间WebSocket错误: {e}")
    finally:
        # 清理连接
        if world_id in time_connections:
            if websocket in time_connections[world_id]:
                time_connections[world_id].remove(websocket)
