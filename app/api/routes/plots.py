"""
剧情管理 API 路由
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.plot import Chapter, CreateChapterDTO, Hook, Plot, UpdateChapterDTO
from app.services.graph_projection_service import enqueue_graph_projection_best_effort

logger = logging.getLogger(__name__)

router = APIRouter()


def _filesystem_chapter_payload(
    chapter_data: Dict[str, Any],
    content: str,
    *,
    preserve_existing_path: bool = True,
) -> Dict[str, Any]:
    from app.services.chapter_document_storage import chapter_document_storage

    metadata = chapter_document_storage.write_chapter(
        chapter_id=str(chapter_data["id"]),
        project_id=chapter_data.get("project_id"),
        title=chapter_data.get("title") or "未命名章节",
        content=content,
        existing_path=chapter_data.get("content_path") if preserve_existing_path else None,
    )
    chapter_data.update(metadata)
    chapter_data["content"] = ""
    chapter_data["word_count"] = len(content)
    return chapter_data


def _hydrate_chapter_content(chapter: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.chapter_document_storage import chapter_document_storage

    try:
        return chapter_document_storage.hydrate_chapter(chapter)
    except FileNotFoundError as exc:
        logger.error("章节文件不存在: %s", exc)
        raise HTTPException(status_code=500, detail="章节文件不存在") from exc
    except ValueError as exc:
        logger.error("章节文件路径非法: %s", exc)
        raise HTTPException(status_code=500, detail="章节文件路径非法") from exc


def _hydrate_chapters_content(chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_hydrate_chapter_content(chapter) for chapter in chapters]


@router.get("/hooks", response_model=List[Dict[str, Any]])
async def list_hooks(
    project_id: Optional[str] = Query(None, description="按项目 ID 过滤"),
    world_id: Optional[str] = Query(None, description="按世界 ID 过滤"),
    include_inherited: bool = Query(False, description="是否包含父级世界/项目级伏笔"),
    scope_type: Optional[str] = Query(None, description="按伏笔作用域过滤"),
    character_id: Optional[str] = Query(None, description="按角色 ID 过滤"),
    status: Optional[str] = None,
    hook_type: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    """
    获取伏笔列表

    Args:
        project_id: 按项目 ID 过滤
        status: 按状态过滤
        hook_type: 按类型过滤
        limit: 返回数量限制

    Returns:
        List: 伏笔列表
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    hooks = await postgres_db.get_all_hooks(
        project_id=project_id,
        world_id=world_id,
        include_inherited=include_inherited,
        scope_type=scope_type,
        character_id=character_id,
        status=status,
        limit=limit,
    )

    # 类型过滤
    if hook_type and hooks:
        hooks = [h for h in hooks if h.get("hook_type") == hook_type]

    return hooks


