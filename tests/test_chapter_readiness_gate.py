import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.director import DirectorSystem, _serialize_for_json
from app.services.workflow_engine import ChapterReadinessBlockedError, WorkflowEngine


PROJECT_ID = "11111111-1111-1111-1111-111111111111"
OUTLINE_ID = "22222222-2222-2222-2222-222222222222"
REQUIREMENT_ID = "33333333-3333-3333-3333-333333333333"


class _GateFakeDB:
    def __init__(self, requirements=None):
        self.requirements = requirements or []
        self.readiness_calls = []

    async def get_outline_resource_requirements(self, **kwargs):
        requirements = list(self.requirements)
        if kwargs.get("outline_id"):
            requirements = [item for item in requirements if item.get("outline_id") == kwargs["outline_id"]]
        if kwargs.get("chapter_num") is not None:
            requirements = [item for item in requirements if item.get("chapter_num") == kwargs["chapter_num"]]
        return requirements

    async def update_chapter_resource_readiness(self, **kwargs):
        self.readiness_calls.append(dict(kwargs))
        return {
            "project_id": kwargs["project_id"],
            "outline_id": kwargs.get("outline_id"),
            "chapter_num": kwargs["chapter_num"],
            "readiness_status": "blocked",
        }


class _NoopWriter:
    async def execute(self, payload):
        return type(
            "WriterResult",
            (),
            {
                "success": True,
                "structured_data": {"chapter_content": "正文"},
                "data": {},
                "text_output": "正文",
                "error": None,
            },
        )()


def _blocking_requirement(**overrides):
    data = {
        "id": REQUIREMENT_ID,
        "project_id": PROJECT_ID,
        "outline_id": OUTLINE_ID,
        "chapter_num": 3,
        "severity": "blocking",
        "status": "pending",
        "resource_name": "缺失角色",
        "requirement_type": "character",
    }
    data.update(overrides)
    return data


def _approved_outline(**overrides):
    data = {
        "id": OUTLINE_ID,
        "project_id": PROJECT_ID,
        "chapter_number": 3,
        "title": "第三章",
        "summary": "推进剧情",
        "target_word_count": 1200,
        "status": "approved",
        "next_outline_id": None,
    }
    data.update(overrides)
    return SimpleNamespace(
        **data,
        model_dump=lambda mode="json": dict(data),
    )


def _patch_plot_service(monkeypatch, outline=None):
    outline = outline or _approved_outline()

    class FakePlotService:
        async def get_outline_by_id(self, project_id, outline_id):
            return outline if outline_id == OUTLINE_ID else None

        async def get_outline(self, project_id, chapter_num):
            return outline if chapter_num == 3 else None

    monkeypatch.setattr("app.services.plot_outline_service.get_plot_outline_service", lambda: FakePlotService())


@pytest.mark.asyncio
async def test_public_readiness_gate_blocks_unresolved_blocking_requirement(monkeypatch):
    _patch_plot_service(monkeypatch)
    db = _GateFakeDB([_blocking_requirement()])
    engine = WorkflowEngine()

    with pytest.raises(ChapterReadinessBlockedError) as exc_info:
        await engine.check_chapter_resource_readiness(
            PROJECT_ID,
            {"chapter_num": 3, "chapter_outline_id": OUTLINE_ID},
            db,
        )

    payload = exc_info.value.payload
    assert payload["readiness_status"] == "blocked"
    assert payload["chapter_num"] == 3
    assert payload["chapter_outline_id"] == OUTLINE_ID
    assert payload["blocking_requirements"][0]["id"] == REQUIREMENT_ID
    assert db.readiness_calls == [{"project_id": PROJECT_ID, "outline_id": OUTLINE_ID, "chapter_num": 3}]


