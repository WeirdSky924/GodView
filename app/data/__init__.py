"""
GodView 数据模块
包含系统内置的 Prompt 模板、Agent 模板、写作规则等
"""

from app.data.system_prompts import SYSTEM_PROMPTS
from app.data.system_agent_templates import SYSTEM_AGENT_TEMPLATES
from app.data.web_novel_writing_rules import (
    WEB_NOVEL_WRITING_RULES,
    WEB_NOVEL_RULE_SETS,
)
from app.data.fanqie_writing_rules import (
    FANQIE_WRITING_RULES,
    FANQIE_RULE_SETS,
)

__all__ = [
    "SYSTEM_PROMPTS",
    "SYSTEM_AGENT_TEMPLATES",
    "WEB_NOVEL_WRITING_RULES",
    "WEB_NOVEL_RULE_SETS",
    "FANQIE_WRITING_RULES",
    "FANQIE_RULE_SETS",
]
