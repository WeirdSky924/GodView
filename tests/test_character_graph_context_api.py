import pytest
from fastapi.testclient import TestClient

import app.api.app as app_module
from app.api.app import create_app


class FakePostgres:
    async def get_character(self, character_id):
        if character_id == "char-1":
            return {
                "id": "char-1",
                "name": "林砚",
                "project_id": "proj-1",
                "key_relationships": {"char-2": "盟友"},
            }
        if character_id == "char-2":
            return {"id": "char-2", "name": "洛澜", "project_id": "proj-1", "key_relationships": {}}
        return None

    async def get_all_characters(self, project_id=None, role=None, limit=100):
        return [
            {"id": "char-1", "name": "林砚", "project_id": "proj-1", "key_relationships": {"char-2": "盟友"}},
            {"id": "char-2", "name": "洛澜", "project_id": "proj-1", "key_relationships": {}},
        ]

    async def get_all_hooks(self, project_id=None, status=None, limit=100):
        return []


@pytest.fixture
def client(monkeypatch):
    app = create_app()
    monkeypatch.setattr(app_module, "postgres_db", FakePostgres())
    monkeypatch.setattr(app_module, "nebula_db", None)
    return TestClient(app)


def test_relationships_endpoint_falls_back_to_postgres(client):
    response = client.get("/api/characters/char-1/relationships")

    assert response.status_code == 200
    assert response.json()[0]["target_name"] == "洛澜"


def test_graph_context_endpoint_returns_envelope(client):
    response = client.get("/api/characters/char-1/graph-context")

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "postgres"
    assert data["anchor"]["id"] == "char-1"


def test_graph_context_endpoint_returns_404_for_missing_character(client):
    response = client.get("/api/characters/missing/graph-context")

    assert response.status_code == 404
