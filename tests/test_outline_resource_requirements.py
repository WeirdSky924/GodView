import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.chapter_outlines import (
    ConfirmResourceSupplementDraft,
    ConfirmResourceSupplementDraftsRequest,
    CreateResourceRequirementRequest,
    UpdateResourceRequirementStatusRequest,
    confirm_resource_supplements,
    create_resource_requirement,
    list_resource_readiness,
    list_resource_requirements,
    update_resource_requirement_status,
)
from app.database.postgres import PostgresDatabase


PROJECT_ID = str(uuid.uuid4())
OTHER_PROJECT_ID = str(uuid.uuid4())
REQUIREMENT_ID = str(uuid.uuid4())
CHARACTER_ID = str(uuid.uuid4())
LORE_ID = str(uuid.uuid4())
REGION_ID = str(uuid.uuid4())
OUTLINE_ID = "outline_runtime_smoke"


class _RouteFakePostgresDB:
    def __init__(self):
        self.updated_calls = []
        self.readiness_calls = []
        self.list_requirement_calls = []
        self.list_readiness_calls = []
        self.saved_characters = []
        self.saved_requirements = []
        self.requirement_rows = [{"id": REQUIREMENT_ID}]
        self.updated_requirement = {
            "id": REQUIREMENT_ID,
            "project_id": PROJECT_ID,
            "outline_id": OUTLINE_ID,
            "chapter_num": 3,
            "status": "resolved",
        }
        self.return_none = False
        self.raise_value_error = False

    async def update_outline_resource_requirement_status(self, **kwargs):
        self.updated_calls.append(kwargs)
        if self.raise_value_error:
            raise ValueError("bad requirement")
        if self.return_none:
            return None
        return dict(self.updated_requirement, **kwargs)

    async def update_chapter_resource_readiness(self, **kwargs):
        self.readiness_calls.append(kwargs)
        return {"project_id": kwargs["project_id"], "chapter_num": kwargs["chapter_num"], "readiness_status": "ready"}

    async def get_outline_resource_requirements(self, **kwargs):
        self.list_requirement_calls.append(kwargs)
        return [{"id": REQUIREMENT_ID, **kwargs}]

    async def get_chapter_resource_readiness(self, **kwargs):
        self.list_readiness_calls.append(kwargs)
        return [{"project_id": kwargs["project_id"], "chapter_num": kwargs.get("chapter_num") or 3, "readiness_status": "ready"}]

    async def save_outline_resource_requirement(self, requirement_data):
        requirement_id = str(uuid.uuid4())
        saved = {"id": requirement_id, **requirement_data}
        self.saved_requirements.append(saved)
        self.requirement_rows = [saved]
        return requirement_id

    async def execute_query(self, query, params=None):
        return list(self.requirement_rows)

    async def save_character(self, character_data):
        saved = dict(character_data)
        saved.setdefault("id", CHARACTER_ID)
        self.saved_characters.append(saved)
        return saved["id"]


@pytest.fixture
def route_db(monkeypatch):
    db = _RouteFakePostgresDB()
    import app.api.app as api_app

    monkeypatch.setattr(api_app, "postgres_db", db)
    return db


@pytest.mark.asyncio
async def test_update_route_passes_resolution_method_and_refreshes_readiness(route_db):
    result = await update_resource_requirement_status(
        REQUIREMENT_ID,
        UpdateResourceRequirementStatusRequest(
            status="resolved",
            matched_resource_id=CHARACTER_ID,
            matched_resource_type="character",
            resolution_method="bind_existing",
        ),
    )

    assert route_db.updated_calls[-1]["resolution_method"] == "bind_existing"
    assert route_db.updated_calls[-1]["matched_resource_id"] == CHARACTER_ID
    assert route_db.readiness_calls == [{"project_id": PROJECT_ID, "outline_id": OUTLINE_ID, "chapter_num": 3}]
    assert result["readiness"]["readiness_status"] == "ready"


