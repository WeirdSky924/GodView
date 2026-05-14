import pytest

from app.services.chapter_document_storage import ChapterDocumentStorage
from app.models.workflow_execution import WorkflowExecution, WorkflowStatus
from app.services.workflow_engine import WorkflowEngine

from tests.workflow_test_fakes import FakeDiscussionDB


@pytest.mark.asyncio
async def test_writer_save_marks_current_approved_outline_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.chapter_document_storage.chapter_document_storage",
        ChapterDocumentStorage(str(tmp_path)),
    )
    engine = WorkflowEngine()
    db = FakeDiscussionDB()
    db.outlines["outline-ready"] = {
        "id": "outline-ready",
        "project_id": "00000000-0000-0000-0000-000000000001",
        "chapter_number": 3,
        "status": "approved",
        "next_outline_id": None,
    }
    execution = WorkflowExecution(
        workflow_id="test-wf",
        project_id="00000000-0000-0000-0000-000000000001",
        status=WorkflowStatus.RUNNING,
        context={
            "chapter_num": 3,
            "chapter_title": "第三章：归航",
            "chapter_outline_id": "outline-ready",
        },
        node_states={},
    )

    broadcast_events = []

    async def capture_broadcast(execution_id, event_type, payload):
        broadcast_events.append((execution_id, event_type, payload))

    monkeypatch.setattr(engine, "_broadcast_status", capture_broadcast)

    writer_node = type("WriterNode", (), {"id": "writer", "label": "写作", "agent_type": "writer"})()
    execution.context["node_runtime_metadata"] = {
        "writer": {
            "resolved_agent_type": "writer",
            "resolved_scenario": "workflow_chapter_generation",
            "source_node_input_keys": ["chapter_outline", "target_word_count"],
        }
    }
    writer_output = {
        "chapter_content": "归航正文",
        "word_count": 4,
        "metadata": {"word_count_passed": True},
    }
    prompt_trace = {
        "template_id": "writer-template",
        "prompt_ids": ["function_writing"],
        "skill_ids": ["scene_pacing"],
        "writing_rule_ids": ["long_novel_core"],
        "prompt": "must not be saved",
    }

    await engine._save_chapter_from_writer(
        execution,
        writer_output,
        db,
        source_node=writer_node,
        contract_metadata={
            "output_contract_id": "writer.workflow_output",
            "output_schema_name": "writer.workflow_output",
            "output_schema_version": "1.0.0",
        },
        prompt_trace=prompt_trace,
    )

    assert db.chapters[0]["chapter_outline_id"] == "outline-ready"
    assert db.chapters[0]["content"] == ""
    assert db.chapters[0]["content_storage"] == "filesystem"
    saved_path = tmp_path / db.chapters[0]["content_path"]
    assert saved_path.read_text(encoding="utf-8") == "归航正文"
    assert db.outlines["outline-ready"]["status"] == "completed"
    assert db.outline_status_events[0]["project_id"] == execution.project_id
    assert execution.context["chapter_saved"] is True
    assert execution.context["chapter_id"] == db.chapters[0]["id"]
    assert execution.context["chapter_saved_at"]
    assert execution.context["chapter_outline_status"] == "completed"
    assert execution.context["chapter_content_storage"] == "filesystem"
    assert execution.context["chapter_content_path"] == db.chapters[0]["content_path"]
    assert execution.context["chapter_content_size_bytes"] == db.chapters[0]["content_size_bytes"]
    assert execution.context["chapter_content_checksum"] == db.chapters[0]["content_checksum"]

    assert broadcast_events[0][0] == execution.id
    assert broadcast_events[0][1] == "chapter_saved"
    saved_payload = broadcast_events[0][2]
    assert saved_payload["chapter_id"] == db.chapters[0]["id"]
    assert saved_payload["chapter_num"] == 3
    assert saved_payload["chapter_number"] == 3
    assert saved_payload["title"] == "第三章：归航"
    assert saved_payload["chapter_title"] == "第三章：归航"
    assert saved_payload["chapter_outline_id"] == "outline-ready"
    assert saved_payload["project_id"] == execution.project_id
    assert saved_payload["execution_id"] == execution.id
    assert saved_payload["workflow_id"] == execution.workflow_id
    assert saved_payload["status"] == "saved"
    assert saved_payload["saved_at"] == execution.context["chapter_saved_at"]
    assert saved_payload["word_count"] == 4
    assert saved_payload["content_chars"] == len("归航正文")
    assert saved_payload["content_storage"] == "filesystem"
    assert saved_payload["content_path"] == db.chapters[0]["content_path"]
    assert saved_payload["content_size_bytes"] == db.chapters[0]["content_size_bytes"]
    assert saved_payload["content_checksum"] == db.chapters[0]["content_checksum"]
    assert saved_payload["source_node_id"] == "writer"
    assert saved_payload["source_node_label"] == "写作"
    assert saved_payload["source_agent_type"] == "writer"
    assert saved_payload["resolved_agent_type"] == "writer"
    assert saved_payload["resolved_scenario"] == "workflow_chapter_generation"
    assert saved_payload["source_output_contract_id"] == "writer.workflow_output"
    assert saved_payload["source_output_schema_name"] == "writer.workflow_output"
    assert saved_payload["writer_output_content_field"] == "chapter_content"
    assert saved_payload["writer_output_content_chars"] == len("归航正文")
    assert saved_payload["writer_output_word_count"] == 4
    assert saved_payload["writer_prompt_trace_present"] is True
    assert saved_payload["writer_prompt_trace"]["prompt_ids"] == ["function_writing"]
    assert saved_payload["writer_prompt_trace"]["skill_ids"] == ["scene_pacing"]
    assert saved_payload["writer_prompt_trace"]["writing_rule_ids"] == ["long_novel_core"]
    assert "prompt" not in saved_payload["writer_prompt_trace"]
    assert "content" not in saved_payload
    assert execution.context["chapter_writer_provenance"]["source_node_id"] == "writer"
    assert execution.context["chapter_saved_payload"] == saved_payload


