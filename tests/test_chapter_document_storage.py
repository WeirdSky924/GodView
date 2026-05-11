import pytest

from app.api.routes import plots
from app.services.chapter_document_storage import ChapterDocumentStorage


class FakeChapterDB:
    def __init__(self):
        self.chapters = {}
        self.deleted_ids = []
        self.worlds = {}

    async def save_chapter(self, chapter_data):
        self.chapters[chapter_data["id"]] = dict(chapter_data)
        return chapter_data["id"]

    async def get_chapter(self, chapter_id):
        chapter = self.chapters.get(chapter_id)
        return dict(chapter) if chapter else None

    async def get_chapters_by_project(self, project_id, status=None, limit=100):
        rows = [dict(row) for row in self.chapters.values() if row.get("project_id") == project_id]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows[:limit]

    async def get_chapters_by_world(self, world_id):
        return [dict(row) for row in self.chapters.values() if row.get("world_id") == world_id]

    async def get_world(self, world_id):
        return self.worlds.get(world_id)

    async def execute_write(self, query, params=None):
        self.deleted_ids.append(params["id"])
        self.chapters.pop(params["id"], None)


@pytest.fixture()
def fake_chapter_db(monkeypatch, tmp_path):
    db = FakeChapterDB()
    monkeypatch.setattr("app.api.app.postgres_db", db)
    monkeypatch.setattr(
        "app.services.chapter_document_storage.chapter_document_storage",
        ChapterDocumentStorage(str(tmp_path)),
    )
    return db, tmp_path


@pytest.mark.asyncio
async def test_create_chapter_writes_file_and_stores_path(fake_chapter_db):
    db, tmp_path = fake_chapter_db

    result = await plots.create_chapter(plots.CreateChapterDTO(
        title="第一章：启程",
        project_id="00000000-0000-0000-0000-000000000001",
        content="正文内容",
        chapter_outline_id="outline-001",
    ))

    stored = db.chapters[result["id"]]
    assert stored["content"] == ""
    assert stored["content_storage"] == "filesystem"
    assert stored["chapter_outline_id"] == "outline-001"
    assert stored["content_path"]
    assert (tmp_path / stored["content_path"]).read_text(encoding="utf-8") == "正文内容"
    assert result["chapter_outline_id"] == "outline-001"
    assert result["content"] == "正文内容"


@pytest.mark.asyncio
async def test_get_chapter_hydrates_filesystem_content(fake_chapter_db):
    db, tmp_path = fake_chapter_db
    storage = ChapterDocumentStorage(str(tmp_path))
    metadata = storage.write_chapter("00000000-0000-0000-0000-000000000002", "00000000-0000-0000-0000-000000000001", "第二章", "文件正文")
    db.chapters["00000000-0000-0000-0000-000000000002"] = {
        "id": "00000000-0000-0000-0000-000000000002",
        "title": "第二章",
        "project_id": "00000000-0000-0000-0000-000000000001",
        "content": "",
        **metadata,
    }

    result = await plots.get_chapter("00000000-0000-0000-0000-000000000002")

    assert result["content"] == "文件正文"


@pytest.mark.asyncio
async def test_existing_database_content_remains_readable(fake_chapter_db):
    db, _ = fake_chapter_db
    db.chapters["00000000-0000-0000-0000-000000000003"] = {
        "id": "00000000-0000-0000-0000-000000000003",
        "title": "旧章节",
        "project_id": "00000000-0000-0000-0000-000000000001",
        "content": "数据库正文",
        "content_storage": "database",
    }

    result = await plots.get_chapter("00000000-0000-0000-0000-000000000003")

    assert result["content"] == "数据库正文"


@pytest.mark.asyncio
async def test_update_content_rewrites_file_and_rename_changes_path(fake_chapter_db):
    db, tmp_path = fake_chapter_db
    created = await plots.create_chapter(plots.CreateChapterDTO(
        title="原名",
        project_id="00000000-0000-0000-0000-000000000001",
        content="旧正文",
    ))
    old_path = db.chapters[created["id"]]["content_path"]

    db.chapters[created["id"]]["chapter_outline_id"] = "outline-preserved"
    updated = await plots.update_chapter(created["id"], plots.UpdateChapterDTO(
        title="新名",
        content="新正文",
    ))

    stored = db.chapters[created["id"]]
    assert stored["content"] == ""
    assert stored["chapter_outline_id"] == "outline-preserved"
    assert stored["content_path"] != old_path
    assert not (tmp_path / old_path).exists()
    assert (tmp_path / stored["content_path"]).read_text(encoding="utf-8") == "新正文"
    assert updated["chapter_outline_id"] == "outline-preserved"
    assert updated["content"] == "新正文"


@pytest.mark.asyncio
async def test_delete_chapter_renames_file_and_removes_db_row(fake_chapter_db):
    db, tmp_path = fake_chapter_db
    created = await plots.create_chapter(plots.CreateChapterDTO(
        title="待删除",
        project_id="00000000-0000-0000-0000-000000000001",
        content="删除正文",
    ))
    content_path = db.chapters[created["id"]]["content_path"]
    assert (tmp_path / content_path).exists()

    result = await plots.delete_chapter(created["id"])

    assert not (tmp_path / content_path).exists()
    assert result["archived_content_path"]
    archived_path = tmp_path / result["archived_content_path"]
    assert archived_path.exists()
    assert archived_path.name.endswith(".md")
    assert "__deleted_" in archived_path.name
    assert archived_path.read_text(encoding="utf-8") == "删除正文"
    assert created["id"] in db.deleted_ids


def test_chapter_storage_rejects_path_traversal(tmp_path):
    storage = ChapterDocumentStorage(str(tmp_path))

    with pytest.raises(ValueError):
        storage.read_chapter_content("../escape.md")
