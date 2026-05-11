import pytest
from datetime import datetime

from app.models.narrative import NarrativeStateChangeStatus
from app.services.narrative_state_change_service import NarrativeStateChangeService


PROJECT_ID = "11111111-1111-1111-1111-111111111111"


class _FakeStateChangeDB:
    def __init__(self):
        self.characters = {}
        self.hooks = {}
        self.regions = {}
        self.state_changes = {}
        self.saved_characters = []
        self.saved_hooks = []
        self.saved_regions = []

    async def get_character(self, character_id):
        character = self.characters.get(character_id)
        return dict(character) if character else None

    async def save_character(self, character_data):
        saved = dict(character_data)
        self.saved_characters.append(saved)
        if saved.get("id"):
            self.characters[saved["id"]] = saved
        return saved.get("id")

    async def get_hook(self, hook_id):
        hook = self.hooks.get(hook_id)
        return dict(hook) if hook else None

    async def save_hook(self, hook_data):
        saved = dict(hook_data)
        self.saved_hooks.append(saved)
        if saved.get("id"):
            self.hooks[saved["id"]] = saved
        return saved.get("id")

    async def get_region(self, region_id):
        region = self.regions.get(region_id)
        return dict(region) if region else None

    async def save_region(self, region_data):
        saved = dict(region_data)
        self.saved_regions.append(saved)
        if saved.get("id"):
            self.regions[saved["id"]] = saved
        return saved.get("id")

    async def save_narrative_state_change(self, change_data):
        fingerprint = change_data.get("fingerprint")
        if fingerprint:
            existing = await self.get_state_change_by_fingerprint(change_data.get("project_id"), fingerprint)
            if existing:
                return existing["id"]
        saved = dict(change_data)
        change_id = saved.get("id") or f"state-change-{len(self.state_changes) + 1}"
        saved["id"] = change_id
        self.state_changes[change_id] = saved
        return change_id

    async def get_narrative_state_change(self, change_id):
        change = self.state_changes.get(change_id)
        return dict(change) if change else None

    async def get_state_change_by_fingerprint(self, project_id, fingerprint):
        for change in self.state_changes.values():
            if change.get("project_id") == project_id and change.get("fingerprint") == fingerprint:
                return dict(change)
        return None

    async def list_narrative_state_changes(
        self,
        project_id,
        entity_type=None,
        entity_id=None,
        status=None,
        change_type=None,
        chapter_id=None,
        world_id=None,
        workflow_execution_id=None,
        limit=100,
    ):
        changes = [change for change in self.state_changes.values() if change.get("project_id") == project_id]
        if entity_type:
            changes = [change for change in changes if change.get("entity_type") == entity_type]
        if entity_id:
            changes = [change for change in changes if change.get("entity_id") == entity_id]
        if status:
            changes = [change for change in changes if change.get("status") == status]
        if change_type:
            changes = [change for change in changes if change.get("change_type") == change_type]
        if chapter_id:
            changes = [change for change in changes if change.get("chapter_id") == chapter_id]
        if world_id:
            changes = [change for change in changes if change.get("world_id") == world_id]
        if workflow_execution_id:
            changes = [change for change in changes if change.get("workflow_execution_id") == workflow_execution_id]
        return [dict(change) for change in changes[:limit]]

    async def update_narrative_state_change_status(self, change_id, status, timestamp_field=None):
        change = self.state_changes.get(change_id)
        if not change:
            return False
        change["status"] = status
        if timestamp_field:
            change[timestamp_field] = datetime.utcnow().isoformat()
        return True

    async def mark_narrative_state_change_applied(self, change_id):
        return await self.update_narrative_state_change_status(change_id, "applied", "applied_at")


