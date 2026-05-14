import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.base import AgentResponse, BaseAgent
from app.models.agent_template import AgentType
from app.models.intervention import InterventionType
from app.services.agent_communication import AgentCommunicationService
from app.services.character_detection import CharacterPromotionManager
from app.services.collaborator import CollaborationRequest, CollaborationRole, CollaboratorSystem
from app.services.plot_outline_service import PlotOutlineService
from app.services.setting_agent import SettingAgent
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
async def test_plot_outline_approved_update_creates_revision_proposal(monkeypatch):
    from app.models.chapter_outline import ChapterOutline, ChapterOutlineStatus, UpdateChapterOutlineDTO

    service = PlotOutlineService()
    approved = ChapterOutline(
        id="outline-approved",
        project_id="project-1",
        chapter_number=3,
        title="原审批标题",
        summary="原审批摘要",
        status=ChapterOutlineStatus.APPROVED,
        chapter_goals=["原目标"],
    )
    service._outlines_cache[approved.id] = approved
    writes = []

    class FakeDB:
        async def execute_write(self, query, params=None):
            writes.append((query, dict(params or {})))
            return 1

    service._db = FakeDB()
    monkeypatch.setattr(service, "_persist_outline_resource_audit", AsyncMock())

    revision = await service.update_outline(
        approved.id,
        UpdateChapterOutlineDTO(title="修订标题", summary="修订摘要"),
    )

    assert revision is not None
    assert revision.id != approved.id
    assert revision.previous_outline_id == approved.id
    assert revision.status == ChapterOutlineStatus.REVISION
    assert revision.approved_at is None
    assert revision.approved_by is None
    assert revision.title == "修订标题"
    assert revision.summary == "修订摘要"
    assert approved.title == "原审批标题"
    assert approved.summary == "原审批摘要"
    assert service._outlines_cache[approved.id] is approved
    assert service._outlines_cache[revision.id] is revision
    assert writes[0][1]["status"] == "revision"
    assert writes[0][1]["previous_outline_id"] == approved.id
    service._persist_outline_resource_audit.assert_awaited_once_with(revision)


@pytest.mark.asyncio
async def test_plot_outline_revision_update_does_not_mutate_approved(monkeypatch):
    from app.models.chapter_outline import ChapterOutline, ChapterOutlineStatus, UpdateChapterOutlineDTO

    service = PlotOutlineService()
    approved = ChapterOutline(
        id="outline-approved",
        project_id="project-1",
        chapter_number=3,
        title="原审批标题",
        summary="原审批摘要",
        status=ChapterOutlineStatus.APPROVED,
    )
    revision = ChapterOutline(
        id="outline-revision",
        project_id="project-1",
        chapter_number=3,
        title="修订标题",
        summary="修订摘要",
        status=ChapterOutlineStatus.REVISION,
        previous_outline_id=approved.id,
    )
    service._outlines_cache[approved.id] = approved
    service._outlines_cache[revision.id] = revision
    writes = []

    class FakeDB:
        async def execute_write(self, query, params=None):
            writes.append((query, dict(params or {})))
            return 1

    service._db = FakeDB()
    monkeypatch.setattr(service, "_persist_outline_resource_audit", AsyncMock())

    result = await service.update_outline(
        revision.id,
        UpdateChapterOutlineDTO(title="二次修订标题"),
    )

    assert result is revision
    assert revision.title == "二次修订标题"
    assert revision.previous_outline_id == approved.id
    assert approved.title == "原审批标题"
    assert writes[0][1]["id"] == revision.id
    service._persist_outline_resource_audit.assert_awaited_once_with(revision)


@pytest.mark.asyncio
async def test_plot_outline_approving_revision_links_previous_outline(monkeypatch):
    from app.models.chapter_outline import ChapterOutline, ChapterOutlineStatus

    service = PlotOutlineService()
    approved = ChapterOutline(
        id="outline-approved",
        project_id="project-1",
        chapter_number=3,
        title="原审批标题",
        summary="原审批摘要",
        status=ChapterOutlineStatus.APPROVED,
    )
    revision = ChapterOutline(
        id="outline-revision",
        project_id="project-1",
        chapter_number=3,
        title="修订标题",
        summary="修订摘要",
        status=ChapterOutlineStatus.REVISION,
        previous_outline_id=approved.id,
    )
    service._outlines_cache[approved.id] = approved
    service._outlines_cache[revision.id] = revision
    writes = []

    class FakeDB:
        async def execute_write(self, query, params=None):
            writes.append((query, dict(params or {})))
            return 1

    service._db = FakeDB()
    monkeypatch.setattr(service, "_persist_outline_resource_audit", AsyncMock())

    result = await service.approve_outline(revision.id, "reviewer")

    assert result is revision
    assert revision.status == ChapterOutlineStatus.APPROVED
    assert revision.approved_by == "reviewer"
    assert approved.next_outline_id == revision.id
    assert writes[0][1]["id"] == revision.id
    assert writes[0][1]["status"] == "approved"
    assert writes[1][1]["id"] == approved.id
    assert writes[1][1]["next_outline_id"] == revision.id
    service._persist_outline_resource_audit.assert_awaited_once_with(revision)


@pytest.mark.asyncio
async def test_plot_outline_rejecting_revision_preserves_approved_outline():
    from app.models.chapter_outline import ChapterOutline, ChapterOutlineStatus

    service = PlotOutlineService()
    approved = ChapterOutline(
        id="outline-approved",
        project_id="project-1",
        chapter_number=3,
        title="原审批标题",
        summary="原审批摘要",
        status=ChapterOutlineStatus.APPROVED,
    )
    revision = ChapterOutline(
        id="outline-revision",
        project_id="project-1",
        chapter_number=3,
        title="修订标题",
        summary="修订摘要",
        status=ChapterOutlineStatus.REVISION,
        previous_outline_id=approved.id,
    )
    service._outlines_cache[approved.id] = approved
    service._outlines_cache[revision.id] = revision
    writes = []

    class FakeDB:
        async def execute_write(self, query, params=None):
            writes.append((query, dict(params or {})))
            return 1

    service._db = FakeDB()

    result = await service.reject_outline_revision(revision.id)

    assert result is revision
    assert revision.status == ChapterOutlineStatus.REJECTED
    assert revision.previous_outline_id == approved.id
    assert approved.status == ChapterOutlineStatus.APPROVED
    assert approved.next_outline_id is None
    assert writes[0][1]["id"] == revision.id
    assert writes[0][1]["status"] == "rejected"


@pytest.mark.asyncio
async def test_plot_outline_chapter_lookup_prefers_approved_when_revision_exists():
    from app.models.chapter_outline import ChapterOutline, ChapterOutlineStatus

    service = PlotOutlineService()
    approved = ChapterOutline(
        id="outline-approved",
        project_id="project-1",
        chapter_number=3,
        title="原审批标题",
        summary="原审批摘要",
        status=ChapterOutlineStatus.APPROVED,
    )
    revision = ChapterOutline(
        id="outline-revision",
        project_id="project-1",
        chapter_number=3,
        title="修订标题",
        summary="修订摘要",
        status=ChapterOutlineStatus.REVISION,
        previous_outline_id=approved.id,
    )
    service._outlines_cache[revision.id] = revision
    service._outlines_cache[approved.id] = approved
    service._loaded_outline_projects.add("project-1")

    assert await service.get_outline("project-1", 3) is approved
    assert await service.get_outline_by_id("project-1", revision.id) is revision
    versions = await service.get_outline_versions("project-1", 3)
    assert versions["current_approved"] is approved
    assert versions["pending_revisions"] == [revision]


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



def test_plot_outline_generation_prompt_uses_md_output_contract(monkeypatch):
    service = PlotOutlineService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "md plot outline output contract",
    )

    prompt = service._build_generation_prompt(
        chapter_number=7,
        context="需要在结尾制造危机",
        previous_events="主角刚获得青铜书签",
        characters=[{"name": "林澈", "role": "主角"}],
        world_info={
            "name": "青岚界",
            "world_type": "wuxia",
            "description": "旧城与灵压并存",
            "settings": [{"priority": "constitutional", "title": "灵压守恒", "summary": "灵压不可凭空产生"}],
        },
        existing_hooks=[{"title": "青铜书签", "description": "接近真相时发热"}],
        full_context=None,
    )

    assert loaded_prompt_ids == ["plot_outline_output"]
    assert "请为第 7 章生成详细的章节大纲。" in prompt
    assert "【输出格式要求】\nmd plot outline output contract" in prompt
    assert "主角刚获得青铜书签" in prompt
    assert "- 林澈 (主角)" in prompt
    assert "本章角色可用性硬约束" in prompt
    assert "pov_character 与 participating_characters" in prompt
    assert "请输出 JSON 格式：" not in prompt
    assert "\"emotion_curve\"" not in prompt
    assert "\"hooks_to_plant\"" not in prompt


def test_plot_outline_generation_prompt_uses_deprecated_minimal_output_fallback(monkeypatch):
    service = PlotOutlineService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "",
    )

    prompt = service._build_generation_prompt(
        chapter_number=1,
        context=None,
        previous_events=None,
        characters=None,
        world_info=None,
        existing_hooks=None,
        full_context=None,
    )

    assert loaded_prompt_ids == ["plot_outline_output"]
    assert "【输出格式要求】" in prompt
    assert "deprecated 最小输出格式 fallback" in prompt
    assert "必须输出完整 JSON" in prompt


def test_plot_outline_consistency_repair_uses_md_asset_and_runtime_feedback(monkeypatch):
    service = PlotOutlineService()
    loaded_prompt_ids = []

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return "MD consistency repair rules: output complete JSON only"

    monkeypatch.setattr(service, "_load_md_prompt_content", fake_load)

    message = "请生成第 3 章大纲"
    consistency = {
        "conflicts": ["主角在未获得能力前使用能力"],
        "risk_areas": ["时间线: 第三章早于觉醒事件"],
        "setting_gaps": ["需要明确青铜书签能力边界"],
    }

    repair_message = service._build_outline_consistency_repair_message(message, consistency)

    assert loaded_prompt_ids == ["function_plot_outline_consistency_repair"]
    assert repair_message.startswith(message)
    assert "MD consistency repair rules: output complete JSON only" in repair_message
    assert "主角在未获得能力前使用能力" in repair_message
    assert "时间线: 第三章早于觉醒事件" in repair_message
    assert "需要明确青铜书签能力边界" in repair_message
    assert "你刚生成的大纲存在设定一致性风险，请基于原任务立即修正后重新输出完整 JSON" not in repair_message


def test_plot_outline_presence_hierarchy_assets_define_foreshadowing_semantics():
    assets = {
        "prompts/identity/role_plot_outline.md": [
            "角色“存在”不等于角色“出场”",
            "foreshadowing_presence",
            "最终大反派的代理人篡改了城市广播",
        ],
        "prompts/instruction/function_plot_outline.md": [
            "角色存在层级（必须先判断）",
            "身影、阴影、注视、未知存在",
            "不能把最终大反派写入出场角色",
        ],
        "prompts/output/plot_outline_output.md": [
            "幕后影响、伏笔性存在、异常痕迹、未知注视",
            "隐藏核心威胁只以痕迹和系统异常存在",
        ],
        "skills/core/skill_outline_context.md": [
            "约束的是“直接出场”",
            "不应自动变成角色绑定需求",
        ],
        "skills/plotting/skill_chapter_outline_generation.md": [
            "近场钩子优先",
            "不要默认动用最终大反派本人制造钩子",
        ],
        "skills/plotting/skill_chapter_villain_arc.md": [
            "这不等于每章都必须安排反派本人出现",
            "低确认度注视/异常",
            "不应写成最终反派本人出场",
        ],
    }

    for path, markers in assets.items():
        content = Path(path).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in content, f"{path} missing marker: {marker}"


def test_plot_outline_assets_define_knowledge_boundary_and_causal_chain_rules():
    assets = {
        "prompts/identity/role_plot_outline.md": [
            "设定真实 ≠ 角色可知",
            "事件神秘 ≠ 事件无因",
            "贫民窟少年根据国家机密",
            "前因/背景压力 → 触发机制 → 主角为何卷入",
        ],
        "prompts/instruction/function_plot_outline.md": [
            "角色知识边界与事件因果（强制）",
            "author/system_known",
            "贫民窟主角知道宪法级国家机密",
            "每个关键事件都必须有可成立的因果链",
        ],
        "prompts/output/plot_outline_output.md": [
            "角色知识边界",
            "事件因果链",
            "protagonist_knowledge_boundary",
            "国家级机密是真实世界因果，但主角只接触到低层可感知线索",
        ],
        "skills/core/skill_outline_context.md": [
            "完整上下文是给 Agent 用来保证设定不冲突的",
            "贫民窟主角可以看到",
            "前因/背景压力 → 触发机制 → 主角卷入路径",
        ],
        "skills/plotting/skill_chapter_outline_generation.md": [
            "主角知识边界",
            "因果优先于强钩子",
            "贫民窟少年直接根据国家级机密判断军方行动",
            "信息权限与因果链检查",
        ],
        "skills/plotting/skill_chapter_hooks_design.md": [
            "因果可追溯原则",
            "角色知识边界原则",
            "天空突然掉下一份国家机密",
        ],
    }

    for path, markers in assets.items():
        content = Path(path).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in content, f"{path} missing marker: {marker}"


def test_plot_outline_assets_define_golden_three_information_and_tension_balance():
    assets = {
        "prompts/instruction/function_plot_outline.md": [
            "低门槛信息赋予 + 高密度近场张力 + 渐进式主线牵引",
            "信息通过冲突赋予",
            "冲突规模：life_pressure / local_anomaly / proxy_conflict / mainline_edge / core_threat",
        ],
        "skills/plotting/skill_chapter_outline_generation.md": [
            "读者信息赋予",
            "主动张力来源",
            "升级不是单纯变“大”，而是变得更与主角有关",
        ],
        "skills/plotting/skill_opening_design.md": [
            "life_pressure",
            "active_tension_source",
            "读者由此理解贫民区资源制度",
        ],
        "skills/plotting/skill_chapter_hooks_design.md": [
            "信息通过冲突赋予",
            "不默认使用 core_threat",
            "问题贴近主角且后果明确",
        ],
        "prompts/output/plot_outline_output.md": [
            "opening_information_delivery",
            "active_tension_source",
            "not_over_escalated",
        ],
    }

    for path, markers in assets.items():
        content = Path(path).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in content, f"{path} missing marker: {marker}"


def test_auxiliary_prompt_assets_define_knowledge_causality_and_resource_safety():
    assets = {
        "prompts/identity/role_character.md": [
            "设定真实 ≠ 角色可知",
            "公开言行",
            "不要现场发明成事实",
        ],
        "skills/performance/skill_character_performance.md": [
            "public_content",
            "private_thought",
            "信息越界",
        ],
        "skills/writing/skill_chapter_hook_generator.md": [
            "钩子可以神秘，但不能无因",
            "真实来源",
            "主角能感知到什么",
        ],
        "prompts/identity/role_dungeon_generator.md": [
            "前因",
            "触发机制",
            "资源需求",
        ],
        "prompts/instruction/function_dungeon_design.md": [
            "risk_reward_balance",
            "failure_consequences",
            "crisis_resolution_resources",
        ],
        "skills/plotting/skill_opening_design.md": [
            "近场钩子优先",
            "隐藏核心威胁克制",
            "因果优先于强钩子",
        ],
        "skills/plotting/skill_webnovel_cool_points.md": [
            "已铺垫资源",
            "代价",
            "状态改变",
        ],
        "skills/plotting/skill_villain_management.md": [
            "direct_scene_presence",
            "foreshadowing_presence",
            "这不等于每章都必须安排反派本人出现",
        ],
    }

    for path, markers in assets.items():
        content = Path(path).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in content, f"{path} missing marker: {marker}"


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
async def test_writer_missing_config_prompt_fails_closed_for_project_runtime(monkeypatch):
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
    with pytest.raises(Exception, match="Writer prompt configuration is missing"):
        await writer._get_writer_config_prompt({"task_type": "character_voice_rewrite"})

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