@router.get("/hooks/{hook_id}", response_model=Dict[str, Any])
async def get_hook(hook_id: str):
    """
    获取伏笔详情

    Args:
        hook_id: 伏笔 ID

    Returns:
        Dict: 伏笔数据
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    hook = await postgres_db.get_hook(hook_id)

    if not hook:
        raise HTTPException(status_code=404, detail="伏笔不存在")

    return hook


@router.post("/hooks", response_model=Dict[str, Any])
async def create_hook(hook: Hook):
    """
    创建新伏笔

    Args:
        hook: 伏笔数据

    Returns:
        Dict: 创建结果
    """
    from app.api.app import postgres_db
    import uuid
    from datetime import datetime

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    hook_data = hook.model_dump(mode="json")

    # 自动生成 ID（如果未提供）
    if not hook_data.get("id"):
        hook_data["id"] = str(uuid.uuid4())

    if hook_data.get("project_id") and hook_data.get("world_id"):
        belongs = await postgres_db.assert_world_belongs_to_project(str(hook_data["world_id"]), str(hook_data["project_id"]))
        if not belongs:
            raise HTTPException(status_code=400, detail="伏笔所属世界不属于当前项目")
    if not hook_data.get("scope_type"):
        hook_data["scope_type"] = "world" if hook_data.get("world_id") else "project"
    if not hook_data.get("priority"):
        hook_data["priority"] = 3

    duplicate = None
    if hook_data.get("project_id") and hasattr(postgres_db, "find_duplicate_hook"):
        duplicate = await postgres_db.find_duplicate_hook(
            str(hook_data["project_id"]),
            hook_data.get("title", ""),
            hook_data.get("description", "") or hook_data.get("plant_context", ""),
            world_id=hook_data.get("world_id"),
            scope_type=hook_data.get("scope_type"),
        )
    if duplicate:
        return {
            "success": True,
            "id": str(duplicate.get("id")),
            "duplicate": True,
            "message": f"伏笔 '{hook.title}' 已存在，已复用现有条目",
        }

    # 设置默认值和时间戳（使用 datetime 对象）
    now = datetime.now()
    if not hook_data.get("status"):
        hook_data["status"] = "planted"
    if not hook_data.get("priority"):
        hook_data["priority"] = 3
    hook_data["created_at"] = now

    try:
        await postgres_db.save_hook(hook_data)
        await enqueue_graph_projection_best_effort("hook", hook_data)
        return {
            "success": True,
            "id": hook_data["id"],
            "message": f"伏笔 '{hook.title}' 创建成功",
        }
    except Exception as e:
        logger.error(f"创建伏笔失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/hooks/{hook_id}/status", response_model=Dict[str, Any])
async def update_hook_status(hook_id: str, status: str):
    """
    更新伏笔状态

    Args:
        hook_id: 伏笔 ID
        status: 新状态 (planted/triggered/resolved/dropped)

    Returns:
        Dict: 更新结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        await postgres_db.update_hook_status(hook_id, status)
        hook = await postgres_db.get_hook(hook_id)
        if hook:
            await enqueue_graph_projection_best_effort("hook", hook)
        return {
            "success": True,
            "message": f"伏笔状态已更新为 '{status}'",
        }
    except Exception as e:
        logger.error(f"更新伏笔状态失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chapters", response_model=List[Dict[str, Any]])