@pytest.mark.asyncio
async def test_create_change_loads_before_state_and_lists_with_filters():
    db = _FakeStateChangeDB()
    db.characters["char-1"] = {
        "id": "char-1",
        "project_id": PROJECT_ID,
        "name": "林砚",
        "status": "active",
    }
    service = NarrativeStateChangeService(db)

    change = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "entity_type": "character",
            "entity_id": "char-1",
            "entity_name": "林砚",
            "change_type": "status_change",
            "title": "林砚负伤退场",
            "after_state": {"status": "inactive"},
        },
        source_context={
            "workflow_execution_id": "exec-1",
            "workflow_id": "workflow-1",
            "node_id": "node-1",
            "agent_type": "setting",
            "discussion_id": "discussion-1",
        },
    )

    assert change["id"] == "state-change-1"
    assert change["status"] == "proposed"
    assert change["before_state"]["status"] == "active"
    assert change["workflow_execution_id"] == "exec-1"
    assert change["fingerprint"]

    listed = await service.list_changes(PROJECT_ID, entity_type="character", entity_id="char-1", status="proposed")
    assert [item["id"] for item in listed] == [change["id"]]


@pytest.mark.asyncio
async def test_list_changes_validates_filters_and_supports_owner_scope_filters():
    db = _FakeStateChangeDB()
    service = NarrativeStateChangeService(db)
    first = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "world_id": "22222222-2222-2222-2222-222222222222",
            "entity_type": "plot",
            "change_type": "custom",
            "title": "第一章状态",
            "chapter_id": "33333333-3333-3333-3333-333333333333",
            "workflow_execution_id": "exec-owner-1",
        }
    )
    await service.create_change(
        {
            "project_id": PROJECT_ID,
            "world_id": "44444444-4444-4444-4444-444444444444",
            "entity_type": "world",
            "change_type": "world_state_change",
            "title": "第二章状态",
            "chapter_id": "55555555-5555-5555-5555-555555555555",
            "workflow_execution_id": "exec-owner-2",
        }
    )

    chapter_filtered = await service.list_changes(PROJECT_ID, chapter_id="33333333-3333-3333-3333-333333333333")
    world_filtered = await service.list_changes(PROJECT_ID, world_id="22222222-2222-2222-2222-222222222222")
    execution_filtered = await service.list_changes(PROJECT_ID, workflow_execution_id="exec-owner-1")

    assert [item["id"] for item in chapter_filtered] == [first["id"]]
    assert [item["id"] for item in world_filtered] == [first["id"]]
    assert [item["id"] for item in execution_filtered] == [first["id"]]
    with pytest.raises(ValueError, match="无效的剧情状态变更状态"):
        await service.list_changes(PROJECT_ID, status="unknown")
    with pytest.raises(ValueError, match="无效的剧情状态变更实体类型"):
        await service.list_changes(PROJECT_ID, entity_type="artifact")
    with pytest.raises(ValueError, match="无效的剧情状态变更变更类型"):
        await service.list_changes(PROJECT_ID, change_type="teleport")


@pytest.mark.asyncio
async def test_create_change_is_idempotent_by_generated_fingerprint():
    db = _FakeStateChangeDB()
    service = NarrativeStateChangeService(db)
    payload = {
        "project_id": PROJECT_ID,
        "entity_type": "world",
        "entity_name": "潮汐门",
        "change_type": "world_state_change",
        "title": "潮汐门开启",
        "summary": "世界规则开始受潮汐门影响",
        "after_state": {"gate_open": True},
    }
    source_context = {"workflow_execution_id": "exec-1", "node_id": "node-1", "discussion_id": "discussion-1"}

    first = await service.create_change(payload, source_context=source_context)
    second = await service.create_change(payload, source_context=source_context)

    assert first["id"] == second["id"]
    assert len(db.state_changes) == 1


@pytest.mark.asyncio
async def test_proposed_change_requires_confirmation_and_does_not_project():
    db = _FakeStateChangeDB()
    db.characters["char-1"] = {"id": "char-1", "project_id": PROJECT_ID, "name": "林砚", "status": "active"}
    service = NarrativeStateChangeService(db)
    change = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "entity_type": "character",
            "entity_id": "char-1",
            "change_type": "status_change",
            "title": "林砚退场",
            "after_state": {"status": "inactive"},
        }
    )

    with pytest.raises(ValueError, match="尚未确认"):
        await service.apply_change(change["id"])

    assert db.characters["char-1"]["status"] == "active"
    assert db.state_changes[change["id"]]["status"] == NarrativeStateChangeStatus.PROPOSED.value


