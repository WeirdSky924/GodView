"""
角色晋升服务 (Character Promotion Service)
v4/v5 核心需求：处理 candidate character → durable character 的升级逻辑，
              包括 bootstrap 初始分类和 runtime 后续晋升
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.seed import CharacterCandidate
from app.models.character import Character, CharacterStatus
from app.models.project import ProjectStatus

logger = logging.getLogger(__name__)


class CharacterPromotionService:
    """角色晋升服务 - 负责角色从候选到正式的转换"""

    def __init__(self):
        # 候选角色缓存：{project_id: [CharacterCandidate]}
        self._candidates: Dict[str, List[CharacterCandidate]] = {}
        # 晋升阈值配置
        self.promotion_thresholds = {
            "appearance_count": 3,  # 出现次数阈值
            "importance_score": 0.7,  # 重要性评分阈值
            "relationship_count": 2,  # 关系数量阈值
        }

    async def add_candidate(
        self,
        project_id: str,
        candidate: CharacterCandidate,
    ) -> Dict[str, Any]:
        """
        添加候选角色

        Args:
            project_id: 项目 ID
            candidate: 角色候选

        Returns:
            Dict: 添加结果
        """
        if project_id not in self._candidates:
            self._candidates[project_id] = []

        # 生成候选 ID
        candidate_id = f"candidate_{uuid.uuid4().hex[:12]}"
        candidate_importance = candidate.importance_score or 0.5

        candidate_with_id = CharacterCandidate(
            name=candidate.name,
            role=candidate.role,
            description=candidate.description,
            importance_score=candidate_importance,
            traits=candidate.traits,
            relationships=candidate.relationships,
            background_story=candidate.background_story,
            appearance=candidate.appearance,
            goals=candidate.goals,
            inventory=candidate.inventory,
            current_location=candidate.current_location,
            speech_pattern=candidate.speech_pattern,
            lexicon=candidate.lexicon,
            forbidden_words=candidate.forbidden_words,
            voice_samples=candidate.voice_samples,
            attributes=candidate.attributes,
        )

        self._candidates[project_id].append(candidate_with_id)

        # 自动检查是否可以晋升
        promotion_needed = await self.check_promotion_needed(project_id, candidate_with_id)

        return {
            "success": True,
            "candidate_id": candidate_id,
            "candidate": candidate_with_id.model_dump(),
            "promotion_needed": promotion_needed,
        }

    async def get_candidates(self, project_id: str) -> List[CharacterCandidate]:
        """获取项目的所有候选角色"""
        return self._candidates.get(project_id, [])

    async def remove_candidate(
        self,
        project_id: str,
        candidate_name: str,
    ) -> bool:
        """移除候选角色"""
        candidates = self._candidates.get(project_id, [])
        self._candidates[project_id] = [
            c for c in candidates if c.name != candidate_name
        ]
        return True

    async def promote_candidate(
        self,
        project_id: str,
        candidate_name: str,
        world_id: str,
        promotion_reason: str,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        将候选角色晋升为正式角色

        Args:
            project_id: 项目 ID
            candidate_name: 候选角色名称
            world_id: 世界 ID
            promotion_reason: 晋升原因
            additional_data: 附加数据

        Returns:
            Dict: 晋升结果
        """
        candidates = self._candidates.get(project_id, [])
        candidate = next((c for c in candidates if c.name == candidate_name), None)

        if not candidate:
            raise ValueError(f"Candidate {candidate_name} not found")

        # 创建正式角色
        character_id = f"char_{uuid.uuid4().hex[:12]}"

        character = Character(
            id=character_id,
            name=candidate.name,
            description=candidate.description,
            role=candidate.role or "supporting",
            status=CharacterStatus.ACTIVE,
            appearance=candidate.appearance,
            background_story=candidate.background_story,
            speech_pattern=candidate.speech_pattern,
            lexicon=candidate.lexicon or [],
            forbidden_words=candidate.forbidden_words or [],
            voice_samples=candidate.voice_samples or [],
            goals=candidate.goals or [],
            inventory=candidate.inventory or [],
            current_location=candidate.current_location,
            attributes=candidate.attributes or {},
        )

        # 保存到数据库
        from app.api.app import postgres_db
        if postgres_db:
            await postgres_db.save_character(character.model_dump(mode="json"))

        # 记录晋升日志
        await self._log_promotion(
            project_id=project_id,
            character_id=character_id,
            candidate_name=candidate_name,
            promotion_reason=promotion_reason,
        )

        # 从候选列表中移除
        await self.remove_candidate(project_id, candidate_name)

        return {
            "success": True,
            "character_id": character_id,
            "character": character.model_dump(),
            "promotion_reason": promotion_reason,
            "message": f"角色 {candidate_name} 已晋升为正式角色",
        }

    async def check_promotion_needed(
        self,
        project_id: str,
        candidate: CharacterCandidate,
    ) -> bool:
        """
        检查候选角色是否需要晋升

        基于多个因素自动判断：
        1. 重要性评分
        2. 关联的其他角色数量
        3. 是否有明确的目标

        Args:
            project_id: 项目 ID
            candidate: 候选角色

        Returns:
            bool: 是否需要晋升
        """
        # 检查重要性评分
        if candidate.importance_score >= self.promotion_thresholds["importance_score"]:
            return True

        # 检查关联角色数量
        if len(candidate.relationships or []) >= self.promotion_thresholds["relationship_count"]:
            return True

        # 检查是否有明确的目标
        if candidate.goals and len(candidate.goals) > 0:
            # 如果有重要目标和背景故事，可以晋升
            if candidate.importance_score >= 0.5 and candidate.background_story:
                return True

        return False

    async def auto_promote_high_priority(
        self,
        project_id: str,
        world_id: str,
    ) -> List[Dict[str, Any]]:
        """
        自动晋升高优先级候选角色

        Args:
            project_id: 项目 ID
            world_id: 世界 ID

        Returns:
            List: 晋升结果列表
        """
        candidates = self._candidates.get(project_id, [])
        promoted = []

        for candidate in candidates[:]:
            if await self.check_promotion_needed(project_id, candidate):
                try:
                    result = await self.promote_candidate(
                        project_id=project_id,
                        candidate_name=candidate.name,
                        world_id=world_id,
                        promotion_reason="自动晋升：高优先级候选",
                    )
                    promoted.append(result)
                except Exception as e:
                    logger.error(f"自动晋升失败：{e}")

        return promoted

    async def get_promotion_stats(self, project_id: str) -> Dict[str, Any]:
        """
        获取晋升统计信息

        Args:
            project_id: 项目 ID

        Returns:
            Dict: 统计信息
        """
        candidates = self._candidates.get(project_id, [])

        return {
            "total_candidates": len(candidates),
            "high_priority_count": sum(
                1 for c in candidates
                if c.importance_score >= self.promotion_thresholds["importance_score"]
            ),
            "with_relationships_count": sum(
                1 for c in candidates
                if c.relationships and len(c.relationships) > 0
            ),
            "with_goals_count": sum(
                1 for c in candidates
                if c.goals and len(c.goals) > 0
            ),
        }

    async def _log_promotion(
        self,
        project_id: str,
        character_id: str,
        candidate_name: str,
        promotion_reason: str,
    ):
        """记录晋升日志"""
        logger.info(
            f"角色晋升记录 - project: {project_id}, "
            f"character: {character_id}, "
            f"candidate_name: {candidate_name}, "
            f"reason: {promotion_reason}"
        )

    # ==================== Bootstrap 阶段的方法 ====================

    async def promote_from_seed(
        self,
        project_id: str,
        world_id: str,
        seed_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        从 seed 数据中晋升主要角色（Bootstrap 阶段使用）

        Args:
            project_id: 项目 ID
            world_id: 世界 ID
            seed_data: 种子数据

        Returns:
            List: 晋升结果列表
        """
        promoted = []

        # 获取主要角色
        main_characters = seed_data.get("main_characters", [])
        supporting_characters = seed_data.get("supporting_characters", [])

        # 晋升所有 main characters
        for char_data in main_characters:
            candidate = CharacterCandidate(
                name=char_data.get("name", ""),
                role="main",
                description=char_data.get("description", ""),
                importance_score=char_data.get("importance_score", 0.9),
                traits=char_data.get("traits", []),
                relationships=char_data.get("relationships", []),
                background_story=char_data.get("background_story"),
                appearance=char_data.get("appearance"),
                goals=char_data.get("goals", []),
                inventory=char_data.get("inventory", []),
                current_location=char_data.get("current_location"),
                speech_pattern=char_data.get("speech_pattern"),
                lexicon=char_data.get("lexicon", []),
                forbidden_words=char_data.get("forbidden_words", []),
                voice_samples=char_data.get("voice_samples", []),
                attributes=char_data.get("attributes", {}),
            )

            try:
                result = await self.promote_candidate(
                    project_id=project_id,
                    candidate_name=candidate.name,
                    world_id=world_id,
                    promotion_reason="Bootstrap：主要角色自动晋升",
                )
                promoted.append(result)
            except Exception as e:
                logger.error(f"晋升角色失败：{e}")

        # 晋升部分 supporting characters（重要性高的）
        for char_data in supporting_characters:
            if char_data.get("importance_score", 0.5) >= 0.7:
                candidate = CharacterCandidate(
                    name=char_data.get("name", ""),
                    role="supporting",
                    description=char_data.get("description", ""),
                    importance_score=char_data.get("importance_score", 0.5),
                    traits=char_data.get("traits", []),
                    relationships=char_data.get("relationships", []),
                    background_story=char_data.get("background_story"),
                    goals=char_data.get("goals", []),
                )

                try:
                    result = await self.promote_candidate(
                        project_id=project_id,
                        candidate_name=candidate.name,
                        world_id=world_id,
                        promotion_reason="Bootstrap：配角自动晋升",
                    )
                    promoted.append(result)
                except Exception as e:
                    logger.error(f"晋升角色失败：{e}")

        return promoted


# 全局单例
_promotion_service: Optional[CharacterPromotionService] = None


def get_character_promotion_service() -> CharacterPromotionService:
    """获取角色晋升服务单例"""
    global _promotion_service
    if _promotion_service is None:
        _promotion_service = CharacterPromotionService()
    return _promotion_service


def set_character_promotion_service(service: CharacterPromotionService):
    """设置角色晋升服务实例（用于测试）"""
    global _promotion_service
    _promotion_service = service