import pytest

from app.services.character_reference_resolver import get_character_reference_resolver


class FakeReferenceDb:
    def __init__(self):
        self.characters = [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "project_id": "project-a",
                "name": "林默",
                "aliases": ["林队", "L"],
                "role": "main",
                "importance_tier": "protagonist",
                "description": "主角",
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "project_id": "project-a",
                "name": "K",
                "aliases": ["K老师"],
                "role": "supporting",
                "importance_tier": "mentor",
                "description": "AI 导师",
            },
        ]
        self.external_character = {
            "id": "33333333-3333-3333-3333-333333333333",
            "project_id": "project-b",
            "name": "跨项目角色",
        }

    async def get_characters_for_reference_resolution(self, project_id):
        return [item for item in self.characters if item["project_id"] == project_id]

    async def get_character(self, character_id):
        if character_id == self.external_character["id"]:
            return self.external_character
        return next((item for item in self.characters if item["id"] == character_id), None)


@pytest.mark.asyncio
async def test_resolver_canonicalizes_id_name_and_alias_without_raw_fallback():
    resolver = get_character_reference_resolver(FakeReferenceDb())

    result = await resolver.resolve_for_lore(
        project_id="project-a",
        references=[
            "11111111-1111-1111-1111-111111111111",
            "K",
            "林队",
            "不存在的人",
        ],
        provenance={"test": "resolver"},
    )

    assert result.related_characters == [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]
    assert [item["resolution_method"] for item in result.related_character_refs] == ["id", "exact_name"]
    assert result.unresolved_character_refs[0]["source_text"] == "不存在的人"
    assert result.unresolved_character_refs[0]["reason"] == "no_deterministic_match"


@pytest.mark.asyncio
async def test_resolver_rejects_cross_project_uuid_as_unresolved():
    resolver = get_character_reference_resolver(FakeReferenceDb())

    result = await resolver.resolve_for_lore(
        project_id="project-a",
        references=["33333333-3333-3333-3333-333333333333"],
        provenance={"test": "cross_project"},
    )

    assert result.related_characters == []
    assert result.related_character_refs == []
    assert result.unresolved_character_refs[0]["reason"] == "cross_project_reference"
