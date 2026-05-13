import pytest
from fastapi import HTTPException

from app.models.world import Region
from app.api.routes.worlds import (
    WorldMapAgentGenerateRequest,
    _normalize_agent_draft_regions,
    delete_region,
    generate_world_map_drafts,
    get_region,
    list_regions,
    update_region,
)
from app.agents.base import AgentResponse
from app.models.world import Region, RegionType, TerrainType


class _FakePostgresDB:
    def __init__(self):
        self.worlds = {
            "world-1": {
                "id": "world-1",
                "project_id": "project-1",
                "name": "主世界",
                "description": "近未来都市",
            },
            "world-2": {
                "id": "world-2",
                "project_id": "project-2",
                "name": "其它世界",
            },
        }
        self.regions = {
            "region-1": {
                "id": "region-1",
                "world_id": "world-1",
                "name": "旧区域",
                "region_type": "city",
                "terrain_type": "plain",
                "description": "中央车站",
                "created_at": "created",
            },
            "region-2": {
                "id": "region-2",
                "world_id": "world-2",
                "name": "其它世界区域",
                "region_type": "forest",
                "terrain_type": "hill",
            },
        }
        self.saved_regions = []
        self.deleted_region_ids = []
        self.memory_loaded_by = []

    async def get_world(self, world_id):
        return self.worlds.get(world_id)

    async def get_region(self, region_id):
        return self.regions.get(region_id)

    async def get_regions_by_world(self, world_id):
        return [region for region in self.regions.values() if region.get("world_id") == world_id]

    async def save_region(self, region_data):
        self.saved_regions.append(dict(region_data))
        self.regions[region_data["id"]] = dict(region_data)
        return region_data["id"]

    async def delete_region(self, region_id):
        self.deleted_region_ids.append(region_id)
        return self.regions.pop(region_id, None) is not None

    async def get_agent_memories(self, agent_id, limit=10):
        self.memory_loaded_by.append((agent_id, limit))
        return []


@pytest.fixture
def fake_postgres(monkeypatch):
    db = _FakePostgresDB()
    import app.api.app as api_app

    monkeypatch.setattr(api_app, "postgres_db", db)
    return db


@pytest.mark.asyncio
async def test_list_regions_uses_world_filter(fake_postgres):
    regions = await list_regions("world-1")

    assert len(regions) == 1
    assert regions[0]["id"] == "region-1"


@pytest.mark.asyncio
async def test_get_region_validates_world_ownership(fake_postgres):
    region = await get_region("world-1", "region-1")

    assert region["id"] == "region-1"

    with pytest.raises(HTTPException) as exc_info:
        await get_region("world-1", "region-2")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_region_preserves_id_world_and_created_at(fake_postgres):
    updated = Region(
        id="client-id-ignored",
        name="新区域",
        world_id="client-world-ignored",
        region_type=RegionType.VILLAGE,
        terrain_type=TerrainType.MOUNTAIN,
        description="新描述",
        coordinates={"x": 10, "y": 20},
        connections=["region-3"],
    )

    result = await update_region("world-1", "region-1", updated)

    assert result["success"] is True
    saved = fake_postgres.saved_regions[-1]
    assert saved["id"] == "region-1"
    assert saved["world_id"] == "world-1"
    assert saved["created_at"] == "created"
    assert saved["name"] == "新区域"
    assert saved["connections"] == ["region-3"]


@pytest.mark.asyncio
async def test_delete_region_validates_world_ownership(fake_postgres):
    result = await delete_region("world-1", "region-1")

    assert result["success"] is True
    assert fake_postgres.deleted_region_ids == ["region-1"]

    with pytest.raises(HTTPException) as exc_info:
        await delete_region("world-1", "region-2")
    assert exc_info.value.status_code == 404
    assert fake_postgres.deleted_region_ids == ["region-1"]


def test_normalize_agent_draft_regions_resolves_safe_connections_and_warnings():
    normalized = _normalize_agent_draft_regions(
        {
            "overview": "勘测摘要",
            "suggested_starting_location": "旧区域",
            "regions": [
                {
                    "region_name": "雨棚夹层",
                    "region_type": "invalid-kind",
                    "terrain_type": "invalid-terrain",
                    "description": "车站上方的临时藏身点",
                    "atmosphere": "雨声密集",
                    "coordinates": {"x": 12, "y": 4, "z": 99},
                    "terrain_features": ["锈蚀雨棚"],
                    "landmarks": [{"name": "旧信号灯"}],
                    "encounters": ["巡逻无人机"],
                    "suggested_connections": ["region-1", "旧区域", "不存在的区域"],
                    "local_rules": ["夜间有监控盲区"],
                    "importance": "承接追踪戏",
                }
            ],
        },
        [
            {"id": "region-1", "name": "旧区域"},
            {"id": "region-2", "name": "其它区域"},
        ],
        generation_count=3,
    )

    assert normalized["overview"] == "勘测摘要"
    assert normalized["suggested_starting_location"] == "旧区域"
    draft = normalized["draft_regions"][0]
    assert draft["name"] == "雨棚夹层"
    assert draft["region_type"] == "custom"
    assert draft["terrain_type"] == "custom"
    assert draft["coordinates"] == {"x": 12.0, "y": 4.0}
    assert draft["terrain_features"] == [{"name": "锈蚀雨棚"}]
    assert draft["landmarks"] == [{"name": "旧信号灯"}]
    assert draft["encounters"] == [{"name": "巡逻无人机"}]
    assert draft["connections"] == ["region-1"]
    assert any("未知区域类型" in warning for warning in draft["validation_warnings"])
    assert any("未知地形类型" in warning for warning in draft["validation_warnings"])
    assert any("不存在的区域" in warning for warning in draft["validation_warnings"])


