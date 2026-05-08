import pytest

from app.models.graph_context import GraphContextOptions, GraphContextSource
from app.services.graph_context_service import GraphContextService


class FakePostgres:
    def __init__(self):
        self.characters = {
            "char-1": {
                "id": "char-1",
                "name": "林砚",
                "project_id": "proj-1",
                "world_id": "world-1",
                "current_region_id": "region-1",
                "current_location_reason": "追踪潮汐裂隙",
                "key_relationships": {"char-2": "盟友"},
            },
            "char-2": {
                "id": "char-2",
                "name": "洛澜",
                "project_id": "proj-1",
                "key_relationships": {},
            },
        }
        self.worlds = {"world-1": {"id": "world-1", "name": "雾港世界", "project_id": "proj-1"}}
        self.regions = {"region-1": {"id": "region-1", "name": "雾港", "world_id": "world-1"}}
        self.hooks = [
            {
                "id": "hook-1",
                "title": "潮汐裂隙",
                "project_id": "proj-1",
                "related_characters": ["char-1"],
                "status": "planted",
            }
        ]

    async def get_character(self, character_id):
        return self.characters.get(character_id)

    async def get_all_characters(self, project_id=None, role=None, limit=100):
        values = list(self.characters.values())
        if project_id:
            values = [item for item in values if item.get("project_id") == project_id]
        return values[:limit]

    async def get_world(self, world_id):
        return self.worlds.get(world_id)

    async def get_region(self, region_id):
        return self.regions.get(region_id)

    async def get_all_hooks(self, project_id=None, status=None, limit=100):
        values = self.hooks
        if project_id:
            values = [item for item in values if item.get("project_id") == project_id]
        return values[:limit]


class FakeNebula:
    async def get_local_character_graph(self, character_id, depth=1, max_nodes=16):
        return {
            "nodes": [
                {"id": character_id, "type": "character", "name": "林砚"},
                {"id": "char-2", "type": "character", "name": "洛澜"},
            ],
            "edges": [
                {"source": character_id, "target": "char-2", "type": "knows", "label": "盟友", "properties": {"strength": 0.5}}
            ],
            "relationships": [
                {"target_id": "char-2", "target_name": "洛澜", "type": "盟友", "strength": 0.5, "source": "nebula"}
            ],
        }


@pytest.mark.asyncio
async def test_graph_context_falls_back_to_postgres_without_nebula():
    service = GraphContextService(FakePostgres(), None)

    result = await service.get_local_graph_context("character", "char-1", project_id="proj-1")

    assert result.source == GraphContextSource.POSTGRES
    assert result.anchor.name == "林砚"
    assert any(node.id == "char-2" for node in result.nodes)
    assert any(edge.type == "located_in" for edge in result.edges)
    assert any(node.type == "hook" for node in result.nodes)
    assert result.relationships[0]["target_name"] == "洛澜"


@pytest.mark.asyncio
async def test_graph_context_uses_nebula_when_available():
    service = GraphContextService(FakePostgres(), FakeNebula())

    result = await service.get_local_graph_context("character", "char-1", project_id="proj-1")

    assert result.source == GraphContextSource.NEBULA
    assert result.relationships[0]["source"] == "nebula"


@pytest.mark.asyncio
async def test_graph_context_can_force_postgres_source():
    service = GraphContextService(FakePostgres(), FakeNebula())

    result = await service.get_local_graph_context(
        "character",
        "char-1",
        project_id="proj-1",
        options=GraphContextOptions(source=GraphContextSource.POSTGRES),
    )

    assert result.source == GraphContextSource.POSTGRES
