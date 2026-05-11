from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.api.app as api_app
from app.api.app import create_app
from app.models.assistant_context import AssistantContextBudget
from app.models.skill import SkillTestResult
from app.services.assistant_context import get_assistant_context_fabric
from app.services.assistant_context.packet_builder import ContextPacketBuilder
from app.services.assistant_context.snapshot_service import ProjectSnapshotService


PROJECT_ID = "35d82acc-1dc7-4f0d-a7e1-9cf919960f6a"


class InMemoryAssistantContextDB:
    def __init__(self):
        self.projects = {
            PROJECT_ID: {
                "id": PROJECT_ID,
                "name": "星辰",
                "description": "跨星门长篇项目",
                "created_at": datetime(2026, 5, 1),
                "updated_at": datetime(2026, 5, 11),
            }
        }
        self.worlds = [
            {
                "id": str(uuid4()),
                "project_id": PROJECT_ID,
                "name": "主世界",
                "world_type": "科幻",
                "tone": "冷峻",
                "description": "星门网络覆盖的近未来世界。",
                "created_at": datetime(2026, 5, 1),
                "updated_at": datetime(2026, 5, 2),
            }
        ]
        self.characters = [
            {
                "id": str(uuid4()),
                "project_id": PROJECT_ID,
                "name": "林砚",
                "role": "主角",
                "personality": "谨慎、执拗",
                "background_story": "事故调查员。",
                "importance_tier": "core",
                "status": "active",
                "created_at": datetime(2026, 5, 1),
                "updated_at": datetime(2026, 5, 3),
            }
        ]
        self.lores = [
            {
                "id": str(uuid4()),
                "title": "星门协议",
                "category": "technology",
                "priority": "core",
                "summary": "限制星门跃迁的基础协议。",
                "content": "所有星门跃迁必须经过三重签名确认。",
                "keywords": ["星门", "协议"],
                "created_at": datetime(2026, 5, 1),
                "updated_at": datetime(2026, 5, 4),
            }
        ]
        self.hooks = [
            {
                "id": str(uuid4()),
                "title": "失踪信标",
                "description": "第一章出现的异常信标。",
                "hook_type": "mystery",
                "status": "planted",
                "plant_chapter": 1,
                "resolution_chapter": None,
                "created_at": datetime(2026, 5, 1),
                "resolved_at": None,
            }
        ]
        self.outlines = [
            {
                "id": str(uuid4()),
                "chapter_number": 1,
                "title": "雨夜信标",
                "summary": "林砚发现异常信标。",
                "status": "approved",
                "created_at": datetime(2026, 5, 1),
                "updated_at": datetime(2026, 5, 5),
            }
        ]
        self.regions = [
            {
                "id": str(uuid4()),
                "name": "旧港星门站",
                "world_id": self.worlds[0]["id"],
                "world_name": "主世界",
                "region_type": "city",
                "terrain_type": "urban",
                "description": "旧港边缘的星门枢纽。",
                "atmosphere": "潮湿、警戒森严",
                "connections": [],
                "created_at": datetime(2026, 5, 1),
                "updated_at": datetime(2026, 5, 6),
            }
        ]
        self.snapshots: List[Dict[str, Any]] = []
        self.sections: Dict[str, List[Dict[str, Any]]] = {}
        self.deltas: List[Dict[str, Any]] = []
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.messages: List[Dict[str, Any]] = []
        self.packets: Dict[str, Dict[str, Any]] = {}

    async def get_project(self, project_id: str):
        return self.projects.get(project_id)

    async def get_worlds_by_project(self, project_id: str, limit: int = 200):
        return [row for row in self.worlds if row.get("project_id") == project_id][:limit]

    async def get_all_characters(self, project_id: Optional[str] = None, limit: int = 500, **_: Any):
        rows = self.characters if project_id is None else [row for row in self.characters if row.get("project_id") == project_id]
        return rows[:limit]

    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None):
        if "FROM lore_entries" in query:
            return list(self.lores)
        if "FROM hooks" in query:
            return list(self.hooks)
        if "FROM chapter_outlines" in query:
            return list(self.outlines)
        if "FROM regions" in query:
            return list(self.regions)
        raise AssertionError(f"Unexpected SQL in fake DB: {query}")

    async def save_assistant_snapshot(self, snapshot_data: Dict[str, Any], sections: Optional[List[Dict[str, Any]]] = None):
        data = dict(snapshot_data)
        data.setdefault("id", str(uuid4()))
        data.setdefault("created_at", datetime.utcnow())
        data.setdefault("updated_at", datetime.utcnow())
        self.snapshots = [row for row in self.snapshots if row["id"] != data["id"]]
        self.snapshots.append(data)
        if sections is not None:
            self.sections[data["id"]] = []
            for section in sections:
                await self.save_assistant_snapshot_section(data["id"], data["project_id"], section)
        return data["id"]

    async def save_assistant_snapshot_section(self, snapshot_id: str, project_id: str, section: Dict[str, Any]):
        row = dict(section)
        row.setdefault("id", str(uuid4()))
        row["snapshot_id"] = snapshot_id
        row["project_id"] = project_id
        self.sections.setdefault(snapshot_id, []).append(row)
        return row["id"]

    async def get_latest_assistant_snapshot(self, project_id: str, status: Optional[str] = "ready"):
        rows = [row for row in self.snapshots if row.get("project_id") == project_id]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        rows.sort(key=lambda row: (int(row.get("snapshot_version") or 0), row.get("built_at") or datetime.min), reverse=True)
        return rows[0] if rows else None

    async def get_assistant_snapshot_sections(self, snapshot_id: str):
        return sorted(self.sections.get(snapshot_id, []), key=lambda row: (row.get("priority", 100), row.get("section_type", ""), row.get("title", "")))

    async def mark_assistant_snapshots_stale(self, project_id: str, except_snapshot_id: Optional[str] = None):
        count = 0
        for row in self.snapshots:
            if row.get("project_id") == project_id and row.get("status") == "ready" and row.get("id") != except_snapshot_id:
                row["status"] = "stale"
                count += 1
        return count

    async def save_assistant_delta(self, delta_data: Dict[str, Any]):
        row = dict(delta_data)
        row.setdefault("id", str(uuid4()))
        row.setdefault("created_at", datetime.utcnow())
        row.setdefault("consumed_by_snapshot_id", None)
        self.deltas.append(row)
        return row["id"]

    async def get_assistant_deltas(self, project_id: str, limit: int = 100, consumed: Optional[bool] = None):
        rows = [row for row in self.deltas if row.get("project_id") == project_id]
        if consumed is True:
            rows = [row for row in rows if row.get("consumed_by_snapshot_id")]
        elif consumed is False:
            rows = [row for row in rows if not row.get("consumed_by_snapshot_id")]
        rows.sort(key=lambda row: row.get("created_at") or datetime.min, reverse=True)
        return rows[:limit]

    async def save_assistant_session(self, session_data: Dict[str, Any]):
        row = dict(session_data)
        row.setdefault("created_at", datetime.utcnow())
        row.setdefault("updated_at", datetime.utcnow())
        self.sessions[row["id"]] = row
        return row["id"]

    async def get_assistant_session(self, session_id: str):
        return self.sessions.get(session_id)

    async def get_active_assistant_session(self, project_id: str, assistant_surface: str, mode: str = "default"):
        rows = [
            row for row in self.sessions.values()
            if row.get("project_id") == project_id
            and row.get("assistant_surface") == assistant_surface
            and row.get("mode") == mode
            and row.get("status") == "active"
        ]
        rows.sort(key=lambda row: row.get("last_activity_at") or datetime.min, reverse=True)
        return rows[0] if rows else None

    async def reset_assistant_session(self, session_id: str, reason: str = "user_requested"):
        session = self.sessions[session_id]
        session["status"] = "reset"
        session["reset_reason"] = reason
        session["reset_at"] = datetime.utcnow()
        return 1

    async def append_assistant_message(self, session_id: str, project_id: str, role: str, content: str, request_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None, packet_id: Optional[str] = None, snapshot_id: Optional[str] = None):
        for row in self.messages:
            if request_id and row.get("session_id") == session_id and row.get("request_id") == request_id and row.get("role") == role:
                row.update({"content": content, "metadata": metadata or {}, "packet_id": packet_id, "snapshot_id": snapshot_id})
                return row["id"]
        row = {
            "id": str(uuid4()),
            "session_id": session_id,
            "project_id": project_id,
            "role": role,
            "content": content,
            "request_id": request_id,
            "metadata": metadata or {},
            "packet_id": packet_id,
            "snapshot_id": snapshot_id,
            "created_at": datetime.utcnow(),
        }
        self.messages.append(row)
        return row["id"]

    async def get_assistant_messages(self, session_id: str, limit: int = 200):
        return [row for row in self.messages if row.get("session_id") == session_id][:limit]

    async def delete_assistant_messages(self, session_id: str):
        before = len(self.messages)
        self.messages = [row for row in self.messages if row.get("session_id") != session_id]
        return before - len(self.messages)

    async def save_assistant_packet(self, packet_data: Dict[str, Any]):
        if packet_data.get("request_id"):
            for existing_id, existing in self.packets.items():
                if (
                    existing.get("session_id") == packet_data.get("session_id")
                    and existing.get("request_id") == packet_data.get("request_id")
                    and existing.get("assistant_surface") == packet_data.get("assistant_surface")
                ):
                    existing.update(packet_data)
                    return existing_id
        row = dict(packet_data)
        row.setdefault("id", str(uuid4()))
        row.setdefault("created_at", datetime.utcnow())
        self.packets[row["id"]] = row
        if row.get("session_id") and row["session_id"] in self.sessions:
            self.sessions[row["session_id"]]["last_packet_id"] = row["id"]
        return row["id"]

    async def get_assistant_packet(self, packet_id: str):
        return self.packets.get(packet_id)


