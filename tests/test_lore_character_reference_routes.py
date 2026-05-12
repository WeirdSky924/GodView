import json

import pytest
from fastapi.testclient import TestClient

import app.api.app as app_module
import app.api.routes.lore as lore_routes
from app.api.app import create_app


PROJECT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CHARACTER_ID = "11111111-1111-1111-1111-111111111111"
SECOND_CHARACTER_ID = "22222222-2222-2222-2222-222222222222"
LORE_ID = "99999999-9999-9999-9999-999999999999"


class FakeReferenceRouteDb:
    def __init__(self):
        self.characters = [
            {
                "id": CHARACTER_ID,
                "project_id": PROJECT_ID,
                "name": "林默",
                "aliases": ["林队"],
                "role": "main",
                "importance_tier": "protagonist",
                "description": "主角",
            },
            {
                "id": SECOND_CHARACTER_ID,
                "project_id": PROJECT_ID,
                "name": "K",
                "aliases": ["K老师"],
                "role": "supporting",
                "importance_tier": "mentor",
                "description": "AI 导师",
            },
        ]
        self.lore_rows = {
            LORE_ID: {
                "id": LORE_ID,
                "project_id": PROJECT_ID,
                "title": "已有设定",
                "category": "character_setting",
                "priority": "standard",
                "content": "已有设定内容",
                "related_characters": [CHARACTER_ID],
                "related_character_refs": [
                    {
                        "status": "resolved",
                        "source_text": "林默",
                        "character_id": CHARACTER_ID,
                        "character_name": "林默",
                        "resolution_method": "exact_name",
                    }
                ],
                "unresolved_character_refs": [
                    {"status": "unresolved", "source_text": "未知观察者", "reason": "no_deterministic_match", "message": "未匹配"},
                    {"status": "unresolved", "source_text": "旁观者", "reason": "no_deterministic_match", "message": "未匹配"},
                ],
            }
        }
        self.writes = []
        self.saved_resolutions = []
        self.saved_characters = []
        self.assistant_deltas = []

    async def save_assistant_delta(self, delta):
        self.assistant_deltas.append(delta)
        return "delta-test"

    async def find_duplicate_lore(self, project_id, title, content):
        return None

    async def get_characters_for_reference_resolution(self, project_id):
        return [item for item in self.characters if item["project_id"] == project_id]

    async def get_character(self, character_id):
        return next((item for item in self.characters if item["id"] == character_id), None)

    async def save_character(self, character):
        self.saved_characters.append(character)
        self.characters.append(character)
        return character

    async def save_lore_character_reference_resolution(self, *, lore_id, project_id, resolution):
        self.saved_resolutions.append(
            {"lore_id": lore_id, "project_id": project_id, "resolution": resolution}
        )
        if lore_id in self.lore_rows:
            self.lore_rows[lore_id]["related_characters"] = resolution.get("related_characters", [])
            self.lore_rows[lore_id]["related_character_refs"] = resolution.get("related_character_refs", [])
            self.lore_rows[lore_id]["unresolved_character_refs"] = resolution.get("unresolved_character_refs", [])

    async def execute_write(self, query, params=None):
        self.writes.append({"query": query, "params": params or {}})
        return 1

    async def execute_query(self, query, params=None):
        if "information_schema.columns" in query:
            return [
                {"column_name": "title"},
                {"column_name": "content"},
                {"column_name": "summary"},
                {"column_name": "category"},
                {"column_name": "priority"},
                {"column_name": "related_characters"},
                {"column_name": "related_character_refs"},
                {"column_name": "unresolved_character_refs"},
            ]
        if "SELECT * FROM lore_entries" in query:
            lore = self.lore_rows.get((params or {}).get("id"))
            if lore and lore.get("project_id") == (params or {}).get("project_id"):
                return [lore]
            return []
        if "SELECT id FROM lore_entries" in query:
            return [{"id": LORE_ID}]
        if "SELECT project_id FROM lore_entries" in query:
            return [{"project_id": PROJECT_ID}]
        return []


@pytest.fixture
def route_client(monkeypatch):
    fake_db = FakeReferenceRouteDb()
    app = create_app()
    monkeypatch.setattr(app_module, "postgres_db", fake_db)
    monkeypatch.setattr(app_module, "nebula_db", None)
    monkeypatch.setattr(lore_routes, "_lore_entry_columns_cache", None)
    monkeypatch.setattr(lore_routes, "_invalidate_plot_outline_context", lambda project_id: None)

    return TestClient(app), fake_db


