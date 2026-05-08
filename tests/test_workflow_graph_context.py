import pytest

from app.models.workflow_definition import DataInputSource, NodeInputConfig, NodeType, WorkflowNode
from app.models.workflow_execution import WorkflowExecution, WorkflowStatus
from app.services.agent_prompt_builder import AgentPromptBuilder
from app.services.workflow_engine import WorkflowEngine


class FakeGraphDB:
    async def get_character(self, character_id):
        return {
            "id": character_id,
            "name": "林砚" if character_id == "char-1" else "洛澜",
            "project_id": "proj-1",
            "key_relationships": {"char-2": "盟友"} if character_id == "char-1" else {},
        }

    async def get_all_characters(self, project_id=None, role=None, limit=100):
        return [
            {"id": "char-1", "name": "林砚", "project_id": "proj-1", "key_relationships": {"char-2": "盟友"}},
            {"id": "char-2", "name": "洛澜", "project_id": "proj-1", "key_relationships": {}},
        ]

    async def get_all_hooks(self, project_id=None, status=None, limit=100):
        return []


@pytest.mark.asyncio
async def test_workflow_loads_graph_context_only_when_enabled():
    engine = WorkflowEngine()
    db = FakeGraphDB()

    disabled = await engine._load_data_from_database(
        "graph_context",
        "proj-1",
        db,
        {"graph_context_request": {"enabled": False, "anchor_id": "char-1"}},
    )
    assert disabled is None

    context = {"graph_context_request": {"enabled": True, "anchor_type": "character", "anchor_id": "char-1"}}
    loaded = await engine._load_data_from_database("graph_context", "proj-1", db, context)

    assert loaded["source"] == "postgres"
    assert loaded["anchor"]["id"] == "char-1"
    assert context["graph_context_candidate"] == loaded


@pytest.mark.asyncio
async def test_prepare_node_inputs_accepts_graph_context_data_type():
    engine = WorkflowEngine()
    node = WorkflowNode(
        id="graph-node",
        node_type=NodeType.AGENT,
        agent_type="writer",
        label="图上下文节点",
        inputs=[
            NodeInputConfig(
                name="graph_context",
                source=DataInputSource.DATABASE,
                data_type="graph_context",
                required=False,
            )
        ],
    )
    execution = WorkflowExecution(
        workflow_id="wf-1",
        project_id="proj-1",
        status=WorkflowStatus.RUNNING,
        context={"graph_context_request": {"enabled": True, "anchor_type": "character", "anchor_id": "char-1"}},
    )

    prepared = await engine._prepare_node_inputs(node, execution, FakeGraphDB())

    assert prepared["graph_context"]["source"] == "postgres"
    assert prepared["graph_context_candidate"]["anchor"]["id"] == "char-1"


@pytest.mark.asyncio
async def test_maybe_attach_graph_context_is_default_off_for_supported_profile():
    engine = WorkflowEngine()
    node = WorkflowNode(
        id="writer-node",
        node_type=NodeType.AGENT,
        agent_type="writer",
        label="写作节点",
    )
    execution = WorkflowExecution(
        workflow_id="wf-1",
        project_id="proj-1",
        status=WorkflowStatus.RUNNING,
        context={"character_id": "char-1"},
    )

    from app.services.workflow_node_registry import get_workflow_node_profile

    context = await engine._maybe_attach_graph_context(
        node,
        execution,
        FakeGraphDB(),
        execution.context.copy(),
        get_workflow_node_profile("writer"),
    )

    assert "graph_context" not in context
    assert "graph_context_summary" not in context


@pytest.mark.asyncio
async def test_maybe_attach_graph_context_adds_compact_context_when_enabled():
    engine = WorkflowEngine()
    node = WorkflowNode(
        id="writer-node",
        node_type=NodeType.AGENT,
        agent_type="writer",
        label="写作节点",
    )
    execution = WorkflowExecution(
        workflow_id="wf-1",
        project_id="proj-1",
        status=WorkflowStatus.RUNNING,
        context={
            "character_id": "char-1",
            "graph_context_request": {"enabled": True, "anchor_type": "character", "max_nodes": 4},
        },
    )

    from app.services.workflow_node_registry import get_workflow_node_profile

    context = await engine._maybe_attach_graph_context(
        node,
        execution,
        FakeGraphDB(),
        execution.context.copy(),
        get_workflow_node_profile("writer"),
    )

    assert context["graph_context_source"] == "postgres"
    assert context["graph_context"]["anchor"]["id"] == "char-1"
    assert context["graph_context"]["relationships"][0]["target_name"] == "洛澜"
    assert "properties" not in context["graph_context"]["nodes"][0]
    assert execution.context["graph_context_candidate"]["anchor"]["id"] == "char-1"


def test_prompt_builder_renders_compact_graph_context_without_raw_properties():
    builder = AgentPromptBuilder()

    prompt = builder._build_context_section(
        {
            "graph_context_summary": "林砚周边包含 2 个节点、1 条边。",
            "graph_context_source": "postgres",
            "graph_context": {
                "source": "postgres",
                "summary": "林砚周边包含 2 个节点、1 条边。",
                "anchor": {"id": "char-1", "type": "character", "name": "林砚"},
                "relationships": [
                    {"target_id": "char-2", "target_name": "洛澜", "type": "盟友", "strength": 0.8}
                ],
                "nodes": [
                    {"id": "char-1", "type": "character", "name": "林砚", "properties": {"secret": "不应渲染"}},
                    {"id": "char-2", "type": "character", "name": "洛澜"},
                ],
                "warnings": ["fallback"],
            },
        }
    )

    assert "### 关系图上下文（局部）" in prompt
    assert "洛澜: 盟友" in prompt
    assert "properties" not in prompt
    assert "不应渲染" not in prompt


def test_prompt_builder_omits_graph_section_when_absent():
    builder = AgentPromptBuilder()

    prompt = builder._build_context_section({"characters": []})

    assert "关系图上下文" not in prompt