def test_writer_segment_task_prompts_use_md_asset_for_stable_rules(monkeypatch):
    from app.agents.director.writer import WriterAgent

    writer = WriterAgent(project_id="project-1")
    loaded_prompt_ids = []

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        assert prompt_id == "function_writer_segment_generation"
        return "md writer segment generation rules"

    monkeypatch.setattr(writer, "_load_md_prompt_content", fake_load)

    plan_notes = writer._build_writer_segment_task_notes(
        "segment_plan",
        ["当前运行时目标：输出 WriterSegmentPlanSchema。"],
    )
    segment_prompt = writer._build_segment_prompt(
        segment_info={"focus": "追踪旧城线索", "key_elements": ["线索", "阻力"], "tone": "紧张"},
        previous_content="上一段结尾",
        segment_num=1,
        total_segments=2,
        target_words=800,
        min_words=680,
        max_words=1000,
        world_info={"name": "云岫洲"},
        previous_style="冷峻克制",
        writing_rules_guidance="写作规则：移动端可读",
        discussion_asset_digest="已确认线索：青铜书签",
        workflow_binding_block="绑定大纲：旧城追踪",
        config_prompt="Writer runtime prompt",
    )
    supplement_prompt = writer._build_supplement_prompt(
        existing_content="已有正文",
        shortage=300,
        chapter_num=2,
        total_chapters=100,
        writing_rules_guidance="写作规则",
        workflow_binding_block="绑定大纲",
        config_prompt="Writer runtime prompt",
    )
    continue_prompt = writer._build_continue_prompt(
        existing_content="已有正文",
        shortage=250,
        intents=["推进追踪"],
        character_moods={"沈砚": "警惕"},
        chapter_num=2,
        total_chapters=100,
        writing_rules_guidance="写作规则",
        workflow_binding_block="绑定大纲",
        config_prompt="Writer runtime prompt",
    )

    assert loaded_prompt_ids == [
        "function_writer_segment_generation",
        "function_writer_segment_generation",
        "function_writer_segment_generation",
        "function_writer_segment_generation",
    ]
    assert "md writer segment generation rules" in "\n".join(plan_notes)
    assert "当前运行时目标：输出 WriterSegmentPlanSchema。" in "\n".join(plan_notes)
    for prompt in (segment_prompt, supplement_prompt, continue_prompt):
        assert "md writer segment generation rules" in prompt
        assert "Writer runtime prompt" in prompt
        assert "【输出 JSON Schema】" in prompt
    assert "当前运行时字数范围：680-1000 字" in segment_prompt
    assert "绑定大纲：旧城追踪" in segment_prompt
    assert "已确认线索：青铜书签" in segment_prompt
    assert "把绑定章节大纲、章节目标、修订要求中的关键剧情点分配到具体段落" not in segment_prompt
    assert "续写必须与上文自然衔接，只用于补足字数或补足未覆盖的大纲节点" not in continue_prompt
    assert "补写只能扩展已有合法场景中的前因、行动、阻力、线索或后果" not in supplement_prompt

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
    assert "content:function_summarize" in prompt
    assert "content:function_workflow_performance_summary" in prompt
    assert "content:function_summarizer_runtime_context_packet" in prompt
    assert "content:function_summarizer_setting_check" in prompt
    assert loaded_prompt_ids == [
        "role_summarizer",
        "function_summarize",
        "function_workflow_discussion_summary",
        "function_workflow_performance_summary",
        "function_summarizer_runtime_context_packet",
        "function_summarizer_setting_check",
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
async def test_setting_service_bootstrap_seed_extraction_uses_md_prompt_asset(monkeypatch):
    from app.models.agent_output_schemas import BootstrapSeedExtractionSchema

    service = SettingAgentService()
    captured = {}

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: captured.setdefault("loaded_prompt_ids", []).append(prompt_id) or "md bootstrap seed extraction contract",
    )

    async def fake_call_structured(schema, prompt, project_id=None):
        captured["schema"] = schema
        captured["prompt"] = prompt
        captured["project_id"] = project_id
        return SimpleNamespace(
            model_dump=lambda: {
                "world_setting": {"name": "青岚界", "description": "旧城与灵压并存", "world_type": "wuxia", "tone": "adventurous"},
                "world_rules": ["灵压不可凭空产生"],
                "power_system": "灵压修行",
                "technology_level": "近代机关",
                "main_characters": [],
                "regions": [],
                "plot_hooks": [],
                "narrative_tone": "adventurous",
                "writing_style": "长篇网文",
            }
        )

    monkeypatch.setattr(service, "_call_structured", fake_call_structured)
    session = SimpleNamespace(
        project_id="project-1",
        setting_agent_history=[
            {"role": "user", "content": "世界叫青岚界，旧城与灵压并存。"},
            {"role": "assistant", "content": "我会保留为 seed 草案。"},
        ],
    )

    seed = await service._extract_seed_from_history(session)

    assert captured["loaded_prompt_ids"] == [service.SETTING_BOOTSTRAP_SEED_EXTRACTION_PROMPT_ID]
    assert captured["schema"] is BootstrapSeedExtractionSchema
    assert captured["project_id"] == "project-1"
    prompt = captured["prompt"]
    assert prompt.startswith("md bootstrap seed extraction contract")
    assert "## 对话历史" in prompt
    assert "世界叫青岚界" in prompt
    assert "md bootstrap seed extraction contract" not in prompt.split("## 对话历史", 1)[1]
    assert "请从以下对话中提取结构化的项目 seed" not in prompt
    assert '"world_setting": {"name": "", "description": "", "world_type": "", "tone": ""}' not in prompt
    assert seed["world_setting"]["name"] == "青岚界"
    assert seed["power_system"] == "灵压修行"


@pytest.mark.asyncio
async def test_setting_hook_extraction_uses_md_prompt_asset(monkeypatch):
    service = SettingAgentService()
    captured = {}

    def fake_load_md(prompt_id):
        captured.setdefault("loaded_prompt_ids", []).append(prompt_id)
        assert prompt_id == service.SETTING_HOOK_EXTRACTION_PROMPT_ID
        return "md hook extraction rules\noutput_schema: SettingPendingHooksExtractionSchema"

    async def fake_call_structured(schema, prompt, project_id=None):
        captured["schema"] = schema.__name__
        captured["prompt"] = prompt
        captured["project_id"] = project_id
        hook = SimpleNamespace(
            model_dump=lambda: {
                "title": "青铜书签",
                "description": "书签会在主角接近真相时发热",
                "hook_type": "object",
                "status": "planted",
                "related_characters": ["主角"],
                "related_locations": [],
                "related_objects": ["青铜书签"],
                "plant_context": "用户明确确认该物件作为长期伏笔",
                "resolution_hint": "终局揭示其来源",
                "priority": 7,
            }
        )
        return SimpleNamespace(hooks=[hook])

    monkeypatch.setattr(service, "_load_md_prompt_content", fake_load_md)
    monkeypatch.setattr(service, "_call_structured", fake_call_structured)

    session = SimpleNamespace(
        conversation_history=[
            {"role": "user", "content": "书签会发热，可以作为长期伏笔。"},
            {"role": "assistant", "content": "我会把青铜书签作为待确认伏笔记录。"},
        ]
    )

    hooks = await service._extract_hooks_from_conversation("project-1", session)

    assert captured["loaded_prompt_ids"] == [service.SETTING_HOOK_EXTRACTION_PROMPT_ID]
    assert captured["schema"] == "SettingPendingHooksExtractionSchema"
    assert captured["project_id"] == "project-1"
    prompt = captured["prompt"]
    assert "md hook extraction rules" in prompt
    assert "## 对话内容" in prompt
    assert "书签会发热，可以作为长期伏笔" in prompt
    assert "分析以下对话，判断用户是否明确确认了值得记录为“伏笔（hook）”的内容" not in prompt
    assert "重要规则：" not in prompt
    assert hooks == [
        {
            "title": "青铜书签",
            "description": "书签会在主角接近真相时发热",
            "hook_type": "object",
            "status": "planted",
            "related_characters": ["主角"],
            "related_locations": [],
            "related_objects": ["青铜书签"],
            "plant_context": "用户明确确认该物件作为长期伏笔",
            "resolution_hint": "终局揭示其来源",
            "priority": 5,
        }
    ]


@pytest.mark.asyncio
async def test_auxiliary_runtime_prompts_keep_summarizer_rules_in_md(monkeypatch):
    from app.agents.director.summarizer import SummarizerAgent
    from app.models.agent_output_schemas import SummarizerSettingCheckSchema, SummarizerSummarySchema

    agent = SummarizerAgent(system_prompt="summarizer system")
    captured = {}

    prompt_assets = {
        "function_summarize": "md summarize rules",
        "function_summarizer_runtime_context_packet": "md runtime context packet rules",
    }

    def fake_load(prompt_id):
        return prompt_assets[prompt_id]

    monkeypatch.setattr(agent, "_load_md_prompt_content", fake_load)

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
    assert "md summarize rules" in summary_prompt
    assert "md runtime context packet rules" in summary_prompt
    assert "output_schema: SummarizerSummarySchema" in summary_prompt
    assert "请将以上对话压缩成事件摘要" not in summary_prompt
    assert "不得写成所有角色已知事实" not in summary_prompt
    check_prompt = captured["SummarizerSettingCheckSchema"]
    assert "output_schema: SummarizerSettingCheckSchema" in check_prompt
    assert "请重点检查" not in check_prompt
    assert "角色能力使用是否符合设定" not in check_prompt


def test_summarizer_setting_check_instruction_uses_md_asset_for_stable_rules(monkeypatch):
    from app.agents.director.summarizer import SummarizerAgent

    agent = SummarizerAgent(system_prompt="summarizer system")
    loaded_prompt_ids = []

    prompt_assets = {
        "function_summarizer_setting_check": "md summarizer setting check rules",
        "role_setting": "md setting role rules",
        "function_setting_resource_management": "md setting resource rules",
        "function_setting_lore_interconnection": "md setting interconnection rules",
    }

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return prompt_assets[prompt_id]

    monkeypatch.setattr(agent, "_load_md_prompt_content", fake_load)

    confirmation_instruction = agent._build_setting_check_instruction(has_chapter_content=False)
    consistency_instruction = agent._build_setting_check_instruction(has_chapter_content=True)

    assert loaded_prompt_ids == [
        "function_summarizer_setting_check",
        "role_setting",
        "function_setting_resource_management",
        "function_setting_lore_interconnection",
        "function_summarizer_setting_check",
        "role_setting",
        "function_setting_resource_management",
        "function_setting_lore_interconnection",
    ]
    assert "md summarizer setting check rules" in confirmation_instruction
    assert "md summarizer setting check rules" in consistency_instruction
    assert "md setting resource rules" in consistency_instruction
    assert "【当前任务模式】\n世界观设定确认" in confirmation_instruction
    assert "【当前任务模式】\n章节内容一致性检查" in consistency_instruction
    assert "你是世界观设定管理员，负责确认世界观设定并检查章节内容与设定的一致性" not in confirmation_instruction


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
                "function_summarize",
                "function_workflow_discussion_summary",
                "function_workflow_performance_summary",
                "function_summarizer_runtime_context_packet",
                "function_summarizer_setting_check",
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


def test_setting_bootstrap_collection_system_prompt_uses_md_asset(monkeypatch):
    class FakeMdService:
        def __init__(self):
            self.requested_prompt_ids = []

        def get_prompt(self, prompt_id):
            self.requested_prompt_ids.append(prompt_id)
            assert prompt_id == "function_setting_bootstrap_collection"
            return {"content": "md bootstrap collection rules"}

    md_service = FakeMdService()
    monkeypatch.setattr(
        "app.services.setting_agent.get_md_file_service",
        lambda: md_service,
    )

    agent = SettingAgent()
    prompt = agent._build_system_prompt(SimpleNamespace())

    assert md_service.requested_prompt_ids == ["function_setting_bootstrap_collection"]
    assert prompt == "md bootstrap collection rules"
    assert "你是长篇网络小说设定专家（Setting Agent）。请通过多轮对话收集世界观" not in prompt
    assert "主动追问缺口，并保持所有内容为待确认草案" not in prompt


def test_setting_bootstrap_collection_system_prompt_uses_deprecated_minimal_fallback(monkeypatch):
    class EmptyMdService:
        def get_prompt(self, prompt_id):
            return None

    monkeypatch.setattr(
        "app.services.setting_agent.get_md_file_service",
        lambda: EmptyMdService(),
    )

    agent = SettingAgent()
    prompt = agent._build_system_prompt(SimpleNamespace())

    assert prompt.startswith("【DEPRECATED 最小 fallback】")
    assert "Setting Prompt 资产缺失" not in prompt


def test_setting_agent_service_bootstrap_prompt_uses_md_asset(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "md bootstrap collection rules",
    )

    prompt = service._build_bootstrap_prompt(SimpleNamespace())

    assert loaded_prompt_ids == ["function_setting_bootstrap_collection"]
    assert prompt == "md bootstrap collection rules"
    assert "你是一个长篇网络小说设定专家（Setting Agent）。你的职责是" not in prompt
    assert "【长篇网文核心设定要素】" not in prompt


def test_setting_agent_service_bootstrap_prompt_uses_deprecated_minimal_fallback(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "",
    )

    prompt = service._build_bootstrap_prompt(SimpleNamespace())

    assert loaded_prompt_ids == ["function_setting_bootstrap_collection"]
    assert prompt.startswith("【DEPRECATED 最小 fallback】")
    assert "主动追问缺口" in prompt
    assert "【长篇网文核心设定要素】" not in prompt


def test_agent_communication_intervention_classification_prompt_uses_md_asset(monkeypatch):
    service = AgentCommunicationService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_prompt_asset",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "md intervention classification rules",
    )

    prompt = service._build_intervention_classification_prompt(
        message="这里人物动机错了，请修正",
        target_agent_type="writer",
        context={"chapter": 3, "node_id": "writer-1"},
    )

    assert loaded_prompt_ids == ["function_agent_intervention_classification"]
    assert prompt.startswith("md intervention classification rules")
    assert "## 目标 Agent\n作家 Agent (writer)" in prompt
    assert "## 干预类型定义" in prompt
    assert "- correction:" in prompt
    assert "## 用户干预消息\n这里人物动机错了，请修正" in prompt
    assert '"chapter": 3' in prompt
    assert "分析以下用户对" not in prompt
    assert "请只回答干预类型的英文名称" not in prompt


def test_agent_communication_intervention_classification_prompt_uses_deprecated_minimal_fallback(monkeypatch):
    service = AgentCommunicationService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_prompt_asset",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "",
    )

    prompt = service._build_intervention_classification_prompt(
        message="直接把结局改成主角失败",
        target_agent_type="master_plotter",
        context=None,
    )

    assert loaded_prompt_ids == ["function_agent_intervention_classification"]
    assert prompt.startswith("【DEPRECATED 最小 fallback】")
    assert "## 目标 Agent\n总编剧 Agent (master_plotter)" in prompt
    assert "## 上下文信息\n无" in prompt
    assert "分析以下用户对" not in prompt


@pytest.mark.asyncio
async def test_agent_communication_classification_uses_md_prompt_and_normalizes_llm_output(monkeypatch):
    service = AgentCommunicationService()
    captured = {}

    class FakePlotter:
        async def _call_llm(self, prompt):
            captured["prompt"] = prompt
            return "Correction."

    async def fake_factory(agent_type, project_id):
        captured["agent_type"] = agent_type
        captured["project_id"] = project_id
        return FakePlotter()

    service.set_agent_factory(fake_factory)
    monkeypatch.setattr(
        service,
        "_load_prompt_asset",
        lambda prompt_id: captured.setdefault("loaded_prompt_ids", []).append(prompt_id) or "md intervention classification rules",
    )

    intervention_type = await service.classify_intervention_type(
        message="主角这里不该知道秘密，请修正逻辑",
        target_agent_type="writer",
        project_id="project-1",
        context={"node_id": "writer-1"},
    )

    assert captured["agent_type"] == "master_plotter"
    assert captured["project_id"] == "project-1"
    assert captured["loaded_prompt_ids"] == ["function_agent_intervention_classification"]
    assert captured["prompt"].startswith("md intervention classification rules")
    assert intervention_type is InterventionType.CORRECTION


@pytest.mark.asyncio
async def test_agent_communication_classification_defaults_invalid_llm_output_to_guidance(monkeypatch):
    service = AgentCommunicationService()

    class FakePlotter:
        async def _call_llm(self, prompt):
            return "这需要更多上下文"

    async def fake_factory(agent_type, project_id):
        return FakePlotter()

    service.set_agent_factory(fake_factory)
    monkeypatch.setattr(
        service,
        "_load_prompt_asset",
        lambda prompt_id: "md intervention classification rules",
    )

    intervention_type = await service.classify_intervention_type(
        message="看看这里是否需要调整",
        target_agent_type="writer",
        project_id="project-1",
        context=None,
    )

    assert intervention_type is InterventionType.GUIDANCE


def test_agent_intervention_classification_prompt_asset_defines_enum_contract():
    content = Path("prompts/instruction/function_agent_intervention_classification.md").read_text(encoding="utf-8")

    assert "id: function_agent_intervention_classification" in content
    assert "只能输出以下英文枚举之一" in content
    for value in ["guidance", "correction", "direction", "override"]:
        assert f"`{value}`" in content
    assert "不要输出解释、Markdown、JSON、标点、前后缀或额外文本" in content


def test_setting_world_description_analysis_prompt_uses_md_asset(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "md world description analysis rules",
    )

    prompt = service._build_world_description_analysis_prompt("青岚界由灵压和旧城遗迹构成")

    assert loaded_prompt_ids == ["function_setting_world_description_analysis"]
    assert prompt.startswith("md world description analysis rules")
    assert "## 世界观描述\n青岚界由灵压和旧城遗迹构成" in prompt
    assert "请分析以下世界观描述，并提取结构化信息" not in prompt


def test_setting_negotiation_response_prompt_uses_md_asset(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []
    conflict = SimpleNamespace(
        description="青铜书签是否可直接攻击",
        severity=SimpleNamespace(value="high"),
        resolution_suggestions=["保留限制", "改为回放回声"],
    )

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "md negotiation response rules",
    )

    prompt = service._build_negotiation_response_prompt(conflict, "用户倾向保留限制")

    assert loaded_prompt_ids == ["function_setting_negotiation_response"]
    assert prompt.startswith("md negotiation response rules")
    assert "## 冲突描述\n青铜书签是否可直接攻击" in prompt
    assert "## 严重程度\nhigh" in prompt
    assert "1. 保留限制" in prompt
    assert "## 用户回复\n用户倾向保留限制" in prompt
    assert "请生成一个有帮助的回复，帮助用户做出决定" not in prompt



def test_setting_lore_extraction_prompt_uses_md_asset(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "md lore extraction rules",
    )

    prompt = service._build_lore_extraction_prompt("user: 用户确认保存青铜书签")

    assert loaded_prompt_ids == ["function_setting_lore_extraction_confirmation"]
    assert prompt.startswith("md lore extraction rules")
    assert "## 对话内容\nuser: 用户确认保存青铜书签" in prompt
    assert "请只在用户明确确认后才提取" not in prompt



def test_setting_hook_extraction_prompt_uses_md_asset(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "md hook extraction rules",
    )

    prompt = service._build_hook_extraction_prompt("user: 用户确认这个伏笔要保留")

    assert loaded_prompt_ids == ["function_setting_hook_extraction_confirmation"]
    assert prompt.startswith("md hook extraction rules")
    assert "## 对话内容\nuser: 用户确认这个伏笔要保留" in prompt



def test_setting_character_extraction_prompt_uses_md_asset(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "md character extraction rules",
    )

    prompt = service._build_character_extraction_prompt("user: 请保存这个角色")

    assert loaded_prompt_ids == ["function_setting_character_extraction_confirmation"]
    assert prompt.startswith("md character extraction rules")
    assert "## 对话内容\nuser: 请保存这个角色" in prompt



def test_setting_world_type_and_tone_inference_prompts_use_md_assets(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return f"md rules for {prompt_id}"

    monkeypatch.setattr(service, "_load_md_prompt_content", fake_load)

    world_type_prompt = service._build_world_type_inference_prompt("user: 这个世界有门派和江湖恩怨")
    tone_prompt = service._build_tone_inference_prompt("user: 故事整体是热血成长冒险")

    assert loaded_prompt_ids == [
        "function_setting_world_type_inference",
        "function_setting_tone_inference",
    ]
    assert world_type_prompt.startswith("md rules for function_setting_world_type_inference")
    assert "## 对话内容\nuser: 这个世界有门派和江湖恩怨" in world_type_prompt
    assert "请从以下对话中推断故事的世界类型" not in world_type_prompt
    assert "可能的类型：" not in world_type_prompt
    assert tone_prompt.startswith("md rules for function_setting_tone_inference")
    assert "## 对话内容\nuser: 故事整体是热血成长冒险" in tone_prompt
    assert "请从以下对话中推断故事的叙事基调" not in tone_prompt
    assert "可能的基调：" not in tone_prompt


@pytest.mark.asyncio
async def test_setting_world_type_and_tone_inference_paths_use_md_prompt_builders(monkeypatch):
    service = SettingAgentService()
    captured_prompts = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: f"md inference rules for {prompt_id}",
    )

    async def fake_call_llm_simple(prompt):
        captured_prompts.append(prompt)
        if "function_setting_world_type_inference" in prompt:
            return "wuxia"
        if "function_setting_tone_inference" in prompt:
            return "adventurous"
        raise AssertionError(prompt)

    monkeypatch.setattr(service, "_call_llm_simple", fake_call_llm_simple)

    history = [
        {"role": "user", "content": "故事发生在江湖门派之间。"},
        {"role": "assistant", "content": "这是武侠底色。"},
        {"role": "user", "content": "整体要热血成长、持续冒险。"},
    ]

    assert await service.infer_world_type(history) == "wuxia"
    assert await service.infer_tone(history) == "adventurous"

    assert len(captured_prompts) == 2
    assert "md inference rules for function_setting_world_type_inference" in captured_prompts[0]
    assert "## 对话内容" in captured_prompts[0]
    assert "故事发生在江湖门派之间" in captured_prompts[0]
    assert "请从以下对话中推断故事的世界类型" not in captured_prompts[0]
    assert "md inference rules for function_setting_tone_inference" in captured_prompts[1]
    assert "整体要热血成长、持续冒险" in captured_prompts[1]
    assert "请从以下对话中推断故事的叙事基调" not in captured_prompts[1]


