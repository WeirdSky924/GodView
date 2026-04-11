"""
角色选择器 - 根据剧情需要智能选择应该登场的角色

职责：
1. 分析当前场景和剧情焦点
2. 根据角色与剧情的关联度选择角色
3. 考虑角色重要性和出场频率
4. 避免角色过度集中或缺失
"""

import logging
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SceneContext:
    """场景上下文"""
    location: str = ""
    atmosphere: str = ""
    plot_focus: str = ""
    key_events: List[str] = None
    involved_characters: List[str] = None  # 剧情提及的角色
    conflict_type: str = ""  # 冲突类型
    scene_type: str = ""  # 场景类型


@dataclass
class CharacterRelevance:
    """角色相关性评分"""
    character_name: str
    relevance_score: float  # 0-1
    reasons: List[str]
    tier: int  # 重要性层级


class CharacterSelector:
    """智能角色选择器"""

    # 场景类型与角色数量的推荐映射
    SCENE_CHARACTER_LIMITS = {
        "对话": {"min": 2, "max": 4, "ideal": 3},
        "战斗": {"min": 2, "max": 6, "ideal": 4},
        "日常": {"min": 1, "max": 3, "ideal": 2},
        "会议": {"min": 3, "max": 8, "ideal": 5},
        "独角戏": {"min": 1, "max": 1, "ideal": 1},
        "群像": {"min": 4, "max": 10, "ideal": 6},
        "默认": {"min": 2, "max": 4, "ideal": 3},
    }

    def __init__(self):
        self._character_cache: Dict[str, Dict[str, Any]] = {}

    async def select_characters(
        self,
        all_characters: List[Dict[str, Any]],
        scene_context: SceneContext,
        previous_characters: List[str] = None,
        director_guidance: Dict[str, Any] = None,
        max_characters: int = None,
    ) -> List[Dict[str, Any]]:
        """
        根据场景上下文智能选择应该登场的角色

        Args:
            all_characters: 所有可用角色列表
            scene_context: 场景上下文
            previous_characters: 上一场出现的角色
            director_guidance: 编剧指导（如指定角色）
            max_characters: 最大角色数量限制

        Returns:
            List[Dict]: 应该登场的角色列表（已排序）
        """
        if not all_characters:
            logger.warning("没有可用角色")
            return []

        # 1. 处理编剧指导（强制包含的角色）
        forced_characters: Set[str] = set()
        if director_guidance:
            forced_characters.update(director_guidance.get("required_characters", []))

        # 2. 计算每个角色的相关性得分
        relevance_scores = await self._calculate_relevance_scores(
            all_characters, scene_context, previous_characters or []
        )

        # 3. 确定角色数量限制
        scene_limits = self._get_scene_limits(scene_context.scene_type)
        max_chars = max_characters or scene_limits["max"]

        # 4. 选择角色
        selected = self._select_by_relevance(
            relevance_scores=relevance_scores,
            forced_characters=forced_characters,
            min_characters=scene_limits["min"],
            max_characters=max_chars,
        )

        # 5. 转换为角色数据
        selected_characters = []
        char_map = {c.get("name"): c for c in all_characters}
        for char_name in selected:
            if char_name in char_map:
                selected_characters.append(char_map[char_name])

        logger.info(
            f"角色选择完成: {len(selected_characters)} 个角色 - "
            f"{[c.get('name') for c in selected_characters]}"
        )

        return selected_characters

    async def _calculate_relevance_scores(
        self,
        characters: List[Dict[str, Any]],
        scene_context: SceneContext,
        previous_characters: List[str],
    ) -> List[CharacterRelevance]:
        """
        计算每个角色与当前场景的相关性得分

        评分维度：
        1. 剧情关联度（角色是否被剧情提及）
        2. 位置相关性（角色是否在场景地点）
        3. 角色目标匹配（角色目标是否与当前剧情相关）
        4. 连续性考量（是否在上一场出现）
        5. 重要性权重
        """
        scores = []

        for char in characters:
            char_name = char.get("name", "")
            score = 0.0
            reasons = []

            # 获取角色信息
            tier = self._get_tier(char)
            char_goals = char.get("goals", []) or []
            char_location = char.get("current_location", "")
            char_traits = char.get("personality_traits", []) or char.get("traits", [])

            # ===== 剧情关联度（最高权重 0.4）=====
            if scene_context.involved_characters:
                if char_name in scene_context.involved_characters:
                    score += 0.4
                    reasons.append("剧情提及此角色")

            # 检查剧情焦点中是否提及
            if scene_context.plot_focus and char_name in scene_context.plot_focus:
                score += 0.3
                reasons.append("剧情焦点包含此角色")

            # 检查关键事件中是否提及
            if scene_context.key_events:
                for event in scene_context.key_events:
                    if char_name in str(event):
                        score += 0.1
                        reasons.append(f"事件提及: {event[:30]}")
                        break

            # ===== 位置相关性（权重 0.15）=====
            if scene_context.location and char_location:
                if scene_context.location in char_location or char_location in scene_context.location:
                    score += 0.15
                    reasons.append("角色在场景位置")

            # ===== 角色目标匹配（权重 0.15）=====
            if char_goals and scene_context.plot_focus:
                for goal in char_goals:
                    if self._goal_matches_scene(goal, scene_context):
                        score += 0.15
                        reasons.append(f"目标相关: {goal[:30]}")
                        break

            # ===== 连续性考量（权重 0.1）=====
            if char_name in previous_characters:
                # 如果在上一场出现，给予一定的连续性加分
                score += 0.1
                reasons.append("上一场已出现（保持连续性）")
            elif tier <= 2:
                # 主角层角色如果没在上一场出现，可以考虑加入新鲜感
                score += 0.05

            # ===== 重要性基础分（权重 0.2）=====
            importance_score = self._get_importance_base_score(tier)
            score += importance_score
            if tier == 1:
                reasons.append("主角层角色")
            elif tier == 2:
                reasons.append("核心配角层角色")

            # ===== 场景氛围匹配 =====
            if scene_context.atmosphere and char_traits:
                atmosphere_match = self._check_atmosphere_match(
                    scene_context.atmosphere, char_traits
                )
                if atmosphere_match > 0:
                    score += 0.05 * atmosphere_match
                    reasons.append("性格契合场景氛围")

            # 归一化得分到 0-1
            score = min(1.0, score)

            scores.append(CharacterRelevance(
                character_name=char_name,
                relevance_score=score,
                reasons=reasons,
                tier=tier,
            ))

        # 按得分排序
        scores.sort(key=lambda x: x.relevance_score, reverse=True)

        return scores

    def _select_by_relevance(
        self,
        relevance_scores: List[CharacterRelevance],
        forced_characters: Set[str],
        min_characters: int,
        max_characters: int,
    ) -> List[str]:
        """
        根据相关性得分选择角色

        策略：
        1. 强制角色必须包含
        2. 按得分从高到低选择
        3. 确保至少有 min_characters 个角色
        4. 确保主角层角色有适当的出场机会
        """
        selected = []
        forced_added = set()

        # 首先添加强制角色
        for char_name in forced_characters:
            for rel in relevance_scores:
                if rel.character_name == char_name:
                    selected.append(char_name)
                    forced_added.add(char_name)
                    break

        # 按得分选择其他角色
        for rel in relevance_scores:
            if len(selected) >= max_characters:
                break

            if rel.character_name not in forced_added:
                # 得分超过阈值或者为了满足最小数量
                if rel.relevance_score >= 0.3 or len(selected) < min_characters:
                    selected.append(rel.character_name)

        # 如果角色数量不足最小值，补充主角层角色
        if len(selected) < min_characters:
            for rel in relevance_scores:
                if rel.character_name not in selected:
                    if rel.tier <= 2:  # 主角层或核心配角层
                        selected.append(rel.character_name)
                        if len(selected) >= min_characters:
                            break

        return selected

    def _get_scene_limits(self, scene_type: str) -> Dict[str, int]:
        """获取场景的角色数量限制"""
        return self.SCENE_CHARACTER_LIMITS.get(
            scene_type, self.SCENE_CHARACTER_LIMITS["默认"]
        )

    def _get_tier(self, character: Dict[str, Any]) -> int:
        """安全获取角色的重要性层级"""
        tier = character.get("importance_tier", 3)

        if isinstance(tier, int):
            return tier

        if isinstance(tier, str):
            tier_map = {
                "protagonist": 1, "co_protagonist": 1,
                "deuteragonist": 2, "mentor": 2, "love_interest": 2,
                "best_friend": 2, "archenemy": 2,
                "major_ally": 3, "major_antagonist": 3, "rival": 3,
                "family_member": 3, "guardian": 3, "arc_antagonist": 3,
                "minor_ally": 4, "minor_antagonist": 4, "recurring": 4,
                "npc": 5, "background": 5, "cameo": 5,
            }
            return tier_map.get(tier.lower().replace("-", "_"), 3)

        return 3

    def _get_importance_base_score(self, tier: int) -> float:
        """获取重要性基础分"""
        scores = {
            1: 0.2,   # 主角层
            2: 0.15,  # 核心配角层
            3: 0.1,   # 重要配角层
            4: 0.05,  # 阶段性角色
            5: 0.02,  # 背景角色
        }
        return scores.get(tier, 0.1)

    def _goal_matches_scene(self, goal: str, scene_context: SceneContext) -> bool:
        """检查角色目标是否与场景匹配"""
        if not goal:
            return False

        goal_lower = goal.lower()

        # 检查剧情焦点
        if scene_context.plot_focus:
            focus_lower = scene_context.plot_focus.lower()
            # 简单的关键词匹配
            common_keywords = [
                "战斗", "修炼", "学习", "探索", "复仇", "保护",
                "调查", "寻找", "救援", "谈判", "竞争",
            ]
            for kw in common_keywords:
                if kw in goal_lower and kw in focus_lower:
                    return True

        # 检查冲突类型
        if scene_context.conflict_type:
            if scene_context.conflict_type in goal_lower:
                return True

        return False

    def _check_atmosphere_match(
        self, atmosphere: str, traits: List[str]
    ) -> float:
        """检查角色性格是否匹配场景氛围"""
        if not atmosphere or not traits:
            return 0.0

        atmosphere_traits_map = {
            "紧张": ["冷静", "谨慎", "果断", "勇敢"],
            "轻松": ["幽默", "乐观", "开朗", "随和"],
            "悲伤": ["敏感", "深沉", "温柔", "善良"],
            "激昂": ["热血", "冲动", "激情", "豪迈"],
            "神秘": ["神秘", "深沉", "聪慧", "狡黠"],
        }

        matching_traits = atmosphere_traits_map.get(atmosphere, [])
        if not matching_traits:
            return 0.0

        match_count = sum(1 for t in traits if any(m in t for m in matching_traits))
        return min(1.0, match_count / 2)


