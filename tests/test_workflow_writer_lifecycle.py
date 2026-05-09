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

    await engine._save_chapter_from_writer(
        execution,
        {
            "chapter_content": "归航正文",
            "word_count": 4,
            "metadata": {"word_count_passed": True},
        },
        db,
    )

    assert db.chapters[0]["chapter_outline_id"] == "outline-ready"
    assert db.chapters[0]["content"] == ""
    assert db.chapters[0]["content_storage"] == "filesystem"
    saved_path = tmp_path / db.chapters[0]["content_path"]
    assert saved_path.read_text(encoding="utf-8") == "归航正文"
    assert db.outlines["outline-ready"]["status"] == "completed"
    assert db.outline_status_events[0]["project_id"] == execution.project_id
    assert execution.context["chapter_saved"] is True
    assert execution.context["chapter_outline_status"] == "completed"


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