@pytest.mark.parametrize(
    ("prompt_id", "expected_terms"),
    [
        ("function_setting_world_type_inference", ["fantasy", "scifi", "modern", "historical", "wuxia", "unknown"]),
        ("function_setting_tone_inference", ["serious", "lighthearted", "dark", "comedic", "adventurous", "unknown"]),
    ],
)
def test_setting_inference_prompt_assets_define_stable_enum_contract(prompt_id, expected_terms):
    prompt_path = Path("prompts/instruction") / f"{prompt_id}.md"
    content = prompt_path.read_text(encoding="utf-8")

    assert f"id: {prompt_id}" in content
    assert "不要输出解释文字" in content
    for term in expected_terms:
        assert term in content


def test_setting_personality_generation_prompt_uses_md_asset(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "md personality generation rules",
    )

    prompt = service._build_personality_generation_prompt_from_context(
        name="陆青",
        role="main",
        description="旧城药铺出身的少年",
        background="懂得隐藏力量",
        existing_personalities="\n\n现有角色性格（避免过于相似）：\n- 林掌柜：沉稳",
        project_context="青岚界",
        role_descriptions={"main": "主角 - 故事的核心人物，需要鲜明的性格和成长空间"},
    )

    assert loaded_prompt_ids == ["function_setting_personality_generation"]
    assert prompt.startswith("md personality generation rules")
    assert "【项目背景】\n青岚界" in prompt
    assert "【角色信息】" in prompt
    assert "- 姓名：陆青" in prompt
    assert "- 定位：主角 - 故事的核心人物，需要鲜明的性格和成长空间" in prompt



def test_setting_management_system_prompt_uses_md_asset(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "md management system rules",
    )

    class FakeSession:
        project_id = "project-1"

    prompt = asyncio.run(service._build_management_system_prompt(FakeSession()))

    assert loaded_prompt_ids == ["function_setting_management_system_prompt"]
    assert prompt.startswith("md management system rules")
    assert "【世界类型提示】" in prompt
    assert "【叙事基调提示】" in prompt



def test_character_detection_prompt_uses_md_asset_and_runtime_blocks(monkeypatch):
    class FakeMdService:
        def __init__(self):
            self.requested_prompt_ids = []

        def get_prompt(self, prompt_id):
            self.requested_prompt_ids.append(prompt_id)
            assert prompt_id == "function_character_detection"
            return {"content": "md character detection rules and JSON contract"}

    md_service = FakeMdService()
    monkeypatch.setattr(
        "app.services.character_detection.get_md_file_service",
        lambda: md_service,
    )

    manager = CharacterPromotionManager()
    prompt = manager._build_character_detection_prompt(
        "青岚界旧城药铺中，白衣少年第一次开口。",
        "陆青, 林掌柜",
    )

    assert md_service.requested_prompt_ids == ["function_character_detection"]
    assert prompt.startswith("md character detection rules and JSON contract")
    assert "## 章节内容\n青岚界旧城药铺中，白衣少年第一次开口。" in prompt
    assert "## 已有角色列表\n陆青, 林掌柜" in prompt
    assert "请从以下章节内容中检测和提取所有出现的角色" not in prompt
    assert "【检测任务】" not in prompt
    assert "【重要性判断标准】" not in prompt
    assert "只输出 JSON，不要有其他内容。" not in prompt


@pytest.mark.asyncio
async def test_character_detection_llm_path_parses_json_and_filters_existing_characters(monkeypatch):
    class FakeMdService:
        def __init__(self):
            self.requested_prompt_ids = []

        def get_prompt(self, prompt_id):
            self.requested_prompt_ids.append(prompt_id)
            assert prompt_id == "function_character_detection"
            return {"content": "md character detection rules"}

    class FakeResponse:
        content = """
        {
          "existing_characters_found": ["陆青"],
          "new_characters": [
            {
              "name": "陆青",
              "importance_tier": 1,
              "first_appearance_context": "陆青回到药铺",
              "description": "已有角色",
              "dialogue_count": 1,
              "importance_reason": "已有主角"
            },
            {
              "name": "白衣少年",
              "importance_tier": 3,
              "first_appearance_context": "白衣少年推门而入",
              "description": "带来线索的新角色",
              "dialogue_count": 2,
              "importance_reason": "有台词并推动情节"
            }
          ],
          "total_characters_in_chapter": 2
        }
        """

    class FakeLlm:
        def __init__(self):
            self.messages = []

        async def ainvoke(self, messages):
            self.messages = messages
            return FakeResponse()

    md_service = FakeMdService()
    monkeypatch.setattr(
        "app.services.character_detection.get_md_file_service",
        lambda: md_service,
    )

    manager = CharacterPromotionManager()
    llm = FakeLlm()
    detected = await manager._detect_characters_with_llm(
        content="陆青回到药铺。白衣少年推门而入：我知道青岚界旧城的秘密。",
        project_id="project-1",
        existing_characters=[{"name": "陆青"}],
        llm_model=llm,
    )

    assert md_service.requested_prompt_ids == ["function_character_detection"]
    assert detected == [
        {
            "name": "白衣少年",
            "importance_tier": 3,
            "first_appearance_context": "白衣少年推门而入",
            "description": "带来线索的新角色",
            "dialogue_count": 2,
            "importance_reason": "有台词并推动情节",
        }
    ]
    assert len(llm.messages) == 1
    prompt = llm.messages[0].content
    assert prompt.startswith("md character detection rules")
    assert "## 章节内容\n陆青回到药铺。白衣少年推门而入" in prompt
    assert "## 已有角色列表\n陆青" in prompt
    assert "请从以下章节内容中检测和提取所有出现的角色" not in prompt

def test_collaborator_prompt_uses_md_asset_and_runtime_role_context(monkeypatch):
    class FakeMdService:
        def __init__(self):
            self.requested_prompt_ids = []

        def get_prompt(self, prompt_id):
            self.requested_prompt_ids.append(prompt_id)
            assert prompt_id == "function_collaborator_role_advice"
            return {"content": "md collaborator advice rules"}

    md_service = FakeMdService()
    monkeypatch.setattr(
        "app.services.collaborator.get_md_file_service",
        lambda: md_service,
    )

    system = CollaboratorSystem()
    role_profile = system.role_profiles[CollaborationRole.PLOT_ADVISOR]
    request = CollaborationRequest(
        request_type="plot_gap_review",
        context={
            "world": {"name": "云岫洲", "description": "慢热玄幻世界"},
            "characters": [{"name": "沈砚", "role": "main"}],
            "plot": "主角获得青铜书签后需要承接古碑回声线索。",
            "current_issue": "第二章缺少明确事件推进。",
            "specific_question": "如何避免只有对话？",
        },
        role=CollaborationRole.PLOT_ADVISOR,
    )

    prompt = system._prepare_prompt(request, role_profile)

    assert md_service.requested_prompt_ids == ["function_collaborator_role_advice"]
    assert prompt[0]["role"] == "system"
    assert prompt[0]["content"].startswith("md collaborator advice rules")
    assert "## 当前协作角色" in prompt[0]["content"]
    assert "角色名称：剧情顾问" in prompt[0]["content"]
    assert "角色优势：结构设计、节奏控制、张力构建" in prompt[0]["content"]
    assert "你是一个经验丰富的剧情顾问" not in prompt[0]["content"]
    assert "请关注剧情的连贯性、张力和节奏感" not in prompt[0]["content"]

    assert prompt[1]["role"] == "user"
    user_message = prompt[1]["content"]
    assert "## 协作请求类型\nplot_gap_review" in user_message
    assert "世界：云岫洲" in user_message
    assert "角色列表：" in user_message
    assert "沈砚 - main" in user_message
    assert "当前问题：第二章缺少明确事件推进。" in user_message
    assert "具体问题：如何避免只有对话？" in user_message
    assert "请根据你的角色" not in user_message


@pytest.mark.asyncio
async def test_setting_bootstrap_seed_extraction_uses_md_system_prompt_and_dynamic_history(monkeypatch):
    class FakeMdService:
        def __init__(self):
            self.requested_prompt_ids = []

        def get_prompt(self, prompt_id):
            self.requested_prompt_ids.append(prompt_id)
            assert prompt_id == "function_setting_bootstrap_seed_extraction"
            return {"content": "md bootstrap seed extraction contract"}

    md_service = FakeMdService()
    monkeypatch.setattr(
        "app.services.setting_agent.get_md_file_service",
        lambda: md_service,
    )

    agent = SettingAgent()
    captured = {}

    async def fake_call_llm(system_prompt, user_message, context):
        captured["system_prompt"] = system_prompt
        captured["user_message"] = user_message
        captured["context"] = context
        return '{"world_setting":{"name":"青岚界"},"main_characters":[]}'

    monkeypatch.setattr(agent, "_call_llm", fake_call_llm)
    session = SimpleNamespace(
        setting_agent_history=[
            {"role": "user", "content": "世界叫青岚界，主角从旧城药铺起步。"},
            {"role": "assistant", "content": "已记录为待确认草案。"},
        ]
    )

    seed_data = await agent.extract_seed_from_history(session)

    assert md_service.requested_prompt_ids == ["function_setting_bootstrap_seed_extraction"]
    assert seed_data == {"world_setting": {"name": "青岚界"}, "main_characters": []}
    assert captured["system_prompt"] == "md bootstrap seed extraction contract"
    assert captured["user_message"].startswith("## 对话历史")
    assert "user: 世界叫青岚界" in captured["user_message"]
    assert "assistant: 已记录为待确认草案。" in captured["user_message"]
    assert captured["context"] == ""
    assert "你是一个结构化数据提取专家。请从对话中提取 JSON 数据。" not in captured["system_prompt"]
    assert "请从对话历史中提取结构化项目 seed，只输出 JSON 对象" not in captured["system_prompt"]
    assert "md bootstrap seed extraction contract" not in captured["user_message"]


