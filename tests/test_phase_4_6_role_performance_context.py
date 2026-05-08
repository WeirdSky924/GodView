import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.director.writer import WriterAgent
from app.agents.evaluator import EvaluatorAgent
from app.agents.scene_coordinator import SceneCoordinatorAgent
from app.services.workflow_engine import WorkflowEngine


@pytest.mark.asyncio
async def test_scene_coordinator_builds_character_packet_and_scene_context():
    coordinator = SceneCoordinatorAgent(project_id="project-1")

    message = coordinator._build_performance_message(
        char_name="角色甲",
        result_data={
            "dialogue": "我们先离开这里。",
            "action": "压低声音示意撤离",
            "private_thought": "不能让他们知道真正的计划。",
            "intent": "先稳住局面再观察",
            "perceived_facts": ["现场有人受伤"],
            "misinterpretations": ["以为对方已经识破自己"],
            "withheld_information": ["隐藏的接头地点"],
            "relationship_delta": [{"target_character": "角色乙", "dimension": "trust", "delta": -1}],
            "state_delta": [{"field": "emotion", "change": "警惕升高"}],
            "continuity_notes": ["下一轮仍需保留撤离意图"],
            "warnings": ["不要泄露身份"],
            "emotion": "紧张",
        },
        char_data={"importance_tier": 2},
        round_value=2,
    )

    assert message["character_performance_packet"]["character"] == "角色甲"
    assert message["character_performance_packet"]["private_thought"] == "不能让他们知道真正的计划。"
    assert "private_thought" in message["character_performance_packet"]["visibility"]["writer_only_fields"]

    integrated = await coordinator._integrate_performances(
        [message],
        {"scene_type": "interactive", "main_scene": "测试场景"},
    )

    assert integrated["character_performance_packets"][0]["character"] == "角色甲"
    assert integrated["scene_performance_context"]["character_performance_packets"][0]["intent"] == "先稳住局面再观察"
    assert "private_performances" in integrated["scene_performance_context"]["visibility_policy"]


def test_workflow_engine_extracts_scene_performance_context_from_packet():
    engine = WorkflowEngine()
    performance_result = {
        "public_performances": [{"agent": "角色甲", "content": "我去探路。"}],
        "character_performance_packets": [
            {
                "character": "角色甲",
                "public_content": "我去探路。",
                "private_thought": "不能让队友知道我在试探敌人。",
                "intent": "先侦查再回报",
                "withheld_information": ["真正的敌人位置"],
                "misinterpretations": ["误以为对方已经撤退"],
                "relationship_delta": [{"target_character": "角色乙", "dimension": "trust", "delta": 1}],
                "state_delta": [{"field": "location", "change": "进入前厅"}],
                "continuity_notes": ["离开前厅后仍需回报"],
                "warnings": ["避免暴露行踪"],
            }
        ],
        "private_performances": [{"agent": "角色甲", "private_thought": "不能让队友知道我在试探敌人。"}],
        "relationship_deltas": [{"source_character": "角色甲", "target_character": "角色乙", "dimension": "trust", "delta": 1}],
        "state_deltas": [{"source_character": "角色甲", "field": "location", "change": "进入前厅"}],
        "continuity_notes": [{"source_character": "角色甲", "note": "离开前厅后仍需回报"}],
        "performance_warnings": [{"source_character": "角色甲", "warning": "避免暴露行踪"}],
        "full_content": "【角色甲】我去探路。",
        "summary": "角色甲先行侦查。",
        "scene_directions": {"main_scene": "前厅"},
    }

    extracted = engine._extract_role_performance_context(performance_result)

    assert extracted["character_performance_packets"][0]["private_thought"] == "不能让队友知道我在试探敌人。"
    assert extracted["scene_performance_context"]["character_performance_packets"][0]["withheld_information"] == ["真正的敌人位置"]
    assert extracted["last_performance_content"] == "【角色甲】我去探路。"
    assert extracted["last_scene_directions"]["main_scene"] == "前厅"


def test_writer_binding_block_includes_layered_scene_context():
    writer = WriterAgent(project_id="project-1")
    block = writer._build_workflow_binding_block(
        {
            "scene_performance_context": {
                "public_performances": [{"agent": "角色甲", "content": "我去探路。"}],
                "character_performance_packets": [{"character": "角色甲", "private_thought": "不能让队友知道我在试探敌人。"}],
                "private_performances": [{"agent": "角色甲", "private_thought": "不能让队友知道我在试探敌人。"}],
                "relationship_deltas": [{"source_character": "角色甲", "target_character": "角色乙", "dimension": "trust", "delta": 1}],
                "state_deltas": [{"source_character": "角色甲", "field": "location", "change": "进入前厅"}],
                "continuity_notes": [{"source_character": "角色甲", "note": "离开前厅后仍需回报"}],
                "performance_warnings": [{"source_character": "角色甲", "warning": "避免暴露行踪"}],
            },
            "character_performance_packets": [{"character": "角色甲", "private_thought": "不能让队友知道我在试探敌人。"}],
            "relationship_deltas": [{"source_character": "角色甲", "target_character": "角色乙", "dimension": "trust", "delta": 1}],
            "state_deltas": [{"source_character": "角色甲", "field": "location", "change": "进入前厅"}],
            "continuity_notes": [{"source_character": "角色甲", "note": "离开前厅后仍需回报"}],
            "performance_warnings": [{"source_character": "角色甲", "warning": "避免暴露行踪"}],
        }
    )

    assert "场景演绎分层上下文" in block
    assert "角色表演包" in block
    assert "关系/状态/连续性变化" in block
    assert "不能让队友知道我在试探敌人。" in block


def test_evaluator_private_fragments_pick_packets_from_scene_context():
    evaluator = EvaluatorAgent(project_id="project-1")
    fragments = evaluator._private_performance_fragments(
        {
            "scene_performance_context": {
                "character_performance_packets": [
                    {
                        "character": "角色甲",
                        "private_thought": "不能让队友知道我在试探敌人。",
                        "intent": "先侦查再回报",
                        "withheld_information": ["真正的敌人位置"],
                        "misinterpretations": ["误以为对方已经撤退"],
                    }
                ]
            }
        }
    )

    fields = {(item["agent"], item["field"]) for item in fragments}
    values = {item["value"] for item in fragments}

    assert ("角色甲", "private_thought") in fields
    assert ("角色甲", "intent") in fields
    assert "不能让队友知道我在试探敌人。" in values
    assert "真正的敌人位置" in values
