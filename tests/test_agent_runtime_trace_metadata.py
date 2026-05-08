import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.base import BaseAgent


class TraceProbeAgent(BaseAgent):
    AGENT_TYPE = "writer"
    DEFAULT_SCENARIO = "workflow_chapter_generation"

    def _get_default_variables(self):
        return {}

    async def execute(self, input_data):
        return None


@pytest.mark.asyncio
async def test_base_agent_stores_prompt_render_trace(monkeypatch):
    agent = TraceProbeAgent(name="TraceProbe", project_id="project-1")

    class FakePromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            assert kwargs["agent_type"] == "writer"
            assert kwargs["project_id"] == "project-1"
            assert kwargs["scenario"] == "workflow_chapter_generation"
            return {
                "content": "runtime prompt",
                "trace": {
                    "agent_type": "writer",
                    "scenario": "workflow_chapter_generation",
                    "project_id": "project-1",
                    "template_id": "writer-template",
                    "template_scenario": "workflow_chapter_generation",
                    "config_id": "config-1",
                    "prompt_ids": ["prompt-writer"],
                    "skill_ids": ["skill-long-novel"],
                    "writing_rule_ids": ["rule-long-novel"],
                    "context_blocks": [],
                    "fallbacks_used": [],
                    "deprecated_sources_used": [],
                },
            }

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakePromptService(),
    )

    await agent._ensure_system_prompt_loaded()

    assert agent.system_prompt == "runtime prompt"
    trace = agent.get_system_prompt_render_trace()
    assert trace["template_id"] == "writer-template"
    assert trace["config_id"] == "config-1"
    assert agent._get_runtime_trace_metadata()["prompt_render_trace"]["prompt_ids"] == ["prompt-writer"]


def test_runtime_trace_metadata_uses_default_scenario_when_no_trace():
    agent = TraceProbeAgent(name="TraceProbe")

    metadata = agent._get_runtime_trace_metadata()

    assert metadata["scenario"] == "workflow_chapter_generation"
    assert metadata["prompt_render_trace"] is None