def test_workflow_setting_agent_chapter_consistency_prompt_uses_md_asset(monkeypatch):
    from app.agents.setting_agent import SettingAgent as WorkflowSettingAgent

    agent = WorkflowSettingAgent(project_id="project-1")
    loaded_prompt_ids = []

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        assert prompt_id == "function_setting_chapter_consistency"
        return "md setting chapter consistency rules"

    monkeypatch.setattr(agent, "_load_md_prompt_content", fake_load)

    prompt = agent._build_chapter_consistency_prompt(
        "陆青在旧城灵压下用青铜书签直接击溃敌人。"
    )

    assert loaded_prompt_ids == ["function_setting_chapter_consistency"]
    assert prompt.startswith("md setting chapter consistency rules")
    assert "【章节内容】\n陆青在旧城灵压下用青铜书签直接击溃敌人。" in prompt
    assert "请检查以下章节内容与世界设定的一致性" not in prompt
    assert "力量体系使用是否一致" not in prompt
    assert "如果发现问题，列出具体问题并建议修改方案" not in prompt
    trace = agent.get_system_prompt_render_trace()
    assert trace["scenario"] == "chapter_consistency"
    assert trace["prompt_ids"] == ["function_setting_chapter_consistency"]
    assert trace["fallbacks_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


def test_workflow_setting_agent_chapter_consistency_missing_asset_fails_closed_for_project(monkeypatch):
    from app.agents.setting_agent import SettingAgent as WorkflowSettingAgent

    agent = WorkflowSettingAgent(project_id="project-1")
    monkeypatch.setattr(agent, "_load_md_prompt_content", lambda prompt_id: "")

    with pytest.raises(Exception, match="Setting prompt asset is missing"):
        agent._build_chapter_consistency_prompt("正文")

    trace = agent.get_system_prompt_render_trace()
    assert trace["scenario"] == "chapter_consistency"
    assert trace["fallbacks_used"] == ["setting_missing_prompt_asset"]
    assert trace["missing_prompt_ids"] == ["function_setting_chapter_consistency"]
    assert_render_trace_contract(trace)


def test_workflow_setting_agent_context_analysis_prompt_uses_md_asset_and_runtime_blocks(monkeypatch):
    from app.agents.setting_agent import SettingAgent as WorkflowSettingAgent

    agent = WorkflowSettingAgent(project_id="project-1")
    loaded_prompt_ids = []

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        assert prompt_id == "function_setting_workflow_context_analysis"
        return "md setting workflow context analysis rules"

    monkeypatch.setattr(agent, "_load_md_prompt_content", fake_load)

    prompt = agent._build_workflow_context_analysis_prompt(
        chapter_num=3,
        goal_text="揭示青铜书签只能回放古碑回声",
        outline_text="陆青在旧城药铺发现书签限制",
        world_name="青岚界",
        world_type="fantasy",
        world_rules_text="灵气不能凭空转化为神识",
        lore_summaries=["- 青铜书签: 只能回放古碑回声，不能直接攻击"],
    )

    assert loaded_prompt_ids == ["function_setting_workflow_context_analysis"]
    assert prompt.startswith("md setting workflow context analysis rules")
    assert "- 章节号：3" in prompt
    assert "- 章节目标：揭示青铜书签只能回放古碑回声" in prompt
    assert "- 当前大纲/焦点：陆青在旧城药铺发现书签限制" in prompt
    assert "- 世界名：青岚界" in prompt
    assert "- 类型/风格：fantasy" in prompt
    assert "- 核心规则：灵气不能凭空转化为神识" in prompt
    assert "- 青铜书签: 只能回放古碑回声，不能直接攻击" in prompt
    assert "你不是在泛泛整理世界观" not in prompt
    assert "不要自行脑补默认奇幻/冒险设定" not in prompt
    assert "输出尽量结构化" not in prompt
    trace = agent.get_system_prompt_render_trace()
    assert trace["scenario"] == "workflow_context"
    assert trace["prompt_ids"] == ["function_setting_workflow_context_analysis"]
    assert trace["fallbacks_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


@pytest.mark.asyncio
async def test_workflow_setting_agent_methods_send_md_backed_prompts_to_chat(monkeypatch):
    from app.agents.setting_agent import SettingAgent as WorkflowSettingAgent

    agent = WorkflowSettingAgent(project_id="project-1")
    loaded_prompt_ids = []
    captured_calls = []

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return f"md rules for {prompt_id}"

    class FakeSettingService:
        async def chat(self, **kwargs):
            captured_calls.append(kwargs)
            return {"response": "ok"}

    monkeypatch.setattr(agent, "_load_md_prompt_content", fake_load)
    agent._setting_service = FakeSettingService()

    chapter_result = await agent._check_chapter_consistency(
        "陆青用青铜书签直接攻击敌人。",
        {"world_info": {"name": "青岚界"}},
    )
    organize_result = await agent._organize_settings(
        {
            "chapter_num": 1,
            "chapter_goals": [{"goal": "确认书签能力边界"}],
            "chapter_outline": {"1": {"summary": "旧城药铺测试书签"}},
            "world_info": {
                "name": "青岚界",
                "world_type": "fantasy",
                "rules": ["书签只能回放回声"],
            },
            "lore_entries": [
                {
                    "title": "青铜书签",
                    "summary": "只能回放古碑回声",
                    "constraints": ["不能直接攻击"],
                }
            ],
        }
    )

    assert chapter_result == "ok"
    assert organize_result == "ok"
    assert loaded_prompt_ids == [
        "function_setting_chapter_consistency",
        "function_setting_workflow_context_analysis",
    ]

    chapter_call = captured_calls[0]
    assert chapter_call["project_id"] == "project-1"
    assert chapter_call["message"].startswith("md rules for function_setting_chapter_consistency")
    assert "【章节内容】\n陆青用青铜书签直接攻击敌人。" in chapter_call["message"]
    assert chapter_call["context"]["chapter_check"] is True
    assert chapter_call["context"]["world_info"] == {"name": "青岚界"}
    assert "力量体系使用是否一致" not in chapter_call["message"]

    organize_call = captured_calls[1]
    assert organize_call["project_id"] == "project-1"
    assert organize_call["message"].startswith("md rules for function_setting_workflow_context_analysis")
    assert "- 章节号：1" in organize_call["message"]
    assert "- 章节目标：确认书签能力边界" in organize_call["message"]
    assert "- 当前大纲/焦点：旧城药铺测试书签" in organize_call["message"]
    assert "- 世界名：青岚界" in organize_call["message"]
    assert "- 青铜书签: 只能回放古碑回声；禁止/限制：不能直接攻击" in organize_call["message"]
    assert organize_call["context"]["workflow_setting_analysis"] is True
    assert "你不是在泛泛整理世界观" not in organize_call["message"]


def test_setting_improvement_analysis_prompt_uses_md_asset_and_runtime_blocks(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        assert prompt_id == "function_setting_improvement_analysis"
        return "md setting improvement analysis rules"

    monkeypatch.setattr(service, "_load_md_prompt_content", fake_load)

    prompt = service._build_setting_improvement_analysis_prompt(
        world_type_hint="fantasy：魔法、异世界、宗门体系",
        lores_summary="- [core] 青岚界灵气规则 (power): 灵气不能凭空转化为神识",
        conversation_context="用户刚确认青铜书签只能回放古碑回声，不能直接攻击。",
    )

    assert loaded_prompt_ids == ["function_setting_improvement_analysis"]
    assert prompt.startswith("md setting improvement analysis rules")
    assert "## 世界类型\nfantasy：魔法、异世界、宗门体系" in prompt
    assert "## 现有设定列表\n- [core] 青岚界灵气规则" in prompt
    assert "## 最近对话上下文\n用户刚确认青铜书签只能回放古碑回声" in prompt
    assert "你是一个专业的小说设定审核专家。请分析以下世界观设定" not in prompt
    assert "请识别以下类型的改进机会" not in prompt
    assert "只输出 JSON 数组，不要其他内容" not in prompt


@pytest.mark.asyncio
async def test_setting_improvement_analysis_path_uses_structured_schema_and_filters_results(monkeypatch):
    from app.models.agent_output_schemas import SettingImprovementSuggestionsSchema

    service = SettingAgentService()
    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: "md setting improvement analysis rules",
    )

    class FakeDb:
        async def execute_query(self, query, params):
            assert params == {"project_id": "project-1"}
            return [
                {
                    "id": "lore-1",
                    "title": "青铜书签",
                    "category": "artifact",
                    "priority": "core",
                    "content": "只能回放古碑回声，不能直接攻击。",
                    "summary": "回放古碑回声",
                    "keywords": [],
                },
                {
                    "id": "lore-2",
                    "title": "旧城灵压",
                    "category": "power_system",
                    "priority": "standard",
                    "content": "旧城灵压会压制初学者施法。",
                    "summary": "旧城灵压限制",
                    "keywords": [],
                },
            ]

    captured = {}

    async def fake_call_structured(schema, prompt, *, project_id=None, **kwargs):
        captured["schema"] = schema
        captured["prompt"] = prompt
        captured["project_id"] = project_id
        return SimpleNamespace(
            suggestions=[
                SimpleNamespace(model_dump=lambda: {
                    "type": "relation",
                    "target_lore_id": "lore-1",
                    "target_lore_title": "青铜书签",
                    "issue": "与旧城灵压的互动边界未说明",
                    "suggestion": "补充书签回放能力在灵压环境下的限制",
                    "suggested_content": "青铜书签在旧城灵压下只能回放短片段。",
                    "priority": "high",
                    "reason": "避免后续大纲误用能力",
                }),
                SimpleNamespace(model_dump=lambda: {
                    "type": "missing",
                    "issue": "缺少 suggestion 字段，应被过滤",
                }),
            ]
        )

    monkeypatch.setattr("app.api.app.postgres_db", FakeDb(), raising=False)
    monkeypatch.setattr(service, "_call_structured", fake_call_structured)
    monkeypatch.setattr(service, "_get_world_type_hint", lambda world_type: f"hint:{world_type}")

    suggestions = await service.analyze_existing_lores(
        project_id="project-1",
        conversation_context="用户刚确认书签不能直接攻击。",
        world_type="fantasy",
    )

    assert captured["schema"] is SettingImprovementSuggestionsSchema
    assert captured["project_id"] == "project-1"
    assert captured["prompt"].startswith("md setting improvement analysis rules")
    assert "## 世界类型\nhint:fantasy" in captured["prompt"]
    assert "青铜书签" in captured["prompt"]
    assert "旧城灵压" in captured["prompt"]
    assert "用户刚确认书签不能直接攻击" in captured["prompt"]
    assert "你是一个专业的小说设定审核专家。请分析以下世界观设定" not in captured["prompt"]
    assert len(suggestions) == 1
    assert suggestions[0]["type"] == "relation"
    assert suggestions[0]["target_lore_id"] == "lore-1"
    assert suggestions[0]["priority"] == "high"
    assert suggestions[0]["id"]


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


def test_setting_segment_key_point_extraction_prompt_uses_md_asset(monkeypatch):
    service = SettingAgentService()
    loaded_prompt_ids = []

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: loaded_prompt_ids.append(prompt_id) or "md segmented synthesis rules",
    )

    prompt = service._build_segment_key_point_extraction_prompt(
        section_name="设定库",
        segment_content="青铜书签只能回放旧城短片段。",
        user_question="如何补全书签限制？",
        world_type_hint="武侠 / 灵压体系",
    )

    assert loaded_prompt_ids == ["function_setting_segmented_context_synthesis"]
    assert prompt.startswith("md segmented synthesis rules")
    assert "## 世界类型\n武侠 / 灵压体系" in prompt
    assert "## 片段来源\n设定库" in prompt
    assert "## 片段内容\n青铜书签只能回放旧城短片段。" in prompt
    assert "## 用户问题\n如何补全书签限制？" in prompt
    assert "分析以下项目上下文片段，提取关键信息点" not in prompt
    assert "提取关键信息点，格式如下" not in prompt


@pytest.mark.asyncio
async def test_setting_extract_key_points_uses_md_prompt_builder(monkeypatch):
    service = SettingAgentService()
    captured = {}

    monkeypatch.setattr(
        service,
        "_load_md_prompt_content",
        lambda prompt_id: captured.setdefault("loaded_prompt_ids", []).append(prompt_id) or "md segmented synthesis rules",
    )

    async def fake_call_llm_simple(prompt):
        captured["prompt"] = prompt
        return """
        ```json
        [
          {
            "category": "道具规则",
            "entity": "青铜书签",
            "key_fact": "青铜书签只能回放旧城短片段",
            "relevance": "高",
            "related_entities": ["旧城"],
            "relation_type": "requires_resource",
            "resource_requirements": [
              {"requirement_type":"item","resource_name":"青铜书签","severity":"blocking","reason":"需要补全回放边界"}
            ]
          }
        ]
        ```
        """

    monkeypatch.setattr(service, "_call_llm_simple", fake_call_llm_simple)

    key_points = await service._extract_key_points(
        section_name="设定库",
        segment_content="青铜书签只能回放旧城短片段。",
        user_question="如何补全书签限制？",
        world_type_hint="武侠 / 灵压体系",
        project_id="project-1",
    )

    assert captured["loaded_prompt_ids"] == ["function_setting_segmented_context_synthesis"]
    assert captured["prompt"].startswith("md segmented synthesis rules")
    assert "## 片段内容\n青铜书签只能回放旧城短片段。" in captured["prompt"]
    assert "分析以下项目上下文片段，提取关键信息点" not in captured["prompt"]
    assert key_points == [
        {
            "category": "道具规则",
            "entity": "青铜书签",
            "key_fact": "青铜书签只能回放旧城短片段",
            "relevance": "高",
            "related_entities": ["旧城"],
            "relation_type": "requires_resource",
            "potential_conflicts": [],
            "resource_requirements": [
                {
                    "requirement_type": "item",
                    "resource_name": "青铜书签",
                    "severity": "blocking",
                    "reason": "需要补全回放边界",
                    "suggested_payload": {},
                }
            ],
        }
    ]


@pytest.mark.asyncio
async def test_setting_improvement_analysis_prompt_uses_deprecated_minimal_fallback_when_md_missing(monkeypatch):
    service = SettingAgentService()
    monkeypatch.setattr(service, "_load_md_prompt_content", lambda prompt_id: "")

    prompt = service._build_setting_improvement_analysis_prompt(
        world_type_hint="hint:fantasy",
        lores_summary="- [core] 青铜书签",
        conversation_context="用户刚确认书签不能直接攻击。",
    )

    assert prompt.startswith("【DEPRECATED 最小 fallback】请分析现有世界观设定")
    assert "## 世界类型\nhint:fantasy" in prompt
    assert "## 现有设定列表\n- [core] 青铜书签" in prompt
    assert "## 最近对话上下文\n用户刚确认书签不能直接攻击。" in prompt


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


def test_workflow_runtime_constraints_use_md_asset_and_runtime_blocks(monkeypatch):
    engine = WorkflowEngine()
    loaded_prompt_ids = []

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        assert prompt_id == "function_workflow_runtime_constraints"
        return "md workflow runtime constraint rules"

    monkeypatch.setattr(engine, "_load_prompt_asset_content", fake_load)

    context = {
        "scene_directions": {
            "performers": [{"name": "沈砚"}],
            "mentioned_characters": [{"name": "旧城守夜人"}],
            "unavailable_characters": [{"name": "已故师父"}],
            "background_characters": [{"name": "客栈伙计"}],
        },
        "selected_lore_entries": [
            {
                "id": "lore-char-1",
                "category": "character_setting",
                "title": "沈砚来源",
                "content": "沈砚来自旧城书铺。",
            }
        ],
    }

    constraints = engine._build_character_constraint_state(context)
    prompt = engine._format_agent_constraint_context(context)

    assert constraints["rules_prompt_id"] == "function_workflow_runtime_constraints"
    assert loaded_prompt_ids == ["function_workflow_runtime_constraints"]
    assert prompt.startswith("【工作流角色/设定约束】\nmd workflow runtime constraint rules")
    assert "【角色出场运行期数据】" in prompt
    assert "present_character_names" in prompt
    assert "沈砚" in prompt
    assert "mentioned_only_names" in prompt
    assert "旧城守夜人" in prompt
    assert "forbidden_direct_appearance_names" in prompt
    assert "已故师父" in prompt
    assert "【角色设定库条目（来源/历史/身份必须遵守）】" in prompt
    assert "沈砚来源" in prompt
    assert "只有 present_character_names 中的角色可以在当前正面场景中说话" not in prompt
    assert "mentioned_only_names 只能作为传闻" not in prompt
    assert "角色来源、历史、身份和背景必须服从 selected_lore_entries" not in prompt


def test_workflow_normalizes_discussion_message_shape():
    engine = WorkflowEngine()

    normalized = engine._normalize_discussion_message({
        "speaker": "角色甲",
        "role": "主角",
        "public_content": "我们先离开这里。",
    })

    assert normalized["agent"] == "角色甲"
    assert normalized["character"] == "角色甲"
    assert normalized["speaker"] == "角色甲"
    assert normalized["content"] == "我们先离开这里。"
    assert normalized["public_content"] == "我们先离开这里。"
    assert normalized["speaker_type"] == "agent"


@pytest.mark.asyncio
async def test_workflow_discussion_broadcast_uses_normalized_payload():
    engine = WorkflowEngine()
    events = []

    async def fake_status(execution_id, event_type, data):
        events.append((execution_id, event_type, data))

    engine._broadcast_status = fake_status

    await engine._broadcast_discussion_message_event(
        "exec-1",
        {"speaker": "角色乙", "summary": "总结了撤离路线。"},
    )

    assert events[0][0] == "exec-1"
    assert events[0][1] == "discussion_message"
    assert events[0][2]["agent"] == "角色乙"
    assert events[0][2]["character"] == "角色乙"
    assert events[0][2]["content"] == "总结了撤离路线。"
    assert events[0][2]["message"]["speaker"] == "角色乙"


@pytest.mark.asyncio
async def test_workflow_discussion_broadcast_filters_empty_payload():
    engine = WorkflowEngine()
    events = []

    async def fake_status(execution_id, event_type, data):
        events.append((execution_id, event_type, data))

    engine._broadcast_status = fake_status

    await engine._broadcast_discussion_message_event("exec-1", {"speaker": "角色乙"})

    assert events == []


def test_workflow_reference_material_instruction_uses_constraints_asset(monkeypatch):
    engine = WorkflowEngine()
    loaded_prompt_ids = []

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return "md workflow runtime constraint rules"

    monkeypatch.setattr(engine, "_load_prompt_asset_content", fake_load)

    instruction = engine._build_workflow_reference_material_instruction()

    assert loaded_prompt_ids == ["function_workflow_runtime_constraints"]
    assert "function_workflow_runtime_constraints" in instruction
    assert "参考的素材索引" in instruction
    assert "已确认资产冲突" in instruction


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


def test_master_and_evaluator_workflow_output_contracts_resolve_schemas():
    engine = WorkflowEngine()

    scene_contract = engine._resolve_output_contract("master_plotter.scene_plan.workflow_output")
    revision_contract = engine._resolve_output_contract("master_plotter.revision_directive.workflow_output")
    evaluator_contract = engine._resolve_output_contract("evaluator.chapter_quality_gate.workflow_output")

    assert scene_contract.schema_ref.endswith("MasterScenePlanSchema")
    assert "scene_plan" in scene_contract.structured_fields
    assert revision_contract.schema_ref.endswith("MasterRevisionDirectiveSchema")
    assert "writer_revision_brief" in revision_contract.structured_fields
    assert evaluator_contract.schema_ref.endswith("EvaluatorChapterEndSchema")
    assert "scene_plan_adherence_check" in evaluator_contract.structured_fields
    assert "revision_directive_adherence_check" in evaluator_contract.structured_fields


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


def test_phase_4_6_scene_coordinator_builds_per_character_knowledge_packet(monkeypatch):
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

    def fake_load(prompt_id):
        return {
            "function_summarize": "md summarize rules",
            "function_summarizer_runtime_context_packet": "md runtime context packet rules",
        }[prompt_id]

    monkeypatch.setattr(summarizer, "_load_md_prompt_content", fake_load)
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

    assert "md summarize rules" in user_message
    assert "md runtime context packet rules" in user_message
    assert "【私有表演素材】" in user_message
    assert "【私有表演素材（仅供 Writer/Evaluator 参考，不得总结成场内公开事实）】" not in user_message
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
            "master_scene_plan": {"plan_id": "plan-1", "scene_plan": [{"beat_id": "beat-1", "acceptance_criteria": ["可见后果"]}]},
            "writer_brief": {"must_follow": ["按 beat 写"]},
            "master_revision_directive": {"revision_id": "rev-1", "issues": [{"issue_id": "issue-1"}]},
            "writer_revision_brief": {"scope": "重写 beat-1"},
            "evaluator_focus": ["beat-1"],
        }
    )

    assert "Master 场景计划" in block
    assert "Master 修订指令" in block
    assert "修订执行简报" in block
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

    writer_skill_ids = {slot.skill_id for slot in DIRECTOR_WRITER.skill_slots if slot.is_enabled}
    assert "skill_de_ai_if_y" in writer_skill_ids
    assert "de_ai" in (DIRECTOR_WRITER.default_skill_order or [])
    assert (DIRECTOR_WRITER.default_skill_order or []).index("de_ai") < (DIRECTOR_WRITER.default_skill_order or []).index("primary")


def test_de_ai_natural_prose_rule_is_core_system_rule():
    from app.data.web_novel_writing_rules import WEB_NOVEL_RULE_SETS, WEB_NOVEL_WRITING_RULES

    rules_by_id = {rule["id"]: rule for rule in WEB_NOVEL_WRITING_RULES}
    rule = rules_by_id["style_de_ai_natural_prose"]

    assert rule["severity"] == "required"
    assert rule["application_mode"] == "always_postcheck"
    assert "去AI感" in rule["tags"]
    assert "模板化" in rule["content"]
    assert "解释腔" in rule["content"]
    assert "大纲不是正文" in rule["content"]
    assert "恒星塞进了他的颅腔" in rule["content"]
    assert "记忆碎片" in rule["examples"][2]
    assert "大纲转场景" in rule["examples"][2]

    sets_by_id = {rule_set["id"]: rule_set for rule_set in WEB_NOVEL_RULE_SETS}
    assert "style_de_ai_natural_prose" in sets_by_id["rule_set_web_novel_basics"]["rule_ids"]
    assert "style_de_ai_natural_prose" in sets_by_id["rule_set_web_novel_advanced"]["rule_ids"]


def test_evaluator_chapter_end_schema_tracks_outline_transposition_check():
    from app.models.agent_output_schemas import EvaluatorChapterEndSchema

    data = {
        "should_end": False,
        "reason": "需要修订",
        "pacing_check": {"is_appropriate": False, "note": "像梗概扩写"},
        "long_term_check": {"has_room_for_future": True, "note": "仍有空间"},
        "world_consistency_check": {"is_consistent": True, "issues": []},
        "scores": {"info_gain": 6, "suspense": 4, "pacing": 4, "completeness": 6, "world_consistency": 8},
        "outline_transposition_check": {
            "passed": False,
            "issues": ["大纲节点被直接扩写为旁白"],
            "copied_outline_phrases": ["记忆碎片"],
            "missing_scene_grounding": ["警告符号没有场景触发"],
            "rewrite_focus": ["从身体反应和设备异常进入"],
        },
    }

    parsed = EvaluatorChapterEndSchema.model_validate(data)

    assert parsed.outline_transposition_check.passed is False
    assert parsed.outline_transposition_check.copied_outline_phrases == ["记忆碎片"]
    assert parsed.outline_transposition_check.rewrite_focus == ["从身体反应和设备异常进入"]


def test_master_scene_and_revision_schemas_validate_runtime_artifacts():
    from app.models.agent_output_schemas import (
        EvaluatorChapterEndSchema,
        MasterPlotterWritingPlanSchema,
        MasterRevisionDirectiveSchema,
        MasterScenePlanSchema,
    )

    scene_plan = MasterScenePlanSchema.model_validate({
        "plan_id": "plan-1",
        "chapter_intent": "让主角通过可见异常进入大纲事件",
        "core_conflict": "是否触碰异常设备",
        "scene_plan": [{
            "beat_id": "beat-1",
            "sequence_index": 1,
            "purpose": "设备异常触发",
            "cause": "前文留下未解释信号",
            "trigger": "屏幕断帧",
            "character_action": "主角伸手断电",
            "sensory_or_environment_feedback": ["耳鸣", "灯管闪烁"],
            "visible_result": "设备烧出黑痕",
            "information_release": ["只释放坐标片段"],
            "transition_to_next": "保安敲门",
            "acceptance_criteria": ["正文必须出现可见设备后果"],
        }],
        "writer_brief": {"must_follow": ["不要直接复述大纲"]},
        "evaluator_checklist": {"required_beat_ids": ["beat-1"]},
    })
    directive = MasterRevisionDirectiveSchema.model_validate({
        "revision_id": "rev-1",
        "revision_attempt": 1,
        "rewrite_strategy": "scene_rewrite",
        "issues": [{
            "issue_id": "issue-1",
            "failure_type": "outline_transposition",
            "severity": "blocking",
            "failed_scene_beat_ids": ["beat-1"],
            "required_fix": "把旁白改为动作和后果",
        }],
        "writer_revision_brief": {"scope": "beat-1"},
        "evaluator_focus": ["beat-1 是否场景化"],
    })
    legacy_plan = MasterPlotterWritingPlanSchema.model_validate({
        "writing_plan": {"chapter_focus": "焦点", "opening": "承接", "middle_beats": [], "ending": "钩子", "target_word_count": 2000},
        "master_scene_plan": scene_plan.model_dump(),
        "scene_plan": scene_plan.scene_plan,
        "writer_brief": scene_plan.writer_brief,
        "evaluator_checklist": scene_plan.evaluator_checklist,
    })
    evaluator = EvaluatorChapterEndSchema.model_validate({
        "should_end": False,
        "reason": "需要修订",
        "pacing_check": {"is_appropriate": False, "note": "缺 beat"},
        "long_term_check": {"has_room_for_future": True, "note": "可修订"},
        "world_consistency_check": {"is_consistent": True, "issues": []},
        "scores": {"info_gain": 4, "suspense": 4, "pacing": 4, "completeness": 4, "world_consistency": 8},
        "scene_plan_adherence_check": {"passed": False, "covered_beat_ids": [], "missing_beat_ids": ["beat-1"], "failed_beat_ids": ["beat-1"], "issues": ["缺 beat"]},
        "revision_directive_adherence_check": {"passed": False, "resolved_issue_ids": [], "unresolved_issue_ids": ["issue-1"], "issues": ["未修复"]},
        "failed_scene_beat_ids": ["beat-1"],
        "scene_coverage": {"required_beat_count": 1, "covered_beat_count": 0},
    })

    assert scene_plan.scene_plan[0].beat_id == "beat-1"
    assert directive.issues[0].failed_scene_beat_ids == ["beat-1"]
    assert legacy_plan.master_scene_plan.plan_id == "plan-1"
    assert evaluator.scene_plan_adherence_check.missing_beat_ids == ["beat-1"]
    assert evaluator.revision_directive_adherence_check.unresolved_issue_ids == ["issue-1"]


