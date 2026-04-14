"""
质量检测 API 路由
封装已有 Skills 的调用，提供质量检测相关接口
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.skill_service import get_skill_service, ExecuteSkillDTO

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class GoldenThreeCheckRequest(BaseModel):
    """黄金三章检测请求"""
    project_id: str
    chapter1_content: str = Field(..., description="第一章内容")
    chapter2_content: str = Field(..., description="第二章内容")
    chapter3_content: str = Field(..., description="第三章内容")
    world_intro: Optional[str] = Field(None, description="世界观简介")


class GoldenThreeCheckResponse(BaseModel):
    """黄金三章检测响应"""
    success: bool
    opening_analysis: Dict[str, Any]
    chapter_scores: Dict[str, Any]
    golden_rules: Dict[str, Any]
    reader_retention_prediction: str
    improvement_suggestions: List[str]
    overall_score: int


class SatisfactionAnalysisRequest(BaseModel):
    """爽点分析请求"""
    project_id: str
    chapter_content: str = Field(..., description="章节内容")


class SatisfactionAnalysisResponse(BaseModel):
    """爽点分析响应"""
    success: bool
    cool_points: List[Dict[str, Any]]
    density_analysis: Dict[str, Any]
    overall_assessment: str
    suggestions: List[str]


class ConsistencyCheckRequest(BaseModel):
    """一致性检测请求"""
    project_id: str
    chapter_content: str = Field(..., description="章节内容")
    world_settings: Optional[str] = Field(None, description="世界观设定")
    character_settings: Optional[str] = Field(None, description="角色设定")
    ability_settings: Optional[str] = Field(None, description="能力设定")


class ConsistencyCheckResponse(BaseModel):
    """一致性检测响应"""
    success: bool
    conflicts: List[Dict[str, Any]]
    setting_gaps: List[Dict[str, Any]]
    consistency_score: int
    risk_areas: List[str]


class PlotHoleCheckRequest(BaseModel):
    """剧情漏洞检测请求"""
    project_id: str
    chapter_content: str = Field(..., description="章节内容")
    previous_context: Optional[str] = Field(None, description="前文关键信息")
    world_settings: Optional[str] = Field(None, description="世界观设定")


class PlotHoleCheckResponse(BaseModel):
    """剧情漏洞检测响应"""
    success: bool
    plot_holes: List[Dict[str, Any]]
    logic_issues: List[str]
    overall_quality: str
    risk_level: str


class CharacterMemoryCheckRequest(BaseModel):
    """角色记忆一致性检查请求"""
    project_id: str
    character_name: str
    chapter_content: str
    character_profile: Optional[str] = None
    character_history: Optional[str] = None


class CharacterMemoryCheckResponse(BaseModel):
    """角色记忆一致性检查响应"""
    success: bool
    memory_issues: List[Dict[str, Any]]
    consistency_score: int
    character_authenticity: str
    warnings: List[str]


class PowerLevelCheckRequest(BaseModel):
    """战力体系校验请求"""
    project_id: str
    chapter_content: str
    power_system: Optional[str] = None
    character_power: Optional[str] = None
    previous_battles: Optional[str] = None


class PowerLevelCheckResponse(BaseModel):
    """战力体系校验响应"""
    success: bool
    power_issues: List[Dict[str, Any]]
    battle_analysis: List[Dict[str, Any]]
    power_balance_score: int
    collapse_risk: str
    warnings: List[str]


class PacingAnalysisRequest(BaseModel):
    """节奏分析请求"""
    project_id: str
    chapter_content: str
    target_words: Optional[int] = None


class PacingAnalysisResponse(BaseModel):
    """节奏分析响应"""
    success: bool
    pacing_score: int
    pacing_status: str
    sections_analysis: List[Dict[str, Any]]
    water_content: Dict[str, Any]
    rhythm_curve: List[str]
    improvement_suggestions: List[str]


class DialogueStyleCheckRequest(BaseModel):
    """对话风格一致性检查请求"""
    project_id: str
    character_name: str
    dialogue_content: str
    personality: Optional[str] = None
    speaking_style: Optional[str] = None
    catchphrases: Optional[str] = None
    forbidden_words: Optional[str] = None


class DialogueStyleCheckResponse(BaseModel):
    """对话风格一致性检查响应"""
    success: bool
    dialogue_analysis: List[Dict[str, Any]]
    character_voice_score: int
    uniqueness_score: int
    ooc_warnings: List[str]
    style_suggestions: str


# ==================== API 端点 ====================

@router.post("/golden-three", response_model=GoldenThreeCheckResponse)
async def check_golden_three_chapters(request: GoldenThreeCheckRequest):
    """
    黄金三章检测

    分析开篇前三章是否足够吸引读者
    """
    skill_service = get_skill_service()

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_golden_three_chapters",
        project_id=request.project_id,
        parameters={
            "chapter1": request.chapter1_content,
            "chapter2": request.chapter2_content,
            "chapter3": request.chapter3_content,
            "world_intro": request.world_intro or "",
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    import json
    try:
        data = json.loads(result.output)
        return GoldenThreeCheckResponse(
            success=True,
            opening_analysis=data.get("opening_analysis", {}),
            chapter_scores=data.get("chapter_scores", {}),
            golden_rules=data.get("golden_rules", {}),
            reader_retention_prediction=data.get("reader_retention_prediction", "中"),
            improvement_suggestions=data.get("improvement_suggestions", []),
            overall_score=data.get("overall_score", 0),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="解析检测结果失败")


@router.post("/satisfaction", response_model=SatisfactionAnalysisResponse)
async def analyze_satisfaction(request: SatisfactionAnalysisRequest):
    """
    爽点分析

    分析章节中的爽点密度、类型和质量
    """
    skill_service = get_skill_service()

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_cool_point_detection",
        project_id=request.project_id,
        parameters={
            "chapter_content": request.chapter_content,
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    import json
    try:
        data = json.loads(result.output)
        return SatisfactionAnalysisResponse(
            success=True,
            cool_points=data.get("cool_points", []),
            density_analysis=data.get("density_analysis", {}),
            overall_assessment=data.get("overall_assessment", ""),
            suggestions=data.get("suggestions", []),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="解析检测结果失败")


@router.post("/consistency", response_model=ConsistencyCheckResponse)
async def check_consistency(request: ConsistencyCheckRequest):
    """
    设定一致性检测

    检测世界观、角色、能力等设定之间是否存在矛盾冲突
    """
    skill_service = get_skill_service()

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_setting_conflict_detection",
        project_id=request.project_id,
        parameters={
            "chapter_content": request.chapter_content,
            "world_settings": request.world_settings or "",
            "character_settings": request.character_settings or "",
            "ability_settings": request.ability_settings or "",
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    import json
    try:
        data = json.loads(result.output)
        return ConsistencyCheckResponse(
            success=True,
            conflicts=data.get("conflicts", []),
            setting_gaps=data.get("setting_gaps", []),
            consistency_score=data.get("consistency_score", 0),
            risk_areas=data.get("risk_areas", []),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="解析检测结果失败")


@router.post("/plot-hole", response_model=PlotHoleCheckResponse)
async def check_plot_hole(request: PlotHoleCheckRequest):
    """
    剧情漏洞检测

    检测章节中的逻辑问题、前后矛盾、设定冲突等剧情漏洞
    """
    skill_service = get_skill_service()

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_plot_hole_detection",
        project_id=request.project_id,
        parameters={
            "chapter_content": request.chapter_content,
            "previous_context": request.previous_context or "",
            "world_settings": request.world_settings or "",
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    import json
    try:
        data = json.loads(result.output)
        return PlotHoleCheckResponse(
            success=True,
            plot_holes=data.get("plot_holes", []),
            logic_issues=data.get("logic_issues", []),
            overall_quality=data.get("overall_quality", ""),
            risk_level=data.get("risk_level", "low"),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="解析检测结果失败")


@router.post("/character-memory", response_model=CharacterMemoryCheckResponse)
async def check_character_memory(request: CharacterMemoryCheckRequest):
    """
    角色记忆一致性检查

    检查角色是否记得之前发生的事、认识的人，确保角色行为连贯
    """
    skill_service = get_skill_service()

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_character_memory_check",
        project_id=request.project_id,
        parameters={
            "character_name": request.character_name,
            "chapter_content": request.chapter_content,
            "character_profile": request.character_profile or "",
            "character_history": request.character_history or "",
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    import json
    try:
        data = json.loads(result.output)
        return CharacterMemoryCheckResponse(
            success=True,
            memory_issues=data.get("memory_issues", []),
            consistency_score=data.get("consistency_score", 0),
            character_authenticity=data.get("character_authenticity", ""),
            warnings=data.get("warnings", []),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="解析检测结果失败")


@router.post("/power-level", response_model=PowerLevelCheckResponse)
async def check_power_level(request: PowerLevelCheckRequest):
    """
    战力体系校验

    检测战力是否崩坏，战斗力描述是否合理
    """
    skill_service = get_skill_service()

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_power_level_check",
        project_id=request.project_id,
        parameters={
            "chapter_content": request.chapter_content,
            "power_system": request.power_system or "",
            "character_power": request.character_power or "",
            "previous_battles": request.previous_battles or "",
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    import json
    try:
        data = json.loads(result.output)
        return PowerLevelCheckResponse(
            success=True,
            power_issues=data.get("power_issues", []),
            battle_analysis=data.get("battle_analysis", []),
            power_balance_score=data.get("power_balance_score", 0),
            collapse_risk=data.get("collapse_risk", "low"),
            warnings=data.get("warnings", []),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="解析检测结果失败")


@router.post("/pacing", response_model=PacingAnalysisResponse)
async def analyze_pacing(request: PacingAnalysisRequest):
    """
    节奏分析

    分析章节节奏，检测是否过快或拖沓，识别注水内容
    """
    skill_service = get_skill_service()

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_pacing_analysis",
        project_id=request.project_id,
        parameters={
            "chapter_content": request.chapter_content,
            "target_words": request.target_words or 2000,
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    import json
    try:
        data = json.loads(result.output)
        return PacingAnalysisResponse(
            success=True,
            pacing_score=data.get("pacing_score", 0),
            pacing_status=data.get("pacing_status", "适中"),
            sections_analysis=data.get("sections_analysis", []),
            water_content=data.get("water_content", {}),
            rhythm_curve=data.get("rhythm_curve", []),
            improvement_suggestions=data.get("improvement_suggestions", []),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="解析检测结果失败")


@router.post("/dialogue-style", response_model=DialogueStyleCheckResponse)
async def check_dialogue_style(request: DialogueStyleCheckRequest):
    """
    对话风格一致性检查

    检查角色对话是否符合其性格和说话风格，确保角色声音独特
    """
    skill_service = get_skill_service()

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_dialogue_style_check",
        project_id=request.project_id,
        parameters={
            "character_name": request.character_name,
            "dialogue_content": request.dialogue_content,
            "personality": request.personality or "",
            "speaking_style": request.speaking_style or "",
            "catchphrases": request.catchphrases or "",
            "forbidden_words": request.forbidden_words or "",
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    import json
    try:
        data = json.loads(result.output)
        return DialogueStyleCheckResponse(
            success=True,
            dialogue_analysis=data.get("dialogue_analysis", []),
            character_voice_score=data.get("character_voice_score", 0),
            uniqueness_score=data.get("uniqueness_score", 0),
            ooc_warnings=data.get("ooc_warnings", []),
            style_suggestions=data.get("style_suggestions", ""),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="解析检测结果失败")


# ==================== 开局设计 API ====================

class OpeningDesignRequest(BaseModel):
    """开局设计请求"""
    project_id: str
    genre: Optional[str] = Field(None, description="题材类型（玄幻/都市/仙侠等）")
    protagonist_name: Optional[str] = Field(None, description="主角姓名")
    protagonist_background: Optional[str] = Field(None, description="主角背景")
    world_setting: Optional[str] = Field(None, description="世界观设定")
    golden_finger_type: Optional[str] = Field(None, description="金手指类型偏好（system/spatial/rebirth/talent/inheritance/artifact）")


class OpeningDesignResponse(BaseModel):
    """开局设计响应"""
    success: bool
    golden_finger: Dict[str, Any]
    protagonist_design: Dict[str, Any]
    opening_conflict: Dict[str, Any]
    goals: Dict[str, Any]
    first_chapter_outline: Dict[str, Any]
    suggestions: List[str]


@router.post("/opening-design", response_model=OpeningDesignResponse)
async def design_opening(request: OpeningDesignRequest):
    """
    开局设计

    为小说开局生成完整的设计方案，包括金手指、主角吸引力、冲突设计、目标设定
    """
    skill_service = get_skill_service()

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_opening_design",
        project_id=request.project_id,
        parameters={
            "genre": request.genre or "玄幻",
            "protagonist_name": request.protagonist_name or "主角",
            "protagonist_background": request.protagonist_background or "",
            "world_setting": request.world_setting or "",
            "golden_finger_type": request.golden_finger_type or "",
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    import json
    try:
        data = json.loads(result.output)
        return OpeningDesignResponse(
            success=True,
            golden_finger=data.get("golden_finger", {}),
            protagonist_design=data.get("protagonist_design", {}),
            opening_conflict=data.get("opening_conflict", {}),
            goals=data.get("goals", {}),
            first_chapter_outline=data.get("first_chapter_outline", {}),
            suggestions=data.get("suggestions", []),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="解析设计结果失败")


class GoldenFingerSuggestionRequest(BaseModel):
    """金手指建议请求"""
    project_id: str
    protagonist_traits: str = Field(..., description="主角特质")
    story_theme: str = Field(..., description="故事主题")


class GoldenFingerSuggestionResponse(BaseModel):
    """金手指建议响应"""
    success: bool
    suggestions: List[Dict[str, Any]]
    recommended: Dict[str, Any]


@router.post("/golden-finger-suggest", response_model=GoldenFingerSuggestionResponse)
async def suggest_golden_finger(request: GoldenFingerSuggestionRequest):
    """
    金手指建议

    根据主角特质和故事主题推荐合适的金手指类型
    """
    skill_service = get_skill_service()

    result = await skill_service.execute_skill(ExecuteSkillDTO(
        skill_id="skill_opening_design",
        project_id=request.project_id,
        parameters={
            "task": "golden_finger_suggest",
            "protagonist_traits": request.protagonist_traits,
            "story_theme": request.story_theme,
        }
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    import json
    try:
        data = json.loads(result.output)
        return GoldenFingerSuggestionResponse(
            success=True,
            suggestions=data.get("suggestions", []),
            recommended=data.get("recommended", {}),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="解析建议失败")


@router.get("/skills")
async def list_quality_skills():
    """
    列出所有可用的质量检测 Skills
    """
    return {
        "skills": [
            {
                "id": "skill_golden_three_chapters",
                "name": "黄金三章检测",
                "description": "分析开篇前三章是否足够吸引读者",
                "category": "evaluation",
            },
            {
                "id": "skill_cool_point_detection",
                "name": "爽点检测与分析",
                "description": "分析章节中的爽点密度、类型和质量",
                "category": "evaluation",
            },
            {
                "id": "skill_setting_conflict_detection",
                "name": "设定冲突检测",
                "description": "检测设定之间是否存在矛盾冲突",
                "category": "setting",
            },
            {
                "id": "skill_plot_hole_detection",
                "name": "剧情漏洞检测",
                "description": "检测章节中的逻辑问题、前后矛盾",
                "category": "evaluation",
            },
            {
                "id": "skill_character_memory_check",
                "name": "角色记忆一致性检查",
                "description": "检查角色行为是否连贯",
                "category": "character",
            },
            {
                "id": "skill_power_level_check",
                "name": "战力体系校验",
                "description": "检测战力是否崩坏",
                "category": "evaluation",
            },
            {
                "id": "skill_pacing_analysis",
                "name": "节奏分析",
                "description": "分析章节节奏，识别注水内容",
                "category": "pacing",
            },
            {
                "id": "skill_dialogue_style_check",
                "name": "对话风格一致性检查",
                "description": "检查角色对话是否符合人设",
                "category": "dialogue",
            },
            {
                "id": "skill_foreshadowing_tracker",
                "name": "伏笔追踪与提醒",
                "description": "追踪已埋下的伏笔，提醒需要回收的伏笔",
                "category": "foreshadowing",
            },
            {
                "id": "skill_timeline_verification",
                "name": "时间线校验",
                "description": "校验事件时间顺序是否合理",
                "category": "analysis",
            },
            {
                "id": "skill_opening_design",
                "name": "开局设计",
                "description": "设计小说开局的金手指、冲突、目标等核心元素",
                "category": "design",
            },
            {
                "id": "skill_villain_management",
                "name": "反派与冲突管理",
                "description": "设计反派层级、冲突线和升级机制",
                "category": "planning",
            },
        ]
    }
