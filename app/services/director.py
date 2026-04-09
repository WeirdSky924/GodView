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
from app.models.character import Character
from app.models.world import World
# Removed to fix circular import: DirectorWorkflow will be imported lazily
# from app.services.workflow import DirectorWorkflow

logger = logging.getLogger(__name__)


class DirectorSystem:
    """导演系统 - orchestrates all agents for novel generation"""

    def __init__(self, world_data: Dict[str, Any], config: Optional[Dict[str, Any]] = None, project_id: Optional[str] = None):
        self.world_id = world_data.get("id", str(uuid.uuid4()))
        self.world_data = world_data
        self.config = config or {}
        self.project_id = project_id  # v7: 用于加载 prompt 模板

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
        chapter_id = f"chapter_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

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
            for hook_info in decisions.get("hooks_to_plant", []):
                await self._plant_hook(hook_info)
            for hook_info in decisions.get("hooks_to_resolve", []):
                await self._resolve_hook(hook_info)
            self.state_machine["phase"] = "hooks_managed"
            return decisions
        return {"success": False, "error": result.error}

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
            narrative = result.data
            narrative_voice_review = await self._review_narrative_voice(
                narrative.get("content", ""),
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
        snapshot_id = f"snapshot_{uuid.uuid4().hex[:12]}"
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
            "id": f"intervention_{uuid.uuid4().hex[:12]}",
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
        character = char_data if isinstance(char_data, Character) else Character(**char_data)
        return CharacterAgent(character=character, model=model, project_id=self.project_id)

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
                vector_hits = await qdrant_db.get_similar_voice_samples_by_text(
                    query_text=query_text,
                    character_id=agent.character.id,
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

        rewritten_text = rewrite.data.get("rewritten_text", "").strip()
        if not rewritten_text:
            return None

        second_review = await self._review_character_voice(agent, rewritten_text)
        return {
            "dialogue": rewritten_text,
            "voice_review": second_review,
            "rewrite_result": {
                "applied": True,
                "changes_made": rewrite.data.get("changes_made", []),
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

        rewritten_text = rewrite.data.get("rewritten_text", "").strip()
        if not rewritten_text:
            return None

        second_review = await self._review_narrative_voice(rewritten_text, {character_id: "rewritten"}, "")
        return {
            "content": rewritten_text,
            "voice_review": second_review,
            "rewrite_result": {
                "applied": True,
                "changes_made": rewrite.data.get("changes_made", []),
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

    async def _get_pending_hooks(self) -> List[str]:
        return [hook for hook in self.hooks_planted if hook not in self.hooks_resolved]

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
        hook_id = hook_info.get("id") or hook_info.get("title") or f"hook_{len(self.hooks_planted)}"
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
            character_id = f"char_{uuid.uuid4().hex[:12]}"
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