async def list_chapters(
    project_id: Optional[str] = Query(None, description="按项目 ID 过滤"),
    world_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    """
    获取章节列表

    Args:
        project_id: 按项目 ID 过滤
        world_id: 按世界过滤
        status: 按状态过滤
        limit: 返回数量限制

    Returns:
        List: 章节列表
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    if project_id:
        if world_id:
            chapters = await postgres_db.get_chapters_by_world(world_id)
            chapters = [c for c in chapters if str(c.get("project_id")) == str(project_id)]
            if status and chapters:
                chapters = [c for c in chapters if c.get("status") == status]
        else:
            chapters = await postgres_db.get_chapters_by_project(
                project_id=project_id,
                status=status,
                limit=limit,
            )
    elif world_id:
        chapters = await postgres_db.get_chapters_by_world(world_id)
        if status and chapters:
            chapters = [c for c in chapters if c.get("status") == status]
    else:
        chapters = await postgres_db.execute_query(
            "SELECT * FROM chapters ORDER BY created_at ASC LIMIT :limit",
            {"limit": limit},
        )
        if status and chapters:
            chapters = [c for c in chapters if c.get("status") == status]

    return _hydrate_chapters_content(chapters[:limit])


@router.get("/chapters/{chapter_id}", response_model=Dict[str, Any])
async def get_chapter(chapter_id: str):
    """
    获取章节详情

    Args:
        chapter_id: 章节 ID

    Returns:
        Dict: 章节数据
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    chapter = await postgres_db.get_chapter(chapter_id)

    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    return _hydrate_chapter_content(chapter)


@router.post("/chapters", response_model=Dict[str, Any])
async def create_chapter(chapter: CreateChapterDTO):
    """
    创建新章节

    Args:
        chapter: 章节数据

    Returns:
        Dict: 创建结果
    """
    from app.api.app import postgres_db
    import uuid
    from datetime import datetime

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 生成 UUID 作为章节 ID
    chapter_id = str(uuid.uuid4())
    now = datetime.now()
    content = chapter.content or ""

    # 优先使用传入的 project_id，否则从 world_id 获取
    project_id = chapter.project_id
    world_id = chapter.world_id

    if not project_id and world_id:
        try:
            world = await postgres_db.get_world(world_id)
            if world:
                project_id = world.get("project_id")
        except:
            pass

    chapter_data = {
        "id": chapter_id,
        "title": chapter.title,
        "project_id": project_id,
        "world_id": world_id,
        "summary": chapter.summary or "",
        "content": content,
        "word_count": len(content),
        "status": chapter.status.value if hasattr(chapter.status, "value") else chapter.status,
        "events": [],
        "hooks_planted": [],
        "hooks_resolved": [],
        "main_plot_progress": {},
        "reader_scores": {},
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }

    try:
        chapter_data = _filesystem_chapter_payload(chapter_data, content)
        await postgres_db.save_chapter(chapter_data)
        return _hydrate_chapter_content(chapter_data)
    except Exception as e:
        logger.error(f"创建章节失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/chapters/{chapter_id}", response_model=Dict[str, Any])
async def update_chapter(chapter_id: str, chapter: UpdateChapterDTO):
    """
    更新章节数据

    Args:
        chapter_id: 章节 ID
        chapter: 新章节数据

    Returns:
        Dict: 更新结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    existing = await postgres_db.get_chapter(chapter_id)
    if not existing:
        raise HTTPException(status_code=404, detail="章节不存在")

    existing = _hydrate_chapter_content(existing)
    update_payload = chapter.model_dump(mode="json", exclude_unset=True)
    content_changed = "content" in update_payload
    title_changed = "title" in update_payload and update_payload.get("title") != existing.get("title")
    merged = {**existing, **update_payload}
    content = merged.get("content") or ""
    merged["updated_at"] = datetime.now()  # 使用 datetime 对象而非字符串

    try:
        if content_changed:
            old_content_path = existing.get("content_path")
            merged = _filesystem_chapter_payload(
                merged,
                content,
                preserve_existing_path=not title_changed,
            )
            if title_changed and old_content_path and old_content_path != merged.get("content_path"):
                from app.services.chapter_document_storage import chapter_document_storage
                chapter_document_storage.delete_chapter_file(str(old_content_path))
        elif title_changed and merged.get("content_path"):
            from app.services.chapter_document_storage import chapter_document_storage
            metadata = chapter_document_storage.rename_chapter(
                str(merged["content_path"]),
                str(merged["id"]),
                merged.get("project_id"),
                merged.get("title") or "未命名章节",
            )
            merged.update(metadata)
            merged["content"] = ""
            merged["word_count"] = len(content)
        else:
            merged["word_count"] = len(content)
            if merged.get("content_storage") == "filesystem":
                merged["content"] = ""
        await postgres_db.save_chapter(merged)
        return _hydrate_chapter_content(merged)
    except Exception as e:
        logger.error(f"更新章节失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chapters/{chapter_id}/evaluate", response_model=Dict[str, Any])
async def evaluate_chapter(chapter_id: str):
    """评估章节是否可收尾"""
    from app.api.app import postgres_db
    from app.services.director import DirectorSystem
    from app.services.model_router import create_model_factory
    from app.config import settings

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    chapter = await postgres_db.get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    chapter = _hydrate_chapter_content(chapter)

    try:
        director = DirectorSystem(
            world_data={"id": chapter.get("world_id") or "default_world", "name": "Evaluation World"},
            config={
                "max_turns_threshold": getattr(settings, 'max_turns_threshold', 20),
                "target_word_count_per_intent": getattr(settings, 'target_word_count_per_intent', 2000),
            },
        )
        await director.initialize(create_model_factory(), characters=[])
        director.current_chapter = {
            "id": chapter.get("id"),
            "title": chapter.get("title"),
            "goal": "评估章节",
            "word_count": chapter.get("word_count") or len(chapter.get("content") or ""),
            "status": chapter.get("status", "draft"),
            "content": chapter.get("content") or "",
        }
        director.chapter_events = chapter.get("events") or []
        director.hooks_planted = chapter.get("hooks_planted") or []
        director.main_plot_progress = chapter.get("main_plot_progress") or 0.0

        result = await director.check_chapter_end(chapter_content=chapter.get("content") or "")
        return result
    except Exception as e:
        logger.error(f"评估章节失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"评估失败：{str(e)}")



@router.post("/chapters/{chapter_id}/reader-simulate", response_model=Dict[str, Any])
async def simulate_reader_for_chapter(chapter_id: str):
    """模拟读者阅读体验"""
    from app.api.app import postgres_db
    from app.services.director import DirectorSystem
    from app.services.model_router import create_model_factory
    from app.config import settings

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    chapter = await postgres_db.get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    chapter = _hydrate_chapter_content(chapter)

    try:
        director = DirectorSystem(
            world_data={"id": chapter.get("world_id") or "default_world", "name": "Reader Simulation World"},
            config={
                "max_turns_threshold": getattr(settings, 'max_turns_threshold', 20),
                "target_word_count_per_intent": getattr(settings, 'target_word_count_per_intent', 2000),
            },
        )
        await director.initialize(create_model_factory(), characters=[])
        result = await director.simulate_reader_feedback(
            chapter_content=chapter.get("content") or "",
            chapter_title=chapter.get("title") or "无标题",
        )
        return result
    except Exception as e:
        logger.error(f"模拟读者失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"模拟失败：{str(e)}")


@router.get("/snapshots/diff", response_model=Dict[str, Any])
async def diff_snapshots(left_snapshot_id: str, right_snapshot_id: str):
    """比较两个快照的内容差异"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    left = await postgres_db.get_snapshot(left_snapshot_id)
    right = await postgres_db.get_snapshot(right_snapshot_id)

    if not left or not right:
        raise HTTPException(status_code=404, detail="快照不存在")

    left_lines = json.dumps(left, ensure_ascii=False, indent=2).splitlines()
    right_lines = json.dumps(right, ensure_ascii=False, indent=2).splitlines()
    max_len = max(len(left_lines), len(right_lines))
    lines = []
    summary = {"added": 0, "removed": 0, "unchanged": 0}

    for i in range(max_len):
        left_line = left_lines[i] if i < len(left_lines) else None
        right_line = right_lines[i] if i < len(right_lines) else None
        if left_line is None and right_line is not None:
            lines.append({"type": "added", "content": right_line})
            summary["added"] += 1
        elif right_line is None and left_line is not None:
            lines.append({"type": "removed", "content": left_line})
            summary["removed"] += 1
        elif left_line == right_line:
            lines.append({"type": "unchanged", "content": left_line or ""})
            summary["unchanged"] += 1
        else:
            lines.append({"type": "removed", "content": left_line or ""})
            lines.append({"type": "added", "content": right_line or ""})
            summary["removed"] += 1
            summary["added"] += 1

    return {
        "summary": summary,
        "lines": lines,
        "left_label": left.get("name") or left_snapshot_id,
        "right_label": right.get("name") or right_snapshot_id,
    }


@router.get("/visualization", response_model=Dict[str, Any])
async def get_visualization_data(world_id: str):
    """获取可视化工作台真实数据"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    world = await postgres_db.get_world(world_id)
    if not world:
        raise HTTPException(status_code=404, detail="世界不存在")

    chapters = _hydrate_chapters_content(await postgres_db.get_chapters_by_world(world_id))
    snapshots = await postgres_db.get_snapshots_by_world(world_id)
    project_id = world.get("project_id")
    hooks = await postgres_db.get_all_hooks(
        project_id=str(project_id) if project_id else None,
        world_id=world_id,
        include_inherited=True,
    )

    workflow_nodes = [
        {"id": "director", "label": "Director"},
        {"id": "character", "label": "CharacterAgent"},
        {"id": "plot", "label": "MasterPlotter"},
        {"id": "hook", "label": "HookManager"},
        {"id": "writer", "label": "Writer"},
        {"id": "evaluator", "label": "Evaluator"},
    ]
    workflow_edges = [
        {"source": "director", "target": "character"},
        {"source": "director", "target": "plot"},
        {"source": "director", "target": "hook"},
        {"source": "director", "target": "writer"},
        {"source": "writer", "target": "evaluator"},
    ]

    plot_nodes = [
        {"id": chapter["id"], "label": chapter.get("title") or chapter["id"]}
        for chapter in chapters
    ]
    plot_edges = [
        {"source": plot_nodes[i]["id"], "target": plot_nodes[i + 1]["id"]}
        for i in range(len(plot_nodes) - 1)
    ]

    snapshot_nodes = [
        {
            "id": item["id"],
            "label": item.get("name") or item["id"],
            "parent_snapshot_id": item.get("parent_snapshot_id"),
            "is_branch": item.get("is_branch", False),
        }
        for item in snapshots
    ]
    snapshot_edges = [
        {"source": item["parent_snapshot_id"], "target": item["id"]}
        for item in snapshots
        if item.get("parent_snapshot_id")
    ]

    return {
        "world": world,
        "hooks": hooks,
        "workflow": {"nodes": workflow_nodes, "edges": workflow_edges},
        "plot_tree": {"nodes": plot_nodes, "edges": plot_edges},
        "snapshot_tree": {"nodes": snapshot_nodes, "edges": snapshot_edges},
    }


@router.get("/snapshots/tree", response_model=Dict[str, Any])
async def get_snapshot_tree(world_id: str):
    """获取指定世界的快照树"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    snapshots = await postgres_db.get_snapshots_by_world(world_id)
    node_map = {
        item["id"]: {
            "id": item["id"],
            "name": item.get("name"),
            "snapshot_type": item.get("snapshot_type"),
            "parent_snapshot_id": item.get("parent_snapshot_id"),
            "is_branch": item.get("is_branch", False),
            "branch_reason": item.get("branch_reason"),
            "created_at": item.get("created_at"),
            "children": [],
        }
        for item in snapshots
    }

    roots = []
    for node in node_map.values():
        parent_id = node.get("parent_snapshot_id")
        if parent_id and parent_id in node_map:
            node_map[parent_id]["children"].append(node)
        else:
            roots.append(node)

    return {"success": True, "data": roots}


@router.get("/plots", response_model=List[Dict[str, Any]])
async def list_plots(world_id: Optional[str] = None):
    """
    获取剧情线列表

    Args:
        world_id: 按世界过滤

    Returns:
        List: 剧情线列表
    """
    # 简化实现
    return []


@router.post("/plots", response_model=Dict[str, Any])
async def create_plot(plot: Plot):
    """
    创建新剧情线

    Args:
        plot: 剧情线数据

    Returns:
        Dict: 创建结果
    """
    # 简化实现
    return {
        "success": True,
        "id": plot.id,
        "message": f"剧情线 '{plot.title}' 创建成功",
    }


@router.put("/hooks/{hook_id}", response_model=Dict[str, Any])
async def update_hook(hook_id: str, hook: Hook):
    """
    更新伏笔数据

    Args:
        hook_id: 伏笔 ID
        hook: 新伏笔数据

    Returns:
        Dict: 更新结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    existing = await postgres_db.get_hook(hook_id)
    if not existing:
        raise HTTPException(status_code=404, detail="伏笔不存在")

    hook_data = hook.model_dump(mode="json")
    if hook_data.get("project_id") and hook_data.get("world_id"):
        belongs = await postgres_db.assert_world_belongs_to_project(str(hook_data["world_id"]), str(hook_data["project_id"]))
        if not belongs:
            raise HTTPException(status_code=400, detail="伏笔所属世界不属于当前项目")
    if not hook_data.get("scope_type"):
        hook_data["scope_type"] = "world" if hook_data.get("world_id") else "project"

    # 确保使用正确的 ID 和保留原有的创建时间
    hook_data["id"] = hook_id
    if existing.get("created_at"):
        hook_data["created_at"] = existing["created_at"]

    try:
        await postgres_db.save_hook(hook_data)
        await enqueue_graph_projection_best_effort("hook", hook_data)
        return {
            "success": True,
            "id": hook_id,
            "message": f"伏笔 '{hook.title}' 更新成功",
        }
    except Exception as e:
        logger.error(f"更新伏笔失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/hooks/{hook_id}", response_model=Dict[str, Any])
async def delete_hook(hook_id: str):
    """
    删除伏笔

    Args:
        hook_id: 伏笔 ID

    Returns:
        Dict: 删除结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    query = "DELETE FROM hooks WHERE id = CAST(:id AS UUID)"
    await postgres_db.execute_write(query, {"id": hook_id})

    return {
        "success": True,
        "message": f"伏笔 {hook_id} 已删除",
    }


@router.delete("/chapters/{chapter_id}", response_model=Dict[str, Any])
async def delete_chapter(chapter_id: str):
    """
    删除章节

    Args:
        chapter_id: 章节 ID

    Returns:
        Dict: 删除结果
    """
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    existing = await postgres_db.get_chapter(chapter_id)
    if not existing:
        raise HTTPException(status_code=404, detail="章节不存在")

    archived_path = None
    try:
        from app.services.chapter_document_storage import chapter_document_storage
        archived_path = chapter_document_storage.archive_deleted_chapter_file(existing.get("content_path"))
    except ValueError as exc:
        logger.error("归档删除章节文件路径非法：%s", exc)
        raise HTTPException(status_code=500, detail="章节文件路径非法") from exc

    query = "DELETE FROM chapters WHERE id = CAST(:id AS UUID)"
    await postgres_db.execute_write(query, {"id": chapter_id})

    return {
        "success": True,
        "message": f"章节 {chapter_id} 已删除",
        "archived_content_path": archived_path,
    }


@router.get("/snapshots", response_model=List[Dict[str, Any]])
async def list_snapshots(world_id: Optional[str] = None):
    """获取世界快照列表"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    if world_id:
        return await postgres_db.get_snapshots_by_world(world_id)
    return []


@router.get("/snapshots/{snapshot_id}", response_model=Dict[str, Any])
async def get_snapshot(snapshot_id: str):
    """获取快照详情"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    snapshot = await postgres_db.get_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="快照不存在")
    return snapshot


@router.post("/snapshots", response_model=Dict[str, Any])
async def create_snapshot(snapshot_data: Dict[str, Any]):
    """创建世界快照"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        snapshot_id = await postgres_db.save_snapshot(snapshot_data)
        return {"success": True, "id": snapshot_id, "message": "快照创建成功"}
    except Exception as e:
        logger.error(f"创建快照失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshots/{snapshot_id}/rollback", response_model=Dict[str, Any])
async def rollback_to_snapshot(snapshot_id: str):
    """回档到指定快照"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        result = await postgres_db.rollback_to_snapshot(snapshot_id)
        return {"success": True, "message": "回档成功", "snapshot": result}
    except Exception as e:
        logger.error(f"回档失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/interventions", response_model=List[Dict[str, Any]])
async def list_interventions(limit: int = Query(default=100, le=1000)):
    """获取干预日志列表"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    return await postgres_db.get_intervention_logs(limit)


@router.post("/interventions", response_model=Dict[str, Any])
async def create_intervention(intervention_data: Dict[str, Any]):
    """创建干预日志"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    try:
        log_id = await postgres_db.log_intervention(intervention_data)
        return {"success": True, "id": log_id, "message": "干预日志记录成功"}
    except Exception as e:
        logger.error(f"记录干预日志失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/interventions/{intervention_id}/evaluation", response_model=Dict[str, Any])
async def update_intervention_evaluation(intervention_id: str, evaluation_data: Dict[str, Any]):
    """更新干预效果评估"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    intervention_logs = await postgres_db.get_intervention_logs(limit=1000)
    intervention = next((item for item in intervention_logs if item.get("id") == intervention_id), None)
    if not intervention:
        raise HTTPException(status_code=404, detail="干预记录不存在")

    try:
        await postgres_db.update_intervention_evaluation(
            intervention_id=intervention_id,
            outcome_rating=evaluation_data.get("outcome_rating"),
            outcome_notes=evaluation_data.get("outcome_notes"),
        )
        updated = {**intervention, **evaluation_data}
        return {"success": True, "data": updated}
    except Exception as e:
        logger.error(f"更新干预评估失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/interventions/{intervention_id}", response_model=Dict[str, Any])
async def delete_intervention(intervention_id: str):
    """删除干预记录"""
    from app.api.app import postgres_db

    if not postgres_db:
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 检查是否存在
    intervention_logs = await postgres_db.get_intervention_logs(limit=1000)
    intervention = next((item for item in intervention_logs if item.get("id") == intervention_id), None)
    if not intervention:
        raise HTTPException(status_code=404, detail="干预记录不存在")

    try:
        await postgres_db.delete_intervention_log(intervention_id)
        return {"success": True, "message": "干预记录已删除", "deleted_id": intervention_id}
    except Exception as e:
        logger.error(f"删除干预记录失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))
