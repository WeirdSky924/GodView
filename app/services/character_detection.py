"""
角色检测与晋升服务 - 在剧情生成过程中检测新角色并自动晋升

职责：
1. 从生成的内容中检测新出现的角色（使用 LLM 智能识别）
2. 评估角色的重要性
3. 决定是否晋升为正式角色
4. 为晋升的角色创建 CharacterAgent 并初始化记忆
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from app.models.character import Character
else:
    # Import at runtime for the enum comparison
    from app.models.character import CharacterImportanceTier

logger = logging.getLogger(__name__)


def _normalize_text_content(value: Any) -> str:
    """将 LLM 内容块或结构化内容归一化为文本。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            text = _normalize_text_content(item)
            if text:
                parts.append(text)
        return "\n".join(parts)
    if isinstance(value, dict):
        for key in ("text", "content", "summary", "full_content"):
            text = value.get(key)
            if isinstance(text, (str, list, dict)):
                normalized = _normalize_text_content(text)
                if normalized:
                    return normalized
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    return str(value)


def _extract_json_object(text: str) -> Dict[str, Any]:
    """从 LLM 响应中提取首个 JSON object，允许后面跟随说明文本。"""
    decoder = json.JSONDecoder()
    candidates: List[str] = []

    for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE):
        candidates.append(match.group(1).strip())
    candidates.append(text.strip())

    for candidate in candidates:
        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                result, _ = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(result, dict):
                return result

    raise ValueError("未能从 LLM 响应中解析 JSON 对象")


@dataclass
class DetectedCharacter:
    """检测到的角色信息"""
    name: str
    description: str = ""
    first_appearance: str = ""  # 首次出现的上下文
    mention_count: int = 1
    dialogue_count: int = 0
    importance_hint: str = "unknown"  # 从上下文推断的重要性
    relationships: List[str] = None
    traits: List[str] = None

    def __post_init__(self):
        if self.relationships is None:
            self.relationships = []
        if self.traits is None:
            self.traits = []


