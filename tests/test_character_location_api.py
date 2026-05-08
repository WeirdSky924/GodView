import pytest
from fastapi import HTTPException

from app.api.routes.characters import create_character, update_character
from app.models.character import Character, CharacterImportanceTier


class _FakePostgresDB:
    def __init__(self):
        self.regions = {
            "region-1": {"id": "region-1", "world_id": "world-1", "name": "旧码头"},
            "region-2": {"id": "region-2", "world_id": "world-2", "name": "北境森林"},
        }
        self.characters = {
            "char-1": {
                "id": "char-1",
                "name": "旧角色",
                "world_id": "world-1",
                "created_at": "created",
                "has_agent": False,
                "agent_enabled": True,
            }
        }
        self.saved_characters = []

    async def get_region(self, region_id):
        return self.regions.get(region_id)

    async def get_character(self, character_id):
        return self.characters.get(character_id)

    async def get_all_characters(self, *args, **kwargs):
        return []

    async def save_character(self, character_data):
        saved = dict(character_data)
        self.saved_characters.append(saved)
        self.characters[saved["id"]] = saved
        return saved["id"]


@pytest.fixture
def fake_postgres(monkeypatch):
    db = _FakePostgresDB()
    import app.api.app as api_app

    monkeypatch.setattr(api_app, "postgres_db", db)
    monkeypatch.setattr(api_app, "nebula_db", None)
    return db


@pytest.mark.asyncio
async def test_create_character_saves_region_and_arrival_reason(fake_postgres):
    character = Character(
        name="洛澜",
        description="熟悉旧码头的引路人",
        importance_tier=CharacterImportanceTier.NPC,
        world_id="world-1",
        current_region_id="region-1",
        current_location="旧码头",
        current_location_reason="追踪潮汐门钥匙线索来到这里",
    )

    result = await create_character(character)

    assert result["success"] is True
    saved = fake_postgres.saved_characters[-1]
    assert saved["world_id"] == "world-1"
    assert saved["current_region_id"] == "region-1"
    assert saved["current_location"] == "旧码头"
    assert saved["current_location_reason"] == "追踪潮汐门钥匙线索来到这里"


@pytest.mark.asyncio
async def test_create_character_infers_world_from_region(fake_postgres):
    character = Character(
        name="无世界角色",
        description="只选择了当前区域",
        importance_tier=CharacterImportanceTier.NPC,
        current_region_id="region-1",
        current_location_reason="躲避追兵进入旧码头",
    )

    await create_character(character)

    saved = fake_postgres.saved_characters[-1]
    assert saved["world_id"] == "world-1"
    assert saved["current_region_id"] == "region-1"
    assert saved["current_location_reason"] == "躲避追兵进入旧码头"


@pytest.mark.asyncio
async def test_create_character_rejects_region_from_other_world(fake_postgres):
    character = Character(
        name="跨世界角色",
        description="错误关联到其它世界区域",
        importance_tier=CharacterImportanceTier.NPC,
        world_id="world-1",
        current_region_id="region-2",
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_character(character)

    assert exc_info.value.status_code == 400
    assert fake_postgres.saved_characters == []


@pytest.mark.asyncio
async def test_update_character_saves_region_and_arrival_reason(fake_postgres):
    character = Character(
        name="旧角色",
        description="更新当前位置",
        importance_tier=CharacterImportanceTier.NPC,
        world_id="world-1",
        current_region_id="region-1",
        current_location="旧码头",
        current_location_reason="为了履行与主角的约定返回码头",
    )

    result = await update_character("char-1", character)

    assert result["success"] is True
    saved = fake_postgres.saved_characters[-1]
    assert saved["id"] == "char-1"
    assert saved["created_at"] == "created"
    assert saved["current_region_id"] == "region-1"
    assert saved["current_location_reason"] == "为了履行与主角的约定返回码头"


@pytest.mark.asyncio
async def test_create_character_without_location_fields_still_saves(fake_postgres):
    character = Character(
        name="旧格式角色",
        description="旧 payload 不携带地图位置字段",
        importance_tier=CharacterImportanceTier.NPC,
    )

    result = await create_character(character)

    assert result["success"] is True
    saved = fake_postgres.saved_characters[-1]
    assert saved["name"] == "旧格式角色"
    assert saved["current_region_id"] is None
    assert saved["current_location_reason"] is None