@pytest.mark.asyncio
async def test_writer_save_does_not_complete_superseded_outline(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.chapter_document_storage.chapter_document_storage",
        ChapterDocumentStorage(str(tmp_path)),
    )
    engine = WorkflowEngine()
    db = FakeDiscussionDB()
    db.outlines["outline-old"] = {
        "id": "outline-old",
        "project_id": "00000000-0000-0000-0000-000000000001",
        "chapter_number": 3,
        "status": "approved",
        "next_outline_id": "outline-new",
    }
    execution = WorkflowExecution(
        workflow_id="test-wf",
        project_id="00000000-0000-0000-0000-000000000001",
        status=WorkflowStatus.RUNNING,
        context={
            "chapter_num": 3,
            "chapter_title": "第三章：旧稿",
            "chapter_outline_id": "outline-old",
        },
        node_states={},
    )

    await engine._save_chapter_from_writer(
        execution,
        {"chapter_content": "旧稿正文", "word_count": 4},
        db,
    )

    assert db.chapters[0]["chapter_outline_id"] == "outline-old"
    assert db.outlines["outline-old"]["status"] == "approved"
    assert "chapter_outline_status" not in execution.context


@pytest.mark.asyncio
async def test_quality_gated_writer_stages_draft_without_saving_or_completing_outline(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.chapter_document_storage.chapter_document_storage",
        ChapterDocumentStorage(str(tmp_path)),
    )
    engine = WorkflowEngine()
    db = FakeDiscussionDB()
    db.outlines["outline-gated"] = {
        "id": "outline-gated",
        "project_id": "00000000-0000-0000-0000-000000000001",
        "chapter_number": 4,
        "status": "approved",
        "next_outline_id": None,
    }
    execution = WorkflowExecution(
        workflow_id="wf-gated",
        project_id="00000000-0000-0000-0000-000000000001",
        status=WorkflowStatus.RUNNING,
        context={"chapter_num": 4, "chapter_title": "第四章：门槛", "chapter_outline_id": "outline-gated"},
        node_states={},
    )
    writer_node = type("WriterNode", (), {"id": "writer", "label": "写作", "agent_type": "writer"})()
    events = []

    async def capture_broadcast(execution_id, event_type, payload):
        events.append((execution_id, event_type, payload))

    monkeypatch.setattr(engine, "_broadcast_status", capture_broadcast)

    await engine._stage_writer_draft(
        execution,
        writer_node,
        {"chapter_content": "需要评审的正文", "word_count": 8, "hooks_embedded": [{"title": "不应提前落库"}]},
        db,
        contract_metadata={"output_contract_id": "writer.workflow_output"},
        prompt_trace={"prompt_ids": ["function_writing"], "prompt": "must not be exposed"},
    )

    assert db.chapters == []
    assert db.hooks == []
    assert db.outlines["outline-gated"]["status"] == "approved"
    assert execution.context["pending_chapter_save"] is True
    assert execution.context.get("chapter_saved") is not True
    assert execution.context["chapter_content"] == "需要评审的正文"
    assert execution.context["chapter_draft_attempt"] == 1
    assert execution.context["quality_gate_status"] == "pending_evaluation"
    assert events[0][1] == "chapter_draft_ready"
    assert events[0][2]["status"] == "draft_pending_quality_gate"
    assert "content" not in events[0][2]
    assert "chapter_content" not in events[0][2]
    assert "prompt" not in events[0][2]["writer_prompt_trace"]