def test_setting_agent_reference_preflight_route_returns_canonical_and_unresolved(route_client):
    client, _ = route_client

    response = client.post(
        "/api/setting-agent/resolve-character-references",
        json={
            "project_id": PROJECT_ID,
            "references": ["林队", "不存在的人"],
            "provenance": {"test": "preflight_route"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["related_characters"] == [CHARACTER_ID]
    assert data["related_character_refs"][0]["character_id"] == CHARACTER_ID
    assert data["related_character_refs"][0]["resolution_method"] == "exact_alias"
    assert data["unresolved_character_refs"][0]["source_text"] == "不存在的人"
    assert data["unresolved_character_refs"][0]["reason"] == "no_deterministic_match"


def test_create_lore_route_persists_only_canonical_character_ids(route_client):
    client, fake_db = route_client

    response = client.post(
        "/api/lore",
        json={
            "project_id": PROJECT_ID,
            "title": "林默与神网规则",
            "category": "character_setting",
            "priority": "core",
            "content": "林默可以调用神网，但未知观察者还没有角色卡。",
            "related_characters": ["林默", "未知观察者"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    resolution = data["character_reference_resolution"]
    assert resolution["related_characters"] == [CHARACTER_ID]
    assert resolution["unresolved_character_refs"][0]["source_text"] == "未知观察者"

    insert_params = fake_db.writes[0]["params"]
    assert json.loads(insert_params["related_characters"]) == [CHARACTER_ID]
    assert json.loads(insert_params["related_character_refs"])[0]["resolution_method"] == "exact_name"
    unresolved = json.loads(insert_params["unresolved_character_refs"])
    assert unresolved[0]["reason"] == "no_deterministic_match"
    assert "未知观察者" not in json.loads(insert_params["related_characters"])

    assert fake_db.saved_resolutions[0]["resolution"]["related_characters"] == [CHARACTER_ID]


def test_update_lore_route_resolves_reference_fields_before_update(route_client):
    client, fake_db = route_client

    response = client.put(
        f"/api/lore/{LORE_ID}",
        json={
            "related_characters": [SECOND_CHARACTER_ID, "影子角色"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    resolution = data["character_reference_resolution"]
    assert resolution["related_characters"] == [SECOND_CHARACTER_ID]
    assert resolution["related_character_refs"][0]["resolution_method"] == "id"
    assert resolution["unresolved_character_refs"][0]["source_text"] == "影子角色"

    update_write = fake_db.writes[0]
    assert "related_character_refs = CAST(:related_character_refs AS jsonb)" in update_write["query"]
    assert "unresolved_character_refs = CAST(:unresolved_character_refs AS jsonb)" in update_write["query"]
    assert json.loads(update_write["params"]["related_characters"]) == [SECOND_CHARACTER_ID]
    assert json.loads(update_write["params"]["unresolved_character_refs"])[0]["reason"] == "no_deterministic_match"
    assert fake_db.saved_resolutions[0]["lore_id"] == LORE_ID


def test_bind_lore_character_reference_to_existing_preserves_reference_state(route_client):
    client, fake_db = route_client

    response = client.post(
        f"/api/lore/{LORE_ID}/character-references/bind",
        json={
            "project_id": PROJECT_ID,
            "source_text": "未知观察者",
            "action": "bind_existing",
            "character_id": SECOND_CHARACTER_ID,
            "provenance": {"test": "bind_existing"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    resolution = data["character_reference_resolution"]
    assert resolution["related_characters"] == [CHARACTER_ID, SECOND_CHARACTER_ID]
    assert resolution["related_character_refs"][-1]["resolution_method"] == "user_bind_existing"
    assert resolution["related_character_refs"][-1]["source_text"] == "未知观察者"
    assert [item["source_text"] for item in resolution["unresolved_character_refs"]] == ["旁观者"]
    assert fake_db.saved_resolutions[-1]["resolution"] == resolution
    assert fake_db.assistant_deltas[-1]["operation"] == "bind_lore_character_reference"


def test_bind_lore_character_reference_create_character(route_client, monkeypatch):
    client, fake_db = route_client

    class FakeGraphProjectionService:
        async def enqueue_character_projection(self, character):
            return {"status": "queued"}

    monkeypatch.setattr(
        "app.services.graph_projection_service.get_graph_projection_service",
        lambda: FakeGraphProjectionService(),
    )

    response = client.post(
        f"/api/lore/{LORE_ID}/character-references/bind",
        json={
            "project_id": PROJECT_ID,
            "source_text": "未知观察者",
            "action": "create_character",
            "character": {
                "name": "未知观察者",
                "description": "由未解析引用创建",
                "status": "active",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    created_character = fake_db.saved_characters[-1]
    assert created_character["project_id"] == PROJECT_ID
    assert created_character["name"] == "未知观察者"
    assert created_character["importance_tier"] == "npc"
    assert created_character["role"] == "npc"
    assert data["character"]["id"] == created_character["id"]
    resolution = data["character_reference_resolution"]
    assert created_character["id"] in resolution["related_characters"]
    assert resolution["related_character_refs"][-1]["resolution_method"] == "user_create_character"
    assert [item["source_text"] for item in resolution["unresolved_character_refs"]] == ["旁观者"]


def test_bind_lore_character_reference_rejects_cross_project_character(route_client):
    client, fake_db = route_client
    fake_db.characters.append({
        "id": "33333333-3333-3333-3333-333333333333",
        "project_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "name": "外部角色",
    })

    response = client.post(
        f"/api/lore/{LORE_ID}/character-references/bind",
        json={
            "project_id": PROJECT_ID,
            "source_text": "未知观察者",
            "action": "bind_existing",
            "character_id": "33333333-3333-3333-3333-333333333333",
        },
    )

    assert response.status_code == 409
    assert fake_db.saved_resolutions == []


def test_bind_lore_character_reference_rejects_stale_source_text(route_client):
    client, fake_db = route_client

    response = client.post(
        f"/api/lore/{LORE_ID}/character-references/bind",
        json={
            "project_id": PROJECT_ID,
            "source_text": "已经不存在",
            "action": "bind_existing",
            "character_id": SECOND_CHARACTER_ID,
        },
    )

    assert response.status_code == 409
    assert fake_db.saved_resolutions == []