def extract_scene_context(
    scene_directions: Dict[str, Any],
    previous_output: Dict[str, Any],
    plot_focus: str = "",
) -> SceneContext:
    """
    从场景方向和上节点输出中提取场景上下文

    Args:
        scene_directions: 场景方向（编剧设定）
        previous_output: 上一个节点的输出
        plot_focus: 当前剧情焦点

    Returns:
        SceneContext: 场景上下文对象
    """
    context = SceneContext()

    # 从场景方向提取
    if scene_directions:
        context.location = scene_directions.get("main_scene", "")
        context.atmosphere = scene_directions.get("atmosphere", "")
        context.scene_type = scene_directions.get("scene_type", "")

        # 获取场景中指定的角色
        character_roles = scene_directions.get("character_roles", {})
        if character_roles:
            context.involved_characters = list(character_roles.keys())

        # 获取冲突点
        conflicts = scene_directions.get("conflict_points", [])
        if conflicts:
            context.conflict_type = conflicts[0] if isinstance(conflicts[0], str) else conflicts[0].get("type", "")

    # 从上节点输出提取
    if previous_output:
        # 提取关键事件
        events = previous_output.get("key_events", [])
        if events:
            context.key_events = events[:5]

        # 提取剧情焦点
        if not plot_focus:
            plot_focus = previous_output.get("plot_focus", "")
        context.plot_focus = plot_focus

        # 从内容中提取涉及的角色
        content = previous_output.get("content", "") or previous_output.get("full_content", "")
        if content and not context.involved_characters:
            # 简单的姓名提取（后续可以用 NER 改进）
            context.involved_characters = _extract_names_from_content(content)

    return context


def _extract_names_from_content(content: str) -> List[str]:
    """从内容中提取角色名称（简单实现）"""
    import re

    # 匹配中文人名模式（2-4个字，可能出现在引号或特定位置）
    patterns = [
        r'【([^\】]+)】',  # 【角色名】
        r'"([^"]+)"说道',  # "角色名"说道
        r'([^\s，。！？]{2,4})说道',  # 角色名说道
        r'([^\s，。！？]{2,4})冷声道',  # 角色名冷声道
    ]

    names = set()
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            if len(match) >= 2 and len(match) <= 4:
                # 过滤掉常见的非人名词汇
                exclude_words = ["此时", "忽然", "突然", "这时", "然后", "虽然", "但是"]
                if match not in exclude_words:
                    names.add(match)

    return list(names)[:10]  # 最多返回10个


# 全局实例
_character_selector: Optional[CharacterSelector] = None


def get_character_selector() -> CharacterSelector:
    """获取角色选择器单例"""
    global _character_selector
    if _character_selector is None:
        _character_selector = CharacterSelector()
    return _character_selector