@pytest.mark.asyncio
async def test_list_resource_requirements_rejects_invalid_project_id_before_db(route_db):
    with pytest.raises(HTTPException) as exc_info:
        await list_resource_requirements(project_id="__missing__", status="pending")

    assert exc_info.value.status_code == 400
    assert "项目 ID" in exc_info.value.detail
    assert route_db.list_requirement_calls == []


@pytest.mark.asyncio
async def test_list_resource_requirements_normalizes_filters_before_db(route_db):
    result = await list_resource_requirements(
        project_id=PROJECT_ID,
        outline_id=OUTLINE_ID,
        chapter_num=3,
        status="PENDING",
        severity="BLOCKING",
        requirement_type="character",
    )

    assert result["total"] == 1
    assert route_db.list_requirement_calls[-1] == {
        "project_id": PROJECT_ID,
        "outline_id": OUTLINE_ID,
        "chapter_num": 3,
        "status": "pending",
        "severity": "blocking",
        "requirement_type": "character",
    }


@pytest.mark.asyncio
async def test_list_resource_readiness_accepts_text_outline_id(route_db):
    result = await list_resource_readiness(
        project_id=PROJECT_ID,
        outline_id="outline_runtime_smoke",
        chapter_num=3,
        refresh=False,
    )

    assert result["total"] == 1
    assert route_db.list_readiness_calls[-1] == {
        "project_id": PROJECT_ID,
        "outline_id": "outline_runtime_smoke",
        "chapter_num": 3,
    }
    assert route_db.readiness_calls == []


@pytest.mark.asyncio
async def test_list_resource_readiness_rejects_malformed_outline_id_before_db(route_db):
    with pytest.raises(HTTPException) as exc_info:
        await list_resource_readiness(project_id=PROJECT_ID, outline_id="outline bad", chapter_num=3, refresh=False)

    assert exc_info.value.status_code == 400
    assert "大纲 ID" in exc_info.value.detail
    assert route_db.list_readiness_calls == []
    assert route_db.readiness_calls == []


@pytest.mark.asyncio
async def test_update_route_rejects_invalid_requirement_id_before_db(route_db):
    with pytest.raises(HTTPException) as exc_info:
        await update_resource_requirement_status(
            "bad-requirement",
            UpdateResourceRequirementStatusRequest(status="resolved", resolution_method="manual_resolved"),
        )

    assert exc_info.value.status_code == 400
    assert "资源需求 ID" in exc_info.value.detail
    assert route_db.updated_calls == []
    assert route_db.readiness_calls == []


@pytest.mark.asyncio
async def test_update_route_rejects_invalid_matched_resource_id_before_db(route_db):
    with pytest.raises(HTTPException) as exc_info:
        await update_resource_requirement_status(
            REQUIREMENT_ID,
            UpdateResourceRequirementStatusRequest(
                status="resolved",
                matched_resource_id="not-a-resource-id",
                matched_resource_type="character",
                resolution_method="bind_existing",
            ),
        )

    assert exc_info.value.status_code == 400
    assert "绑定资源 ID" in exc_info.value.detail
    assert route_db.updated_calls == []
    assert route_db.readiness_calls == []