@pytest.mark.asyncio
async def test_quality_gated_writer_finalizes_after_pass_once_with_quality_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.chapter_document_storage.chapter_document_storage",
        ChapterDocumentStorage(str(tmp_path)),
    )
    engine = WorkflowEngine()
    db = FakeDiscussionDB()
    db.outlines["outline-pass"] = {
        "id": "outline-pass",
        "project_id": "00000000-0000-0000-0000-000000000001",
        "chapter_number": 5,
        "status": "approved",
        "next_outline_id": None,
    }
    execution = WorkflowExecution(
        workflow_id="wf-gated-pass",
        project_id="00000000-0000-0000-0000-000000000001",
        status=WorkflowStatus.RUNNING,
        context={
            "chapter_num": 5,
            "chapter_title": "第五章：通过",
            "chapter_outline_id": "outline-pass",
            "scene_plan_id": "plan-1",
            "scene_plan_checksum": "scene-checksum",
            "scene_plan_attempt": 1,
            "revision_directive_id": "rev-1",
            "revision_directive_checksum": "revision-checksum",
            "revision_directive_attempt": 1,
            "evaluation_feedback": {"scene_coverage": {"required_beat_count": 1, "covered_beat_count": 1}},
        },
        node_states={},
    )
    writer_node = type("WriterNode", (), {"id": "writer", "label": "写作", "agent_type": "writer"})()
    events = []

    async def capture_broadcast(execution_id, event_type, payload):
        events.append((execution_id, event_type, payload))

    monkeypatch.setattr(engine, "_broadcast_status", capture_broadcast)
    await engine._stage_writer_draft(
        execution,
        writer_node,
        {
            "chapter_content": "最终保存的正文",
            "word_count": 7,
            "hooks_embedded": [{"title": "已确认伏笔", "description": "确认后才落库"}],
            "state_changes": [
                {
                    "entity_type": "plot",
                    "change_type": "custom",
                    "title": "主线线索浮现",
                    "summary": "主角确认潮汐门与旧案有关",
                }
            ],
        },
        db,
        contract_metadata={"output_contract_id": "writer.workflow_output"},
        prompt_trace={"prompt_ids": ["function_writing"]},
    )
    execution.context.setdefault("node_outputs", {})["writer"] = {
        "chapter_content": "最终保存的正文",
        "word_count": 7,
        "hooks_embedded": [{"title": "已确认伏笔", "description": "确认后才落库"}],
        "state_changes": [
            {
                "entity_type": "plot",
                "change_type": "custom",
                "title": "主线线索浮现",
                "summary": "主角确认潮汐门与旧案有关",
            }
        ],
    }
    execution.context["quality_gate"] = {"status": "passed", "passed": True, "score": 8.5}
    execution.context["quality_gate_history"] = [{"passed": True, "score": 8.5, "draft_attempt": 1}]
    execution.context["revision_history"] = [{"attempt": 1}]

    await engine._finalize_chapter_after_quality_pass(execution, db)
    await engine._finalize_chapter_after_quality_pass(execution, db)

    assert len(db.chapters) == 1
    assert len(db.hooks) == 1
    assert db.outlines["outline-pass"]["status"] == "completed"
    assert execution.context["pending_chapter_save"] is False
    assert execution.context["chapter_saved"] is True
    saved_payload = execution.context["chapter_saved_payload"]
    assert saved_payload["quality_gate_passed"] is True
    assert saved_payload["quality_gate_score"] == 8.5
    assert saved_payload["quality_gate_attempts"] == 1
    assert saved_payload["revision_attempts"] == 1
    assert saved_payload["finalized_from_draft_attempt"] == 1
    assert saved_payload["scene_plan_id"] == "plan-1"
    assert saved_payload["scene_plan_checksum"] == "scene-checksum"
    assert saved_payload["revision_directive_id"] == "rev-1"
    assert saved_payload["revision_directive_attempt"] == 1
    assert saved_payload["final_scene_coverage"] == {"required_beat_count": 1, "covered_beat_count": 1}
    assert execution.context["chapter_draft_payload"]["scene_plan_id"] == "plan-1"
    assert [event[1] for event in events].count("chapter_saved") == 1
    assert "chapter_finalized" in [event[1] for event in events]
    assert len(db.state_changes) == 1
    state_change = next(iter(db.state_changes.values()))
    assert state_change["status"] == "proposed"
    assert state_change["chapter_id"] == execution.context["chapter_id"]
    assert execution.context["state_writeback_status"] == "completed"
    assert execution.context["state_writeback_counts"] == {"proposed": 1, "applied": 0, "pending": 1, "errors": 0}
    assert [event[1] for event in events].count("chapter_state_writeback_proposed") == 1


