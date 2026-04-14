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

    async def _ensure_cache(self, project_id: str):
        """确保缓存有效"""
        cache_key = f"project_{project_id}"
        if self._cache_valid and cache_key in self._outlines_cache:
            return

        if self._db:
            try:
                rows = await self._db.execute_query(
                    "SELECT * FROM chapter_outlines WHERE project_id = $1 ORDER BY chapter_number",
                    project_id
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
        return ChapterOutline(
            id=row['id'],
            project_id=row['project_id'],
            chapter_number=row['chapter_number'],
            title=row['title'],
            summary=row['summary'],
            status=ChapterOutlineStatus(row['status']),
            scenes=[SceneOutline(**s) for s in json.loads(row.get('scenes', '[]'))],
            emotion_curve=EmotionCurve(**json.loads(row['emotion_curve'])) if row.get('emotion_curve') else None,
            chapter_goals=json.loads(row.get('chapter_goals', '[]')),
            plot_advancement=row.get('plot_advancement'),
            character_arcs=json.loads(row.get('character_arcs', '{}')),
            hooks_planted=json.loads(row.get('hooks_planted', '[]')),
            hooks_resolved=json.loads(row.get('hooks_resolved', '[]')),
            quality_metrics=json.loads(row.get('quality_metrics', '{}')),
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
            chapter_goals=dto.chapter_goals,
            target_word_count=dto.target_word_count,
        )

        # 保存到数据库
        if self._db:
            try:
                await self._db.execute_query(
                    """
                    INSERT INTO chapter_outlines
                    (id, project_id, chapter_number, title, summary, chapter_goals, target_word_count, status, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    outline.id, outline.project_id, outline.chapter_number,
                    outline.title, outline.summary, json.dumps(outline.chapter_goals),
                    outline.target_word_count, outline.status.value,
                    outline.created_at, outline.updated_at
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
                await self._db.execute_query(
                    """
                    UPDATE chapter_outlines
                    SET title = $1, summary = $2, scenes = $3, emotion_curve = $4,
                        chapter_goals = $5, status = $6, hooks_planted = $7, hooks_resolved = $8,
                        target_word_count = $9, updated_at = $10
                    WHERE id = $11
                    """,
                    outline.title, outline.summary, json.dumps([s.model_dump() for s in outline.scenes]),
                    outline.emotion_curve.model_dump_json() if outline.emotion_curve else None,
                    json.dumps(outline.chapter_goals), outline.status.value,
                    json.dumps(outline.hooks_planted), json.dumps(outline.hooks_resolved),
                    outline.target_word_count, outline.updated_at, outline_id
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
                prompt_parts.append(f"描述: {world_info.get('description')[:500]}")
            # 添加设定列表
            if world_info.get('settings'):
                prompt_parts.append("\n关键设定：")
                for setting in world_info['settings'][:10]:
                    prompt_parts.append(f"- {setting.get('title', '')}: {setting.get('summary', '')[:100]}")
            prompt_parts.append("")

        if characters:
            prompt_parts.append("【主要角色】")
            for char in characters[:10]:  # 最多显示10个
                name = char.get('name', '未知')
                role = char.get('role', char.get('character_type', ''))
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
                desc = hook.get('description', '')[:100]
                prompt_parts.append(f"- {title}: {desc}")
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
        )

    async def _generate_outline_direct(
        self,
        project_id: str,
        chapter_number: int,
        prompt: str,
    ) -> ChapterOutline:
        """直接生成大纲（无 Skill 时使用）"""
        # 返回一个基本大纲模板
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
                await self._db.execute_query(
                    "DELETE FROM chapter_outlines WHERE id = $1",
                    outline_id
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
                await self._db.execute_query(
                    """
                    UPDATE chapter_outlines
                    SET status = $1, approved_at = $2, approved_by = $3, updated_at = $4
                    WHERE id = $5
                    """,
                    outline.status.value, outline.approved_at, outline.approved_by,
                    outline.updated_at, outline_id
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
                context["project"] = {
                    "title": project.get("title", ""),
                    "description": project.get("description", "")[:500] if project.get("description") else "",
                    "world_type": project.get("metadata", {}).get("world_type", ""),
                    "tone": project.get("metadata", {}).get("tone", ""),
                }

            # 2. 获取角色信息
            characters = await self._db.execute_query(
                """
                SELECT id, name, role, character_type, personality, background_story,
                       importance_level, current_status
                FROM characters
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY importance_level DESC, name
                LIMIT 20
                """,
                {"project_id": project_id}
            )
            for char in characters:
                context["characters"].append({
                    "name": char.get("name", ""),
                    "role": char.get("role", char.get("character_type", "supporting")),
                    "personality": char.get("personality", "")[:200] if char.get("personality") else "",
                    "background": char.get("background_story", "")[:200] if char.get("background_story") else "",
                    "importance": char.get("importance_level", 3),
                    "status": char.get("current_status", ""),
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
                context["world_settings"].append({
                    "title": lore.get("title", ""),
                    "category": lore.get("category", "custom"),
                    "priority": lore.get("priority", "standard"),
                    "summary": lore.get("summary", "")[:300] if lore.get("summary") else lore.get("content", "")[:300],
                })

            # 4. 获取伏笔状态
            hooks = await self._db.execute_query(
                """
                SELECT id, title, description, hook_type, status, planted_chapter
                FROM hooks
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY planted_chapter DESC
                LIMIT 30
                """,
                {"project_id": project_id}
            )
            for hook in hooks:
                hook_status = hook.get("status", "planted")
                hook_info = {
                    "id": hook.get("id", ""),
                    "title": hook.get("title", ""),
                    "description": hook.get("description", "")[:100] if hook.get("description") else "",
                    "planted_chapter": hook.get("planted_chapter"),
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
                    parts.append(f"- [{h.get('planted_chapter', '?')}章] {h['title']}")
            if hooks.get("to_resolve"):
                parts.append("建议回收的伏笔：")
                for h in hooks["to_resolve"][:3]:
                    parts.append(f"- {h['title']}: {h.get('description', '')[:50]}")
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

        # 构建系统提示
        system_prompt = self._build_chat_system_prompt(chapter_number, existing_outline, full_context)

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

            # 尝试解析大纲更新
            outline_updates = self._try_parse_outline_updates(response)

            return {
                "message": response,
                "outline_updates": outline_updates,
                "suggestions": self._extract_suggestions(response),
            }
        except Exception as e:
            logger.error(f"Agent 聊天失败: {e}")
            return {
                "message": "抱歉，处理您的请求时遇到问题。请稍后再试。",
                "outline_updates": None,
                "suggestions": None,
            }

    def _build_chat_system_prompt(
        self,
        chapter_number: int,
        existing_outline: Optional[ChapterOutline],
        full_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建聊天系统提示"""
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

        return f"""你是专业的章节大纲规划助手（Plot Outline Agent）。

你的职责是：
1. 帮助用户规划章节结构和场景设计
2. 设计情绪曲线和节奏控制
3. 管理章节目标、伏笔埋设和回收
4. 确保章节与整体剧情的衔接
5. 基于已有角色和设定进行创作

{outline_context}

{context_hints}

【大纲设计原则】
1. **场景规划**: 每章2-5个场景，每个场景有明确目的
2. **情绪曲线**: 设计起伏变化，高峰和低谷交替
3. **冲突层次**: 从低到高递进，保持张力
4. **伏笔管理**: 记录待埋设和待回收的伏笔
5. **字数估算**: 根据场景内容预估字数
6. **设定一致**: 确保角色行为和场景设定与已有设定一致

【使用上下文】
你已获得项目的完整上下文信息（角色、设定、伏笔等）。在生成大纲时：
- 出场角色应从已有角色中选择，保持性格一致
- 场景设定应符合世界观规则
- 合理安排伏笔的埋设和回收

【输出格式】
如果用户要求更新大纲，请使用以下格式输出：
```json
{{
  "title": "章节标题",
  "summary": "章节摘要",
  "scenes": [
    {{
      "scene_number": 1,
      "title": "场景标题",
      "scene_type": "dialogue/action/description/climax",
      "summary": "场景摘要",
      "participating_characters": ["角色名"],
      "location": "地点",
      "emotion_start": "neutral",
      "emotion_end": "tension",
      "conflict_level": "low/medium/high/critical",
      "estimated_words": 800,
      "key_events": ["事件1", "事件2"]
    }}
  ],
  "chapter_goals": ["目标1", "目标2"],
  "hooks_to_plant": ["伏笔1"],
  "hooks_to_resolve": ["伏笔ID"],
  "emotion_curve": {{
    "points": [
      {{"position": 0.0, "emotion": "neutral", "intensity": 0.3}},
      {{"position": 0.5, "emotion": "tension", "intensity": 0.8}},
      {{"position": 1.0, "emotion": "relief", "intensity": 0.5}}
    ],
    "dominant_emotion": "tension"
  }}
}}
```

请根据用户的需求，提供专业的建议和帮助。
"""

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
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return "无法连接到语言模型，请检查配置。"

        client = AsyncOpenAI(
            api_key=llm_config.get("api_key", ""),
            base_url=llm_config.get("base_url", "https://api.openai.com/v1"),
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"上下文信息：\n{context}"},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await client.chat.completions.create(
                model=llm_config.get("model", "gpt-4"),
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return f"处理请求时出错: {str(e)}"

    def _try_parse_outline_updates(self, response: str) -> Optional[Dict[str, Any]]:
        """尝试从响应中解析大纲更新"""
        try:
            import re
            # 查找 JSON 代码块
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)
                # 验证必要字段
                if "title" in data or "scenes" in data:
                    return data
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"解析大纲更新失败: {e}")
        return None

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