@pytest.mark.asyncio
async def test_snapshot_builds_typed_sections_and_stales_previous_snapshot():
    db = InMemoryAssistantContextDB()
    service = ProjectSnapshotService(db)

    first = await service.build_snapshot(PROJECT_ID)
    second = await service.force_rebuild(PROJECT_ID, request_id="force-1", forced_by_user_id="user-1")

    assert first["snapshot_version"] == 1
    assert second["snapshot_version"] == 2
    assert second["build_reason"] == "manual_force_rebuild"
    assert second["force_rebuild_request_id"] == "force-1"
    assert db.snapshots[0]["status"] == "stale"
    assert db.snapshots[1]["status"] == "ready"

    sections = await db.get_assistant_snapshot_sections(second["id"])
    section_types = {section["section_type"] for section in sections}
    assert {"project_brief", "world", "lore", "characters", "plot_hooks", "chapter_outlines", "map_regions"}.issubset(section_types)
    assert second["structured_index"]["lores"] == 1
    assert second["token_estimate"] > 0


@pytest.mark.asyncio
async def test_fabric_build_packet_persists_session_message_packet_and_delta_metadata():
    db = InMemoryAssistantContextDB()
    fabric = get_assistant_context_fabric(db)
    delta_id = await fabric.deltas.record_entity_change(
        project_id=PROJECT_ID,
        entity_type="lore",
        entity_id="lore-1",
        operation="update",
        before={"title": "旧协议"},
        after={"title": "星门协议"},
        source_table="lore_entries",
    )

    result = await fabric.build_packet(
        project_id=PROJECT_ID,
        assistant_surface="setting_agent",
        task_type="chat",
        request_id="req-1",
        user_message="请检查星门协议",
        scope={"topic": "星门"},
    )

    assert result["packet_id"] in db.packets
    assert result["session_id"] in db.sessions
    assert db.sessions[result["session_id"]]["last_packet_id"] == result["packet_id"]
    assert db.messages[0]["content"] == "请检查星门协议"
    assert db.messages[0]["packet_id"] == result["packet_id"]
    packet = db.packets[result["packet_id"]]
    assert packet["delta_ids"] == [delta_id]
    assert packet["invalidation_state"] == "delta_applied"
    assert result["metadata"]["delta_count"] == 1
    assert "Recent Project Deltas" in result["prompt_context"]


