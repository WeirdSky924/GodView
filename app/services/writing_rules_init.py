"""
写作规则初始化服务
在系统启动时将内置的网文写作规则加载到数据库
整合了基础网文写作规范和番茄小说网写作技巧
"""

import logging
from typing import List, Dict, Any

from app.data.web_novel_writing_rules import (
    WEB_NOVEL_WRITING_RULES,
    WEB_NOVEL_RULE_SETS,
)
from app.data.fanqie_writing_rules import (
    FANQIE_WRITING_RULES,
    FANQIE_RULE_SETS,
)

logger = logging.getLogger(__name__)

# 合并所有写作规则
ALL_WRITING_RULES = WEB_NOVEL_WRITING_RULES + FANQIE_WRITING_RULES

# 合并所有规则集
ALL_RULE_SETS = WEB_NOVEL_RULE_SETS + FANQIE_RULE_SETS


async def init_writing_rules(db_session=None) -> Dict[str, int]:
    """
    初始化写作规则到数据库

    Args:
        db_session: 数据库会话（可选）

    Returns:
        Dict: 初始化结果统计
    """
    stats = {
        "rules_created": 0,
        "rules_updated": 0,
        "rule_sets_created": 0,
        "rule_sets_updated": 0,
    }

    # TODO: 实现数据库持久化
    # 目前规则数据存储在内存中，通过 API 直接返回

    total_rules = len(ALL_WRITING_RULES)
    total_sets = len(ALL_RULE_SETS)

    logger.info(f"写作规则初始化完成: {total_rules} 条规则, {total_sets} 个规则集")
    logger.info(f"  - 基础网文规则: {len(WEB_NOVEL_WRITING_RULES)} 条")
    logger.info(f"  - 番茄写作规则: {len(FANQIE_WRITING_RULES)} 条")

    return stats


def get_system_writing_rules(
    category: str = None,
    severity: str = None,
    tags: List[str] = None,
    search: str = None,
    source: str = None,
) -> List[Dict[str, Any]]:
    """
    获取系统写作规则

    Args:
        category: 分类过滤
        severity: 严重程度过滤
        tags: 标签过滤
        search: 搜索关键词
        source: 来源过滤 ("fanqie" 或 "web_novel")

    Returns:
        List: 规则列表
    """
    # 根据来源选择规则
    if source == "fanqie":
        rules = FANQIE_WRITING_RULES.copy()
    elif source == "web_novel":
        rules = WEB_NOVEL_WRITING_RULES.copy()
    else:
        rules = ALL_WRITING_RULES.copy()

    # 分类过滤
    if category:
        rules = [r for r in rules if r.get("category") == category]

    # 严重程度过滤
    if severity:
        rules = [r for r in rules if r.get("severity") == severity]

    # 标签过滤
    if tags:
        rules = [r for r in rules if any(tag in r.get("tags", []) for tag in tags)]

    # 搜索
    if search:
        search_lower = search.lower()
        rules = [
            r for r in rules
            if search_lower in r.get("name", "").lower()
            or search_lower in r.get("description", "").lower()
            or search_lower in r.get("content", "").lower()
        ]

    return rules


def get_system_rule_sets(
    category: str = None,
    tags: List[str] = None,
    target_genre: str = None,
    source: str = None,
) -> List[Dict[str, Any]]:
    """
    获取系统规则集

    Args:
        category: 分类过滤
        tags: 标签过滤
        target_genre: 目标体裁过滤
        source: 来源过滤 ("fanqie" 或 "web_novel")

    Returns:
        List: 规则集列表
    """
    # 根据来源选择规则集
    if source == "fanqie":
        rule_sets = FANQIE_RULE_SETS.copy()
    elif source == "web_novel":
        rule_sets = WEB_NOVEL_RULE_SETS.copy()
    else:
        rule_sets = ALL_RULE_SETS.copy()

    # 分类过滤
    if category:
        rule_sets = [rs for rs in rule_sets if rs.get("category") == category]

    # 标签过滤
    if tags:
        rule_sets = [rs for rs in rule_sets if any(tag in rs.get("tags", []) for tag in tags)]

    # 目标体裁过滤
    if target_genre:
        rule_sets = [rs for rs in rule_sets if target_genre in rs.get("target_genres", [])]

    return rule_sets