class CharacterDetectionService:
    """角色检测服务 - 从文本中检测和识别角色"""

    # 角色重要性关键词
    IMPORTANCE_KEYWORDS = {
        "high": [
            "主角", "女主角", "男主角", "主要角色", "核心人物",
            "英雄", "反派", "大反派", "终极BOSS",
        ],
        "medium": [
            "重要配角", "关键人物", "重要角色", "配角",
            "导师", "对手", "朋友", "敌人", "师兄", "师妹",
        ],
        "low": [
            "路人", "NPC", "龙套", "背景人物", "普通村民",
            "侍从", "仆人", "守卫", "士兵",
        ],
    }

    # 称谓词（用于识别人名后的称谓）
    TITLE_PATTERNS = [
        r"(.{2,4})(公子|小姐|姑娘|大人|老爷|夫人|少爷|师父|师尊|师叔|师兄|师妹|掌门|长老)",
        r"(.{2,4})(王爷|公主|皇子|皇后|皇帝|将军|统领|队长)",
        r"(.{2,4})(说|道|喊|叫|笑|叹|问|答)",
    ]

    def __init__(self):
        # 已知角色缓存
        self._known_characters: Dict[str, Set[str]] = {}  # project_id -> set of names

    def set_known_characters(self, project_id: str, character_names: List[str]):
        """设置已知角色列表"""
        self._known_characters[project_id] = set(character_names)

    async def detect_new_characters(
        self,
        content: str,
        project_id: str,
        existing_characters: List[Dict[str, Any]] = None,
        context: Dict[str, Any] = None,
    ) -> List[DetectedCharacter]:
        """
        从内容中检测新出现的角色

        Args:
            content: 文本内容（章节内容、对话等）
            project_id: 项目 ID
            existing_characters: 已有的角色列表
            context: 上下文信息（场景、剧情焦点等）

        Returns:
            List[DetectedCharacter]: 检测到的新角色列表
        """
        content = _normalize_text_content(content)

        existing_names = set()
        if existing_characters:
            existing_names = {c.get("name") for c in existing_characters if c.get("name")}

        # 合并缓存
        if project_id in self._known_characters:
            existing_names.update(self._known_characters[project_id])

        detected = {}

        # 方法1：从对话标记中检测（【角色名】格式）
        dialogue_pattern = r'【([^】]{2,8})】'
        for match in re.finditer(dialogue_pattern, content):
            name = match.group(1)
            if name not in existing_names and not self._is_common_word(name):
                if name not in detected:
                    detected[name] = DetectedCharacter(
                        name=name,
                        first_appearance=content[max(0, match.start()-20):match.end()+50],
                    )
                detected[name].dialogue_count += 1

        # 方法2：从说话模式中检测（"XXX说"格式）
        speech_patterns = [
            r'([^\s，。！？]{2,4})(说[道完]|问道|笑道|叹道|喊道|答道|冷声道|沉声道)',
            r'"([^"]{2,8})"[说道喊笑叹]',
        ]
        for pattern in speech_patterns:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                if name not in existing_names and not self._is_common_word(name):
                    if name not in detected:
                        detected[name] = DetectedCharacter(
                            name=name,
                            first_appearance=content[max(0, match.start()-20):match.end()+50],
                        )
                    detected[name].mention_count += 1

        # 方法3：从称谓模式中检测
        for pattern in self.TITLE_PATTERNS:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                if name not in existing_names and not self._is_common_word(name):
                    if name not in detected:
                        detected[name] = DetectedCharacter(
                            name=name,
                            first_appearance=content[max(0, match.start()-20):match.end()+50],
                        )
                    detected[name].mention_count += 1

        # 方法4：推断重要性
        for name, char in detected.items():
            char.importance_hint = self._infer_importance(content, name)

        # 过滤掉低出现次数且低重要性的
        significant_characters = [
            char for char in detected.values()
            if char.mention_count >= 2 or char.dialogue_count >= 1 or char.importance_hint in ["high", "medium"]
        ]

        return significant_characters

    def _is_common_word(self, name: str) -> bool:
        """检查是否是常见的非人名词汇"""
        common_words = {
            "此时", "忽然", "突然", "这时", "然后", "虽然", "但是",
            "一个", "这个", "那个", "什么", "怎么", "如何", "为何",
            "众人", "所有人", "大家", "对方", "此人", "那人",
            "天地", "世界", "一切", "万物", "所有",
        }
        return name in common_words

    def _infer_importance(self, content: str, name: str) -> str:
        """从上下文推断角色重要性"""
        # 检查是否有高重要性关键词
        for keyword in self.IMPORTANCE_KEYWORDS["high"]:
            if keyword in content and name in content:
                # 检查关键词是否与角色名相关
                context = content[max(0, content.find(name)-50):content.find(name)+50]
                if keyword in context:
                    return "high"

        # 检查中等重要性
        for keyword in self.IMPORTANCE_KEYWORDS["medium"]:
            if keyword in content:
                context = content[max(0, content.find(name)-50):content.find(name)+50]
                if keyword in context:
                    return "medium"

        # 检查低重要性
        for keyword in self.IMPORTANCE_KEYWORDS["low"]:
            context = content[max(0, content.find(name)-30):content.find(name)+30]
            if keyword in context:
                return "low"

        # 根据出现次数判断
        mention_count = len(re.findall(re.escape(name), content))
        if mention_count >= 5:
            return "medium"
        elif mention_count >= 3:
            return "low"

        return "unknown"