@pytest.mark.asyncio
async def test_reset_history_archives_old_session_without_deleting_project_data_or_pending_items():
    db = InMemoryAssistantContextDB()
    fabric = get_assistant_context_fabric(db)
    packet = await fabric.build_packet(
        project_id=PROJECT_ID,
        assistant_surface="setting_agent",
        request_id="req-reset-seed",
        user_message="旧对话",
    )
    session = db.sessions[packet["session_id"]]
    session["pending_items"] = [{"kind": "lore", "title": "待确认设定"}]

    reset = await fabric.reset_history(project_id=PROJECT_ID, session_id=session["id"], clear_pending_items=False)

    assert db.sessions[session["id"]]["status"] == "reset"
    assert reset["messages_deleted"] == 1
    assert reset["new_session_id"] != session["id"]
    new_session = db.sessions[reset["new_session_id"]]
    assert new_session["status"] == "active"
    assert new_session["history_window"] == []
    assert new_session["pending_items"] == [{"kind": "lore", "title": "待确认设定"}]
    assert db.lores[0]["title"] == "星门协议"


def test_packet_builder_truncates_low_priority_sections_deterministically():
    builder = ContextPacketBuilder()
    snapshot = {"id": "snapshot-1", "snapshot_version": 1, "summary": "摘要"}
    sections = [
        {"id": "project", "section_type": "project_brief", "scope_key": "project", "title": "项目", "content": "项目简介", "priority": 10, "token_estimate": 4},
        {"id": "lore", "section_type": "lore", "scope_key": "lore:1", "title": "设定", "content": "设定内容" * 20, "priority": 30, "token_estimate": 80},
    ]

    packet = builder.build(
        project_id=PROJECT_ID,
        assistant_surface="setting_agent",
        task_type="chat",
        snapshot=snapshot,
        sections=sections,
        deltas=[],
        session=None,
        scope={},
        budget=AssistantContextBudget(max_context_tokens=1000, snapshot_tokens=10, delta_tokens=10, history_tokens=10, retrieval_tokens=10),
    )

    assert packet["packet_data"]["truncated"] is True
    assert [section["section_type"] for section in packet["metadata"]["selected_sections"]] == ["project_brief"]
    assert packet["metadata"]["omitted_sections"][0]["section_type"] == "lore"
    assert packet["metadata"]["omitted_sections"][0]["reason"] == "budget"


