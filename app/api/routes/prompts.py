"""
Prompt 模板管理 API 路由
v7 核心需求：Prompt 模板的 CRUD 操作、搜索、分类、渲染预览
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.prompt_template import (
    PromptCategory,
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptFilter,
    PromptRenderRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局服务实例
_prompt_service = None


def get_prompt_service():
    """获取 Prompt 服务实例"""
    global _prompt_service
    if _prompt_service is None:
        from app.services.prompt_template_service import PromptTemplateService
        _prompt_service = PromptTemplateService()
    return _prompt_service


def set_prompt_service(service):
    """设置 Prompt 服务实例（用于初始化）"""
    global _prompt_service
    _prompt_service = service


# ==================== Prompt CRUD API ====================

@router.get("/prompts", response_model=List[Dict[str, Any]])
async def list_prompts(
    category: Optional[str] = Query(default=None, description="按分类过滤"),
    tags: Optional[List[str]] = Query(default=None, description="按标签过滤"),
    is_system: Optional[bool] = Query(default=None, description="是否系统内置"),
    search: Optional[str] = Query(default=None, description="搜索关键词"),
    limit: int = Query(default=50, le=500, description="返回数量限制"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
):
    """
    获取 Prompt 模板列表

    Args:
        category: 分类过滤
        tags: 标签过滤（任一匹配）
        is_system: 系统内置过滤
        search: 搜索关键词
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        List: Prompt 模板列表
    """
    service = get_prompt_service()

    # 构建过滤条件
    category_enum = None
    if category:
        try:
            category_enum = PromptCategory(category)
        except ValueError:
            pass  # 忽略无效的分类值

    filters = PromptFilter(
        category=category_enum,
        tags=tags,
        is_system=is_system,
        search=search,
        limit=limit,
        offset=offset,
    )

    try:
        templates = await service.list_templates(filters)
        return [t.dict() for t in templates]
    except Exception as e:
        logger.error(f"获取 Prompt 列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prompts", response_model=Dict[str, Any])
async def create_prompt(request: PromptTemplateCreate):
    """
    创建 Prompt 模板

    Args:
        request: 创建请求

    Returns:
        Dict: 创建结果
    """
    service = get_prompt_service()

    try:
        template = await service.create_template(request)
        return {
            "success": True,
            "message": "Prompt 模板创建成功",
            "template": template.dict(),
        }
    except Exception as e:
        logger.error(f"创建 Prompt 模板失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 注意：/prompts/categories-list 避免与 /prompts/{prompt_id} 冲突

@router.get("/prompts/categories-list", response_model=Dict[str, int])
async def get_categories():
    """
    获取分类统计信息

    Returns:
        Dict: 分类名称 -> 数量
    """
    service = get_prompt_service()

    try:
        categories = await service.get_categories()
        return categories
    except Exception as e:
        logger.error(f"获取分类统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompts/audit/agent-template-resolution", response_model=Dict[str, Any])
async def audit_agent_template_prompt_resolution():
    """Dry-run 系统 AgentTemplate 的 prompt slot 解析，不调用 LLM。"""
    try:
        from app.services.agent_prompt_service import get_agent_prompt_service

        result = await get_agent_prompt_service().audit_system_agent_template_prompt_resolution()
        return result
    except Exception as e:
        logger.error(f"审计 Agent Template Prompt 解析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== MD 文件同步 API ====================

@router.post("/prompts/sync-md-files", response_model=Dict[str, Any])
async def sync_md_files():
    """
    将 prompts/ 目录下的 MD 文件同步到数据库

    这个API会：
    1. 扫描 prompts/ 目录下的所有 MD 文件
    2. 提取 YAML frontmatter 作为元数据
    3. 将元数据存入数据库（内容从 MD 文件读取）

    Returns:
        Dict: 同步结果统计
    """
    service = get_prompt_service()

    try:
        result = await service.sync_md_files_to_db()
        return {
            "success": True,
            "message": f"同步完成: {result.get('synced', 0)} 个成功",
            "result": result,
        }
    except Exception as e:
        logger.error(f"同步 MD 文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompts/md-stats", response_model=Dict[str, Any])
async def get_md_stats():
    """
    获取 MD 文件统计信息

    Returns:
        Dict: MD 文件统计
    """
    try:
        from app.services.md_file_service import get_md_file_service
        md_service = get_md_file_service()
        stats = md_service.get_stats()
        return stats
    except Exception as e:
        logger.error(f"获取 MD 文件统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/prompts/{prompt_id}", response_model=Dict[str, Any])
async def get_prompt(prompt_id: str):
    """
    获取 Prompt 模板详情

    Args:
        prompt_id: Prompt ID

    Returns:
        Dict: Prompt 模板详情
    """
    service = get_prompt_service()

    template = await service.get_template(prompt_id)
    if not template:
        raise HTTPException(status_code=404, detail="Prompt 模板不存在")

    return template.dict()


@router.put("/prompts/{prompt_id}", response_model=Dict[str, Any])
async def update_prompt(prompt_id: str, request: PromptTemplateUpdate):
    """
    更新 Prompt 模板

    Args:
        prompt_id: Prompt ID
        request: 更新请求

    Returns:
        Dict: 更新结果
    """
    service = get_prompt_service()

    template, error = await service.update_template(prompt_id, request)
    if error == 'not_found':
        raise HTTPException(status_code=404, detail="Prompt 模板不存在")
    if error == 'is_system':
        raise HTTPException(status_code=403, detail="系统内置模板不可修改")

    return {
        "success": True,
        "message": f"Prompt 模板 {prompt_id} 更新成功",
        "template": template.dict(),
    }


@router.delete("/prompts/{prompt_id}", response_model=Dict[str, Any])
async def delete_prompt(prompt_id: str):
    """
    删除 Prompt 模板

    Args:
        prompt_id: Prompt ID

    Returns:
        Dict: 删除结果
    """
    service = get_prompt_service()

    success, error = await service.delete_template(prompt_id)
    if error == 'not_found':
        raise HTTPException(status_code=404, detail="Prompt 模板不存在")
    if error == 'is_system':
        raise HTTPException(status_code=403, detail="系统内置模板不可删除")

    return {
        "success": True,
        "message": f"Prompt 模板 {prompt_id} 删除成功",
    }


@router.post("/prompts/search", response_model=List[Dict[str, Any]])
async def search_prompts(
    query: str = Query(..., description="搜索关键词"),
    category: Optional[str] = Query(default=None, description="分类过滤"),
    limit: int = Query(default=50, le=500, description="返回数量限制"),
):
    """
    搜索 Prompt 模板

    Args:
        query: 搜索关键词
        category: 分类过滤
        limit: 返回数量限制

    Returns:
        List: 搜索结果列表
    """
    service = get_prompt_service()

    category_enum = None
    if category:
        try:
            category_enum = PromptCategory(category)
        except ValueError:
            pass  # 忽略无效的分类值

    try:
        templates = await service.search_templates(
            query=query,
            category=category_enum,
            limit=limit,
        )
        return [t.dict() for t in templates]
    except Exception as e:
        logger.error(f"搜索 Prompt 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prompts/{prompt_id}/render", response_model=Dict[str, Any])
async def render_prompt(
    prompt_id: str,
    variables: Optional[Dict[str, Any]] = None,
):
    """
    渲染 Preview Prompt 模板

    Args:
        prompt_id: Prompt ID
        variables: 变量值 (请求体)

    Returns:
        Dict: 渲染结果
    """
    service = get_prompt_service()

    request = PromptRenderRequest(
        template_id=prompt_id,
        variables=variables or {},
    )

    try:
        result = await service.render_template(request)
        return result.dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"渲染 Prompt 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
