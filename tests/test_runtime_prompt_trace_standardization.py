import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.base import AgentResponse, BaseAgent
from app.models.agent_template import AgentType
from app.services.plot_outline_service import PlotOutlineService
from app.services.setting_agent_service import SegmentedContextSynthesis, SettingAgentService
from app.services.workflow_engine import WorkflowEngine


def _trace(agent_type: str, scenario: str, project_id: str = "project-1"):
    return {
        "agent_type": agent_type,
        "scenario": scenario,
        "project_id": project_id,
        "template_id": f"{agent_type}-template",
        "template_scenario": scenario,
        "config_id": None,
        "prompt_ids": [f"prompt-{agent_type}"],
        "skill_ids": ["skill-long-novel"],
        "writing_rule_ids": ["rule-long-novel"],
        "context_blocks": [],
        "fallbacks_used": [],
        "deprecated_sources_used": [],
        "missing_prompt_ids": [],
    }


@pytest.mark.asyncio
async def test_plot_outline_cached_system_prompt_preserves_render_trace(monkeypatch):
    service = PlotOutlineService()

    class FakePromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            assert kwargs["agent_type"] == "plot_outline"
            assert kwargs["project_id"] == "project-1"
            assert kwargs["scenario"] == "generate_chapter_outline"
            return {
                "content": "plot outline prompt",
                "trace": _trace("plot_outline", "generate_chapter_outline"),
            }

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakePromptService(),
    )
    async def fake_output_format_prompt():
        return "output format"

    monkeypatch.setattr(service, "_get_cached_output_format_prompt", fake_output_format_prompt)

    result = await service._get_cached_system_prompt_with_trace(
        "project-1",
        3,
        {"characters": []},
    )

    assert "plot outline prompt" in result["content"]
    assert result["trace"]["scenario"] == "generate_chapter_outline"
    assert result["trace"]["template_id"] == "plot_outline-template"


@pytest.mark.asyncio
async def test_plot_outline_prompt_service_failure_uses_md_fallback_trace(monkeypatch):
    service = PlotOutlineService()

    class BrokenPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            raise RuntimeError("template unavailable")

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: BrokenPromptService(),
    )
    monkeypatch.setattr(
        service,
        "_build_md_plot_outline_fallback_prompt",
        lambda: "md plot outline prompt",
    )

    async def fake_output_format_prompt():
        return "output format"

    monkeypatch.setattr(service, "_get_cached_output_format_prompt", fake_output_format_prompt)

    result = await service._get_cached_system_prompt_with_trace(
        "project-1",
        3,
        {"characters": []},
    )

    assert "md plot outline prompt" in result["content"]
    assert result["trace"]["fallbacks_used"] == ["plot_outline_md_prompt_fallback"]
    assert result["trace"]["deprecated_sources_used"] == []
    assert result["trace"]["missing_prompt_ids"] == []
    assert_render_trace_contract(result["trace"])


@pytest.mark.asyncio
async def test_plot_outline_prompt_service_failure_records_deprecated_minimal_fallback(monkeypatch):
    service = PlotOutlineService()

    class BrokenPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            raise RuntimeError("template unavailable")

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: BrokenPromptService(),
    )
    monkeypatch.setattr(service, "_build_md_plot_outline_fallback_prompt", lambda: "")

    async def fake_output_format_prompt():
        return "output format"

    monkeypatch.setattr(service, "_get_cached_output_format_prompt", fake_output_format_prompt)

    result = await service._get_cached_system_prompt_with_trace(
        "project-1",
        3,
        {"characters": []},
    )

    assert "deprecated 最小 fallback" in result["content"]
    assert result["trace"]["fallbacks_used"] == ["plot_outline_deprecated_minimal_system_prompt"]
    assert result["trace"]["deprecated_sources_used"] == ["PlotOutlineService._build_fallback_prompt_with_trace"]
    assert "role_plot_outline" in result["trace"]["missing_prompt_ids"]
    assert_render_trace_contract(result["trace"])


def test_plot_outline_direct_fallback_trace_distinguishes_md_and_deprecated_minimal(monkeypatch):
    service = PlotOutlineService()

    monkeypatch.setattr(service, "_build_md_plot_outline_fallback_prompt", lambda: "md plot outline prompt")
    md_result = service._build_fallback_prompt_with_trace("project-1")
    assert md_result["content"] == "md plot outline prompt"
    assert md_result["trace"]["fallbacks_used"] == ["plot_outline_md_prompt_fallback"]
    assert md_result["trace"]["deprecated_sources_used"] == []
    assert md_result["trace"]["missing_prompt_ids"] == []
    assert_render_trace_contract(md_result["trace"])

    monkeypatch.setattr(service, "_build_md_plot_outline_fallback_prompt", lambda: "")
    minimal_result = service._build_fallback_prompt_with_trace("project-1")
    assert "deprecated 最小 fallback" in minimal_result["content"]
    assert minimal_result["trace"]["fallbacks_used"] == ["plot_outline_deprecated_minimal_system_prompt"]
    assert minimal_result["trace"]["deprecated_sources_used"] == ["PlotOutlineService._build_fallback_prompt_with_trace"]
    assert minimal_result["trace"]["missing_prompt_ids"] == [
        "role_plot_outline",
        "function_plot_outline",
        "plot_outline_output",
    ]
    assert_render_trace_contract(minimal_result["trace"])


def test_writer_legacy_fallback_loads_auxiliary_md_prompt_assets(monkeypatch):
    from app.agents.director.writer import WriterAgent

    loaded_prompt_ids = []

    def fake_load(self, prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return f"content:{prompt_id}"

    monkeypatch.setattr(WriterAgent, "_load_md_prompt_content", fake_load)

    writer = WriterAgent()
    prompt = writer.system_prompt
    trace = writer.get_system_prompt_render_trace()

    assert "content:function_writer_workflow_context_binding" in prompt
    assert "content:function_writer_segment_generation" in prompt
    assert "content:function_writer_style_consistency" in prompt
    assert "content:function_writer_scene_description" in prompt
    assert "content:function_writer_character_voice_rewrite" in prompt
    assert loaded_prompt_ids == [
        "role_writer",
        "function_writing",
        "function_writer_workflow_context_binding",
        "function_writer_segment_generation",
        "function_writer_style_consistency",
        "function_writer_scene_description",
        "function_writer_character_voice_rewrite",
    ]
    assert trace["fallbacks_used"] == ["writer_legacy_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []


@pytest.mark.asyncio
async def test_writer_task_scenarios_use_runtime_prompt_builder_and_trace_contract(monkeypatch):
    from app.agents.director.writer import WriterAgent

    calls = []

    class FakePromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            calls.append(kwargs)
            scenario = kwargs["scenario"]
            return {
                "content": f"Writer runtime prompt for {scenario}",
                "trace": {
                    "agent_type": "writer",
                    "scenario": scenario,
                    "project_id": "project-1",
                    "config_id": "config-writer",
                    "template_id": "template-writer",
                    "template_scenario": scenario,
                    "prompt_ids": ["prompt-writer"],
                    "skill_ids": ["skill_long_novel_awareness"],
                    "writing_rule_ids": ["rule-long-novel"],
                    "context_blocks": ["writing_rules"],
                    "fallbacks_used": [],
                    "deprecated_sources_used": [],
                    "missing_prompt_ids": [],
                },
            }

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakePromptService(),
    )

    writer = WriterAgent(project_id="project-1")

    prompt = await writer._get_writer_config_prompt({"task_type": "chapter_generation", "chapter_num": 3})
    assert prompt == "Writer runtime prompt for workflow_chapter_generation"
    trace = writer.get_system_prompt_render_trace()
    assert trace["scenario"] == "workflow_chapter_generation"
    assert trace["skill_ids"] == ["skill_long_novel_awareness"]
    assert_render_trace_contract(trace)

    prompt = await writer._get_writer_config_prompt({"task_type": "rewrite_by_review"})
    assert prompt == "Writer runtime prompt for rewrite_by_review"
    assert writer.get_system_prompt_render_trace()["scenario"] == "rewrite_by_review"
    assert_render_trace_contract(writer.get_system_prompt_render_trace())

    prompt = await writer._get_writer_config_prompt({"task_type": "style_check"})
    assert prompt == "Writer runtime prompt for style_consistency_check"
    assert writer.get_system_prompt_render_trace()["scenario"] == "style_consistency_check"
    assert_render_trace_contract(writer.get_system_prompt_render_trace())

    assert [call["scenario"] for call in calls] == [
        "workflow_chapter_generation",
        "rewrite_by_review",
        "style_consistency_check",
    ]
    assert calls[0]["variables"]["task_type"] == "chapter_generation"
    assert calls[1]["variables"]["task_type"] == "rewrite_by_review"


@pytest.mark.asyncio
async def test_writer_prompt_service_failure_records_observable_md_fallback_trace(monkeypatch):
    from app.agents.director.writer import WriterAgent

    class BrokenPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            raise RuntimeError("template unavailable")

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: BrokenPromptService(),
    )
    monkeypatch.setattr(WriterAgent, "_build_md_writer_fallback_prompt", lambda self: "Writer md prompt")

    writer = WriterAgent(project_id="project-1")
    prompt = await writer._get_writer_config_prompt({"task_type": "chapter_generation"})

    assert prompt == "Writer md prompt"
    assert writer._writer_config_prompt_source == "md_prompt_fallback"
    trace = writer.get_system_prompt_render_trace()
    assert trace["scenario"] == "workflow_chapter_generation"
    assert trace["fallbacks_used"] == ["writer_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


@pytest.mark.asyncio
async def test_writer_missing_config_prompt_is_not_silent(monkeypatch):
    from app.agents.director.writer import WriterAgent

    class EmptyPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            return {"content": "", "trace": _trace("writer", kwargs["scenario"])}

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: EmptyPromptService(),
    )
    monkeypatch.setattr(WriterAgent, "_build_md_writer_fallback_prompt", lambda self: "")

    writer = WriterAgent(project_id="project-1")
    prompt = await writer._get_writer_config_prompt({"task_type": "character_voice_rewrite"})

    assert prompt == ""
    assert writer._writer_config_prompt_source == "missing"
    trace = writer.get_system_prompt_render_trace()
    assert trace["scenario"] == "character_voice_rewrite"
    assert trace["fallbacks_used"] == ["writer_missing_config_prompt"]
    assert trace["deprecated_sources_used"] == ["WriterAgent._build_md_writer_fallback_prompt"]
    assert "function_writer_character_voice_rewrite" in trace["missing_prompt_ids"]
    assert_render_trace_contract(trace)


@pytest.mark.asyncio
async def test_writer_segmented_generation_accepts_discussion_asset_digest(monkeypatch):
    from app.agents.director.writer import WriterAgent
    from app.models.agent_output_schemas import WriterSegmentPlanSchema

    writer = WriterAgent(project_id="project-1")

    async def fake_call_structured(schema, messages, temperature=0.0, category=None):
        assert schema is WriterSegmentPlanSchema
        assert "资产摘要" in messages[0].content
        return WriterSegmentPlanSchema(
            segments=[{"focus": "承接大纲", "key_elements": ["行动"], "tone": "紧张"}],
            overall_structure="单段",
            pacing_note="稳步推进",
        )

    monkeypatch.setattr(writer, "_call_structured", fake_call_structured)

    result = await writer._plan_segments(
        intents=["推进剧情"],
        environment="夜色",
        character_moods={"角色甲": "警惕"},
        word_count=1600,
        segment_count=1,
        chapter_num=2,
        total_chapters=100,
        world_info={"rule": "长篇慢热"},
        discussion_asset_digest="资产摘要：已确认线索",
        workflow_binding_block="绑定大纲",
        config_prompt="Writer runtime prompt",
    )

    assert result["segments"][0]["focus"] == "承接大纲"