@pytest.mark.asyncio
async def test_saved_chapter_state_writeback_auto_applies_safe_supported_entities(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.chapter_document_storage.chapter_document_storage",
        ChapterDocumentStorage(str(tmp_path)),
    )
    engine = WorkflowEngine()
    db = FakeDiscussionDB()
    db.existing_characters["char-1"] = {
        "id": "char-1",
        "project_id": "00000000-0000-0000-0000-000000000001",
        "name": "林砚",
        "status": "alive",
    }
    execution = WorkflowExecution(
        workflow_id="wf-writeback-safe",
        project_id="00000000-0000-0000-0000-000000000001",
        status=WorkflowStatus.RUNNING,
        context={"chapter_num": 8, "chapter_title": "第八章：状态", "chapter_outline_id": "outline-safe"},
        node_states={},
    )
    events = []

    async def capture_broadcast(execution_id, event_type, payload):
        events.append((execution_id, event_type, payload))

    monkeypatch.setattr(engine, "_broadcast_status", capture_broadcast)
    await engine._save_chapter_from_writer(
        execution,
        {
            "chapter_content": "状态写回正文",
            "word_count": 6,
            "state_changes": [
                {
                    "entity_type": "character",
                    "entity_id": "char-1",
                    "change_type": "status_change",
                    "title": "林砚受伤",
                    "summary": "林砚在潮汐门受伤",
                    "after_state": {"status": "injured"},
                }
            ],
        },
        db,
        source_node=type("WriterNode", (), {"id": "writer", "label": "写作", "agent_type": "writer"})(),
    )
    await engine._run_writer_finalization_side_effects(execution, {"state_changes": [
        {
            "entity_type": "character",
            "entity_id": "char-1",
            "change_type": "status_change",
            "title": "林砚受伤",
            "summary": "林砚在潮汐门受伤",
            "after_state": {"status": "injured"},
        }
    ]}, db)

    state_change = next(iter(db.state_changes.values()))
    assert state_change["status"] == "applied"
    assert db.existing_characters["char-1"]["status"] == "injured"
    assert execution.context["state_writeback_counts"] == {"proposed": 1, "applied": 1, "pending": 0, "errors": 0}
    assert "chapter_state_writeback_applied" in [event[1] for event in events]


@pytest.mark.asyncio
async def test_failed_quality_gate_records_revision_without_saving(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.chapter_document_storage.chapter_document_storage",
        ChapterDocumentStorage(str(tmp_path)),
    )
    engine = WorkflowEngine()
    db = FakeDiscussionDB()
    execution = WorkflowExecution(
        workflow_id="wf-gated-fail",
        project_id="00000000-0000-0000-0000-000000000001",
        status=WorkflowStatus.RUNNING,
        context={
            "chapter_num": 6,
            "chapter_title": "第六章：未过",
            "chapter_outline_id": "outline-fail",
            "pending_chapter_save": True,
            "chapter_draft_payload": {"draft_attempt": 1, "content_checksum": "abc", "content_chars": 12},
            "chapter_draft_attempt": 1,
            "chapter_draft_checksum": "abc",
            "scene_plan_id": "plan-fail",
            "scene_plan_checksum": "scene-fail-checksum",
            "evaluation_feedback": {
                "passed": False,
                "score": 4,
                "issues": ["逻辑断裂"],
                "suggestions": ["重写动机"],
                "scene_plan_adherence_check": {"passed": False, "failed_beat_ids": ["beat-fail"], "issues": ["beat 失败"]},
                "failed_scene_beat_ids": ["beat-fail"],
            },
        },
        node_states={},
    )
    condition_node = type("ConditionNode", (), {"id": "gate", "label": "质量门", "config": {}, "node_type": None})()
    events = []

    async def capture_broadcast(execution_id, event_type, payload):
        events.append((execution_id, event_type, payload))

    monkeypatch.setattr(engine, "_broadcast_status", capture_broadcast)

    output = await engine._execute_condition_node(condition_node, execution, db)

    assert output["quality_passed"] is False
    assert db.chapters == []
    assert execution.context["pending_chapter_save"] is True
    assert execution.context.get("chapter_saved") is not True
    assert execution.context["is_retry"] is True
    assert execution.context["revision_history"][0]["quality_summary"]["issues_count"] == 1
    assert execution.context["quality_failure_packet"]["scene_plan_id"] == "plan-fail"
    assert execution.context["quality_failure_packet"]["failed_scene_beat_ids"] == ["beat-fail"]
    assert db.state_changes == {}
    assert "saved_chapter_state_writeback" not in execution.context
    assert events == [(execution.id, "chapter_revision_requested", execution.context["revision_history"][0])]


