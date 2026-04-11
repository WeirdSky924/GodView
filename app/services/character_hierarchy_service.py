"""
角色层级服务
提供角色重要性层级的相关信息，帮助 Agent 理解角色的相对重要性
"""

from typing import Dict, List, Optional, Any
from enum import Enum

from app.models.character import (
    Character,
    CharacterImportanceTier,
    NarrativeWeight,
    StoryArcRole,
    TIER_DEFAULTS,
)


class CharacterHierarchyService:
    """角色层级服务"""

    # 层级分组名称
    TIER_GROUPS = {
        "protagonist_tier": {
            "name": "主角层",
            "tiers": [
                CharacterImportanceTier.PROTAGONIST,
                CharacterImportanceTier.CO_PROTAGONIST,
            ],
            "description": "故事的核心人物，所有剧情都围绕他们展开",
        },
        "core_supporting_tier": {
            "name": "核心配角层",
            "tiers": [
                CharacterImportanceTier.DEUTERAGONIST,
                CharacterImportanceTier.MENTOR,
                CharacterImportanceTier.LOVE_INTEREST,
                CharacterImportanceTier.BEST_FRIEND,
                CharacterImportanceTier.ARCHENEMY,
            ],
            "description": "贯穿全文的重要角色，有完整的人物弧光",
        },
        "major_supporting_tier": {
            "name": "重要配角层",
            "tiers": [
                CharacterImportanceTier.MAJOR_ALLY,
                CharacterImportanceTier.MAJOR_ANTAGONIST,
                CharacterImportanceTier.RIVAL,
                CharacterImportanceTier.FAMILY_MEMBER,
                CharacterImportanceTier.GUARDIAN,
            ],
            "description": "有独立剧情线的重要角色",
        },
        "arc_tier": {
            "name": "阶段性角色层",
            "tiers": [
                CharacterImportanceTier.ARC_ANtagonist,
                CharacterImportanceTier.ARC_ALLY,
                CharacterImportanceTier.RECURRING,
                CharacterImportanceTier.CATALYST,
                CharacterImportanceTier.MYSTERY_FIGURE,
            ],
            "description": "在特定篇章重要的角色",
        },
        "functional_tier": {
            "name": "功能性角色层",
            "tiers": [
                CharacterImportanceTier.MINION,
                CharacterImportanceTier.INFORMANT,
                CharacterImportanceTier.MENTOR_FIGURE,
                CharacterImportanceTier.COMIC_RELIEF,
                CharacterImportanceTier.VICTIM,
            ],
            "description": "服务于特定剧情功能的角色",
        },
        "background_tier": {
            "name": "背景层",
            "tiers": [
                CharacterImportanceTier.NPC,
                CharacterImportanceTier.BACKGROUND,
                CharacterImportanceTier.CAMEO,
            ],
            "description": "背景人物和路人角色",
        },
    }

    @classmethod
    def get_character_context_for_prompt(cls, character: Character) -> str:
        """
        获取角色在 prompt 中的上下文描述

        这段描述会被添加到 Agent 的 prompt 中，帮助 Agent 理解
        如何在生成内容时处理这个角色。

        Args:
            character: 角色对象

        Returns:
            str: 角色上下文描述
        """
        tier_info = character.get_tier_info()
        tier_name = cls.get_tier_display_name(character.importance_tier)
        group_name = cls.get_tier_group_name(character.importance_tier)

        context_parts = [
            f"【角色层级】{character.name} 是 {group_name} - {tier_name}",
            f"【剧情优先级】{character.plot_priority}/10",
            f"【叙事权重】{cls.get_narrative_weight_description(character.narrative_weight)}",
        ]

        # 添加角色作用描述
        if character.story_arc_role:
            role_desc = cls.get_story_arc_role_description(character.story_arc_role)
            context_parts.append(f"【故事作用】{role_desc}")

        # 添加层级特殊说明
        tier_desc = tier_info.get("description", "")
        if tier_desc:
            context_parts.append(f"【层级说明】{tier_desc}")

        # 添加叙事指令
        narrative_instruction = character.get_narrative_focus_instruction()
        if narrative_instruction:
            context_parts.append(f"【叙事处理】{narrative_instruction}")

        return "\n".join(context_parts)

    @classmethod
    def get_all_characters_context(cls, characters: List[Character]) -> str:
        """
        获取所有角色的层级上下文（按重要性排序）

        Args:
            characters: 角色列表

        Returns:
            str: 所有角色的上下文描述
        """
        # 按重要性排序
        sorted_chars = sorted(
            characters,
            key=lambda c: c.plot_priority,
            reverse=True
        )

        # 分组
        protagonist_chars = []
        core_chars = []
        major_chars = []
        other_chars = []

        for char in sorted_chars:
            if char.is_protagonist():
                protagonist_chars.append(char)
            elif char.is_core_character():
                core_chars.append(char)
            elif char.plot_priority >= 3:
                major_chars.append(char)
            else:
                other_chars.append(char)

        context_parts = ["# 角色层级体系\n"]

        # 主角层
        if protagonist_chars:
            context_parts.append("## 主角层（故事核心）")
            for char in protagonist_chars:
                context_parts.append(f"- **{char.name}** (优先级: {char.plot_priority}/10)")
                if char.description:
                    context_parts.append(f"  {char.description}")
                context_parts.append("")

        # 核心配角层
        if core_chars:
            context_parts.append("## 核心配角层（贯穿全文）")
            for char in core_chars:
                tier_name = cls.get_tier_display_name(char.importance_tier)
                context_parts.append(f"- **{char.name}** [{tier_name}] (优先级: {char.plot_priority}/10)")
                if char.description:
                    context_parts.append(f"  {char.description}")
                context_parts.append("")

        # 重要配角层
        if major_chars:
            context_parts.append("## 重要配角层（独立剧情线）")
            for char in major_chars:
                tier_name = cls.get_tier_display_name(char.importance_tier)
                context_parts.append(f"- **{char.name}** [{tier_name}] (优先级: {char.plot_priority}/10)")
            context_parts.append("")

        # 其他角色
        if other_chars:
            context_parts.append("## 其他角色")
            char_names = [char.name for char in other_chars[:10]]
            if len(other_chars) > 10:
                char_names.append(f"...等 {len(other_chars)} 人")
            context_parts.append(", ".join(char_names))

        # 添加处理指南
        context_parts.append("\n## 角色处理指南")
        context_parts.append(cls._get_handling_guidelines())

        return "\n".join(context_parts)

    @classmethod
    def _get_handling_guidelines(cls) -> str:
        """获取角色处理指南"""
        return """
1. **主角层处理**
   - 所有重要决策都要展现内心挣扎和思考过程
   - 每个场景都要考虑主角的视角和感受
   - 主角的成长和变化是剧情主线

2. **核心配角处理**
   - 给予足够的出场时间和独立情节
   - 与主角的互动要推动双方的人物弧光
   - 重要场景需要详细描写对话和动作

3. **反派处理**
   - 反派的行动要有合理动机
   - 反派的出场要制造张力和危机感
   - 反派的败亡要有戏剧性

4. **功能性角色处理**
   - 完成特定功能即可，不要过度展开
   - 可以用来调节节奏或提供信息
   - 不需要深入刻画心理活动

5. **背景角色处理**
   - 作为环境元素简单提及
   - 可以用群体描写代替个体
   - 不需要名字和详细特征
"""

    @classmethod
    def get_tier_display_name(cls, tier: CharacterImportanceTier) -> str:
        """获取层级的中文显示名称"""
        tier_names = {
            CharacterImportanceTier.PROTAGONIST: "主角",
            CharacterImportanceTier.CO_PROTAGONIST: "共同主角",
            CharacterImportanceTier.DEUTERAGONIST: "第二主角",
            CharacterImportanceTier.MENTOR: "导师",
            CharacterImportanceTier.LOVE_INTEREST: "恋爱对象",
            CharacterImportanceTier.BEST_FRIEND: "挚友/跟班",
            CharacterImportanceTier.ARCHENEMY: "宿敌",
            CharacterImportanceTier.MAJOR_ALLY: "重要盟友",
            CharacterImportanceTier.MAJOR_ANTAGONIST: "重要反派",
            CharacterImportanceTier.RIVAL: "竞争对手",
            CharacterImportanceTier.FAMILY_MEMBER: "家人",
            CharacterImportanceTier.GUARDIAN: "守护者",
            CharacterImportanceTier.ARC_ANtagonist: "篇章反派",
            CharacterImportanceTier.ARC_ALLY: "篇章盟友",
            CharacterImportanceTier.RECURRING: "常驻配角",
            CharacterImportanceTier.CATALYST: "催化剂角色",
            CharacterImportanceTier.MYSTERY_FIGURE: "神秘人物",
            CharacterImportanceTier.MINION: "爪牙",
            CharacterImportanceTier.INFORMANT: "消息提供者",
            CharacterImportanceTier.MENTOR_FIGURE: "指导型NPC",
            CharacterImportanceTier.COMIC_RELIEF: "喜剧担当",
            CharacterImportanceTier.VICTIM: "受害者",
            CharacterImportanceTier.NPC: "NPC",
            CharacterImportanceTier.BACKGROUND: "背景人物",
            CharacterImportanceTier.CAMEO: "客串",
        }
        return tier_names.get(tier, "未知")

    @classmethod
    def get_tier_group_name(cls, tier: CharacterImportanceTier) -> str:
        """获取层级所属分组的名称"""
        for group_key, group_info in cls.TIER_GROUPS.items():
            if tier in group_info["tiers"]:
                return group_info["name"]
        return "未知层级"

    @classmethod
    def get_narrative_weight_description(cls, weight: NarrativeWeight) -> str:
        """获取叙事权重的描述"""
        descriptions = {
            NarrativeWeight.FULL_FOCUS: "完全聚焦 - 需要详细描写心理、动作、对话的每个细节",
            NarrativeWeight.MAJOR_FOCUS: "主要关注 - 详细描写对话和关键动作",
            NarrativeWeight.MODERATE: "中等关注 - 主要描写对话和必要动作",
            NarrativeWeight.MINIMAL: "最小关注 - 仅描写必要行为",
            NarrativeWeight.BACKGROUND: "背景处理 - 简单提及或作为环境",
        }
        return descriptions.get(weight, "未知")

    @classmethod
    def get_story_arc_role_description(cls, role: StoryArcRole) -> str:
        """获取故事弧角色的描述"""
        descriptions = {
            StoryArcRole.HERO: "英雄角色，拯救者",
            StoryArcRole.GUIDE: "引导者，指引方向",
            StoryArcRole.HELPER: "帮助者，提供援助",
            StoryArcRole.PROTECTOR: "保护者，守护他人",
            StoryArcRole.MENTOR_ROLE: "导师，传授知识",
            StoryArcRole.VILLAIN: "反派，主要敌对者",
            StoryArcRole.OBSTACLE: "阻碍者，制造困难",
            StoryArcRole.BETRAYER: "叛徒，背叛者",
            StoryArcRole.CORRUPTOR: "堕落者，诱惑他人堕落",
            StoryArcRole.NEUTRAL: "中立，不偏不倚",
            StoryArcRole.WILD_CARD: "变数，立场不明确",
            StoryArcRole.DOUBLE_AGENT: "双面间谍",
            StoryArcRole.SACRIFICE: "牺牲者，为他人牺牲",
            StoryArcRole.REDEEMED: "救赎者，从反派转为正派",
            StoryArcRole.THRAGIC: "悲剧角色，命运悲惨",
            StoryArcRole.HERALD: "先驱，带来变化的消息",
        }
        return descriptions.get(role, "未知")

    @classmethod
    def suggest_tier_from_role(cls, role: str, is_antagonist: bool = False) -> CharacterImportanceTier:
        """
        根据角色类型建议重要性层级

        Args:
            role: 角色类型 (main/supporting/npc/antagonist)
            is_antagonist: 是否是反派

        Returns:
            CharacterImportanceTier: 建议的层级
        """
        if role == "main":
            if is_antagonist:
                return CharacterImportanceTier.ARCHENEMY
            return CharacterImportanceTier.PROTAGONIST
        elif role == "antagonist" or is_antagonist:
            return CharacterImportanceTier.MAJOR_ANTAGONIST
        elif role == "supporting":
            return CharacterImportanceTier.RECURRING
        else:
            return CharacterImportanceTier.NPC

    @classmethod
    def get_priority_characters_for_scene(
        cls,
        characters: List[Character],
        max_count: int = 5
    ) -> List[Character]:
        """
        获取场景中应该优先关注的角色

        Args:
            characters: 所有在场角色
            max_count: 最大返回数量

        Returns:
            List[Character]: 按优先级排序的角色列表
        """
        sorted_chars = sorted(
            characters,
            key=lambda c: (c.plot_priority, c.is_protagonist(), c.is_core_character()),
            reverse=True
        )
        return sorted_chars[:max_count]

    @classmethod
    def build_character_hierarchy_prompt(cls, characters: List[Character]) -> str:
        """
        构建 Agent 可用的角色层级 prompt

        这个 prompt 可以注入到任何需要理解角色重要性的 Agent 中

        Args:
            characters: 角色列表

        Returns:
            str: 完整的角色层级 prompt
        """
        if not characters:
            return ""

        prompt_parts = [
            "# 角色重要性层级系统\n",
            "在生成内容时，请根据角色的层级分配适当的关注度和描写详细程度。\n",
        ]

        # 主角层
        protagonists = [c for c in characters if c.is_protagonist()]
        if protagonists:
            prompt_parts.append("## 主角层（最高优先级）")
            for char in protagonists:
                prompt_parts.append(f"- **{char.name}**: {char.description or '故事核心人物'}")
                prompt_parts.append(f"  - 剧情优先级: {char.plot_priority}/10")
                prompt_parts.append(f"  - 所有场景都应考虑此角色的视角和感受")
            prompt_parts.append("")

        # 核心配角层
        core_chars = [c for c in characters if c.is_core_character() and not c.is_protagonist()]
        if core_chars:
            prompt_parts.append("## 核心配角层（高优先级）")
            for char in core_chars:
                tier_name = cls.get_tier_display_name(char.importance_tier)
                prompt_parts.append(f"- **{char.name}** [{tier_name}]: {char.description or ''}")
            prompt_parts.append("")

        # 重要角色层
        major_chars = [c for c in characters if c.plot_priority >= 3 and not c.is_core_character()]
        if major_chars:
            prompt_parts.append("## 重要角色层（中优先级）")
            for char in major_chars:
                tier_name = cls.get_tier_display_name(char.importance_tier)
                prompt_parts.append(f"- **{char.name}** [{tier_name}]")
            prompt_parts.append("")

        # 其他角色
        other_chars = [c for c in characters if c.plot_priority < 3]
        if other_chars:
            prompt_parts.append("## 其他角色（低优先级）")
            prompt_parts.append(", ".join([c.name for c in other_chars]))
            prompt_parts.append("")

        # 处理规则
        prompt_parts.append("## 处理规则")
        prompt_parts.append("""
1. 主角的决策和心理变化是剧情的核心，每章都要有主角的视角描写
2. 核心配角的出场和对话要推动剧情或主角的成长
3. 反派的行动要有合理动机，出场要制造张力
4. 低优先级角色不需要详细刻画，完成功能性任务即可
5. 场景描写应该以高优先级角色的视角为主导
""")

        return "\n".join(prompt_parts)


# 便捷函数
def get_character_hierarchy_service() -> CharacterHierarchyService:
    """获取角色层级服务实例"""
    return CharacterHierarchyService()