def test_region_accepts_agent_draft_encounters_without_id_or_type():
    region = Region(
        name="下城区集市",
        region_type="village",
        terrain_type="plain",
        encounters=[
            {
                "name": "阿Ken的通讯",
                "description": "触发条件：林默在此休息或交易；事件：阿Ken通过加密频道联系林默",
            },
            {"name": "失踪人口传闻", "type": "unknown-kind"},
        ],
    )

    dumped = region.model_dump(mode="json")
    assert len(dumped["encounters"]) == 2
    assert dumped["encounters"][0]["id"]
    assert dumped["encounters"][0]["type"] == "event"
    assert dumped["encounters"][1]["type"] == "event"


@pytest.mark.asyncio
async def test_generate_world_map_drafts_uses_page_scenario_without_saving(monkeypatch, fake_postgres):
    captured = {}

    class FakeWorldMapManagerAgent:
        def __init__(self, model=None, project_id=None, agent_id=None, scenario=None):
            captured["model"] = model
            captured["project_id"] = project_id
            captured["agent_id"] = agent_id
            captured["scenario"] = scenario

        async def load_memory(self, db):
            captured["memory_db"] = db

        async def execute(self, payload):
            captured["payload"] = payload
            return AgentResponse(
                success=True,
                data={
                    "overview": "生成 1 个草稿",
                    "regions": [
                        {
                            "region_name": "雨棚夹层",
                            "region_type": "building",
                            "terrain_type": "plain",
                            "description": "适合伏击的站台上层空间",
                            "suggested_connections": ["旧区域"],
                            "importance": "承接追踪戏",
                        }
                    ],
                },
                metadata={"prompt_render_trace": {"template_id": "world_map_manager_draft"}},
            )

    monkeypatch.setattr("app.agents.world_map_manager.WorldMapManagerAgent", FakeWorldMapManagerAgent)
    monkeypatch.setattr("app.services.model_router.create_model_factory", lambda **kwargs: lambda: "fake-model")

    result = await generate_world_map_drafts(
        "world-1",
        WorldMapAgentGenerateRequest(
            project_id="project-1",
            world_id="world-1",
            message="围绕旧区域补一个追踪地点",
            generation_count=1,
            selected_region_id="region-1",
        ),
    )

    assert result["success"] is True
    assert result["draft_regions"][0]["name"] == "雨棚夹层"
    assert result["draft_regions"][0]["connections"] == ["region-1"]
    assert result["metadata"]["scenario"] == "world_map_draft_generation"
    assert result["metadata"]["template_id"] == "world_map_manager_draft"
    assert captured["model"] == "fake-model"
    assert captured["project_id"] == "project-1"
    assert captured["agent_id"] == "world_map_manager_page"
    assert captured["scenario"] == "world_map_draft_generation"
    assert captured["payload"]["task"] == "create_draft"
    assert captured["payload"]["world_info"]["selected_region"]["id"] == "region-1"
    assert captured["payload"]["existing_regions"][0]["id"] == "region-1"
    assert fake_postgres.saved_regions == []


@pytest.mark.asyncio
async def test_generate_world_map_drafts_rejects_project_and_selected_region_mismatch(fake_postgres):
    with pytest.raises(HTTPException) as project_exc:
        await generate_world_map_drafts(
            "world-1",
            WorldMapAgentGenerateRequest(
                project_id="project-2",
                world_id="world-1",
                message="生成地点",
            ),
        )
    assert project_exc.value.status_code == 400

    with pytest.raises(HTTPException) as region_exc:
        await generate_world_map_drafts(
            "world-1",
            WorldMapAgentGenerateRequest(
                project_id="project-1",
                world_id="world-1",
                message="生成地点",
                selected_region_id="region-2",
            ),
        )
    assert region_exc.value.status_code == 404


def test_world_map_draft_template_uses_dedicated_prompt_asset():
    from app.data.system_agent_templates import WORLD_MAP_MANAGER_DRAFT

    assert WORLD_MAP_MANAGER_DRAFT.scenario == "world_map_draft_generation"
    assert WORLD_MAP_MANAGER_DRAFT.id == "world_map_manager_draft"
    prompt_slots = {slot.slot_name: slot for slot in WORLD_MAP_MANAGER_DRAFT.prompt_slots}
    assert prompt_slots["map_draft_request"].prompt_template_id == "function_map_draft_generation"
    assert "map_draft_request" in WORLD_MAP_MANAGER_DRAFT.default_prompt_order