def test_writer_style_consistency_template_is_scenario_specific():
    from app.data.system_agent_templates import SYSTEM_AGENT_TEMPLATES, WRITER_STYLE_CONSISTENCY

    prompt_ids = {slot.prompt_template_id for slot in WRITER_STYLE_CONSISTENCY.prompt_slots if slot.prompt_template_id}

    assert WRITER_STYLE_CONSISTENCY in SYSTEM_AGENT_TEMPLATES
    assert WRITER_STYLE_CONSISTENCY.id == "director_writer_style_consistency"
    assert WRITER_STYLE_CONSISTENCY.agent_type.value == "writer"
    assert WRITER_STYLE_CONSISTENCY.scenario == "style_consistency_check"
    assert "function_writer_style_consistency" in prompt_ids
    assert "function_writer_segment_generation" not in prompt_ids
    assert "style_consistency" in WRITER_STYLE_CONSISTENCY.default_prompt_order
    assert "writing_rules" in WRITER_STYLE_CONSISTENCY.default_prompt_order


@pytest.mark.asyncio
async def test_writer_style_consistency_runtime_trace_does_not_use_template_fallback():
    from app.data.system_agent_templates import WRITER_STYLE_CONSISTENCY
    from app.services.agent_prompt_service import AgentPromptService

    service = AgentPromptService()
    result = await service.build_agent_prompt_with_trace(
        agent_type="writer",
        project_id="project-1",
        variables={"scenario": "style_consistency_check"},
        scenario="style_consistency_check",
        resolved_template=WRITER_STYLE_CONSISTENCY,
        include_skills=False,
        use_project_config=False,
    )
    trace = result["trace"]

    assert "function_writer_style_consistency" in trace["prompt_ids"]
    assert "function_writer_segment_generation" not in trace["prompt_ids"]
    assert trace["template_id"] == "director_writer_style_consistency"
    assert trace["template_scenario"] == "style_consistency_check"
    assert trace["fallbacks_used"] == []
    assert trace["deprecated_sources_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


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
async def test_shared_de_ai_rule_is_forced_for_writer_and_evaluator_when_rag_misses(monkeypatch):
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
    for agent_type, scenario in [
        ("writer", "workflow_chapter_generation"),
        ("writer", "rewrite_by_review"),
        ("evaluator", "chapter_quality_review"),
    ]:
        result = await service.build_writing_rules_prompt_with_trace(
            project_id="project-1",
            context={"query": "没有语义检索结果"},
            agent_type=agent_type,
            scenario=scenario,
        )

        assert "## 共享去AI感自然文风规则" in result["content"]
        assert "style_de_ai_natural_prose" in result["content"]
        assert "模板化" in result["content"]
        assert AgentPromptService.SHARED_DE_AI_RULE_IDS.issubset(set(result["trace"]["writing_rule_ids"]))
        assert set(result["trace"]["shared_de_ai_rule_ids"]) == AgentPromptService.SHARED_DE_AI_RULE_IDS
        assert result["trace"]["missing_shared_de_ai_rule_ids"] == []
        assert any(rule["reason"] == "shared_de_ai_core" for rule in result["trace"]["retrieved_rules"])


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
        self.query_results = []

    async def execute_write(self, query, params=None):
        self.writes.append({"query": query, "params": params or {}})

    async def execute_query(self, query, params=None):
        return list(self.query_results)


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
async def test_skill_md_sync_deletes_stale_md_skills_from_cache_and_db():
    from app.models.skill import Skill, SkillCategory, SkillType
    from app.services.skill_service import SkillService

    db = MdSyncFakeDb()
    db.query_results = [{"id": "skill_stale_md"}, {"id": "skill_current_md"}]
    service = SkillService(db=db)
    service._skills_cache["skill_stale_md"] = Skill(
        id="skill_stale_md",
        name="Stale MD Skill",
        description="Removed md skill",
        skill_type=SkillType.PROMPT,
        category=SkillCategory.WRITING,
        prompt_template="stale body",
    )
    service._skills_cache["skill_current_md"] = Skill(
        id="skill_current_md",
        name="Current MD Skill",
        description="Synced md skill",
        skill_type=SkillType.PROMPT,
        category=SkillCategory.WRITING,
        prompt_template="current body",
    )

    await service._delete_stale_md_skills({"skill_current_md"})

    assert "skill_stale_md" not in service._skills_cache
    assert "skill_current_md" in service._skills_cache
    deleted_params = [write["params"] for write in db.writes if write["params"].get("id") == "skill_stale_md"]
    assert len(deleted_params) == 2
    assert any("DELETE FROM skill_assignments" in write["query"] for write in db.writes)
    assert any("DELETE FROM skills" in write["query"] for write in db.writes)


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
    "md_asset_prompt_ids",
    "system_seed_prompt_ids",
    "deprecated_prompt_ids",
    "unresolved_md_asset_prompt_ids",
    "templates",
}

AUDIT_LIST_KEYS = (
    "resolved_prompt_ids",
    "missing_prompt_ids",
    "md_asset_prompt_ids",
    "system_seed_prompt_ids",
    "deprecated_prompt_ids",
    "unresolved_md_asset_prompt_ids",
    "templates",
)

AUDIT_TEMPLATE_REQUIRED_KEYS = {
    "template_id",
    "agent_type",
    "scenario",
    "prompt_ids",
    "missing_prompt_ids",
    "md_asset_prompt_ids",
    "system_seed_prompt_ids",
    "deprecated_prompt_ids",
    "unresolved_md_asset_prompt_ids",
    "fallbacks_used",
    "deprecated_sources_used",
}

AUDIT_TEMPLATE_LIST_KEYS = (
    "prompt_ids",
    "missing_prompt_ids",
    "md_asset_prompt_ids",
    "system_seed_prompt_ids",
    "deprecated_prompt_ids",
    "unresolved_md_asset_prompt_ids",
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


def test_agent_prompt_service_get_agent_template_accepts_agent_type_string():
    from app.data.system_agent_templates import DIRECTOR_WRITER
    from app.services.agent_prompt_service import AgentPromptService

    service = AgentPromptService()

    assert service.get_agent_template("writer") is DIRECTOR_WRITER


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
async def test_evaluator_missing_config_prompt_fails_closed_for_project_runtime(monkeypatch):
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
    with pytest.raises(Exception, match="Evaluator prompt configuration is missing"):
        await evaluator._get_evaluator_config_prompt({"task_type": "ooc_review"})

    trace = evaluator.get_system_prompt_render_trace()
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
async def test_evaluator_deterministic_confirmed_prior_state_gate_ignores_rejected_changes(monkeypatch):
    from app.agents.evaluator import EvaluatorAgent
    from app.models.agent_output_schemas import EvaluatorChapterEndSchema

    class FakePromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            return {
                "content": "Evaluator runtime prompt",
                "trace": _trace("evaluator", kwargs["scenario"]),
            }

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakePromptService(),
    )

    evaluator = EvaluatorAgent(project_id="project-1")

    async def fake_call_structured(schema, messages, temperature=0.0, category=None):
        assert schema is EvaluatorChapterEndSchema
        prompt_text = messages[0].content
        assert "已确认前文章节状态包" in prompt_text
        assert "废弃设定不应进入状态包" not in prompt_text
        return EvaluatorChapterEndSchema(
            should_end=True,
            quality_passed=True,
            score=8.0,
            reason="模型初判通过",
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
            "chapter_content": "正文沿用一个已拒绝废弃设定，但没有否定任何已确认状态。",
            "confirmed_prior_state_packet": {
                "confirmed_state_changes": [],
                "open_proposed_changes": [],
            },
        }
    )

    assert result.success is True
    data = result.structured_data
    assert data["quality_passed"] is True
    assert data["should_end"] is True
    assert data["confirmed_prior_state_check"]["passed"] is True
    assert data["confirmed_prior_state_check"]["issues"] == []
    assert_render_trace_contract(result.metadata["prompt_render_trace"])


@pytest.mark.asyncio
async def test_evaluator_deterministic_confirmed_prior_state_gate_blocks_continuity_conflict(monkeypatch):
    from app.agents.evaluator import EvaluatorAgent
    from app.models.agent_output_schemas import EvaluatorChapterEndSchema

    class FakePromptService:
        async def build_agent_prompt_with_trace(self, **kwargs):
            return {
                "content": "Evaluator runtime prompt",
                "trace": _trace("evaluator", kwargs["scenario"]),
            }

    monkeypatch.setattr(
        "app.services.agent_prompt_service.get_agent_prompt_service",
        lambda: FakePromptService(),
    )

    evaluator = EvaluatorAgent(project_id="project-1")

    async def fake_call_structured(schema, messages, temperature=0.0, category=None):
        assert schema is EvaluatorChapterEndSchema
        assert "已确认前文章节状态包" in messages[0].content
        return EvaluatorChapterEndSchema(
            should_end=True,
            quality_passed=True,
            score=8.0,
            reason="模型初判通过",
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
            "chapter_content": "正文却写主角没有获得星砂印记，并把星门失稳仍是待确认提示当成已经发生的正史。",
            "confirmed_prior_state_packet": {
                "confirmed_state_changes": [
                    {
                        "id": "state-applied",
                        "status": "applied",
                        "entity_type": "plot",
                        "summary": "主角已获得星砂印记，这是下一章必须尊重的已确认剧情状态。",
                    }
                ],
                "open_proposed_changes": [
                    {
                        "id": "state-proposed",
                        "status": "proposed",
                        "entity_type": "world",
                        "summary": "星门失稳仍是待确认提示，下一章不得当作正史。",
                    }
                ],
            },
        }
    )

    assert result.success is True
    data = result.structured_data
    assert data["quality_passed"] is False
    assert data["should_end"] is False
    assert any("正文疑似否定已确认前文状态" in issue for issue in data["issues"])
    assert data["confirmed_prior_state_check"]["passed"] is False
    assert any("待确认状态" in issue for issue in data["upstream_context_usage_check"]["issues"])
    assert_render_trace_contract(result.metadata["prompt_render_trace"])


def test_evaluator_task_prompts_use_md_assets_for_stable_rules(monkeypatch):
    from app.agents.evaluator import EvaluatorAgent

    evaluator = EvaluatorAgent(project_id="project-1")
    loaded_prompt_ids = []

    prompt_assets = {
        "function_evaluator_chapter_quality_gate": "md evaluator chapter gate rules\nAI感文风 Gate\nde_ai_style_check",
        "function_evaluator_reader_simulation": "md evaluator reader simulation rules\nAI 腔与模板化总结检查",
        "function_evaluator_ooc_review": "md evaluator ooc review rules",
    }

    def fake_load(prompt_id):
        loaded_prompt_ids.append(prompt_id)
        return prompt_assets[prompt_id]

    monkeypatch.setattr(evaluator, "_load_md_prompt_content", fake_load)

    chapter_prompt = evaluator._format_evaluator_task_prompt(
        evaluator._evaluator_task_title("chapter_end"),
        [("当前章节数据", {"word_count": 1200, "chapter_content": "正文"})],
        output_schema=evaluator._evaluator_task_schema(
            "chapter_end",
            word_count=1200,
            target_word_count=1500,
        ),
        task_notes=evaluator._evaluator_task_notes(
            "chapter_end",
            ["当前运行时目标：输出 EvaluatorChapterEndSchema。"],
        ),
        config_prompt="Evaluator runtime prompt",
    )
    reader_prompt = evaluator._format_evaluator_task_prompt(
        evaluator._evaluator_task_title("reader_simulate"),
        [("章节内容", "正文")],
        output_schema=evaluator._evaluator_task_schema("reader_simulate"),
        task_notes=evaluator._evaluator_task_notes(
            "reader_simulate",
            ["当前运行时目标：输出 EvaluatorReaderSimulateSchema。"],
        ),
        config_prompt="Evaluator runtime prompt",
    )
    ooc_prompt = evaluator._format_evaluator_task_prompt(
        evaluator._evaluator_task_title("ooc_review"),
        [("待审查台词", "我必须守住秘密")],
        output_schema=evaluator._evaluator_task_schema("ooc_review"),
        task_notes=evaluator._evaluator_task_notes(
            "ooc_review",
            ["当前运行时目标：输出 EvaluatorOOCSchema。"],
        ),
        config_prompt="Evaluator runtime prompt",
    )

    assert loaded_prompt_ids == [
        "function_evaluator_chapter_quality_gate",
        "function_evaluator_reader_simulation",
        "function_evaluator_ooc_review",
    ]
    assert "md evaluator chapter gate rules" in chapter_prompt
    assert "AI感文风 Gate" in chapter_prompt
    assert "de_ai_style_check" in chapter_prompt
    assert "outline_transposition_check" in evaluator._evaluator_task_schema("chapter_end", word_count=1200, target_word_count=1500)
    assert "scene_plan_adherence_check" in evaluator._evaluator_task_schema("chapter_end", word_count=1200, target_word_count=1500)
    assert "revision_directive_adherence_check" in evaluator._evaluator_task_schema("chapter_end", word_count=1200, target_word_count=1500)
    assert "failed_scene_beat_ids" in evaluator._evaluator_task_schema("chapter_end", word_count=1200, target_word_count=1500)
    assert "de_ai_style_check" in evaluator._evaluator_task_schema("chapter_end", word_count=1200, target_word_count=1500)
    assert "md evaluator reader simulation rules" in reader_prompt
    assert "AI 腔与模板化总结检查" in reader_prompt
    assert "md evaluator ooc review rules" in ooc_prompt
    for prompt in (chapter_prompt, reader_prompt, ooc_prompt):
        assert "Evaluator runtime prompt" in prompt
        assert "【输出 JSON Schema】" in prompt
    assert "当前运行时目标：输出 EvaluatorChapterEndSchema。" in chapter_prompt
    assert "当前运行时目标：输出 EvaluatorReaderSimulateSchema。" in reader_prompt
    assert "当前运行时目标：输出 EvaluatorOOCSchema。" in ooc_prompt
    assert "稳定评估规则以 md prompt 资产 function_evaluator_chapter_quality_gate 为准。" in chapter_prompt
    assert "Master 场景计划" in chapter_prompt
    assert "scene_plan_adherence_check" in chapter_prompt
    assert "revision_directive_adherence_check" in chapter_prompt
    assert "outline_transposition_check" in evaluator._evaluator_task_schema("chapter_end", word_count=1200, target_word_count=1500)
    assert "必须以 Agent Template / md prompt / writing-rules 中的门禁为准。" not in chapter_prompt
    assert "确定性 role_performance_gate 问题必须写入" not in reader_prompt
    assert "确定性角色约束预检问题必须作为阻断问题写入" not in ooc_prompt


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

    async def fake_resolve(prompt_id):
        if prompt_id == prompt_template.id:
            return {"template": prompt_template, "source": "prompt_template_service"}
        return {"template": None, "source": "missing"}

    monkeypatch.setattr(prompt_module, "SYSTEM_AGENT_TEMPLATES", [template])
    monkeypatch.setattr(service, "_resolve_prompt_template_with_source", fake_resolve)

    audit = await service.audit_system_agent_template_prompt_resolution()

    assert_prompt_resolution_audit_contract(audit)
    assert audit["template_count"] == 1
    assert audit["slot_count"] == 2
    assert audit["resolved_prompt_ids"] == ["prompt_existing"]
    assert audit["missing_prompt_ids"] == ["prompt_missing"]
    assert audit["md_asset_prompt_ids"] == []
    assert audit["system_seed_prompt_ids"] == []
    assert audit["deprecated_prompt_ids"] == []
    assert audit["unresolved_md_asset_prompt_ids"] == []
    assert audit["templates"][0]["prompt_ids"] == ["prompt_existing"]
    assert audit["templates"][0]["missing_prompt_ids"] == ["prompt_missing"]
    assert audit["templates"][0]["md_asset_prompt_ids"] == []
    assert audit["templates"][0]["system_seed_prompt_ids"] == []
    assert audit["templates"][0]["deprecated_prompt_ids"] == []
    assert audit["templates"][0]["unresolved_md_asset_prompt_ids"] == []
    assert audit["templates"][0]["fallbacks_used"] == ["missing_prompt_template:prompt_missing"]


@pytest.mark.asyncio
async def test_system_agent_template_prompt_resolution_audit_reports_md_and_seed_sources(monkeypatch):
    from app.models.agent_template import AgentTemplate, AgentType, PromptSlot
    from app.models.prompt_template import PromptCategory, PromptTemplate
    from app.services.agent_prompt_service import AgentPromptService
    import app.services.agent_prompt_service as prompt_module

    template = AgentTemplate(
        id="audit-source-template",
        name="Audit Source Template",
        agent_type=AgentType.SETTING,
        scenario="resource_management",
        prompt_slots=[
            PromptSlot(slot_name="md", prompt_template_id="prompt_md", priority=100),
            PromptSlot(slot_name="seed", prompt_template_id="prompt_seed", priority=90),
        ],
    )
    md_prompt = PromptTemplate(id="prompt_md", name="MD Prompt", category=PromptCategory.FUNCTION, content="MD")
    seed_prompt = PromptTemplate(id="prompt_seed", name="Seed Prompt", category=PromptCategory.FUNCTION, content="Seed")

    service = AgentPromptService()

    async def fake_resolve(prompt_id):
        if prompt_id == "prompt_md":
            return {"template": md_prompt, "source": "md_asset"}
        if prompt_id == "prompt_seed":
            return {"template": seed_prompt, "source": "system_seed"}
        return {"template": None, "source": "missing"}

    monkeypatch.setattr(prompt_module, "SYSTEM_AGENT_TEMPLATES", [template])
    monkeypatch.setattr(service, "_resolve_prompt_template_with_source", fake_resolve)

    audit = await service.audit_system_agent_template_prompt_resolution()

    assert_prompt_resolution_audit_contract(audit)
    assert audit["md_asset_prompt_ids"] == ["prompt_md"]
    assert audit["system_seed_prompt_ids"] == ["prompt_seed"]
    assert audit["deprecated_prompt_ids"] == ["prompt_seed"]
    assert audit["unresolved_md_asset_prompt_ids"] == []
    template_result = audit["templates"][0]
    assert template_result["md_asset_prompt_ids"] == ["prompt_md"]
    assert template_result["system_seed_prompt_ids"] == ["prompt_seed"]
    assert template_result["deprecated_prompt_ids"] == ["prompt_seed"]
    assert template_result["unresolved_md_asset_prompt_ids"] == []
    assert template_result["fallbacks_used"] == [
        "prompt_template_md_asset:prompt_md",
        "prompt_template_system_seed:prompt_seed",
    ]
    assert template_result["deprecated_sources_used"] == ["system_prompt_seed:prompt_seed"]


