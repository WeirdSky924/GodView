"""
工作流编排服务 - LangGraph 优先，缺失时回退到线性编排
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from app.services.director import DirectorSystem

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover
    StateGraph = None
    END = "__end__"


class WorkflowState(TypedDict, total=False):
    speaker_id: str
    context: str
    present_characters: List[str]
    intents: List[str]
    environment: str
    character_moods: Dict[str, str]
    dialogue: Dict[str, Any]
    summary: Dict[str, Any]
    hooks: Dict[str, Any]
    plot: Dict[str, Any]
    narrative: Dict[str, Any]
    evaluation: Dict[str, Any]
    snapshot: Dict[str, Any]
    steps: List[Dict[str, Any]]


class DirectorWorkflow:
    """导演工作流。支持 LangGraph，缺失时自动回退。"""

    def __init__(self, director: DirectorSystem):
        self.director = director
        self.steps: List[Dict[str, Any]] = []
        self._graph = self._build_graph() if StateGraph else None

    def supports_langgraph(self) -> bool:
        return self._graph is not None

    def describe_graph(self) -> Dict[str, Any]:
        graph_type = "langgraph" if self.supports_langgraph() else "fallback"
        return {
            "type": graph_type,
            "nodes": [
                {"id": "start", "label": "Start Session"},
                {"id": "dialogue", "label": "Character Dialogue"},
                {"id": "summary", "label": "Summarize Dialogue"},
                {"id": "hooks", "label": "Manage Hooks"},
                {"id": "plot", "label": "Advance Plot"},
                {"id": "writer", "label": "Generate Narrative"},
                {"id": "evaluate", "label": "Evaluate Chapter"},
                {"id": "snapshot", "label": "Create Snapshot"},
            ],
            "edges": [
                {"source": "start", "target": "dialogue"},
                {"source": "dialogue", "target": "summary"},
                {"source": "summary", "target": "hooks"},
                {"source": "hooks", "target": "plot"},
                {"source": "plot", "target": "writer"},
                {"source": "writer", "target": "evaluate"},
                {"source": "evaluate", "target": "snapshot"},
            ],
        }

    def _build_graph(self):
        workflow = StateGraph(WorkflowState)
        workflow.add_node("dialogue", self._dialogue_step)
        workflow.add_node("summary", self._summary_step)
        workflow.add_node("hooks", self._hooks_step)
        workflow.add_node("plot", self._plot_step)
        workflow.add_node("writer", self._writer_step)
        workflow.add_node("evaluate", self._evaluate_step)
        workflow.add_node("snapshot", self._snapshot_step)

        workflow.set_entry_point("dialogue")
        workflow.add_edge("dialogue", "summary")
        workflow.add_edge("summary", "hooks")
        workflow.add_edge("hooks", "plot")
        workflow.add_edge("plot", "writer")
        workflow.add_edge("writer", "evaluate")
        workflow.add_edge("evaluate", "snapshot")
        workflow.add_edge("snapshot", END)
        return workflow.compile()

    async def _dialogue_step(self, state: WorkflowState) -> WorkflowState:
        result = await self.director.process_dialogue_turn(
            speaker_id=state["speaker_id"],
            context=state["context"],
            present_characters=state.get("present_characters", []),
        )
        return self._append_step(state, "dialogue", result, dialogue=result)

    async def _summary_step(self, state: WorkflowState) -> WorkflowState:
        result = await self.director.summarize_dialogue(self.director.dialogue_history[-1:])
        return self._append_step(state, "summary", result, summary=result)

    async def _hooks_step(self, state: WorkflowState) -> WorkflowState:
        result = await self.director.manage_hooks()
        return self._append_step(state, "hooks", result, hooks=result)

    async def _plot_step(self, state: WorkflowState) -> WorkflowState:
        result = await self.director.advance_plot()
        return self._append_step(state, "plot", result, plot=result)

    async def _writer_step(self, state: WorkflowState) -> WorkflowState:
        result = await self.director.generate_narrative(
            intents=state.get("intents") or ["推进剧情"],
            environment=state.get("environment", ""),
            character_moods=state.get("character_moods") or {},
        )
        return self._append_step(state, "writer", result, narrative=result)

    async def _evaluate_step(self, state: WorkflowState) -> WorkflowState:
        result = await self.director.check_chapter_end()
        return self._append_step(state, "evaluate", result, evaluation=result)

    async def _snapshot_step(self, state: WorkflowState) -> WorkflowState:
        result = await self.director.create_snapshot(snapshot_type="auto")
        return self._append_step(state, "snapshot", result, snapshot=result)

    def _append_step(self, state: WorkflowState, step_name: str, result: Dict[str, Any], **extra: Any) -> WorkflowState:
        steps = list(state.get("steps", []))
        steps.append({"step": step_name, "result": result})
        next_state: WorkflowState = {**state, **extra, "steps": steps}
        return next_state

    async def run_cycle(
        self,
        speaker_id: str,
        context: str,
        present_characters: List[str],
        intents: Optional[List[str]] = None,
        environment: str = "",
        character_moods: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        initial_state: WorkflowState = {
            "speaker_id": speaker_id,
            "context": context,
            "present_characters": present_characters,
            "intents": intents or ["推进剧情"],
            "environment": environment,
            "character_moods": character_moods or {},
            "steps": [],
        }

        if self._graph:
            result = await self._graph.ainvoke(initial_state)
            self.steps = result.get("steps", [])
            return {
                "dialogue": result.get("dialogue"),
                "summary": result.get("summary"),
                "hooks": result.get("hooks"),
                "plot": result.get("plot"),
                "narrative": result.get("narrative"),
                "evaluation": result.get("evaluation"),
                "snapshot": result.get("snapshot"),
                "steps": self.steps,
                "engine": "langgraph",
            }

        dialogue = await self.director.process_dialogue_turn(
            speaker_id=speaker_id,
            context=context,
            present_characters=present_characters,
        )
        self.steps.append({"step": "dialogue", "result": dialogue})

        summary = await self.director.summarize_dialogue(self.director.dialogue_history[-1:])
        self.steps.append({"step": "summary", "result": summary})

        hooks = await self.director.manage_hooks()
        self.steps.append({"step": "hooks", "result": hooks})

        plot = await self.director.advance_plot()
        self.steps.append({"step": "plot", "result": plot})

        narrative = await self.director.generate_narrative(
            intents=intents or ["推进剧情"],
            environment=environment,
            character_moods=character_moods or {},
        )
        self.steps.append({"step": "writer", "result": narrative})

        evaluation = await self.director.check_chapter_end()
        self.steps.append({"step": "evaluate", "result": evaluation})

        snapshot = await self.director.create_snapshot(snapshot_type="auto")
        self.steps.append({"step": "snapshot", "result": snapshot})

        return {
            "dialogue": dialogue,
            "summary": summary,
            "hooks": hooks,
            "plot": plot,
            "narrative": narrative,
            "evaluation": evaluation,
            "snapshot": snapshot,
            "steps": self.steps,
            "engine": "fallback",
        }
