import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.chapter_outline import ChapterOutline, SceneOutline
from app.services.plot_outline_service import PlotOutlineService


def test_character_availability_packet_uses_hierarchy_and_lifecycle():
    service = PlotOutlineService(db=None)
    packet = service._build_character_availability_packet(
        [
            {
                "name": "林默",
                "role": "npc",
                "importance_tier": "protagonist",
                "status": "active",
                "available_presence_types": ["present"],
                "goals": ["寻找真相"],
            },
            {
                "name": "旧王",
                "importance_tier": "major_antagonist",
                "status": "dead",
                "available_presence_types": ["memory"],
            },
            {
                "name": "未来导师",
                "status": "active",
                "debut_chapter": 5,
                "available_presence_types": ["present"],
            },
        ],
        chapter_number=1,
    )

    assert packet["direct_available_characters"][0]["name"] == "林默"
    assert "主角" in packet["direct_available_characters"][0]["hierarchy_label"]
    assert packet["mentioned_only_characters"][0]["name"] == "旧王"
    assert packet["unavailable_characters"][0]["name"] == "未来导师"


def test_format_context_for_prompt_includes_availability_contract_and_not_raw_role_only():
    service = PlotOutlineService(db=None)
    characters = [
        {
            "name": "林默",
            "aliases": ["小林"],
            "role": "npc",
            "importance_tier": "protagonist",
            "status": "active",
            "available_presence_types": ["present"],
            "description": "第一主角。",
        }
    ]
    context = {"characters": characters, "character_availability_packet": service._build_character_availability_packet(characters, 1)}

    rendered = service.format_context_for_prompt(context)

    assert "本章角色可用性硬约束" in rendered
    assert "林默 (主角; role=npc)" in rendered
    assert "输出字段必须使用标准名“林默”" in rendered


def test_outline_character_availability_audit_blocks_unavailable_direct_participation():
    service = PlotOutlineService(db=None)
    characters = [
        {"name": "林默", "importance_tier": "protagonist", "status": "active", "available_presence_types": ["present"]},
        {"name": "旧王", "status": "dead", "available_presence_types": ["memory"]},
    ]
    packet = service._build_character_availability_packet(characters, 3)
    outline = ChapterOutline(
        project_id="project_1",
        chapter_number=3,
        title="测试章",
        summary="旧王的阴影仍在。",
        scenes=[
            SceneOutline(
                scene_number=1,
                title="旧王入场",
                summary="旧王走进大厅并开口命令众人。",
                participating_characters=["旧王"],
                pov_character="林默",
            )
        ],
        character_arcs={},
    )

    audit = service._audit_outline_character_availability(outline, packet)

    assert audit["passed"] is False
    assert audit["violations"][0]["character_name"] == "旧王"
    assert audit["violations"][0]["availability_bucket"] == "mentioned_only"


def test_outline_resource_requirements_include_known_but_unavailable_character():
    service = PlotOutlineService(db=None)
    full_context = {
        "characters": [
            {"name": "旧王", "status": "dead", "available_presence_types": ["memory"]},
        ],
        "world_settings": [],
    }
    full_context["character_availability_packet"] = service._build_character_availability_packet(full_context["characters"], 4)
    outline = ChapterOutline(
        project_id="project_1",
        chapter_number=4,
        title="测试章",
        summary="旧王被安排直接出场。",
        scenes=[
            SceneOutline(
                scene_number=1,
                title="旧王现身",
                summary="旧王出现并说出命令。",
                participating_characters=["旧王"],
            )
        ],
        character_arcs={},
    )

    requirements = service._build_outline_resource_requirements(outline, full_context, known_location_names=set())

    assert any(req["requirement_type"] == "character_availability" for req in requirements)
    requirement = next(req for req in requirements if req["requirement_type"] == "character_availability")
    assert requirement["resource_name"] == "旧王"
    assert requirement["severity"] == "blocking"
