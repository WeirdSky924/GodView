"""
技能记忆集成服务 - 连接 Skill 系统与 Agent 记忆

职责：
1. 为 Skill 执行提供记忆上下文
2. 将 Skill 执行结果存入记忆
3. 支持基于记忆的 Skill 触发
4. 管理跨 Skill 的知识共享
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.skill import Skill, SkillType
from app.services.agent_memory_service import (
    AgentMemoryService,
    MemoryType,
    MemoryImportance,
    get_memory_service,
)

logger = logging.getLogger(__name__)


class SkillMemoryIntegration:
    """技能记忆集成服务"""

    def __init__(self, db=None):
        self._db = db
        self._memory_service: Optional[AgentMemoryService] = None

    @property
    def memory_service(self) -> AgentMemoryService:
        """获取记忆服务"""
        if self._memory_service is None:
            self._memory_service = get_memory_service(self._db)
        return self._memory_service

    async def prepare_skill_context(
        self,
        skill: Skill,
        project_id: str,
        agent_type: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        为 Skill 执行准备上下文（包含记忆）

        Args:
            skill: Skill 对象
            project_id: 项目 ID
            agent_type: Agent 类型
            additional_context: 额外上下文

        Returns:
            Dict[str, Any]: 完整的执行上下文
        """
        context = additional_context or {}

        # 如果 Skill 配置了使用记忆
        if skill.use_agent_memory:
            memory_context = await self._load_memory_context(
                project_id=project_id,
                agent_type=agent_type,
                memory_types=skill.memory_types,
            )
            context["agent_memory"] = memory_context

        # 加载相关伏笔（如果技能涉及伏笔）
        if "hook" in skill.tags or "foreshadowing" in skill.tags:
            hooks_context = await self._load_hooks_context(project_id)
            context["project_hooks"] = hooks_context

        # 加载角色信息（如果技能涉及角色）
        if "character" in skill.tags or "stance" in skill.tags:
            characters_context = await self._load_characters_context(project_id)
            context["project_characters"] = characters_context

        return context

    async def _load_memory_context(
        self,
        project_id: str,
        agent_type: str,
        memory_types: List[str],
    ) -> Dict[str, Any]:
        """
        加载 Agent 记忆上下文

        Args:
            project_id: 项目 ID
            agent_type: Agent 类型
            memory_types: 记忆类型列表

        Returns:
            Dict[str, Any]: 记忆上下文
        """
        memory = await self.memory_service.get_memory(project_id, agent_type)

        # 按类型过滤
        filtered_memories = {
            "decisions": [],
            "observations": [],
            "facts": [],
        }

        for entry in memory.memories:
            entry_type = entry.type.value
            if entry_type in filtered_memories:
                # 转换为可序列化格式
                entry_data = {
                    "content": entry.content,
                    "summary": entry.summary,
                    "importance": entry.importance.value,
                    "tags": entry.tags,
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                }
                filtered_memories[entry_type].append(entry_data)

        # 如果指定了类型，只返回这些类型
        if memory_types:
            return {k: v for k, v in filtered_memories.items() if k in memory_types}

        return filtered_memories

    async def _load_hooks_context(
        self,
        project_id: str,
    ) -> Dict[str, Any]:
        """加载项目伏笔上下文"""
        if not self._db:
            return {"hooks": [], "pending_count": 0}

        try:
            query = """
                SELECT id, title, description, hook_type, status, priority,
                       created_at, plant_chapter_id
                FROM hooks
                WHERE project_id = CAST(:project_id AS UUID)
                  AND status IN ('pending', 'triggered', 'ready_for_resolution')
                ORDER BY priority DESC, created_at DESC
                LIMIT 20
            """
            results = await self._db.execute_query(
                query, {"project_id": project_id}
            )

            hooks = []
            for row in (results or []):
                hooks.append({
                    "id": str(row.get("id")),
                    "title": row.get("title"),
                    "description": row.get("description"),
                    "hook_type": row.get("hook_type"),
                    "status": row.get("status"),
                    "priority": row.get("priority"),
                })

            pending_count = sum(1 for h in hooks if h["status"] in ["pending", "triggered"])

            return {"hooks": hooks, "pending_count": pending_count}

        except Exception as e:
            logger.error(f"加载伏笔上下文失败: {e}")
            return {"hooks": [], "pending_count": 0}

    async def _load_characters_context(
        self,
        project_id: str,
    ) -> Dict[str, Any]:
        """加载项目角色上下文"""
        if not self._db:
            return {"characters": [], "villains": []}

        try:
            query = """
                SELECT id, name, role_type, importance_tier, story_arc_role,
                       stance, current_status
                FROM characters
                WHERE project_id = CAST(:project_id AS UUID)
                ORDER BY
                    CASE importance_tier
                        WHEN 'protagonist' THEN 1
                        WHEN 'archenemy' THEN 2
                        WHEN 'deuteragonist' THEN 3
                        WHEN 'major_ally' THEN 4
                        ELSE 5
                    END
            """
            results = await self._db.execute_query(
                query, {"project_id": project_id}
            )

            characters = []
            villains = []

            for row in (results or []):
                char_data = {
                    "id": str(row.get("id")),
                    "name": row.get("name"),
                    "role_type": row.get("role_type"),
                    "importance_tier": row.get("importance_tier"),
                    "story_arc_role": row.get("story_arc_role"),
                    "stance": row.get("stance"),
                    "current_status": row.get("current_status"),
                }
                characters.append(char_data)

                # 标记反派
                if row.get("role_type") in ["antagonist", "archenemy", "major_antagonist", "minion"]:
                    villains.append(char_data)

            return {"characters": characters, "villains": villains}

        except Exception as e:
            logger.error(f"加载角色上下文失败: {e}")
            return {"characters": [], "villains": []}

    async def record_skill_execution(
        self,
        skill: Skill,
        project_id: str,
        agent_type: str,
        input_params: Dict[str, Any],
        output_result: Dict[str, Any],
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        记录 Skill 执行结果到记忆

        Args:
            skill: Skill 对象
            project_id: 项目 ID
            agent_type: Agent 类型
            input_params: 输入参数
            output_result: 输出结果
            success: 是否成功
            error_message: 错误信息

        Returns:
            bool: 是否记录成功
        """
        if not skill.use_agent_memory:
            return True  # 不需要记录

        memory_type = MemoryType.DECISION if success else MemoryType.OBSERVATION
        importance = MemoryImportance.HIGH if skill.priority >= 80 else MemoryImportance.MEDIUM

        # 构建记忆内容
        content = f"执行技能 [{skill.name}]: "
        if success:
            content += "成功"
            if output_result:
                # 提取关键输出
                summary = self._extract_output_summary(output_result)
                content += f" - {summary}"
        else:
            content += f"失败: {error_message}"

        # 添加到记忆
        memory = await self.memory_service.get_memory(project_id, agent_type)
        memory.add_memory(
            content=content,
            memory_type=memory_type,
            importance=importance,
            context={
                "skill_id": skill.id,
                "skill_name": skill.name,
                "input_params": input_params,
                "output_result": output_result if success else None,
                "error_message": error_message,
            },
            tags=skill.tags + [skill.category.value],
        )

        await self.memory_service.save_memory(memory)
        logger.info(f"记录技能执行到记忆: {skill.name} ({agent_type})")

        return True

    def _extract_output_summary(self, output: Dict[str, Any]) -> str:
        """提取输出摘要"""
        # 尝试提取关键信息
        if "summary" in output:
            return str(output["summary"])[:100]
        if "result" in output:
            return str(output["result"])[:100]
        if "content" in output:
            return str(output["content"])[:100]

        # 返回 JSON 摘要
        return json.dumps(output, ensure_ascii=False)[:100]

    async def get_skill_recommendations(
        self,
        project_id: str,
        agent_type: str,
        current_context: str,
    ) -> List[Dict[str, Any]]:
        """
        基于记忆推荐可能需要的 Skill

        Args:
            project_id: 项目 ID
            agent_type: Agent 类型
            current_context: 当前上下文

        Returns:
            List[Dict[str, Any]]: 推荐的 Skill 列表
        """
        # 获取相关记忆
        relevant_memories = await self.memory_service.get_relevant_memories(
            project_id=project_id,
            agent_type=agent_type,
            query_text=current_context,
            limit=5,
        )

        recommendations = []

        for memory in relevant_memories:
            # 检查记忆中的技能使用记录
            context = memory.context or {}
            if "skill_id" in context:
                recommendations.append({
                    "skill_id": context["skill_id"],
                    "skill_name": context.get("skill_name", "未知技能"),
                    "relevance_score": 0.8,  # 基于记忆匹配
                    "reason": f"之前在类似场景使用过",
                })

        return recommendations[:3]  # 最多返回3个推荐


# 单例实例
_integration: Optional[SkillMemoryIntegration] = None


def get_skill_memory_integration(db=None) -> SkillMemoryIntegration:
    """获取技能记忆集成服务单例"""
    global _integration
    if _integration is None:
        _integration = SkillMemoryIntegration(db)
    elif db is not None:
        _integration._db = db
        _integration._memory_service = None  # 重置以使用新的 db
    return _integration
