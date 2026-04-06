"""
导演系统核心服务 - 协调所有 Agent 进行小说生成
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.agents.character_agent import CharacterAgent
from app.agents.procgen import ProcGenAgent
from app.agents.evaluator import EvaluatorAgent
from app.agents.director.summarizer import SummarizerAgent
from app.agents.director.master_plotter import MasterPlotterAgent
from app.agents.director.hook_manager import HookManagerAgent
from app.agents.director.writer import WriterAgent

logger = logging.getLogger(__name__)


class DirectorSystem:
    """导演系统 -  orchestrates all agents for novel generation"""

    def __init__(self, world_data: Dict[str, Any], config: Optional[Dict[str, Any]] = None):
        self.world_id = world_data.get("id", str(uuid.uuid4()))
        self.world_data = world_data
        self.config = config or {}

        # 状态
        self.current_chapter: Optional[Dict[str, Any]] = None
        self.chapter_events: List[Dict[str, Any]] = []
        self.dialogue_history: List[Dict[str, Any]] = []
        self.hooks_planted: List[str] = []
        self.main_plot_progress: float = 0.0

        # Agent 实例（待注入模型）
        self.summarizer: Optional[SummarizerAgent] = None
        self.master_plotter: Optional[MasterPlotterAgent] = None
        self.hook_manager: Optional[HookManagerAgent] = None
        self.writer: Optional[WriterAgent] = None
        self.evaluator: Optional[EvaluatorAgent] = None

        # 角色 Agent 池
        self.character_agents: Dict[str, CharacterAgent] = {}

        logger.info(f"导演系统初始化完成 (世界 ID: {self.world_id})")

    async def initialize(
        self,
        model_factory: callable,
        characters: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        初始化导演系统的各个 Agent

        Args:
            model_factory: 返回语言模型实例的工厂函数
            characters: 角色数据列表
        """
        model = model_factory()

        # 初始化导演系统 Agents
        self.summarizer = SummarizerAgent(model=model)
        self.master_plotter = MasterPlotterAgent(model=model)
        self.hook_manager = HookManagerAgent(model=model)
        self.writer = WriterAgent(model=model)
        self.evaluator = EvaluatorAgent(model=model)

        # 初始化角色 Agents
        if characters:
            for char_data in characters:
                agent = CharacterAgent(
                    character=char_data.get("id", ""),
                    model=model,
                )
                self.character_agents[char_data["id"]] = agent

        logger.info("导演系统 Agent 初始化完成")

    async def start_chapter(self, title: str, goal: Optional[str] = None) -> Dict[str, Any]:
        """
        开始新章节

        Args:
            title: 章节标题
            goal: 章节目标

        Returns:
            Dict: 章节初始化结果
        """
        chapter_id = f"chapter_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        self.current_chapter = {
            "id": chapter_id,
            "title": title,
            "goal": goal,
            "word_count": 0,
            "status": "in_progress",
        }
        self.chapter_events = []
        self.hooks_planted = []

        return {
            "success": True,
            "chapter_id": chapter_id,
            "message": f"章节 '{title}' 已启动",
        }

    async def process_dialogue_turn(
        self,
        speaker_id: str,
        context: str,
        present_characters: List[str],
    ) -> Dict[str, Any]:
        """
        处理一轮对话

        Args:
            speaker_id: 说话者 ID
            context: 当前情境
            present_characters: 在场角色列表

        Returns:
            Dict: 生成的对话结果
        """
        # TODO: 调用角色 Agent 生成对话
        # 模拟响应
        response = {
            "speaker_id": speaker_id,
            "dialogue": "（示例对话）",
            "action": "（示例动作）",
            "emotion": "neutral",
        }

        # 记录到对话历史
        self.dialogue_history.append({
            "speaker": speaker_id,
            "content": response["dialogue"],
            "action": response.get("action", ""),
            "turn": len(self.dialogue_history),
        })

        return response

    async def summarize_dialogue(self, dialogue_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        总结对话批次为事件摘要

        Args:
            dialogue_batch: 对话批次数据

        Returns:
            Dict: 事件摘要
        """
        if not self.summarizer:
            raise RuntimeError("导演系统未初始化")

        result = await self.summarizer.execute({
            "dialogue_history": dialogue_batch,
            "participants": list(set([d["speaker"] for d in dialogue_batch])),
            "context": self.current_chapter.get("goal", ""),
            "active_hooks": self._get_active_hooks(),
        })

        if result.success:
            summary = result.data
            event = {
                "id": f"event_{len(self.chapter_events)}",
                "summary": summary.get("summary", ""),
                "subtext_markers": summary.get("subtext_markers", []),
                "hook_triggers": summary.get("hook_triggers", []),
                "info_gain_score": summary.get("info_gain_score", 0),
            }
            self.chapter_events.append(event)

            # 更新伏笔状态
            for hook_id in summary.get("hook_triggers", []):
                if hook_id not in self.hooks_planted:
                    self.hooks_planted.append(hook_id)

            return {"success": True, "event": event}
        else:
            return {"success": False, "error": result.error}

    async def check_chapter_end(self) -> Dict[str, Any]:
        """
        检查章节是否可以收尾

        Returns:
            Dict: 评估结果
        """
        if not self.evaluator:
            raise RuntimeError("导演系统未初始化")

        word_count = self.current_chapter.get("word_count", 0) if self.current_chapter else 0

        result = await self.evaluator.execute({
            "task_type": "chapter_end",
            "events": self.chapter_events,
            "hooks_planted": self.hooks_planted,
            "word_count": word_count,
            "chapter_content": "",
        })

        if result.success:
            evaluation = result.data
            if evaluation.get("should_end", False):
                await self._finalize_chapter()

            return evaluation
        else:
            return {"success": False, "error": result.error}

    async def advance_plot(self) -> Dict[str, Any]:
        """
        推进主线剧情

        Returns:
            Dict: 推进决策
        """
        if not self.master_plotter:
            raise RuntimeError("导演系统未初始化")

        pending_hooks = await self._get_pending_hooks()

        result = await self.master_plotter.execute({
            "main_plot_progress": self.main_plot_progress,
            "pending_hooks": pending_hooks,
            "chapter_goal": self.current_chapter.get("goal", "") if self.current_chapter else "",
            "recent_events": [e.get("summary", "") for e in self.chapter_events[-3:]],
            "interaction_turns": len(self.dialogue_history),
            "max_turns_threshold": self.config.get("max_turns_threshold", 5),
        })

        if result.success:
            decision = result.data

            # 如果需要强制推进
            if decision.get("forced_event"):
                await self._trigger_forced_event(decision["forced_event"])

            # 更新进度
            if decision.get("should_advance", False):
                self.main_plot_progress = min(decision.get("current_progress", 0), 1.0)

            return decision
        else:
            return {"success": False, "error": result.error}

    async def manage_hooks(self) -> Dict[str, Any]:
        """
        管理伏笔埋设与回收

        Returns:
            Dict: 伏笔管理决策
        """
        if not self.hook_manager:
            raise RuntimeError("导演系统未初始化")

        available_hooks = await self._get_available_hooks()
        triggered_hooks = await self._get_triggered_hooks()
        pending_hooks = await self._get_pending_hooks()

        result = await self.hook_manager.execute({
            "available_hooks": available_hooks,
            "triggered_hooks": triggered_hooks,
            "pending_hooks": pending_hooks,
            "current_scene": self._get_current_scene_description(),
            "recent_events": [e.get("summary", "") for e in self.chapter_events[-3:]],
        })

        if result.success:
            decisions = result.data

            # 应用伏笔埋设
            for hook_info in decisions.get("hooks_to_plant", []):
                await self._plant_hook(hook_info)

            # 应用伏笔回收
            for hook_info in decisions.get("hooks_to_resolve", []):
                await self._resolve_hook(hook_info)

            return decisions
        else:
            return {"success": False, "error": result.error}

    async def generate_narrative(
        self,
        intents: List[str],
        environment: str = "",
        character_moods: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        生成叙事文本

        Args:
            intents: 意图列表
            environment: 环境描述
            character_moods: 角色情绪

        Returns:
            Dict: 生成的文本
        """
        if not self.writer:
            raise RuntimeError("导演系统未初始化")

        hooks = await self._get_active_hooks_with_details()

        result = await self.writer.execute({
            "intents": intents,
            "environment": environment,
            "character_moods": character_moods or {},
            "hooks": hooks,
            "word_count": self.config.get("target_word_count_per_intent", 200),
        })

        if result.success:
            narrative = result.data
            self.current_chapter["word_count"] = (
                self.current_chapter.get("word_count", 0) + narrative.get("word_count", 0)
            )
            return narrative
        else:
            return {"success": False, "error": result.error}

    async def simulate_reader_feedback(self, chapter_content: str) -> Dict[str, Any]:
        """
        模拟读者反馈评分

        Args:
            chapter_content: 章节内容

        Returns:
            Dict: 评分结果
