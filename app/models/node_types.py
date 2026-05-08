"""
节点类型定义 - 用于前端动态渲染节点面板
v8 Agent协作可视化工作台
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NodeCategory(str, Enum):
    """节点类别"""

    AGENT = "agent"           # Agent节点
    CONTROL = "control"       # 控制节点
    INTERACTION = "interaction"  # 交互节点


class NodeTypeInfo(BaseModel):
    """节点类型信息"""

    type: str = Field(..., description="节点类型标识")
    label: str = Field(..., description="显示名称")
    description: str = Field(default="", description="节点描述")
    category: NodeCategory = Field(..., description="节点类别")
    icon: str = Field(default="Bot", description="图标名称（lucide-react）")
    color: str = Field(default="gray", description="颜色主题")

    # Agent 节点专属配置
    agent_type: Optional[str] = Field(None, description="绑定的Agent类型（仅AGENT类别）")
    is_system: bool = Field(default=False, description="是否系统内置")
    supports_multiple: bool = Field(default=False, description="是否支持多实例")

    # 配置提示
    config_hints: Dict[str, Any] = Field(default_factory=dict, description="配置提示")


# ==================== 系统 Agent 节点类型 ====================

SYSTEM_AGENT_NODES: List[NodeTypeInfo] = [
    # 核心 Agent
    NodeTypeInfo(
        type="agent",
        agent_type="master_plotter",
        label="总编剧",
        description="规划剧情大纲、章节结构、场景方向",
        category=NodeCategory.AGENT,
        icon="GitBranch",
        color="purple",
        is_system=True,
        config_hints={
            "temperature": {"default": 0.7, "description": "创意温度"},
        }
    ),
    NodeTypeInfo(
        type="agent",
        agent_type="writer",
        label="作家",
        description="执行章节内容写作，输出正文",
        category=NodeCategory.AGENT,
        icon="PenTool",
        color="green",
        is_system=True,
        config_hints={
            "temperature": {"default": 0.8, "description": "写作温度"},
        }
    ),
    NodeTypeInfo(
        type="agent",
        agent_type="summarizer",
        label="摘要员",
        description="生成内容摘要、提取关键信息",
        category=NodeCategory.AGENT,
        icon="BookOpen",
        color="cyan",
        is_system=True,
    ),
    NodeTypeInfo(
        type="agent",
        agent_type="evaluator",
        label="评估员",
        description="评估内容质量、检查一致性",
        category=NodeCategory.AGENT,
        icon="Search",
        color="red",
        is_system=True,
    ),
    NodeTypeInfo(
        type="agent",
        agent_type="hook_manager",
        label="伏笔管理员",
        description="管理伏笔的埋设、追踪和回收",
        category=NodeCategory.AGENT,
        icon="Link",
        color="orange",
        is_system=True,
    ),
    NodeTypeInfo(
        type="agent",
        agent_type="setting",
        label="设定管理员",
        description="管理和维护世界观设定",
        category=NodeCategory.AGENT,
        icon="Settings",
        color="blue",
        is_system=True,
    ),
    NodeTypeInfo(
        type="agent",
        agent_type="event_generator",
        label="事件生成器",
        description="生成故事事件、转折和随机变数",
        category=NodeCategory.AGENT,
        icon="Dices",
        color="pink",
        is_system=True,
    ),
    NodeTypeInfo(
        type="agent",
        agent_type="world_map_manager",
        label="地图管理员",
        description="管理世界地图、地点和空间关系",
        category=NodeCategory.AGENT,
        icon="Map",
        color="teal",
        is_system=True,
    ),
    NodeTypeInfo(
        type="agent",
        agent_type="proc_gen",
        label="过程生成器",
        description="过程化生成内容",
        category=NodeCategory.AGENT,
        icon="Zap",
        color="yellow",
        is_system=True,
    ),
    NodeTypeInfo(
        type="agent",
        agent_type="dungeon_generator",
        label="副本生成器",
        description="生成副本和关卡",
        category=NodeCategory.AGENT,
        icon="Globe",
        color="emerald",
        is_system=True,
    ),
    NodeTypeInfo(
        type="agent",
        agent_type="plot_outline",
        label="章节大纲",
        description="规划章节大纲",
        category=NodeCategory.AGENT,
        icon="BookOpen",
        color="rose",
        is_system=True,
    ),
]

# ==================== 特殊交互节点类型 ====================

INTERACTION_NODES: List[NodeTypeInfo] = [
    NodeTypeInfo(
        type="scene_performance",
        label="场景演绎",
        description="多角色同台演绎场景，自动协调角色Agent",
        category=NodeCategory.INTERACTION,
        icon="Users",
        color="rose",
        is_system=True,
        supports_multiple=True,
        config_hints={
            "scene_mode": {
                "type": "select",
                "options": ["interactive", "parallel"],
                "default": "interactive",
                "description": "互动模式或并行模式"
            },
            "required_characters": {
                "type": "character_multiselect",
                "description": "选择参与的角色"
            },
            "need_background_characters": {
                "type": "boolean",
                "default": True,
                "description": "是否需要背景角色"
            },
        }
    ),
    NodeTypeInfo(
        type="group_discussion",
        label="集体讨论",
        description="多个Agent进行创作会议讨论",
        category=NodeCategory.INTERACTION,
        icon="MessageCircle",
        color="indigo",
        is_system=True,
        supports_multiple=True,
        config_hints={
            "discussion_topic": {
                "type": "text",
                "description": "讨论主题"
            },
            "participants": {
                "type": "agent_multiselect",
                "description": "选择参与讨论的Agent"
            },
        }
    ),
]

# ==================== 控制节点类型 ====================

CONTROL_NODES: List[NodeTypeInfo] = [
    NodeTypeInfo(
        type="start",
        label="开始",
        description="工作流起点",
        category=NodeCategory.CONTROL,
        icon="Play",
        color="green",
        is_system=True,
    ),
    NodeTypeInfo(
        type="end",
        label="结束",
        description="工作流终点",
        category=NodeCategory.CONTROL,
        icon="Square",
        color="gray",
        is_system=True,
    ),
    NodeTypeInfo(
        type="condition",
        label="条件分支",
        description="根据条件选择执行路径",
        category=NodeCategory.CONTROL,
        icon="GitBranch",
        color="amber",
        is_system=True,
        config_hints={
            "conditions": {
                "type": "condition_editor",
                "description": "条件表达式"
            }
        }
    ),
    NodeTypeInfo(
        type="parallel",
        label="并行执行",
        description="同时执行多个分支",
        category=NodeCategory.CONTROL,
        icon="Layers",
        color="purple",
        is_system=True,
    ),
    NodeTypeInfo(
        type="input",
        label="用户输入",
        description="等待用户输入或干预",
        category=NodeCategory.CONTROL,
        icon="MessageSquare",
        color="blue",
        is_system=True,
        config_hints={
            "prompt": {
                "type": "text",
                "description": "输入提示"
            }
        }
    ),
]


def get_all_node_types() -> List[NodeTypeInfo]:
    """获取所有节点类型"""
    return SYSTEM_AGENT_NODES + INTERACTION_NODES + CONTROL_NODES


def get_node_types_by_category(category: NodeCategory) -> List[NodeTypeInfo]:
    """按类别获取节点类型"""
    return [n for n in get_all_node_types() if n.category == category]


def get_node_type_info(type_or_agent_type: str) -> Optional[NodeTypeInfo]:
    """
    根据类型标识获取节点类型信息

    Args:
        type_or_agent_type: 可以是节点类型(type)或Agent类型(agent_type)

    Returns:
        NodeTypeInfo 或 None
    """
    for node in get_all_node_types():
        if node.type == type_or_agent_type:
            return node
        if node.agent_type == type_or_agent_type:
            return node
    return None