@pytest.mark.asyncio
async def test_rejected_change_cannot_confirm_or_apply():
    db = _FakeStateChangeDB()
    service = NarrativeStateChangeService(db)
    change = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "entity_type": "plot",
            "change_type": "custom",
            "title": "待拒绝状态",
        }
    )

    rejected = await service.reject_change(change["id"])

    assert rejected["status"] == NarrativeStateChangeStatus.REJECTED.value
    with pytest.raises(ValueError, match="不能确认"):
        await service.confirm_change(change["id"])
    with pytest.raises(ValueError, match="不能应用"):
        await service.apply_change(change["id"])


@pytest.mark.asyncio
async def test_already_applied_change_apply_is_idempotent():
    db = _FakeStateChangeDB()
    service = NarrativeStateChangeService(db)
    change = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "entity_type": "custom",
            "change_type": "custom",
            "title": "审计状态",
            "after_state": {"canon": True},
        }
    )

    await service.confirm_change(change["id"])
    first = await service.apply_change(change["id"])
    second = await service.apply_change(change["id"])

    assert first["applied"] is True
    assert second["success"] is True
    assert second["applied"] is False
    assert second["message"] == "剧情状态变更已应用"


@pytest.mark.asyncio
async def test_confirmed_change_can_be_rejected_before_apply():
    db = _FakeStateChangeDB()
    service = NarrativeStateChangeService(db)
    change = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "entity_type": "world",
            "change_type": "world_state_change",
            "title": "待确认世界状态",
        }
    )

    await service.confirm_change(change["id"])
    rejected = await service.reject_change(change["id"])

    assert rejected["status"] == NarrativeStateChangeStatus.REJECTED.value
    with pytest.raises(ValueError, match="不能应用"):
        await service.apply_change(change["id"])


@pytest.mark.asyncio
async def test_confirm_and_apply_character_death_updates_current_projection():
    db = _FakeStateChangeDB()
    db.characters["char-death"] = {
        "id": "char-death",
        "project_id": PROJECT_ID,
        "name": "林砚",
        "status": "active",
        "description": "观测员",
    }
    service = NarrativeStateChangeService(db)
    change = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "entity_type": "character",
            "entity_id": "char-death",
            "entity_name": "林砚",
            "change_type": "death",
            "title": "林砚牺牲",
            "summary": "林砚为关闭潮汐门而死亡",
            "reason": "以自身灵力封闭潮汐门",
            "after_state": {"status": "dead"},
            "metadata": {"witnesses": ["洛澜"]},
        }
    )

    confirmed = await service.confirm_change(change["id"])
    result = await service.apply_change(confirmed["id"])

    assert result["success"] is True
    assert result["projection"]["projection"] == "character"
    assert db.characters["char-death"]["status"] == "dead"
    assert db.characters["char-death"]["death_detail"]["cause"] == "以自身灵力封闭潮汐门"
    assert db.characters["char-death"]["death_detail"]["witnesses"] == ["洛澜"]
    assert db.characters["char-death"]["exit_reason"] == "以自身灵力封闭潮汐门"
    assert db.state_changes[change["id"]]["status"] == "applied"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change_type", "expected_status"),
    [
        ("hook_triggered", "triggered"),
        ("hook_resolved", "resolved"),
        ("hook_dropped", "dropped"),
    ],
)
async def test_confirm_and_apply_hook_lifecycle_updates_status(change_type, expected_status):
    db = _FakeStateChangeDB()
    db.hooks["hook-1"] = {
        "id": "hook-1",
        "project_id": PROJECT_ID,
        "title": "潮汐门钥匙",
        "status": "planted",
    }
    service = NarrativeStateChangeService(db)
    change = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "entity_type": "hook",
            "entity_id": "hook-1",
            "change_type": change_type,
            "title": "潮汐门钥匙状态变化",
            "after_state": {"resolution_context": "主角在旧码头揭开真相"},
        }
    )

    await service.confirm_change(change["id"])
    result = await service.apply_change(change["id"])

    assert result["projection"]["projection"] == "hook"
    assert db.hooks["hook-1"]["status"] == expected_status
    assert db.hooks["hook-1"]["resolution_context"] == "主角在旧码头揭开真相"
    if expected_status == "resolved":
        assert db.hooks["hook-1"]["resolved_at"]