@pytest.mark.asyncio
async def test_update_route_rejects_invalid_status_before_db(route_db):
    with pytest.raises(HTTPException) as exc_info:
        await update_resource_requirement_status(
            REQUIREMENT_ID,
            UpdateResourceRequirementStatusRequest(status="done", resolution_method="manual_resolved"),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "无效的资源需求状态"
    assert route_db.updated_calls == []


@pytest.mark.asyncio
async def test_update_route_returns_404_when_requirement_missing(route_db):
    route_db.return_none = True

    with pytest.raises(HTTPException) as exc_info:
        await update_resource_requirement_status(
            REQUIREMENT_ID,
            UpdateResourceRequirementStatusRequest(status="resolved", resolution_method="manual_resolved"),
        )

    assert exc_info.value.status_code == 404
    assert route_db.readiness_calls == []


@pytest.mark.asyncio
async def test_update_route_returns_400_for_db_validation_error(route_db):
    route_db.raise_value_error = True

    with pytest.raises(HTTPException) as exc_info:
        await update_resource_requirement_status(
            REQUIREMENT_ID,
            UpdateResourceRequirementStatusRequest(status="resolved", resolution_method="manual_resolved"),
        )

    assert exc_info.value.status_code == 400
    assert route_db.readiness_calls == []


@pytest.mark.asyncio
async def test_confirm_resource_supplements_marks_requirement_as_created_resource(route_db):
    request = ConfirmResourceSupplementDraftsRequest(
        project_id=PROJECT_ID,
        drafts=[
            ConfirmResourceSupplementDraft(
                requirement_id=REQUIREMENT_ID,
                resource_type="character",
                draft_payload={"name": "补全角色", "description": "来自需求"},
            )
        ],
    )

    result = await confirm_resource_supplements(request)

    assert result["success"] is True
    assert route_db.updated_calls[-1]["resolution_method"] == "create_resource"
    assert route_db.updated_calls[-1]["matched_resource_type"] == "character"
    assert route_db.readiness_calls[-1] == {"project_id": PROJECT_ID, "outline_id": OUTLINE_ID, "chapter_num": 3}


@pytest.mark.asyncio
async def test_debug_create_resource_requirement_persists_and_refreshes_readiness(route_db, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "debug", True)

    result = await create_resource_requirement(
        CreateResourceRequirementRequest(
            project_id=PROJECT_ID,
            outline_id=OUTLINE_ID,
            chapter_num=3,
            requirement_type="character",
            resource_name="缺失角色",
            severity="blocking",
            status="pending",
            reason="启动前必须补齐",
        )
    )

    assert result["requirement"]["severity"] == "blocking"
    assert route_db.saved_requirements[-1]["metadata"]["created_by"] == "debug_resource_requirement_api"
    assert route_db.readiness_calls[-1] == {"project_id": PROJECT_ID, "outline_id": OUTLINE_ID, "chapter_num": 3}
    assert result["readiness"]["readiness_status"] == "ready"


@pytest.mark.asyncio
async def test_debug_create_resource_requirement_rejects_invalid_project_id_before_db(route_db, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "debug", True)

    with pytest.raises(HTTPException) as exc_info:
        await create_resource_requirement(
            CreateResourceRequirementRequest(
                project_id="not-a-project-id",
                outline_id=OUTLINE_ID,
                chapter_num=3,
                requirement_type="character",
                resource_name="缺失角色",
            )
        )

    assert exc_info.value.status_code == 400
    assert "项目 ID" in exc_info.value.detail
    assert route_db.saved_requirements == []
    assert route_db.readiness_calls == []


@pytest.mark.asyncio
async def test_debug_create_resource_requirement_rejects_invalid_severity_before_db(route_db, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "debug", True)

    with pytest.raises(HTTPException) as exc_info:
        await create_resource_requirement(
            CreateResourceRequirementRequest(
                project_id=PROJECT_ID,
                outline_id=OUTLINE_ID,
                chapter_num=3,
                requirement_type="character",
                resource_name="缺失角色",
                severity="fatal",
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "无效的资源需求严重级别"
    assert route_db.saved_requirements == []


@pytest.mark.asyncio
async def test_debug_create_resource_requirement_is_hidden_when_debug_disabled(route_db, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "debug", False)

    with pytest.raises(HTTPException) as exc_info:
        await create_resource_requirement(
            CreateResourceRequirementRequest(
                project_id=PROJECT_ID,
                outline_id=OUTLINE_ID,
                chapter_num=3,
                requirement_type="character",
                resource_name="缺失角色",
            )
        )

    assert exc_info.value.status_code == 404
    assert route_db.saved_requirements == []


class _RequirementStatusDB(PostgresDatabase):
    def __init__(self):
        self.requirement = {
            "id": REQUIREMENT_ID,
            "project_id": PROJECT_ID,
            "outline_id": OUTLINE_ID,
            "chapter_num": 2,
            "status": "pending",
            "metadata": {"source": "test"},
            "resolved_at": None,
        }
        self.characters = {CHARACTER_ID: {"id": CHARACTER_ID, "project_id": PROJECT_ID}}
        self.lore_entries = {LORE_ID: {"id": LORE_ID, "project_id": PROJECT_ID}}
        self.region_project_ids = {REGION_ID: PROJECT_ID}
        self.last_update_params = None

    async def execute_query(self, query, params=None):
        params = params or {}
        if "SELECT * FROM outline_resource_requirements" in query:
            return [dict(self.requirement)] if params.get("id") == REQUIREMENT_ID else []
        if "UPDATE outline_resource_requirements" in query:
            self.last_update_params = dict(params)
            metadata = json.loads(params["metadata"])
            updated = dict(self.requirement)
            updated.update({
                "status": params["status"],
                "matched_resource_id": params["matched_resource_id"],
                "matched_resource_type": params["matched_resource_type"],
                "metadata": metadata,
                "updated_at": params["updated_at"],
                "resolved_at": None if params["status"] in {"pending", "in_progress"} else params["updated_at"],
            })
            self.requirement = updated
            return [dict(updated)]
        if "FROM regions r" in query:
            if self.region_project_ids.get(params.get("resource_id")) == params.get("project_id"):
                return [{"id": params.get("resource_id")}]
            return []
        return []

    async def get_character(self, character_id):
        return self.characters.get(character_id)

    async def get_lore_entry(self, lore_id):
        return self.lore_entries.get(lore_id)


@pytest.mark.asyncio
async def test_db_manual_resolved_writes_metadata_without_resource():
    db = _RequirementStatusDB()

    updated = await db.update_outline_resource_requirement_status(
        REQUIREMENT_ID,
        status="resolved",
        resolution_method="manual_resolved",
    )

    assert updated["metadata"]["resolution_method"] == "manual_resolved"
    assert updated["metadata"]["previous_status"] == "pending"
    assert updated["matched_resource_id"] is None


@pytest.mark.asyncio
async def test_db_ignored_writes_metadata():
    db = _RequirementStatusDB()

    updated = await db.update_outline_resource_requirement_status(
        REQUIREMENT_ID,
        status="ignored",
        resolution_method="ignored",
    )

    assert updated["metadata"]["resolution_method"] == "ignored"
    assert "resolution_recorded_at" in updated["metadata"]


@pytest.mark.asyncio
async def test_db_bind_existing_requires_and_validates_resource():
    db = _RequirementStatusDB()

    updated = await db.update_outline_resource_requirement_status(
        REQUIREMENT_ID,
        status="resolved",
        matched_resource_id=CHARACTER_ID,
        matched_resource_type="character",
        resolution_method="bind_existing",
    )

    assert updated["matched_resource_id"] == CHARACTER_ID
    assert updated["matched_resource_type"] == "character"
    assert updated["metadata"]["resolved_with_resource_type"] == "character"


@pytest.mark.asyncio
async def test_db_create_resource_supports_lore_binding():
    db = _RequirementStatusDB()

    updated = await db.update_outline_resource_requirement_status(
        REQUIREMENT_ID,
        status="resolved",
        matched_resource_id=LORE_ID,
        matched_resource_type="lore",
        resolution_method="create_resource",
    )

    assert updated["metadata"]["resolution_method"] == "create_resource"
    assert updated["metadata"]["resolved_with_resource_type"] == "lore"


@pytest.mark.asyncio
async def test_db_location_alias_is_validated_and_normalized():
    db = _RequirementStatusDB()

    updated = await db.update_outline_resource_requirement_status(
        REQUIREMENT_ID,
        status="resolved",
        matched_resource_id=REGION_ID,
        matched_resource_type="region",
        resolution_method="bind_existing",
    )

    assert updated["matched_resource_type"] == "location"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "resolved", "matched_resource_id": CHARACTER_ID, "resolution_method": "bind_existing"},
        {"status": "resolved", "matched_resource_id": CHARACTER_ID, "matched_resource_type": "character", "resolution_method": "manual_resolved"},
        {"status": "ignored", "matched_resource_id": CHARACTER_ID, "matched_resource_type": "character", "resolution_method": "ignored"},
        {"status": "resolved", "resolution_method": "unknown"},
        {"status": "in_progress", "resolution_method": "manual_resolved"},
        {"status": "ignored", "resolution_method": "manual_resolved"},
        {"status": "resolved", "matched_resource_id": str(uuid.uuid4()), "matched_resource_type": "character", "resolution_method": "bind_existing"},
        {"status": "resolved", "matched_resource_id": CHARACTER_ID, "matched_resource_type": "bad_type", "resolution_method": "bind_existing"},
    ],
)
async def test_db_rejects_invalid_resolution_combinations(kwargs):
    db = _RequirementStatusDB()

    with pytest.raises(ValueError):
        await db.update_outline_resource_requirement_status(REQUIREMENT_ID, **kwargs)


