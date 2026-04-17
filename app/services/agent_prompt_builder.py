"""
Agent Prompt 组装服务
负责将记忆、技能、上下文统一组装到 Agent 的 system prompt 中
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.agent_io import AgentInput, AgentOutput, SkillCallRequest
from app.models.skill import Skill, SkillType, SkillLoadMode
from app.models.agent_memory import MemoryEntry, MemoryType, MemoryImportance

logger = logging.getLogger(__name__)


class AgentPromptBuilder:
    """
    Agent Prompt 组装器

    职责：
    1. 将 Agent 记忆注入到 prompt
    2. 将 Skills 内容注入到 prompt
    3. 构建完整的执行上下文
    4. 支持"记忆-技能-Prompt"三层组装
    """

    def __init__(self, db=None):
        self._db = db

    async def build_full_prompt(
        self,
        agent_type: str,
        project_id: str,
        base_prompt: str,
        memory_entries: Optional[List[MemoryEntry]] = None,
        skills: Optional[List[Skill]] = None,
        context: Optional[Dict[str, Any]] = None,
        global_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        构建完整的 Agent prompt

        组装顺序（从上到下）：
        1. 角色/身份定义
        2. 核心规则（核心技能）
        3. 长期记忆（决策、事实）
        4. 当前上下文（角色、设定等）
        5. 按需技能（场景相关）
        6. 任务指令

        Args:
            agent_type: Agent 类型
            project_id: 项目 ID
            base_prompt: 基础 prompt
            memory_entries: 记忆条目列表
            skills: 技能列表
            context: 执行上下文
            global_state: 全局状态

        Returns:
            str: 完整的 system prompt
        """
        sections = []

        # 1. 基础 prompt（角色定义）
        if base_prompt:
            sections.append(base_prompt)

        # 2. 核心技能（始终加载）
        if skills:
            core_skills = [s for s in skills if s.load_mode == SkillLoadMode.CORE]
            core_section = self._build_skills_section(core_skills, "核心规则")
            if core_section:
                sections.append(core_section)

        # 3. 长期记忆注入
        if memory_entries:
            memory_section = self._build_memory_section(memory_entries)
            if memory_section:
                sections.append(memory_section)

        # 4. 当前上下文
        if context:
            context_section = self._build_context_section(context, global_state)
            if context_section:
                sections.append(context_section)

        # 5. 按需技能（场景相关）
        if skills:
            on_demand_skills = [s for s in skills if s.load_mode == SkillLoadMode.ON_DEMAND]
            on_demand_section = self._build_skills_section(on_demand_skills, "场景技能")
            if on_demand_section:
                sections.append(on_demand_section)

        return "\n\n".join(sections)

    def _build_memory_section(
        self,
        entries: List[MemoryEntry],
        max_entries: int = 10,
    ) -> str:
        """
        构建记忆注入部分

        将重要的决策和事实注入到 prompt 中，帮助 Agent 保持一致性。

        Args:
            entries: 记忆条目列表
            max_entries: 最大条目数

        Returns:
            str: 记忆部分的 prompt
        """
        if not entries:
            return ""

        # 按重要性和时间排序
        importance_order = {
            MemoryImportance.CRITICAL: 0,
            MemoryImportance.HIGH: 1,
            MemoryImportance.MEDIUM: 2,
            MemoryImportance.LOW: 3,
        }

        sorted_entries = sorted(
            entries,
            key=lambda e: (importance_order.get(e.importance, 3), e.timestamp or datetime.min),
            reverse=True
        )[:max_entries]

        # 分组
        decisions = []
        facts = []
        observations = []

        for entry in sorted_entries:
            if entry.type == MemoryType.DECISION:
                decisions.append(entry)
            elif entry.type == MemoryType.FACT:
                facts.append(entry)
            elif entry.type == MemoryType.OBSERVATION:
                observations.append(entry)

        parts = ["## 历史记忆（保持一致性）"]

        if decisions:
            parts.append("\n### 重要决策")
            for d in decisions:
                parts.append(f"- {d.content}")
                if d.summary:
                    parts.append(f"  理由: {d.summary}")

        if facts:
            parts.append("\n### 已知事实")
            for f in facts:
                parts.append(f"- {f.content}")

        if observations:
            parts.append("\n### 关键观察")
            for o in observations:
                parts.append(f"- {o.content}")

        return "\n".join(parts)

    def _build_skills_section(
        self,
        skills: List[Skill],
        section_title: str,
    ) -> str:
        """
        构建技能注入部分

        Args:
            skills: 技能列表
            section_title: 部分标题

        Returns:
            str: 技能部分的 prompt
        """
        if not skills:
            return ""

        # 按优先级排序
        sorted_skills = sorted(skills, key=lambda s: -s.priority)

        parts = [f"## {section_title}"]

        for skill in sorted_skills:
            if not skill.is_enabled:
                continue

            # 获取内容
            if skill.skill_type == SkillType.KNOWLEDGE:
                content = skill.knowledge_content or ""
            elif skill.skill_type == SkillType.PROMPT:
                content = skill.prompt_template or ""
            else:
                continue

            if not content:
                continue

            # 添加技能名称
            parts.append(f"\n### {skill.name}")
            parts.append(content)

        return "\n".join(parts)

    def _build_context_section(
        self,
        context: Dict[str, Any],
        global_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        构建上下文部分

        Args:
            context: 执行上下文
            global_state: 全局状态

        Returns:
            str: 上下文部分的 prompt
        """
        parts = ["## 当前上下文"]

        # 角色信息
        if "characters" in context:
            chars = context["characters"]
            if chars:
                parts.append("\n### 出场角色")
                for char in chars:
                    name = char.get("name", "未知")
                    role_type = char.get("role_type", "未知")
                    stance = char.get("stance", "未知")
                    parts.append(f"- {name} ({role_type}, 立场: {stance})")

        # 世界设定
        if "world_settings" in context:
            settings = context["world_settings"]
            if settings:
                parts.append("\n### 相关设定")
                for setting in settings:
                    name = setting.get("name", "未知")
                    desc = setting.get("description", "")
                    parts.append(f"- {name}: {desc}")

        # 伏笔状态
        if "active_hooks" in context:
            hooks = context["active_hooks"]
            if hooks:
                parts.append("\n### 待处理伏笔")
                for hook in hooks:
                    title = hook.get("title", "未知")
                    status = hook.get("status", "pending")
                    parts.append(f"- [{status}] {title}")

        # 全局状态
        if global_state:
            parts.append("\n### 项目状态")
            if "main_plot_progress" in global_state:
                progress = global_state["main_plot_progress"]
                parts.append(f"- 剧情进度: {progress * 100:.1f}%")
            if "villain_threat_level" in global_state:
                threat = global_state["villain_threat_level"]
                parts.append(f"- 反派威胁等级: {threat}")
            if "current_chapter" in global_state:
                chapter = global_state["current_chapter"]
                parts.append(f"- 当前章节: 第 {chapter} 章")

        return "\n".join(parts)

    def build_skill_call_prompt(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """
        构建技能调用的 prompt

        Args:
            skill: 技能对象
            parameters: 调用参数
            context: 执行上下文

        Returns:
            str: 调用 prompt
        """
        # 获取模板内容
        if skill.skill_type == SkillType.KNOWLEDGE:
            content = skill.knowledge_content or ""
        elif skill.skill_type == SkillType.PROMPT:
            content = skill.prompt_template or ""
        else:
            return ""

        # 替换参数
        rendered = content
        for key, value in parameters.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in rendered:
                if isinstance(value, (dict, list)):
                    rendered = rendered.replace(placeholder, json.dumps(value, ensure_ascii=False, indent=2))
                else:
                    rendered = rendered.replace(placeholder, str(value))

        # 替换上下文
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in rendered:
                if isinstance(value, (dict, list)):
                    rendered = rendered.replace(placeholder, json.dumps(value, ensure_ascii=False, indent=2))
                else:
                    rendered = rendered.replace(placeholder, str(value))

        return rendered


class AgentContextBuilder:
    """
    Agent 上下文构建器

    从数据库加载相关数据，构建执行上下文
    """

    def __init__(self, db=None):
        self._db = db

    async def build_context(
        self,
        project_id: str,
        chapter_number: Optional[int] = None,
        include_characters: bool = True,
        include_settings: bool = True,
        include_hooks: bool = True,
        include_previous_outlines: bool = True,
    ) -> Dict[str, Any]:
        """
        构建完整的执行上下文

        Args:
            project_id: 项目 ID
            chapter_number: 章节序号
            include_characters: 是否包含角色
            include_settings: 是否包含设定
            include_hooks: 是否包含伏笔
            include_previous_outlines: 是否包含前文大纲

        Returns:
            Dict[str, Any]: 完整上下文
        """
        context = {}

        if not self._db:
            return context

        try:
            # 项目元数据
            project = await self._get_project(project_id)
            if project:
                context["project_metadata"] = project

            # 角色信息
            if include_characters:
                characters = await self._get_characters(project_id)
                if characters:
                    context["characters"] = characters

            # 世界设定
            if include_settings:
                settings = await self._get_world_settings(project_id)
                if settings:
                    context["world_settings"] = settings

            # 伏笔
            if include_hooks:
                hooks = await self._get_active_hooks(project_id)
                if hooks:
                    context["active_hooks"] = hooks

            # 前文大纲
            if include_previous_outlines and chapter_number:
                outlines = await self._get_previous_outlines(project_id, chapter_number)
                if outlines:
                    context["previous_outlines"] = outlines

        except Exception as e:
            logger.error(f"构建上下文失败: {e}")

        return context

    async def _get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目信息"""
        if not self._db:
            return None

        try:
            query = """
                SELECT id, title, genre, tone, target_word_count,
                       current_chapter, total_chapters, status
                FROM projects
                WHERE id = CAST(:project_id AS UUID)
            """
            results = await self._db.execute_query(query, {"project_id": project_id})
            return results[0] if results else None
        except Exception as e:
            logger.error(f"获取项目信息失败: {e}")
            return None

    async def _get_characters(self, project_id: str) -> List[Dict[str, Any]]:
        """获取角色信息"""
        if not self._db:
            return []

        try:
            query = """
                SELECT id, name, role_type, importance_tier, story_arc_role,
                       stance, current_status, core_goal
                FROM characters
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY
                    CASE importance_tier
                        WHEN 'protagonist' THEN 1
                        WHEN 'archenemy' THEN 2
                        WHEN 'deuteragonist' THEN 3
                        ELSE 4
                    END
            """
            results = await self._db.execute_query(query, {"project_id": project_id})
            return results or []
        except Exception as e:
            logger.error(f"获取角色信息失败: {e}")
            return []

    async def _get_world_settings(self, project_id: str) -> List[Dict[str, Any]]:
        """获取世界设定"""
        if not self._db:
            return []

        try:
            query = """
                SELECT id, name, category, description
                FROM world_settings
                WHERE project_id = CAST(:project_id AS UUID)
            """
            results = await self._db.execute_query(query, {"project_id": project_id})
            return results or []
        except Exception as e:
            logger.error(f"获取世界设定失败: {e}")
            return []

    async def _get_active_hooks(self, project_id: str) -> List[Dict[str, Any]]:
        """获取活跃伏笔"""
        if not self._db:
            return []

        try:
            query = """
                SELECT id, title, description, hook_type, status, priority
                FROM hooks
                WHERE project_id = CAST(:project_id AS UUID)
                  AND status IN ('pending', 'triggered', 'ready_for_resolution')
                ORDER BY priority DESC
            """
            results = await self._db.execute_query(query, {"project_id": project_id})
            return results or []
        except Exception as e:
            logger.error(f"获取伏笔失败: {e}")
            return []

    async def _get_previous_outlines(
        self,
        project_id: str,
        current_chapter: int,
        look_back: int = 3,
    ) -> List[Dict[str, Any]]:
        """获取前文大纲"""
        if not self._db:
            return []

        try:
            query = """
                SELECT chapter_number, title, summary
                FROM chapter_outlines
                WHERE project_id = CAST(:project_id AS UUID)
                  AND chapter_number < :current_chapter
                  AND chapter_number >= :start_chapter
                ORDER BY chapter_number DESC
            """
            start_chapter = max(1, current_chapter - look_back)
            results = await self._db.execute_query(
                query,
                {"project_id": project_id, "current_chapter": current_chapter, "start_chapter": start_chapter}
            )
            return results or []
        except Exception as e:
            logger.error(f"获取前文大纲失败: {e}")
            return []


# 单例
_prompt_builder: Optional[AgentPromptBuilder] = None
_context_builder: Optional[AgentContextBuilder] = None


def get_agent_prompt_builder(db=None) -> AgentPromptBuilder:
    """获取 Agent Prompt 构建器单例"""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = AgentPromptBuilder(db)
    elif db is not None:
        _prompt_builder._db = db
    return _prompt_builder


def get_agent_context_builder(db=None) -> AgentContextBuilder:
    """获取 Agent 上下文构建器单例"""
    global _context_builder
    if _context_builder is None:
        _context_builder = AgentContextBuilder(db)
    elif db is not None:
        _context_builder._db = db
    return _context_builder
