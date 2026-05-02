"""
场景协调者 Agent - 统筹多角色演绎场景

职责：
1. 接收场景方向和上一个节点的输出
2. 为每个参与角色分配信息
3. 协调多个角色 Agent 的表演顺序
4. 汇总所有角色的表演内容
5. 输出整合后的场景结果
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.agents.character_agent import CharacterAgent
from app.models.character import Character
from app.models.token_usage import UsageCategory

logger = logging.getLogger(__name__)


# 角色重要性枚举到数字层级的映射
TIER_NUMBER_MAP = {
    # Tier 1: 主角层
    "protagonist": 1,
    "co_protagonist": 1,
    # Tier 2: 核心配角层
    "deuteragonist": 2,
    "mentor": 2,
    "love_interest": 2,
    "best_friend": 2,
    "archenemy": 2,
    # Tier 3: 重要配角层
    "major_ally": 3,
    "major_antagonist": 3,
    "rival": 3,
    "family_member": 3,
    "guardian": 3,
    "arc_antagonist": 3,
    # Tier 4: 阶段性角色层
    "minor_ally": 4,
    "minor_antagonist": 4,
    "recurring": 4,
    "informant": 4,
    # Tier 5: 背景角色层
    "npc": 5,
    "background": 5,
    "cameo": 5,
    "minion": 5,
}

# 数字层级到默认枚举字符串的反向映射
NUMBER_TO_TIER_MAP = {
    1: "protagonist",
    2: "deuteragonist",
    3: "major_ally",
    4: "recurring",
    5: "npc",
}


def _normalize_importance_tier(tier_value: Any) -> str:
    """
    将各种格式的 importance_tier 转换为有效的枚举字符串

    Args:
        tier_value: 可以是数字、字符串枚举、或其他格式

    Returns:
        str: 有效的 CharacterImportanceTier 枚举字符串
    """
    if isinstance(tier_value, str):
        # 已经是字符串，检查是否是有效的枚举值
        tier_lower = tier_value.lower().replace("-", "_")
        if tier_lower in TIER_NUMBER_MAP:
            return tier_lower
        # 尝试部分匹配
        for key in TIER_NUMBER_MAP:
            if key in tier_lower or tier_lower in key:
                return key
        return "npc"  # 默认值

    if isinstance(tier_value, int):
        # 数字转换为默认枚举
        return NUMBER_TO_TIER_MAP.get(tier_value, "npc")

    return "npc"  # 默认值


def _get_importance_tier(data: Dict[str, Any], default: int = 3) -> int:
    """
    安全获取 importance_tier 数字层级

    将枚举字符串（如 "protagonist"）转换为数字层级（如 1）

    Args:
        data: 包含 importance_tier 的字典
        default: 默认值（无法解析时使用）

    Returns:
        int: importance_tier 数字层级 (1-5)
    """
    tier = data.get("importance_tier", default)

    # 如果已经是整数，直接返回
    if isinstance(tier, int):
        return tier

    # 如果是字符串，尝试多种解析方式
    if isinstance(tier, str):
        # 1. 尝试直接解析为整数
        try:
            return int(tier)
        except ValueError:
            pass

        # 2. 从枚举字符串映射获取
        tier_lower = tier.lower().replace("-", "_")
        if tier_lower in TIER_NUMBER_MAP:
            return TIER_NUMBER_MAP[tier_lower]

        # 3. 尝试匹配部分字符串
        for key, value in TIER_NUMBER_MAP.items():
            if key in tier_lower or tier_lower in key:
                return value

    return default


def _character_presence_types(character: Dict[str, Any]) -> set[str]:
    presence_types = character.get("available_presence_types")
    if isinstance(presence_types, str):
        return {item.strip().lower() for item in presence_types.replace("，", ",").split(",") if item.strip()}
    if isinstance(presence_types, list):
        return {str(item).lower() for item in presence_types if str(item).strip()}
    return {"present", "mentioned", "background"}


def _can_character_perform(character: Dict[str, Any]) -> tuple[bool, str]:
    status = str(character.get("status") or character.get("activity_status") or "active").lower()
    if status in {"inactive", "archived", "dead", "retired", "disabled"}:
        return False, f"status={status}"
    presence_types = _character_presence_types(character)
    if presence_types and "present" not in presence_types:
        return False, "available_presence_types excludes present"
    return True, "eligible"


class SceneCoordinatorAgent(BaseAgent):
    """场景协调者 Agent - 统筹多角色演绎"""

    AGENT_TYPE = "scene_coordinator"
    DEFAULT_SCENARIO = "scene_coordination"

    def __init__(
        self,
        model: Optional[BaseLanguageModel] = None,
        project_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        db=None,  # 数据库连接，用于字数统计 skill
    ):
        super().__init__(
            name="SceneCoordinatorAgent",
            model=model,
            system_prompt=None if project_id else self._build_system_prompt(),
            config=config,
            project_id=project_id,
        )

        # 数据库连接
        self._db = db

        # 角色实例池 - 每个角色一个独立的 Agent
        self._character_agents: Dict[str, CharacterAgent] = {}

        # 场景状态
        self._current_scene: Dict[str, Any] = {}
        self._conversation_history: List[Dict[str, Any]] = []

    def _get_default_variables(self) -> Dict[str, Any]:
        return {
            "agent_role": "场景协调者",
            "task_description": "统筹多角色演绎场景，协调信息分配，汇总表演结果",
        }

    def _build_system_prompt(self) -> str:
        return (
            "你是场景协调者，负责统筹多角色演绎场景。"
            "优先使用 Agent Template 绑定的 md prompt / skills / writing-rules；"
            "仅在未能加载配置资产时，将此最小提示作为 deprecated fallback。"
        )

    def _build_supplement_context(
        self,
        *,
        base_context: str,
        current_content: str,
        shortage: int,
        character_name: str,
        plot_intents: Optional[List[str]] = None,
    ) -> str:
        """构建场景补充上下文，稳定规则由 Character Agent 模板提供。"""
        parts = [base_context]
        supplement_lines = [
            f"当前场景素材字数不足，需要补充约 {shortage} 字。",
            "补充内容必须延续已有场景，只作为 Writer 的参考素材，不扩写成完整章节正文。",
            "只能让当前角色基于可见信息行动；不得让仅提及、不可用或禁止正面出场角色发言、行动或进入现场。",
        ]
        if character_name:
            supplement_lines.append(f"当前补充角色：{character_name}")
        if plot_intents:
            supplement_lines.append("剧情意图参考：" + "；".join(str(item) for item in plot_intents if item))
        parts.append("【补充任务边界】\n" + "\n".join(f"- {line}" for line in supplement_lines))
        if current_content:
            parts.append(f"【已有内容摘要】\n{current_content[-500:]}")
        return "\n\n".join(part for part in parts if part)

    def get_or_create_character_agent(
        self,
        character_data: Dict[str, Any],
        model: Optional[BaseLanguageModel] = None,
    ) -> CharacterAgent:
        """
        获取或创建角色的专属 Agent 实例

        重要：每个角色有独立的 Agent 实例，保证信息隔离

        Args:
            character_data: 角色数据
            model: 语言模型（可选）

        Returns:
            CharacterAgent: 该角色的专属 Agent
        """
        char_id = character_data.get("id") or character_data.get("name")

        if char_id not in self._character_agents:
            # 创建 Character 对象
            character = self._dict_to_character(character_data)

            # 创建独立的 Agent 实例
            agent = CharacterAgent(
                character=character,
                model=model or self.model,
                config={"scenario": "roleplay"},
                project_id=self.project_id,
            )

            self._character_agents[char_id] = agent
            logger.info(f"为角色 '{character_data.get('name')}' 创建了独立的 Agent 实例")

        return self._character_agents[char_id]

    def _dict_to_character(self, data: Dict[str, Any]) -> Character:
        """将字典转换为 Character 对象"""
        # 处理 id（可能是 UUID 对象）
        char_id = data.get("id") or str(uuid.uuid4())
        if hasattr(char_id, 'hex'):  # UUID object
            char_id = str(char_id)

        # 处理 personality_traits（可能是 dict 或 None）
        personality_traits = data.get("personality_traits") or data.get("traits", [])
        if isinstance(personality_traits, dict):
            personality_traits = []
        elif not isinstance(personality_traits, list):
            personality_traits = []

        return Character(
            id=char_id,
            name=data.get("name", "未知角色"),
            description=data.get("description") or data.get("background", ""),
            role=data.get("role") or data.get("character_type", "supporting"),
            personality=data.get("personality", ""),
            background_story=data.get("background") or data.get("background_story", ""),
            speech_pattern=data.get("speech_pattern", ""),
            lexicon=data.get("lexicon", []),
            forbidden_words=data.get("forbidden_words", []),
            current_location=data.get("current_location", ""),
            goals=data.get("goals", []),
            inventory=data.get("inventory", []),
            personality_traits=personality_traits,
            importance_tier=_normalize_importance_tier(data.get("importance_tier", 3)),
            is_protagonist=data.get("is_protagonist", False),
            is_antagonist=data.get("is_antagonist", False),
        )

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行场景协调

        Args:
            input_data: 包含以下字段
                - scene_directions: 场景方向（编剧设定）
                - characters: 参与角色列表
                - world_info: 世界观信息
                - previous_output: 上一个节点的输出
                - mode: "interactive" 或 "parallel"
                - iteration_count: 迭代轮数（默认2-3轮）
                - target_word_count: 目标字数（用于动态调整迭代次数）
                - plot_intents: 剧情意图（需要演绎的内容）

        Returns:
            AgentResponse: 协调结果
        """
        try:
            await self._ensure_system_prompt_loaded()

            scene_directions = input_data.get("scene_directions", {})
            if not isinstance(scene_directions, dict):
                scene_directions = {}
            scene_directions.setdefault("scenario", self.scenario)
            scene_directions.setdefault("config_prompt_source", "agent_template_runtime" if self.system_prompt else "deprecated_fallback")
            characters_data = input_data.get("characters", [])
            performers = scene_directions.get("performers") or characters_data
            mentioned_characters = scene_directions.get("mentioned_characters") or []
            background_characters = scene_directions.get("background_characters") or []
            unavailable_characters = scene_directions.get("unavailable_characters") or []
            if performers or background_characters:
                characters_data = [*performers, *background_characters]
            filtered_characters = []
            filtered_out = []
            for character in characters_data:
                if not isinstance(character, dict):
                    continue
                can_perform, reason = _can_character_perform(character)
                if can_perform:
                    filtered_characters.append(character)
                else:
                    filtered_out.append({**character, "unavailable_reason": reason})
            if filtered_out:
                unavailable_characters = [*unavailable_characters, *filtered_out]
                scene_directions["unavailable_characters"] = unavailable_characters
                scene_directions.setdefault("participation_warnings", []).extend(
                    f"场景协调器移除不可正面出场角色 {item.get('name', '未知角色')}：{item.get('unavailable_reason')}"
                    for item in filtered_out
                )
            characters_data = filtered_characters
            world_info = input_data.get("world_info", {})
            previous_output = input_data.get("previous_output", {})
            mode = input_data.get("mode", "interactive")
            iteration_count = input_data.get("iteration_count", 2)  # 默认2轮
            target_word_count = input_data.get("target_word_count", 1500)
            reference_mode = bool(input_data.get("reference_mode", False))
            plot_intents = input_data.get("plot_intents", [])

            self._current_scene = scene_directions
            self._conversation_history = []

            # 根据目标字数动态调整迭代轮数；参考素材模式不按章节正文规模扩写
            if not reference_mode:
                if target_word_count >= 3000:
                    iteration_count = max(iteration_count, 4)
                elif target_word_count >= 2000:
                    iteration_count = max(iteration_count, 3)

            if mentioned_characters or unavailable_characters:
                scene_directions["mentioned_character_rule"] = (
                    "mentioned_characters/unavailable_characters 只能作为影响、传闻、姓名、势力或回忆被提及，"
                    "不得直接发言、行动或作为当前场景活人参与者。"
                )

            logger.info(f"场景演绎配置: {iteration_count} 轮迭代, 目标 {target_word_count} 字, {len(characters_data)} 个角色")

            # 1. 分析场景，准备信息分发
            distribution_plan = await self._prepare_distribution(
                scene_directions, characters_data, world_info, previous_output
            )

            # 2. 执行角色表演（支持多轮迭代）
            performance_results = []

            if mode == "interactive":
                # 同场景互动模式（支持多轮）
                performance_results = await self._run_interactive_scene_with_iterations(
                    characters_data, distribution_plan, scene_directions, world_info,
                    iteration_count=iteration_count,
                    plot_intents=plot_intents,
                    target_word_count=target_word_count,
                )
            else:
                # 并行独立模式
                performance_results = await self._run_parallel_scene(
                    characters_data, distribution_plan, scene_directions, world_info
                )

            # 3. 检查字数，必要时补充
            full_content = "\n".join([
                p.get("content", "") for p in performance_results if p.get("content")
            ])
            current_word_count = await self._count_words_with_skill(full_content)

            if not reference_mode and current_word_count < target_word_count * 0.7:
                logger.info(f"内容字数不足 ({current_word_count}/{target_word_count})，进行补充迭代...")
                supplement_results = await self._supplement_scene_content(
                    characters_data, distribution_plan, scene_directions, world_info,
                    current_content=full_content,
                    shortage=target_word_count - current_word_count,
                    plot_intents=plot_intents,
                )
                performance_results.extend(supplement_results)
            elif reference_mode and current_word_count < target_word_count * 0.7:
                logger.info(
                    f"参考素材模式：场景演绎内容较短 ({current_word_count}/{target_word_count})，"
                    "不进行章节正文式补写"
                )

            # 4. 整合表演内容
            final_result = await self._integrate_performances(
                performance_results, scene_directions
            )

            # 添加统计信息（使用 skill 统计字数）
            final_result["iteration_count"] = iteration_count
            final_result["target_word_count"] = target_word_count
            final_result["reference_mode"] = reference_mode
            final_result["material_role"] = input_data.get("material_role", "reference_only" if reference_mode else "performance")
            final_result["usage_instruction"] = input_data.get("usage_instruction", "")
            final_result["actual_word_count"] = await self._count_words_with_skill(final_result.get("full_content", ""))
            final_result["performers"] = performers
            final_result["mentioned_characters"] = mentioned_characters
            final_result["background_characters"] = background_characters
            final_result["unavailable_characters"] = scene_directions.get("unavailable_characters", [])
            final_result["participation_trace"] = scene_directions.get("participation_trace", [])
            final_result["participation_warnings"] = scene_directions.get("participation_warnings", [])

            return AgentResponse(
                success=True,
                data=final_result,
                metadata={
                    "characters_participated": [c.get("name") for c in characters_data],
                    "total_messages": len(performance_results),
                    "scene_type": scene_directions.get("scene_type", "interactive"),
                    "iteration_count": iteration_count,
                    "word_count": final_result["actual_word_count"],
                },
            )

        except Exception as e:
            logger.error(f"场景协调执行失败: {e}")
            return AgentResponse(success=False, error=str(e))

    def _count_words(self, text: str) -> int:
        """统计字数（内置方法，用于简单场景）"""
        if not text:
            return 0
        import re
        chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
        english = len(re.findall(r'\b[a-zA-Z]+\b', text))
        return chinese + english

    async def _count_words_with_skill(self, text: str) -> int:
        """
        使用 Skill 统计字数（异步版本，优先使用）

        优先使用 skill_word_count skill 进行精确统计，
        如果失败则回退到内置方法。
        """
        if not text:
            return 0

        # 尝试使用 Skill 进行精确统计
        try:
            result = await self.execute_skill("skill_word_count", {"text": text})
            if result.get("success") and result.get("output"):
                import json
                data = result["output"] if isinstance(result["output"], dict) else json.loads(result["output"])
                total = data.get("total_count", 0)
                if total > 0:
                    logger.debug(f"Skill 字数统计: {total} 字")
                    return total
        except Exception as e:
            logger.debug(f"Skill 字数统计失败，使用内置方法: {e}")

        # 回退到内置统计
        return self._count_words(text)

    async def _prepare_distribution(
        self,
        scene_directions: Dict[str, Any],
        characters_data: List[Dict[str, Any]],
        world_info: Dict[str, Any],
        previous_output: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """
        准备信息分发计划

        为每个角色准备其应该知道的信息
        """
        distribution_plan = {}

        for char_data in characters_data:
            char_name = char_data.get("name", "未知角色")
            importance_tier = _get_importance_tier(char_data, 3)
            char_role = scene_directions.get("character_roles", {}).get(char_name, {})

            # 基础场景信息（所有在场角色都知道）
            info_package = {
                "scene_info": {
                    "location": scene_directions.get("main_scene", ""),
                    "atmosphere": scene_directions.get("atmosphere", "正剧"),
                    "time": scene_directions.get("time_of_day", ""),
                },
                "character_specific": char_role,
            }

            # 根据重要性分发剧情信息
            if importance_tier <= 2:
                # 重要角色知道更多
                info_package["plot_context"] = {
                    "plot_focus": scene_directions.get("plot_focus", ""),
                    "conflict_points": scene_directions.get("conflict_points", []),
                    "key_events": previous_output.get("key_events", [])[:3],
                }
            else:
                # 普通角色只知道表面
                info_package["plot_context"] = {
                    "visible_events": scene_directions.get("visible_events", []),
                }

            # 添加相关的上节点信息
            if previous_output:
                info_package["previous_context"] = self._extract_relevant_context(
                    char_name, previous_output
                )

            distribution_plan[char_name] = info_package

        return distribution_plan

    def _extract_relevant_context(
        self,
        char_name: str,
        previous_output: Dict[str, Any],
    ) -> Dict[str, Any]:
        """提取与该角色相关的上下文"""
        relevant = {
            "related_dialogues": [],
            "recent_events": [],
        }

        # 提取相关对话
        for dialogue in previous_output.get("dialogues", []):
            content = dialogue.get("content", "")
            if char_name in content or dialogue.get("is_public", True):
                relevant["related_dialogues"].append(dialogue)

        relevant["related_dialogues"] = relevant["related_dialogues"][-3:]

        # 提取最近事件
        relevant["recent_events"] = previous_output.get("events", [])[-2:]

        return relevant

    def _build_performance_message(
        self,
        *,
        char_name: str,
        result_data: Dict[str, Any],
        char_data: Dict[str, Any],
        message_type: str = "character_performance",
        round_value: Any = None,
    ) -> Dict[str, Any]:
        """从 CharacterAgent 输出构建公开/私有分层表演消息。"""
        dialogue = result_data.get("dialogue", "")
        action = result_data.get("action", "")
        content_parts = []
        if action:
            content_parts.append(f"（{action}）")
        if dialogue:
            content_parts.append(dialogue)
        public_content = result_data.get("public_content") or " ".join(content_parts)
        private_thought = result_data.get("private_thought") or result_data.get("inner_thought", "")

        message = {
            "agent": char_name,
            "type": message_type,
            "content": public_content,
            "public_content": public_content,
            "dialogue": dialogue,
            "action": action,
            "private_thought": private_thought,
            "inner_thought": private_thought,
            "emotion": result_data.get("emotion", ""),
            "intent": result_data.get("intent", ""),
            "perceived_facts": result_data.get("perceived_facts", []),
            "misinterpretations": result_data.get("misinterpretations", []),
            "withheld_information": result_data.get("withheld_information", []),
            "relationship_delta": result_data.get("relationship_delta", []),
            "state_delta": result_data.get("state_delta", []),
            "continuity_notes": result_data.get("continuity_notes", []),
            "warnings": result_data.get("warnings", []),
            "importance_tier": _get_importance_tier(char_data, 3),
        }
        if round_value is not None:
            message["round"] = round_value
        return message

    def _public_history_messages(self, limit: int) -> List[Dict[str, Any]]:
        """只把公开内容传给后续角色，避免泄露私有思考和隐藏意图。"""
        public_messages = []
        for msg in self._conversation_history[-limit:]:
            public_messages.append({
                "agent": msg.get("agent"),
                "speaker": msg.get("agent"),
                "content": msg.get("public_content") or msg.get("content", ""),
                "action": msg.get("action", ""),
                "dialogue": msg.get("dialogue", ""),
                "emotion": msg.get("emotion", ""),
                "round": msg.get("round"),
            })
        return public_messages

    async def _run_interactive_scene(
        self,
        characters_data: List[Dict[str, Any]],
        distribution_plan: Dict[str, Dict[str, Any]],
        scene_directions: Dict[str, Any],
        world_info: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        执行同场景互动模式（单轮，向后兼容）

        角色按顺序发言，可以互相响应
        """
        results = []

        # 分离主要角色和背景角色
        main_chars = [c for c in characters_data if _get_importance_tier(c, 3) <= 3]
        background_chars = [c for c in characters_data if _get_importance_tier(c, 3) > 3]

        # 主要角色互动
        for i, char_data in enumerate(main_chars):
            char_name = char_data.get("name")

            # 获取该角色的独立 Agent
            char_agent = self.get_or_create_character_agent(char_data)

            # 准备输入
            char_input = {
                "context": self._build_character_context(
                    char_data, distribution_plan.get(char_name, {}),
                    scene_directions, world_info
                ),
                "present_characters": [c.get("name") for c in main_chars],
                "recent_events": distribution_plan.get(char_name, {}).get("previous_context", {}).get("recent_events", []),
                "dialogue_history": self._public_history_messages(5),
            }

            # 执行角色表演
            result = await char_agent.execute(char_input)

            if result.success:
                message = self._build_performance_message(
                    char_name=char_name,
                    result_data=result.data,
                    char_data=char_data,
                    message_type="character_performance",
                )
                results.append(message)
                self._conversation_history.append(message)

                # 广播（如果设置了流式回调）
                if self._stream_callback:
                    await self._stream_callback(f"[{char_name}] {message.get('public_content', '')}")

        # 插入背景角色行为
        for bg_char in background_chars:
            bg_behavior = self._generate_background_action(bg_char, scene_directions)
            results.append(bg_behavior)

        return results

    async def _run_interactive_scene_with_iterations(
        self,
        characters_data: List[Dict[str, Any]],
        distribution_plan: Dict[str, Dict[str, Any]],
        scene_directions: Dict[str, Any],
        world_info: Dict[str, Any],
        iteration_count: int = 2,
        plot_intents: List[str] = None,
        target_word_count: int = 1500,
    ) -> List[Dict[str, Any]]:
        """
        执行多轮迭代的同场景互动模式

        角色按顺序发言，可以互相响应，支持多轮对话

        Args:
            characters_data: 参与角色列表
            distribution_plan: 信息分发计划
            scene_directions: 场景方向
            world_info: 世界观信息
            iteration_count: 迭代轮数
            plot_intents: 需要演绎的剧情意图
            target_word_count: 目标字数
        """
        results = []
        plot_intents = plot_intents or []

        # 分离主要角色和背景角色
        main_chars = [c for c in characters_data if _get_importance_tier(c, 3) <= 3]
        background_chars = [c for c in characters_data if _get_importance_tier(c, 3) > 3]

        # 按重要性排序主要角色
        main_chars.sort(key=lambda c: _get_importance_tier(c, 3))

        logger.info(f"开始多轮迭代场景演绎: {iteration_count} 轮, {len(main_chars)} 个主要角色")

        # ========== 多轮迭代 ==========
        for round_num in range(iteration_count):
            logger.info(f"=== 第 {round_num + 1}/{iteration_count} 轮迭代 ===")

            # 确定本轮的剧情焦点
            round_focus = None
            if plot_intents and round_num < len(plot_intents):
                round_focus = plot_intents[round_num]
            elif plot_intents:
                round_focus = plot_intents[-1]  # 重复最后一个意图

            # 每个主要角色发言
            for char_data in main_chars:
                char_name = char_data.get("name")

                # 获取该角色的独立 Agent
                char_agent = self.get_or_create_character_agent(char_data)

                # 构建上下文（包含之前的对话历史）
                char_input = {
                    "context": self._build_character_context_with_history(
                        char_data, distribution_plan.get(char_name, {}),
                        scene_directions, world_info, round_num, iteration_count
                    ),
                    "present_characters": [c.get("name") for c in main_chars],
                    "recent_events": distribution_plan.get(char_name, {}).get("previous_context", {}).get("recent_events", []),
                    "dialogue_history": self._public_history_messages(10),  # 最近10条公开对话
                    "round_number": round_num + 1,
                    "total_rounds": iteration_count,
                    "round_focus": round_focus,
                    "target_word_count": target_word_count // len(main_chars) // iteration_count,
                }

                # 执行角色表演
                result = await char_agent.execute(char_input)

                if result.success:
                    message = self._build_performance_message(
                        char_name=char_name,
                        result_data=result.data,
                        char_data=char_data,
                        message_type="character_performance",
                        round_value=round_num + 1,
                    )
                    results.append(message)
                    self._conversation_history.append(message)

                    logger.debug(f"  [{char_name}] 第{round_num + 1}轮: {message.get('public_content', '')[:50]}...")

            # 每轮结束后插入背景角色行为
            if background_chars and round_num < iteration_count - 1:
                for bg_char in background_chars[:2]:  # 每轮最多2个背景角色
                    bg_behavior = self._generate_background_action(bg_char, scene_directions)
                    results.append(bg_behavior)

        # 最终背景角色行为
        for bg_char in background_chars:
            bg_behavior = self._generate_background_action(bg_char, scene_directions)
            results.append(bg_behavior)

        logger.info(f"多轮迭代完成，共 {len(results)} 条表演记录")
        return results

    def _build_character_context_with_history(
        self,
        char_data: Dict[str, Any],
        info_package: Dict[str, Any],
        scene_directions: Dict[str, Any],
        world_info: Dict[str, Any],
        round_num: int,
        total_rounds: int,
    ) -> str:
        """构建包含历史对话的角色上下文"""
        parts = []

        # 基础场景信息
        scene_info = info_package.get("scene_info", {})
        if scene_info:
            parts.append(f"【当前场景】\n地点：{scene_info.get('location', '未知')}\n氛围：{scene_info.get('atmosphere', '正剧')}")

        # 角色出场边界
        constraint_lines = []
        present_names = [str(c.get("name")) for c in scene_directions.get("performers", []) if isinstance(c, dict) and c.get("name")]
        present_names.extend(str(c.get("name")) for c in scene_directions.get("background_characters", []) if isinstance(c, dict) and c.get("name"))
        mentioned_names = [str(c.get("name")) for c in scene_directions.get("mentioned_characters", []) if isinstance(c, dict) and c.get("name")]
        unavailable_names = [str(c.get("name")) for c in scene_directions.get("unavailable_characters", []) if isinstance(c, dict) and c.get("name")]
        if present_names:
            constraint_lines.append(f"可在当前正面场景互动/发言的角色：{', '.join(dict.fromkeys(present_names))}")
        if mentioned_names:
            constraint_lines.append(f"只能提及、不能出场/发言/行动的角色：{', '.join(dict.fromkeys(mentioned_names))}")
        if unavailable_names:
            constraint_lines.append(f"禁止作为当前场景活人参与者的角色：{', '.join(dict.fromkeys(unavailable_names))}")
        if scene_directions.get("mentioned_character_rule"):
            constraint_lines.append(str(scene_directions.get("mentioned_character_rule")))
        if constraint_lines:
            parts.append("【角色出场硬约束】\n" + "\n".join(f"- {line}" for line in constraint_lines) + "\n- 不得让禁止/仅提及角色直接说话、行动、进入现场或推动当前场景。")

        # 迭代轮次信息
        parts.append(f"【当前进度】这是第 {round_num}/{total_rounds} 轮对话")

        # 角色定位
        char_specific = info_package.get("character_specific", {})
        if char_specific:
            parts.append(f"【你的角色定位】\n{char_specific.get('role_in_scene', '参与者')}\n情绪：{char_specific.get('emotional_state', '平静')}")

        # 剧情上下文
        plot_context = info_package.get("plot_context", {})
        if plot_context.get("plot_focus"):
            parts.append(f"【剧情焦点】\n{plot_context.get('plot_focus')}")
        if plot_context.get("visible_events"):
            parts.append(f"【你能看到的事】\n{chr(10).join(plot_context.get('visible_events', []))}")

        # 之前的公开对话历史（如果有）
        public_history = self._public_history_messages(8)
        if public_history:
            history_lines = []
            for msg in public_history:
                agent = msg.get("agent", "某人")
                content = msg.get("content", "")
                if content:
                    history_lines.append(f"【{agent}】{content[:100]}...")
            if history_lines:
                parts.append(f"【之前的对话】\n{chr(10).join(history_lines)}")

        # 根据轮次给出提示
        if round_num == 1:
            parts.append("【提示】这是开场，请根据场景和你的角色设定，自然地开始表演")
        elif round_num == total_rounds:
            parts.append("【提示】这是最后一轮，请为这场戏做一个自然的收尾或铺垫后续")
        else:
            parts.append("【提示】请回应之前的内容，推动剧情发展")

        return "\n\n".join(parts)

    async def _supplement_scene_content(
        self,
        characters_data: List[Dict[str, Any]],
        distribution_plan: Dict[str, Dict[str, Any]],
        scene_directions: Dict[str, Any],
        world_info: Dict[str, Any],
        current_content: str,
        shortage: int,
        plot_intents: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        补充场景内容

        当字数不足时，让角色继续表演以补充内容
        """
        results = []

        # 选择主要角色进行补充
        main_chars = [c for c in characters_data if _get_importance_tier(c, 3) <= 2]
        if not main_chars:
            main_chars = [c for c in characters_data if _get_importance_tier(c, 3) <= 3]

        if not main_chars:
            return results

        logger.info(f"补充场景内容，需要增加约 {shortage} 字")

        for char_data in main_chars[:2]:  # 最多2个角色补充
            char_name = char_data.get("name")
            char_agent = self.get_or_create_character_agent(char_data)

            char_input = {
                "context": self._build_supplement_context(
                    base_context=self._build_character_context_with_history(
                        char_data, distribution_plan.get(char_name, {}),
                        scene_directions, world_info, 1, 1
                    ),
                    current_content=current_content,
                    shortage=shortage,
                    character_name=char_data.get('name', '未知'),
                    plot_intents=plot_intents,
                ),
                "present_characters": [c.get("name") for c in main_chars],
                "dialogue_history": self._public_history_messages(5),
                "is_supplement": True,
                "target_word_count": shortage // 2,
            }

            result = await char_agent.execute(char_input)

            if result.success:
                message = self._build_performance_message(
                    char_name=char_name,
                    result_data=result.data,
                    char_data=char_data,
                    message_type="supplement_performance",
                    round_value="supplement",
                )
                results.append(message)
                self._conversation_history.append(message)

        return results

    async def _run_parallel_scene(
        self,
        characters_data: List[Dict[str, Any]],
        distribution_plan: Dict[str, Dict[str, Any]],
        scene_directions: Dict[str, Any],
        world_info: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        执行并行独立模式

        每个角色独立表演自己的场景
        """
        import asyncio

        tasks = []

        for char_data in characters_data:
            char_name = char_data.get("name")
            char_agent = self.get_or_create_character_agent(char_data)

            char_input = {
                "context": self._build_character_context(
                    char_data, distribution_plan.get(char_name, {}),
                    scene_directions, world_info
                ),
                "present_characters": [],
                "recent_events": [],
                "dialogue_history": [],
            }

            tasks.append(char_agent.execute(char_input))

        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        messages = []
        for i, result in enumerate(results):
            char_data = characters_data[i]
            char_name = char_data.get("name")
            if isinstance(result, AgentResponse) and result.success:
                messages.append(self._build_performance_message(
                    char_name=char_name,
                    result_data=result.data,
                    char_data=char_data,
                    message_type="character_performance",
                ))

        return messages

    def _build_character_context(
        self,
        char_data: Dict[str, Any],
        info_package: Dict[str, Any],
        scene_directions: Dict[str, Any],
        world_info: Dict[str, Any],
    ) -> str:
        """构建角色上下文"""
        parts = []

        # 场景信息
        scene_info = info_package.get("scene_info", {})
        if scene_info:
            parts.append(f"【当前场景】\n地点：{scene_info.get('location', '未知')}\n氛围：{scene_info.get('atmosphere', '正剧')}")

        # 角色出场边界
        constraint_lines = []
        present_names = [str(c.get("name")) for c in scene_directions.get("performers", []) if isinstance(c, dict) and c.get("name")]
        present_names.extend(str(c.get("name")) for c in scene_directions.get("background_characters", []) if isinstance(c, dict) and c.get("name"))
        mentioned_names = [str(c.get("name")) for c in scene_directions.get("mentioned_characters", []) if isinstance(c, dict) and c.get("name")]
        unavailable_names = [str(c.get("name")) for c in scene_directions.get("unavailable_characters", []) if isinstance(c, dict) and c.get("name")]
        if present_names:
            constraint_lines.append(f"可在当前正面场景互动/发言的角色：{', '.join(dict.fromkeys(present_names))}")
        if mentioned_names:
            constraint_lines.append(f"只能提及、不能出场/发言/行动的角色：{', '.join(dict.fromkeys(mentioned_names))}")
        if unavailable_names:
            constraint_lines.append(f"禁止作为当前场景活人参与者的角色：{', '.join(dict.fromkeys(unavailable_names))}")
        if scene_directions.get("mentioned_character_rule"):
            constraint_lines.append(str(scene_directions.get("mentioned_character_rule")))
        if constraint_lines:
            parts.append("【角色出场硬约束】\n" + "\n".join(f"- {line}" for line in constraint_lines) + "\n- 不得让禁止/仅提及角色直接说话、行动、进入现场或推动当前场景。")

        # 角色定位
        char_specific = info_package.get("character_specific", {})
        if char_specific:
            parts.append(f"【你的角色定位】\n{char_specific.get('role_in_scene', '参与者')}\n情绪：{char_specific.get('emotional_state', '平静')}")

        # 剧情上下文
        plot_context = info_package.get("plot_context", {})
        if plot_context.get("plot_focus"):
            parts.append(f"【剧情焦点】\n{plot_context.get('plot_focus')}")
        if plot_context.get("visible_events"):
            parts.append(f"【你能看到的事】\n{chr(10).join(plot_context.get('visible_events', []))}")

        # 上文相关内容
        prev_context = info_package.get("previous_context", {})
        if prev_context.get("related_dialogues"):
            dialogues = [f"{d.get('agent', '某人')}: {d.get('content', '')}" for d in prev_context.get("related_dialogues", [])]
            parts.append(f"【之前听到的话】\n{chr(10).join(dialogues)}")

        return "\n\n".join(parts)

    def _generate_background_action(
        self,
        bg_char: Dict[str, Any],
        scene_directions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """生成背景角色的行为"""
        import random

        char_name = bg_char.get("name", "路人")
        atmosphere = scene_directions.get("atmosphere", "正剧")

        templates = {
            "正剧": [
                f"（{char_name}在一旁静静观看）",
                f"（{char_name}走过，没有停留）",
            ],
            "紧张": [
                f"（{char_name}神色紧张地望向这边）",
                f"（{char_name}快步走过）",
            ],
        }

        actions = templates.get(atmosphere, templates["正剧"])

        return {
            "agent": char_name,
            "type": "background_action",
            "content": random.choice(actions),
            "importance": "background",
            "importance_tier": 5,
        }

    async def _integrate_performances(
        self,
        performance_results: List[Dict[str, Any]],
        scene_directions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """整合表演内容，并保留公开/私有分层与关系/状态变化提案。"""
        # 分离主要角色和背景角色内容
        main_performances = [p for p in performance_results if _get_importance_tier(p, 3) <= 3]
        background_actions = [p for p in performance_results if _get_importance_tier(p, 3) > 3]

        # 构建完整公开场景内容
        full_content_lines = []
        for perf in performance_results:
            public_content = perf.get("public_content") or perf.get("content", "")
            if public_content:
                if _get_importance_tier(perf, 3) <= 3:
                    full_content_lines.append(f"【{perf.get('agent')}】{public_content}")
                else:
                    full_content_lines.append(public_content)

        private_performances = []
        relationship_deltas = []
        state_deltas = []
        continuity_notes = []
        performance_warnings = []

        for perf in performance_results:
            agent = perf.get("agent", "")
            private_thought = perf.get("private_thought") or perf.get("inner_thought")
            if private_thought or perf.get("intent") or perf.get("withheld_information"):
                private_performances.append({
                    "agent": agent,
                    "private_thought": private_thought or "",
                    "intent": perf.get("intent", ""),
                    "withheld_information": perf.get("withheld_information", []),
                    "misinterpretations": perf.get("misinterpretations", []),
                    "round": perf.get("round"),
                })

            for delta in perf.get("relationship_delta", []) or []:
                if isinstance(delta, dict):
                    relationship_deltas.append({"source_character": agent, **delta})
                else:
                    relationship_deltas.append({"source_character": agent, "change": delta})

            for delta in perf.get("state_delta", []) or []:
                if isinstance(delta, dict):
                    state_deltas.append({"source_character": agent, **delta})
                else:
                    state_deltas.append({"source_character": agent, "change": delta})

            for note in perf.get("continuity_notes", []) or []:
                continuity_notes.append({"source_character": agent, "note": note})

            for warning in perf.get("warnings", []) or []:
                performance_warnings.append({"source_character": agent, "warning": warning})

        return {
            "mode": scene_directions.get("scene_type", "interactive"),
            "scene": scene_directions.get("main_scene", ""),
            "characters": list(set(p.get("agent") for p in performance_results)),
            "performances": performance_results,
            "public_performances": [
                {
                    "agent": p.get("agent"),
                    "type": p.get("type"),
                    "content": p.get("public_content") or p.get("content", ""),
                    "dialogue": p.get("dialogue", ""),
                    "action": p.get("action", ""),
                    "emotion": p.get("emotion", ""),
                    "round": p.get("round"),
                    "importance_tier": _get_importance_tier(p, 3),
                }
                for p in performance_results
                if p.get("public_content") or p.get("content")
            ],
            "private_performances": private_performances,
            "relationship_deltas": relationship_deltas,
            "state_deltas": state_deltas,
            "continuity_notes": continuity_notes,
            "performance_warnings": performance_warnings,
            "full_content": "\n".join(full_content_lines),
            "main_dialogues": [p for p in main_performances if p.get("public_content") or p.get("content")],
            "background_actions": background_actions,
            "total_lines": len([p for p in performance_results if p.get("public_content") or p.get("content")]),
        }

    def clear_character_agents(self):
        """清理角色 Agent 实例池"""
        self._character_agents.clear()
        logger.info("已清理所有角色 Agent 实例")

    def get_character_agent(self, character_id: str) -> Optional[CharacterAgent]:
        """获取指定角色的 Agent 实例"""
        return self._character_agents.get(character_id)

    def get_all_character_agents(self) -> Dict[str, CharacterAgent]:
        """获取所有角色 Agent 实例"""
        return self._character_agents.copy()
