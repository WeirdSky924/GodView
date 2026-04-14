"""
黄金三章规则配置 API
GodView v9: 开局质量保障系统

管理黄金三章规则的配置和检测
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from app.models.golden_three import (
    GoldenThreeRuleType,
    RuleSeverity,
    GoldenThreeRule,
    GoldenThreeCheckResult,
    CreateGoldenThreeRuleDTO,
    UpdateGoldenThreeRuleDTO,
)
from app.services.golden_three_service import GoldenThreeService

router = APIRouter(prefix="/api/golden-three-rules", tags=["Golden Three Rules"])

# 服务实例
_service: Optional[GoldenThreeService] = None


def get_service() -> GoldenThreeService:
    """获取服务实例"""
    global _service
    if _service is None:
        _service = GoldenThreeService()
    return _service


def set_service(service: GoldenThreeService):
    """设置服务实例"""
    global _service
    _service = service


# ==================== 规则管理 ====================

@router.get("", response_model=List[GoldenThreeRule])
async def list_rules(
    rule_type: Optional[GoldenThreeRuleType] = Query(None, description="规则类型过滤"),
    chapter: Optional[int] = Query(None, ge=1, le=3, description="章节过滤"),
    genre: Optional[str] = Query(None, description="题材过滤"),
    active_only: bool = Query(True, description="只返回启用的规则")
):
    """获取规则列表"""
    service = get_service()
    rules = await service.get_rules(rule_type, chapter, genre, active_only)
    return rules


@router.get("/types")
async def get_rule_types():
    """获取规则类型列表"""
    return {
        "types": [
            {"value": "hook", "label": "钩子规则", "description": "开篇吸引力相关规则"},
            {"value": "conflict", "label": "冲突规则", "description": "冲突设置相关规则"},
            {"value": "protagonist", "label": "主角规则", "description": "主角塑造相关规则"},
        ],
        "severities": [
            {"value": "critical", "label": "必须", "description": "必须满足的规则"},
            {"value": "important", "label": "重要", "description": "重要的建议规则"},
            {"value": "optional", "label": "可选", "description": "可选的优化规则"},
        ]
    }


@router.get("/{rule_id}", response_model=GoldenThreeRule)
async def get_rule(rule_id: str):
    """获取规则详情"""
    service = get_service()
    rule = await service.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


@router.post("", response_model=GoldenThreeRule)
async def create_rule(data: CreateGoldenThreeRuleDTO):
    """创建规则"""
    service = get_service()
    rule = await service.create_rule(data)
    return rule


@router.put("/{rule_id}", response_model=GoldenThreeRule)
async def update_rule(rule_id: str, data: UpdateGoldenThreeRuleDTO):
    """更新规则"""
    service = get_service()
    rule = await service.update_rule(rule_id, data)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    """删除规则"""
    service = get_service()
    success = await service.delete_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"success": True, "message": "规则已删除"}


# ==================== 检测功能 ====================

@router.post("/check/chapter", response_model=Dict[str, Any])
async def check_chapter(
    project_id: str = Query(..., description="项目ID"),
    chapter_number: int = Query(..., ge=1, le=3, description="章节号(1-3)"),
    content: str = Query(..., description="章节内容"),
    genre: Optional[str] = Query(None, description="题材类型")
):
    """检测单章"""
    service = get_service()
    result = await service.check_chapter(project_id, chapter_number, content, genre)
    return result


@router.post("/check/golden-three", response_model=GoldenThreeCheckResult)
async def check_golden_three(
    project_id: str = Query(..., description="项目ID"),
    genre: Optional[str] = Query(None, description="题材类型"),
    chapter1: str = Query("", description="第一章内容"),
    chapter2: str = Query("", description="第二章内容"),
    chapter3: str = Query("", description="第三章内容")
):
    """检测黄金三章"""
    service = get_service()

    chapters = {}
    if chapter1:
        chapters[1] = chapter1
    if chapter2:
        chapters[2] = chapter2
    if chapter3:
        chapters[3] = chapter3

    if not chapters:
        raise HTTPException(status_code=400, detail="请至少提供一章内容")

    result = await service.check_golden_three(project_id, chapters, genre)
    return result


# ==================== 规则统计 ====================

@router.get("/stats/summary")
async def get_rules_summary():
    """获取规则统计摘要"""
    service = get_service()
    rules = await service.get_rules(active_only=False)

    by_type = {}
    by_severity = {}
    active_count = 0

    for rule in rules:
        # 按类型统计
        type_key = rule.rule_type.value
        by_type[type_key] = by_type.get(type_key, 0) + 1

        # 按严重程度统计
        severity_key = rule.severity.value
        by_severity[severity_key] = by_severity.get(severity_key, 0) + 1

        # 活跃规则数
        if rule.is_active:
            active_count += 1

    return {
        "total_rules": len(rules),
        "active_rules": active_count,
        "by_type": by_type,
        "by_severity": by_severity
    }