@pytest.mark.asyncio
async def test_system_agent_template_prompt_resolution_audit_reports_unresolved_md_assets(monkeypatch):
    from app.models.agent_template import AgentTemplate, AgentType, PromptSlot
    from app.models.prompt_template import PromptCategory, PromptTemplate
    from app.services.agent_prompt_service import AgentPromptService
    import app.services.agent_prompt_service as prompt_module

    template = AgentTemplate(
        id="audit-unresolved-md-template",
        name="Audit Unresolved MD Template",
        agent_type=AgentType.MASTER_PLOTTER,
        scenario="workflow_plot_planning",
        prompt_slots=[
            PromptSlot(slot_name="md-only", prompt_template_id="prompt_md_only", priority=100),
            PromptSlot(slot_name="missing", prompt_template_id="prompt_missing", priority=90),
        ],
    )
    md_prompt = PromptTemplate(id="prompt_md_only", name="MD Only", category=PromptCategory.FUNCTION, content="MD only")

    service = AgentPromptService()

    async def fake_resolve(prompt_id):
        return {"template": None, "source": "missing"}

    def fake_build_from_md(prompt_id):
        if prompt_id == "prompt_md_only":
            return md_prompt
        return None

    monkeypatch.setattr(prompt_module, "SYSTEM_AGENT_TEMPLATES", [template])
    monkeypatch.setattr(service, "_resolve_prompt_template_with_source", fake_resolve)
    monkeypatch.setattr(service, "_build_prompt_template_from_md", fake_build_from_md)

    audit = await service.audit_system_agent_template_prompt_resolution()

    assert_prompt_resolution_audit_contract(audit)
    assert audit["missing_prompt_ids"] == ["prompt_md_only", "prompt_missing"]
    assert audit["unresolved_md_asset_prompt_ids"] == ["prompt_md_only"]
    template_result = audit["templates"][0]
    assert template_result["missing_prompt_ids"] == ["prompt_md_only", "prompt_missing"]
    assert template_result["unresolved_md_asset_prompt_ids"] == ["prompt_md_only"]
    assert template_result["fallbacks_used"] == [
        "prompt_template_md_asset_unresolved:prompt_md_only",
        "missing_prompt_template:prompt_missing",
    ]


@pytest.mark.asyncio
async def test_skill_orchestrator_decision_prompt_uses_md_asset(monkeypatch):
    from app.models.skill import Skill, SkillCategory, SkillType
    from app.services.skill_orchestrator import OrchestrationContext, SkillOrchestrator

    class FakeMdService:
        def get_prompt(self, prompt_id):
            assert prompt_id == "function_skill_orchestration_decision"
            return {"content": "md orchestration decision rules"}

    monkeypatch.setattr(
        "app.services.skill_orchestrator.get_md_file_service",
        lambda: FakeMdService(),
    )

    orchestrator = SkillOrchestrator(llm_client=object())
    context = OrchestrationContext(
        agent_type="writer",
        initial_goal="完成章节补写",
        current_iteration=2,
        max_iterations=5,
        variables={"chapter_goal": "推进局部冲突"},
    )
    skills = [
        Skill(
            id="skill_continue_writing",
            name="续写",
            description="根据已有内容继续写作",
            skill_type=SkillType.PROMPT,
            category=SkillCategory.WRITING,
        )
    ]

    captured = {}

    async def fake_call_llm(prompt):
        captured["prompt"] = prompt
        return '{"action":"finish","reason":"已完成","should_continue":false}'

    monkeypatch.setattr(orchestrator, "_call_llm", fake_call_llm)

    decision = await orchestrator._get_llm_decision(context, skills)

    assert decision.action == "finish"
    assert "md orchestration decision rules" in captured["prompt"]
    assert "## 任务目标\n完成章节补写" in captured["prompt"]
    assert "## 可用技能" in captured["prompt"]
    assert "根据当前任务状态，决定下一步应该调用哪个技能" not in captured["prompt"]

    prompt_result = orchestrator._build_decision_prompt_with_trace(
        context=context,
        skills_desc=orchestrator._build_skills_description(skills),
        context_desc=orchestrator._build_context_description(context),
    )
    assert prompt_result["trace"] == {
        "source": "md_prompt_asset",
        "prompt_ids": ["function_skill_orchestration_decision"],
        "fallbacks_used": [],
        "deprecated_sources_used": [],
        "missing_prompt_ids": [],
    }


def test_skill_orchestrator_decision_prompt_trace_reports_deprecated_fallback(monkeypatch):
    from app.services.skill_orchestrator import OrchestrationContext, SkillOrchestrator

    class EmptyMdService:
        def get_prompt(self, prompt_id):
            assert prompt_id == "function_skill_orchestration_decision"
            return None

    monkeypatch.setattr(
        "app.services.skill_orchestrator.get_md_file_service",
        lambda: EmptyMdService(),
    )

    orchestrator = SkillOrchestrator(llm_client=object())
    context = OrchestrationContext(agent_type="writer", initial_goal="完成章节补写")
    prompt_result = orchestrator._build_decision_prompt_with_trace(
        context=context,
        skills_desc="- skill",
        context_desc="- state",
    )

    assert prompt_result["content"].startswith("# Skill 编排决策")
    assert prompt_result["trace"] == {
        "source": "deprecated_minimal_fallback",
        "prompt_ids": ["function_skill_orchestration_decision"],
        "fallbacks_used": ["skill_orchestration_deprecated_minimal_fallback:function_skill_orchestration_decision"],
        "deprecated_sources_used": ["SkillOrchestrator._build_decision_prompt"],
        "missing_prompt_ids": ["function_skill_orchestration_decision"],
    }


def test_skill_retrieval_decision_prompt_uses_md_asset(monkeypatch):
    from app.models.skill import Skill, SkillCategory, SkillType
    from app.services.skill_retrieval import SkillCandidate, SkillRetrievalService

    class FakeMdService:
        def get_prompt(self, prompt_id):
            assert prompt_id == "function_skill_retrieval_decision"
            return {"content": "md retrieval decision rules"}

    monkeypatch.setattr(
        "app.services.skill_retrieval.get_md_file_service",
        lambda: FakeMdService(),
    )

    service = SkillRetrievalService(llm_client=object())
    skill = Skill(
        id="skill_scene_dialogue",
        name="场景对话",
        description="生成角色对话",
        skill_type=SkillType.PROMPT,
        category=SkillCategory.DIALOGUE,
    )

    candidates = [SkillCandidate(skill=skill, similarity_score=0.87)]
    prompt = service._build_decision_prompt("需要增强角色对话", candidates)

    assert "md retrieval decision rules" in prompt
    assert "## 用户场景描述\n需要增强角色对话" in prompt
    assert "skill_scene_dialogue" in prompt
    assert "根据用户的场景描述，从候选技能中选择最合适的技能" not in prompt

    prompt_result = service._build_decision_prompt_with_trace("需要增强角色对话", candidates)
    assert prompt_result["trace"] == {
        "source": "md_prompt_asset",
        "prompt_ids": ["function_skill_retrieval_decision"],
        "fallbacks_used": [],
        "deprecated_sources_used": [],
        "missing_prompt_ids": [],
    }


def test_skill_retrieval_decision_prompt_trace_reports_deprecated_fallback(monkeypatch):
    from app.models.skill import Skill, SkillCategory, SkillType
    from app.services.skill_retrieval import SkillCandidate, SkillRetrievalService

    class EmptyMdService:
        def get_prompt(self, prompt_id):
            assert prompt_id == "function_skill_retrieval_decision"
            return None

    monkeypatch.setattr(
        "app.services.skill_retrieval.get_md_file_service",
        lambda: EmptyMdService(),
    )

    service = SkillRetrievalService(llm_client=object())
    skill = Skill(
        id="skill_scene_dialogue",
        name="场景对话",
        description="生成角色对话",
        skill_type=SkillType.PROMPT,
        category=SkillCategory.DIALOGUE,
    )
    prompt_result = service._build_decision_prompt_with_trace(
        "需要增强角色对话",
        [SkillCandidate(skill=skill, similarity_score=0.87)],
    )

    assert prompt_result["content"].startswith("# Skill 检索决策")
    assert prompt_result["trace"] == {
        "source": "deprecated_minimal_fallback",
        "prompt_ids": ["function_skill_retrieval_decision"],
        "fallbacks_used": ["skill_retrieval_deprecated_minimal_fallback:function_skill_retrieval_decision"],
        "deprecated_sources_used": ["SkillRetrievalService._build_decision_prompt"],
        "missing_prompt_ids": ["function_skill_retrieval_decision"],
    }


def test_director_auto_write_prompt_uses_md_asset(monkeypatch):
    from app.services.director import DirectorSystem

    class FakeMdService:
        def get_prompt(self, prompt_id):
            assert prompt_id == "function_director_auto_write"
            return {"content": "md director auto-write rules"}

    monkeypatch.setattr(
        "app.services.director.get_md_file_service",
        lambda: FakeMdService(),
    )

    director = DirectorSystem({"id": "world-1", "name": "测试世界", "description": "世界说明"}, project_id="project-1")
    prompt, trace = director._build_auto_write_prompt(
        chapter_title="第一章",
        chapter_goal="完成局部冲突",
        characters_info=[{"name": "甲", "role": "主角", "description": "谨慎"}],
        world_info={"name": "测试世界", "description": "世界说明"},
        target_word_count=1200,
        style_reference="简洁",
    )

    assert "md director auto-write rules" in prompt
    assert "【章节标题】\n第一章" in prompt
    assert "【主要角色】" in prompt
    assert "展示而非告知 (Show, Don't Tell)" not in prompt
    assert trace["agent_type"] == "director"
    assert trace["scenario"] == "director_auto_write"
    assert trace["project_id"] == "project-1"
    assert trace["prompt_ids"] == ["function_director_auto_write"]
    assert trace["fallbacks_used"] == []
    assert trace["missing_prompt_ids"] == []
    assert_render_trace_contract(trace)


def test_director_auto_write_missing_prompt_asset_fails_closed_for_project(monkeypatch):
    from app.services.director import DirectorSystem

    class EmptyMdService:
        def get_prompt(self, prompt_id):
            return None

    monkeypatch.setattr(
        "app.services.director.get_md_file_service",
        lambda: EmptyMdService(),
    )

    director = DirectorSystem({"id": "world-1", "name": "测试世界"}, project_id="project-1")
    with pytest.raises(RuntimeError, match="Director auto-write prompt asset is missing"):
        director._build_auto_write_prompt(
            chapter_title="第一章",
            chapter_goal="完成局部冲突",
            characters_info=[],
            world_info={"name": "测试世界"},
            target_word_count=1200,
            style_reference=None,
        )


