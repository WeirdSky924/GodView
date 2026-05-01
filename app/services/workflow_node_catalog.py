"""Workflow node catalog and label normalization helpers."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.models.agent_template import AgentType
from app.models.workflow_definition import NodeType

logger = logging.getLogger(__name__)


SYSTEM_AGENT_NODE_CATALOG: List[Dict[str, Any]] = [

    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.SETTING.value,
        "scenario": "workflow_context",
        "label": "设定 Agent",
        "description": "按当前节点输入检索并传输相关已有设定",
        "category": "agent",
        "icon": "Settings",
        "color": "blue",
        "is_system": True,
    },
    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.WRITER.value,
        "scenario": "workflow_chapter_generation",
        "label": "作家 Agent",
        "description": "生成小说内容",
        "category": "agent",
        "icon": "PenTool",
        "color": "purple",
        "is_system": True,
    },
    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.MASTER_PLOTTER.value,
        "scenario": "workflow_plot_planning",
        "label": "总编剧 Agent",
        "description": "规划整体剧情结构",
        "category": "agent",
        "icon": "GitBranch",
        "color": "indigo",
        "is_system": True,
    },
    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.PLOTTER.value,
        "label": "编剧 Agent",
        "description": "规划局部剧情与桥段",
        "category": "agent",
        "icon": "GitBranch",
        "color": "violet",
        "is_system": True,
    },
    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.SUMMARIZER.value,
        "scenario": "workflow_summary",
        "label": "摘要 Agent",
        "description": "生成内容摘要",
        "category": "agent",
        "icon": "BookOpen",
        "color": "amber",
        "is_system": True,
    },
    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.EVALUATOR.value,
        "scenario": "chapter_quality_review",
        "label": "评估 Agent",
        "description": "评估内容质量",
        "category": "agent",
        "icon": "Search",
        "color": "orange",
        "is_system": True,
    },
    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.HOOK_MANAGER.value,
        "scenario": "workflow_hook_management",
        "label": "伏笔 Agent",
        "description": "管理伏笔和悬念",
        "category": "agent",
        "icon": "Link",
        "color": "cyan",
        "is_system": True,
    },
    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.EVENT_GENERATOR.value,
        "scenario": "event_generation",
        "label": "事件 Agent",
        "description": "生成随机事件",
        "category": "agent",
        "icon": "Dices",
        "color": "pink",
        "is_system": True,
    },
    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.WORLD_MAP_MANAGER.value,
        "scenario": "world_map_management",
        "label": "地图 Agent",
        "description": "管理世界地图和地点",
        "category": "agent",
        "icon": "Map",
        "color": "teal",
        "is_system": True,
    },
    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.PROC_GEN.value,
        "scenario": "procedural_generation",
        "label": "过程生成 Agent",
        "description": "过程化生成内容",
        "category": "agent",
        "icon": "Zap",
        "color": "yellow",
        "is_system": True,
    },
    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.DUNGEON_GENERATOR.value,
        "scenario": "dungeon_generation",
        "label": "副本生成 Agent",
        "description": "生成副本和关卡",
        "category": "agent",
        "icon": "Globe",
        "color": "emerald",
        "is_system": True,
    },
    {
        "type": NodeType.AGENT.value,
        "agent_type": AgentType.PLOT_OUTLINE.value,
        "scenario": "generate_chapter_outline",
        "label": "章节大纲 Agent",
        "description": "优先输出已准备的章节大纲，缺失时兜底生成",
        "category": "agent",
        "icon": "BookOpen",
        "color": "rose",
        "is_system": True,
    },
]

INTERACTION_NODE_CATALOG: List[Dict[str, Any]] = [
    {
        "type": NodeType.INPUT.value,
        "label": "用户输入",
        "description": "暂停等待用户输入",
        "category": "interaction",
        "icon": "MessageSquare",
        "color": "blue",
        "is_system": True,
        "config_hints": {
            "prompt": {"type": "string", "default": "请输入内容", "description": "提示语"}
        },
    },
    {
        "type": NodeType.GROUP_DISCUSSION.value,
        "label": "集体讨论",
        "description": "多个Agent进行创作会议",
        "category": "interaction",
        "icon": "MessageCircle",
        "color": "purple",
        "is_system": True,
        "supports_multiple": True,
    },
    {
        "type": NodeType.SCENE_PERFORMANCE.value,
        "label": "场景演绎",
        "description": "多角色同台飙戏",
        "category": "interaction",
        "icon": "Users",
        "color": "green",
        "is_system": True,
        "supports_multiple": True,
    },
]

CONTROL_NODE_CATALOG: List[Dict[str, Any]] = [
    {
        "type": NodeType.START.value,
        "label": "开始",
        "description": "工作流起点",
        "category": "control",
        "icon": "Play",
        "color": "green",
        "is_system": True,
    },
    {
        "type": NodeType.END.value,
        "label": "结束",
        "description": "工作流终点",
        "category": "control",
        "icon": "Square",
        "color": "red",
        "is_system": True,
    },
    {
        "type": NodeType.CONDITION.value,
        "label": "条件分支",
        "description": "根据条件选择分支",
        "category": "control",
        "icon": "GitBranch",
        "color": "amber",
        "is_system": True,
        "config_hints": {
            "condition": {"type": "string", "default": "", "description": "条件表达式"}
        },
    },
    {
        "type": NodeType.PARALLEL.value,
        "label": "并行执行",
        "description": "同时执行多个分支",
        "category": "control",
        "icon": "Layers",
        "color": "indigo",
        "is_system": True,
    },
]


async def resolve_disabled_agent_types(project_id: Optional[str], db: Any) -> set[str]:
    disabled_agent_types: set[str] = set()
    if not db:
        return disabled_agent_types

    try:
        if project_id:
            from app.services.agent_config_service import get_agent_config_service

            config_service = get_agent_config_service()
            for node in get_system_agent_nodes():
                agent_type = node.get("agent_type")
                if not agent_type:
                    continue
                runtime_state = await config_service.resolve_agent_runtime_state(
                    project_id,
                    agent_type,
                    node.get("scenario"),
                )
                if runtime_state.get("enabled") is False:
                    disabled_agent_types.add(agent_type)
        else:
            from app.services.agent_template_service import AgentTemplateService

            template_service = AgentTemplateService(db)
            templates = await template_service.list_templates(limit=100)
            for template in templates:
                if not template.is_enabled:
                    disabled_agent_types.add(template.agent_type.value)
    except Exception as exc:
        logger.warning(f"获取 Agent 模板启用状态失败: {exc}")

    return disabled_agent_types


def filter_enabled_agent_nodes(
    all_agent_nodes: List[Dict[str, Any]],
    disabled_agent_types: Optional[set[str]] = None,
) -> List[Dict[str, Any]]:
    disabled = disabled_agent_types or set()
    return [
        dict(node)
        for node in all_agent_nodes
        if node.get("agent_type") not in disabled
    ]


async def get_project_character_nodes(project_id: Optional[str], db: Any) -> List[Dict[str, Any]]:
    if not project_id or not db:
        return []

    try:
        characters = await db.execute_query(
            "SELECT id, name, importance_tier FROM characters WHERE project_id = :project_id ORDER BY importance_tier DESC, name",
            {"project_id": project_id},
        )
    except Exception as exc:
        logger.warning(f"获取项目角色失败: {exc}")
        return []

    return [
        {
            "type": NodeType.AGENT.value,
            "agent_type": AgentType.CHARACTER.value,
            "label": f"{char['name']} Agent",
            "description": f"角色 {char['name']} 的专属 Agent",
            "category": "agent",
            "icon": "User",
            "color": "green",
            "is_system": False,
            "character_id": str(char["id"]),
            "character_name": char["name"],
            "importance_tier": char.get("importance_tier", 1),
        }
        for char in characters
    ]


async def resolve_workflow_node_types_payload(
    project_id: Optional[str],
    db: Any,
    disabled_agent_types: Optional[set[str]] = None,
) -> Dict[str, Any]:
    all_agent_nodes = get_system_agent_nodes()
    agent_nodes = filter_enabled_agent_nodes(all_agent_nodes, disabled_agent_types)
    character_nodes = await get_project_character_nodes(project_id, db)

    return {
        "version": "v9.0",
        "agent_nodes": agent_nodes,
        "character_nodes": character_nodes,
        "interaction_nodes": get_interaction_nodes(),
        "control_nodes": get_control_nodes(),
    }


AGENT_LABEL_ALIASES: Dict[str, List[str]] = {
    AgentType.SETTING.value: ["设定 Agent", "设定", "设定Agent", "Setting", "Setting Agent"],
    AgentType.WRITER.value: ["作家 Agent", "作家", "Writer", "Writer Agent"],
    AgentType.MASTER_PLOTTER.value: ["总编剧 Agent", "总编剧", "Master Plotter", "Master Plotter Agent"],
    AgentType.PLOTTER.value: ["编剧 Agent", "编剧", "Plotter", "Plotter Agent"],
    AgentType.SUMMARIZER.value: ["摘要 Agent", "摘要", "摘要提取", "Summarizer", "Summarize Dialogue"],
    AgentType.EVALUATOR.value: ["评估 Agent", "评估", "Evaluator", "Evaluator Agent"],
    AgentType.HOOK_MANAGER.value: ["伏笔 Agent", "伏笔管理", "Hook Manager", "Hook Manager Agent"],
    AgentType.EVENT_GENERATOR.value: ["事件 Agent", "事件生成", "Event Generator", "Event Generator Agent"],
    AgentType.WORLD_MAP_MANAGER.value: ["地图 Agent", "地图管理", "World Map", "Map Agent", "World Map Agent"],
    AgentType.PROC_GEN.value: ["过程生成 Agent", "过程生成", "ProcGen", "Proc Gen", "ProcGen Agent"],
    AgentType.DUNGEON_GENERATOR.value: ["副本生成 Agent", "副本生成", "Dungeon Generator", "Dungeon Generator Agent", "Dungeon Agent"],
    AgentType.PLOT_OUTLINE.value: ["章节大纲 Agent", "章节大纲", "大纲 Agent", "Plot Outline", "Plot Outline Agent"],
    AgentType.SCENE_COORDINATOR.value: ["场景协调 Agent", "场景协调", "Scene Coordinator", "Scene Coordinator Agent"],
    AgentType.CHARACTER.value: ["角色 Agent", "角色", "角色对话", "角色演绎", "Character", "Character Agent"],
}

NODE_LABEL_ALIASES: Dict[str, List[str]] = {
    NodeType.START.value: ["开始", "Start", "start"],
    NodeType.END.value: ["结束", "End", "end"],
    NodeType.INPUT.value: ["用户输入", "等待输入", "User Input"],
    NodeType.GROUP_DISCUSSION.value: ["集体讨论", "创作讨论会", "Group Discussion"],
    NodeType.SCENE_PERFORMANCE.value: ["场景演绎", "Scene Performance"],
    NodeType.CONDITION.value: ["条件分支", "条件判断", "章节结束?", "质量达标?", "需要补充输入?", "Condition"],
    NodeType.PARALLEL.value: ["并行执行", "并行准备", "Parallel"],
}


def get_system_agent_nodes() -> List[Dict[str, Any]]:
    return [dict(node) for node in SYSTEM_AGENT_NODE_CATALOG]


def get_interaction_nodes() -> List[Dict[str, Any]]:
    return [dict(node) for node in INTERACTION_NODE_CATALOG]


def get_control_nodes() -> List[Dict[str, Any]]:
    return [dict(node) for node in CONTROL_NODE_CATALOG]


def get_canonical_label(node_type: str, agent_type: Optional[str] = None, character_name: Optional[str] = None) -> Optional[str]:
    if node_type == NodeType.AGENT.value and agent_type:
        if agent_type == AgentType.CHARACTER.value and character_name:
            return f"{character_name} Agent"
        for node in SYSTEM_AGENT_NODE_CATALOG:
            if node.get("agent_type") == agent_type:
                return node["label"]
        if agent_type == AgentType.CHARACTER.value:
            return "角色 Agent"
        return None

    for node in [*INTERACTION_NODE_CATALOG, *CONTROL_NODE_CATALOG]:
        if node["type"] == node_type:
            return node["label"]
    return None


def infer_agent_type_from_label(label: str) -> Optional[str]:
    normalized = (label or "").strip().lower()
    if not normalized:
        return None

    for agent_type, aliases in AGENT_LABEL_ALIASES.items():
        for alias in aliases:
            if alias.lower() == normalized:
                return agent_type
    return None


def should_normalize_label(node_type: str, label: str, canonical_label: Optional[str], agent_type: Optional[str] = None) -> bool:
    normalized = (label or "").strip()
    if not canonical_label:
        return False
    if not normalized:
        return True
    if normalized == canonical_label:
        return False

    if node_type == NodeType.AGENT.value and agent_type:
        return normalized in AGENT_LABEL_ALIASES.get(agent_type, [])

    return normalized in NODE_LABEL_ALIASES.get(node_type, [])


def normalize_workflow_node_data(node: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(node)
    label = str(normalized.get("label") or "").strip()
    node_id = str(normalized.get("id") or "")
    node_type = str(normalized.get("node_type") or "")
    agent_type = normalized.get("agent_type")

    if node_id == "start" or label in NODE_LABEL_ALIASES[NodeType.START.value]:
        normalized["node_type"] = NodeType.START.value
        normalized.pop("agent_type", None)
        node_type = NodeType.START.value
        agent_type = None
    elif node_id == "end" or label in NODE_LABEL_ALIASES[NodeType.END.value]:
        normalized["node_type"] = NodeType.END.value
        normalized.pop("agent_type", None)
        node_type = NodeType.END.value
        agent_type = None
    elif node_type == NodeType.AGENT.value and not agent_type and label:
        inferred = infer_agent_type_from_label(label)
        if inferred:
            normalized["agent_type"] = inferred
            agent_type = inferred

    character_name = normalized.get("character_name")
    canonical_label = get_canonical_label(node_type, agent_type, character_name)
    if should_normalize_label(node_type, label, canonical_label, agent_type):
        normalized["label"] = canonical_label
    elif not label and canonical_label:
        normalized["label"] = canonical_label

    return normalized


def normalize_workflow_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalize_workflow_node_data(node) for node in nodes]


def get_agent_type_options(node_types_payload: Dict[str, Any]) -> List[Dict[str, str]]:
    seen: set[Tuple[str, str]] = set()
    options: List[Dict[str, str]] = []
    for node in [*node_types_payload.get("agent_nodes", []), *node_types_payload.get("character_nodes", [])]:
        agent_type = node.get("agent_type")
        label = node.get("label")
        if not agent_type or not label:
            continue
        key = (agent_type, label if agent_type == AgentType.CHARACTER.value else agent_type)
        if key in seen:
            continue
        seen.add(key)
        if agent_type == AgentType.CHARACTER.value:
            label = "角色 Agent"
        options.append({"value": agent_type, "label": label})
    return options
