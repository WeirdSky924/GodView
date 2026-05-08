import pytest
from fastapi import HTTPException

from app.api.routes.worlds import delete_region, get_region, list_regions, update_region
from app.models.world import Region, RegionType, TerrainType


class _FakePostgresDB:
    def __init__(self):
        self.regions = {
            "region-1": {
                "id": "region-1",
                "world_id": "world-1",
                "name": "旧区域",
                "region_type": "city",
                "terrain_type": "plain",
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