@pytest.mark.asyncio
async def test_master_plotter_forced_event_failure_uses_deterministic_low_intrusion_fallback(monkeypatch):
    from app.agents.director.master_plotter import MasterPlotterAgent

    agent = MasterPlotterAgent(system_prompt="system")
    async def fake_config_prompt(*args, **kwargs):
        return "md forced event rules"

    monkeypatch.setattr(agent, "_get_master_plotter_config_prompt", fake_config_prompt)

    async def broken_call_llm(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(agent, "_call_llm", broken_call_llm)

    first = await agent._generate_forced_event([], [])
    second = await agent._generate_forced_event(["旧事件"], [{"title": "伏笔"}])

    assert first == "周围环境出现异常动静，迫使众人立刻确认情况"
    assert second == first
    assert "远处传来异常动静" != first


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
                "md_asset_prompt_ids": [],
                "system_seed_prompt_ids": [],
                "deprecated_prompt_ids": [],
                "unresolved_md_asset_prompt_ids": [],
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


def test_outline_version_api_routes_require_explicit_revision_selection(monkeypatch):
    from app.api.app import create_app
    from app.models.chapter_outline import ChapterOutline, ChapterOutlineStatus
    from app.services.plot_outline_service import PlotOutlineService, set_plot_outline_service

    service = PlotOutlineService()
    approved = ChapterOutline(
        id="outline-approved",
        project_id="project-1",
        chapter_number=3,
        title="原审批标题",
        summary="原审批摘要",
        status=ChapterOutlineStatus.APPROVED,
    )
    revision = ChapterOutline(
        id="outline-revision",
        project_id="project-1",
        chapter_number=3,
        title="修订标题",
        summary="修订摘要",
        status=ChapterOutlineStatus.REVISION,
        previous_outline_id=approved.id,
    )
    service._outlines_cache[approved.id] = approved
    service._outlines_cache[revision.id] = revision
    service._loaded_outline_projects.add("project-1")
    monkeypatch.setattr(service, "_persist_outline_resource_audit", AsyncMock())
    set_plot_outline_service(service)

    try:
        client = TestClient(create_app())

        exact_response = client.get("/api/outlines/by-id/outline-revision?project_id=project-1")
        assert exact_response.status_code == 200
        assert exact_response.json()["id"] == "outline-revision"
        assert exact_response.json()["status"] == "revision"

        versions_response = client.get("/api/outlines/3/versions?project_id=project-1")
        assert versions_response.status_code == 200
        versions = versions_response.json()
        assert versions["current_approved"]["id"] == "outline-approved"
        assert [outline["id"] for outline in versions["pending_revisions"]] == ["outline-revision"]
        assert [outline["id"] for outline in versions["versions"]] == ["outline-approved", "outline-revision"]

        legacy_approve_response = client.post(
            "/api/outlines/3/approve?project_id=project-1",
            json={"approved_by": "reviewer"},
        )
        assert legacy_approve_response.status_code == 409
        legacy_detail = legacy_approve_response.json()["detail"]
        assert legacy_detail["code"] == "outline_revision_selection_required"
        assert legacy_detail["pending_revision_ids"] == ["outline-revision"]
        assert legacy_detail["current_approved_id"] == "outline-approved"

        reject_response = client.post("/api/outlines/by-id/outline-revision/reject?project_id=project-1", json={})
        assert reject_response.status_code == 200
        assert reject_response.json()["status"] == "rejected"
        assert approved.status == ChapterOutlineStatus.APPROVED
        assert revision.status == ChapterOutlineStatus.REJECTED

        rejected_versions_response = client.get("/api/outlines/3/versions?project_id=project-1")
        assert rejected_versions_response.status_code == 200
        rejected_versions = rejected_versions_response.json()
        assert rejected_versions["pending_revisions"] == []
        assert [outline["id"] for outline in rejected_versions["rejected_revisions"]] == ["outline-revision"]
    finally:
        set_plot_outline_service(None)


@pytest.mark.asyncio
async def test_plot_outline_soft_delete_excludes_stale_versions_and_forces_context_rebuild(monkeypatch):
    from app.models.chapter_outline import ChapterOutline, ChapterOutlineStatus
    from app.services.plot_outline_service import PlotOutlineService

    class FakeDB:
        def __init__(self):
            self.rows = [
                {
                    "id": "outline-old",
                    "project_id": "project-1",
                    "chapter_number": 1,
                    "title": "数据幽影",
                    "summary": "旧主角林墨的已删除版本。",
                    "status": "approved",
                    "scenes": [],
                    "chapter_goals": [],
                    "character_arcs": {},
                    "hooks_planted": [],
                    "hooks_resolved": [],
                    "quality_metrics": {},
                    "target_word_count": 3000,
                    "estimated_word_count": 0,
                    "previous_outline_id": None,
                    "next_outline_id": None,
                    "deleted_at": None,
                },
                {
                    "id": "outline-current",
                    "project_id": "project-1",
                    "chapter_number": 1,
                    "title": "雨夜信标",
                    "summary": "当前有效版本。",
                    "status": "approved",
                    "scenes": [],
                    "chapter_goals": [],
                    "character_arcs": {},
                    "hooks_planted": [],
                    "hooks_resolved": [],
                    "quality_metrics": {},
                    "target_word_count": 3000,
                    "estimated_word_count": 0,
                    "previous_outline_id": None,
                    "next_outline_id": None,
                    "deleted_at": None,
                },
            ]
            self.stale_projects = []
            self.writes = []

        async def execute_query(self, query, params=None):
            rows = [row for row in self.rows if row["project_id"] == params.get("project_id", "project-1")]
            if params and params.get("id"):
                rows = [row for row in self.rows if row["id"] == params["id"]]
            if "deleted_at IS NULL" in query:
                rows = [row for row in rows if row.get("deleted_at") is None]
            return [dict(row) for row in rows]

        async def execute_write(self, query, params=None):
            self.writes.append((query, params))
            for row in self.rows:
                if row["id"] == params["id"]:
                    row["deleted_at"] = "now"
            return 1

        async def mark_assistant_snapshots_stale(self, project_id, except_snapshot_id=None):
            self.stale_projects.append(project_id)
            return 1

    class FakeSnapshots:
        def __init__(self):
            self.force_rebuild_calls = []

        async def force_rebuild(self, project_id, request_id=None):
            self.force_rebuild_calls.append((project_id, request_id))
            return {"id": "snapshot-new"}

    fake_db = FakeDB()
    fake_snapshots = FakeSnapshots()
    monkeypatch.setattr(
        "app.services.assistant_context.get_assistant_context_fabric",
        lambda db: SimpleNamespace(
            snapshots=fake_snapshots,
            deltas=SimpleNamespace(record_entity_change=AsyncMock()),
        ),
    )
    service = PlotOutlineService(db=fake_db)

    await service._ensure_cache("project-1")
    assert "outline-old" in service._outlines_cache
    assert "outline-current" in service._outlines_cache

    result = await service.delete_outline("outline-old")

    assert result["success"] is True
    assert "outline-old" not in service._outlines_cache
    assert fake_db.rows[0]["deleted_at"] == "now"
    assert fake_db.stale_projects == ["project-1"]
    assert fake_snapshots.force_rebuild_calls == [("project-1", None)]
    assert (await service.get_outline("project-1", 1)).id == "outline-current"
    versions = await service.get_outline_versions("project-1", 1)
    assert [outline.id for outline in versions["versions"]] == ["outline-current"]


def test_outline_version_api_routes_approve_revision_by_id(monkeypatch):
    from app.api.app import create_app
    from app.models.chapter_outline import ChapterOutline, ChapterOutlineStatus
    from app.services.plot_outline_service import PlotOutlineService, set_plot_outline_service

    service = PlotOutlineService()
    approved = ChapterOutline(
        id="outline-approved",
        project_id="project-1",
        chapter_number=3,
        title="原审批标题",
        summary="原审批摘要",
        status=ChapterOutlineStatus.APPROVED,
    )
    revision = ChapterOutline(
        id="outline-revision",
        project_id="project-1",
        chapter_number=3,
        title="修订标题",
        summary="修订摘要",
        status=ChapterOutlineStatus.REVISION,
        previous_outline_id=approved.id,
    )
    service._outlines_cache[approved.id] = approved
    service._outlines_cache[revision.id] = revision
    service._loaded_outline_projects.add("project-1")
    monkeypatch.setattr(service, "_persist_outline_resource_audit", AsyncMock())
    set_plot_outline_service(service)

    try:
        client = TestClient(create_app())
        approve_response = client.post(
            "/api/outlines/by-id/outline-revision/approve?project_id=project-1",
            json={"approved_by": "reviewer"},
        )

        assert approve_response.status_code == 200
        approved_revision = approve_response.json()
        assert approved_revision["id"] == "outline-revision"
        assert approved_revision["status"] == "approved"
        assert approved_revision["approved_by"] == "reviewer"
        assert revision.status == ChapterOutlineStatus.APPROVED
        assert approved.next_outline_id == revision.id
        service._persist_outline_resource_audit.assert_awaited_once_with(revision)
    finally:
        set_plot_outline_service(None)


@pytest.mark.asyncio
async def test_plot_outline_resource_audit_refreshes_readiness_with_outline_id_only():
    from app.models.chapter_outline import ChapterOutline, ChapterOutlineStatus
    from app.services.plot_outline_service import PlotOutlineService

    readiness_calls = []

    class FakeDB:
        async def save_outline_resource_requirements(self, requirements):
            return None

        async def update_chapter_resource_readiness(self, project_id, outline_id, chapter_num):
            readiness_calls.append({
                "project_id": project_id,
                "outline_id": outline_id,
                "chapter_num": chapter_num,
            })
            return {"outline_id": outline_id, "chapter_num": chapter_num}

    service = PlotOutlineService(db=FakeDB())
    outline = ChapterOutline(
        id="outline-refresh",
        project_id="00000000-0000-0000-0000-000000000001",
        chapter_number=7,
        title="资源审计刷新",
        summary="用于证明 readiness 刷新不再发起缺少 outline_id 的噪声调用。",
        status=ChapterOutlineStatus.DRAFT,
    )

    await service._persist_outline_resource_audit(outline)

    assert readiness_calls == [
        {
            "project_id": "00000000-0000-0000-0000-000000000001",
            "outline_id": "outline-refresh",
            "chapter_num": 7,
        }
    ]


def test_outline_chat_route_defaults_to_preview_and_requires_explicit_auto_save(monkeypatch):
    import app.api.app as api_app
    from app.api.app import create_app
    from app.services.plot_outline_service import PlotOutlineService, set_plot_outline_service

    service = PlotOutlineService()
    service._loaded_outline_projects.add("project-chat")
    calls = []

    async def fake_chat_with_agent(**kwargs):
        calls.append(kwargs)
        return {
            "message": "预览大纲 JSON",
            "outline_updates": {"title": "预览标题", "summary": "不应默认保存"},
            "pending_outlines": [{"chapter_number": 1, "title": "预览标题", "summary": "不应默认保存", "scenes": []}] if not kwargs.get("auto_save") else None,
            "saved_outline": {"id": "saved"} if kwargs.get("auto_save") else None,
            "assistant_session_id": "session-1",
            "parse_status": "outline_update",
        }

    monkeypatch.setattr(service, "chat_with_agent", fake_chat_with_agent)
    monkeypatch.setattr(api_app, "postgres_db", object())
    set_plot_outline_service(service)

    try:
        client = TestClient(create_app())
        preview_response = client.post(
            "/api/outlines/1/chat?project_id=project-chat",
            json={"message": "生成一版大纲"},
        )
        autosave_response = client.post(
            "/api/outlines/1/chat?project_id=project-chat",
            json={"message": "保存这版大纲", "auto_save": True},
        )

        assert preview_response.status_code == 200
        preview_payload = preview_response.json()
        assert preview_payload["saved_outline"] is None
        assert preview_payload["pending_outlines"][0]["title"] == "预览标题"
        assert preview_payload["parse_status"] == "outline_update"
        assert autosave_response.status_code == 200
        assert autosave_response.json()["saved_outline"] == {"id": "saved"}
        assert [call["auto_save"] for call in calls] == [False, True]
    finally:
        set_plot_outline_service(None)
        monkeypatch.setattr(api_app, "postgres_db", None)


def test_plot_outline_chat_contract_preserves_full_context_and_optional_json():
    service = PlotOutlineService()

    contract = service._build_chat_response_contract(auto_save=False)
    assert "快速问答" not in contract
    assert "可以正常回答" in contract
    assert "```json" in contract

    parsed = service._try_parse_outline_updates("我先解释一下，不输出大纲。")
    assert parsed is None


def test_plot_outline_chat_parser_accepts_common_wrapped_json_payloads():
    service = PlotOutlineService()

    parsed = service._try_parse_outline_updates(
        '```json\n{"chapter_outline":{"chapter_number":1,"title":"灰巷噪点","summary":"主角只看到异常痕迹。","scenes":[]}}\n```'
    )

    assert parsed["chapter_number"] == 1
    assert parsed["title"] == "灰巷噪点"

    list_payload = service._try_parse_outline_updates(
        '```json\n[{"chapter_number":1,"title":"第一章","summary":"开端","scenes":[]}]\n```'
    )
    assert list_payload["chapters"][0]["title"] == "第一章"


@pytest.mark.asyncio
async def test_plot_outline_chat_persists_assistant_message_before_pending_save(monkeypatch):
    service = PlotOutlineService(db=object())

    async def fake_build_packet(**kwargs):
        return {
            "packet_id": "00000000-0000-0000-0000-000000000001",
            "snapshot_id": "00000000-0000-0000-0000-000000000002",
            "snapshot_version": 1,
            "session_id": "session-1",
            "prompt_context": "上下文",
            "metadata": {"token_estimate": 10},
        }

    async def fake_llm(**kwargs):
        return '```json\n{"chapter_outline":{"chapter_number":1,"title":"灰巷噪点","summary":"主角只看到异常痕迹。","scenes":[{"title":"线索","summary":"主角只看到异常痕迹。"}]}}\n```'

    append_calls = []

    async def fake_append(**kwargs):
        append_calls.append(kwargs)

    monkeypatch.setattr(service, "_build_outline_context_packet", fake_build_packet)
    monkeypatch.setattr(service, "_get_cached_project_context", AsyncMock(return_value={"characters": [], "world_settings": [], "hooks": {}}))
    monkeypatch.setattr(service, "_get_cached_formatted_context", lambda *args, **kwargs: "完整项目上下文")
    monkeypatch.setattr(service, "_get_cached_system_prompt_with_trace", AsyncMock(return_value={"content": "系统提示", "trace": {}}))
    monkeypatch.setattr(service, "_build_outline_runtime_context", lambda existing_outline: "")
    monkeypatch.setattr(service, "_build_chat_user_context", AsyncMock(return_value="用户上下文"))
    monkeypatch.setattr(service, "_call_llm_for_chat", fake_llm)
    monkeypatch.setattr(service, "_check_outline_setting_consistency", AsyncMock(return_value={}))
    monkeypatch.setattr(service, "_append_outline_assistant_response", fake_append)

    response = await service.chat_with_agent("project-1", 1, "生成第一章大纲", auto_save=False)

    assert response["pending_outlines"][0]["title"] == "灰巷噪点"
    assert append_calls and append_calls[0]["request_id"] is None


@pytest.mark.asyncio
async def test_plot_outline_chat_continues_when_assistant_history_append_fails(monkeypatch):
    service = PlotOutlineService(db=object())

    async def fake_build_packet(**kwargs):
        return {
            "packet_id": "00000000-0000-0000-0000-000000000001",
            "snapshot_id": "00000000-0000-0000-0000-000000000002",
            "snapshot_version": 1,
            "session_id": "session-1",
            "prompt_context": "上下文",
            "metadata": {"token_estimate": 10},
        }

    async def fake_llm(**kwargs):
        return '```json\n{"chapters":[{"chapter_number":1,"title":"捕获","summary":"第一章","scenes":[{"summary":"缺标题场景","scene_type":"行动","conflict_level":"高"}]},{"chapter_number":2,"title":"回声","summary":"第二章","scenes":[{"title":"线索","summary":"只看到线索","emotion_start":"紧张"}]}]}\n```\x00'

    async def failing_append(**kwargs):
        raise ValueError("invalid byte sequence for encoding UTF8: 0x00")

    monkeypatch.setattr(service, "_build_outline_context_packet", fake_build_packet)
    monkeypatch.setattr(service, "_get_cached_project_context", AsyncMock(return_value={"characters": [], "world_settings": [], "hooks": {}}))
    monkeypatch.setattr(service, "_get_cached_formatted_context", lambda *args, **kwargs: "完整项目上下文")
    monkeypatch.setattr(service, "_get_cached_system_prompt_with_trace", AsyncMock(return_value={"content": "系统提示", "trace": {}}))
    monkeypatch.setattr(service, "_build_outline_runtime_context", lambda existing_outline: "")
    monkeypatch.setattr(service, "_build_chat_user_context", AsyncMock(return_value="用户上下文"))
    monkeypatch.setattr(service, "_call_llm_for_chat", fake_llm)
    monkeypatch.setattr(service, "_check_outline_setting_consistency", AsyncMock(return_value={}))
    monkeypatch.setattr(service, "_append_outline_assistant_response", failing_append)

    response = await service.chat_with_agent("project-1", 1, "生成黄金三章", auto_save=False)

    assert response["parse_status"] == "outline_update"
    assert [item["chapter_number"] for item in response["pending_outlines"]] == [1, 2]
    assert response["pending_outlines"][0]["scenes"][0]["title"] == "场景1"
    assert response["pending_outlines"][0]["scenes"][0]["scene_type"] == "action"
    assert response["pending_outlines"][0]["scenes"][0]["conflict_level"] == "high"


def test_assistant_message_append_sanitizes_postgres_nul_text():
    from app.database.postgres import _sanitize_postgres_text, _sanitize_postgres_value

    assert _sanitize_postgres_text("a\x00b") == "ab"
    assert _sanitize_postgres_value({"bad\x00key": ["x\x00y"]}) == {"badkey": ["xy"]}


def test_plot_outline_chat_contract_allows_multi_chapter_by_default():
    service = PlotOutlineService()

    contract = service._build_chat_response_contract(auto_save=False)

    assert "不要默认限制为当前单章" in contract
    assert "黄金三章" in contract
    assert '{"chapters":[...]}' in contract


def test_outlines_frontend_uses_single_agent_session_and_legacy_first_chapter_cache():
    content = Path("frontend/src/pages/Outlines.tsx").read_text(encoding="utf-8")

    assert "plotOutlineAgentSession:${projectId}:outlines" in content
    assert "plotOutlineAgentSession:${projectId}:1" in content
    assert "const outlineAgentMode = 'chapter:1'" in content
    assert "localStorage.getItem(storageKey) || localStorage.getItem(legacyFirstChapterStorageKey)" in content
    assert "mode={outlineAgentMode}" in content
    assert "selected_chapter_number" in content
    assert "localStorage.removeItem(`plotOutlineAgentSession:${currentProject.id}:${deletedChapter}`)" not in content
    assert "mode: `chapter:${chapterNumber}`" not in content
    assert "plotOutlineAgentSession:${currentProject.id}:${chapterNumber}`" not in content


@pytest.mark.asyncio
async def test_plot_outline_context_packet_uses_single_outlines_session_mode(monkeypatch):
    service = PlotOutlineService(db=object())
    captured = {}

    class FakeFabric:
        async def build_packet(self, **kwargs):
            captured.update(kwargs)
            return {
                "packet_id": "packet-1",
                "snapshot_id": "snapshot-1",
                "snapshot_version": 1,
                "session_id": kwargs.get("session_id") or "session-1",
                "prompt_context": "上下文",
                "metadata": {"token_estimate": 10},
            }

    import app.services.assistant_context as assistant_context_module

    monkeypatch.setattr(assistant_context_module, "get_assistant_context_fabric", lambda db: FakeFabric())

    packet = await service._build_outline_context_packet(
        project_id="project-1",
        chapter_number=7,
        task_type="chat",
        session_id="session-1",
        request_id="request-1",
        user_message="修改第7章",
        extra_scope={"selected_chapter_number": 7},
    )

    assert packet["session_id"] == "session-1"
    assert captured["mode"] == "chapter:1"
    assert captured["scope"]["chapter_number"] == 7
    assert captured["scope"]["selected_chapter_number"] == 7


def test_plot_outline_chat_uses_larger_token_budget_for_multi_chapter_json():
    service = PlotOutlineService()

    assert service._outline_chat_max_tokens >= 8192
    assert service._outline_chat_max_tokens >= service._llm_max_tokens
    assert service._outline_chat_max_continuations >= 4


def test_plot_outline_prompt_context_does_not_hard_truncate_character_or_lore_text():
    service = PlotOutlineService()
    long_description = "角色完整身份线索" * 80
    long_background = "背景里的国家机密误认边界" * 70
    long_goal = "长期目标需要完整保留" * 40
    long_lore = "宪法级设定完整内容" * 120
    context = {
        "project": {"title": "星辰"},
        "characters": [{
            "name": "林默",
            "aliases": [f"别名{i}" for i in range(10)],
            "description": long_description,
            "personality": "谨慎" * 100,
            "background_story": long_background,
            "goals": [long_goal, "第二目标"],
            "key_relationships": {f"角色{i}": f"关系{i}" for i in range(8)},
        }],
        "constitutional_rules": [{"title": "国家级机密", "priority": "constitutional", "summary": long_lore}],
        "core_settings": [],
        "relevant_settings": [],
        "hooks": {},
    }

    formatted = service.format_context_for_prompt(context)

    assert long_description in formatted
    assert long_background in formatted
    assert long_goal in formatted
    assert long_lore in formatted
    assert "别名9" in formatted
    assert "角色7:关系7" in formatted


@pytest.mark.asyncio
async def test_plot_outline_chat_continues_openai_length_truncated_multi_chapter_json(monkeypatch):
    service = PlotOutlineService()
    service._llm_provider = "openai"
    service._llm_api_key = "test-key"
    calls = []

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return SimpleNamespace(
                    choices=[SimpleNamespace(
                        finish_reason="length",
                        message=SimpleNamespace(content='```json\n{"chapters":[{"chapter_number":2,"title":"钥匙","summary":"第二章","scenes":[{"title":"休整","summary":"线索"}]},')
                    )]
                )
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content='{"chapter_number":3,"title":"东区血案","summary":"第三章","scenes":[{"title":"现场","summary":"抵达"}]}]}\n```')
                )]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    fake_module = ModuleType("openai")
    fake_module.AsyncOpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    response = await service._call_llm_for_chat("系统", "生成第2章到第3章", "上下文", {})
    parsed = service._try_parse_outline_updates(response)

    assert len(calls) == 2
    assert calls[1]["messages"][-1]["role"] == "user"
    assert "从上一轮回复的最后一个字符之后继续输出" in calls[1]["messages"][-1]["content"]
    assert [item["chapter_number"] for item in parsed["chapters"]] == [2, 3]


@pytest.mark.asyncio
async def test_plot_outline_chat_continues_anthropic_max_tokens_until_json_complete(monkeypatch):
    service = PlotOutlineService()
    service._llm_provider = "anthropic"
    service._llm_api_key = "test-key"
    calls = []

    class FakeMessages:
        async def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return SimpleNamespace(
                    stop_reason="max_tokens",
                    content=[SimpleNamespace(text='```json\n{"chapter_outline":{"chapter_number":4,"title":"规则幽灵","summary":"第四章","scenes":[')],
                )
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(text='{"title":"追踪","summary":"主角只看到痕迹"}]}}\n```')],
            )

    class FakeAnthropic:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    fake_module = ModuleType("anthropic")
    fake_module.AsyncAnthropic = FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    response = await service._call_llm_for_chat("系统", "生成第四章", "上下文", {})
    parsed = service._try_parse_outline_updates(response)

    assert len(calls) == 2
    assert calls[1]["messages"][-1]["role"] == "user"
    assert parsed["chapter_number"] == 4
    assert parsed["scenes"][0]["title"] == "追踪"


@pytest.mark.asyncio
async def test_plot_outline_chat_continues_structurally_incomplete_json_without_finish_reason(monkeypatch):
    service = PlotOutlineService()
    service._llm_provider = "openai"
    service._llm_api_key = "test-key"
    calls = []

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return SimpleNamespace(
                    choices=[SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(content='```json\n{"chapter_outline":{"chapter_number":5,"title":"未闭合","summary":"第五章","scenes":[{"title":"开端","summary":"线索"}]')
                    )]
                )
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content='}}\n```')
                )]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    fake_module = ModuleType("openai")
    fake_module.AsyncOpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    response = await service._call_llm_for_chat("系统", "生成第五章", "上下文", {})
    parsed = service._try_parse_outline_updates(response)

    assert len(calls) == 2
    assert parsed["chapter_number"] == 5


@pytest.mark.asyncio
async def test_plot_outline_chat_refuses_to_save_after_exhausted_incomplete_continuations(monkeypatch):
    service = PlotOutlineService()
    service._outline_chat_max_continuations = 1
    attempts = []

    async def fake_build_packet(**kwargs):
        return None

    async def fake_llm(**kwargs):
        attempts.append(kwargs)
        return '```json\n{"chapters":[{"chapter_number":2,"title":"钥匙","summary":"第二章","scenes":[{"title":"休整","summary":"线索"}]}'

    monkeypatch.setattr(service, "_build_outline_context_packet", fake_build_packet)
    monkeypatch.setattr(service, "_get_cached_project_context", AsyncMock(return_value={"characters": [], "world_settings": [], "hooks": {}}))
    monkeypatch.setattr(service, "_get_cached_formatted_context", lambda *args, **kwargs: "完整项目上下文")
    monkeypatch.setattr(service, "_get_cached_system_prompt_with_trace", AsyncMock(return_value={"content": "系统提示", "trace": {}}))
    monkeypatch.setattr(service, "_build_outline_runtime_context", lambda existing_outline: "")
    monkeypatch.setattr(service, "_build_chat_user_context", AsyncMock(return_value="用户上下文"))
    monkeypatch.setattr(service, "_call_llm_for_chat", fake_llm)

    response = await service.chat_with_agent("project-1", 1, "请生成第2章大纲", auto_save=False)

    assert response["parse_status"] == "outline_parse_failed"
    assert response.get("pending_outlines") is None
    assert response["outline_updates"] is None