def get_system_rule_by_id(rule_id: str) -> Dict[str, Any] | None:
    """根据ID获取系统规则"""
    for rule in ALL_WRITING_RULES:
        if rule["id"] == rule_id:
            return rule.copy()
    return None


def get_system_rule_set_by_id(rule_set_id: str) -> Dict[str, Any] | None:
    """根据ID获取系统规则集"""
    for rule_set in ALL_RULE_SETS:
        if rule_set["id"] == rule_set_id:
            return rule_set.copy()
    return None


def build_writing_prompt(
    rule_ids: List[str] = None,
    rule_set_ids: List[str] = None,
    category: str = None,
    severity_min: str = "recommended",
) -> str:
    """
    构建写作规则提示词

    Args:
        rule_ids: 指定规则ID列表
        rule_set_ids: 规则集ID列表
        category: 只包含指定分类
        severity_min: 最低严重程度

    Returns:
        str: 写作规则提示词
    """
    severity_order = ["required", "strong", "recommended", "optional", "info"]

    # 收集规则
    rules_to_include = []

    # 从规则集收集
    if rule_set_ids:
        for rs_id in rule_set_ids:
            rule_set = get_system_rule_set_by_id(rs_id)
            if rule_set:
                for rule_id in rule_set.get("rule_ids", []):
                    rule = get_system_rule_by_id(rule_id)
                    if rule and rule not in rules_to_include:
                        rules_to_include.append(rule)

    # 直接添加规则
    if rule_ids:
        for rule_id in rule_ids:
            rule = get_system_rule_by_id(rule_id)
            if rule and rule not in rules_to_include:
                rules_to_include.append(rule)

    # 如果没有指定，使用所有规则
    if not rules_to_include:
        rules_to_include = ALL_WRITING_RULES.copy()

    # 过滤
    if category:
        rules_to_include = [r for r in rules_to_include if r.get("category") == category]

    if severity_min and severity_min in severity_order:
        min_index = severity_order.index(severity_min)
        rules_to_include = [
            r for r in rules_to_include
            if severity_order.index(r.get("severity", "recommended")) <= min_index
        ]

    # 构建提示词
    prompt_parts = ["# 写作规范指南\n"]

    # 按严重程度分组
    by_severity = {}
    for rule in rules_to_include:
        sev = rule.get("severity", "recommended")
        if sev not in by_severity:
            by_severity[sev] = []
        by_severity[sev].append(rule)

    severity_labels = {
        "required": "必须遵守",
        "strong": "强烈建议",
        "recommended": "推荐",
        "optional": "可选",
        "info": "信息",
    }

    for sev in severity_order:
        if sev not in by_severity:
            continue

        label = severity_labels.get(sev, sev)
        prompt_parts.append(f"\n## [{label}]\n")

        for rule in by_severity[sev]:
            prompt_parts.append(f"\n### {rule.get('name', '未命名规则')}\n")
            prompt_parts.append(f"{rule.get('content', '')}\n")

            # 示例
            examples = rule.get("examples", [])
            if examples:
                prompt_parts.append("\n**示例：**\n")
                for ex in examples[:3]:  # 最多3个示例
                    prompt_parts.append(f"- {ex}\n")

            # 反例
            counter_examples = rule.get("counter_examples", [])
            if counter_examples:
                prompt_parts.append("\n**反例：**\n")
                for ce in counter_examples[:2]:  # 最多2个反例
                    prompt_parts.append(f"- {ce}\n")

    return "".join(prompt_parts)


def get_writing_rules_stats() -> Dict[str, Any]:
    """
    获取写作规则统计信息

    Returns:
        Dict: 统计信息
    """
    # 按分类统计
    by_category = {}
    for rule in ALL_WRITING_RULES:
        cat = rule.get("category", "other")
        by_category[cat] = by_category.get(cat, 0) + 1

    # 按严重程度统计
    by_severity = {}
    for rule in ALL_WRITING_RULES:
        sev = rule.get("severity", "recommended")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    # 按来源统计
    by_source = {
        "web_novel": len(WEB_NOVEL_WRITING_RULES),
        "fanqie": len(FANQIE_WRITING_RULES),
    }

    return {
        "total_rules": len(ALL_WRITING_RULES),
        "total_rule_sets": len(ALL_RULE_SETS),
        "by_category": by_category,
        "by_severity": by_severity,
        "by_source": by_source,
    }
