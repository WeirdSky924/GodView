import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.agent_config import AgentConfig, ModelConfig
from app.services.agent_config_service import AgentConfigService


@pytest.mark.asyncio
async def test_preview_prompt_exposes_unified_render_trace(monkeypatch):
    config = AgentConfig(
        id="config-1",
        project_id="project-1",
        agent_type="writer",
        scenario="workflow_chapter_generation",
        name="Writer runtime config",
        description="",
        template_id="template-1",
        is_custom=False,
        slot_overrides=[],
        custom_prompt_order=None,
        llm_config=ModelConfig(model_name="test-model", temperature=0.2),
        is_active=True,
        version="1.0.0",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    service = AgentConfigService()

    async def fake_get_config(config_id):
        assert config_id == config.id
        return config

    async def fake_get_final_prompt_with_trace(config_id, variables=None):
        assert config_id == config.id
        assert variables == {"chapter_num": 3}
        return {
            "content": "final prompt",
            "trace": {
                "agent_type": "writer",
                "scenario": "workflow_chapter_generation",
                "project_id": "project-1",
                "template_id": "template-1",
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

    monkeypatch.setattr(service, "get_config", fake_get_config)
    monkeypatch.setattr(service, "get_final_prompt_with_trace", fake_get_final_prompt_with_trace)

    result = await service.preview_prompt(config.id, {"chapter_num": 3})

    assert result["final_prompt"] == "final prompt"
    assert result["prompt_length"] == len("final prompt")
    assert result["render_trace"]["template_id"] == "template-1"
    assert result["render_trace"]["config_id"] == "config-1"
    assert result["render_trace"]["prompt_ids"] == ["prompt-writer"]
    assert result["render_trace"]["skill_ids"] == ["skill-long-novel"]
    assert result["render_trace"]["writing_rule_ids"] == ["rule-long-novel"]