@pytest.mark.asyncio
async def test_db_reopen_clears_resolved_at_and_records_reopened_metadata():
    db = _RequirementStatusDB()
    db.requirement.update({
        "status": "resolved",
        "metadata": {"resolution_method": "manual_resolved"},
        "resolved_at": "old",
    })

    updated = await db.update_outline_resource_requirement_status(REQUIREMENT_ID, status="in_progress")

    assert updated["resolved_at"] is None
    assert updated["metadata"]["reopened_at"]
    assert updated["metadata"]["previous_status"] == "resolved"


class _SaveRequirementDB(PostgresDatabase):
    def __init__(self, rows):
        self.rows = rows
        self.saved_query = None
        self.saved_params = None

    async def execute_query(self, query, params=None):
        self.saved_query = query
        self.saved_params = dict(params or {})
        return list(self.rows)


@pytest.mark.asyncio
async def test_save_outline_resource_requirement_returns_actual_upserted_id():
    existing_id = str(uuid.uuid4())
    db = _SaveRequirementDB([{"id": existing_id}])

    saved_id = await db.save_outline_resource_requirement({
        "id": str(uuid.uuid4()),
        "project_id": PROJECT_ID,
        "outline_id": OUTLINE_ID,
        "chapter_num": 3,
        "requirement_type": "character",
        "resource_name": "缺失角色",
        "severity": "blocking",
        "status": "pending",
        "reason": "同 fingerprint 的历史需求",
    })

    assert saved_id == existing_id
    assert "RETURNING id" in db.saved_query
    assert db.saved_params["fingerprint"].startswith(f"{PROJECT_ID}|{OUTLINE_ID}|3|character|缺失角色")