@pytest.mark.asyncio
async def test_confirm_and_apply_region_destroyed_updates_region_projection():
    db = _FakeStateChangeDB()
    db.regions["region-1"] = {
        "id": "region-1",
        "world_id": "world-1",
        "name": "旧码头",
        "state": "normal",
    }
    service = NarrativeStateChangeService(db)
    change = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "entity_type": "region",
            "entity_id": "region-1",
            "entity_name": "旧码头",
            "change_type": "region_destroyed",
            "title": "旧码头沉没",
            "summary": "旧码头在潮汐门崩塌后沉入海底",
            "after_state": {"state": "destroyed"},
        }
    )

    await service.confirm_change(change["id"])
    result = await service.apply_change(change["id"])

    assert result["projection"] == {"projection": "region", "entity_id": "region-1", "state": "destroyed"}
    assert db.regions["region-1"]["state"] == "destroyed"
    assert db.regions["region-1"]["state_summary"] == "旧码头在潮汐门崩塌后沉入海底"
    assert db.regions["region-1"]["destroyed_at"]


@pytest.mark.asyncio
async def test_confirm_and_apply_region_state_change_merges_after_state():
    db = _FakeStateChangeDB()
    db.regions["region-1"] = {
        "id": "region-1",
        "world_id": "world-1",
        "name": "旧码头",
        "state": "normal",
    }
    service = NarrativeStateChangeService(db)
    change = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "entity_type": "region",
            "entity_id": "region-1",
            "change_type": "region_state_change",
            "title": "旧码头封锁",
            "after_state": {"state": "sealed", "state_summary": "被守夜人临时封锁"},
        }
    )

    await service.confirm_change(change["id"])
    await service.apply_change(change["id"])

    assert db.regions["region-1"]["state"] == "sealed"
    assert db.regions["region-1"]["state_summary"] == "被守夜人临时封锁"


@pytest.mark.asyncio
async def test_apply_missing_entity_keeps_change_unapplied():
    db = _FakeStateChangeDB()
    service = NarrativeStateChangeService(db)
    change = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "entity_type": "character",
            "entity_id": "missing-character",
            "change_type": "death",
            "title": "不存在角色死亡",
            "after_state": {"status": "dead"},
        }
    )
    await service.confirm_change(change["id"])

    with pytest.raises(ValueError, match="角色不存在"):
        await service.apply_change(change["id"])

    assert db.state_changes[change["id"]]["status"] == "confirmed"
    assert db.saved_characters == []


@pytest.mark.asyncio
async def test_confirm_and_apply_custom_change_is_log_only():
    db = _FakeStateChangeDB()
    service = NarrativeStateChangeService(db)
    change = await service.create_change(
        {
            "project_id": PROJECT_ID,
            "entity_type": "custom",
            "change_type": "custom",
            "title": "叙事规则变化",
            "after_state": {"rule": "夜晚无法使用潮汐术"},
        }
    )

    await service.confirm_change(change["id"])
    result = await service.apply_change(change["id"])

    assert result["projection"] == {"projection": "log_only"}
    assert db.state_changes[change["id"]]["status"] == "applied"
    assert db.saved_characters == []
    assert db.saved_hooks == []
    assert db.saved_regions == []