@pytest.mark.asyncio
async def test_writer_save_failure_emits_event_and_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.chapter_document_storage.chapter_document_storage",
        ChapterDocumentStorage(str(tmp_path)),
    )
    engine = WorkflowEngine()
    db = FakeDiscussionDB()

    async def fail_save_chapter(chapter_data):
        raise RuntimeError("database unavailable")

    db.save_chapter = fail_save_chapter
    execution = WorkflowExecution(
        workflow_id="test-wf",
        project_id="00000000-0000-0000-0000-000000000001",
        status=WorkflowStatus.RUNNING,
        context={
            "chapter_num": 7,
            "chapter_title": "第七章：断链",
            "chapter_outline_id": "outline-failed",
        },
        node_states={},
    )
    broadcast_events = []

    async def capture_broadcast(execution_id, event_type, payload):
        broadcast_events.append((execution_id, event_type, payload))

    monkeypatch.setattr(engine, "_broadcast_status", capture_broadcast)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await engine._save_chapter_from_writer(
            execution,
            {"chapter_content": "保存失败正文", "word_count": 6},
            db,
        )

    assert execution.context["chapter_save_error"] == "database unavailable"
    assert execution.context.get("chapter_saved") is not True
    assert broadcast_events == [
        (
            execution.id,
            "chapter_save_failed",
            {
                "execution_id": execution.id,
                "workflow_id": execution.workflow_id,
                "project_id": execution.project_id,
                "chapter_outline_id": "outline-failed",
                "chapter_num": 7,
                "title": "第七章：断链",
                "error": "database unavailable",
            },
        )
    ]


@pytest.mark.asyncio
async def test_writer_save_retry_after_failure_clears_error_and_emits_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.chapter_document_storage.chapter_document_storage",
        ChapterDocumentStorage(str(tmp_path)),
    )
    engine = WorkflowEngine()
    db = FakeDiscussionDB()
    attempts = {"count": 0}

    async def flaky_save_chapter(chapter_data):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("database unavailable")
        db.chapters.append(dict(chapter_data))
        return chapter_data.get("id")

    db.save_chapter = flaky_save_chapter
    execution = WorkflowExecution(
        workflow_id="test-wf",
        project_id="00000000-0000-0000-0000-000000000001",
        status=WorkflowStatus.RUNNING,
        context={
            "chapter_num": 8,
            "chapter_title": "第八章：重连",
            "chapter_outline_id": "outline-recovered",
        },
        node_states={},
    )
    broadcast_events = []

    async def capture_broadcast(execution_id, event_type, payload):
        broadcast_events.append((execution_id, event_type, payload))

    monkeypatch.setattr(engine, "_broadcast_status", capture_broadcast)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await engine._save_chapter_from_writer(
            execution,
            {"chapter_content": "第一次保存失败", "word_count": 7},
            db,
        )

    assert execution.context["chapter_save_error"] == "database unavailable"

    writer_node = type("WriterNode", (), {"id": "writer", "label": "写作", "agent_type": "writer"})()
    await engine._save_chapter_from_writer(
        execution,
        {"chapter_content": "恢复后的正文", "word_count": 6},
        db,
        source_node=writer_node,
        contract_metadata={"output_contract_id": "writer.workflow_output"},
        prompt_trace={"prompt_ids": ["function_writing"]},
    )

    assert "chapter_save_error" not in execution.context
    assert execution.context["chapter_saved"] is True
    assert execution.context["chapter_saved_payload"]["chapter_id"] == execution.context["chapter_id"]
    assert execution.context["chapter_saved_payload"]["content_path"] == db.chapters[0]["content_path"]
    assert [event[1] for event in broadcast_events] == ["chapter_save_failed", "chapter_saved"]
    saved_payload = broadcast_events[-1][2]
    assert saved_payload["chapter_id"] == execution.context["chapter_id"]
    assert saved_payload["content_checksum"] == db.chapters[0]["content_checksum"]
    assert saved_payload["source_node_id"] == "writer"
    assert saved_payload["source_output_contract_id"] == "writer.workflow_output"
    assert saved_payload["writer_prompt_trace_present"] is True
    assert saved_payload["writer_prompt_trace"]["prompt_ids"] == ["function_writing"]
    assert "content" not in saved_payload