@pytest.mark.asyncio
async def test_readiness_gate_uses_strict_outline_identity_for_same_chapter_requirements(monkeypatch):
    _patch_plot_service(monkeypatch)
    stale_outline_id = "44444444-4444-4444-4444-444444444444"
    db = _GateFakeDB([
        _blocking_requirement(outline_id=stale_outline_id),
        _blocking_requirement(id="55555555-5555-5555-5555-555555555555", status="resolved"),
    ])
    engine = WorkflowEngine()

    payload = await engine.check_chapter_resource_readiness(
        PROJECT_ID,
        {"chapter_num": 3, "chapter_outline_id": OUTLINE_ID},
        db,
    )

    assert payload["readiness_status"] == "ready"
    assert payload["chapter_outline_id"] == OUTLINE_ID
    assert payload["blocking_requirements"] == []
    assert db.readiness_calls == [{"project_id": PROJECT_ID, "outline_id": OUTLINE_ID, "chapter_num": 3}]


@pytest.mark.asyncio
async def test_readiness_gate_rejects_non_current_approved_outline(monkeypatch):
    engine = WorkflowEngine()
    stale_outline = SimpleNamespace(
        id=OUTLINE_ID,
        project_id=PROJECT_ID,
        chapter_number=3,
        title="旧审批版本",
        summary="旧版本",
        target_word_count=1200,
        status="approved",
        next_outline_id="44444444-4444-4444-4444-444444444444",
        model_dump=lambda mode="json": {
            "id": OUTLINE_ID,
            "project_id": PROJECT_ID,
            "chapter_number": 3,
            "title": "旧审批版本",
            "summary": "旧版本",
            "target_word_count": 1200,
            "status": "approved",
            "next_outline_id": "44444444-4444-4444-4444-444444444444",
        },
    )

    class FakePlotService:
        async def get_outline_by_id(self, project_id, outline_id):
            return stale_outline

    monkeypatch.setattr("app.services.plot_outline_service.get_plot_outline_service", lambda: FakePlotService())

    with pytest.raises(ChapterReadinessBlockedError) as exc_info:
        await engine.check_chapter_resource_readiness(
            PROJECT_ID,
            {"chapter_num": 3, "chapter_outline_id": OUTLINE_ID},
            _GateFakeDB(),
        )

    assert exc_info.value.payload["block_reason"] == "outline_not_current_approved"
    assert exc_info.value.payload["chapter_outline_id"] == OUTLINE_ID


@pytest.mark.asyncio
async def test_readiness_gate_rejects_mismatched_outline_chapter(monkeypatch):
    engine = WorkflowEngine()
    wrong_chapter_outline = SimpleNamespace(
        id=OUTLINE_ID,
        project_id=PROJECT_ID,
        chapter_number=4,
        title="第四章",
        summary="章节不匹配",
        target_word_count=1200,
        status="approved",
        next_outline_id=None,
        model_dump=lambda mode="json": {
            "id": OUTLINE_ID,
            "project_id": PROJECT_ID,
            "chapter_number": 4,
            "title": "第四章",
            "summary": "章节不匹配",
            "target_word_count": 1200,
            "status": "approved",
            "next_outline_id": None,
        },
    )

    class FakePlotService:
        async def get_outline_by_id(self, project_id, outline_id):
            return wrong_chapter_outline

    monkeypatch.setattr("app.services.plot_outline_service.get_plot_outline_service", lambda: FakePlotService())

    with pytest.raises(ChapterReadinessBlockedError) as exc_info:
        await engine.check_chapter_resource_readiness(
            PROJECT_ID,
            {"chapter_num": 3, "chapter_outline_id": OUTLINE_ID},
            _GateFakeDB(),
        )

    assert exc_info.value.payload["block_reason"] == "outline_chapter_mismatch"
    assert exc_info.value.payload["chapter_num"] == 3


@pytest.mark.asyncio
async def test_director_auto_write_gate_runs_before_start_chapter(monkeypatch):
    _patch_plot_service(monkeypatch)
    db = _GateFakeDB([_blocking_requirement()])
    director = DirectorSystem({"id": "world-1", "name": "测试世界"}, project_id=PROJECT_ID)
    director.writer = _NoopWriter()
    start_calls = []

    async def fake_start_chapter(**kwargs):
        start_calls.append(kwargs)

    monkeypatch.setattr(director, "start_chapter", fake_start_chapter)

    with pytest.raises(ChapterReadinessBlockedError):
        await director.auto_write_chapter(
            chapter_title="第三章",
            chapter_goal="推进剧情",
            project_id=PROJECT_ID,
            chapter_num=3,
            chapter_outline_id=OUTLINE_ID,
            chapter_outline={"id": OUTLINE_ID, "chapter_number": 3},
            db=db,
        )

    assert start_calls == []
    assert db.readiness_calls == [{"project_id": PROJECT_ID, "outline_id": OUTLINE_ID, "chapter_num": 3}]