@pytest.mark.asyncio
async def test_plot_outline_chat_warns_when_generation_response_has_no_saveable_json(monkeypatch):
    service = PlotOutlineService()

    async def fake_build_packet(**kwargs):
        return None

    async def fake_llm(**kwargs):
        return "已保存成功。```json\n{\"status\":\"success\"}\n```"

    monkeypatch.setattr(service, "_build_outline_context_packet", fake_build_packet)
    monkeypatch.setattr(service, "_get_cached_project_context", AsyncMock(return_value={"characters": [], "world_settings": [], "hooks": {}}))
    monkeypatch.setattr(service, "_get_cached_formatted_context", lambda *args, **kwargs: "完整项目上下文")
    monkeypatch.setattr(service, "_get_cached_system_prompt_with_trace", AsyncMock(return_value={"content": "系统提示", "trace": {}}))
    monkeypatch.setattr(service, "_build_outline_runtime_context", lambda existing_outline: "")
    monkeypatch.setattr(service, "_build_chat_user_context", AsyncMock(return_value="用户上下文"))
    monkeypatch.setattr(service, "_call_llm_for_chat", fake_llm)

    response = await service.chat_with_agent("project-1", 1, "保存刚才的大纲", auto_save=False)

    assert response["parse_status"] == "outline_parse_failed"
    assert response.get("pending_outlines") is None
    assert "没有解析到可保存的大纲 JSON" in response["warnings"][0]


@pytest.mark.asyncio
async def test_plot_outline_chat_rejects_truncated_multi_chapter_json_instead_of_text_fallback(monkeypatch):
    service = PlotOutlineService()

    async def fake_build_packet(**kwargs):
        return None

    async def fake_llm(**kwargs):
        return '''我来生成第2章和第3章的大纲。
```json
{
  "chapters": [
    {
      "chapter_number": 2,
      "title": "钥匙",
      "summary": "第二章",
      "scenes": [{"scene_number": 1, "title": "休整", "summary": "林默休整"}]
    },
    {
      "chapter_number": 3,
      "title": "东区血案",
      "summary": "第三章",
      "scenes": [{"scene_number": 1, "title": "现场", "summary": "林默抵达现场"}]
'''

    monkeypatch.setattr(service, "_build_outline_context_packet", fake_build_packet)
    monkeypatch.setattr(service, "_get_cached_project_context", AsyncMock(return_value={"characters": [], "world_settings": [], "hooks": {}}))
    monkeypatch.setattr(service, "_get_cached_formatted_context", lambda *args, **kwargs: "完整项目上下文")
    monkeypatch.setattr(service, "_get_cached_system_prompt_with_trace", AsyncMock(return_value={"content": "系统提示", "trace": {}}))
    monkeypatch.setattr(service, "_build_outline_runtime_context", lambda existing_outline: "")
    monkeypatch.setattr(service, "_build_chat_user_context", AsyncMock(return_value="用户上下文"))
    monkeypatch.setattr(service, "_call_llm_for_chat", fake_llm)

    response = await service.chat_with_agent("project-1", 1, "请生成第2章到第3章的大纲", auto_save=False)

    assert response["parse_status"] == "outline_parse_failed"
    assert response.get("pending_outlines") is None
    assert response["outline_updates"] is None


@pytest.mark.asyncio
async def test_plot_outline_chat_keeps_multiple_saveable_chapters_from_long_response(monkeypatch):
    service = PlotOutlineService()

    async def fake_build_packet(**kwargs):
        return None

    async def fake_llm(**kwargs):
        return '''以下是第2章到第4章：
```json
{
  "chapters": [
    {"chapter_number": 2, "title": "钥匙", "summary": "第二章", "scenes": [{"scene_number": 1, "title": "休整", "summary": "林默休整"}]},
    {"chapter_number": 3, "title": "东区血案", "summary": "第三章", "scenes": [{"scene_number": 1, "title": "现场", "summary": "林默抵达现场"}]},
    {"chapter_number": 4, "title": "规则幽灵", "summary": "第四章", "scenes": [{"scene_number": 1, "title": "追踪", "summary": "林默追踪线索"}]}
  ]
}
```
补充说明。'''

    monkeypatch.setattr(service, "_build_outline_context_packet", fake_build_packet)
    monkeypatch.setattr(service, "_get_cached_project_context", AsyncMock(return_value={"characters": [], "world_settings": [], "hooks": {}}))
    monkeypatch.setattr(service, "_get_cached_formatted_context", lambda *args, **kwargs: "完整项目上下文")
    monkeypatch.setattr(service, "_get_cached_system_prompt_with_trace", AsyncMock(return_value={"content": "系统提示", "trace": {}}))
    monkeypatch.setattr(service, "_build_outline_runtime_context", lambda existing_outline: "")
    monkeypatch.setattr(service, "_build_chat_user_context", AsyncMock(return_value="用户上下文"))
    monkeypatch.setattr(service, "_call_llm_for_chat", fake_llm)
    monkeypatch.setattr(service, "_check_outline_setting_consistency", AsyncMock(return_value={}))

    response = await service.chat_with_agent("project-1", 1, "请一次性生成第2章到第4章的大纲", auto_save=False)

    assert response["parse_status"] == "outline_update"
    assert [item["chapter_number"] for item in response["pending_outlines"]] == [2, 3, 4]
    assert all(item["scenes"] for item in response["pending_outlines"])


@pytest.mark.asyncio
async def test_plot_outline_chat_filters_unsaveable_chapters_from_multi_chapter_payload(monkeypatch):
    service = PlotOutlineService()

    async def fake_build_packet(**kwargs):
        return None

    async def fake_llm(**kwargs):
        return '''```json
{"chapters":[
  {"chapter_number":2,"title":"无场景章","summary":"不能保存","scenes":[]},
  {"chapter_number":3,"title":"可保存章","summary":"可以保存","scenes":[{"title":"线索","summary":"有场景"}]}
]}
```'''

    monkeypatch.setattr(service, "_build_outline_context_packet", fake_build_packet)
    monkeypatch.setattr(service, "_get_cached_project_context", AsyncMock(return_value={"characters": [], "world_settings": [], "hooks": {}}))
    monkeypatch.setattr(service, "_get_cached_formatted_context", lambda *args, **kwargs: "完整项目上下文")
    monkeypatch.setattr(service, "_get_cached_system_prompt_with_trace", AsyncMock(return_value={"content": "系统提示", "trace": {}}))
    monkeypatch.setattr(service, "_build_outline_runtime_context", lambda existing_outline: "")
    monkeypatch.setattr(service, "_build_chat_user_context", AsyncMock(return_value="用户上下文"))
    monkeypatch.setattr(service, "_call_llm_for_chat", fake_llm)
    monkeypatch.setattr(service, "_check_outline_setting_consistency", AsyncMock(return_value={}))

    response = await service.chat_with_agent("project-1", 1, "生成多章大纲", auto_save=False)

    assert response["parse_status"] == "outline_update"
    assert [item["chapter_number"] for item in response["pending_outlines"]] == [3]


@pytest.mark.asyncio
async def test_plot_outline_resource_audit_auto_resolves_existing_lore_and_hook():
    from app.models.chapter_outline import ChapterOutline, ChapterOutlineStatus, SceneOutline

    service = PlotOutlineService()
    outline = ChapterOutline(
        id="outline-resource-auto-bind",
        project_id="project-1",
        chapter_number=1,
        title="能力协议",
        summary="主角在已知地点学习秘法，并触发旧伏笔。",
        scenes=[SceneOutline(scene_number=1, title="训练", summary="秘法协议被启动", location="已知地点")],
        hooks_planted=["旧伏笔再次出现"],
        status=ChapterOutlineStatus.DRAFT,
    )
    full_context = {
        "characters": [],
        "world_settings": [
            {"id": "lore-location", "title": "已知地点", "priority": "standard", "summary": "地点设定"},
            {"id": "lore-ability", "title": "秘法协议", "priority": "core", "summary": "能力边界"},
        ],
        "hooks": {"pending": [{"id": "hook-1", "title": "旧伏笔", "description": "待回收"}], "to_resolve": [], "to_plant": []},
        "character_availability_packet": {"availability_by_name": {}, "canonical_name_map": {}},
    }

    requirements = service._build_outline_resource_requirements(outline, full_context, set())

    resolved = [item for item in requirements if item["status"] == "resolved"]
    assert any(item["resource_name"] == "已知地点" and item["matched_resource_type"] == "lore" for item in resolved)
    assert any(item["resource_name"] == "秘法协议" and item["matched_resource_id"] == "lore-ability" for item in resolved)
    assert not [item for item in requirements if item["status"] == "pending" and item["resource_name"] in {"已知地点", "第1章能力规则"}]


@pytest.mark.asyncio
async def test_batch_generate_route_preview_does_not_save_without_policy(monkeypatch):
    import app.api.app as api_app
    from app.api.app import create_app
    from app.models.chapter_outline import ChapterOutline, GenerateOutlineResponse
    from app.services.plot_outline_service import PlotOutlineService, set_plot_outline_service

    service = PlotOutlineService()
    service._loaded_outline_projects.add("project-batch")
    save_calls = []

    async def fake_generate_outline(**kwargs):
        chapter_number = kwargs["chapter_number"]
        return GenerateOutlineResponse(
            outline=ChapterOutline(
                id=f"outline-preview-{chapter_number}",
                project_id=kwargs["project_id"],
                chapter_number=chapter_number,
                title=f"第{chapter_number}章预览",
                summary="只生成预览，不写库。",
            ),
            suggestions=["人工审核后保存"],
            warnings=[],
            context_packet={"packet_id": f"packet-{chapter_number}"},
        )

    async def fake_save_outline_updates(**kwargs):
        save_calls.append(kwargs)
        return None, []

    monkeypatch.setattr(service, "generate_outline", fake_generate_outline)
    monkeypatch.setattr(service, "_save_outline_updates", fake_save_outline_updates)
    monkeypatch.setattr(api_app, "postgres_db", object())
    set_plot_outline_service(service)

    try:
        client = TestClient(create_app())
        response = client.post(
            "/api/outlines/batch-generate",
            json={"project_id": "project-batch", "start_chapter": 1, "end_chapter": 2},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["auto_save"] is False
        assert payload["summary"] == {"generated": 2, "saved": 0, "approved": 0, "failed": 0}
        assert [item["status"] for item in payload["results"]] == ["generated", "generated"]
        assert save_calls == []
    finally:
        set_plot_outline_service(None)
        monkeypatch.setattr(api_app, "postgres_db", None)


@pytest.mark.asyncio
async def test_batch_generate_route_auto_save_uses_explicit_policy(monkeypatch):
    import app.api.app as api_app
    from app.api.app import create_app
    from app.models.chapter_outline import ChapterOutline, GenerateOutlineResponse
    from app.services.plot_outline_service import PlotOutlineService, set_plot_outline_service

    service = PlotOutlineService()
    service._loaded_outline_projects.add("project-batch")
    save_calls = []

    async def fake_generate_outline(**kwargs):
        chapter_number = kwargs["chapter_number"]
        return GenerateOutlineResponse(
            outline=ChapterOutline(
                id=f"outline-preview-{chapter_number}",
                project_id=kwargs["project_id"],
                chapter_number=chapter_number,
                title=f"第{chapter_number}章预览",
                summary="显式保存。",
            ),
        )

    async def fake_save_outline_updates(**kwargs):
        save_calls.append(kwargs)
        chapter_number = kwargs["default_chapter_number"]
        return ChapterOutline(
            id=f"outline-saved-{chapter_number}",
            project_id=kwargs["project_id"],
            chapter_number=chapter_number,
            title="已保存",
            summary="显式策略写库。",
        ), []

    monkeypatch.setattr(service, "generate_outline", fake_generate_outline)
    monkeypatch.setattr(service, "_save_outline_updates", fake_save_outline_updates)
    monkeypatch.setattr(api_app, "postgres_db", object())
    set_plot_outline_service(service)

    try:
        client = TestClient(create_app())
        response = client.post(
            "/api/outlines/batch-generate",
            json={"project_id": "project-batch", "chapter_numbers": [2, 1], "auto_save": True},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"] == {"generated": 2, "saved": 2, "approved": 0, "failed": 0}
        assert [call["default_chapter_number"] for call in save_calls] == [1, 2]
        assert [item["saved_outline"]["id"] for item in payload["results"]] == ["outline-saved-1", "outline-saved-2"]
    finally:
        set_plot_outline_service(None)
        monkeypatch.setattr(api_app, "postgres_db", None)


@pytest.mark.asyncio
async def test_batch_generate_route_rejects_auto_approve_without_auto_save():
    from app.api.app import create_app

    client = TestClient(create_app())
    response = client.post(
        "/api/outlines/batch-generate",
        json={"project_id": "project-batch", "chapter_numbers": [1], "auto_approve": True, "approved_by": "reviewer"},
    )

    assert response.status_code == 422


def test_save_pending_outlines_normalizes_repairable_scene_fields(monkeypatch):
    import app.api.app as api_app
    from app.api.app import create_app
    from app.services.plot_outline_service import PlotOutlineService, set_plot_outline_service

    service = PlotOutlineService()
    service._loaded_outline_projects.add("project-save")
    monkeypatch.setattr(service, "_persist_outline_resource_audit", AsyncMock())
    monkeypatch.setattr(api_app, "postgres_db", object())
    set_plot_outline_service(service)

    try:
        client = TestClient(create_app())
        response = client.post(
            "/api/outlines/save-outlines?project_id=project-save",
            json={
                "outlines": [
                    {
                        "chapter_number": 1,
                        "title": "可修复大纲",
                        "summary": "场景缺少 title 且使用中文枚举，应被规范化后保存。",
                        "scenes": [
                            {
                                "scene_number": 1,
                                "summary": "缺少场景标题",
                                "scene_type": "行动",
                                "conflict_level": "高",
                                "emotion_start": "紧张",
                            }
                        ],
                    }
                ]
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["saved_count"] == 1
        assert payload["results"][0]["status"] == "saved"
    finally:
        set_plot_outline_service(None)
        monkeypatch.setattr(api_app, "postgres_db", None)


def test_save_pending_outlines_reports_all_failed_validation_errors(monkeypatch):
    import app.api.app as api_app
    from app.api.app import create_app
    from app.services.plot_outline_service import PlotOutlineService, set_plot_outline_service

    service = PlotOutlineService()
    service._loaded_outline_projects.add("project-save")
    monkeypatch.setattr(service, "_persist_outline_resource_audit", AsyncMock())
    monkeypatch.setattr(api_app, "postgres_db", object())
    set_plot_outline_service(service)

    try:
        client = TestClient(create_app())
        response = client.post(
            "/api/outlines/save-outlines?project_id=project-save",
            json={
                "outlines": [
                    {
                        "chapter_number": 1,
                        "title": "失效大纲",
                        "summary": "场景包含不可修复字段，应暴露为结构化保存失败。",
                        "scenes": [
                            {
                                "scene_number": 1,
                                "title": "失效场景",
                                "summary": "estimated_words 类型错误",
                                "estimated_words": "很多",
                                "participating_characters": ["林澈"],
                            }
                        ],
                    }
                ]
            },
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["success"] is False
        assert detail["saved_count"] == 0
        assert detail["failed_count"] == 1
        assert detail["message"] == "1 个大纲保存失败，请根据 results 查看具体原因"
        assert detail["results"][0]["chapter_number"] == 1
        assert detail["results"][0]["status"] == "failed"
        assert detail["results"][0]["error_type"] == "validation_error"
        assert "estimated_words" in detail["results"][0]["error"]
    finally:
        set_plot_outline_service(None)
        monkeypatch.setattr(api_app, "postgres_db", None)


def test_save_pending_outlines_returns_partial_success_results(monkeypatch):
    import app.api.app as api_app
    from app.api.app import create_app
    from app.services.plot_outline_service import PlotOutlineService, set_plot_outline_service

    service = PlotOutlineService()
    service._loaded_outline_projects.add("project-save")
    monkeypatch.setattr(service, "_persist_outline_resource_audit", AsyncMock())
    monkeypatch.setattr(api_app, "postgres_db", object())
    set_plot_outline_service(service)

    try:
        client = TestClient(create_app())
        response = client.post(
            "/api/outlines/save-outlines?project_id=project-save",
            json={
                "outlines": [
                    {
                        "chapter_number": 1,
                        "title": "有效大纲",
                        "summary": "可保存的大纲。",
                        "scenes": [
                            {
                                "scene_number": 1,
                                "title": "有效场景",
                                "summary": "字段完整。",
                                "participating_characters": ["林澈"],
                            }
                        ],
                    },
                    {
                        "chapter_number": 2,
                        "title": "失效大纲",
                        "summary": "场景包含不可修复字段。",
                        "scenes": [
                            {
                                "scene_number": 1,
                                "title": "失效场景",
                                "summary": "estimated_words 类型错误",
                                "estimated_words": "很多",
                            }
                        ],
                    },
                ]
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["saved_count"] == 1
        assert body["failed_count"] == 1
        assert body["message"] == "已保存 1 个大纲，1 个大纲保存失败，请检查失败项"
        assert body["results"][0]["chapter_number"] == 1
        assert body["results"][0]["status"] == "saved"
        assert body["results"][0]["action"] == "created"
        assert body["results"][0]["outline_id"].startswith("outline_")
        assert body["results"][1]["chapter_number"] == 2
        assert body["results"][1]["status"] == "failed"
        assert body["results"][1]["error_type"] == "validation_error"
    finally:
        set_plot_outline_service(None)
        monkeypatch.setattr(api_app, "postgres_db", None)


def test_prompt_audit_api_route_smoke_uses_non_llm_agent_prompt_service(monkeypatch):
    from app.api.app import create_app

    class FakeAgentPromptService:
        async def audit_system_agent_template_prompt_resolution(self):
            return {
                "template_count": 1,
                "slot_count": 2,
                "resolved_prompt_ids": ["prompt_existing"],
                "missing_prompt_ids": ["prompt_missing"],
                "md_asset_prompt_ids": ["prompt_existing"],
                "system_seed_prompt_ids": [],
                "deprecated_prompt_ids": [],
                "unresolved_md_asset_prompt_ids": [],
                "templates": [
                    {
                        "template_id": "template-writer",
                        "agent_type": "writer",
                        "scenario": "workflow_chapter_generation",
                        "prompt_ids": ["prompt_existing"],
                        "missing_prompt_ids": ["prompt_missing"],
                        "md_asset_prompt_ids": ["prompt_existing"],
                        "system_seed_prompt_ids": [],
                        "deprecated_prompt_ids": [],
                        "unresolved_md_asset_prompt_ids": [],
                        "fallbacks_used": ["prompt_template_md_asset:prompt_existing", "missing_prompt_template:prompt_missing"],
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
    assert result["templates"][0]["fallbacks_used"] == [
        "prompt_template_md_asset:prompt_existing",
        "missing_prompt_template:prompt_missing",
    ]