def test_volume_generation_routes_return_assistant_context_packets(monkeypatch):
    db = InMemoryAssistantContextDB()
    monkeypatch.setattr(api_app, "postgres_db", db)

    captured_parameters: List[Dict[str, Any]] = []

    class FakeSkillService:
        async def execute_skill(self, dto):
            captured_parameters.append(dto.parameters)
            if dto.parameters.get("task") == "climax_design":
                return SkillTestResult(
                    success=True,
                    structured_output={
                        "climax_chapter": 12,
                        "climax_description": "星门站真相爆发。",
                        "buildup_scenes": [{"summary": "信标回响"}],
                        "aftermath_scenes": [{"summary": "阵营重组"}],
                    },
                )
            return SkillTestResult(
                success=True,
                structured_output={
                    "volume_info": {"title": "星门余波", "summary": "追查事故源头。"},
                    "emotional_arc": {"dominant": "紧张"},
                    "climax_design": {"climax_description": "旧港对峙", "climax_chapter": 10},
                    "chapter_plan": [{"chapter": 1, "title": "旧港", "summary": "抵达旧港"}],
                    "transitions": {"from_previous": "承接信标"},
                    "word_distribution": {"target": 50000},
                },
            )

    import app.services.skill_service as skill_service_module

    previous_skill_service = getattr(skill_service_module, "_skill_service", None)
    skill_service_module.set_skill_service(FakeSkillService())
    client = TestClient(create_app())

    try:
        plan_response = client.post(
            "/api/volumes/plan",
            json={
                "project_id": PROJECT_ID,
                "volume_number": 2,
                "book_outline": "调查星门事故",
                "request_id": "volume-plan-1",
            },
        )
        assert plan_response.status_code == 200
        plan_payload = plan_response.json()
        assert plan_payload["context_packet"]["assistant_surface"] == "volume_planning"
        assert plan_payload["assistant_session_id"]
        assert captured_parameters[0]["assistant_context_packet_id"] == plan_payload["context_packet"]["packet_id"]
        assert "Project Snapshot" in captured_parameters[0]["assistant_context"]

        climax_response = client.post(
            "/api/volumes/2/climax",
            json={
                "project_id": PROJECT_ID,
                "volume_id": "volume-2",
                "climax_event": "旧港星门站对峙",
                "emotional_peak": "紧张爆发",
                "participating_characters": ["林砚"],
                "request_id": "volume-climax-1",
            },
        )
        assert climax_response.status_code == 200
        climax_payload = climax_response.json()
        assert climax_payload["context_packet"]["assistant_surface"] == "volume_planning"
        assert captured_parameters[1]["assistant_context_packet_id"] == climax_payload["context_packet"]["packet_id"]
    finally:
        skill_service_module.set_skill_service(previous_skill_service)