class CharacterPromotionManager:
    """角色晋升管理器 - 管理从检测到晋升的完整流程"""

    # 晋升阈值
    PROMOTION_THRESHOLDS = {
        "importance_high": 1,      # 高重要性角色出现1次即晋升
        "importance_medium": 3,    # 中等重要性角色出现3次晋升
        "importance_low": 5,       # 低重要性角色出现5次晋升
        "dialogue_count": 2,       # 有2次以上对话即晋升
        "total_mentions": 5,       # 总提及次数超过5次晋升
    }

    def __init__(self):
        self._detection_service = CharacterDetectionService()
        # 候选角色追踪：{project_id: {name: detection_info}}
        self._candidates: Dict[str, Dict[str, Dict[str, Any]]] = {}

    async def process_content(
        self,
        content: str,
        project_id: str,
        existing_characters: List[Dict[str, Any]] = None,
        context: Dict[str, Any] = None,
        db=None,
        llm_model=None,
    ) -> Dict[str, Any]:
        """
        处理内容，检测并可能晋升角色（使用 LLM 智能检测）

        Args:
            content: 文本内容
            project_id: 项目 ID
            existing_characters: 已有角色
            context: 上下文
            db: 数据库连接
            llm_model: LLM 模型实例（用于智能检测）

        Returns:
            Dict: 处理结果，包含检测到的角色和晋升的角色
        """
        # 1. 使用 LLM 智能检测新角色
        detected = await self._detect_characters_with_llm(
            content=content,
            project_id=project_id,
            existing_characters=existing_characters or [],
            llm_model=llm_model,
        )

        if not detected:
            return {"detected": [], "promoted": [], "candidates": []}

        # 2. 更新候选角色追踪
        if project_id not in self._candidates:
            self._candidates[project_id] = {}

        for char in detected:
            name = char.get("name", "")
            if not name:
                continue

            if name not in self._candidates[project_id]:
                self._candidates[project_id][name] = {
                    "name": name,
                    "description": char.get("description", ""),
                    "first_appearance": char.get("first_appearance_context", ""),
                    "mention_count": 0,
                    "dialogue_count": char.get("dialogue_count", 0),
                    "importance_hint": self._tier_to_importance(char.get("importance_tier", 4)),
                    "first_detected_at": datetime.now().isoformat(),
                }

            self._candidates[project_id][name]["mention_count"] += 1
            self._candidates[project_id][name]["dialogue_count"] += char.get("dialogue_count", 0)

        # 3. 检查是否需要晋升
        promoted = []
        candidates_to_promote = []

        for name, info in self._candidates[project_id].items():
            if self._should_promote(info):
                candidates_to_promote.append(info)

        # 4. 执行晋升
        for candidate in candidates_to_promote:
            try:
                result = await self._promote_character(
                    project_id=project_id,
                    candidate_info=candidate,
                    context=context,
                    db=db,
                )
                if result.get("success"):
                    promoted.append(result)
                    # 从候选列表中移除
                    promoted_name = candidate.get("name")
                    if promoted_name:
                        self._candidates[project_id].pop(promoted_name, None)
            except Exception as e:
                logger.error(f"角色晋升失败: {e}")

        return {
            "detected": detected,
            "promoted": promoted,
            "candidates": list(self._candidates.get(project_id, {}).values()),
        }

    async def _detect_characters_with_llm(
        self,
        content: str,
        project_id: str,
        existing_characters: List[Dict[str, Any]],
        llm_model=None,
    ) -> List[Dict[str, Any]]:
        """
        使用 LLM 智能检测角色

        Args:
            content: 章节内容
            project_id: 项目 ID
            existing_characters: 已有角色列表
            llm_model: LLM 模型实例

        Returns:
            List[Dict]: 检测到的新角色列表
        """
        if not llm_model:
            logger.warning("没有 LLM 模型，无法进行智能角色检测")
            return []

        try:
            from langchain_core.messages import HumanMessage
            import json

            # 构建已有角色名列表
            existing_names = [c.get("name", "") for c in existing_characters if c.get("name")]
            existing_names_str = ", ".join(existing_names) if existing_names else "无"

            # 截取内容（避免过长）
            content = _normalize_text_content(content)
            content_to_analyze = content[:3000] if len(content) > 3000 else content

            prompt = f"""请从以下章节内容中检测和提取所有出现的角色。

【章节内容】
{content_to_analyze}

【已有角色列表】
{existing_names_str}

【检测任务】
1. 识别章节中所有出现的角色
2. 对于新角色（不在已有角色列表中的），评估其重要性
3. 提取角色的关键信息

【角色识别标准】
- 有名字的个体（如：张三、李四、王大锤）
- 有独特称谓的个体（如：白衣少年、黑袍长老）
- 有台词或行动描述的人物
- 注意：不要把普通名词、地名、组织名、时间词、形容词等误认为角色名

【重要性判断标准】
- Tier 1-2：主角、核心配角、有多次对话或关键行动
- Tier 3：有名字的配角、有一定剧情作用
- Tier 4-5：路人、背景人物、仅提及一次

请输出 JSON 格式：
{{
    "existing_characters_found": ["章节中出现的已有角色名"],
    "new_characters": [
        {{
            "name": "角色名称",
            "importance_tier": 1-5,
            "first_appearance_context": "首次出现的上下文（50字内）",
            "description": "基于内容推断的角色描述",
            "dialogue_count": 对话次数,
            "importance_reason": "判断重要性的理由"
        }}
    ],
    "total_characters_in_chapter": 章节中出现的角色总数
}}

只输出 JSON，不要有其他内容。"""

            response = await llm_model.ainvoke([HumanMessage(content=prompt)])
            response_text = _normalize_text_content(response.content)

            result = _extract_json_object(response_text)

            # 提取新角色
            new_characters = result.get("new_characters", [])

            # 过滤掉已有的角色名（双重检查）
            new_characters = [
                c for c in new_characters
                if c.get("name") and c.get("name") not in existing_names
            ]

            logger.info(f"LLM 检测到 {len(new_characters)} 个新角色: {[c.get('name') for c in new_characters]}")

            return new_characters

        except Exception as e:
            logger.error(f"LLM 角色检测失败: {e}")
            return []

    def _tier_to_importance(self, tier: int) -> str:
        """将层级转换为重要性提示"""
        if tier <= 2:
            return "high"
        elif tier == 3:
            return "medium"
        else:
            return "low"

    def _should_promote(self, candidate_info: Dict[str, Any]) -> bool:
        """判断是否应该晋升"""
        importance = candidate_info.get("importance_hint", "unknown")
        mention_count = candidate_info.get("mention_count", 0)
        dialogue_count = candidate_info.get("dialogue_count", 0)

        # 高重要性角色
        if importance == "high" and mention_count >= self.PROMOTION_THRESHOLDS["importance_high"]:
            return True

        # 中等重要性角色
        if importance == "medium" and mention_count >= self.PROMOTION_THRESHOLDS["importance_medium"]:
            return True

        # 有多次对话
        if dialogue_count >= self.PROMOTION_THRESHOLDS["dialogue_count"]:
            return True

        # 总提及次数很高
        if mention_count >= self.PROMOTION_THRESHOLDS["total_mentions"]:
            return True

        return False

    async def _promote_character(
        self,
        project_id: str,
        candidate_info: Dict[str, Any],
        context: Dict[str, Any] = None,
        db=None,
    ) -> Dict[str, Any]:
        """
        晋升角色为正式角色

        包括：
        1. 创建角色记录
        2. 为重要角色创建 Agent 并初始化记忆
        3. 通知系统
        """
        from app.models.character import Character, CharacterStatus
        from app.api.app import postgres_db

        character_id = f"char_{uuid.uuid4().hex[:12]}"

        # 确定角色重要性层级
        importance_hint = candidate_info.get("importance_hint", "unknown")
        importance_tier = self._map_importance_to_tier(importance_hint)

        # 创建角色
        character = Character(
            id=character_id,
            project_id=project_id,
            name=candidate_info["name"],
            description=candidate_info.get("description", f"在剧情中首次出现: {candidate_info.get('first_appearance', '')[:100]}"),
            role="supporting" if importance_hint in ["medium", "low"] else "major",
            status=CharacterStatus.ACTIVE,
            importance_tier=importance_tier,
            background_story=f"首次出现于: {candidate_info.get('first_appearance', '')[:200]}",
            goals=[],
            inventory=[],
            personality_traits=[],
        )

        # 保存到数据库
        if postgres_db:
            await postgres_db.save_character(character.model_dump(mode="json"))

        logger.info(f"角色晋升成功: {character.name} (ID: {character_id}, 层级: {importance_tier})")

        # 为重要角色创建 Agent 和记忆（Tier 1-3）
        agent_created = False
        high_priority_tiers = [
            CharacterImportanceTier.PROTAGONIST,
            CharacterImportanceTier.CO_PROTAGONIST,
            CharacterImportanceTier.DEUTERAGONIST,
            CharacterImportanceTier.MENTOR,
            CharacterImportanceTier.LOVE_INTEREST,
            CharacterImportanceTier.BEST_FRIEND,
            CharacterImportanceTier.ARCHENEMY,
            CharacterImportanceTier.MAJOR_ALLY,
            CharacterImportanceTier.MAJOR_ANTAGONIST,
            CharacterImportanceTier.RIVAL,
            CharacterImportanceTier.FAMILY_MEMBER,
            CharacterImportanceTier.GUARDIAN,
        ]
        if importance_tier in high_priority_tiers:
            agent_created = await self._create_character_agent_with_memory(
                character=character,
                project_id=project_id,
                context=context,
            )

        return {
            "success": True,
            "character_id": character_id,
            "character": character.model_dump(mode="json"),
            "importance_tier": importance_tier.value if hasattr(importance_tier, 'value') else str(importance_tier),
            "agent_created": agent_created,
            "promotion_reason": f"自动晋升: {importance_hint}重要性, {candidate_info.get('mention_count', 0)}次提及, {candidate_info.get('dialogue_count', 0)}次对话",
        }

    def _map_importance_to_tier(self, importance_hint: str):
        """将重要性提示映射到 CharacterImportanceTier 枚举"""
        from app.models.character import CharacterImportanceTier

        mapping = {
            "high": CharacterImportanceTier.DEUTERAGONIST,      # 核心配角层 (Tier 2)
            "medium": CharacterImportanceTier.MAJOR_ALLY,      # 重要配角层 (Tier 3)
            "low": CharacterImportanceTier.RECURRING,          # 阶段性角色层 (Tier 4)
            "unknown": CharacterImportanceTier.NPC,            # 默认 NPC (Tier 6)
        }
        return mapping.get(importance_hint, CharacterImportanceTier.NPC)

    async def _create_character_agent_with_memory(
        self,
        character: "Character",
        project_id: str,
        context: Dict[str, Any] = None,
    ) -> bool:
        """
        为角色创建 Agent 并初始化记忆系统

        Args:
            character: 角色对象
            project_id: 项目 ID
            context: 上下文信息

        Returns:
            bool: 是否创建成功
        """
        try:
            from app.services.agent_memory_service import get_memory_service

            # 初始化记忆
            memory_service = get_memory_service()
            # 记忆会在第一次执行时自动加载

            logger.info(f"角色 {character.name} 的 Agent 已准备就绪（记忆系统已初始化）")
            return True

        except Exception as e:
            logger.error(f"创建角色 Agent 失败: {e}")
            return False

    def get_candidate_characters(self, project_id: str) -> List[Dict[str, Any]]:
        """获取项目的候选角色列表"""
        return list(self._candidates.get(project_id, {}).values())

    def clear_candidates(self, project_id: str):
        """清除项目的候选角色"""
        self._candidates[project_id] = {}


# 全局实例
_detection_manager: Optional[CharacterPromotionManager] = None


def get_character_detection_manager() -> CharacterPromotionManager:
    """获取角色检测管理器单例"""
    global _detection_manager
    if _detection_manager is None:
        _detection_manager = CharacterPromotionManager()
    return _detection_manager
