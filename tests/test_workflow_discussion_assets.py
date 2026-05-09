import pytest

from app.models.workflow_definition import NodeType, WorkflowNode
from app.models.workflow_execution import WorkflowExecution, WorkflowStatus
from app.services.workflow_engine import WorkflowEngine

from tests.workflow_test_fakes import FakeDiscussionDB


class TestDiscussionAssets:
    """讨论资产归一化、确认边界与持久化测试。"""

    def setup_method(self):
        self.engine = WorkflowEngine()

    def test_build_discussion_asset_bundle_classifies_regions_and_lore(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            context={"chapter_title": "第一章"},
            node_states={},
        )
        discussion_result = {
            "summary": "众人决定让旧码头成为后续追踪线索的关键地点。",
            "topic": "码头追踪线",
            "hooks": [{"title": "潮汐钟失准", "description": "钟声会暴露隐藏入口"}],
            "map_candidates": [
                {
                    "name": "旧码头",
                    "description": "被废弃的港口区域",
                    "terrain_features": ["雾", "潮汐栈桥"],
                    "connections": ["下城区"],
                },
                {
                    "name": "潮汐禁忌",
                    "history": "旧码头居民相信午夜潮声不可回应。",
                    "category": "culture",
                },
                {
                    "name": "沉钟灯塔",
                    "description": "灯塔本体可进入，内部保存失落钟声的传说。",
                    "landmarks": ["裂钟"],
                    "history": "曾是守夜人的誓约之地。",
                },
            ],
            "character_candidates": [{"name": "洛澜", "importance_tier": "major_ally", "description": "码头引路人"}],
            "state_changes": [
                {
                    "entity_type": "region",
                    "entity_id": "region-1",
                    "change_type": "region_destroyed",
                    "title": "旧码头被毁",
                    "summary": "旧码头在潮汐门崩塌后沉入海底",
                    "after_state": {"state": "destroyed"},
                }
            ],
        }

        bundle = self.engine._build_discussion_asset_bundle(
            execution,
            discussion_result,
            node_id="discussion",
            discussion_mode="meeting",
        )

        assert bundle["source_metadata"]["topic"] == "码头追踪线"
        assert bundle["persistence_preview"]["plot_update_count"] == 1
        assert bundle["persistence_preview"]["hook_count"] == 1
        assert [r["name"] for r in bundle["region_candidates"]] == ["旧码头", "沉钟灯塔"]
        lore_titles = [l["title"] for l in bundle["lore_candidates"]]
        assert "潮汐禁忌" in lore_titles
        assert "沉钟灯塔" in lore_titles
        dual_lore = next(l for l in bundle["lore_candidates"] if l["title"] == "沉钟灯塔")
        assert dual_lore["metadata"]["dual_write_region_name"] == "沉钟灯塔"
        assert bundle["persistence_preview"]["region_count"] == 2
        assert bundle["persistence_preview"]["lore_count"] == 2
        assert bundle["persistence_preview"]["state_change_count"] == 1
        assert bundle["persistence_preview"]["state_change_titles"] == ["旧码头被毁"]

    def test_extract_discussion_assets_from_fenced_json_text(self):
        discussion_result = {
            "summary": """
本次讨论决定强化旧码头线索。

```json
{
  "discussion_assets": {
    "plot_updates": [{"title": "旧码头追踪", "summary": "主角将追查潮汐门"}],
    "hooks": [{"title": "潮汐钟失准", "description": "钟声会暴露隐藏入口", "related_locations": ["旧码头"]}],
    "lore_candidates": [{"title": "潮汐禁忌", "content": "午夜潮声不可回应", "category": "culture"}],
    "region_candidates": [{"name": "旧码头", "description": "废弃港口", "landmarks": ["潮汐钟"]}],
    "character_candidates": [{"name": "洛澜", "importance_tier": "major_ally", "description": "码头引路人", "appearance": "灰蓝斗篷"}],
    "state_changes": [{
      "entity_type": "character",
      "entity_id": "char-1",
      "change_type": "death",
      "title": "林砚牺牲",
      "summary": "林砚为关闭潮汐门而死亡",
      "after_state": {"status": "dead"}
    }]
  }
}
```

请确认是否同意。
""",
            "messages": [],
        }

        extracted = self.engine._extract_discussion_assets_from_text(discussion_result)

        assert extracted["plot_updates"][0]["title"] == "旧码头追踪"
        assert extracted["hooks"][0]["title"] == "潮汐钟失准"
        assert extracted["lore_candidates"][0]["title"] == "潮汐禁忌"
        assert extracted["region_candidates"][0]["name"] == "旧码头"
        assert extracted["character_candidates"][0]["name"] == "洛澜"
        assert extracted["state_changes"][0]["title"] == "林砚牺牲"
        assert extracted["state_changes"][0]["change_type"] == "death"

    def test_apply_discussion_asset_bundle_keeps_legacy_context_fields(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            context={"chapter_title": "第一章"},
            node_states={},
        )
        discussion_result = {"summary": "确认新角色会在下一章登场", "topic": "角色登场"}
        bundle = self.engine._build_discussion_asset_bundle(execution, discussion_result, "discussion", "meeting")

        digest = self.engine._apply_discussion_asset_bundle(execution, discussion_result, bundle, "meeting")

        assert execution.context["discussion_assets"] == bundle
        assert execution.context["discussion_asset_digest"] == digest
        assert execution.context["discussion_assets_committed"] is False
        assert execution.context["discussion_summary"] == "确认新角色会在下一章登场"
        assert execution.context["last_discussion_summary"] == "确认新角色会在下一章登场"
        assert execution.context["group_discussion"]["discussion_assets"] == bundle
        assert discussion_result["discussion_asset_digest"] == digest

    @pytest.mark.asyncio
    async def test_execute_group_discussion_waits_for_confirmation_before_persistence(self):
        node = WorkflowNode(
            id="discussion",
            node_type=NodeType.GROUP_DISCUSSION,
            label="讨论",
            config={"require_user_confirmation": True, "confirmation_timeout": 999},
            position={"x": 0, "y": 0},
        )
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            node_states={},
        )
        db = FakeDiscussionDB()

        async def _fake_discussion(*args, **kwargs):
            return {
                "status": "completed",
                "summary": "确认旧码头伏笔",
                "hooks": [{"title": "旧码头钥匙", "description": "钥匙会打开潮汐门"}],
            }

        async def _fake_broadcast(*args, **kwargs):
            return None

        self.engine._execute_meeting_discussion = _fake_discussion
        self.engine._broadcast_status = _fake_broadcast

        result = await self.engine._execute_group_discussion_node(node, execution, db=db)

        assert result["waiting_user_confirmation"] is True
        assert execution.status == WorkflowStatus.PAUSED
        assert execution.context["discussion_assets_committed"] is False
        assert execution.context["waiting_confirmation"]["discussion_assets"]["hooks"][0]["title"] == "旧码头钥匙"
        assert db.hooks == []
        assert db.lores == []
        assert db.regions == []
        assert db.characters == []

    @pytest.mark.asyncio
    async def test_persist_discussion_assets_saves_confirmed_assets_and_context_refs(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={"world_id": "22222222-2222-2222-2222-222222222222", "chapter_title": "第一章"},
            node_states={},
        )
        db = FakeDiscussionDB()

        async def _fake_broadcast(*args, **kwargs):
            return None

        self.engine._broadcast_status = _fake_broadcast
        bundle = {
            "plot_updates": [{"summary": "新增码头追踪线"}],
            "hooks": [{"title": "旧码头钥匙", "description": "钥匙会打开潮汐门", "related_locations": ["旧码头"]}],
            "lore_candidates": [{"title": "潮汐禁忌", "content": "午夜潮声不可回应", "category": "culture"}],
            "region_candidates": [{"name": "旧码头", "description": "废弃港口", "terrain_features": ["浓雾"]}],
            "character_candidates": [
                {
                    "name": "洛澜",
                    "importance_tier": "major_ally",
                    "description": "熟悉旧码头的引路人",
                    "current_location": "旧码头",
                    "current_region_id": "region-1",
                    "arrival_reason": "受主角委托提前探查潮汐门",
                    "goals": ["帮助主角进入旧码头"],
                },
                {"name": "一个神秘商人", "description": "只被短暂提及"},
            ],
            "state_changes": [
                {
                    "entity_type": "character",
                    "entity_id": "char-death",
                    "entity_name": "林砚",
                    "change_type": "death",
                    "title": "林砚牺牲",
                    "summary": "林砚为关闭潮汐门而死亡",
                    "reason": "以自身灵力封闭潮汐门",
                    "after_state": {"status": "dead"},
                }
            ],
            "source_metadata": {"node_id": "discussion"},
        }
        db.existing_characters["char-death"] = {
            "id": "char-death",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "林砚",
            "status": "active",
            "description": "观测员",
        }

        state = await self.engine._persist_discussion_assets(execution, bundle, db=db, confirmation_mode="user_confirm")

        assert state["committed"] is True
        assert state["confirmation_mode"] == "user_confirm"
        assert len(db.hooks) == 1
        assert db.hooks[0]["related_locations"] == ["旧码头"]
        assert len(db.lores) == 1
        assert db.lores[0]["title"] == "潮汐禁忌"
        assert len(db.regions) == 1
        assert db.regions[0]["name"] == "旧码头"
        assert db.regions[0]["world_id"] == "22222222-2222-2222-2222-222222222222"
        assert len(db.characters) == 2
        assert db.characters[0]["name"] == "洛澜"
        assert db.characters[0]["role"] == "supporting"
        assert db.characters[0]["current_location"] == "旧码头"
        assert db.characters[0]["current_region_id"] == "region-1"
        assert db.characters[0]["current_location_reason"] == "受主角委托提前探查潮汐门"
        assert db.characters[0]["personality_traits"] == []
        assert db.existing_characters["char-death"]["status"] == "dead"
        assert db.existing_characters["char-death"]["death_detail"]["cause"] == "以自身灵力封闭潮汐门"
        assert state["characters"]["skipped"] == [{"name": "一个神秘商人", "reason": "角色信息不够明确，暂不提前落库"}]
        assert state["state_changes"]["created"][0]["title"] == "林砚牺牲"
        assert state["state_changes"]["applied"][0]["projection"]["projection"] == "character"
        assert execution.context["discussion_assets_committed"] is True
        assert execution.context["discussion_persistence_state"] == state
        assert execution.context["discussion_created_characters"] == state["characters"]["created"]
        assert execution.context["discussion_state_changes"] == state["state_changes"]["created"]
        assert execution.context["discussion_applied_state_changes"] == state["state_changes"]["applied"]
        assert state["persisted_asset_refs"]["hooks"]
        assert state["persisted_asset_refs"]["lores"]
        assert state["persisted_asset_refs"]["regions"]
        assert state["persisted_asset_refs"]["characters"]
        assert state["persisted_asset_refs"]["state_changes"] == ["state-change-1"]
        assert state["persisted_asset_refs"]["applied_state_changes"] == ["state-change-1"]

    @pytest.mark.asyncio
    async def test_persist_discussion_character_location_updates_existing_character_by_id(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={},
            node_states={},
        )
        db = FakeDiscussionDB()
        db.existing_characters["char-1"] = {
            "id": "char-1",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "林砚",
            "world_id": "world-1",
            "current_location": "旧地点",
            "current_region_id": "region-old",
            "current_location_reason": "旧原因",
            "description": "观测员",
        }
        db.regions_by_id["region-1"] = {"id": "region-1", "world_id": "world-1", "name": "雾港观测塔"}

        state = await self.engine._persist_discussion_assets(
            execution,
            {
                "character_location_updates": [
                    {
                        "character_id": "char-1",
                        "current_region_id": "region-1",
                        "arrival_reason": "追查裂钟钥匙线索而返回观测塔",
                    }
                ],
            },
            db=db,
            confirmation_mode="user_confirm",
        )

        assert state["character_location_updates"]["updated"] == [
            {
                "id": "char-1",
                "name": "林砚",
                "current_region_id": "region-1",
                "current_location": "雾港观测塔",
                "current_location_reason": "追查裂钟钥匙线索而返回观测塔",
            }
        ]
        saved = db.existing_characters["char-1"]
        assert saved["description"] == "观测员"
        assert saved["current_region_id"] == "region-1"
        assert saved["current_location"] == "雾港观测塔"
        assert saved["current_location_reason"] == "追查裂钟钥匙线索而返回观测塔"
        assert execution.context["discussion_character_location_updates"] == state["character_location_updates"]["updated"]
        assert state["persisted_asset_refs"]["character_location_updates"] == ["char-1"]

    @pytest.mark.asyncio
    async def test_persist_discussion_character_location_updates_matches_by_name_and_infers_world(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={},
            node_states={},
        )
        db = FakeDiscussionDB()
        db.existing_characters["char-2"] = {
            "id": "char-2",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "洛澜",
            "world_id": None,
            "current_location": None,
            "current_region_id": None,
            "current_location_reason": "",
        }
        db.regions_by_id["region-2"] = {"id": "region-2", "world_id": "world-2", "name": "旧码头"}

        state = await self.engine._persist_discussion_assets(
            execution,
            {
                "character_location_updates": [
                    {
                        "character_name": "洛澜",
                        "region_id": "region-2",
                        "movement_reason": "躲避追兵进入旧码头",
                    }
                ],
            },
            db=db,
            confirmation_mode="user_confirm",
        )

        saved = db.existing_characters["char-2"]
        assert state["character_location_updates"]["updated"][0]["id"] == "char-2"
        assert saved["world_id"] == "world-2"
        assert saved["current_region_id"] == "region-2"
        assert saved["current_location"] == "旧码头"
        assert saved["current_location_reason"] == "躲避追兵进入旧码头"

    @pytest.mark.asyncio
    async def test_persist_discussion_character_location_updates_skips_cross_world_region(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={},
            node_states={},
        )
        db = FakeDiscussionDB()
        db.existing_characters["char-3"] = {
            "id": "char-3",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "跨界角色",
            "world_id": "world-1",
            "current_region_id": "region-old",
        }
        db.regions_by_id["region-3"] = {"id": "region-3", "world_id": "world-2", "name": "北境森林"}

        state = await self.engine._persist_discussion_assets(
            execution,
            {
                "character_location_updates": [
                    {
                        "character_id": "char-3",
                        "current_region_id": "region-3",
                        "current_location_reason": "错误跨世界移动",
                    }
                ],
            },
            db=db,
            confirmation_mode="user_confirm",
        )

        assert state["character_location_updates"]["updated"] == []
        assert state["character_location_updates"]["skipped"] == [
            {"id": "char-3", "name": "跨界角色", "reason": "角色所属世界与当前所在区域不一致"}
        ]
        assert db.existing_characters["char-3"]["current_region_id"] == "region-old"

    @pytest.mark.asyncio
    async def test_confirm_discussion_persists_assets_before_resuming(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={
                "waiting_confirmation": {
                    "discussion_assets": {"plot_updates": [{"summary": "用户确认后再提交"}]},
                    "auto_confirmed": True,
                    "confirmation_mode": "timeout_auto_confirm",
                },
                "group_discussion": {"leader_type": "master_plotter"},
            },
            node_states={},
        )
        self.engine._executions[execution.id] = execution

        async def _fake_broadcast(*args, **kwargs):
            return None

        async def _fake_get_agent(*args, **kwargs):
            return None

        async def _fake_get_workflow(*args, **kwargs):
            return None

        persisted = {}

        async def _fake_persist(execution, bundle, db=None, confirmation_mode="user_confirm"):
            persisted["bundle"] = bundle
            persisted["confirmation_mode"] = confirmation_mode
            state = {"committed": True, "persisted_asset_refs": {"hooks": [], "lores": [], "regions": [], "characters": []}}
            execution.context["discussion_persistence_state"] = state
            execution.context["persisted_asset_refs"] = state["persisted_asset_refs"]
            return state

        self.engine._broadcast_status = _fake_broadcast
        self.engine._get_agent_for_discussion = _fake_get_agent
        self.engine.get_workflow = _fake_get_workflow
        self.engine._persist_discussion_assets = _fake_persist

        result = await self.engine.confirm_discussion(execution.id, approved=True)

        assert result["success"] is True
        assert result["confirmation_mode"] == "timeout_auto_confirm"
        assert persisted["bundle"] == {"plot_updates": [{"summary": "用户确认后再提交"}]}
        assert persisted["confirmation_mode"] == "timeout_auto_confirm"
        assert "waiting_confirmation" not in execution.context
        assert execution.status == WorkflowStatus.RUNNING

    @pytest.mark.asyncio
    async def test_confirm_discussion_persists_character_location_updates_before_resuming(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={
                "waiting_confirmation": {
                    "discussion_assets": {
                        "character_location_updates": [
                            {
                                "character_id": "char-confirm",
                                "current_region_id": "region-confirm",
                                "reason_for_arrival": "确认讨论后前往钟楼守夜",
                            }
                        ]
                    },
                },
                "group_discussion": {"leader_type": "master_plotter"},
            },
            node_states={},
        )
        self.engine._executions[execution.id] = execution
        db = FakeDiscussionDB()
        db.existing_characters["char-confirm"] = {
            "id": "char-confirm",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "守夜人",
            "world_id": "world-confirm",
            "current_location": "旧钟楼外",
            "current_region_id": "region-old",
        }
        db.regions_by_id["region-confirm"] = {
            "id": "region-confirm",
            "world_id": "world-confirm",
            "name": "裂钟楼",
        }

        async def _fake_broadcast(*args, **kwargs):
            return None

        async def _fake_get_agent(*args, **kwargs):
            return None

        async def _fake_get_workflow(*args, **kwargs):
            return None

        async def _fake_save_execution(*args, **kwargs):
            return None

        self.engine._broadcast_status = _fake_broadcast
        self.engine._get_agent_for_discussion = _fake_get_agent
        self.engine.get_workflow = _fake_get_workflow
        self.engine._save_execution_to_db = _fake_save_execution

        result = await self.engine.confirm_discussion(execution.id, approved=True, db=db)

        assert result["success"] is True
        assert result["confirmation_mode"] == "user_confirm"
        assert "waiting_confirmation" not in execution.context
        assert execution.status == WorkflowStatus.RUNNING
        saved = db.existing_characters["char-confirm"]
        assert saved["current_region_id"] == "region-confirm"
        assert saved["current_location"] == "裂钟楼"
        assert saved["current_location_reason"] == "确认讨论后前往钟楼守夜"
        persistence_state = result["discussion_persistence_state"]
        assert persistence_state["character_location_updates"]["updated"][0]["id"] == "char-confirm"
        assert execution.context["persisted_asset_refs"]["character_location_updates"] == ["char-confirm"]

    @pytest.mark.asyncio
    async def test_confirm_discussion_persists_state_changes_before_resuming(self):
        execution = WorkflowExecution(
            workflow_id="test-wf",
            project_id="11111111-1111-1111-1111-111111111111",
            status=WorkflowStatus.PAUSED,
            context={
                "waiting_confirmation": {
                    "discussion_assets": {
                        "state_changes": [
                            {
                                "entity_type": "character",
                                "entity_id": "char-confirm-death",
                                "entity_name": "林砚",
                                "change_type": "death",
                                "title": "林砚确认牺牲",
                                "summary": "确认讨论后记录林砚为关闭裂钟门牺牲",
                                "reason": "以自身灵力封闭裂钟门",
                                "after_state": {"status": "dead"},
                            }
                        ]
                    },
                },
                "group_discussion": {"leader_type": "master_plotter"},
            },
            node_states={},
        )
        self.engine._executions[execution.id] = execution
        db = FakeDiscussionDB()
        db.existing_characters["char-confirm-death"] = {
            "id": "char-confirm-death",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "name": "林砚",
            "status": "active",
            "description": "裂钟门观测员",
        }

        async def _fake_broadcast(*args, **kwargs):
            return None

        async def _fake_get_agent(*args, **kwargs):
            return None

        async def _fake_get_workflow(*args, **kwargs):
            return None

        async def _fake_save_execution(*args, **kwargs):
            return None

        self.engine._broadcast_status = _fake_broadcast
        self.engine._get_agent_for_discussion = _fake_get_agent
        self.engine.get_workflow = _fake_get_workflow
        self.engine._save_execution_to_db = _fake_save_execution

        result = await self.engine.confirm_discussion(execution.id, approved=True, db=db)

        assert result["success"] is True
        assert result["confirmation_mode"] == "user_confirm"
        assert "waiting_confirmation" not in execution.context
        assert execution.status == WorkflowStatus.RUNNING
        saved = db.existing_characters["char-confirm-death"]
        assert saved["status"] == "dead"
        assert saved["death_detail"]["cause"] == "以自身灵力封闭裂钟门"
        persistence_state = result["discussion_persistence_state"]
        assert persistence_state["state_changes"]["created"][0]["title"] == "林砚确认牺牲"
        assert persistence_state["state_changes"]["applied"][0]["projection"]["projection"] == "character"
        assert execution.context["persisted_asset_refs"]["state_changes"] == ["state-change-1"]
        assert execution.context["persisted_asset_refs"]["applied_state_changes"] == ["state-change-1"]

    def test_is_persistable_discussion_character_requires_name_role_and_detail(self):
        assert self.engine._is_persistable_discussion_character({
            "name": "洛澜",
            "importance_tier": "major_ally",
            "description": "码头引路人",
        }) is True
        assert self.engine._is_persistable_discussion_character({
            "name": "一个神秘商人",
            "description": "只被短暂提及",
        }) is False
        assert self.engine._is_persistable_discussion_character({
            "name": "洛澜",
            "description": "缺少叙事定位",
        }) is False