def test_assistant_context_api_reset_and_force_reread(monkeypatch):
    db = InMemoryAssistantContextDB()
    monkeypatch.setattr(api_app, "postgres_db", db)
    client = TestClient(create_app())

    create_response = client.post(
        f"/api/assistant-context/{PROJECT_ID}/sessions",
        json={"assistant_surface": "setting_agent", "mode": "management", "scope": {"entry": "lore"}},
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    db.messages.append({
        "id": str(uuid4()),
        "session_id": session_id,
        "project_id": PROJECT_ID,
        "role": "user",
        "content": "需要清空的旧消息",
        "metadata": {},
        "created_at": datetime.utcnow(),
    })
    reset_response = client.post(
        f"/api/assistant-context/{PROJECT_ID}/sessions/{session_id}/reset-history",
        json={"assistant_surface": "setting_agent", "mode": "management", "request_id": "reset-1"},
    )
    assert reset_response.status_code == 200
    reset_payload = reset_response.json()
    assert reset_payload["old_session_id"] == session_id
    assert reset_payload["new_session_id"] != session_id
    assert reset_payload["messages_deleted"] == 1

    reread_response = client.post(
        f"/api/assistant-context/{PROJECT_ID}/force-reread",
        json={"assistant_surface": "setting_agent", "session_id": reset_payload["new_session_id"], "mode": "management", "request_id": "reread-1"},
    )
    assert reread_response.status_code == 200
    reread_payload = reread_response.json()
    assert reread_payload["force_reread"] is True
    assert reread_payload["snapshot_version"] >= 2
    assert reread_payload["previous_snapshot_version"] == 1
    assert reread_payload["packet_metadata"]["invalidation_state"] == "force_rebuilt"

    health_response = client.get(f"/api/assistant-context/{PROJECT_ID}/health")
    assert health_response.status_code == 200
    assert health_response.json()["healthy"] is True
