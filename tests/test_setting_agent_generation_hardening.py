import pytest
from langchain_core.messages import AIMessage

from app.database.postgres import _normalize_age, _normalize_bool, _normalize_int
from app.models.agent_output_schemas import SettingPendingHooksExtractionSchema
from app.services.setting_agent_service import SettingAgentService
from app.services.structured_llm import StructuredLLMRunner


class _RawOnlyStructuredModel:
    async def ainvoke(self, messages):
        return {
            "raw": AIMessage(content='[{"title":"失踪怀表","description":"怀表会在月蚀夜回响","priority":4}]'),
            "parsed": None,
            "parsing_error": ValueError("未拿到 parsed 对象"),
        }


@pytest.mark.asyncio
async def test_structured_runner_recovers_raw_json_array_when_parsed_missing():
    runner = StructuredLLMRunner()

    parsed, raw_text, parse_error = await runner._invoke_once(
        _RawOnlyStructuredModel(),
        [],
        SettingPendingHooksExtractionSchema,
    )

    assert parse_error is None
    assert raw_text
    assert len(parsed.hooks) == 1
    assert parsed.hooks[0].title == "失踪怀表"
    assert parsed.hooks[0].priority == 4


def test_setting_agent_normalizes_generated_character_fields():
    service = SettingAgentService()

    normalized = service._normalize_character_payload_for_persistence({
        "name": "阿洛",
        "importance_tier": "major",
        "narrative_weight": "核心领袖角色",
        "story_arc_role": "领袖牺牲者",
        "plot_priority": "high",
        "age": "30多岁",
        "has_agent": "是",
        "agent_enabled": "否",
    })

    assert normalized["importance_tier"] == "deuteragonist"
    assert normalized["narrative_weight"] == "full_focus"
    assert normalized["story_arc_role"] == "sacrifice"
    assert normalized["plot_priority"] == 8
    assert normalized["age"] == 30
    assert normalized["has_agent"] is True
    assert normalized["agent_enabled"] is False


def test_postgres_character_scalar_guards_coerce_llm_labels():
    assert _normalize_int("high", 0, 0, 10) == 0
    assert _normalize_int("优先级7", 0, 0, 10) == 7
    assert _normalize_int(99, 0, 0, 10) == 10
    assert _normalize_age("30多岁") == 30
    assert _normalize_age("未知") is None
    assert _normalize_bool("启用") is True
    assert _normalize_bool("关闭", True) is False


def test_setting_agent_backfills_explicit_character_name_when_structured_extract_misses_it():
    service = SettingAgentService()

    merged = service._merge_explicit_pending_characters(
        [],
        [{"role": "user", "content": "在设定助手生成角色管理的内容时遗漏了一个角色，角色是破晓者。"}],
    )

    assert len(merged) == 1
    assert merged[0]["name"] == "破晓者"
    assert merged[0]["importance_tier"] == "npc"
    assert merged[0]["plot_priority"] == 0


def test_setting_agent_does_not_duplicate_explicit_character_already_extracted():
    service = SettingAgentService()

    merged = service._merge_explicit_pending_characters(
        [{"name": "破晓者", "importance_tier": "major_ally"}],
        [{"role": "user", "content": "角色是破晓者"}],
    )

    assert len(merged) == 1
    assert merged[0]["importance_tier"] == "major_ally"


def test_setting_agent_save_intent_does_not_intercept_new_character_content():
    service = SettingAgentService()

    classified = service._classify_save_intent("保存这个新角色，角色是破晓者")

    assert classified["is_save_intent"] is False
    assert classified["scope"] == "new_content"
    assert classified["targets"] == ["破晓者"]


def test_setting_agent_save_intent_supports_targeted_pending_filter():
    service = SettingAgentService()
    classification = service._classify_save_intent("只保存破晓者")

    assert classification["is_save_intent"] is True
    assert classification["scope"] == "targeted"
    assert classification["targets"] == ["破晓者"]

    class Session:
        cached_pending_lores = [{"title": "旧设定"}]
        cached_pending_characters = [{"name": "旧角色"}, {"name": "破晓者"}]
        cached_pending_hooks = [{"title": "旧伏笔"}]

    lores, characters, hooks = service._filter_pending_for_save_intent(Session(), classification)

    assert lores == []
    assert characters == [{"name": "破晓者"}]
    assert hooks == []


def test_setting_agent_pure_save_intent_still_returns_all_pending():
    service = SettingAgentService()

    classified = service._classify_save_intent("确认保存")

    assert classified["is_save_intent"] is True
    assert classified["scope"] == "all"
    assert classified["targets"] == []