class _SaveCharacterDB(PostgresDatabase):
    def __init__(self):
        self.saved_query = None
        self.saved_params = None

    async def execute_write(self, query, params=None):
        self.saved_query = query
        self.saved_params = dict(params or {})
        return 1


@pytest.mark.asyncio
async def test_save_character_minimal_payload_fills_all_sql_params():
    db = _SaveCharacterDB()

    character_id = await db.save_character({"name": "最小角色"})

    assert uuid.UUID(character_id)
    params = db.saved_params
    expected_keys = {
        "id", "name", "project_id", "world_id", "description", "role", "status",
        "appearance", "age", "gender", "personality", "background_story", "speech_pattern",
        "current_location", "current_location_reason", "has_agent", "agent_enabled",
        "importance_tier", "narrative_weight", "story_arc_role", "plot_priority",
        "total_scenes", "dialogue_count", "debut_chapter", "debut_scene", "exit_chapter",
        "exit_reason", "active_arc", "relationships", "key_relationships", "lexicon",
        "forbidden_words", "voice_samples", "attributes", "goals", "inventory",
        "death_detail", "available_presence_types", "agent_goals", "agent_memory",
        "personality_traits", "major_events",
    }
    assert expected_keys.issubset(params.keys())
    assert params["description"] == ""
    assert params["role"] == "npc"
    assert params["status"] == "active"
    assert params["has_agent"] is False
    assert params["agent_enabled"] is True
    assert json.loads(params["relationships"]) == []
    assert json.loads(params["attributes"]) == {}