@pytest.mark.asyncio
async def test_director_auto_mode_callback_awaits_async_callback():
    director = DirectorSystem({"id": "world-1", "name": "测试世界"}, project_id=PROJECT_ID)
    events = []

    async def async_callback(event_type, data):
        events.append((event_type, data))

    await director._emit_auto_mode_callback(async_callback, "chapter_blocked", {"chapter_num": 3})

    assert events == [("chapter_blocked", {"chapter_num": 3})]


def test_director_blocked_payload_serialization_handles_uuid_and_datetime():
    payload = {
        "readiness_status": "blocked",
        "chapter_outline_id": uuid.UUID(OUTLINE_ID),
        "readiness": {"last_audited_at": datetime(2026, 5, 3, tzinfo=timezone.utc)},
        "blocking_requirements": [
            {
                "id": uuid.UUID(REQUIREMENT_ID),
                "created_at": datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc),
            }
        ],
    }

    serialized = _serialize_for_json(payload)

    assert serialized["chapter_outline_id"] == OUTLINE_ID
    assert serialized["blocking_requirements"][0]["id"] == REQUIREMENT_ID
    json.dumps(serialized)


@pytest.mark.asyncio
async def test_director_auto_mode_exposes_blocked_chapter_and_completes(monkeypatch):
    director = DirectorSystem({"id": "world-1", "name": "测试世界"}, project_id=PROJECT_ID)
    events = []

    async def callback(event_type, data):
        events.append((event_type, data))

    class FakeEngine:
        async def get_workflow(self, workflow_id, db):
            return {"id": workflow_id}

        async def execute_workflow(self, workflow_id, project_id, initial_context, db):
            raise ChapterReadinessBlockedError({
                "readiness_status": "blocked",
                "chapter_num": initial_context["chapter_num"],
                "chapter_outline_id": initial_context["chapter_outline_id"],
                "readiness": {"id": uuid.UUID(REQUIREMENT_ID)},
                "blocking_requirements": [
                    {
                        "id": uuid.UUID(REQUIREMENT_ID),
                        "resource_name": "缺失角色",
                        "severity": "blocking",
                        "status": "pending",
                    }
                ],
            })

    fake_outline = SimpleNamespace(
        id=OUTLINE_ID,
        chapter_number=3,
        title="第三章",
        summary="推进剧情",
        chapter_goals=[],
        target_word_count=1200,
        status="approved",
        model_dump=lambda mode="json": {"id": OUTLINE_ID, "chapter_number": 3},
    )

    class FakePlotService:
        async def get_outlines_by_project(self, project_id):
            return [fake_outline]

    monkeypatch.setattr("app.services.workflow_engine.get_workflow_engine", lambda: FakeEngine())
    monkeypatch.setattr("app.services.plot_outline_service.get_plot_outline_service", lambda: FakePlotService())
    monkeypatch.setattr("app.api.app.postgres_db", _GateFakeDB())

    result = await director.start_auto_mode(
        workflow_id="workflow-1",
        chapter_count=1,
        words_per_chapter=1200,
        callback=callback,
        outline_mode="selected",
        outline_ids=[OUTLINE_ID],
        project_id=PROJECT_ID,
    )

    assert result["success"] is True
    assert result["chapters"] == []
    assert result["blocked_chapters"][0]["chapter_num"] == 3
    assert result["blocked_chapters"][0]["blocking_requirements"][0]["id"] == REQUIREMENT_ID
    assert any(event_type == "chapter_blocked" for event_type, _ in events)
    completed_events = [data for event_type, data in events if event_type == "completed"]
    assert completed_events[-1]["blocked_chapters"] == 1
