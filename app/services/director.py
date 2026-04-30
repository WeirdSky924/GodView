"""
导演系统核心服务 - 协调所有 Agent 进行小说生成
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.agents.character_agent import CharacterAgent
from app.agents.evaluator import EvaluatorAgent
from app.agents.director.hook_manager import HookManagerAgent
from app.agents.director.master_plotter import MasterPlotterAgent
from app.agents.director.summarizer import SummarizerAgent
from app.agents.director.writer import WriterAgent
from app.agents.procgen import ProcGenAgent
# Removed circular import: qdrant_db will be imported lazily
# from app.api.app import qdrant_db
from app.models.character import Character, CharacterStatus
from app.models.world import World
# Removed to fix circular import: DirectorWorkflow will be imported lazily
# from app.services.workflow import DirectorWorkflow

logger = logging.getLogger(__name__)


class CharacterEvent:
    """角色事件"""
    CHARACTER_CREATED = "character_created"
    CHARACTER_DIED = "character_died"
    CHARACTER_RESURRECTED = "character_resurrected"
    CHARACTER_STATUS_CHANGED = "character_status_changed"
    CHARACTER_ADDED_TO_SCENE = "character_added_to_scene"
    CHARACTER_REMOVED_FROM_SCENE = "character_removed_from_scene"
    CHARACTER_PRESENCE_CHANGED = "character_presence_changed"

    def __init__(
        self,
        event_type: str,
        character_id: str,
        character_name: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        self.event_type = event_type
        self.character_id = character_id
        self.character_name = character_name
        self.data = data or {}
        self.timestamp = datetime.utcnow()


class DirectorSystem:
    """导演系统 - orchestrates all agents for novel generation"""

    def __init__(self, world_data: Dict[str, Any], config: Optional[Dict[str, Any]] = None, project_id: Optional[str] = None):
        self.world_id = world_data.get("id", str(uuid.uuid4()))
        self.world_data = world_data
        self.config = config or {}
        self.project_id = project_id  # v7: 用于加载 prompt 模板
        self.session_id: Optional[str] = None

        self.current_chapter: Optional[Dict[str, Any]] = None
        self.chapter_events: List[Dict[str, Any]] = []
        self.dialogue_history: List[Dict[str, Any]] = []
        self.hooks_planted: List[str] = []
        self.hooks_resolved: List[str] = []
        self.main_plot_progress: float = 0.0
        self.current_snapshot_id: Optional[str] = None
        self.state_machine: Dict[str, Any] = {
            "phase": "idle",
            "last_forced_event": None,
            "branch_count": 0,
        }

        self.summarizer: Optional[SummarizerAgent] = None
        self.master_plotter: Optional[MasterPlotterAgent] = None
        self.hook_manager: Optional[HookManagerAgent] = None
        self.writer: Optional[WriterAgent] = None
        self.evaluator: Optional[EvaluatorAgent] = None
        self.procgen: Optional[ProcGenAgent] = None

        self.character_agents: Dict[str, CharacterAgent] = {}
        self._model_factory: Optional[Callable] = None

        # v8: 角色事件回调（用于通知工作流引擎）
        self._character_event_callbacks: List[Callable[[CharacterEvent], None]] = []
        # 角色死亡记录（用于剧情追踪）
        self.dead_characters: List[Dict[str, Any]] = []

        logger.info(f"导演系统初始化完成 (世界 ID: {self.world_id})")

    async def initialize(
        self,
        model_factory: Callable,
        characters: Optional[List[Dict[str, Any]]] = None,
    ):
        """初始化导演系统的各个 Agent。"""
        self._model_factory = model_factory
        model = model_factory()

        # v7: 传入 project_id 以支持 prompt 模板系统
        self.summarizer = SummarizerAgent(model=model, project_id=self.project_id)
        self.master_plotter = MasterPlotterAgent(model=model, project_id=self.project_id)
        self.hook_manager = HookManagerAgent(model=model, project_id=self.project_id)
        self.writer = WriterAgent(model=model, project_id=self.project_id)
        self.evaluator = EvaluatorAgent(model=model, project_id=self.project_id)
        self.procgen = ProcGenAgent(world=World(**self._build_world_payload()), model=model, project_id=self.project_id)

        self.character_agents = {}
        for char_data in characters or []:
            agent = self._create_character_agent(char_data)
            self.character_agents[agent.character.id] = agent

        self.state_machine["phase"] = "initialized"
        logger.info("导演系统 Agent 初始化完成")

    async def start_chapter(self, title: str, goal: Optional[str] = None) -> Dict[str, Any]:
        chapter_id = str(uuid.uuid4())

        self.current_chapter = {
            "id": chapter_id,
            "title": title,
            "goal": goal,
            "word_count": 0,
            "status": "in_progress",
            "content": "",
            "events": [],
            "hooks_planted": [],
            "hooks_resolved": [],
            "main_plot_progress": self.main_plot_progress,
            "reader_scores": None,
        }
        self.chapter_events = []
        self.dialogue_history = []
        self.hooks_planted = []
        self.hooks_resolved = []
        self.state_machine["phase"] = "chapter_started"

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
        """处理一轮对话。"""
        agent = self.character_agents.get(speaker_id)
        if not agent:
            fallback_character = self._build_fallback_character(speaker_id)
            agent = self._create_character_agent(fallback_character)
            self.character_agents[speaker_id] = agent

        result = await agent.execute({
            "context": context,
            "present_characters": present_characters,
            "recent_events": [e.get("summary", "") for e in self.chapter_events[-3:]],
            "dialogue_history": self.dialogue_history[-10:],
        })

        if not result.success:
            return {
                "success": False,
                "speaker_id": speaker_id,
                "error": result.error,
            }

        response = {
            "success": True,
            "speaker_id": speaker_id,
            "dialogue": result.data.get("dialogue", ""),
            "action": result.data.get("action", ""),
            "inner_thought": result.data.get("inner_thought", ""),
            "emotion": result.data.get("emotion", "neutral"),
        }

        voice_context = await self._get_character_voice_context(agent, context, response["dialogue"])
        voice_review = await self._review_character_voice(agent, response["dialogue"], voice_context)
        response["voice_context"] = voice_context
        response["voice_review"] = voice_review

        rewritten_dialogue = await self._rewrite_dialogue_if_needed(agent, response["dialogue"], voice_review)
        if rewritten_dialogue:
            response["dialogue"] = rewritten_dialogue["dialogue"]
            response["voice_review"] = rewritten_dialogue["voice_review"]
            response["rewrite_result"] = rewritten_dialogue["rewrite_result"]

        self.dialogue_history.append({
            "speaker": speaker_id,
            "content": response["dialogue"],
            "action": response.get("action", ""),
            "emotion": response.get("emotion", "neutral"),
            "turn": len(self.dialogue_history),
        })

        if self.current_chapter is not None:
            dialogue_text = response["dialogue"] or ""
            self.current_chapter["word_count"] = self.current_chapter.get("word_count", 0) + len(dialogue_text)
            existing_content = self.current_chapter.get("content", "")
            rendered = f"{speaker_id}：{dialogue_text}" if dialogue_text else ""
            if rendered:
                self.current_chapter["content"] = f"{existing_content}\n{rendered}".strip()

        self.state_machine["phase"] = "dialogue_generated"
        return response

    async def summarize_dialogue(self, dialogue_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.summarizer:
            raise RuntimeError("导演系统未初始化")

        result = await self.summarizer.execute({
            "dialogue_history": dialogue_batch,
            "participants": list(set([d["speaker"] for d in dialogue_batch])),
            "context": self.current_chapter.get("goal", "") if self.current_chapter else "",
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

            if self.current_chapter is not None:
                self.current_chapter["events"] = [e["id"] for e in self.chapter_events]

            for hook_id in summary.get("hook_triggers", []):
                if hook_id not in self.hooks_planted:
                    self.hooks_planted.append(hook_id)

            return {"success": True, "event": event}
        return {"success": False, "error": result.error}

    async def check_chapter_end(self, chapter_content: Optional[str] = None) -> Dict[str, Any]:
        if not self.evaluator:
            raise RuntimeError("导演系统未初始化")

        content = chapter_content
        if content is None and self.current_chapter:
            content = self.current_chapter.get("content", "")

        word_count = self.current_chapter.get("word_count", 0) if self.current_chapter else 0
        if content and not word_count:
            word_count = len(content)

        result = await self.evaluator.execute({
            "task_type": "chapter_end",
            "events": self.chapter_events,
            "hooks_planted": self.hooks_planted,
            "word_count": word_count,
            "chapter_content": content or "",
        })

        if result.success:
            evaluation = result.data
            if evaluation.get("should_end", False):
                await self._finalize_chapter()
            return evaluation
        return {"success": False, "error": result.error}

    async def advance_plot(self) -> Dict[str, Any]:
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
            if decision.get("forced_event"):
                await self._trigger_forced_event(decision["forced_event"])
            if decision.get("should_advance", False):
                self.main_plot_progress = min(decision.get("current_progress", 0), 1.0)
                if self.current_chapter is not None:
                    self.current_chapter["main_plot_progress"] = self.main_plot_progress
            self.state_machine["phase"] = "plot_advanced"
            return decision
        return {"success": False, "error": result.error}

    async def manage_hooks(self) -> Dict[str, Any]:
        """
        管理伏笔 - 根据当前剧情和未来规划管理伏笔的埋设与回收

        功能：
        1. 加载项目中已有的伏笔（从数据库）
        2. 根据当前剧情状态决定是否需要新伏笔
        3. 检查已有伏笔是否可以回收
        4. 更新伏笔状态
        """
        if not self.hook_manager:
            raise RuntimeError("导演系统未初始化")

        # 从数据库加载现有伏笔
        existing_hooks = await self._load_hooks_from_database()

        # 分析当前剧情状态
        plot_context = self._build_plot_context()

        # 构建完整的输入
        result = await self.hook_manager.execute({
            "existing_hooks": existing_hooks,  # 数据库中的伏笔
            "hooks_planted_in_chapter": self.hooks_planted,  # 本章节埋设的伏笔
            "hooks_resolved_in_chapter": self.hooks_resolved,  # 本章节回收的伏笔
            "plot_context": plot_context,
            "current_scene": self._get_current_scene_description(),
            "recent_events": [e.get("summary", "") for e in self.chapter_events[-5:]],
            "chapter_goal": self.current_chapter.get("goal") if self.current_chapter else None,
        })

        if result.success:
            decisions = result.data

            # 处理新伏笔埋设
            planted_hooks = []
            for hook_info in decisions.get("hooks_to_plant", []):
                hook_id = await self._plant_hook_with_details(hook_info)
                planted_hooks.append(hook_id)

            # 处理伏笔回收
            resolved_hooks = []
            for hook_info in decisions.get("hooks_to_resolve", []):
                await self._resolve_hook_with_details(hook_info)
                resolved_hooks.append(hook_info.get("id"))

            # 更新伏笔状态
            for update in decisions.get("hooks_status_updates", []):
                await self._update_hook_status_in_db(update)

            self.state_machine["phase"] = "hooks_managed"

            return {
                "success": True,
                "planted_hooks": planted_hooks,
                "resolved_hooks": resolved_hooks,
                "suggestions": decisions.get("suggestions", []),
                "reasoning": decisions.get("reasoning", ""),
            }

        return {"success": False, "error": result.error}

    async def _load_hooks_from_database(self) -> List[Dict[str, Any]]:
        """从数据库加载项目的伏笔"""
        from app.api.app import postgres_db

        if not postgres_db or not self.project_id:
            return []

        try:
            # 获取所有状态的伏笔
            planted = await postgres_db.get_hooks_by_status("planted", self.project_id)
            triggered = await postgres_db.get_hooks_by_status("triggered", self.project_id)
            pending = await postgres_db.get_hooks_by_status("pending", self.project_id)

            all_hooks = planted + triggered + pending
            return all_hooks
        except Exception as e:
            logger.warning(f"加载伏笔失败: {e}")
            return []

    def _build_plot_context(self) -> Dict[str, Any]:
        """构建剧情上下文"""
        return {
            "main_plot_progress": self.main_plot_progress,
            "current_chapter": self.current_chapter.get("title") if self.current_chapter else None,
            "chapter_events_count": len(self.chapter_events),
            "character_count": len(self.character_agents),
            "active_characters": [char.name for char in [a.character for a in self.character_agents.values()]],
        }

    async def _plant_hook_with_details(self, hook_info: Dict[str, Any]) -> str:
        """埋设伏笔并保存到数据库"""
        import uuid
        from app.api.app import postgres_db

        hook_id = str(uuid.uuid4())

        hook_data = {
            "id": hook_id,
            "title": hook_info.get("title", f"伏笔-{len(self.hooks_planted) + 1}"),
            "project_id": self.project_id,
            "world_id": self.world_id,
            "description": hook_info.get("description", ""),
            "hook_type": hook_info.get("hook_type", "suspense"),  # suspense, foreshadow, twist
            "status": "planted",
            "related_characters": hook_info.get("related_characters", []),
            "related_locations": hook_info.get("related_locations", []),
            "related_objects": hook_info.get("related_objects", []),
            "plant_context": self._get_current_scene_description(),
            "plant_chapter": self.current_chapter.get("id") if self.current_chapter else None,
            "resolution_hint": hook_info.get("resolution_hint"),
            "resolution_context": None,
            "resolution_chapter": None,
            "priority": hook_info.get("priority", 5),
        }

        # 保存到数据库
        if postgres_db:
            try:
                await postgres_db.save_hook(hook_data)
            except Exception as e:
                logger.warning(f"保存伏笔到数据库失败: {e}")

        # 更新内存状态
        if hook_id not in self.hooks_planted:
            self.hooks_planted.append(hook_id)

        if self.current_chapter is not None:
            current = self.current_chapter.setdefault("hooks_planted", [])
            if hook_id not in current:
                current.append(hook_id)

        return hook_id

    async def _resolve_hook_with_details(self, hook_info: Dict[str, Any]):
        """回收伏笔并更新数据库"""
        from app.api.app import postgres_db
        from datetime import datetime

        hook_id = hook_info.get("id")
        if not hook_id:
            return

        # 更新数据库
        if postgres_db:
            try:
                update_data = {
                    "id": hook_id,
                    "status": "resolved",
                    "resolution_context": hook_info.get("resolution_context", self._get_current_scene_description()),
                    "resolution_chapter": self.current_chapter.get("id") if self.current_chapter else None,
                    "resolved_at": datetime.utcnow().isoformat(),
                }
                await postgres_db.save_hook(update_data)
            except Exception as e:
                logger.warning(f"更新伏笔状态失败: {e}")

        # 更新内存状态
        if hook_id in self.hooks_planted:
            self.hooks_planted.remove(hook_id)
        if hook_id not in self.hooks_resolved:
            self.hooks_resolved.append(hook_id)

        if self.current_chapter is not None:
            planted = self.current_chapter.get("hooks_planted", [])
            if hook_id in planted:
                planted.remove(hook_id)

            resolved = self.current_chapter.setdefault("hooks_resolved", [])
            if hook_id not in resolved:
                resolved.append(hook_id)

    async def _update_hook_status_in_db(self, update: Dict[str, Any]):
        """更新伏笔状态"""
        from app.api.app import postgres_db

        hook_id = update.get("id")
        new_status = update.get("new_status")

        if not hook_id or not new_status:
            return

        if postgres_db:
            try:
                await postgres_db.save_hook({
                    "id": hook_id,
                    "status": new_status,
                })
            except Exception as e:
                logger.warning(f"更新伏笔状态失败: {e}")

    async def generate_narrative(
        self,
        intents: List[str],
        environment: str = "",
        character_moods: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
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
            narrative = result.structured_data or result.data or {}
            narrative_content = result.text_output or narrative.get("chapter_content") or narrative.get("content", "")
            narrative["chapter_content"] = narrative_content
            narrative["content"] = narrative_content
            narrative_voice_review = await self._review_narrative_voice(
                narrative_content,
                character_moods or {},
                environment,
            )
            narrative["voice_review"] = narrative_voice_review

            rewritten_narrative = await self._rewrite_narrative_if_needed(
                narrative.get("content", ""),
                narrative_voice_review,
            )
            if rewritten_narrative:
                narrative["content"] = rewritten_narrative["content"]
                narrative["voice_review"] = rewritten_narrative["voice_review"]
                narrative["rewrite_result"] = rewritten_narrative["rewrite_result"]

            if self.current_chapter is not None:
                self.current_chapter["word_count"] = self.current_chapter.get("word_count", 0) + narrative.get("word_count", 0)
                content = narrative.get("content", "")
                existing_content = self.current_chapter.get("content", "")
                if content:
                    self.current_chapter["content"] = f"{existing_content}\n{content}".strip()
            self.state_machine["phase"] = "narrative_generated"
            return narrative
        return {"success": False, "error": result.error}

    async def run_workflow_cycle(
        self,
        speaker_id: str,
        context: str,
        present_characters: Optional[List[str]] = None,
        intents: Optional[List[str]] = None,
        environment: str = "",
        character_moods: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        # Lazy import to avoid circular dependency
        from app.services.workflow import DirectorWorkflow
        workflow = DirectorWorkflow(self)
        return await workflow.run_cycle(
            speaker_id=speaker_id,
            context=context,
            present_characters=present_characters or [],
            intents=intents,
            environment=environment,
            character_moods=character_moods,
        )

    async def simulate_reader_feedback(
        self,
        chapter_content: str,
        chapter_title: str = "无标题",
    ) -> Dict[str, Any]:
        if not self.evaluator:
            raise RuntimeError("导演系统未初始化")

        result = await self.evaluator.execute({
            "task_type": "reader_simulate",
            "chapter_content": chapter_content,
            "chapter_title": chapter_title,
        })
        if result.success:
            if self.current_chapter is not None:
                self.current_chapter["reader_scores"] = result.data.get("scores")
            return result.data
        return {"success": False, "error": result.error}

    async def generate_region(
        self,
        exploration_direction: str,
        current_location: Optional[str] = None,
        generation_type: str = "expansion",
    ) -> Dict[str, Any]:
        if not self.procgen:
            raise RuntimeError("导演系统未初始化")

        existing_regions = self.world_data.get("regions", [])
        result = await self.procgen.execute({
            "exploration_direction": exploration_direction,
            "current_location": current_location,
            "existing_regions": existing_regions,
            "generation_type": generation_type,
        })
        if result.success:
            region_data = result.data
            regions = self.world_data.setdefault("regions", [])
            regions.append(region_data)
            self.state_machine["phase"] = "region_generated"
            return region_data
        return {"success": False, "error": result.error}

    async def create_snapshot(
        self,
        snapshot_type: str = "auto",
        name: Optional[str] = None,
        description: Optional[str] = None,
        created_by: str = "system",
        is_branch: bool = False,
        branch_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        snapshot_id = str(uuid.uuid4())
        snapshot = {
            "id": snapshot_id,
            "world_id": self.world_id,
            "chapter_id": self.current_chapter.get("id") if self.current_chapter else None,
            "snapshot_type": snapshot_type,
            "name": name or self._default_snapshot_name(snapshot_type),
            "description": description,
            "characters": {
                char_id: agent.character.model_dump(mode="json")
                for char_id, agent in self.character_agents.items()
            },
            "relationships": self.world_data.get("relationships", {}),
            "regions": {
                region.get("id", f"region_{index}"): region
                for index, region in enumerate(self.world_data.get("regions", []))
            },
            "hooks": {
                hook_id: {"id": hook_id, "status": "planted"}
                for hook_id in self.hooks_planted
            },
            "main_plot_progress": self.main_plot_progress,
            "completed_events": [event.get("id") for event in self.chapter_events],
            "character_locations": {
                char_id: agent.character.current_location or ""
                for char_id, agent in self.character_agents.items()
            },
            "created_at": datetime.utcnow().isoformat(),
            "created_by": created_by,
            "parent_snapshot_id": self.current_snapshot_id,
            "is_branch": is_branch,
            "branch_reason": branch_reason,
        }
        self.current_snapshot_id = snapshot_id
        if is_branch:
            self.state_machine["branch_count"] = self.state_machine.get("branch_count", 0) + 1
        return snapshot

    async def apply_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        self.current_snapshot_id = snapshot.get("id")
        self.main_plot_progress = snapshot.get("main_plot_progress", 0.0)
        self.hooks_planted = list(snapshot.get("hooks", {}).keys())
        self.chapter_events = [
            {"id": event_id, "summary": "已回档事件", "subtext_markers": [], "hook_triggers": [], "info_gain_score": 0.0}
            for event_id in snapshot.get("completed_events", [])
        ]

        characters = snapshot.get("characters", {})
        self.character_agents = {}
        for char_id, char_data in characters.items():
            agent = self._create_character_agent({"id": char_id, **char_data})
            self.character_agents[char_id] = agent

        self.world_data["regions"] = list(snapshot.get("regions", {}).values())
        self.world_data["relationships"] = snapshot.get("relationships", {})
        self.state_machine["phase"] = "rolled_back"
        return {"success": True, "snapshot_id": self.current_snapshot_id}

    async def create_intervention_record(
        self,
        snapshot_id: str,
        intervention_type: str,
        description: str,
        details: Optional[Dict[str, Any]] = None,
        affected_hooks: Optional[List[str]] = None,
        affected_relationships: Optional[List[str]] = None,
        affected_characters: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "snapshot_id": snapshot_id,
            "intervention_type": intervention_type,
            "description": description,
            "details": details or {},
            "affected_hooks": affected_hooks or [],
            "affected_relationships": affected_relationships or [],
            "affected_characters": affected_characters or [],
            "outcome_rating": None,
            "outcome_notes": None,
            "created_at": datetime.utcnow().isoformat(),
        }

    def export_runtime_state(self) -> Dict[str, Any]:
        return {
            "world_id": self.world_id,
            "current_chapter": self.current_chapter,
            "chapter_events": self.chapter_events,
            "dialogue_history": self.dialogue_history,
            "hooks_planted": self.hooks_planted,
            "hooks_resolved": self.hooks_resolved,
            "main_plot_progress": self.main_plot_progress,
            "current_snapshot_id": self.current_snapshot_id,
            "state_machine": self.state_machine,
            "regions": self.world_data.get("regions", []),
        }

    def _create_character_agent(self, char_data: Dict[str, Any]) -> CharacterAgent:
        model = self._model_factory() if self._model_factory else None

        # 如果已经是 Character 对象，直接使用
        if isinstance(char_data, Character):
            return CharacterAgent(
                character=char_data,
                model=model,
                project_id=self.project_id,
                agent_id=char_data.id,
            )

        # 处理类型转换
        char_dict = dict(char_data)

        # UUID 转 string - 处理所有可能的 UUID 字段
        uuid_fields = ["id", "project_id", "world_id", "current_location", "current_region_id"]
        for field in uuid_fields:
            if field in char_dict and char_dict[field] is not None and not isinstance(char_dict[field], str):
                char_dict[field] = str(char_dict[field])

        # personality_traits: 处理各种格式
        if "personality_traits" in char_dict:
            traits = char_dict["personality_traits"]
            if isinstance(traits, dict):
                # dict 格式转 list
                traits_list = []
                for key, value in traits.items():
                    if isinstance(value, dict):
                        traits_list.append({"name": key, "value": value.get("value", 0.5), "description": value.get("description", "")})
                    elif isinstance(value, (int, float)):
                        traits_list.append({"name": key, "value": float(value)})
                    else:
                        traits_list.append({"name": key, "value": 0.5})
                char_dict["personality_traits"] = traits_list
            elif isinstance(traits, list):
                # 确保列表元素是正确的格式
                traits_list = []
                for t in traits:
                    if isinstance(t, dict):
                        if "name" in t:
                            traits_list.append({"name": t["name"], "value": t.get("value", 0.5), "description": t.get("description")})
                    elif isinstance(t, str):
                        traits_list.append({"name": t, "value": 0.5})
                char_dict["personality_traits"] = traits_list
        else:
            char_dict["personality_traits"] = []

        # 确保其他必要字段存在
        if "name" not in char_dict:
            char_dict["name"] = char_dict.get("id", "未知角色")
        if "role" not in char_dict:
            char_dict["role"] = "npc"
        if "status" not in char_dict:
            char_dict["status"] = "active"

        # 确保有 background 字段（兼容 background_story）
        if "background_story" in char_dict and "background" not in char_dict:
            char_dict["background"] = char_dict.pop("background_story")

        character = Character(**char_dict)
        return CharacterAgent(
            character=character,
            model=model,
            project_id=self.project_id,
            agent_id=character.id,
        )

    def _build_fallback_character(self, speaker_id: str) -> Dict[str, Any]:
        return {
            "id": speaker_id,
            "name": speaker_id,
            "description": "临时注入角色",
            "role": "npc",
            "status": "active",
            "appearance": "",
            "personality_traits": [],
            "background_story": "",
            "speech_pattern": "",
            "lexicon": [],
            "forbidden_words": [],
            "voice_samples": [],
            "attributes": {},
            "goals": [],
            "inventory": [],
            "current_location": None,
        }

    async def _get_character_voice_context(
        self,
        agent: CharacterAgent,
        context: str,
        dialogue: str,
        limit: int = 3,
    ) -> Dict[str, Any]:
        voice_samples = agent.character.voice_samples or []
        similar_samples: List[str] = []
        vector_hits: List[Dict[str, Any]] = []

        # Lazy import to avoid circular dependency
        try:
            from app.api.app import qdrant_db
        except ImportError:
            qdrant_db = None

        if qdrant_db and (context or dialogue):
            query_text = f"{context}\n{dialogue}".strip()
            try:
                # 获取角色的 project_id 用于过滤
                project_id = agent.character.project_id
                vector_hits = await qdrant_db.get_similar_voice_samples_by_text(
                    query_text=query_text,
                    character_id=agent.character.id,
                    project_id=project_id,
                    limit=limit,
                )
            except Exception as exc:
                logger.warning(f"角色声音向量检索失败：{exc}")

        for hit in vector_hits:
            text = hit.get("payload", {}).get("text")
            if text and text not in similar_samples:
                similar_samples.append(text)

        if not similar_samples:
            similar_samples = voice_samples[:limit]

        return {
            "used_qdrant": bool(vector_hits),
            "retrieved_samples": similar_samples,
            "retrieved_count": len(similar_samples),
        }

    async def _review_character_voice(
        self,
        agent: CharacterAgent,
        dialogue: str,
        voice_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.evaluator or not dialogue:
            return {"checked": False}

        review_samples = (voice_context or {}).get("retrieved_samples") or agent.character.voice_samples
        review = await self.evaluator.evaluate_ooc(
            character_name=agent.character.name,
            character_traits=[trait.name for trait in agent.character.personality_traits],
            voice_samples=review_samples,
            dialogue=dialogue,
            forbidden_words=agent.character.forbidden_words,
        )
        if review.success:
            return {
                "checked": True,
                "reference_samples": review_samples,
                **review.data,
            }
        return {"checked": False, "error": review.error}

    async def _rewrite_dialogue_if_needed(
        self,
        agent: CharacterAgent,
        dialogue: str,
        voice_review: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not self.writer or not dialogue:
            return None
        if not voice_review.get("checked") or not voice_review.get("is_ooc"):
            return None

        rewrite = await self.writer.rewrite_with_character_voice(
            original_text=dialogue,
            character_name=agent.character.name,
            speech_pattern=agent.character.speech_pattern or "保持原角色表达习惯",
            lexicon=agent.character.lexicon,
            forbidden_words=agent.character.forbidden_words,
        )
        if not rewrite.success:
            return None

        rewritten_text = rewrite.text_output or (rewrite.structured_data or rewrite.data or {}).get("rewritten_text", "").strip()
        if not rewritten_text:
            return None

        second_review = await self._review_character_voice(agent, rewritten_text)
        return {
            "dialogue": rewritten_text,
            "voice_review": second_review,
            "rewrite_result": {
                "applied": True,
                "changes_made": (rewrite.structured_data or rewrite.data or {}).get("changes_made", []),
                "original_dialogue": dialogue,
            },
        }

    async def _review_narrative_voice(
        self,
        content: str,
        character_moods: Dict[str, str],
        environment: str,
    ) -> Dict[str, Any]:
        if not content or not character_moods:
            return {"checked": False, "reason": "no_character_moods"}

        review_results: List[Dict[str, Any]] = []
        for character_id in character_moods.keys():
            agent = self.character_agents.get(character_id)
            if not agent:
                continue

            voice_context = await self._get_character_voice_context(agent, environment, content)
            voice_review = await self._review_character_voice(agent, content, voice_context)
            review_results.append({
                "character_id": character_id,
                "character_name": agent.character.name,
                "voice_context": voice_context,
                "voice_review": voice_review,
            })

        if not review_results:
            return {"checked": False, "reason": "no_matching_character_agents"}

        return {
            "checked": True,
            "results": review_results,
            "has_ooc": any(item.get("voice_review", {}).get("is_ooc") for item in review_results),
        }

    async def _rewrite_narrative_if_needed(
        self,
        content: str,
        narrative_voice_review: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not self.writer or not content:
            return None
        if not narrative_voice_review.get("checked") or not narrative_voice_review.get("has_ooc"):
            return None

        target = next(
            (
                item for item in narrative_voice_review.get("results", [])
                if item.get("voice_review", {}).get("is_ooc")
            ),
            None,
        )
        if not target:
            return None

        character_id = target.get("character_id")
        agent = self.character_agents.get(character_id)
        if not agent:
            return None

        rewrite = await self.writer.rewrite_with_character_voice(
            original_text=content,
            character_name=agent.character.name,
            speech_pattern=agent.character.speech_pattern or "保持原角色表达习惯",
            lexicon=agent.character.lexicon,
            forbidden_words=agent.character.forbidden_words,
        )
        if not rewrite.success:
            return None

        rewritten_text = rewrite.text_output or (rewrite.structured_data or rewrite.data or {}).get("rewritten_text", "").strip()
        if not rewritten_text:
            return None

        second_review = await self._review_narrative_voice(rewritten_text, {character_id: "rewritten"}, "")
        return {
            "content": rewritten_text,
            "voice_review": second_review,
            "rewrite_result": {
                "applied": True,
                "changes_made": (rewrite.structured_data or rewrite.data or {}).get("changes_made", []),
                "original_content": content,
                "target_character_id": character_id,
                "target_character_name": agent.character.name,
            },
        }

    def _build_world_payload(self) -> Dict[str, Any]:
        # 转换 UUID 对象为字符串（asyncpg 返回 UUID 作为 Python UUID 对象）
        world_id = self.world_id
        if hasattr(world_id, 'hex'):  # UUID object has .hex attribute
            world_id = str(world_id)

        return {
            "id": world_id,
            "name": self.world_data.get("name", "Default World"),
            "description": self.world_data.get("description"),
            "world_type": self.world_data.get("world_type", "fantasy"),
            "tone": self.world_data.get("tone", "serious"),
            "rules": self.world_data.get("rules", []),
            "power_system": self.world_data.get("power_system"),
            "technology_level": self.world_data.get("technology_level"),
            "history": self.world_data.get("history"),
            "geography": self.world_data.get("geography"),
            "factions": self.world_data.get("factions", []),
        }

    def _default_snapshot_name(self, snapshot_type: str) -> str:
        if self.current_chapter:
            return f"{self.current_chapter.get('title', '章节')} - {snapshot_type}"
        return f"{self.world_data.get('name', 'world')} - {snapshot_type}"

    def _get_active_hooks(self) -> List[str]:
        return list(self.hooks_planted)

    async def _get_pending_hooks(self) -> List[Dict[str, Any]]:
        """获取待回收伏笔的详细信息（字典列表）"""
        from app.api.app import postgres_db

        pending_ids = [hook for hook in self.hooks_planted if hook not in self.hooks_resolved]

        # 如果有数据库连接，从数据库获取完整信息
        if postgres_db and pending_ids:
            try:
                all_hooks = await postgres_db.get_hooks_by_status("planted", self.project_id)
                all_hooks += await postgres_db.get_hooks_by_status("triggered", self.project_id)
                # 过滤出 pending_ids 中的伏笔
                return [h for h in all_hooks if h.get("id") in pending_ids]
            except Exception as e:
                logger.warning(f"获取伏笔详情失败: {e}")

        # 回退：返回基本信息
        return [{"id": hook_id, "title": f"伏笔-{hook_id[:8]}", "priority": 5} for hook_id in pending_ids]

    async def _get_available_hooks(self) -> List[Dict[str, Any]]:
        return [{"id": hook_id, "status": "planted"} for hook_id in self.hooks_planted]

    async def _get_triggered_hooks(self) -> List[str]:
        return list(self.hooks_planted)

    async def _get_active_hooks_with_details(self) -> List[Dict[str, Any]]:
        return [{"id": hook_id, "status": "planted"} for hook_id in self.hooks_planted]

    def _get_current_scene_description(self) -> str:
        if not self.current_chapter:
            return ""
        return self.current_chapter.get("goal", "") or self.current_chapter.get("title", "")

    async def _plant_hook(self, hook_info: Dict[str, Any]):
        # 生成有效的 UUID
        provided_id = hook_info.get("id")
        if provided_id:
            # 验证是否为有效 UUID
            try:
                uuid.UUID(str(provided_id))
                hook_id = str(provided_id)
            except (ValueError, TypeError):
                # 不是有效 UUID，生成新的
                hook_id = str(uuid.uuid4())
        else:
            hook_id = str(uuid.uuid4())

        if hook_id not in self.hooks_planted:
            self.hooks_planted.append(hook_id)
        if self.current_chapter is not None:
            current = self.current_chapter.setdefault("hooks_planted", [])
            if hook_id not in current:
                current.append(hook_id)

    async def _resolve_hook(self, hook_info: Dict[str, Any]):
        hook_id = hook_info.get("id") or hook_info.get("title")
        if hook_id and hook_id in self.hooks_planted:
            self.hooks_planted.remove(hook_id)
        if hook_id and hook_id not in self.hooks_resolved:
            self.hooks_resolved.append(hook_id)
        if self.current_chapter is not None and hook_id:
            current = self.current_chapter.setdefault("hooks_resolved", [])
            if hook_id not in current:
                current.append(hook_id)

    async def _trigger_forced_event(self, forced_event: str):
        self.chapter_events.append({
            "id": f"event_{len(self.chapter_events)}",
            "summary": forced_event,
            "subtext_markers": [],
            "hook_triggers": [],
            "info_gain_score": 0.5,
        })
        self.state_machine["last_forced_event"] = forced_event

    async def _finalize_chapter(self):
        if self.current_chapter:
            self.current_chapter["status"] = "completed"
            self.current_chapter["completed_at"] = datetime.utcnow().isoformat()
            self.current_chapter["events"] = [event.get("id") for event in self.chapter_events]
            self.current_chapter["hooks_planted"] = self.hooks_planted
            self.current_chapter["hooks_resolved"] = self.hooks_resolved
            self.current_chapter["main_plot_progress"] = self.main_plot_progress
            self.state_machine["phase"] = "chapter_completed"

    # ==================== 动态角色管理 ====================

    def add_character(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        动态添加角色到导演系统

        Args:
            character_data: 角色数据

        Returns:
            Dict: 添加结果
        """
        character_id = character_data.get("id")
        if not character_id:
            character_id = str(uuid.uuid4())
            character_data["id"] = character_id

        # 检查是否已存在
        if character_id in self.character_agents:
            return {
                "success": False,
                "error": f"角色 {character_id} 已存在",
            }

        # 创建 CharacterAgent
        agent = self._create_character_agent(character_data)
        self.character_agents[character_id] = agent

        logger.info(f"角色 '{character_data.get('name', character_id)}' 已添加到导演系统")

        # 发送角色创建事件
        self._emit_character_event(CharacterEvent(
            event_type=CharacterEvent.CHARACTER_CREATED,
            character_id=character_id,
            character_name=agent.character.name,
            data={"role": agent.character.role, "source": "dynamic"},
        ))

        return {
            "success": True,
            "character_id": character_id,
            "name": agent.character.name,
        }

    def remove_character(self, character_id: str) -> Dict[str, Any]:
        """
        从导演系统移除角色

        Args:
            character_id: 角色 ID

        Returns:
            Dict: 移除结果
        """
        if character_id not in self.character_agents:
            return {
                "success": False,
                "error": f"角色 {character_id} 不存在",
            }

        agent = self.character_agents[character_id]
        character_name = agent.character.name

        del self.character_agents[character_id]

        logger.info(f"角色 '{character_name}' 已从导演系统移除")

        return {
            "success": True,
            "character_id": character_id,
            "name": character_name,
        }

    def update_character_status(
        self,
        character_id: str,
        new_status: CharacterStatus,
        reason: Optional[str] = None,
        death_detail: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        更新角色状态

        Args:
            character_id: 角色 ID
            new_status: 新状态
            reason: 状态变更原因
            death_detail: 死亡详情（死亡时可选）

        Returns:
            Dict: 更新结果
        """
        if character_id not in self.character_agents:
            return {
                "success": False,
                "error": f"角色 {character_id} 不存在",
            }

        agent = self.character_agents[character_id]
        old_status = agent.character.status
        agent.character.status = new_status

        logger.info(f"角色 '{agent.character.name}' 状态变更: {old_status} -> {new_status}")

        # 发送状态变更事件
        self._emit_character_event(CharacterEvent(
            event_type=CharacterEvent.CHARACTER_STATUS_CHANGED,
            character_id=character_id,
            character_name=agent.character.name,
            data={
                "old_status": old_status.value if hasattr(old_status, 'value') else str(old_status),
                "new_status": new_status.value,
                "reason": reason,
            },
        ))

        # 如果是死亡状态，记录到死亡列表并设置在场形式
        if new_status == CharacterStatus.DEAD:
            from app.models.character import DeathDetail, CharacterPresence

            # 设置死亡详情
            if death_detail:
                agent.character.death_detail = DeathDetail(**death_detail)
            else:
                agent.character.death_detail = DeathDetail(
                    cause=reason,
                    is_confirmed=True,
                )

            # 死亡角色可用的在场形式：回忆、闪回、尸体、被提及
            agent.character.available_presence_types = [
                CharacterPresence.MEMORY,
                CharacterPresence.FLASHBACK,
                CharacterPresence.CORPSE,
                CharacterPresence.MENTIONED,
                CharacterPresence.SPIRIT,  # 如果设定允许灵魂
            ]

            self.dead_characters.append({
                "id": character_id,
                "name": agent.character.name,
                "death_time": datetime.utcnow().isoformat(),
                "reason": reason,
                "death_detail": agent.character.death_detail.model_dump() if agent.character.death_detail else None,
            })
            self._emit_character_event(CharacterEvent(
                event_type=CharacterEvent.CHARACTER_DIED,
                character_id=character_id,
                character_name=agent.character.name,
                data={"reason": reason, "death_detail": death_detail},
            ))

        # 如果是复活状态
        elif new_status == CharacterStatus.RESURRECTED:
            from app.models.character import CharacterPresence

            # 清除死亡详情
            agent.character.death_detail = None
            # 恢复正常在场形式
            agent.character.available_presence_types = [
                CharacterPresence.PRESENT,
            ]

            self._emit_character_event(CharacterEvent(
                event_type=CharacterEvent.CHARACTER_RESURRECTED,
                character_id=character_id,
                character_name=agent.character.name,
                data={"reason": reason},
            ))

        return {
            "success": True,
            "character_id": character_id,
            "name": agent.character.name,
            "old_status": old_status.value if hasattr(old_status, 'value') else str(old_status),
            "new_status": new_status.value,
        }

    def mark_character_dead(
        self,
        character_id: str,
        reason: Optional[str] = None,
        death_chapter: Optional[str] = None,
        death_scene: Optional[str] = None,
        witnesses: Optional[List[str]] = None,
        resurrection_possible: bool = False,
    ) -> Dict[str, Any]:
        """
        标记角色死亡

        Args:
            character_id: 角色 ID
            reason: 死亡原因
            death_chapter: 死亡章节
            death_scene: 死亡场景描述
            witnesses: 目击者列表
            resurrection_possible: 是否可能复活

        Returns:
            Dict: 结果
        """
        death_detail = {
            "cause": reason,
            "death_chapter": death_chapter,
            "death_scene": death_scene,
            "witnesses": witnesses or [],
            "resurrection_possible": resurrection_possible,
        }
        return self.update_character_status(
            character_id=character_id,
            new_status=CharacterStatus.DEAD,
            reason=reason,
            death_detail=death_detail,
        )

    def resurrect_character(
        self,
        character_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        复活角色

        Args:
            character_id: 角色 ID
            reason: 复活原因

        Returns:
            Dict: 结果
        """
        if character_id not in self.character_agents:
            return {
                "success": False,
                "error": f"角色 {character_id} 不存在",
            }

        agent = self.character_agents[character_id]
        if agent.character.status != CharacterStatus.DEAD:
            return {
                "success": False,
                "error": f"角色 {agent.character.name} 未处于死亡状态",
            }

        return self.update_character_status(
            character_id=character_id,
            new_status=CharacterStatus.RESURRECTED,
            reason=reason,
        )

    def get_character_by_presence(
        self,
        presence_type: str,
    ) -> List[CharacterAgent]:
        """
        根据在场形式获取角色列表

        Args:
            presence_type: 在场形式 (present/memory/flashback/spirit/corpse/mentioned)

        Returns:
            List[CharacterAgent]: 符合条件的角色列表
        """
        from app.models.character import CharacterPresence

        try:
            presence = CharacterPresence(presence_type)
        except ValueError:
            presence = CharacterPresence.PRESENT

        result = []
        for agent in self.character_agents.values():
            if presence in agent.character.available_presence_types:
                result.append(agent)
        return result

    def get_active_character_agents(self) -> Dict[str, CharacterAgent]:
        """
        获取所有活跃状态的 CharacterAgent

        Returns:
            Dict: 活跃角色 Agent 字典
        """
        return {
            char_id: agent
            for char_id, agent in self.character_agents.items()
            if agent.character.status == CharacterStatus.ACTIVE
        }

    def get_character_agent(self, character_id: str) -> Optional[CharacterAgent]:
        """
        获取指定角色的 CharacterAgent

        Args:
            character_id: 角色 ID

        Returns:
            CharacterAgent 或 None
        """
        return self.character_agents.get(character_id)

    def register_character_event_callback(self, callback: Callable[[CharacterEvent], None]):
        """
        注册角色事件回调

        Args:
            callback: 回调函数，接收 CharacterEvent 参数
        """
        self._character_event_callbacks.append(callback)

    def _emit_character_event(self, event: CharacterEvent):
        """
        发送角色事件到所有注册的回调

        Args:
            event: 角色事件
        """
        for callback in self._character_event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"角色事件回调执行失败: {e}")

    def get_all_characters(self) -> List[Dict[str, Any]]:
        """
        获取所有角色列表

        Returns:
            List: 角色数据列表
        """
        characters = []
        for character_id, agent in self.character_agents.items():
            characters.append({
                "id": character_id,
                "name": agent.character.name,
                "description": agent.character.description,
                "role": agent.character.role,
                "status": agent.character.status.value if hasattr(agent.character.status, 'value') else agent.character.status,
                "current_location": agent.character.current_location,
            })
        return characters

    def get_character(self, character_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个角色信息

        Args:
            character_id: 角色 ID

        Returns:
            Optional[Dict]: 角色数据
        """
        agent = self.character_agents.get(character_id)
        if not agent:
            return None

        return {
            "id": character_id,
            "name": agent.character.name,
            "description": agent.character.description,
            "role": agent.character.role,
            "status": agent.character.status.value if hasattr(agent.character.status, 'value') else agent.character.status,
            "appearance": agent.character.appearance,
            "background_story": agent.character.background_story,
            "speech_pattern": agent.character.speech_pattern,
            "goals": agent.character.goals,
            "current_location": agent.character.current_location,
            "personality_traits": agent.character.personality_traits,
            "skills": agent.character.skills,
        }

    # ==================== 自动写作 ====================

    async def auto_write_chapter(
        self,
        chapter_title: str,
        chapter_goal: str,
        target_word_count: int = 2000,
        style_reference: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        自动写作完整章节

        Args:
            chapter_title: 章节标题
            chapter_goal: 章节目标/大纲
            target_word_count: 目标字数
            style_reference: 风格参考文本

        Returns:
            Dict: 包含生成的章节内容
        """
        if not self.writer:
            raise RuntimeError("导演系统未初始化")

        # 启动新章节
        await self.start_chapter(title=chapter_title, goal=chapter_goal)

        # 获取可用角色信息
        characters_info = []
        for char_id, agent in self.character_agents.items():
            characters_info.append({
                "id": char_id,
                "name": agent.character.name,
                "role": agent.character.role,
                "description": agent.character.description,
                "speech_pattern": agent.character.speech_pattern,
            })

        # 获取世界观信息
        world_info = self._build_world_payload()

        # 构建写作提示
        writing_prompt = self._build_auto_write_prompt(
            chapter_title=chapter_title,
            chapter_goal=chapter_goal,
            characters_info=characters_info,
            world_info=world_info,
            target_word_count=target_word_count,
            style_reference=style_reference,
        )

        # 调用 Writer Agent 生成章节
        result = await self.writer.execute({
            "intents": [chapter_goal],
            "environment": f"世界观：{world_info.get('name', '未知世界')}，类型：{world_info.get('world_type', '奇幻')}",
            "character_moods": {},
            "hooks": [],
            "previous_style": style_reference or "",
            "word_count": target_word_count,
            "auto_write_mode": True,
            "writing_prompt": writing_prompt,
        })

        if result.success:
            chapter_payload = result.structured_data or result.data or {}
            chapter_content = result.text_output or chapter_payload.get("chapter_content") or chapter_payload.get("content", "")
            self.current_chapter["content"] = chapter_content
            self.current_chapter["word_count"] = len(chapter_content)
            self.current_chapter["status"] = "completed"

            return {
                "success": True,
                "chapter_id": self.current_chapter["id"],
                "title": chapter_title,
                "content": chapter_content,
                "word_count": len(chapter_content),
                "goal": chapter_goal,
            }

        return {"success": False, "error": result.error}

    # ==================== 全自动运行模式 ====================

    _auto_running: bool = False
    _auto_stop_flag: bool = False

    async def start_auto_mode(
        self,
        workflow_id: str,
        chapter_count: int = 3,
        words_per_chapter: int = 2000,
        style_reference: Optional[str] = None,
        callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        outline_mode: Optional[str] = None,
        outline_ids: Optional[List[str]] = None,
        outline_chapter_numbers: Optional[List[int]] = None,
        auto_advance_outlines: bool = False,
        start_chapter_num: Optional[int] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        启动连续创作模式 - 基于工作流循环执行

        Args:
            workflow_id: 工作流ID
            chapter_count: 目标章节数
            words_per_chapter: 每章目标字数
            style_reference: 风格参考文本
            callback: 进度回调函数 (event_type, data)
            outline_mode: 大纲模式，selected 或 auto_progression
            outline_ids: 手动选择的大纲 ID 列表
            outline_chapter_numbers: 手动选择的大纲章节号列表
            auto_advance_outlines: 是否从起始大纲自动推进
            start_chapter_num: 自动推进起始章节号
            project_id: 当前项目 ID

        Returns:
            Dict: 运行结果
        """
        if self._auto_running:
            return {"success": False, "error": "自动模式已在运行中"}

        self._auto_running = True
        self._auto_stop_flag = False

        results = {
            "chapters": [],
            "total_words": 0,
            "plots_advanced": [],
            "hooks_planted": [],
            "hooks_resolved": [],
        }

        try:
            # 获取工作流定义
            from app.services.workflow_engine import get_workflow_engine
            from app.api.app import postgres_db

            engine = get_workflow_engine()
            workflow = await engine.get_workflow(workflow_id, postgres_db)

            if not workflow:
                return {"success": False, "error": f"工作流不存在: {workflow_id}"}

            active_project_id = project_id or self.project_id
            if not active_project_id:
                return {"success": False, "error": "无法获取项目ID"}

            selected_outlines: List[Any] = []
            use_outline_sequence = outline_mode in {"selected", "auto_progression"} or auto_advance_outlines

            if use_outline_sequence:
                from app.services.plot_outline_service import get_plot_outline_service

                plot_service = get_plot_outline_service()
                all_outlines = await plot_service.get_outlines_by_project(str(active_project_id))

                def outline_status(outline: Any) -> str:
                    status = getattr(outline, "status", "")
                    return getattr(status, "value", status) or ""

                writable = [
                    outline for outline in all_outlines
                    if outline_status(outline) in {"draft", "approved", "revision"}
                ]

                if outline_mode == "selected":
                    selected_id_set = {str(item) for item in (outline_ids or [])}
                    selected_chapter_set = {int(item) for item in (outline_chapter_numbers or [])}
                    selected_outlines = [
                        outline for outline in writable
                        if str(getattr(outline, "id", "")) in selected_id_set
                        or int(getattr(outline, "chapter_number", 0)) in selected_chapter_set
                    ]
                    selected_outlines.sort(key=lambda item: item.chapter_number)
                else:
                    start_num = int(start_chapter_num or 1)
                    selected_outlines = [
                        outline for outline in writable
                        if int(outline.chapter_number) >= start_num
                    ][:int(chapter_count)]

                if not selected_outlines:
                    return {"success": False, "error": "未找到可用于连续创作的章节大纲"}

                if callback:
                    callback("phase", {
                        "phase": "outline_sequence",
                        "message": f"已选择 {len(selected_outlines)} 个章节大纲，准备按大纲生成",
                    })
            else:
                # 1. 基于项目状态规划剧情
                if callback:
                    callback("phase", {"phase": "plot_planning", "message": "正在基于项目规划剧情..."})

                plot_plan = await self._plan_overall_plot(
                    chapter_count=chapter_count,
                )

                if callback:
                    callback("plot_planned", {"plan": plot_plan})

                selected_outlines = []

            # 2. 逐章执行工作流
            if selected_outlines:
                chapter_items = []
                for outline in selected_outlines:
                    outline_payload = outline.model_dump(mode="json") if hasattr(outline, "model_dump") else dict(outline)
                    chapter_items.append({
                        "chapter_num": int(outline.chapter_number),
                        "chapter_title": outline.title,
                        "chapter_goal": outline.summary or "\n".join(outline.chapter_goals or []) or "推进剧情发展",
                        "chapter_summary": outline.summary,
                        "target_word_count": outline.target_word_count or words_per_chapter,
                        "chapter_outline_id": outline.id,
                        "chapter_outline": outline_payload,
                    })
            else:
                chapter_items = []
                for chapter_num in range(1, chapter_count + 1):
                    chapter_title = f"第{chapter_num}章 {plot_plan.get('chapter_titles', [f'第{chapter_num}章'])[chapter_num - 1] if chapter_num <= len(plot_plan.get('chapter_titles', [])) else f'第{chapter_num}章'}"
                    chapter_goal = plot_plan.get("chapter_goals", ["推进剧情发展"])[chapter_num - 1] if chapter_num <= len(plot_plan.get("chapter_goals", [])) else "推进剧情发展"
                    chapter_items.append({
                        "chapter_num": chapter_num,
                        "chapter_title": chapter_title,
                        "chapter_goal": chapter_goal,
                        "target_word_count": words_per_chapter,
                        "chapter_outline_id": None,
                        "chapter_outline": None,
                    })

            for index, chapter_item in enumerate(chapter_items, start=1):
                if self._auto_stop_flag:
                    if callback:
                        callback("stopped", {"reason": "用户停止", "chapters_completed": index - 1})
                    break

                chapter_num = chapter_item["chapter_num"]
                chapter_title = chapter_item["chapter_title"]
                chapter_goal = chapter_item["chapter_goal"]
                chapter_outline_id = chapter_item.get("chapter_outline_id")
                target_word_count = chapter_item.get("target_word_count") or words_per_chapter

                if callback:
                    callback("chapter_start", {
                        "chapter_num": chapter_num,
                        "title": chapter_title,
                        "goal": chapter_goal,
                        "chapter_outline_id": chapter_outline_id,
                    })

                # 设置工作流执行上下文
                initial_context = {
                    "chapter_num": chapter_num,
                    "chapter_title": chapter_title,
                    "chapter_goal": chapter_goal,
                    "target_word_count": target_word_count,
                    "style_reference": style_reference,
                    "director_session_id": self.session_id,
                }
                if chapter_item.get("chapter_outline"):
                    initial_context.update({
                        "chapter_summary": chapter_item.get("chapter_summary", ""),
                        "chapter_outline_id": chapter_outline_id,
                        "chapter_outline": chapter_item["chapter_outline"],
                    })

                # 执行工作流
                try:
                    execution_id = await engine.execute_workflow(
                        workflow_id,
                        str(active_project_id),
                        initial_context,
                        postgres_db,
                    )

                    # 等待工作流完成（简化版：直接运行到结束）
                    execution = await engine.get_execution_state(execution_id, postgres_db)

                    if execution and execution.status == "completed":
                        # 获取工作流输出
                        chapter_content = execution.context.get("chapter_content", "")
                        word_count = len(chapter_content) if chapter_content else 0

                        if chapter_content:
                            results["chapters"].append({
                                "chapter_num": chapter_num,
                                "chapter_outline_id": chapter_outline_id,
                                "title": chapter_title,
                                "content": chapter_content,
                                "word_count": word_count,
                            })
                            results["total_words"] += word_count

                            if callback:
                                callback("chapter_completed", {
                                    "chapter_num": chapter_num,
                                    "chapter_outline_id": chapter_outline_id,
                                    "title": chapter_title,
                                    "word_count": word_count,
                                    "content": chapter_content,
                                })
                    else:
                        # 工作流执行失败，使用备用方案：直接调用 Director 方法
                        if callback:
                            callback("agent_working", {"agent": "Writer", "message": f"正在写作: {chapter_title}..."})

                        chapter_result = await self.auto_write_chapter(
                            chapter_title=chapter_title,
                            chapter_goal=chapter_goal,
                            target_word_count=target_word_count,
                            style_reference=style_reference,
                        )

                        if chapter_result.get("success"):
                            chapter_result["chapter_num"] = chapter_num
                            chapter_result["chapter_outline_id"] = chapter_outline_id
                            results["chapters"].append(chapter_result)
                            results["total_words"] += chapter_result.get("word_count", 0)

                            if callback:
                                callback("chapter_completed", {
                                    "chapter_num": chapter_num,
                                    "chapter_outline_id": chapter_outline_id,
                                    "title": chapter_title,
                                    "word_count": chapter_result.get("word_count", 0),
                                    "content": chapter_result.get("content", ""),
                                })

                except Exception as e:
                    logger.error(f"工作流执行失败: {e}")
                    if callback:
                        callback("chapter_error", {
                            "chapter_num": chapter_num,
                            "error": str(e),
                        })

                # 创建快照
                snapshot = await self.create_snapshot(
                    snapshot_type="auto_chapter",
                    branch_reason=f"连续创作 - {chapter_title}",
                )
                if callback:
                    callback("snapshot_created", {"snapshot_id": snapshot.get("id", "")})

        except Exception as e:
            logger.error(f"连续创作模式运行失败: {e}")
            if callback:
                callback("error", {"error": str(e)})
            return {"success": False, "error": str(e)}

        finally:
            self._auto_running = False
            self._auto_stop_flag = False

        if callback:
            callback("completed", {
                "total_chapters": len(results["chapters"]),
                "total_words": results["total_words"],
                "hooks_planted": len(results["hooks_planted"]),
                "hooks_resolved": len(results["hooks_resolved"]),
            })

        return {
            "success": True,
            "chapters": results["chapters"],
            "total_words": results["total_words"],
        }

    def stop_auto_mode(self):
        """停止自动运行模式"""
        self._auto_stop_flag = True

    def is_auto_running(self) -> bool:
        """检查是否正在自动运行"""
        return self._auto_running

    async def _plan_overall_plot(
        self,
        chapter_count: int,
    ) -> Dict[str, Any]:
        """
        基于项目状态规划整体剧情大纲

        Args:
            chapter_count: 章节数量

        Returns:
            Dict: 剧情规划结果
        """
        # 构建项目上下文
        project_context = self._build_project_context()

        if not self.master_plotter:
            # 如果没有 Master Plotter，返回基于项目状态的简单规划
            return {
                "chapter_titles": [f"第{i+1}章" for i in range(chapter_count)],
                "chapter_goals": [project_context.get("story_direction", "推进剧情发展") for _ in range(chapter_count)],
            }

        result = await self.master_plotter.execute({
            "task": "plan_plot",
            "chapter_count": chapter_count,
            "project_context": project_context,
            "characters": project_context.get("characters", []),
            "world_info": project_context.get("world_info", {}),
            "main_plot_progress": self.main_plot_progress,
            "current_state": {
                "hooks_planted": self.hooks_planted,
                "hooks_resolved": self.hooks_resolved,
                "current_chapter": self.current_chapter,
            },
        })

        if result.success:
            return result.data

        # 回退到简单规划
        return {
            "chapter_titles": [f"第{i+1}章" for i in range(chapter_count)],
            "chapter_goals": [project_context.get("story_direction", "推进剧情发展") for _ in range(chapter_count)],
        }

    def _build_project_context(self) -> Dict[str, Any]:
        """
        构建项目上下文，用于剧情规划

        Returns:
            Dict: 项目上下文信息
        """
        # 获取角色信息
        characters_info = []
        for char_id, agent in self.character_agents.items():
            char = agent.character
            characters_info.append({
                "id": char_id,
                "name": char.name,
                "role": char.role,
                "description": char.description or "",
                "background": char.background_story or "",
                "goals": char.goals or [],
            })

        # 获取世界观信息
        world_info = self._build_world_payload()

        # 构建故事方向
        story_direction = self._infer_story_direction(characters_info, world_info)

        return {
            "characters": characters_info,
            "world_info": world_info,
            "story_direction": story_direction,
            "regions": self.world_data.get("regions", []),
            "hooks_pending": [h for h in self.hooks_planted if h not in self.hooks_resolved],
        }

    def _infer_story_direction(
        self,
        characters_info: List[Dict[str, Any]],
        world_info: Dict[str, Any]
    ) -> str:
        """
        基于角色和世界信息推断故事发展方向

        Args:
            characters_info: 角色信息列表
            world_info: 世界观信息

        Returns:
            str: 故事方向描述
        """
        directions = []

        # 从角色目标推断
        main_char_goals = []
        for char in characters_info:
            if char.get("role") == "main" and char.get("goals"):
                main_char_goals.extend(char["goals"])

        if main_char_goals:
            directions.append(f"主角目标：{', '.join(main_char_goals[:3])}")

        # 从世界观推断
        if world_info.get("name"):
            directions.append(f"世界观：{world_info['name']}")

        if self.hooks_planted:
            pending_hooks = len(self.hooks_planted) - len(self.hooks_resolved)
            if pending_hooks > 0:
                directions.append(f"待回收伏笔：{pending_hooks} 个")

        if directions:
            return " | ".join(directions)

        return "根据当前项目状态推进剧情发展"

    def _build_auto_write_prompt(
        self,
        chapter_title: str,
        chapter_goal: str,
        characters_info: List[Dict[str, Any]],
        world_info: Dict[str, Any],
        target_word_count: int,
        style_reference: Optional[str],
    ) -> str:
        """构建自动写作提示"""
        prompt_parts = [
            f"【章节标题】\n{chapter_title}",
            f"\n【章节目标/大纲】\n{chapter_goal}",
            f"\n【目标字数】\n约 {target_word_count} 字",
        ]

        if characters_info:
            chars_text = "\n".join([
                f"- {c['name']}（{c['role']}）：{c.get('description', '无描述')}"
                for c in characters_info[:5]  # 最多显示5个主要角色
            ])
            prompt_parts.append(f"\n【主要角色】\n{chars_text}")

        if world_info:
            prompt_parts.append(f"\n【世界观】\n名称：{world_info.get('name', '未知')}")
            if world_info.get('description'):
                prompt_parts.append(f"描述：{world_info['description']}")

        if style_reference:
            prompt_parts.append(f"\n【风格参考】\n{style_reference[:500]}")

        prompt_parts.append("""
【写作要求】
1. 展示而非告知 (Show, Don't Tell)
2. 描写比例：动作 35% + 神态 35% + 对话 30%
3. 段落简短有力，便于移动端阅读
4. 使用生动的感官描写
5. 对话要符合角色性格
6. 安排适当的冲突和转折
7. 结尾要有悬念或伏笔

请生成完整的章节正文。""")

        return "\n".join(prompt_parts)