def test_character_legacy_fallback_loads_role_performance_md_prompt_assets(monkeypatch):
    from app.agents.character_agent import CharacterAgent
    from app.models.character import Character

    loaded_prompt_ids = []

    def fake_load(self, prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return f"content:{prompt_id}"

    monkeypatch.setattr(CharacterAgent, "_load_md_prompt_content", fake_load)

    agent = CharacterAgent(Character(id="char-1", name="角色甲"))
    prompt = agent.system_prompt
    trace = agent.get_system_prompt_render_trace()

    assert "content:role_character" in prompt
    assert "content:function_character_roleplay_decision" in prompt
    assert "content:function_workflow_character_performance" in prompt
    assert "content:function_character_runtime_context_packet" in prompt
    assert "content:function_character_performance_packet" in prompt
    assert loaded_prompt_ids == [
        "role_character",
        "function_character_roleplay_decision",
        "function_workflow_character_performance",
        "function_character_runtime_context_packet",
        "function_character_performance_packet",
    ]
    assert trace["fallbacks_used"] == ["character_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


def test_scene_coordinator_legacy_fallback_loads_role_performance_md_prompt_assets(monkeypatch):
    from app.agents.scene_coordinator import SceneCoordinatorAgent

    loaded_prompt_ids = []

    def fake_load(self, prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return f"content:{prompt_id}"

    monkeypatch.setattr(SceneCoordinatorAgent, "_load_md_prompt_content", fake_load)

    agent = SceneCoordinatorAgent()
    prompt = agent.system_prompt
    trace = agent.get_system_prompt_render_trace()

    assert "content:role_scene_coordinator" in prompt
    assert "content:function_scene_coordination" in prompt
    assert "content:function_workflow_character_performance" in prompt
    assert "content:function_scene_character_context_packet" in prompt
    assert "content:function_character_performance_packet" in prompt
    assert loaded_prompt_ids == [
        "role_scene_coordinator",
        "function_scene_coordination",
        "function_workflow_scene_direction",
        "function_workflow_character_performance",
        "function_scene_character_context_packet",
        "function_character_performance_packet",
    ]
    assert trace["fallbacks_used"] == ["scene_coordinator_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


def test_summarizer_legacy_fallback_loads_performance_summary_md_prompt_assets(monkeypatch):
    from app.agents.director.summarizer import SummarizerAgent

    loaded_prompt_ids = []

    def fake_load(self, prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return f"content:{prompt_id}"

    monkeypatch.setattr(SummarizerAgent, "_load_md_prompt_content", fake_load)

    agent = SummarizerAgent()
    prompt = agent.system_prompt
    trace = agent.get_system_prompt_render_trace()

    assert "content:role_summarizer" in prompt
    assert "content:function_workflow_performance_summary" in prompt
    assert "content:function_summarizer_runtime_context_packet" in prompt
    assert loaded_prompt_ids == [
        "role_summarizer",
        "function_workflow_discussion_summary",
        "function_workflow_performance_summary",
        "function_summarizer_runtime_context_packet",
    ]
    assert trace["fallbacks_used"] == ["summarizer_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


def test_master_plotter_legacy_fallback_loads_md_prompt_assets(monkeypatch):
    from app.agents.director.master_plotter import MasterPlotterAgent

    loaded_prompt_ids = []

    def fake_load(self, prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return f"content:{prompt_id}"

    monkeypatch.setattr(MasterPlotterAgent, "_load_md_prompt_content", fake_load)

    agent = MasterPlotterAgent()
    prompt = agent.system_prompt
    trace = agent.get_system_prompt_render_trace()

    assert "content:role_master_plotter" in prompt
    assert "content:function_master_plotter_plot_planning" in prompt
    assert loaded_prompt_ids == ["role_master_plotter", "function_master_plotter_plot_planning"]
    assert trace["fallbacks_used"] == ["master_plotter_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


@pytest.mark.asyncio
async def test_master_plotter_prompt_service_failure_uses_md_fallback(monkeypatch):
    from app.agents.director.master_plotter import MasterPlotterAgent

    class BrokenPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            raise RuntimeError("template unavailable")

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: BrokenPromptService(),
    )
    monkeypatch.setattr(
        MasterPlotterAgent,
        "_load_md_prompt_content",
        lambda self, prompt_id: f"content:{prompt_id}",
    )

    agent = MasterPlotterAgent(project_id="project-1")
    prompt = await agent._get_master_plotter_config_prompt("workflow_chapter_planning")
    trace = agent.get_system_prompt_render_trace()

    assert "content:role_master_plotter" in prompt
    assert "content:function_master_plotter_chapter_writing_plan" in prompt
    assert trace["scenario"] == "workflow_chapter_planning"
    assert trace["prompt_ids"] == ["role_master_plotter", "function_master_plotter_chapter_writing_plan"]
    assert trace["fallbacks_used"] == ["master_plotter_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


def test_hook_manager_legacy_fallback_loads_md_prompt_assets(monkeypatch):
    from app.agents.director.hook_manager import HookManagerAgent

    loaded_prompt_ids = []

    def fake_load(self, prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return f"content:{prompt_id}"

    monkeypatch.setattr(HookManagerAgent, "_load_md_prompt_content", fake_load)

    agent = HookManagerAgent()
    prompt = agent.system_prompt
    trace = agent.get_system_prompt_render_trace()

    assert "content:role_hook_manager" in prompt
    assert "content:function_hook_management" in prompt
    assert loaded_prompt_ids == ["role_hook_manager", "function_hook_management"]
    assert trace["fallbacks_used"] == ["hook_manager_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


def test_event_generator_legacy_fallback_loads_md_prompt_assets(monkeypatch):
    from app.agents.event_generator import EventGeneratorAgent

    loaded_prompt_ids = []

    def fake_load(self, prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return f"content:{prompt_id}"

    monkeypatch.setattr(EventGeneratorAgent, "_load_md_prompt_content", fake_load)

    agent = EventGeneratorAgent()
    prompt = agent.system_prompt
    trace = agent.get_system_prompt_render_trace()

    assert "content:role_event_generator" in prompt
    assert "content:function_event_generation" in prompt
    assert loaded_prompt_ids == ["role_event_generator", "function_event_generation"]
    assert trace["fallbacks_used"] == ["event_generator_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


def test_procgen_legacy_fallback_loads_md_prompt_assets(monkeypatch):
    from app.agents.procgen import ProcGenAgent
    from app.models.world import World

    loaded_prompt_ids = []

    def fake_load(self, prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return f"content:{prompt_id}"

    monkeypatch.setattr(ProcGenAgent, "_load_md_prompt_content", fake_load)

    agent = ProcGenAgent(World(id="world-1", name="测试世界", world_type="都市"))
    prompt = agent.system_prompt
    trace = agent.get_system_prompt_render_trace()

    assert "content:role_proc_gen" in prompt
    assert "世界名称：测试世界" in prompt
    assert loaded_prompt_ids == ["role_proc_gen"]
    assert trace["fallbacks_used"] == ["proc_gen_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


def test_world_map_manager_legacy_fallback_loads_md_prompt_assets(monkeypatch):
    from app.agents.world_map_manager import WorldMapManagerAgent

    loaded_prompt_ids = []

    def fake_load(self, prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return f"content:{prompt_id}"

    monkeypatch.setattr(WorldMapManagerAgent, "_load_md_prompt_content", fake_load)

    agent = WorldMapManagerAgent()
    prompt = agent.system_prompt
    trace = agent.get_system_prompt_render_trace()

    assert "content:role_world_map_manager" in prompt
    assert "content:function_map_management" in prompt
    assert loaded_prompt_ids == ["role_world_map_manager", "function_map_management"]
    assert trace["fallbacks_used"] == ["world_map_manager_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


@pytest.mark.asyncio
async def test_auxiliary_prompt_service_failure_uses_md_fallback(monkeypatch):
    from app.agents.director.hook_manager import HookManagerAgent
    from app.agents.event_generator import EventGeneratorAgent
    from app.agents.world_map_manager import WorldMapManagerAgent

    class BrokenPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            raise RuntimeError("template unavailable")

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: BrokenPromptService(),
    )
    monkeypatch.setattr(HookManagerAgent, "_load_md_prompt_content", lambda self, prompt_id: f"content:{prompt_id}")
    monkeypatch.setattr(EventGeneratorAgent, "_load_md_prompt_content", lambda self, prompt_id: f"content:{prompt_id}")
    monkeypatch.setattr(WorldMapManagerAgent, "_load_md_prompt_content", lambda self, prompt_id: f"content:{prompt_id}")

    hook_agent = HookManagerAgent(project_id="project-1")
    await hook_agent._ensure_system_prompt_loaded()
    trace = hook_agent.get_system_prompt_render_trace()
    assert trace["fallbacks_used"] == ["hook_manager_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)

    event_agent = EventGeneratorAgent(project_id="project-1")
    await event_agent._ensure_system_prompt_loaded()
    trace = event_agent.get_system_prompt_render_trace()
    assert trace["fallbacks_used"] == ["event_generator_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)

    map_agent = WorldMapManagerAgent(project_id="project-1")
    await map_agent._ensure_system_prompt_loaded()
    trace = map_agent.get_system_prompt_render_trace()
    assert trace["fallbacks_used"] == ["world_map_manager_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


@pytest.mark.asyncio
async def test_auxiliary_runtime_prompts_keep_stable_hook_rules_in_md(monkeypatch):
    from app.agents.director.hook_manager import HookManagerAgent
    from app.models.agent_output_schemas import HookManagerDecisionSchema

    agent = HookManagerAgent(system_prompt="hook system")

    captured = {}

    async def fake_call_structured(schema, messages, temperature=0.0, category=None):
        assert schema is HookManagerDecisionSchema
        captured["prompt"] = messages[0].content
        return SimpleNamespace(model_dump=lambda: {"reasoning": "ok"})

    monkeypatch.setattr(agent, "_call_structured", fake_call_structured)

    result = await agent.execute(
        {
            "existing_hooks": [{"id": "hook-1", "title": "旧伏笔", "status": "hinted"}],
            "chapter_goal": "推进当前场景",
            "current_scene": "角色发现异常物件",
        }
    )

    assert result.success is True
    prompt = captured["prompt"]
    assert "【伏笔 ID 约束】" in prompt
    assert "output_schema: HookManagerDecisionSchema" in prompt
    assert "请输出 JSON 格式的决策" not in prompt
    assert "回收时机是否合适" not in prompt
    assert "新伏笔是否有明确的回收计划" not in prompt


@pytest.mark.asyncio
async def test_auxiliary_runtime_prompts_keep_summarizer_rules_in_md(monkeypatch):
    from app.agents.director.summarizer import SummarizerAgent
    from app.models.agent_output_schemas import SummarizerSettingCheckSchema, SummarizerSummarySchema

    agent = SummarizerAgent(system_prompt="summarizer system")
    captured = {}

    async def fake_call_structured(schema, messages, temperature=0.0, category=None):
        captured[schema.__name__] = messages[0].content
        if schema is SummarizerSummarySchema:
            return SimpleNamespace(model_dump=lambda: {"summary": "ok", "hook_triggers": []})
        if schema is SummarizerSettingCheckSchema:
            return SimpleNamespace(model_dump=lambda: {"consistency_status": "consistent"})
        raise AssertionError(schema)

    monkeypatch.setattr(agent, "_call_structured", fake_call_structured)
    monkeypatch.setattr(
        agent,
        "_build_setting_check_instruction",
        lambda has_chapter_content: "md setting check instruction",
    )

    summary = await agent.execute(
        {
            "dialogue_history": [{"speaker": "甲", "content": "看见旧符号"}],
            "active_hooks": [{"id": "hook-1", "title": "旧符号"}],
        }
    )
    setting_check = await agent._execute_setting_check(
        {
            "world_info": {"name": "测试世界"},
            "chapter_content": "x" * 80,
        }
    )

    assert summary.success is True
    assert setting_check.success is True
    summary_prompt = captured["SummarizerSummarySchema"]
    assert "output_schema: SummarizerSummarySchema" in summary_prompt
    assert "请将以上对话压缩成事件摘要" not in summary_prompt
    assert "不得写成所有角色已知事实" not in summary_prompt
    check_prompt = captured["SummarizerSettingCheckSchema"]
    assert "output_schema: SummarizerSettingCheckSchema" in check_prompt
    assert "请重点检查" not in check_prompt
    assert "角色能力使用是否符合设定" not in check_prompt


@pytest.mark.asyncio
async def test_auxiliary_runtime_prompts_keep_event_procgen_map_rules_in_md(monkeypatch):
    from app.agents.event_generator import EventGeneratorAgent
    from app.agents.procgen import ProcGenAgent
    from app.agents.world_map_manager import WorldMapManagerAgent
    from app.models.agent_output_schemas import (
        EventGeneratorEventSchema,
        ProcGenEncounterSchema,
        ProcGenRegionSchema,
        WorldMapOverviewSchema,
    )
    from app.models.world import Region, RegionType, World

    captured = {}

    event_agent = EventGeneratorAgent(system_prompt="event system")
    monkeypatch.setattr(
        event_agent,
        "_load_md_prompt_content",
        lambda prompt_id: "md event instruction",
    )

    async def fake_event_call(schema, messages, temperature=0.0, category=None):
        assert schema is EventGeneratorEventSchema
        captured["event"] = messages[0].content
        return SimpleNamespace(model_dump=lambda: {"event_name": "事件"})

    monkeypatch.setattr(event_agent, "_call_structured", fake_event_call)
    event_result = await event_agent.execute(
        {
            "event_type": "main",
            "context": {"chapter_num": 1, "chapter_outline": "当前章冲突"},
            "characters": ["甲"],
            "world_info": {"name": "世界", "world_type": "都市"},
        }
    )

    procgen_agent = ProcGenAgent(World(id="world-1", name="测试世界", world_type="都市"), system_prompt="proc system")

    async def fake_proc_call(schema, messages, temperature=0.0, category=None):
        if schema is ProcGenRegionSchema:
            captured["proc_region"] = messages[0].content
            return SimpleNamespace(model_dump=lambda: {"region_name": "新区", "description": "区域"})
        if schema is ProcGenEncounterSchema:
            captured["proc_encounter"] = messages[0].content
            return SimpleNamespace(model_dump=lambda: {"name": "遭遇", "description": "事件"})
        raise AssertionError(schema)

    monkeypatch.setattr(procgen_agent, "_call_structured", fake_proc_call)
    monkeypatch.setattr(procgen_agent, "_load_md_prompt_content", lambda prompt_id: "md proc instruction")
    region_result = await procgen_agent.execute(
        {
            "exploration_direction": "向东探索",
            "generation_type": "first_time",
            "existing_regions": [{"name": "旧街区"}],
        }
    )
    encounter_result = await procgen_agent.generate_encounter(
        Region(
            id="region-1",
            world_id="world-1",
            name="旧街区",
            region_type=RegionType.CITY,
            description="都市区域",
        ),
        {"characters": ["甲"]},
    )

    map_agent = WorldMapManagerAgent(system_prompt="map system")
    monkeypatch.setattr(map_agent, "_load_md_prompt_content", lambda prompt_id: "md map instruction")

    async def fake_map_call(schema, messages, temperature=0.0, category=None):
        assert schema is WorldMapOverviewSchema
        key = "map_match" if "match_or_generate_regions" in messages[0].content else "map_overview"
        captured[key] = messages[0].content
        return SimpleNamespace(model_dump=lambda: {"overview": "地图", "regions": []})

    monkeypatch.setattr(map_agent, "_call_structured", fake_map_call)
    match_result = await map_agent._match_or_generate_regions(
        {"chapter_outline": "当前章地点需求"},
        [{"name": "旧街区", "region_type": "city", "description": "已有区域"}],
    )
    overview_result = await map_agent._generate_map_overview(
        {"name": "世界", "world_type": "科幻", "plot_focus": "当前剧情"}
    )

    assert event_result.success is True
    assert region_result.success is True
    assert encounter_result.success is True
    assert match_result.success is True
    assert overview_result.success is True

    assert "output_schema: EventGeneratorEventSchema" in captured["event"]
    assert "事件必须严格贴合" not in captured["event"]
    assert "不要生成跨到后续章节" not in captured["event"]

    assert "output_schema: ProcGenRegionSchema" in captured["proc_region"]
    assert "首次探索，需要完整生成" not in captured["proc_region"]
    assert "请避免生成风格重复" not in captured["proc_region"]
    assert "output_schema: ProcGenEncounterSchema" in captured["proc_encounter"]
    assert "符合区域特色的遭遇事件" not in captured["proc_encounter"]

    assert "output_schema: WorldMapOverviewSchema" in captured["map_match"]
    assert "优先复用现有地图区域" not in captured["map_match"]
    assert "output_schema: WorldMapOverviewSchema" in captured["map_overview"]
    assert "不得默认转向奇幻地下城套路" not in captured["map_overview"]

@pytest.mark.parametrize(
    "agent_factory,expected_fallback,expected_deprecated,expected_missing",
    [
        (
            lambda: __import__("app.agents.character_agent", fromlist=["CharacterAgent"]).CharacterAgent(
                __import__("app.models.character", fromlist=["Character"]).Character(id="char-1", name="角色甲")
            ),
            "character_deprecated_minimal_system_prompt",
            "CharacterAgent._build_system_prompt",
            [
                "role_character",
                "function_character_roleplay_decision",
                "function_workflow_character_performance",
                "function_character_runtime_context_packet",
                "function_character_performance_packet",
            ],
        ),
        (
            lambda: __import__("app.agents.scene_coordinator", fromlist=["SceneCoordinatorAgent"]).SceneCoordinatorAgent(),
            "scene_coordinator_deprecated_minimal_system_prompt",
            "SceneCoordinatorAgent._build_system_prompt",
            [
                "role_scene_coordinator",
                "function_scene_coordination",
                "function_workflow_scene_direction",
                "function_workflow_character_performance",
                "function_scene_character_context_packet",
                "function_character_performance_packet",
            ],
        ),
        (
            lambda: __import__("app.agents.director.summarizer", fromlist=["SummarizerAgent"]).SummarizerAgent(),
            "summarizer_deprecated_minimal_system_prompt",
            "SummarizerAgent._build_default_system_prompt",
            [
                "role_summarizer",
                "function_workflow_discussion_summary",
                "function_workflow_performance_summary",
                "function_summarizer_runtime_context_packet",
            ],
        ),
        (
            lambda: __import__("app.agents.director.hook_manager", fromlist=["HookManagerAgent"]).HookManagerAgent(),
            "hook_manager_deprecated_minimal_system_prompt",
            "HookManagerAgent._build_default_system_prompt",
            ["role_hook_manager", "function_hook_management"],
        ),
        (
            lambda: __import__("app.agents.event_generator", fromlist=["EventGeneratorAgent"]).EventGeneratorAgent(),
            "event_generator_deprecated_minimal_system_prompt",
            "EventGeneratorAgent._build_system_prompt",
            ["role_event_generator", "function_event_generation"],
        ),
        (
            lambda: __import__("app.agents.procgen", fromlist=["ProcGenAgent"]).ProcGenAgent(
                __import__("app.models.world", fromlist=["World"]).World(id="world-1", name="测试世界", world_type="都市")
            ),
            "proc_gen_deprecated_minimal_system_prompt",
            "ProcGenAgent._build_system_prompt",
            ["role_proc_gen"],
        ),
        (
            lambda: __import__("app.agents.world_map_manager", fromlist=["WorldMapManagerAgent"]).WorldMapManagerAgent(),
            "world_map_manager_deprecated_minimal_system_prompt",
            "WorldMapManagerAgent._build_system_prompt",
            ["role_world_map_manager", "function_map_management"],
        ),
    ],
)
def test_auxiliary_deprecated_minimal_fallback_traces_missing_prompt_ids(
    monkeypatch,
    agent_factory,
    expected_fallback,
    expected_deprecated,
    expected_missing,
):
    from app.agents.character_agent import CharacterAgent
    from app.agents.scene_coordinator import SceneCoordinatorAgent
    from app.agents.director.summarizer import SummarizerAgent
    from app.agents.director.hook_manager import HookManagerAgent
    from app.agents.event_generator import EventGeneratorAgent
    from app.agents.procgen import ProcGenAgent
    from app.agents.world_map_manager import WorldMapManagerAgent

    for agent_class in (
        CharacterAgent,
        SceneCoordinatorAgent,
        SummarizerAgent,
        HookManagerAgent,
        EventGeneratorAgent,
        ProcGenAgent,
        WorldMapManagerAgent,
    ):
        monkeypatch.setattr(agent_class, "_load_md_prompt_content", lambda self, prompt_id: "")

    agent = agent_factory()
    trace = agent.get_system_prompt_render_trace()

    assert trace["fallbacks_used"] == [expected_fallback]
    assert trace["deprecated_sources_used"] == [expected_deprecated]
    assert trace["missing_prompt_ids"] == expected_missing
    assert_render_trace_contract(trace)


@pytest.mark.asyncio
async def test_base_agent_prompt_load_failure_records_deprecated_trace(monkeypatch):
    class FakeAgent(BaseAgent):
        AGENT_TYPE = "fake_agent"
        DEFAULT_SCENARIO = "fake_scenario"

        async def execute(self, input_data):
            return AgentResponse.text("ok")

        def _get_default_variables(self):
            return {}

    class BrokenPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            raise RuntimeError("template unavailable")

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: BrokenPromptService(),
    )

    agent = FakeAgent(name="Fake", project_id="project-1")
    await agent._ensure_system_prompt_loaded()
    trace = agent.get_system_prompt_render_trace()

    assert trace["agent_type"] == "fake_agent"
    assert trace["scenario"] == "fake_scenario"
    assert trace["fallbacks_used"] == ["fake_agent_deprecated_system_prompt"]
    assert trace["deprecated_sources_used"] == ["FakeAgent._build_default_system_prompt"]
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)

    service = SettingAgentService()

    class FakePromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            assert kwargs["agent_type"] == AgentType.SETTING
            assert kwargs["project_id"] == "project-1"
            assert kwargs["scenario"] == "resource_management"
            return {
                "content": "setting prompt",
                "trace": _trace(AgentType.SETTING.value, "resource_management"),
            }

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakePromptService(),
    )

    result = await service._get_setting_config_prompt_with_trace(
        "project-1",
        "resource_management",
        {"scenario": "resource_management"},
    )

    assert result["content"] == "setting prompt"
    assert result["source"] == "agent_template_runtime"
    assert result["trace"]["scenario"] == "resource_management"
    assert result["trace"]["prompt_ids"] == ["prompt-setting"]
    assert_render_trace_contract(result["trace"])


@pytest.mark.asyncio
async def test_setting_prompt_service_failure_records_observable_md_fallback_trace(monkeypatch):
    service = SettingAgentService()

    class BrokenPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            raise RuntimeError("template unavailable")

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: BrokenPromptService(),
    )
    monkeypatch.setattr(service, "_build_md_setting_fallback_prompt", lambda: "Setting md prompt")

    result = await service._get_setting_config_prompt_with_trace(
        "project-1",
        "resource_management",
        {"scenario": "resource_management"},
    )

    assert result["content"] == "Setting md prompt"
    assert result["source"] == "md_prompt_fallback"
    assert result["trace"]["scenario"] == "resource_management"
    assert result["trace"]["fallbacks_used"] == ["setting_md_prompt_fallback"]
    assert result["trace"]["deprecated_sources_used"] == []
    assert result["trace"]["missing_prompt_ids"] == []
    assert_render_trace_contract(result["trace"])


@pytest.mark.asyncio
async def test_setting_missing_config_prompt_is_not_silent(monkeypatch):
    service = SettingAgentService()

    class EmptyPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            return {"content": "", "trace": _trace(AgentType.SETTING.value, kwargs["scenario"])}

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: EmptyPromptService(),
    )
    monkeypatch.setattr(service, "_build_md_setting_fallback_prompt", lambda: "")

    result = await service._get_setting_config_prompt_with_trace(
        "project-1",
        "resource_management",
        {"scenario": "resource_management"},
    )

    assert result["content"] == ""
    assert result["source"] == "missing"
    assert result["trace"]["scenario"] == "resource_management"
    assert result["trace"]["fallbacks_used"] == ["setting_missing_config_prompt"]
    assert result["trace"]["deprecated_sources_used"] == ["SettingAgentService._build_md_setting_fallback_prompt"]
    assert "function_setting_resource_management" in result["trace"]["missing_prompt_ids"]
    assert_render_trace_contract(result["trace"])


def test_setting_segment_parser_preserves_interconnection_fields():
    service = SettingAgentService()
    response = """
说明文字
```json
[
  {
    "category": "角色关系",
    "entity": "林岚",
    "key_fact": "林岚欠青岚会一笔人情债，后续行动会受牵制",
    "relevance": "高",
    "related_entities": ["青岚会", "旧城药铺"],
    "relation_type": "depends_on",
    "potential_conflicts": ["若青岚会已被设为敌对势力，需要先提出修订草案"],
    "resource_requirements": [
      {"requirement_type":"faction","resource_name":"青岚会","severity":"blocking","reason":"需要补全势力层级和出场边界"}
    ],
  }
]
```
"""

    key_points = service._parse_segment_key_points(response)

    assert len(key_points) == 1
    assert key_points[0]["entity"] == "林岚"
    assert key_points[0]["related_entities"] == ["青岚会", "旧城药铺"]
    assert key_points[0]["relation_type"] == "depends_on"
    assert key_points[0]["potential_conflicts"] == ["若青岚会已被设为敌对势力，需要先提出修订草案"]
    assert key_points[0]["resource_requirements"] == [
        {
            "requirement_type": "faction",
            "resource_name": "青岚会",
            "severity": "blocking",
            "reason": "需要补全势力层级和出场边界",
            "suggested_payload": {},
        }
    ]


def test_setting_segment_synthesis_builds_cross_links_conflicts_and_requirements():
    service = SettingAgentService()
    key_points = [
        {
            "category": "角色",
            "entity": "林岚",
            "key_fact": "林岚需要通过旧城药铺联系青岚会",
            "relevance": "高",
            "related_entities": ["旧城药铺", "青岚会"],
            "relation_type": "depends_on",
            "potential_conflicts": ["旧城药铺若未存在，需要先补地点资源"],
            "resource_requirements": [
                {"requirement_type": "location", "resource_name": "旧城药铺", "severity": "blocking", "reason": "关键会面地点未落库"}
            ],
        },
        {
            "category": "地点",
            "entity": "旧城药铺",
            "key_fact": "旧城药铺是低层势力接头点，不应暴露终局势力核心",
            "relevance": "中",
            "related_entities": ["林岚"],
            "relation_type": "supports",
        },
    ]

    synthesis = SegmentedContextSynthesis(
        full_context="完整上下文",
        key_info_index=service._format_key_points_index(key_points),
        key_points=key_points,
        cross_segment_links=service._build_cross_segment_links(key_points),
        potential_conflicts=service._build_segment_potential_conflicts(key_points),
        resource_requirements=service._build_segment_resource_requirements(key_points),
    )
    prompt_block = synthesis.as_prompt_block()

    assert synthesis.cross_segment_links[0]["entities"] == ["林岚", "旧城药铺", "青岚会"]
    assert synthesis.potential_conflicts[0]["note"] == "旧城药铺若未存在，需要先补地点资源"
    assert synthesis.resource_requirements[0]["resource_name"] == "旧城药铺"
    assert "### 跨段关联提示" in prompt_block
    assert "### 潜在冲突提示" in prompt_block
    assert "### 资源补全提示" in prompt_block


def test_setting_lore_interconnection_payload_is_normalized_and_embedded_in_source():
    service = SettingAgentService()
    payload = service._normalize_lore_interconnection_payload({
        "title": "青岚会暗线",
        "related_characters": "林岚, 谢无咎",
        "related_factions": ["青岚会", "青岚会"],
        "depends_on_lore": "旧城规则",
        "supports_lore": {"hook": "第十二章接头伏笔"},
        "potential_conflicts": "不能提前暴露高阶势力核心",
        "usage_guidance": "只作为早期代理人线索使用",
        "resource_requirements": "青岚会势力档案",
    })
    source = service._build_lore_source_with_metadata(payload)

    assert payload["related_characters"] == ["林岚", "谢无咎"]
    assert payload["related_factions"] == ["青岚会"]
    assert payload["depends_on_lore"] == ["旧城规则"]
    assert payload["supports_lore"] == ["第十二章接头伏笔"]
    assert payload["resource_requirements"][0]["resource_name"] == "青岚会势力档案"
    assert "[setting_agent_interconnection_metadata]" in source
    assert "只作为早期代理人线索使用" in source


@pytest.mark.asyncio
async def test_workflow_config_prompt_preserves_render_trace(monkeypatch):
    engine = WorkflowEngine()

    class FakePromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            assert kwargs["agent_type"] == AgentType.CHARACTER.value
            assert kwargs["project_id"] == "project-1"
            assert kwargs["scenario"] == "workflow_character_performance"
            return {
                "content": "character workflow prompt",
                "trace": _trace(AgentType.CHARACTER.value, "workflow_character_performance"),
            }

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakePromptService(),
    )

    result = await engine._build_workflow_config_prompt_with_trace(
        AgentType.CHARACTER,
        "project-1",
        "workflow_character_performance",
        {"scenario": "workflow_character_performance"},
    )

    assert result["content"] == "character workflow prompt"
    assert result["source"] == "agent_template_runtime"
    assert result["trace"]["scenario"] == "workflow_character_performance"
    assert result["trace"]["skill_ids"] == ["skill-long-novel"]


@pytest.mark.asyncio
async def test_workflow_config_prompt_failure_uses_md_prompt_fallback(monkeypatch):
    engine = WorkflowEngine()

    class BrokenPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            raise RuntimeError("template unavailable")

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: BrokenPromptService(),
    )

    loaded_prompt_ids = []

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return {
            "content": f"content:{prompt_id}",
        }

    class FakeMdService:
        def get_prompt(self, prompt_id):
            return fake_load(prompt_id)

    monkeypatch.setattr(
        "app.services.md_file_service.get_md_file_service",
        lambda: FakeMdService(),
    )

    result = await engine._build_workflow_config_prompt_with_trace(
        AgentType.CHARACTER,
        "project-1",
        "workflow_character_performance",
        {"scenario": "workflow_character_performance"},
    )

    assert result["content"] == "content:function_workflow_character_performance"
    assert result["source"] == "md_prompt_fallback"
    assert result["trace"]["prompt_ids"] == ["function_workflow_character_performance"]
    assert result["trace"]["fallbacks_used"] == ["workflow_md_prompt_fallback"]
    assert result["trace"]["deprecated_sources_used"] == []
    assert loaded_prompt_ids == ["function_workflow_character_performance"]


@pytest.mark.asyncio
async def test_workflow_character_performance_response_preserves_config_prompt_source(monkeypatch):
    engine = WorkflowEngine()

    async def fake_prompt(*args, **kwargs):
        return {
            "content": "character workflow md fallback prompt",
            "trace": {
                **_trace(AgentType.CHARACTER.value, "workflow_character_performance"),
                "fallbacks_used": ["workflow_md_prompt_fallback"],
                "deprecated_sources_used": [],
            },
            "source": "md_prompt_fallback",
        }

    async def fake_model_response(model, prompt):
        assert "character workflow md fallback prompt" in prompt
        return "角色表演正文"

    monkeypatch.setattr(engine, "_build_workflow_config_prompt_with_trace", fake_prompt)
    monkeypatch.setattr(engine, "_get_model_response_text", fake_model_response)

    result = await engine._generate_character_performance(
        SimpleNamespace(model="fake-model"),
        {
            "name": "角色甲",
            "project_id": "project-1",
            "personality": "谨慎",
            "importance_tier": 2,
        },
        {"character_roles": {"角色甲": {"role_in_scene": "调查者"}}},
        {"project_id": "project-1"},
        [],
        False,
        1,
        1,
    )

    assert result["content"] == "角色表演正文"
    assert result["config_prompt_source"] == "md_prompt_fallback"
    assert result["prompt_render_trace"]["fallbacks_used"] == ["workflow_md_prompt_fallback"]


@pytest.mark.asyncio
async def test_workflow_character_performance_response_includes_prompt_render_trace(monkeypatch):
    engine = WorkflowEngine()

    async def fake_prompt(*args, **kwargs):
        return {
            "content": "character workflow prompt",
            "trace": _trace(AgentType.CHARACTER.value, "workflow_character_performance"),
            "source": "agent_template_runtime",
        }

    async def fake_model_response(model, prompt):
        assert "character workflow prompt" in prompt
        return "角色表演正文"

    monkeypatch.setattr(engine, "_build_workflow_config_prompt_with_trace", fake_prompt)
    monkeypatch.setattr(engine, "_get_model_response_text", fake_model_response)

    result = await engine._generate_character_performance(
        SimpleNamespace(model="fake-model"),
        {
            "name": "角色甲",
            "project_id": "project-1",
            "personality": "谨慎",
            "importance_tier": 2,
        },
        {"character_roles": {"角色甲": {"role_in_scene": "调查者"}}},
        {"project_id": "project-1"},
        [],
        False,
        1,
        1,
    )

    assert result["content"] == "角色表演正文"
    assert result["config_prompt_source"] == "agent_template_runtime"
    assert result["prompt_render_trace"]["scenario"] == "workflow_character_performance"


@pytest.mark.asyncio
async def test_workflow_plotter_opening_uses_config_prompt_trace(monkeypatch):
    engine = WorkflowEngine()

    async def fake_prompt(agent_type, project_id, scenario, variables=None):
        assert agent_type == AgentType.MASTER_PLOTTER
        assert project_id == "project-1"
        assert scenario == "workflow_discussion_opening"
        assert variables["chapter_title"] == "第一章"
        return {
            "content": "workflow opening prompt asset",
            "trace": _trace(AgentType.MASTER_PLOTTER.value, "workflow_discussion_opening"),
            "source": "md_prompt_fallback",
        }

    async def fake_model_response(model, prompt):
        assert "workflow opening prompt asset" in prompt
        assert "你是总编剧，现在召开" not in prompt
        assert "章节创作总结" not in prompt
        assert "【剧情规划进度】" in prompt
        assert "【评估反馈】" in prompt
        return "开场发言"

    monkeypatch.setattr(engine, "_build_workflow_config_prompt_with_trace", fake_prompt)
    monkeypatch.setattr(engine, "_get_model_response_text", fake_model_response)

    result = await engine._generate_plotter_opening(
        SimpleNamespace(model="fake-model"),
        "第一章",
        "当前摘要",
        "已写正文",
        [{"summary": "情节点"}],
        {"score": 7, "quality_passed": False, "issues": [{"issue": "节奏偏快"}]},
        context={"project_id": "project-1"},
    )
    assert result["content"] == "开场发言"
    assert result["config_prompt_source"] == "md_prompt_fallback"
    assert result["prompt_render_trace"]["scenario"] == "workflow_discussion_opening"


@pytest.mark.asyncio
async def test_workflow_leader_summary_uses_config_prompt_trace_and_preserves_confirmation_action(monkeypatch):
    engine = WorkflowEngine()

    async def fake_prompt(agent_type, project_id, scenario, variables=None):
        assert agent_type == AgentType.MASTER_PLOTTER
        assert project_id == "project-1"
        assert scenario == "workflow_discussion_summary"
        assert variables["chapter_title"] == "第一章"
        return {
            "content": "workflow discussion summary prompt asset",
            "trace": _trace(AgentType.MASTER_PLOTTER.value, "workflow_discussion_summary"),
            "source": "md_prompt_fallback",
        }

    async def fake_model_response(model, prompt):
        assert "workflow discussion summary prompt asset" in prompt
        assert "【讨论记录】" in prompt
        assert "【工作流角色/设定约束】" in prompt
        assert "讨论资产提案" not in prompt
        assert "最后明确询问用户" not in prompt
        return "汇总并请求确认"

    monkeypatch.setattr(engine, "_build_workflow_config_prompt_with_trace", fake_prompt)
    monkeypatch.setattr(engine, "_get_model_response_text", fake_model_response)

    result = await engine._generate_leader_summary_request(
        SimpleNamespace(model="fake-model"),
        "第一章",
        [{"agent": "评估员", "content": "节奏偏快"}],
        context={"project_id": "project-1"},
    )

    assert result["content"] == "汇总并请求确认"
    assert result["is_leader_action"] is True
    assert result["action"] == "request_confirmation"
    assert result["config_prompt_source"] == "md_prompt_fallback"
    assert result["prompt_render_trace"]["scenario"] == "workflow_discussion_summary"


@pytest.mark.asyncio
async def test_workflow_agent_opinion_uses_config_prompt_asset_without_inline_stable_rules(monkeypatch):
    engine = WorkflowEngine()

    async def fake_prompt(agent_type, project_id, scenario, variables=None):
        assert agent_type == AgentType.EVALUATOR
        assert project_id == "project-1"
        assert scenario == "workflow_agent_opinion"
        assert variables["agent_type"] == "evaluator"
        return {
            "content": "workflow agent opinion prompt asset",
            "trace": _trace(AgentType.EVALUATOR.value, "workflow_agent_opinion"),
            "source": "agent_template_runtime",
        }

    async def fake_model_response(model, prompt):
        assert "workflow agent opinion prompt asset" in prompt
        assert "【当前发言身份】" in prompt
        assert "【章节内容（用于分析）】" in prompt
        assert "【之前的讨论要点】" in prompt
        assert "不要只说“不错”" not in prompt
        assert "必须指出具体问题" not in prompt
        return "评估意见"

    monkeypatch.setattr(engine, "_build_workflow_config_prompt_with_trace", fake_prompt)
    monkeypatch.setattr(engine, "_get_model_response_text", fake_model_response)

    result = await engine._generate_agent_opinion(
        SimpleNamespace(model="fake-model"),
        "evaluator",
        "第一章",
        [{"agent": "总编剧", "content": "请聚焦节奏"}],
        "章节正文",
        {"score": 6, "issues": [{"issue": "只有对话"}], "summary": "需要加强事件"},
        ["角色甲"],
        {"project_id": "project-1", "world_info": {"name": "测试世界"}},
    )

    assert result["content"] == "评估意见"
    assert result["config_prompt_source"] == "agent_template_runtime"
    assert result["prompt_render_trace"]["scenario"] == "workflow_agent_opinion"


@pytest.mark.asyncio
async def test_workflow_performance_summary_uses_layered_material_context_and_trace(monkeypatch):
    engine = WorkflowEngine()

    async def fake_prompt(agent_type, project_id, scenario, variables=None):
        assert agent_type == AgentType.SUMMARIZER
        assert project_id == "project-1"
        assert scenario == "workflow_performance_summary"
        assert variables["public_performances"][0]["agent"] == "角色甲"
        assert variables["private_performances"][0]["intent"] == "试探"
        assert variables["relationship_deltas"][0]["source_character"] == "角色甲"
        assert variables["role_performance_gate_passed"] is False
        return {
            "content": "workflow performance summary prompt asset",
            "trace": _trace(AgentType.SUMMARIZER.value, "workflow_performance_summary"),
            "source": "md_prompt_fallback",
        }

    async def fake_model_response(model, prompt):
        assert "workflow performance summary prompt asset" in prompt
        assert "【公开角色表演内容】" in prompt
        assert "【私有表演与连续性素材】" in prompt
        assert "private_thought" in prompt
        assert "relationship_deltas" in prompt
        assert "只输出 JSON" not in prompt
        return '{"summary":"表演总结","relationship_deltas":[{"source_character":"角色甲","target_character":"角色乙","dimension":"trust","delta":-1,"reason":"隐瞒","visibility":"private"}],"state_deltas":[],"continuity_notes":["保留误会"]}'

    monkeypatch.setattr(engine, "_build_workflow_config_prompt_with_trace", fake_prompt)
    monkeypatch.setattr(engine, "_get_model_response_text", fake_model_response)

    result = await engine._generate_performance_summary(
        SimpleNamespace(model="fake-model"),
        {"main_scene": "前厅", "atmosphere": "紧张", "plot_focus": "撤离"},
        [
            {
                "agent": "角色甲",
                "public_content": "我们先走。",
                "private_thought": "不能说出计划。",
                "intent": "试探",
                "relationship_delta": [{"target_character": "角色乙", "dimension": "trust", "delta": -1}],
                "state_delta": [{"field": "emotion", "change": "警惕"}],
                "continuity_notes": ["保留误会"],
                "warnings": ["私有信息不可公开"],
            }
        ],
        project_id="project-1",
        role_performance_gate={"passed": False, "blockers": ["信息越界"], "warnings": []},
    )

    assert result["content"] == "表演总结"
    assert result["data"]["relationship_deltas"][0]["visibility"] == "private"
    assert result["config_prompt_source"] == "md_prompt_fallback"
    assert result["prompt_render_trace"]["scenario"] == "workflow_performance_summary"


@pytest.mark.asyncio
async def test_master_plotter_plot_advance_runtime_uses_advance_md_prompt(monkeypatch):
    from app.agents.director.master_plotter import MasterPlotterAgent

    agent = MasterPlotterAgent(project_id="project-1")
    loaded_prompt_ids = []

    class BrokenPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            assert kwargs["agent_type"] == AgentType.MASTER_PLOTTER.value
            assert kwargs["project_id"] == "project-1"
            assert kwargs["scenario"] == "workflow_plot_advance"
            raise RuntimeError("template unavailable")

    class FakeMdService:
        def get_prompt(self, prompt_id):
            loaded_prompt_ids.append(prompt_id)
            return {"content": f"content:{prompt_id}"}

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: BrokenPromptService(),
    )
    monkeypatch.setattr(
        "app.services.md_file_service.get_md_file_service",
        lambda: FakeMdService(),
    )

    prompt = await agent._get_master_plotter_config_prompt("workflow_plot_advance")

    assert "content:role_master_plotter" in prompt
    assert "content:function_master_plotter_advance_decision" in prompt
    assert loaded_prompt_ids == ["role_master_plotter", "function_master_plotter_advance_decision"]
    trace = agent.get_system_prompt_render_trace()
    assert trace["scenario"] == "workflow_plot_advance"
    assert trace["prompt_ids"] == ["role_master_plotter", "function_master_plotter_advance_decision"]
    assert trace["fallbacks_used"] == ["master_plotter_md_prompt_fallback"]


def test_master_plotter_task_prompt_keeps_stable_instructions_in_config_prompt():
    from app.agents.director.master_plotter import MasterPlotterAgent

    agent = MasterPlotterAgent()
    prompt = agent._build_task_prompt(
        config_prompt="配置资产中的稳定职责",
        task_title="workflow_chapter_planning",
        context_text="【绑定章节大纲】\n事实源",
        output_schema='{"writing_plan": {}}',
    )

    assert "配置资产中的稳定职责" in prompt
    assert "【调用场景】\nworkflow_chapter_planning" in prompt
    assert "【绑定章节大纲】" in prompt
    assert "【输出 JSON Schema】" in prompt
    assert "【当前任务】" not in prompt
    assert "整理上游状态，给 Writer 提供写作计划" not in prompt


@pytest.mark.asyncio
async def test_workflow_scene_direction_preserves_md_fallback_source(monkeypatch):
    engine = WorkflowEngine()

    async def fake_prompt(*args, **kwargs):
        return {
            "content": "scene direction config asset",
            "trace": {
                **_trace(AgentType.MASTER_PLOTTER.value, "workflow_scene_direction"),
                "fallbacks_used": ["workflow_md_prompt_fallback"],
            },
            "source": "md_prompt_fallback",
        }

    async def fake_model_response(model, prompt):
        assert "scene direction config asset" in prompt
        return '{"scene_type":"interactive","main_scene":"前厅","character_roles":{}}'

    monkeypatch.setattr(engine, "_build_workflow_config_prompt_with_trace", fake_prompt)
    monkeypatch.setattr(engine, "_get_model_response_text", fake_model_response)

    result = await engine._generate_scene_directions(
        SimpleNamespace(model="fake-model"),
        {
            "project_id": "project-1",
            "world_info": {"name": "测试世界"},
            "characters": [],
            "chapter_goal": "撤离",
            "plot_outline": [],
        },
    )

    assert result["config_prompt_source"] == "md_prompt_fallback"
    assert result["prompt_render_trace"]["fallbacks_used"] == ["workflow_md_prompt_fallback"]


def test_workflow_contract_normalization_preserves_agent_response_metadata():
    engine = WorkflowEngine()
    contract = engine._resolve_output_contract("plot_outline.workflow_output")
    response = AgentResponse(
        success=True,
        structured_data={"chapter_title": "测试章节"},
        metadata={
            "scenario": "generate_chapter_outline",
            "prompt_render_trace": _trace("plot_outline", "generate_chapter_outline"),
        },
    )

    normalized = engine._normalize_contract_payload(contract, response.structured_data, response=response)

    assert normalized["metadata"]["scenario"] == "generate_chapter_outline"
    assert normalized["metadata"]["prompt_render_trace"]["template_id"] == "plot_outline-template"


def test_character_runtime_user_message_keeps_task_instructions_in_prompt_assets():
    from app.agents.character_agent import CharacterAgent
    from app.models.character import Character

    agent = CharacterAgent(Character(id="char-1", name="角色甲"))
    message = agent._build_user_message(
        context="前厅撤离",
        present_characters=["角色甲", "角色乙"],
        recent_events=["警报响起"],
        dialogue_history=[],
        round_number=1,
        total_rounds=3,
        round_focus="撤离",
        is_supplement=True,
        target_word_count=120,
    )

    assert "【运行时任务参数】" in message
    assert '"scenario": "roleplay"' in message
    assert '"output_schema": "CharacterDecisionSchema"' in message
    assert "【当前任务】" not in message
    assert "根据当前角色档案和可见情境，生成下一步角色决策" not in message
    assert "只使用当前角色可知信息，输出必须符合 CharacterDecisionSchema" not in message


def test_workflow_character_tier_rules_are_prompt_asset_driven():
    engine = WorkflowEngine()

    tier_context = engine._get_character_tier_context(
        importance_tier=2,
        character_type="supporting",
        is_protagonist=False,
        is_antagonist=False,
    )
    tier_description = engine._get_character_tier_description(2, "supporting", False, False)

    assert tier_context == {
        "role_type": "major",
        "importance_tier": 2,
        "character_type": "supporting",
        "is_protagonist": False,
        "is_antagonist": False,
    }
    assert '"role_type": "major"' in tier_description
    assert "你的职责" not in tier_description
    assert "不要抢主角的风头" not in tier_description


def test_scene_coordinator_supplement_context_uses_task_parameters_not_inline_rules():
    from app.agents.scene_coordinator import SceneCoordinatorAgent

    coordinator = SceneCoordinatorAgent(project_id="project-1")
    context = coordinator._build_supplement_context(
        base_context="基础场景",
        current_content="已有内容",
        shortage=120,
        character_name="角色甲",
        plot_intents=["撤离"],
    )

    assert "【补充任务参数】" in context
    assert '"task_mode": "supplement_performance_material"' in context
    assert '"output_usage": "writer_reference_material"' in context
    assert "补充内容必须延续已有场景" not in context
    assert "只能让当前角色基于可见信息行动" not in context


@pytest.mark.asyncio
async def test_phase_4_6_character_context_packet_is_injected_and_list_fields_are_stable():
    from app.agents.character_agent import CharacterAgent
    from app.models.character import Character

    agent = CharacterAgent(Character(id="char-1", name="角色甲"))
    message = agent._build_user_message(
        context="前厅撤离",
        present_characters=["角色甲", "角色乙"],
        recent_events=["警报响起"],
        dialogue_history=[{"speaker": "角色乙", "content": "快走。", "private_thought": "不该泄露"}],
        character_context_packet={
            "visible_scene": {"main_scene": "前厅"},
            "relationship_context": [{"target": "角色乙", "trust": "下降"}],
            "forbidden_knowledge": ["角色乙的私有想法"],
        },
    )

    assert "【角色可知上下文包】" in message
    assert "前厅" in message
    assert "角色乙的私有想法" in message
    assert "private_thought" not in message

    normalized = agent._normalize_decision_packet({
        "dialogue": "先撤。",
        "perceived_facts": "现场有人受伤",
        "withheld_information": '["真实接头地点"]',
        "relationship_delta": '{"target_character":"角色乙","dimension":"trust","delta":-1}',
        "state_delta": '[{"field":"emotion","change":"警惕"}]',
        "continuity_notes": "下轮仍需撤离",
    })

    assert normalized["perceived_facts"] == ["现场有人受伤"]
    assert normalized["withheld_information"] == ["真实接头地点"]
    assert normalized["relationship_delta"][0]["target_character"] == "角色乙"
    assert normalized["state_delta"][0]["field"] == "emotion"
    assert normalized["continuity_notes"] == ["下轮仍需撤离"]



    from app.agents.scene_coordinator import SceneCoordinatorAgent

    coordinator = SceneCoordinatorAgent(project_id="project-1")
    message = coordinator._build_performance_message(
        char_name="角色甲",
        result_data={
            "dialogue": "我们先离开这里。",
            "action": "压低声音示意撤离",
            "private_thought": "不能让他们知道真正的计划。",
            "intent": "先稳住局面再观察",
            "perceived_facts": ["现场有人受伤"],
            "misinterpretations": ["以为对方已经识破自己"],
            "withheld_information": ["隐藏的接头地点"],
            "relationship_delta": [{"target_character": "角色乙", "dimension": "trust", "delta": -1}],
            "state_delta": [{"field": "emotion", "change": "警惕升高"}],
            "continuity_notes": ["下一轮仍需保留撤离意图"],
            "warnings": ["不要泄露身份"],
            "emotion": "紧张",
        },
        char_data={"importance_tier": 2},
        round_value=2,
    )
    coordinator._conversation_history = [message]

    public_history = coordinator._public_history_messages(limit=5)
    assert public_history == [
        {
            "agent": "角色甲",
            "speaker": "角色甲",
            "content": "（压低声音示意撤离） 我们先离开这里。",
            "action": "压低声音示意撤离",
            "dialogue": "我们先离开这里。",
            "emotion": "紧张",
            "round": 2,
        }
    ]
    assert "private_thought" not in public_history[0]
    assert "intent" not in public_history[0]
    assert "withheld_information" not in public_history[0]

    integrated = await coordinator._integrate_performances(
        [message],
        {"scene_type": "interactive", "main_scene": "测试场景"},
    )

    packet = integrated["scene_performance_context"]["character_performance_packets"][0]
    assert packet["character"] == "角色甲"
    assert packet["private_thought"] == "不能让他们知道真正的计划。"
    assert "private_thought" in packet["visibility"]["writer_only_fields"]
    assert integrated["public_performances"][0]["content"] == "（压低声音示意撤离） 我们先离开这里。"
    assert integrated["private_performances"][0]["intent"] == "先稳住局面再观察"


def test_phase_4_6_scene_coordinator_builds_per_character_knowledge_packet():
    from app.agents.scene_coordinator import SceneCoordinatorAgent

    coordinator = SceneCoordinatorAgent(project_id="project-1")
    coordinator._conversation_history = [
        {
            "agent": "角色乙",
            "public_content": "快走。",
            "private_thought": "我知道密道。",
            "intent": "隐瞒密道",
            "dialogue": "快走。",
        }
    ]

    packet = coordinator._build_character_context_packet(
        char_data={
            "name": "角色甲",
            "current_location": "前厅",
            "relationships": [{"target": "角色乙", "trust": "低"}],
            "status": "active",
        },
        character_plan={"previous_context": {"recent_events": ["门外有脚步声"]}},
        scene_directions={"main_scene": "前厅", "atmosphere": "紧张"},
        world_info={},
        public_history_limit=5,
        round_number=1,
        total_rounds=2,
        round_focus="撤离",
    )

    assert packet["character"] == "角色甲"
    assert packet["visible_scene"]["main_scene"] == "前厅"
    assert packet["relationship_context"][0]["target"] == "角色乙"
    assert packet["public_history"][0]["content"] == "快走。"
    assert "private_thought" not in packet["public_history"][0]
    assert "不得知道其他角色私有想法" in "；".join(packet["information_boundaries"])



    from app.agents.director.summarizer import SummarizerAgent

    summarizer = SummarizerAgent(project_id="project-1")
    user_message = summarizer._build_user_message(
        dialogue_history=[{"speaker": "角色甲", "content": "我们先离开这里。"}],
        participants=["角色甲", "角色乙"],
        context="撤离前厅",
        active_hooks=[{"id": "hook-1", "title": "失踪的钥匙"}],
        scene_performance_context={
            "public_performances": [{"agent": "角色甲", "content": "（压低声音）我们先离开这里。"}],
            "private_performances": [
                {
                    "agent": "角色甲",
                    "private_thought": "不能让他们知道真正的计划。",
                    "intent": "先稳住局面再观察",
                    "withheld_information": ["隐藏的接头地点"],
                }
            ],
            "relationship_deltas": [{"source_character": "角色甲", "target_character": "角色乙", "dimension": "trust"}],
            "state_deltas": [{"source_character": "角色甲", "field": "emotion", "change": "警惕升高"}],
            "continuity_notes": [{"source_character": "角色甲", "note": "下轮仍需撤离"}],
            "performance_warnings": ["疑似信息越界"],
        },
    )

    assert "【私有表演素材（仅供 Writer/Evaluator 参考，不得总结成场内公开事实）】" in user_message
    assert "角色甲 私有内心：不能让他们知道真正的计划。" in user_message
    assert "角色甲 下一步意图：先稳住局面再观察" in user_message
    assert "角色甲 隐瞒信息：隐藏的接头地点" in user_message
    assert "【关系/状态/连续性提案】" in user_message
    assert "【演绎素材警告】" in user_message
    assert "output_schema: SummarizerSummarySchema" in user_message


def test_phase_4_6_workflow_extracts_scene_performance_context_from_packet():
    engine = WorkflowEngine()
    performance_result = {
        "public_performances": [{"agent": "角色甲", "content": "我去探路。"}],
        "character_performance_packets": [
            {
                "character": "角色甲",
                "public_content": "我去探路。",
                "private_thought": "不能让队友知道我在试探敌人。",
                "intent": "先侦查再回报",
                "withheld_information": ["真正的敌人位置"],
                "misinterpretations": ["误以为对方已经撤退"],
            }
        ],
        "private_performances": [{"agent": "角色甲", "private_thought": "不能让队友知道我在试探敌人。"}],
        "full_content": "【角色甲】我去探路。",
        "summary": "角色甲先行侦查。",
        "scene_directions": {"main_scene": "前厅"},
    }

    extracted = engine._extract_role_performance_context(performance_result)

    assert extracted["character_performance_packets"][0]["private_thought"] == "不能让队友知道我在试探敌人。"
    assert extracted["scene_performance_context"]["character_performance_packets"][0]["withheld_information"] == ["真正的敌人位置"]
    assert extracted["last_performance_content"] == "【角色甲】我去探路。"
    assert extracted["last_scene_directions"]["main_scene"] == "前厅"


def test_phase_4_6_workflow_direct_character_performance_returns_layered_packet():
    engine = WorkflowEngine()
    result = engine._build_character_performance_packet(
        {
            "agent": "角色甲",
            "content": "我去探路。",
            "private_thought": "不能让队友知道真正计划。",
            "intent": "试探敌人",
            "relationship_delta": '{"target_character":"角色乙","dimension":"suspicion","delta":1}',
            "state_delta": '[{"field":"location","change":"进入前厅","persistence":"chapter"}]',
            "continuity_notes": "后续必须回报侦查结果",
        },
        source_character="角色甲",
    )

    assert result["character"] == "角色甲"
    assert result["public_content"] == "我去探路。"
    assert result["private_thought"] == "不能让队友知道真正计划。"
    assert result["relationship_delta"][0]["target_character"] == "角色乙"
    assert result["state_delta"][0]["field"] == "location"
    assert result["continuity_notes"] == ["后续必须回报侦查结果"]
    assert "private_thought" in result["visibility"]["writer_only_fields"]



    from app.agents.director.writer import WriterAgent
    from app.agents.evaluator import EvaluatorAgent

    scene_context = {
        "public_performances": [{"agent": "角色甲", "content": "我去探路。"}],
        "character_performance_packets": [
            {
                "character": "角色甲",
                "private_thought": "不能让队友知道我在试探敌人。",
                "intent": "先侦查再回报",
                "withheld_information": ["真正的敌人位置"],
                "misinterpretations": ["误以为对方已经撤退"],
            }
        ],
    }
    writer = WriterAgent(project_id="project-1")
    block = writer._build_workflow_binding_block(
        {
            "scene_performance_context": scene_context,
            "character_performance_packets": scene_context["character_performance_packets"],
            "relationship_deltas": [{"source_character": "角色甲", "target_character": "角色乙", "dimension": "trust", "delta": 1}],
            "state_deltas": [{"source_character": "角色甲", "field": "location", "change": "进入前厅"}],
            "continuity_notes": [{"source_character": "角色甲", "note": "离开前厅后仍需回报"}],
            "performance_warnings": [{"source_character": "角色甲", "warning": "避免暴露行踪"}],
        }
    )

    assert "场景演绎分层上下文" in block
    assert "角色表演包" in block
    assert "关系/状态/连续性变化" in block

    evaluator = EvaluatorAgent(project_id="project-1")
    fragments = evaluator._private_performance_fragments({"scene_performance_context": scene_context})
    fields = {(item["agent"], item["field"]) for item in fragments}
    values = {item["value"] for item in fragments}

    assert ("角色甲", "private_thought") in fields
    assert ("角色甲", "intent") in fields
    assert "真正的敌人位置" in values


def test_authoritative_templates_include_long_novel_skills_and_writing_rules_slots():
    from app.data.system_agent_templates import (
        DIRECTOR_HOOK_MANAGER,
        DIRECTOR_WRITER,
        EVALUATOR,
        EVENT_GENERATOR,
        PLOT_OUTLINE,
        PROC_GEN,
        WORLD_MAP_MANAGER,
    )

    templates = [
        DIRECTOR_WRITER,
        EVALUATOR,
        PLOT_OUTLINE,
        DIRECTOR_HOOK_MANAGER,
        EVENT_GENERATOR,
        WORLD_MAP_MANAGER,
        PROC_GEN,
    ]

    for template in templates:
        prompt_slots = {slot.slot_name: slot for slot in template.prompt_slots if slot.is_enabled}
        skill_ids = {slot.skill_id for slot in template.skill_slots if slot.is_enabled}

        assert "writing_rules" in prompt_slots, template.id
        assert prompt_slots["writing_rules"].prompt_template_id is None
        assert "writing_rules" in (template.default_prompt_order or []), template.id
        assert "skill_long_novel_awareness" in skill_ids, template.id


def test_auxiliary_templates_bind_authoritative_prompt_assets():
    from app.data.system_agent_templates import DIRECTOR_HOOK_MANAGER, EVENT_GENERATOR, PROC_GEN, WORLD_MAP_MANAGER

    expected_prompt_ids = {
        DIRECTOR_HOOK_MANAGER.id: {"role_hook_manager", "function_hook_management"},
        EVENT_GENERATOR.id: {"role_event_generator", "function_event_generation"},
        WORLD_MAP_MANAGER.id: {"role_world_map_manager", "function_map_management"},
        PROC_GEN.id: {"role_proc_gen"},
    }

    for template in [DIRECTOR_HOOK_MANAGER, EVENT_GENERATOR, WORLD_MAP_MANAGER, PROC_GEN]:
        bound_prompt_ids = {slot.prompt_template_id for slot in template.prompt_slots if slot.prompt_template_id}
        assert expected_prompt_ids[template.id].issubset(bound_prompt_ids), template.id


@pytest.mark.asyncio
async def test_auxiliary_runtime_builder_injects_project_writing_rules(monkeypatch):
    from app.data.system_agent_templates import DIRECTOR_HOOK_MANAGER, EVENT_GENERATOR, PROC_GEN, WORLD_MAP_MANAGER
    from app.services.agent_prompt_service import AgentPromptService

    service = AgentPromptService()
    templates_by_type = {
        "hook_manager": DIRECTOR_HOOK_MANAGER,
        "event_generator": EVENT_GENERATOR,
        "world_map_manager": WORLD_MAP_MANAGER,
        "proc_gen": PROC_GEN,
    }

    async def fake_resolve(agent_type, project_id=None, scenario=None):
        return templates_by_type[agent_type]

    async def fake_skills(*args, **kwargs):
        return {
            "content": "【Skills】\nskill_long_novel_awareness",
            "trace": {
                "skill_ids": ["skill_long_novel_awareness"],
                "fallbacks_used": [],
                "deprecated_sources_used": [],
            },
        }

    async def fake_writing_rules(project_id, context):
        return {
            "content": "【项目写作规则】\n长篇慢热规则",
            "trace": {
                "writing_rule_ids": ["rule-long-novel"],
                "fallbacks_used": [],
                "deprecated_sources_used": [],
            },
        }

    monkeypatch.setattr(service, "_resolve_template_for_agent", fake_resolve)
    monkeypatch.setattr(service, "build_skills_prompt_with_trace", fake_skills)
    monkeypatch.setattr(service, "_build_writing_rules_prompt_data", fake_writing_rules)

    for agent_type, scenario in [
        ("hook_manager", "workflow_hook_management"),
        ("event_generator", "event_generation"),
        ("world_map_manager", "world_map_management"),
        ("proc_gen", "procedural_generation"),
    ]:
        result = await service.build_agent_prompt_with_trace(
            agent_type=agent_type,
            project_id="project-1",
            variables={"scenario": scenario},
            scenario=scenario,
            context_query="长篇规则 资源边界 当前章节",
        )
        trace = result["trace"]

        assert "长篇慢热规则" in result["content"], agent_type
        assert trace["template_id"] == templates_by_type[agent_type].id
        assert trace["fallbacks_used"] == []
        assert trace["deprecated_sources_used"] == []
        assert trace["skill_ids"] == ["skill_long_novel_awareness"]
        assert trace["writing_rule_ids"] == ["rule-long-novel"]


@pytest.mark.asyncio
async def test_shared_long_novel_writing_rules_injected_for_writer_evaluator_and_plot_outline(monkeypatch):
    from app.data.system_agent_templates import DIRECTOR_WRITER, EVALUATOR, PLOT_OUTLINE
    from app.services import agent_prompt_service as agent_prompt_module
    from app.services.agent_prompt_service import AgentPromptService
    from app.services.writing_rule_rag import WritingRuleRAGService
    from app.services.writing_rule_service import WritingRuleService

    rule_service = WritingRuleService(db=None)
    rag_service = WritingRuleRAGService()
    rag_service._writing_rule_service = rule_service
    rag_service._qdrant_db = None
    monkeypatch.setattr(agent_prompt_module, "get_writing_rule_service", lambda: rule_service)
    monkeypatch.setattr(agent_prompt_module, "get_writing_rule_rag_service", lambda: rag_service)

    service = AgentPromptService()
    cases = [
        ("writer", "workflow_chapter_generation", DIRECTOR_WRITER),
        ("evaluator", "chapter_quality_review", EVALUATOR),
        ("plot_outline", "generate_chapter_outline", PLOT_OUTLINE),
    ]

    for agent_type, scenario, template in cases:
        result = await service.build_agent_prompt_with_trace(
            agent_type=agent_type,
            project_id="project-1",
            variables={"scenario": scenario, "query": "当前章节需要长篇慢热、反派层级和资源门禁"},
            scenario=scenario,
            resolved_template=template,
            include_skills=False,
            use_project_config=False,
        )
        content = result["content"]
        trace = result["trace"]

        assert "## 写作规则约束" in content
        assert "## 当前必须常驻的写作约束" in content
        assert "long_novel_slow_burn_pacing" in content
        assert "long_novel_villain_tier_progression" in content
        assert "long_novel_no_author_view_golden_finger_term" in content
        assert "本项目按长篇慢热网文处理" in content
        assert "关键危机不能靠临时发明" in content
        assert set(AgentPromptService.SHARED_LONG_NOVEL_RULE_IDS).issubset(set(trace["writing_rule_ids"]))
        assert trace["writing_rules"]["resolved_scope"]["used_baseline"] is True
        assert trace["writing_rules"]["missing_shared_long_novel_rule_ids"] == []
        assert_render_trace_contract(trace)


@pytest.mark.asyncio
async def test_shared_long_novel_rules_are_forced_when_rag_retrieval_misses(monkeypatch):
    from app.services import agent_prompt_service as agent_prompt_module
    from app.services.agent_prompt_service import AgentPromptService
    from app.services.writing_rule_service import WritingRuleService

    rule_service = WritingRuleService(db=None)

    class EmptyRagService:
        async def retrieve_for_project(self, project_id, context=None, limit=6):
            scope = await rule_service.resolve_project_rule_scope(project_id)
            return {
                "project_id": project_id,
                "query": "empty-rag",
                "resolved_scope": rule_service.describe_project_rule_scope(scope),
                "retrieved_rules": [],
                "always_rules": [],
                "rendered_guidance": "",
            }

    monkeypatch.setattr(agent_prompt_module, "get_writing_rule_service", lambda: rule_service)
    monkeypatch.setattr(agent_prompt_module, "get_writing_rule_rag_service", lambda: EmptyRagService())

    service = AgentPromptService()
    result = await service.build_writing_rules_prompt_with_trace(
        project_id="project-1",
        context={"query": "没有语义检索结果"},
        agent_type="writer",
        scenario="workflow_chapter_generation",
    )

    assert "## 共享长篇网文核心规则" in result["content"]
    assert "long_novel_chapter_event_progression" in result["content"]
    assert set(AgentPromptService.SHARED_LONG_NOVEL_RULE_IDS).issubset(set(result["trace"]["writing_rule_ids"]))
    assert set(result["trace"]["shared_long_novel_rule_ids"]) == AgentPromptService.SHARED_LONG_NOVEL_RULE_IDS
    assert result["trace"]["retrieved_rules"][0]["reason"] == "shared_long_novel_core"


@pytest.mark.asyncio
async def test_prompt_template_service_resolves_md_only_template_when_cache_is_not_empty(monkeypatch):
    from app.models.prompt_template import PromptCategory, PromptTemplate
    from app.services.prompt_template_service import PromptTemplateService

    service = PromptTemplateService()
    service._cache_valid = True
    service._templates["db_prompt"] = PromptTemplate(
        id="db_prompt",
        name="DB Prompt",
        category=PromptCategory.FUNCTION,
        content="DB content",
    )

    class FakeMdService:
        def get_prompt(self, prompt_id):
            assert prompt_id == "md_only_prompt"
            return {
                "id": prompt_id,
                "name": "MD Only Prompt",
                "category": "function",
                "content": "Hello {name}",
                "variables": [{"name": "name", "default": "reader"}],
            }

    monkeypatch.setattr(
        "app.services.md_file_service.get_md_file_service",
        lambda: FakeMdService(),
    )

    template = await service.get_template("md_only_prompt")
    assert template is not None
    assert template.id == "md_only_prompt"

    rendered = await service.render_template(
        SimpleNamespace(template_id="md_only_prompt", variables={"name": "runtime"})
    )
    assert rendered.rendered_content == "Hello runtime"


def test_md_file_service_records_scan_errors_and_stats(monkeypatch, tmp_path):
    from app.services import md_file_service as md_module
    from app.services.md_file_service import MDFileService

    monkeypatch.setattr(md_module, "PROJECT_ROOT", tmp_path)

    prompts_dir = tmp_path / "prompts"
    skills_dir = tmp_path / "skills"
    prompts_dir.mkdir()
    skills_dir.mkdir()

    (prompts_dir / "valid.md").write_text(
        "---\nid: prompt_sync_valid\nname: Valid Prompt\ncategory: function\n---\n\nPrompt body",
        encoding="utf-8",
    )
    (prompts_dir / "missing_frontmatter.md").write_text("Prompt without metadata", encoding="utf-8")
    (skills_dir / "invalid_mapping.md").write_text(
        "---\n- not\n- a\n- mapping\n---\n\nSkill body",
        encoding="utf-8",
    )

    service = MDFileService()
    service.prompts_dir = prompts_dir
    service.skills_dir = skills_dir

    prompts = service.list_prompts()
    assert [prompt["id"] for prompt in prompts] == ["prompt_sync_valid"]

    errors = service.get_scan_errors()
    assert len(errors) == 2
    assert {error["file_path"] for error in errors} == {
        "prompts/missing_frontmatter.md",
        "skills/invalid_mapping.md",
    }
    assert any("Missing YAML frontmatter" in error["error"] for error in errors)
    assert any("mapping/object" in error["error"] for error in errors)

    stats = service.get_stats()
    assert stats["prompts"]["total"] == 1
    assert stats["skills"]["total"] == 0
    assert stats["errors"] == errors


class MdSyncFakeDb:
    def __init__(self):
        self.writes = []

    async def execute_write(self, query, params=None):
        self.writes.append({"query": query, "params": params or {}})

    async def execute_query(self, query, params=None):
        return []


@pytest.mark.asyncio
async def test_prompt_md_sync_returns_file_level_results(monkeypatch, tmp_path):
    from app.services import md_file_service as md_module
    from app.services.md_file_service import MDFileService
    from app.services.prompt_template_service import PromptTemplateService

    monkeypatch.setattr(md_module, "PROJECT_ROOT", tmp_path)

    prompts_dir = tmp_path / "prompts"
    skills_dir = tmp_path / "skills"
    prompts_dir.mkdir()
    skills_dir.mkdir()

    (prompts_dir / "synced.md").write_text(
        "---\n"
        "id: prompt_file_level_sync\n"
        "name: File Level Prompt\n"
        "description: Prompt sync test\n"
        "category: function\n"
        "tags: [sync, test]\n"
        "variables:\n"
        "  - name: topic\n"
        "    default: 小说\n"
        "priority: 88\n"
        "---\n\n"
        "Prompt content for {topic}",
        encoding="utf-8",
    )
    (prompts_dir / "broken.md").write_text("---\nname: [unterminated\n---\n\nBroken", encoding="utf-8")

    md_service = MDFileService()
    md_service.prompts_dir = prompts_dir
    md_service.skills_dir = skills_dir
    monkeypatch.setattr("app.services.md_file_service.get_md_file_service", lambda: md_service)

    db = MdSyncFakeDb()
    service = PromptTemplateService(db=db)

    result = await service.sync_md_files_to_db()

    assert result["synced"] == 1
    assert result["errors"] == 1
    assert {file["status"] for file in result["files"]} == {"synced", "error"}
    synced_file = next(file for file in result["files"] if file["status"] == "synced")
    error_file = next(file for file in result["files"] if file["status"] == "error")
    assert synced_file == {
        "file_path": "prompts/synced.md",
        "id": "prompt_file_level_sync",
        "status": "synced",
        "message": "Prompt synced to database",
    }
    assert error_file["file_path"] == "prompts/broken.md"
    assert "expected" in error_file["message"] or "while parsing" in error_file["message"]

    prompt_write = db.writes[0]["params"]
    assert prompt_write["id"] == "prompt_file_level_sync"
    assert prompt_write["content"] == "Prompt content for {topic}"
    assert prompt_write["priority"] == 88


@pytest.mark.asyncio
async def test_skill_md_sync_returns_file_results_and_scenario_assignments(monkeypatch, tmp_path):
    from app.services import md_file_service as md_module
    from app.services.md_file_service import MDFileService
    from app.services.skill_service import SkillService

    monkeypatch.setattr(md_module, "PROJECT_ROOT", tmp_path)

    prompts_dir = tmp_path / "prompts"
    skills_dir = tmp_path / "skills"
    prompts_dir.mkdir()
    skills_dir.mkdir()

    (skills_dir / "synced.md").write_text(
        "---\n"
        "id: skill_file_level_sync\n"
        "name: File Level Skill\n"
        "description: Skill sync test\n"
        "skill_type: prompt\n"
        "category: writing\n"
        "applicable_agent_types: [writer, evaluator]\n"
        "applicable_scenarios: [workflow_chapter_generation, chapter_quality_review]\n"
        "priority: 77\n"
        "---\n\n"
        "Skill prompt body",
        encoding="utf-8",
    )
    (skills_dir / "broken.md").write_text("Skill without frontmatter", encoding="utf-8")

    md_service = MDFileService()
    md_service.prompts_dir = prompts_dir
    md_service.skills_dir = skills_dir
    monkeypatch.setattr("app.services.md_file_service.get_md_file_service", lambda: md_service)

    db = MdSyncFakeDb()
    service = SkillService(db=db)

    result = await service.sync_md_files_to_db()

    assert result["synced"] == 1
    assert result["errors"] == 1
    assert {file["status"] for file in result["files"]} == {"synced", "error"}
    assert next(file for file in result["files"] if file["status"] == "synced") == {
        "file_path": "skills/synced.md",
        "id": "skill_file_level_sync",
        "status": "synced",
        "message": "Skill synced to database",
    }
    error_file = next(file for file in result["files"] if file["status"] == "error")
    assert error_file["file_path"] == "skills/broken.md"
    assert "Missing YAML frontmatter" in error_file["message"]

    skill_writes = [write for write in db.writes if "INSERT INTO skills" in write["query"]]
    assignment_writes = [write for write in db.writes if "INSERT INTO skill_assignments" in write["query"]]
    assert len(skill_writes) == 1
    assert len(assignment_writes) == 4
    assert skill_writes[0]["params"]["prompt_template"] == "Skill prompt body"

    assignment_pairs = {
        (write["params"]["agent_type"], write["params"]["scenario"])
        for write in assignment_writes
    }
    assert assignment_pairs == {
        ("writer", "workflow_chapter_generation"),
        ("writer", "chapter_quality_review"),
        ("evaluator", "workflow_chapter_generation"),
        ("evaluator", "chapter_quality_review"),
    }
    assert {write["params"]["slot_name"] for write in assignment_writes} == {"writing"}
    assert {write["params"]["priority"] for write in assignment_writes} == {77}


@pytest.mark.asyncio
async def test_prompt_builder_trace_records_missing_and_raw_fallback(monkeypatch):
    from app.models.agent_config import AgentConfig
    from app.models.agent_template import AgentTemplate, AgentType, PromptSlot
    from app.models.prompt_template import PromptCategory, PromptTemplate
    from app.services.prompt_builder import PromptBuilder

    existing_template = PromptTemplate(
        id="prompt_existing",
        name="Existing",
        category=PromptCategory.FUNCTION,
        content="Existing {{available_skills}} {topic}",
    )

    class FakePromptService:
        async def get_template(self, template_id):
            if template_id == "prompt_existing":
                return existing_template
            return None

        async def render_template(self, request):
            raise RuntimeError("render failed")

    builder = PromptBuilder(prompt_template_service=FakePromptService())
    config = AgentConfig(
        id="config-1",
        project_id="project-1",
        agent_type="writer",
        scenario="workflow_chapter_generation",
        name="Writer Config",
    )
    template = AgentTemplate(
        id="template-1",
        name="Writer Template",
        agent_type=AgentType.WRITER,
        scenario="workflow_chapter_generation",
        prompt_slots=[
            PromptSlot(slot_name="main", prompt_template_id="prompt_existing", priority=100),
            PromptSlot(slot_name="missing", prompt_template_id="prompt_missing", priority=90),
        ],
        default_prompt_order=["main", "missing"],
    )

    result = await builder.build_prompt_with_trace(
        config,
        template,
        {"topic": "章节", "available_skills": "技能列表"},
    )

    assert "Existing 技能列表 章节" in result["content"]
    assert result["trace"]["prompt_ids"] == ["prompt_existing"]
    assert "prompt_template_raw:prompt_existing" in result["trace"]["fallbacks_used"]
    assert "missing_prompt_template:prompt_missing" in result["trace"]["fallbacks_used"]
    assert result["trace"]["missing_prompt_ids"] == ["prompt_missing"]


@pytest.mark.asyncio
async def test_agent_template_preview_uses_runtime_builder_without_project_config(monkeypatch):
    from app.api.routes import agent_templates as route
    from app.models.agent_template import AgentTemplate, AgentType, PromptSlot

    template = AgentTemplate(
        id="template-preview",
        name="Preview Template",
        agent_type=AgentType.WRITER,
        scenario="workflow_chapter_generation",
        prompt_slots=[PromptSlot(slot_name="main", prompt_template_id="prompt_writer")],
        default_prompt_order=["main"],
    )

    class FakeTemplateService:
        async def get_template(self, template_id):
            assert template_id == template.id
            return template

    captured = {}

    class FakeAgentPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            captured.update(kwargs)
            return {
                "content": "runtime preview prompt",
                "trace": {
                    "agent_type": "writer",
                    "scenario": "workflow_chapter_generation",
                    "project_id": "project-1",
                    "template_id": template.id,
                    "template_scenario": template.scenario,
                    "config_id": None,
                    "prompt_ids": ["prompt_writer"],
                    "skill_ids": [],
                    "writing_rule_ids": [],
                    "context_blocks": [],
                    "fallbacks_used": [],
                    "deprecated_sources_used": [],
                },
            }

    monkeypatch.setattr(route, "get_agent_template_service", lambda: FakeTemplateService())
    monkeypatch.setattr(route, "get_agent_prompt_service", lambda: FakeAgentPromptService())

    result = await route.preview_agent_template(
        template_id=template.id,
        project_id="project-1",
        variables={"topic": "章节"},
    )

    assert result["final_prompt"] == "runtime preview prompt"
    assert result["render_trace"]["template_id"] == template.id


RENDER_TRACE_REQUIRED_KEYS = {
    "agent_type",
    "scenario",
    "project_id",
    "config_id",
    "template_id",
    "template_scenario",
    "prompt_ids",
    "skill_ids",
    "writing_rule_ids",
    "context_blocks",
    "fallbacks_used",
    "deprecated_sources_used",
    "missing_prompt_ids",
}

RENDER_TRACE_LIST_KEYS = (
    "prompt_ids",
    "skill_ids",
    "writing_rule_ids",
    "context_blocks",
    "fallbacks_used",
    "deprecated_sources_used",
    "missing_prompt_ids",
)

AUDIT_REQUIRED_KEYS = {
    "template_count",
    "slot_count",
    "resolved_prompt_ids",
    "missing_prompt_ids",
    "templates",
}

AUDIT_LIST_KEYS = (
    "resolved_prompt_ids",
    "missing_prompt_ids",
    "templates",
)

AUDIT_TEMPLATE_REQUIRED_KEYS = {
    "template_id",
    "agent_type",
    "scenario",
    "prompt_ids",
    "missing_prompt_ids",
    "fallbacks_used",
    "deprecated_sources_used",
}

AUDIT_TEMPLATE_LIST_KEYS = (
    "prompt_ids",
    "missing_prompt_ids",
    "fallbacks_used",
    "deprecated_sources_used",
)


def assert_render_trace_contract(trace):
    missing = RENDER_TRACE_REQUIRED_KEYS - set(trace)
    assert not missing
    for key in RENDER_TRACE_LIST_KEYS:
        assert isinstance(trace[key], list), key


def assert_prompt_resolution_audit_contract(audit):
    missing = AUDIT_REQUIRED_KEYS - set(audit)
    assert not missing
    assert isinstance(audit["template_count"], int)
    assert isinstance(audit["slot_count"], int)
    for key in AUDIT_LIST_KEYS:
        assert isinstance(audit[key], list), key

    for template in audit["templates"]:
        missing_template_keys = AUDIT_TEMPLATE_REQUIRED_KEYS - set(template)
        assert not missing_template_keys
        assert isinstance(template["template_id"], str)
        assert isinstance(template["agent_type"], str)
        assert template["scenario"] is None or isinstance(template["scenario"], str)
        for key in AUDIT_TEMPLATE_LIST_KEYS:
            assert isinstance(template[key], list), key


@pytest.mark.asyncio
async def test_project_agent_config_preview_uses_runtime_builder_and_trace_contract(monkeypatch):
    from app.models.agent_config import AgentConfig, ModelConfig
    from app.models.agent_template import AgentTemplate, AgentType
    from app.services import agent_config_service as config_module
    from app.services.agent_config_service import AgentConfigService

    config = AgentConfig(
        id="config-preview",
        project_id="project-1",
        agent_type="writer",
        scenario="workflow_chapter_generation",
        name="Writer Config",
        template_id="template-writer",
        llm_config=ModelConfig(model_name="test-model", temperature=0.2),
    )
    template = AgentTemplate(
        id="template-writer",
        name="Writer Template",
        agent_type=AgentType.WRITER,
        scenario="workflow_chapter_generation",
    )

    service = AgentConfigService()
    service._cache_valid = True
    service._configs[config.id] = config

    class FakePromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            assert kwargs == {
                "agent_type": "writer",
                "project_id": "project-1",
                "variables": {"topic": "章节"},
                "scenario": "workflow_chapter_generation",
            }
            return {
                "content": "project config preview prompt",
                "trace": {
                    "agent_type": "writer",
                    "scenario": "workflow_chapter_generation",
                    "project_id": "project-1",
                    "config_id": config.id,
                    "template_id": template.id,
                    "template_scenario": template.scenario,
                    "prompt_ids": ["prompt_writer"],
                    "skill_ids": ["skill_long_novel_awareness"],
                    "writing_rule_ids": ["rule-long-novel"],
                    "context_blocks": ["writing_rules"],
                    "fallbacks_used": [],
                    "deprecated_sources_used": [],
                    "missing_prompt_ids": [],
                },
            }

    class FakeTemplateService:
        async def get_template(self, template_id):
            assert template_id == template.id
            return template

        async def get_template_by_type(self, agent_type, scenario):
            assert agent_type == AgentType.WRITER
            assert scenario == template.scenario
            return template

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakePromptService(),
    )
    service._agent_template_service = FakeTemplateService()

    result = await service.preview_prompt(config.id, {"topic": "章节"})

    assert result["final_prompt"] == "project config preview prompt"
    assert result["template"]["id"] == template.id
    assert result["render_trace"]["config_id"] == config.id
    assert_render_trace_contract(result["render_trace"])


@pytest.mark.asyncio
async def test_agent_prompt_service_trace_contract_includes_empty_missing_prompt_ids(monkeypatch):
    from app.models.agent_config import AgentConfig
    from app.models.agent_template import AgentTemplate, AgentType, PromptSlot
    from app.models.prompt_template import PromptCategory, PromptTemplate
    from app.services.agent_prompt_service import AgentPromptService

    template = AgentTemplate(
        id="template-writer",
        name="Writer Template",
        agent_type=AgentType.WRITER,
        scenario="workflow_chapter_generation",
        prompt_slots=[PromptSlot(slot_name="main", prompt_template_id="prompt_writer")],
        default_prompt_order=["main"],
    )
    config = AgentConfig(
        id="runtime-project-1-writer",
        project_id="project-1",
        agent_type="writer",
        scenario="workflow_chapter_generation",
        name="Writer Runtime Config",
        template_id=template.id,
    )
    prompt_template = PromptTemplate(
        id="prompt_writer",
        name="Writer Prompt",
        category=PromptCategory.FUNCTION,
        content="Write {topic}",
    )

    class FakeConfigService:
        async def resolve_agent_runtime_state(self, project_id, agent_type, scenario):
            return {"config": config, "template": template}

    class FakePromptTemplateService:
        async def get_template(self, template_id):
            assert template_id == prompt_template.id
            return prompt_template

        async def render_template(self, request):
            raise RuntimeError("force raw fallback")

    monkeypatch.setattr(
        "app.services.agent_config_service.get_agent_config_service",
        lambda: FakeConfigService(),
    )
    monkeypatch.setattr(
        "app.services.prompt_template_service.get_prompt_template_service",
        lambda: FakePromptTemplateService(),
    )
    monkeypatch.setattr(
        "app.api.routes.agent_templates.get_agent_template_service",
        lambda: SimpleNamespace(),
    )

    service = AgentPromptService()
    service.set_services(prompt_template_service=FakePromptTemplateService())
    result = await service.build_agent_prompt_with_trace(
        agent_type="writer",
        project_id="project-1",
        variables={"topic": "章节"},
        include_skills=False,
        scenario="workflow_chapter_generation",
    )

    trace = result["trace"]
    assert "Write 章节" in result["content"]
    assert trace["config_id"] == config.id
    assert trace["prompt_ids"] == ["prompt_writer"]
    assert trace["missing_prompt_ids"] == []
    assert "prompt_template_raw:prompt_writer" in trace["fallbacks_used"]
    assert_render_trace_contract(trace)


@pytest.mark.asyncio
async def test_evaluator_task_scenarios_use_runtime_prompt_builder_and_trace_contract(monkeypatch):
    from app.agents.evaluator import EvaluatorAgent

    calls = []

    class FakePromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            calls.append(kwargs)
            scenario = kwargs["scenario"]
            return {
                "content": f"Evaluator runtime prompt for {scenario}",
                "trace": {
                    "agent_type": "evaluator",
                    "scenario": scenario,
                    "project_id": "project-1",
                    "config_id": f"config-{scenario}",
                    "template_id": f"template-{scenario}",
                    "template_scenario": scenario,
                    "prompt_ids": [f"prompt-{scenario}"],
                    "skill_ids": ["skill_long_novel_awareness"],
                    "writing_rule_ids": ["rule-long-novel"],
                    "context_blocks": ["writing_rules"],
                    "fallbacks_used": [],
                    "deprecated_sources_used": [],
                    "missing_prompt_ids": [],
                },
            }

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakePromptService(),
    )

    evaluator = EvaluatorAgent(project_id="project-1")

    chapter_prompt = await evaluator._get_evaluator_config_prompt({"task_type": "chapter_end", "chapter_num": 3})
    assert "chapter_quality_review" in chapter_prompt
    assert calls[-1]["agent_type"] == "evaluator"
    assert calls[-1]["scenario"] == "chapter_quality_review"
    assert calls[-1]["variables"]["task_type"] == "chapter_end"
    assert_render_trace_contract(evaluator.get_system_prompt_render_trace())

    reader_prompt = await evaluator._get_evaluator_config_prompt({"task_type": "reader_simulate", "chapter_num": 3})
    assert "reader_simulation" in reader_prompt
    assert calls[-1]["scenario"] == "reader_simulation"
    assert calls[-1]["variables"]["task_type"] == "reader_simulate"
    assert_render_trace_contract(evaluator.get_system_prompt_render_trace())

    ooc_prompt = await evaluator._get_evaluator_config_prompt({"task_type": "ooc_review"})
    assert "ooc_information_gate" in ooc_prompt
    assert calls[-1]["scenario"] == "ooc_information_gate"
    assert calls[-1]["variables"]["task_type"] == "ooc_review"
    assert_render_trace_contract(evaluator.get_system_prompt_render_trace())


@pytest.mark.asyncio
async def test_evaluator_prompt_service_failure_records_observable_md_fallback_trace(monkeypatch):
    from app.agents.evaluator import EvaluatorAgent

    class BrokenPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            raise RuntimeError("runtime builder unavailable")

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: BrokenPromptService(),
    )
    monkeypatch.setattr(
        EvaluatorAgent,
        "_build_md_evaluator_fallback_prompt",
        lambda self: "Evaluator md fallback prompt",
    )

    evaluator = EvaluatorAgent(project_id="project-1")
    prompt = await evaluator._get_evaluator_config_prompt({"task_type": "reader_simulate"})

    trace = evaluator.get_system_prompt_render_trace()
    assert prompt == "Evaluator md fallback prompt"
    assert trace["agent_type"] == "evaluator"
    assert trace["scenario"] == "reader_simulation"
    assert trace["fallbacks_used"] == ["evaluator_md_prompt_fallback"]
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


@pytest.mark.asyncio
async def test_evaluator_missing_config_prompt_is_not_silent(monkeypatch):
    from app.agents.evaluator import EvaluatorAgent

    class EmptyPromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            return {"content": "", "trace": {}}

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: EmptyPromptService(),
    )
    monkeypatch.setattr(EvaluatorAgent, "_build_md_evaluator_fallback_prompt", lambda self: "")

    evaluator = EvaluatorAgent(project_id="project-1")
    prompt = await evaluator._get_evaluator_config_prompt({"task_type": "ooc_review"})

    trace = evaluator.get_system_prompt_render_trace()
    assert prompt == ""
    assert trace["scenario"] == "ooc_information_gate"
    assert trace["fallbacks_used"] == ["evaluator_missing_config_prompt"]
    assert trace["deprecated_sources_used"] == ["EvaluatorAgent._build_md_evaluator_fallback_prompt"]
    assert "function_evaluator_ooc_review" in trace["missing_prompt_ids"]
    assert_render_trace_contract(trace)


@pytest.mark.asyncio
async def test_evaluator_deterministic_role_performance_gate_survives_prompt_migration(monkeypatch):
    from app.agents.evaluator import EvaluatorAgent
    from app.models.agent_output_schemas import EvaluatorChapterEndSchema

    class FakePromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            return {
                "content": "Evaluator runtime prompt",
                "trace": {
                    "agent_type": "evaluator",
                    "scenario": kwargs["scenario"],
                    "project_id": "project-1",
                    "config_id": "config-evaluator",
                    "template_id": "template-evaluator",
                    "template_scenario": kwargs["scenario"],
                    "prompt_ids": ["prompt-evaluator"],
                    "skill_ids": ["skill_long_novel_awareness"],
                    "writing_rule_ids": ["rule-long-novel"],
                    "context_blocks": ["writing_rules"],
                    "fallbacks_used": [],
                    "deprecated_sources_used": [],
                    "missing_prompt_ids": [],
                },
            }

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakePromptService(),
    )

    evaluator = EvaluatorAgent(project_id="project-1")

    async def fake_call_structured(schema, messages, temperature=0.0, category=None):
        assert schema is EvaluatorChapterEndSchema
        assert "Evaluator runtime prompt" in messages[0].content
        return EvaluatorChapterEndSchema(
            should_end=True,
            quality_passed=True,
            score=8.0,
            reason="基础质量通过",
            issues=[],
            suggestions=[],
            pacing_check={"is_appropriate": True, "note": "节奏可接受"},
            long_term_check={"has_room_for_future": True, "note": "仍保留后续空间"},
            world_consistency_check={"is_consistent": True, "issues": []},
            scores={
                "info_gain": 8.0,
                "suspense": 7.0,
                "pacing": 8.0,
                "completeness": 8.0,
                "world_consistency": 8.0,
            },
        )

    monkeypatch.setattr(evaluator, "_call_structured", fake_call_structured)

    result = await evaluator.execute(
        {
            "task_type": "chapter_end",
            "chapter_content": "正文直接写出：不能让队友知道我在试探敌人。",
            "scene_performance_context": {
                "character_performance_packets": [
                    {"character": "角色甲", "private_thought": "不能让队友知道我在试探敌人。"}
                ]
            },
        }
    )

    assert result.success is True
    data = result.structured_data
    assert data["quality_passed"] is False
    assert data["should_end"] is False
    assert any("正文采纳了角色私有演绎素材" in issue for issue in data["issues"])
    assert data["role_performance_gate_check"]["passed"] is False
    assert_render_trace_contract(result.metadata["prompt_render_trace"])


@pytest.mark.asyncio
async def test_system_agent_template_prompt_resolution_audit_reports_missing_and_resolved(monkeypatch):
    from app.models.agent_template import AgentTemplate, AgentType, PromptSlot
    from app.models.prompt_template import PromptCategory, PromptTemplate
    from app.services.agent_prompt_service import AgentPromptService
    import app.services.agent_prompt_service as prompt_module

    template = AgentTemplate(
        id="audit-template",
        name="Audit Template",
        agent_type=AgentType.WRITER,
        scenario="workflow_chapter_generation",
        prompt_slots=[
            PromptSlot(slot_name="main", prompt_template_id="prompt_existing", priority=100),
            PromptSlot(slot_name="missing", prompt_template_id="prompt_missing", priority=90),
            PromptSlot(slot_name="rules", priority=80),
        ],
    )
    prompt_template = PromptTemplate(
        id="prompt_existing",
        name="Existing Prompt",
        category=PromptCategory.FUNCTION,
        content="Existing",
    )

    service = AgentPromptService()

    async def fake_get_prompt_template(prompt_id):
        if prompt_id == prompt_template.id:
            return prompt_template
        return None

    monkeypatch.setattr(prompt_module, "SYSTEM_AGENT_TEMPLATES", [template])
    monkeypatch.setattr(service, "get_prompt_template", fake_get_prompt_template)

    audit = await service.audit_system_agent_template_prompt_resolution()

    assert_prompt_resolution_audit_contract(audit)
    assert audit["template_count"] == 1
    assert audit["slot_count"] == 2
    assert audit["resolved_prompt_ids"] == ["prompt_existing"]
    assert audit["missing_prompt_ids"] == ["prompt_missing"]
    assert audit["templates"][0]["prompt_ids"] == ["prompt_existing"]
    assert audit["templates"][0]["missing_prompt_ids"] == ["prompt_missing"]
    assert audit["templates"][0]["fallbacks_used"] == ["missing_prompt_template:prompt_missing"]


@pytest.mark.asyncio
async def test_prompt_audit_route_uses_non_llm_agent_prompt_service(monkeypatch):
    from app.api.routes import prompts as route

    class FakeAgentPromptService:
        async def audit_system_agent_template_prompt_resolution(self):
            return {
                "template_count": 1,
                "slot_count": 1,
                "resolved_prompt_ids": ["prompt_existing"],
                "missing_prompt_ids": [],
                "templates": [],
            }

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakeAgentPromptService(),
    )

    result = await route.audit_agent_template_prompt_resolution()

    assert_prompt_resolution_audit_contract(result)
    assert result["template_count"] == 1
    assert result["resolved_prompt_ids"] == ["prompt_existing"]


def test_prompt_audit_api_route_smoke_uses_non_llm_agent_prompt_service(monkeypatch):
    from app.api.app import create_app

    class FakeAgentPromptService:
        async def audit_system_agent_template_prompt_resolution(self):
            return {
                "template_count": 1,
                "slot_count": 2,
                "resolved_prompt_ids": ["prompt_existing"],
                "missing_prompt_ids": ["prompt_missing"],
                "templates": [
                    {
                        "template_id": "template-writer",
                        "agent_type": "writer",
                        "scenario": "workflow_chapter_generation",
                        "prompt_ids": ["prompt_existing"],
                        "missing_prompt_ids": ["prompt_missing"],
                        "fallbacks_used": ["missing_prompt_template:prompt_missing"],
                        "deprecated_sources_used": [],
                    }
                ],
            }

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakeAgentPromptService(),
    )

    client = TestClient(create_app())
    response = client.get("/api/prompts/audit/agent-template-resolution")

    assert response.status_code == 200
    result = response.json()
    assert_prompt_resolution_audit_contract(result)
    assert result["template_count"] == 1
    assert result["slot_count"] == 2
    assert result["resolved_prompt_ids"] == ["prompt_existing"]
    assert result["missing_prompt_ids"] == ["prompt_missing"]
    assert result["templates"][0]["fallbacks_used"] == ["missing_prompt_template:prompt_missing"]
