"""
章节大纲服务
GodView v9: PlotOutlineAgent 专用

负责章节大纲的生成、管理和存储
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.chapter_outline import (
    ChapterOutline,
    ChapterOutlineStatus,
    CreateChapterOutlineDTO,
    EmotionCurve,
    EmotionPoint,
    EmotionType,
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    SceneOutline,
    SceneType,
    ConflictLevel,
    UpdateChapterOutlineDTO,
    ValidateOutlineRequest,
    ValidateOutlineResponse,
)
from app.models.plot import Hook, HookStatus, HookType

logger = logging.getLogger(__name__)


class PlotOutlineService:
    """章节大纲服务"""

    def __init__(self, db=None, skill_service=None, prompt_service=None):
        """
        初始化章节大纲服务

        Args:
            db: 数据库连接
            skill_service: Skill 服务（用于调用大纲生成 Skill）
            prompt_service: Prompt 模板服务
        """
        self._db = db
        self._skill_service = skill_service
        self._prompt_service = prompt_service

        # 内存缓存
        self._outlines_cache: Dict[str, ChapterOutline] = {}
        self._cache_valid: bool = False

        # 获取 LLM 配置
        from app.config import settings
        self._llm_provider = settings.llm_provider
        llm_config = settings.get_llm_config(self._llm_provider)
        self._llm_api_key = llm_config.get("api_key", "")
        self._llm_base_url = llm_config.get("base_url", "")
        self._llm_model = llm_config.get("model", "")
        self._llm_temperature = llm_config.get("temperature", 0.7)
        self._llm_max_tokens = llm_config.get("max_tokens", 4096)

        logger.info(f"[PlotOutlineService] LLM 配置 - Provider: {self._llm_provider}, Model: {self._llm_model}, Base: {self._llm_base_url}")

    async def _ensure_cache(self, project_id: str):
        """确保缓存有效"""
        cache_key = f"project_{project_id}"
        if self._cache_valid and cache_key in self._outlines_cache:
            return

        if self._db:
            try:
                rows = await self._db.execute_query(
                    "SELECT * FROM chapter_outlines WHERE project_id = :project_id ORDER BY chapter_number",
                    {"project_id": project_id}
                )
                for row in rows:
                    outline = self._row_to_outline(row)
                    self._outlines_cache[outline.id] = outline
                self._cache_valid = True
                logger.info(f"从数据库加载 {len(rows)} 个章节大纲")
            except Exception as e:
                logger.warning(f"从数据库加载章节大纲失败: {e}")

    def _row_to_outline(self, row: Dict) -> ChapterOutline:
        """将数据库行转换为章节大纲对象"""
        # 处理 JSON 字段（可能已经是 dict/list，也可能需要 json.loads）
        def parse_json(value, default=None):
            if value is None:
                return default
            if isinstance(value, (dict, list)):
                return value
            if isinstance(value, str):
                return json.loads(value)
            return default

        return ChapterOutline(
            id=row['id'],
            project_id=row['project_id'],
            chapter_number=row['chapter_number'],
            title=row['title'],
            summary=row['summary'],
            status=ChapterOutlineStatus(row['status']),
            scenes=[SceneOutline(**s) for s in parse_json(row.get('scenes'), [])],
            emotion_curve=None,  # 暂时跳过，数据库格式与模型不匹配
            # emotion_curve=EmotionCurve(**parse_json(row.get('emotion_curve'), {})) if row.get('emotion_curve') else None,
            chapter_goals=parse_json(row.get('chapter_goals'), []),
            plot_advancement=row.get('plot_advancement'),
            character_arcs=parse_json(row.get('character_arcs'), {}),
            hooks_planted=parse_json(row.get('hooks_planted'), []),
            hooks_resolved=parse_json(row.get('hooks_resolved'), []),
            quality_metrics=parse_json(row.get('quality_metrics'), {}),
            target_word_count=row.get('target_word_count', 3000),
            estimated_word_count=row.get('estimated_word_count', 0),
            created_at=row.get('created_at', datetime.now()),
            updated_at=row.get('updated_at', datetime.now()),
            approved_at=row.get('approved_at'),
            approved_by=row.get('approved_by'),
            previous_outline_id=row.get('previous_outline_id'),
            next_outline_id=row.get('next_outline_id'),
        )

    async def create_outline(self, dto: CreateChapterOutlineDTO) -> ChapterOutline:
        """
        创建章节大纲

        Args:
            dto: 创建请求

        Returns:
            ChapterOutline: 创建的大纲
        """
        outline = ChapterOutline(
            id=f"outline_{uuid.uuid4().hex[:8]}",
            project_id=dto.project_id,
            chapter_number=dto.chapter_number,
            title=dto.title,
            summary=dto.summary,
            scenes=dto.scenes or [],
            chapter_goals=dto.chapter_goals,
            hooks_planted=dto.hooks_planted or [],
            hooks_resolved=dto.hooks_resolved or [],
            target_word_count=dto.target_word_count,
        )

        # 保存到数据库
        if self._db:
            try:
                await self._db.execute_write(
                    """
                    INSERT INTO chapter_outlines
                    (id, project_id, chapter_number, title, summary, scenes, chapter_goals,
                     hooks_planted, hooks_resolved, target_word_count, status, created_at, updated_at)
                    VALUES (:id, :project_id, :chapter_number, :title, :summary, :scenes, :chapter_goals,
                     :hooks_planted, :hooks_resolved, :target_word_count, :status, :created_at, :updated_at)
                    """,
                    {
                        "id": outline.id,
                        "project_id": outline.project_id,
                        "chapter_number": outline.chapter_number,
                        "title": outline.title,
                        "summary": outline.summary,
                        "scenes": json.dumps([s.model_dump() for s in outline.scenes]) if outline.scenes else "[]",
                        "chapter_goals": json.dumps(outline.chapter_goals),
                        "hooks_planted": json.dumps(outline.hooks_planted),
                        "hooks_resolved": json.dumps(outline.hooks_resolved),
                        "target_word_count": outline.target_word_count,
                        "status": outline.status.value,
                        "created_at": outline.created_at,
                        "updated_at": outline.updated_at,
                    }
                )
                logger.info(f"创建章节大纲: {outline.id}")
            except Exception as e:
                logger.error(f"保存章节大纲失败: {e}")

        self._outlines_cache[outline.id] = outline
        return outline

    async def get_outline(self, project_id: str, chapter_number: int) -> Optional[ChapterOutline]:
        """
        获取指定章节的大纲

        Args:
            project_id: 项目ID
            chapter_number: 章节号

        Returns:
            ChapterOutline 或 None
        """
        await self._ensure_cache(project_id)

        for outline in self._outlines_cache.values():
            if outline.project_id == project_id and outline.chapter_number == chapter_number:
                return outline

        return None

    async def get_outlines_by_project(self, project_id: str) -> List[ChapterOutline]:
        """
        获取项目的所有章节大纲

        Args:
            project_id: 项目ID

        Returns:
            List[ChapterOutline]: 章节大纲列表
        """
        await self._ensure_cache(project_id)

        outlines = [
            o for o in self._outlines_cache.values()
            if o.project_id == project_id
        ]
        return sorted(outlines, key=lambda x: x.chapter_number)

    async def update_outline(self, outline_id: str, dto: UpdateChapterOutlineDTO) -> Optional[ChapterOutline]:
        """
        更新章节大纲

        Args:
            outline_id: 大纲ID
            dto: 更新请求

        Returns:
            更新后的大纲
        """
        outline = self._outlines_cache.get(outline_id)
        if not outline:
            return None

        update_data = dto.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(outline, key, value)

        outline.updated_at = datetime.now()

        # 保存到数据库
        if self._db:
            try:
                await self._db.execute_write(
                    """
                    UPDATE chapter_outlines
                    SET title = :title, summary = :summary, scenes = :scenes, emotion_curve = :emotion_curve,
                        chapter_goals = :chapter_goals, status = :status, hooks_planted = :hooks_planted, hooks_resolved = :hooks_resolved,
                        target_word_count = :target_word_count, updated_at = :updated_at
                    WHERE id = :id
                    """,
                    {
                        "title": outline.title,
                        "summary": outline.summary,
                        "scenes": json.dumps([s.model_dump() for s in outline.scenes]),
                        "emotion_curve": outline.emotion_curve.model_dump_json() if outline.emotion_curve else None,
                        "chapter_goals": json.dumps(outline.chapter_goals),
                        "status": outline.status.value,
                        "hooks_planted": json.dumps(outline.hooks_planted),
                        "hooks_resolved": json.dumps(outline.hooks_resolved),
                        "target_word_count": outline.target_word_count,
                        "updated_at": outline.updated_at,
                        "id": outline_id,
                    }
                )
                logger.info(f"更新章节大纲: {outline_id}")
            except Exception as e:
                logger.error(f"更新章节大纲失败: {e}")

        return outline

    async def generate_outline(
        self,
        project_id: str,
        chapter_number: int,
        context: Optional[str] = None,
        previous_events: Optional[str] = None,
        characters: Optional[List[Dict]] = None,
        world_info: Optional[Dict] = None,
        existing_hooks: Optional[List[Dict]] = None,
    ) -> GenerateOutlineResponse:
        """
        生成章节大纲

        使用 Skill 或 LLM 生成结构化的章节大纲

        Args:
            project_id: 项目ID
            chapter_number: 章节号
            context: 上下文信息
            previous_events: 前文事件
            characters: 角色列表（可选，会自动从数据库获取）
            world_info: 世界观信息（可选，会自动从数据库获取）
            existing_hooks: 已有伏笔（可选，会自动从数据库获取）

        Returns:
            GenerateOutlineResponse: 生成的大纲和建议
        """
        # 判断是否为黄金三章（1-3章）
        is_golden_three = 1 <= chapter_number <= 3

        # 获取完整项目上下文
        full_context = await self.get_full_project_context(project_id, chapter_number)

        # 如果调用者没有提供特定信息，使用自动获取的上下文
        if not characters:
            characters = full_context.get("characters", [])
        if not world_info:
            world_info = {
                "name": full_context.get("project", {}).get("title", ""),
                "world_type": full_context.get("project", {}).get("world_type", ""),
                "description": full_context.get("project", {}).get("description", ""),
                "settings": full_context.get("world_settings", []),
            }
        if not existing_hooks:
            hooks_data = full_context.get("hooks", {})
            existing_hooks = hooks_data.get("pending", []) + hooks_data.get("to_resolve", [])

        # 构建生成 Prompt
        prompt = self._build_generation_prompt(
            chapter_number=chapter_number,
            context=context,
            previous_events=previous_events,
            characters=characters,
            world_info=world_info,
            existing_hooks=existing_hooks,
            full_context=full_context,
        )

        # 尝试使用 Skill
        if self._skill_service:
            try:
                from app.services.skill_service import ExecuteSkillDTO
                result = await self._skill_service.execute_skill(ExecuteSkillDTO(
                    skill_id="skill_chapter_outline_generation",
                    project_id=project_id,
                    parameters={
                        "prompt": prompt,
                        "chapter_number": chapter_number,
                        "story_context": self.format_context_for_prompt(full_context),
                        "is_golden_three": is_golden_three,
                    }
                ))
                if result.success:
                    data = json.loads(result.output)
                    outline = self._parse_generated_outline(project_id, chapter_number, data)
                    return GenerateOutlineResponse(
                        outline=outline,
                        suggestions=data.get("suggestions", []),
                        warnings=data.get("warnings", []),
                    )
            except Exception as e:
                logger.warning(f"使用 Skill 生成大纲失败，fallback 到直接生成: {e}")

        # 直接生成（fallback）
        outline = await self._generate_outline_direct(
            project_id=project_id,
            chapter_number=chapter_number,
            prompt=prompt,
        )

        return GenerateOutlineResponse(
            outline=outline,
            suggestions=["大纲已生成，建议人工审核后使用"],
            warnings=[],
        )

    def _build_generation_prompt(
        self,
        chapter_number: int,
        context: Optional[str],
        previous_events: Optional[str],
        characters: Optional[List[Dict]],
        world_info: Optional[Dict],
        existing_hooks: Optional[List[Dict]],
        full_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建大纲生成 Prompt"""
        prompt_parts = [
            f"请为第 {chapter_number} 章生成详细的章节大纲。",
            "",
        ]

        # 如果有完整上下文，优先使用
        if full_context:
            context_str = self.format_context_for_prompt(full_context)
            if context_str:
                prompt_parts.append(context_str)

        if world_info:
            prompt_parts.append("【世界观设定】")
            prompt_parts.append(f"名称: {world_info.get('name', '未知')}")
            prompt_parts.append(f"类型: {world_info.get('world_type', '奇幻')}")
            if world_info.get('description'):
                desc = world_info.get('description') or ''
                prompt_parts.append(f"描述: {desc[:500]}")
            # 添加设定列表
            if world_info.get('settings'):
                prompt_parts.append("\n关键设定：")
                for setting in world_info['settings'][:10]:
                    summary = setting.get('summary') or ''
                    prompt_parts.append(f"- {setting.get('title', '')}: {summary[:100]}")
            prompt_parts.append("")

        if characters:
            prompt_parts.append("【主要角色】")
            for char in characters[:10]:  # 最多显示10个
                name = char.get('name', '未知')
                role = char.get('role', '')
                prompt_parts.append(f"- {name} ({role})" if role else f"- {name}")
            prompt_parts.append("")

        if previous_events:
            prompt_parts.append("【前文事件概要】")
            prompt_parts.append(previous_events[:1000])
            prompt_parts.append("")

        if existing_hooks:
            prompt_parts.append("【待回收伏笔】")
            for hook in existing_hooks[:5]:
                title = hook.get('title', '未知伏笔')
                desc = hook.get('description') or ''
                prompt_parts.append(f"- {title}: {desc[:100]}")
            prompt_parts.append("")

        if context:
            prompt_parts.append("【额外上下文】")
            prompt_parts.append(context[:500])
            prompt_parts.append("")

        prompt_parts.append("""
【输出格式要求】
请输出 JSON 格式：
{
    "title": "章节标题",
    "summary": "章节摘要（100-200字）",
    "scenes": [
        {
            "scene_number": 1,
            "title": "场景标题",
            "scene_type": "dialogue/action/description/climax",
            "summary": "场景摘要",
            "participating_characters": ["角色名"],
            "location": "地点",
            "emotion_start": "neutral/joy/fear/tension等",
            "emotion_end": "neutral/joy/fear/tension等",
            "conflict_level": "low/medium/high/critical",
            "estimated_words": 800,
            "key_events": ["关键事件1", "关键事件2"]
        }
    ],
    "emotion_curve": {
        "points": [
            {"position": 0.0, "emotion": "neutral", "intensity": 0.3},
            {"position": 0.5, "emotion": "tension", "intensity": 0.8},
            {"position": 1.0, "emotion": "relief", "intensity": 0.5}
        ],
        "dominant_emotion": "tension"
    },
    "chapter_goals": ["目标1", "目标2"],
    "hooks_to_plant": ["建议埋设的伏笔"],
    "hooks_to_resolve": ["建议回收的伏笔ID"],
    "suggestions": ["写作建议"],
    "warnings": ["注意事项"]
}
""")
        return "\n".join(prompt_parts)

    def _parse_generated_outline(
        self,
        project_id: str,
        chapter_number: int,
        data: Dict
    ) -> ChapterOutline:
        """解析生成的大纲数据"""
        scenes = []
        for s in data.get("scenes", []):
            scene = SceneOutline(
                id=f"scene_{uuid.uuid4().hex[:8]}",
                scene_number=s.get("scene_number", len(scenes) + 1),
                title=s.get("title", f"场景{len(scenes) + 1}"),
                scene_type=SceneType(s.get("scene_type", "dialogue")),
                summary=s.get("summary", ""),
                participating_characters=s.get("participating_characters", []),
                location=s.get("location"),
                emotion_start=EmotionType(s.get("emotion_start", "neutral")),
                emotion_end=EmotionType(s.get("emotion_end", "neutral")),
                conflict_level=ConflictLevel(s.get("conflict_level", "low")),
                estimated_words=s.get("estimated_words", 500),
                key_events=s.get("key_events", []),
            )
            scenes.append(scene)

        emotion_curve = None
        if data.get("emotion_curve"):
            ec = data["emotion_curve"]
            points = [
                EmotionPoint(
                    position=p.get("position", i / max(len(ec.get("points", [])) - 1, 1)),
                    emotion=EmotionType(p.get("emotion", "neutral")),
                    intensity=p.get("intensity", 0.5),
                    description=p.get("description"),
                )
                for i, p in enumerate(ec.get("points", []))
            ]
            emotion_curve = EmotionCurve(
                chapter_number=chapter_number,
                points=points,
                dominant_emotion=EmotionType(ec.get("dominant_emotion", "neutral")),
            )

        return ChapterOutline(
            id=f"outline_{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            chapter_number=chapter_number,
            title=data.get("title", f"第{chapter_number}章"),
            summary=data.get("summary", ""),
            scenes=scenes,
            emotion_curve=emotion_curve,
            chapter_goals=data.get("chapter_goals", []),
            hooks_planted=data.get("hooks_to_plant", []),
            hooks_resolved=data.get("hooks_to_resolve", []),
            target_word_count=sum(s.estimated_words for s in scenes) or 3000,
            writing_guide=data.get("writing_guide"),
        )

    async def _generate_outline_direct(
        self,
        project_id: str,
        chapter_number: int,
        prompt: str,
    ) -> ChapterOutline:
        """直接调用 LLM 生成大纲（Skill 失败时的 fallback）"""
        from app.config import settings

        # 从数据库加载 prompt 模板
        try:
            from app.services.agent_prompt_service import get_agent_prompt_service
            prompt_service = get_agent_prompt_service()
            system_prompt = await prompt_service.build_agent_prompt(
                agent_type="plot_outline",
                project_id=project_id,
                include_skills=True,
            )
        except Exception as e:
            logger.warning(f"加载 plot_outline prompt 模板失败: {e}")
            system_prompt = self._build_fallback_prompt()

        try:
            llm_config = settings.get_llm_config(settings.llm_provider)
            response = await self._call_llm_for_chat(
                system_prompt=system_prompt,
                user_message=prompt,
                context="",
                llm_config=llm_config,
            )

            # 尝试解析 JSON
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                data = json.loads(json_match.group(1))
            else:
                data = json.loads(response)

            return ChapterOutline(
                id=f"outline_{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                chapter_number=chapter_number,
                title=data.get("title", f"第{chapter_number}章"),
                summary=data.get("summary", ""),
                scenes=[],
                chapter_goals=data.get("chapter_goals", []),
                hooks_planted=data.get("hooks_planted", []),
                target_word_count=data.get("target_word_count", 3000),
            )
        except Exception as e:
            logger.error(f"直接生成大纲失败: {e}")
            # 最终 fallback：返回基本模板
            return ChapterOutline(
                id=f"outline_{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                chapter_number=chapter_number,
                title=f"第{chapter_number}章",
                summary="待填写",
                scenes=[],
                chapter_goals=["推进剧情"],
                target_word_count=3000,
            )

    async def validate_outline(
        self,
        project_id: str,
        outline: ChapterOutline,
    ) -> ValidateOutlineResponse:
        """
        验证章节大纲

        检查大纲的完整性、逻辑性和可行性

        Args:
            project_id: 项目ID
            outline: 待验证的大纲

        Returns:
            ValidateOutlineResponse: 验证结果
        """
        issues = []
        suggestions = []
        score = 1.0

        # 检查基本信息
        if not outline.title or len(outline.title) < 2:
            issues.append({
                "type": "error",
                "field": "title",
                "message": "章节标题过短或缺失",
            })
            score -= 0.1

        if not outline.summary or len(outline.summary) < 50:
            issues.append({
                "type": "warning",
                "field": "summary",
                "message": "章节摘要过短，建议至少50字",
            })
            score -= 0.05

        # 检查场景规划
        if not outline.scenes:
            issues.append({
                "type": "warning",
                "field": "scenes",
                "message": "未规划具体场景",
            })
            score -= 0.15
            suggestions.append("建议为章节规划至少2-3个场景")
        else:
            # 检查场景完整性
            for i, scene in enumerate(outline.scenes):
                if not scene.summary:
                    issues.append({
                        "type": "warning",
                        "field": f"scenes[{i}].summary",
                        "message": f"场景{i+1}缺少摘要",
                    })
                    score -= 0.02

                if not scene.participating_characters:
                    suggestions.append(f"场景{i+1}未指定参与角色")

            # 检查情绪曲线连贯性
            if outline.emotion_curve:
                emotions = [p.emotion for p in outline.emotion_curve.points]
                if len(emotions) > 1:
                    # 检查情绪变化是否合理
                    for i in range(1, len(emotions)):
                        # 从恐惧直接跳到喜悦可能不合理
                        if emotions[i-1] == EmotionType.FEAR and emotions[i] == EmotionType.JOY:
                            suggestions.append(f"情绪从恐惧直接跳到喜悦可能需要过渡")

        # 检查章节目标
        if not outline.chapter_goals:
            issues.append({
                "type": "info",
                "field": "chapter_goals",
                "message": "未设定章节目标",
            })
            suggestions.append("建议设定1-3个明确的章节目标")
            score -= 0.05

        # 检查字数规划
        total_scene_words = sum(s.estimated_words for s in outline.scenes)
        if total_scene_words > 0 and abs(total_scene_words - outline.target_word_count) > 500:
            suggestions.append(
                f"场景预估字数({total_scene_words})与目标字数({outline.target_word_count})差异较大"
            )

        # 使用 Skill 进行深度验证
        if self._skill_service:
            try:
                from app.services.skill_service import ExecuteSkillDTO
                result = await self._skill_service.execute_skill(ExecuteSkillDTO(
                    skill_id="skill_chapter_outline_validation",
                    project_id=project_id,
                    parameters={
                        "outline": outline.model_dump(),
                    }
                ))
                if result.success:
                    data = json.loads(result.output)
                    # 合并 Skill 返回的问题
                    issues.extend(data.get("issues", []))
                    suggestions.extend(data.get("suggestions", []))
                    score = min(score, data.get("score", score))
            except Exception as e:
                logger.warning(f"使用 Skill 验证大纲失败: {e}")

        return ValidateOutlineResponse(
            valid=len([i for i in issues if i.get("type") == "error"]) == 0,
            issues=issues,
            suggestions=suggestions,
            score=max(0, score),
        )

    async def delete_outline(self, outline_id: str) -> bool:
        """
        删除章节大纲

        Args:
            outline_id: 大纲ID

        Returns:
            bool: 是否成功
        """
        if outline_id in self._outlines_cache:
            del self._outlines_cache[outline_id]

        if self._db:
            try:
                await self._db.execute_write(
                    "DELETE FROM chapter_outlines WHERE id = :id",
                    {"id": outline_id}
                )
                logger.info(f"删除章节大纲: {outline_id}")
                return True
            except Exception as e:
                logger.error(f"删除章节大纲失败: {e}")
                return False

        return True

    async def approve_outline(self, outline_id: str, approved_by: str) -> Optional[ChapterOutline]:
        """
        审批章节大纲

        Args:
            outline_id: 大纲ID
            approved_by: 审批人

        Returns:
            更新后的大纲
        """
        outline = self._outlines_cache.get(outline_id)
        if not outline:
            return None

        outline.status = ChapterOutlineStatus.APPROVED
        outline.approved_at = datetime.now()
        outline.approved_by = approved_by
        outline.updated_at = datetime.now()

        if self._db:
            try:
                await self._db.execute_write(
                    """
                    UPDATE chapter_outlines
                    SET status = :status, approved_at = :approved_at,
                        approved_by = :approved_by, updated_at = :updated_at
                    WHERE id = :id
                    """,
                    {
                        "status": outline.status.value,
                        "approved_at": outline.approved_at,
                        "approved_by": outline.approved_by,
                        "updated_at": outline.updated_at,
                        "id": outline_id,
                    }
                )
                logger.info(f"审批章节大纲: {outline_id}")
            except Exception as e:
                logger.error(f"审批章节大纲失败: {e}")

        return outline

    async def get_outline_statistics(self, project_id: str) -> Dict[str, Any]:
        """
        获取项目大纲统计

        Args:
            project_id: 项目ID

        Returns:
            Dict: 统计数据
        """
        outlines = await self.get_outlines_by_project(project_id)

        total_words = sum(o.target_word_count for o in outlines)
        status_counts = {}
        for o in outlines:
            status = o.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_outlines": len(outlines),
            "total_target_words": total_words,
            "status_distribution": status_counts,
            "average_scenes_per_chapter": sum(len(o.scenes) for o in outlines) / max(len(outlines), 1),
            "hooks_planned": sum(len(o.hooks_planted) for o in outlines),
            "hooks_resolved": sum(len(o.hooks_resolved) for o in outlines),
        }

    async def get_full_project_context(
        self,
        project_id: str,
        chapter_number: int,
    ) -> Dict[str, Any]:
        """
        获取项目完整上下文信息，用于大纲生成

        包括：角色信息、世界设定、伏笔状态、前文大纲、项目元数据

        Args:
            project_id: 项目ID
            chapter_number: 当前章节号

        Returns:
            Dict: 完整上下文信息
        """
        context = {
            "project": {},
            "characters": [],
            "world_settings": [],
            "hooks": {"to_plant": [], "to_resolve": [], "pending": []},
            "previous_outlines": [],
            "current_chapter": chapter_number,
        }

        if not self._db:
            return context

        try:
            # 1. 获取项目元数据
            project = await self._db.get_project(project_id)
            if project:
                metadata = project.get("metadata") or {}
                description = project.get("description") or ""
                context["project"] = {
                    "title": project.get("title", ""),
                    "description": description[:500] if description else "",
                    "world_type": metadata.get("world_type", ""),
                    "tone": metadata.get("tone", ""),
                }

            # 2. 获取角色信息
            characters = await self._db.execute_query(
                """
                SELECT id, name, role, personality, background_story,
                       importance_tier, status
                FROM characters
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY
                    CASE importance_tier
                        WHEN 'protagonist' THEN 1
                        WHEN 'co_protagonist' THEN 2
                        WHEN 'deuteragonist' THEN 3
                        WHEN 'mentor' THEN 4
                        WHEN 'love_interest' THEN 5
                        WHEN 'best_friend' THEN 6
                        WHEN 'archenemy' THEN 7
                        WHEN 'major_ally' THEN 8
                        WHEN 'major_antagonist' THEN 9
                        WHEN 'rival' THEN 10
                        WHEN 'family_member' THEN 11
                        ELSE 100
                    END,
                    name
                LIMIT 20
                """,
                {"project_id": project_id}
            )
            for char in characters:
                personality = char.get("personality") or ""
                background = char.get("background_story") or ""
                context["characters"].append({
                    "name": char.get("name", ""),
                    "role": char.get("role", "supporting"),
                    "personality": personality[:200] if personality else "",
                    "background": background[:200] if background else "",
                    "importance": char.get("importance_tier", "npc"),
                    "status": char.get("status", ""),
                })

            # 3. 获取世界设定
            lores = await self._db.execute_query(
                """
                SELECT title, category, priority, content, summary
                FROM lore_entries
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY
                    CASE priority
                        WHEN 'constitutional' THEN 1
                        WHEN 'core' THEN 2
                        WHEN 'standard' THEN 3
                        ELSE 4
                    END,
                    created_at DESC
                LIMIT 30
                """,
                {"project_id": project_id}
            )
            for lore in lores:
                summary = lore.get("summary") or lore.get("content") or ""
                context["world_settings"].append({
                    "title": lore.get("title", ""),
                    "category": lore.get("category", "custom"),
                    "priority": lore.get("priority", "standard"),
                    "summary": summary[:300] if summary else "",
                })

            # 4. 获取伏笔状态
            hooks = await self._db.execute_query(
                """
                SELECT id, title, description, hook_type, status, plant_chapter
                FROM hooks
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY plant_chapter DESC
                LIMIT 30
                """,
                {"project_id": project_id}
            )
            for hook in hooks:
                hook_status = hook.get("status", "planted")
                hook_desc = hook.get("description") or ""
                hook_info = {
                    "id": hook.get("id", ""),
                    "title": hook.get("title", ""),
                    "description": hook_desc[:100] if hook_desc else "",
                    "planted_chapter": hook.get("plant_chapter"),
                }
                if hook_status == "planted":
                    context["hooks"]["pending"].append(hook_info)
                elif hook_status == "hinted":
                    context["hooks"]["to_resolve"].append(hook_info)

            # 5. 获取前文大纲
            if chapter_number > 1:
                prev_outlines = await self.get_outlines_by_project(project_id)
                for outline in prev_outlines:
                    if outline.chapter_number < chapter_number:
                        context["previous_outlines"].append({
                            "chapter_number": outline.chapter_number,
                            "title": outline.title,
                            "summary": outline.summary[:200] if outline.summary else "",
                            "status": outline.status.value,
                        })
                # 只保留最近3章
                context["previous_outlines"] = context["previous_outlines"][-3:]

            logger.info(f"获取项目 {project_id} 上下文: {len(context['characters'])} 角色, "
                       f"{len(context['world_settings'])} 设定, {len(hooks)} 伏笔")

        except Exception as e:
            logger.error(f"获取项目上下文失败: {e}")

        return context

    async def get_next_chapter_number(self, project_id: str) -> int:
        """
        自动确定下一章节序号

        根据已存在的最大章节号（大纲+已完成的章节）+1

        Args:
            project_id: 项目ID

        Returns:
            int: 下一章节序号
        """
        if not self._db:
            logger.warning("数据库连接不存在，使用默认章节号 1")
            return 1

        try:
            # 查询已批准/已完成的大纲最大章节号
            outline_result = await self._db.execute_query('''
                SELECT MAX(chapter_number) as max_outline
                FROM chapter_outlines
                WHERE project_id = CAST(:project_id AS UUID)
                  AND status IN ('approved', 'completed')
            ''', {"project_id": project_id})

            max_outline = 0
            if outline_result and outline_result[0].get("max_outline"):
                max_outline = outline_result[0]["max_outline"]

            # 查询已完成的章节最大章节号
            try:
                chapters = await self._db.get_chapters_by_project(project_id, status="completed")
                max_chapter = max((c.chapter_number for c in chapters), default=0) if chapters else 0
            except Exception:
                max_chapter = 0

            # 取两者最大值 + 1
            next_num = max(max_outline, max_chapter) + 1

            logger.info(f"项目 {project_id} 下一章节序号: {next_num} (大纲最大: {max_outline}, 章节最大: {max_chapter})")
            return next_num

        except Exception as e:
            logger.error(f"获取下一章节号失败: {e}，使用默认值 1")
            return 1

    async def get_chapter_outline_for_workflow(
        self,
        project_id: str,
        chapter_number: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        为工作流获取指定章节的大纲

        Args:
            project_id: 项目ID
            chapter_number: 章节号，如果为None则自动获取下一章

        Returns:
            大纲字典，如果不存在则返回None
        """
        # 自动确定章节号
        if chapter_number is None:
            chapter_number = await self.get_next_chapter_number(project_id)

        if not self._db:
            return None

        try:
            result = await self._db.execute_query('''
                SELECT * FROM chapter_outlines
                WHERE project_id = CAST(:project_id AS UUID)
                  AND chapter_number = :chapter_num
                  AND status IN ('draft', 'approved', 'completed')
                LIMIT 1
            ''', {"project_id": project_id, "chapter_num": chapter_number})

            if not result:
                logger.warning(f"第 {chapter_number} 章大纲不存在")
                return None

            outline = dict(result[0])

            # 解析JSON字段
            for field in ['scenes', 'chapter_goals', 'emotion_curve', 'hooks_planted', 'hooks_resolved']:
                if outline.get(field) and isinstance(outline[field], str):
                    import json
                    try:
                        outline[field] = json.loads(outline[field])
                    except:
                        outline[field] = []

            logger.info(f"加载第 {chapter_number} 章大纲: {outline.get('title', '未命名')}")
            return outline

        except Exception as e:
            logger.error(f"加载章节大纲失败: {e}")
            return None

    def format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """
        将上下文信息格式化为 Prompt 可用的字符串

        Args:
            context: 上下文字典

        Returns:
            str: 格式化后的上下文字符串
        """
        parts = []

        # 项目信息
        if context.get("project"):
            proj = context["project"]
            parts.append(f"【作品信息】")
            if proj.get("title"):
                parts.append(f"作品名称：{proj['title']}")
            if proj.get("world_type"):
                parts.append(f"世界类型：{proj['world_type']}")
            if proj.get("tone"):
                parts.append(f"叙事基调：{proj['tone']}")
            if proj.get("description"):
                parts.append(f"作品简介：{proj['description'][:300]}")
            parts.append("")

        # 角色信息
        if context.get("characters"):
            parts.append("【主要角色】")
            for char in context["characters"][:10]:
                role_label = {"main": "主角", "antagonist": "反派", "supporting": "配角"}.get(char.get("role", ""), "角色")
                parts.append(f"- {char['name']} ({role_label})")
                if char.get("personality"):
                    parts.append(f"  性格：{char['personality'][:100]}")
                if char.get("status"):
                    parts.append(f"  当前状态：{char['status']}")
            parts.append("")

        # 世界设定
        if context.get("world_settings"):
            parts.append("【世界设定】")
            for lore in context["world_settings"][:15]:
                parts.append(f"- [{lore.get('priority', 'standard')}] {lore['title']}")
                if lore.get("summary"):
                    parts.append(f"  {lore['summary'][:150]}")
            parts.append("")

        # 伏笔状态
        hooks = context.get("hooks", {})
        if hooks.get("pending") or hooks.get("to_resolve"):
            parts.append("【伏笔状态】")
            if hooks.get("pending"):
                parts.append("待处理伏笔：")
                for h in hooks["pending"][:5]:
                    parts.append(f"- [{h.get('plant_chapter', '?')}章] {h['title']}")
            if hooks.get("to_resolve"):
                parts.append("建议回收的伏笔：")
                for h in hooks["to_resolve"][:3]:
                    desc = h.get('description') or ''
                    parts.append(f"- {h['title']}: {desc[:50]}")
            parts.append("")

        # 前文大纲
        if context.get("previous_outlines"):
            parts.append("【前文大纲】")
            for outline in context["previous_outlines"]:
                parts.append(f"第{outline['chapter_number']}章：{outline['title']}")
                if outline.get("summary"):
                    parts.append(f"  {outline['summary'][:150]}")
            parts.append("")

        return "\n".join(parts)

    async def chat_with_agent(
        self,
        project_id: str,
        chapter_number: int,
        message: str,
        existing_outline: Optional[ChapterOutline] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        与 Plot Outline Agent 聊天

        协作生成或修改章节大纲

        Args:
            project_id: 项目ID
            chapter_number: 章节号
            message: 用户消息
            existing_outline: 现有的大纲
            context: 额外上下文

        Returns:
            Dict: 响应结果
        """
        from app.config import settings

        # 获取项目完整上下文
        full_context = await self.get_full_project_context(project_id, chapter_number)
        context_str = self.format_context_for_prompt(full_context)

        # 构建系统提示（从数据库模板加载）
        system_prompt = await self._build_chat_system_prompt(
            project_id, chapter_number, existing_outline, full_context
        )

        # 构建用户消息上下文
        user_context = await self._build_chat_user_context(
            project_id, chapter_number, existing_outline, context
        )

        # 合并上下文
        combined_context = f"{context_str}\n\n{user_context}"

        # 调用 LLM
        try:
            llm_config = settings.get_llm_config(settings.llm_provider)
            response = await self._call_llm_for_chat(
                system_prompt=system_prompt,
                user_message=message,
                context=combined_context,
                llm_config=llm_config,
            )

            # 调试日志：记录原始响应
            logger.info(f"[PlotOutline] LLM 响应长度: {len(response)} 字符")
            logger.debug(f"[PlotOutline] LLM 响应内容: {response[:500]}...")

            # 尝试解析大纲更新
            outline_updates = self._try_parse_outline_updates(response)
            logger.info(f"[PlotOutline] 解析结果: {outline_updates}")

            # 如果有大纲内容，自动保存为草稿
            saved_outline = None
            saved_outlines = []  # 支持多章保存

            if outline_updates:
                try:
                    # 检查是否为多章大纲
                    if "chapters" in outline_updates:
                        # 保存多章大纲
                        for chapter_data in outline_updates["chapters"]:
                            ch_num = chapter_data.get("chapter_number", 1)
                            existing = await self.get_outline(project_id, ch_num)

                            # 转换场景数据
                            scenes = self._convert_scenes_data(chapter_data.get("scenes", []))

                            if existing:
                                # 更新现有草稿
                                update_dto = UpdateChapterOutlineDTO(
                                    title=chapter_data.get("title", existing.title),
                                    summary=chapter_data.get("summary", existing.summary),
                                    chapter_goals=chapter_data.get("chapter_goals", existing.chapter_goals),
                                    hooks_planted=chapter_data.get("hooks_planted", existing.hooks_planted),
                                    hooks_resolved=chapter_data.get("hooks_resolved", existing.hooks_resolved),
                                    target_word_count=chapter_data.get("target_word_count", existing.target_word_count),
                                )
                                # 如果有场景数据，也更新
                                if scenes:
                                    update_dto.scenes = scenes
                                updated = await self.update_outline(existing.id, update_dto)
                                if updated:
                                    saved_outlines.append(updated)
                                logger.info(f"更新草稿大纲: 第{ch_num}章")
                            else:
                                # 创建新草稿
                                created = await self.create_outline(CreateChapterOutlineDTO(
                                    project_id=project_id,
                                    chapter_number=ch_num,
                                    title=chapter_data.get("title", f"第{ch_num}章"),
                                    summary=chapter_data.get("summary", ""),
                                    scenes=scenes,
                                    chapter_goals=chapter_data.get("chapter_goals", []),
                                    hooks_planted=chapter_data.get("hooks_planted", []),
                                    hooks_resolved=chapter_data.get("hooks_resolved", []),
                                    target_word_count=chapter_data.get("target_word_count", 3000),
                                ))
                                if created:
                                    saved_outlines.append(created)
                                logger.info(f"创建草稿大纲: 第{ch_num}章")

                        # 使缓存失效
                        self._cache_valid = False
                        saved_outline = saved_outlines[-1] if saved_outlines else None
                        logger.info(f"批量保存了 {len(saved_outlines)} 章大纲")

                    elif "title" in outline_updates:
                        # 单章大纲
                        existing = await self.get_outline(project_id, chapter_number)

                        # 转换场景数据
                        scenes = self._convert_scenes_data(outline_updates.get("scenes", []))

                        if existing:
                            # 更新现有草稿
                            update_dto = UpdateChapterOutlineDTO(
                                title=outline_updates.get("title", existing.title),
                                summary=outline_updates.get("summary", existing.summary),
                                chapter_goals=outline_updates.get("chapter_goals", existing.chapter_goals),
                                hooks_planted=outline_updates.get("hooks_planted", existing.hooks_planted),
                                hooks_resolved=outline_updates.get("hooks_resolved", existing.hooks_resolved),
                                target_word_count=outline_updates.get("target_word_count", existing.target_word_count),
                            )
                            # 如果有场景数据，也更新
                            if scenes:
                                update_dto.scenes = scenes
                            saved_outline = await self.update_outline(existing.id, update_dto)
                            logger.info(f"更新草稿大纲: 第{chapter_number}章")
                        else:
                            # 创建新草稿
                            saved_outline = await self.create_outline(CreateChapterOutlineDTO(
                                project_id=project_id,
                                chapter_number=chapter_number,
                                title=outline_updates.get("title", f"第{chapter_number}章"),
                                summary=outline_updates.get("summary", ""),
                                scenes=scenes,
                                chapter_goals=outline_updates.get("chapter_goals", []),
                                hooks_planted=outline_updates.get("hooks_planted", []),
                                hooks_resolved=outline_updates.get("hooks_resolved", []),
                                target_word_count=outline_updates.get("target_word_count", 3000),
                            ))
                            logger.info(f"创建草稿大纲: 第{chapter_number}章")

                        # 使缓存失效
                        self._cache_valid = False

                except Exception as e:
                    logger.error(f"自动保存草稿失败: {e}")

            # 返回结果
            result = {
                "message": response,
                "outline_updates": outline_updates,
                "suggestions": self._extract_suggestions(response),
                "saved_outline": saved_outline.model_dump() if saved_outline else None,
            }
            # 如果保存了多章，添加到返回结果
            if saved_outlines:
                result["saved_outlines"] = [o.model_dump() for o in saved_outlines]

            return result
        except Exception as e:
            logger.error(f"Agent 聊天失败: {e}")
            return {
                "message": "抱歉，处理您的请求时遇到问题。请稍后再试。",
                "outline_updates": None,
                "suggestions": None,
                "saved_outline": None,
            }

    async def _build_chat_system_prompt(
        self,
        project_id: str,
        chapter_number: int,
        existing_outline: Optional[ChapterOutline],
        full_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建聊天系统提示（从数据库加载模板）"""
        # 从 AgentPromptService 加载基础 prompt
        try:
            from app.services.agent_prompt_service import get_agent_prompt_service
            prompt_service = get_agent_prompt_service()
            base_prompt = await prompt_service.build_agent_prompt(
                agent_type="plot_outline",
                project_id=project_id,
                include_skills=True,
            )
        except Exception as e:
            logger.warning(f"加载 plot_outline prompt 模板失败: {e}，使用默认 prompt")
            base_prompt = self._build_fallback_prompt()

        # 构建动态上下文
        outline_context = ""
        if existing_outline:
            outline_context = f"""
当前章节大纲状态：
- 标题: {existing_outline.title}
- 摘要: {existing_outline.summary}
- 状态: {existing_outline.status.value}
- 场景数: {len(existing_outline.scenes)}
- 目标字数: {existing_outline.target_word_count}
"""
        else:
            outline_context = "当前章节暂无大纲，需要创建新的大纲。"

        # 根据上下文生成提示
        context_hints = ""
        if full_context:
            char_count = len(full_context.get("characters", []))
            lore_count = len(full_context.get("world_settings", []))
            hooks_pending = len(full_context.get("hooks", {}).get("pending", []))
            hooks_to_resolve = len(full_context.get("hooks", {}).get("to_resolve", []))

            context_hints = f"""
【已获取的项目上下文】
- 角色信息：{char_count} 个角色可用
- 世界设定：{lore_count} 条设定可用
- 待处理伏笔：{hooks_pending} 个
- 建议回收伏笔：{hooks_to_resolve} 个

请根据上下文信息，确保大纲与现有设定保持一致。
"""

        # 从 prompt 库加载输出格式规范
        output_format = await self._load_output_format_prompt()

        # 组合基础 prompt 和动态上下文
        return f"{base_prompt}\n\n{outline_context}\n\n{context_hints}\n\n{output_format}".strip()

    async def _load_output_format_prompt(self) -> str:
        """从 prompt 库加载输出格式规范"""
        try:
            # 尝试从 MD 文件服务加载
            from app.services.md_file_service import get_md_file_service
            md_service = get_md_file_service()
            prompt = md_service.get_prompt("plot_outline_output")
            if prompt:
                # 提取内容（去掉 YAML frontmatter）
                import re
                content = prompt.content
                # 去掉 frontmatter
                content = re.sub(r'^---\n[\s\S]*?\n---\n', '', content)
                return content.strip()
        except Exception as e:
            logger.warning(f"加载 plot_outline_output prompt 失败: {e}")

        # 返回简化版本
        return self._get_simple_output_format()

    def _get_simple_output_format(self) -> str:
        """获取简化的输出格式（当 prompt 库加载失败时使用）"""
        return """【重要：输出格式要求】

当用户要求生成大纲时，必须输出完整的 JSON 格式：

单章格式：
```json
{"chapter_number": 1, "title": "标题", "summary": "摘要", "chapter_goals": ["目标1"], "scenes": [{"scene_number": 1, "title": "场景", "summary": "内容", "estimated_words": 800}]}
```

多章格式：
```json
{"chapters": [{"chapter_number": 1, "title": "标题", "summary": "摘要", "scenes": [...]}, {"chapter_number": 2, ...}]}
```

规则：必须输出完整 JSON，不要省略字段。"""

    def _build_fallback_prompt(self) -> str:
        """构建备用 prompt（当数据库模板加载失败时使用）"""
        return """你是专业的章节大纲规划助手（Plot Outline Agent）。

你的职责是帮助用户规划章节结构和场景设计，设计情绪曲线和节奏控制，管理章节目标、伏笔埋设和回收。

""" + self._get_simple_output_format()

    async def _build_chat_user_context(
        self,
        project_id: str,
        chapter_number: int,
        existing_outline: Optional[ChapterOutline],
        extra_context: Optional[Dict[str, Any]],
    ) -> str:
        """构建用户消息上下文"""
        parts = [f"章节号: 第{chapter_number}章"]

        # 添加项目信息
        try:
            from app.api.app import postgres_db
            if postgres_db:
                project = await postgres_db.get_project(project_id)
                if project:
                    parts.append(f"作品: {project.get('title', '未命名')}")
        except Exception:
            pass

        # 添加上下文信息
        if extra_context:
            if extra_context.get("previous_events"):
                parts.append(f"前文事件: {extra_context['previous_events'][:500]}")
            if extra_context.get("special_requirements"):
                parts.append(f"特殊要求: {', '.join(extra_context['special_requirements'])}")

        # 添加相邻章节信息
        if existing_outline:
            parts.append(f"当前目标字数: {existing_outline.target_word_count}")
            if existing_outline.chapter_goals:
                parts.append(f"当前章节目标: {', '.join(existing_outline.chapter_goals)}")

        return "\n".join(parts)

    async def _call_llm_for_chat(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
        llm_config: Dict[str, Any],
    ) -> str:
        """调用 LLM 进行聊天"""
        # 使用实例保存的配置
        provider = self._llm_provider
        base_url = self._llm_base_url
        model = self._llm_model
        api_key = self._llm_api_key

        # 记录调用信息用于调试
        logger.info(f"[PlotOutline] LLM调用: provider={provider}, base_url={base_url}, model={model}")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"上下文信息：\n{context}"},
            {"role": "user", "content": user_message},
        ]

        # 根据 provider 选择合适的 SDK
        if provider == "anthropic":
            # 使用 Anthropic SDK（适用于百度千帆的 anthropic 端点）
            try:
                import anthropic
            except ImportError:
                return "无法连接到语言模型，请检查 anthropic 包。"

            if not api_key:
                return "处理请求时出错: API Key 未配置"

            client = anthropic.AsyncAnthropic(
                api_key=api_key,
                base_url=base_url if base_url else "https://api.anthropic.com",
            )

            # 合并所有 system 消息为一个
            system_parts = []
            claude_messages = []

            for m in messages:
                if m["role"] == "system":
                    system_parts.append(m["content"])
                else:
                    claude_messages.append({"role": m["role"], "content": m["content"]})

            system_message = "\n\n".join(system_parts)

            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=self._llm_max_tokens,
                    temperature=self._llm_temperature,
                    system=system_message,
                    messages=claude_messages,
                )
                # 处理响应内容（可能有 ThinkingBlock）
                text_content = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        text_content += block.text
                    elif hasattr(block, 'thinking'):
                        # ThinkingBlock 跳过
                        logger.debug(f"收到 ThinkingBlock")
                return text_content
            except Exception as e:
                logger.error(f"[PlotOutline] LLM 调用失败: {e}")
                return f"处理请求时出错: {str(e)}"
        else:
            # 使用 OpenAI 兼容客户端
            try:
                from openai import AsyncOpenAI
            except ImportError:
                return "无法连接到语言模型，请检查 openai 包。"

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url if base_url else "https://api.openai.com/v1",
            )

            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=self._llm_temperature,
                    max_tokens=self._llm_max_tokens,
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"[PlotOutline] LLM 调用失败: {e}")
                return f"处理请求时出错: {str(e)}"

    def _try_parse_outline_updates(self, response: str) -> Optional[Dict[str, Any]]:
        """
        尝试从响应中解析大纲更新

        支持两种返回格式：
        1. 单章大纲：{"title": "...", "summary": "...", ...}
        2. 多章大纲：{"chapters": [{"chapter_number": 1, ...}, {"chapter_number": 2, ...}, ...]}
        """
        try:
            import re

            # 首先尝试从文本中提取多章大纲（优先级最高，因为JSON可能被截断）
            chapters = self._extract_chapters_from_text(response)
            if chapters and len(chapters) > 1:
                logger.info(f"从文本中提取了 {len(chapters)} 章大纲")
                return {"chapters": chapters}
            elif chapters and len(chapters) == 1:
                # 单章大纲
                return chapters[0]

            # 方法2：查找完整的 JSON 代码块
            json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', response)
            if json_blocks:
                for json_str in json_blocks:
                    try:
                        data = json.loads(json_str)
                        if "title" in data or "scenes" in data:
                            return data
                    except json.JSONDecodeError:
                        continue

            # 方法3：尝试直接解析整个响应为 JSON
            try:
                data = json.loads(response)
                if "title" in data or "scenes" in data or "chapters" in data:
                    return data
            except json.JSONDecodeError:
                pass

            # 方法4：从文本中提取单章大纲信息
            outline_data = self._extract_single_outline_from_text(response)
            if outline_data.get("title") or outline_data.get("summary"):
                logger.info(f"从文本中提取大纲信息: {outline_data}")
                return outline_data

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"解析大纲更新失败: {e}")
        return None

    def _extract_chapters_from_text(self, response: str) -> List[Dict[str, Any]]:
        """从文本中提取多章大纲信息"""
        import re
        chapters = []

        # 匹配章节标题模式：
        # 1. ## 第X章：标题 (markdown 标题)
        # 2. 第X章：标题 (行首)
        # 支持中文数字和阿拉伯数字
        chapter_pattern = r'(?:^|\n)[ \t]*(?:##\s*)?第([一二三四五六七八九十\d]+)章[：:]\s*([^\n\[\]✓×✗]+?)[ \t]*$'

        # 中文数字转阿拉伯数字
        def chinese_to_num(cn: str) -> int:
            mapping = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                      '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
            if cn in mapping:
                return mapping[cn]
            try:
                return int(cn)
            except:
                return 0

        matches = list(re.finditer(chapter_pattern, response, re.MULTILINE))

        # 过滤掉检查列表中的匹配
        valid_matches = []
        for match in matches:
            start_pos = match.start()
            prefix = response[max(0, start_pos-10):start_pos]
            if not re.search(r'\[✓\]|\[×\]|\[✗\]|\[X\]', prefix):
                valid_matches.append(match)

        if not valid_matches:
            return []

        for i, match in enumerate(valid_matches):
            chapter_num = chinese_to_num(match.group(1))
            title = match.group(2).strip()

            if chapter_num == 0:
                continue

            # 提取该章节的内容范围
            start = match.end()
            if i + 1 < len(valid_matches):
                end = valid_matches[i + 1].start()
            else:
                # 查找结束标记
                end_markers = ['## 反派', '## 核心卖点', '---\n```json', '## 伏笔管理', '## 黄金三章自查']
                end = len(response)
                for marker in end_markers:
                    marker_pos = response.find(marker, start)
                    if marker_pos != -1 and marker_pos < end:
                        end = marker_pos

            chapter_text = response[start:end]

            # 提取摘要 - 查找 summary 字段或描述段落
            summary = ""
            # 先尝试从JSON格式的summary提取
            summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', chapter_text)
            if summary_match:
                summary = summary_match.group(1).strip()
            else:
                # 尝试从文本描述提取（核心策略后面的内容）
                strategy_match = re.search(r'\*\*核心策略\*\*[：:]\s*([^\n]+(?:\n[^\n#]*){0,3})', chapter_text)
                if strategy_match:
                    summary = strategy_match.group(1).strip()

            # 提取章节目标
            goals = []
            goals_match = re.search(r'"chapter_goals"\s*:\s*\[((?:[^\[\]]+|\[(?:[^\[\]]+|\[[^\[\]]*\])*\])*)\]', chapter_text)
            if goals_match:
                # 解析JSON数组
                try:
                    goals_str = '[' + goals_match.group(1) + ']'
                    goals = json.loads(goals_str)
                except:
                    pass
            else:
                # 从文本列表提取
                goals = re.findall(r'"([^"]+展示[^"]*|[^"]+建立[^"]*|[^"]+埋设[^"]*|[^"]+制造[^"]*)"', chapter_text)

            # 提取场景规划表格
            scenes = []
            scene_table = re.findall(r'\|\s*(\d+)\s*\|\s*([^|]+)\s*\|\s*(\d+)字\s*\|', chapter_text)
            for s in scene_table:
                scenes.append({
                    "scene_number": int(s[0]),
                    "title": s[1].strip(),
                    "estimated_words": int(s[2])
                })

            # 如果没有表格，尝试从JSON格式的scenes提取
            if not scenes:
                scenes_match = re.search(r'"scenes"\s*:\s*\[', chapter_text)
                if scenes_match:
                    # 找到scenes数组的开始和结束
                    start_idx = scenes_match.start()
                    brace_count = 0
                    bracket_count = 0
                    in_string = False
                    escape = False
                    end_idx = start_idx

                    for idx, char in enumerate(chapter_text[start_idx:], start_idx):
                        if escape:
                            escape = False
                            continue
                        if char == '\\':
                            escape = True
                            continue
                        if char == '"':
                            in_string = not in_string
                            continue
                        if in_string:
                            continue
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                        elif char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0 and brace_count == 0:
                                end_idx = idx + 1
                                break

                    if end_idx > start_idx:
                        try:
                            scenes_json = json.loads(chapter_text[start_idx:end_idx])
                            for scene in scenes_json:
                                scenes.append({
                                    "scene_number": scene.get("scene_number", 0),
                                    "title": scene.get("title", ""),
                                    "summary": scene.get("summary", ""),
                                    "estimated_words": scene.get("estimated_words", 500),
                                    "key_events": scene.get("key_events", []),
                                })
                        except Exception as e:
                            logger.debug(f"解析scenes失败: {e}")

            # 提取钩子
            hooks_planted = []
            hook_patterns = [
                r'\*\*开篇钩子\*\*[（(][^)）]+[)）][：:]\s*\n?\s*>?\s*([^\n#]+)',
                r'\*\*结尾钩子\*\*[（(][^)）]+[)）][：:]\s*\n?\s*>?\s*([^\n#]+)',
            ]
            for pattern in hook_patterns:
                hook_match = re.search(pattern, chapter_text, re.IGNORECASE)
                if hook_match:
                    hooks_planted.append(hook_match.group(1).strip())

            # 提取伏笔
            hooks_from_text = re.findall(r'\*\*埋设\*\*[：:]\s*([^\n]+)', chapter_text)
            hooks_planted.extend(hooks_from_text)

            chapters.append({
                "chapter_number": chapter_num,
                "title": title,
                "summary": summary[:500] if summary else "",
                "chapter_goals": goals[:5] if goals else [],
                "hooks_planted": hooks_planted[:3] if hooks_planted else [],
                "scenes": scenes,
            })

        if chapters:
            logger.info(f"从文本中提取了 {len(chapters)} 章大纲: {[c['title'] for c in chapters]}")

        return chapters

    def _extract_single_outline_from_text(self, response: str) -> Dict[str, Any]:
        """从文本中提取单章大纲信息"""
        import re
        outline_data = {}

        # 提取标题
        title_match = re.search(r'(?:章节标题|标题|第\d+章[：:]?\s*)([^\n「」【】\|]+)', response)
        if title_match:
            outline_data["title"] = title_match.group(1).strip()

        # 提取摘要
        summary_match = re.search(r'(?:章节摘要|摘要|内容概要|summary)[：:]\s*([^\n]+(?:\n[^\n#]*)*)', response, re.IGNORECASE)
        if summary_match:
            outline_data["summary"] = summary_match.group(1).strip()

        # 提取章节目标
        goals_match = re.search(r'(?:章节目标|目标|goals)[：:]\s*((?:[-•]\s*[^\n]+\n?)+)', response, re.IGNORECASE)
        if goals_match:
            goals_text = goals_match.group(1)
            goals = re.findall(r'[-•]\s*([^\n]+)', goals_text)
            if goals:
                outline_data["chapter_goals"] = goals

        # 提取场景（新格式：**场景1：标题（约800字）**）
        scenes = []
        scene_pattern = r'\*\*场景(\d+)[：:]\s*([^(（]+)(?:[(（]约(\d+)字[)）])?\*\*\s*\n((?:[-•]\s*[^\n]+\n?)+)'
        scene_matches = re.finditer(scene_pattern, response)

        for match in scene_matches:
            scene_num = int(match.group(1))
            scene_title = match.group(2).strip()
            estimated_words = int(match.group(3)) if match.group(3) else 500
            scene_content = match.group(4)

            # 提取场景内的关键事件
            key_events = re.findall(r'[-•]\s*\*\*([^*]+)\*\*[：:]\s*([^\n]+)', scene_content)
            if not key_events:
                key_events = [(f"事件{i+1}", line.strip()) for i, line in enumerate(re.findall(r'[-•]\s*([^\n]+)', scene_content))]

            summary = ""
            for event_title, event_content in key_events[:2]:
                summary += event_content + "。"
            if not summary:
                lines = re.findall(r'[-•]\s*([^\n]+)', scene_content)
                summary = lines[0] if lines else ""

            scenes.append({
                "scene_number": scene_num,
                "title": scene_title,
                "summary": summary[:200],
                "estimated_words": estimated_words,
                "key_events": [e[1] if isinstance(e, tuple) else e for e in key_events[:3]]
            })

        # 如果找到了场景，添加到大纲数据
        if scenes:
            outline_data["scenes"] = scenes

        # 提取结尾钩子
        ending_hook = re.search(r'\*\*结尾钩子\*\*[^\n]*\n([\s\S]*?)(?=\n---|\n##|\n```json|$)', response)
        if ending_hook:
            hook_text = ending_hook.group(1).strip()
            # 提取结尾句
            ending_sentence = re.search(r'\*\*结尾句\*\*[：:]\s*"([^"]+)"', hook_text)
            if ending_sentence:
                outline_data["hooks_planted"] = [ending_sentence.group(1)]

        return outline_data

    def _convert_scenes_data(self, scenes_data: List[Any]) -> List[SceneOutline]:
        """
        转换场景数据为 SceneOutline 对象

        Args:
            scenes_data: 场景数据列表（可以是 dict 或 SceneOutline）

        Returns:
            List[SceneOutline]: SceneOutline 对象列表
        """
        if not scenes_data:
            return []

        scenes = []
        for i, scene_data in enumerate(scenes_data):
            try:
                if isinstance(scene_data, SceneOutline):
                    scenes.append(scene_data)
                elif isinstance(scene_data, dict):
                    scene = SceneOutline(
                        id=scene_data.get("id", f"scene_{uuid.uuid4().hex[:8]}"),
                        scene_number=scene_data.get("scene_number", i + 1),
                        title=scene_data.get("title", f"场景{i + 1}"),
                        scene_type=SceneType(scene_data.get("scene_type", "dialogue")),
                        summary=scene_data.get("summary", ""),
                        key_events=scene_data.get("key_events", []),
                        participating_characters=scene_data.get("participating_characters", []),
                        pov_character=scene_data.get("pov_character"),
                        location=scene_data.get("location"),
                        time_of_day=scene_data.get("time_of_day"),
                        emotion_start=EmotionType(scene_data.get("emotion_start", "neutral")),
                        emotion_end=EmotionType(scene_data.get("emotion_end", "neutral")),
                        emotion_arc=scene_data.get("emotion_arc", []),
                        conflict_level=ConflictLevel(scene_data.get("conflict_level", "low")),
                        conflict_description=scene_data.get("conflict_description"),
                        hooks_to_plant=scene_data.get("hooks_to_plant", []),
                        hooks_to_resolve=scene_data.get("hooks_to_resolve", []),
                        estimated_words=scene_data.get("estimated_words", 500),
                        writing_hints=scene_data.get("writing_hints", []),
                    )
                    scenes.append(scene)
            except Exception as e:
                logger.warning(f"转换场景数据失败: {e}, 数据: {scene_data}")

        return scenes

    def _extract_suggestions(self, response: str) -> List[str]:
        """从响应中提取建议"""
        suggestions = []
        # 简单提取：查找"建议"开头的行
        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("建议") or line.startswith("- 建议"):
                suggestions.append(line.lstrip("- ").lstrip("建议：").lstrip("建议:"))
        return suggestions[:5]  # 最多返回5条建议


# 全局实例
_plot_outline_service: Optional[PlotOutlineService] = None


def get_plot_outline_service() -> PlotOutlineService:
    """获取章节大纲服务实例"""
    global _plot_outline_service
    if _plot_outline_service is None:
        from app.api.app import postgres_db
        from app.services.skill_service import get_skill_service
        _plot_outline_service = PlotOutlineService(
            db=postgres_db,
            skill_service=get_skill_service(),
        )
    return _plot_outline_service


def set_plot_outline_service(service: PlotOutlineService):
    """设置章节大纲服务实例"""
    global _plot_outline_service
    _plot_outline_service = service
