"""
设定冲突检测引擎
检测新设定与现有设定之间的冲突
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.models.setting_agent import (
    SettingConflict,
    ConflictSeverity,
    ConflictResolutionStatus,
)
from app.models.lore import LoreEntry, LorePriority

logger = logging.getLogger(__name__)


class ConflictDetector:
    """设定冲突检测器"""

    def __init__(self):
        self._lore_cache: Dict[str, List[LoreEntry]] = {}

    def set_lore_cache(self, project_id: str, lore_list: List[LoreEntry]):
        """设置设定缓存"""
        self._lore_cache[project_id] = lore_list

    async def detect_conflicts(
        self,
        project_id: str,
        new_lore_data: Dict[str, Any],
        existing_lores: List[LoreEntry],
    ) -> List[SettingConflict]:
        """
        检测设定冲突

        Args:
            project_id: 项目 ID
            new_lore_data: 新设定数据
            existing_lores: 现有设定列表

        Returns:
            List[SettingConflict]: 检测到的冲突列表
        """
        conflicts = []

        # 1. 名称冲突检测
        name_conflict = await self._check_name_conflict(
            new_lore_data, existing_lores
        )
        if name_conflict:
            conflicts.append(name_conflict)

        # 2. 关键词冲突检测
        keyword_conflicts = await self._check_keyword_conflicts(
            new_lore_data, existing_lores
        )
        conflicts.extend(keyword_conflicts)

        # 3. 宪法级规则违规检测
        constitutional_conflict = await self._check_constitutional_violation(
            new_lore_data, existing_lores
        )
        if constitutional_conflict:
            conflicts.append(constitutional_conflict)

        # 4. 语义冲突检测（简化版，实际应该用 LLM）
        semantic_conflicts = await self._check_semantic_conflicts(
            new_lore_data, existing_lores
        )
        conflicts.extend(semantic_conflicts)

        return conflicts

    async def _check_name_conflict(
        self,
        new_lore_data: Dict[str, Any],
        existing_lores: List[LoreEntry],
    ) -> Optional[SettingConflict]:
        """检查名称冲突"""
        new_title = new_lore_data.get("title", "").lower().strip()
        if not new_title:
            return None

        for lore in existing_lores:
            existing_title = lore.title.lower().strip()
            if new_title == existing_title:
                return SettingConflict(
                    conflict_type="name_collision",
                    description=f"设定名称 '{new_lore_data.get('title')}' 与现有设定 '{lore.title}' 冲突",
                    severity=ConflictSeverity.HIGH,
                    existing_lore_id=lore.id,
                    existing_lore_title=lore.title,
                    new_lore_title=new_lore_data.get("title"),
                    resolution_suggestions=[
                        f"修改新设定的名称，避免与 '{lore.title}' 重复",
                        f"合并两个设定，保留更完整的版本",
                        f"为新设定添加后缀区分，如 '{new_lore_data.get('title')} (新)'",
                    ],
                )

        return None

    async def _check_keyword_conflicts(
        self,
        new_lore_data: Dict[str, Any],
        existing_lores: List[LoreEntry],
    ) -> List[SettingConflict]:
        """检查关键词冲突"""
        conflicts = []
        new_keywords = set(new_lore_data.get("keywords", []))
        new_category = new_lore_data.get("category", "")

        for lore in existing_lores:
            # 跳过不同类别的设定（关键词允许跨类别重复）
            if lore.category != new_category:
                continue

            existing_keywords = set(lore.keywords)
            common_keywords = new_keywords & existing_keywords

            if common_keywords and len(common_keywords) >= 2:
                # 多个共同关键词，可能是重复设定
                conflicts.append(SettingConflict(
                    conflict_type="keyword_overlap",
                    description=f"新设定与 '{lore.title}' 有多个共同关键词: {', '.join(common_keywords)}",
                    severity=ConflictSeverity.MEDIUM,
                    existing_lore_id=lore.id,
                    existing_lore_title=lore.title,
                    new_lore_title=new_lore_data.get("title"),
                    resolution_suggestions=[
                        "检查两个设定是否描述同一内容，考虑合并",
                        "调整关键词，使其更加区分",
                        "保持两个设定，但确保它们描述的是不同的方面",
                    ],
                ))

        return conflicts

    async def _check_constitutional_violation(
        self,
        new_lore_data: Dict[str, Any],
        existing_lores: List[LoreEntry],
    ) -> Optional[SettingConflict]:
        """检查是否违反宪法级规则"""
        # 获取宪法级规则
        constitutional_lores = [
            lore for lore in existing_lores
            if lore.priority == LorePriority.CONSTITUTIONAL
        ]

        if not constitutional_lores:
            return None

        new_content = new_lore_data.get("content", "").lower()
        new_title = new_lore_data.get("title", "")

        # 检查新设定是否与宪法级规则冲突
        for const_lore in constitutional_lores:
            # 简单的关键词匹配（实际应该用语义分析）
            const_keywords = set(const_lore.keywords)
            const_content = const_lore.content.lower()

            # 检查否定规则
            for keyword in const_keywords:
                if keyword.startswith("禁止") or keyword.startswith("不可"):
                    rule_item = keyword[2:].strip()  # 提取禁止的内容
                    if rule_item in new_content:
                        return SettingConflict(
                            conflict_type="constitutional_violation",
                            description=f"新设定 '{new_title}' 可能违反宪法级规则 '{const_lore.title}'",
                            severity=ConflictSeverity.CRITICAL,
                            existing_lore_id=const_lore.id,
                            existing_lore_title=const_lore.title,
                            new_lore_title=new_title,
                            resolution_suggestions=[
                                f"修改新设定，使其符合 '{const_lore.title}' 规则",
                                "如果这是特殊情况，需要明确说明原因和例外",
                                "考虑修改宪法级规则本身（需管理员权限）",
                            ],
                        )

        return None

    async def _check_semantic_conflicts(
        self,
        new_lore_data: Dict[str, Any],
        existing_lores: List[LoreEntry],
    ) -> List[SettingConflict]:
        """
        检查语义冲突（简化版）

        注：完整的语义冲突检测需要 LLM 辅助
        这里只做简单的规则匹配
        """
        conflicts = []
        new_category = new_lore_data.get("category", "")
        new_content = new_lore_data.get("content", "")

        # 只检查同类别的核心设定
        core_lores = [
            lore for lore in existing_lores
            if lore.category == new_category and lore.priority in [LorePriority.CORE, LorePriority.CONSTITUTIONAL]
        ]

        for lore in core_lores:
            # 检查是否有矛盾的关键词
            contradictions = self._find_contradictions(
                new_content, lore.content
            )
            if contradictions:
                conflicts.append(SettingConflict(
                    conflict_type="semantic_conflict",
                    description=f"新设定与 '{lore.title}' 可能存在语义冲突: {contradictions}",
                    severity=ConflictSeverity.HIGH,
                    existing_lore_id=lore.id,
                    existing_lore_title=lore.title,
                    new_lore_title=new_lore_data.get("title"),
                    resolution_suggestions=[
                        "检查两个设定是否确实矛盾",
                        "如果矛盾，选择保留哪个版本",
                        "考虑是否存在特殊情况可以同时成立",
                    ],
                ))

        return conflicts

    def _find_contradictions(self, text1: str, text2: str) -> Optional[str]:
        """
        查找两个文本之间的矛盾（简化版）

        实际应该使用 LLM 进行语义分析
        """
        # 简单的矛盾词对
        contradiction_pairs = [
            ("可以", "不可以"),
            ("能够", "不能"),
            ("存在", "不存在"),
            ("有", "没有"),
            ("允许", "禁止"),
            ("必须", "禁止"),
        ]

        text1_lower = text1.lower()
        text2_lower = text2.lower()

        for word1, word2 in contradiction_pairs:
            if word1 in text1_lower and word2 in text2_lower:
                return f"检测到矛盾词汇: '{word1}' vs '{word2}'"
            if word2 in text1_lower and word1 in text2_lower:
                return f"检测到矛盾词汇: '{word2}' vs '{word1}'"

        return None

    async def generate_resolution_suggestions(
        self,
        conflict: SettingConflict,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        生成冲突解决建议

        Args:
            conflict: 冲突对象
            context: 额外上下文

        Returns:
            List[str]: 解决建议列表
        """
        # 根据冲突类型生成不同的建议
        suggestions = list(conflict.resolution_suggestions)

        if conflict.conflict_type == "name_collision":
            suggestions.extend([
                "如果两个设定确实不同，建议使用更具描述性的名称",
                "考虑添加前缀或后缀来区分，如地域、时代等",
            ])
        elif conflict.conflict_type == "constitutional_violation":
            suggestions.extend([
                "这是严重冲突，必须在新设定生效前解决",
                "建议查阅宪法级规则的完整内容",
            ])
        elif conflict.conflict_type == "semantic_conflict":
            suggestions.extend([
                "建议详细阅读两个设定的完整内容",
                "考虑是否存在时间线或特殊条件下的例外",
            ])

        return suggestions[:5]  # 最多返回 5 条建议


# 全局单例
_conflict_detector: Optional[ConflictDetector] = None


def get_conflict_detector() -> ConflictDetector:
    """获取冲突检测器单例"""
    global _conflict_detector
    if _conflict_detector is None:
        _conflict_detector = ConflictDetector()
    return _conflict_detector
