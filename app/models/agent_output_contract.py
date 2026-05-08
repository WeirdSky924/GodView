"""Agent 输出契约模型与默认注册表。

用于显式定义 GodView 各 Agent / 场景的输出边界，区分：
- text: 纯文本展示
- hybrid: 文本 + 必须正确的结构化元数据
- strict: 必须通过结构化契约提供给程序消费
"""

import importlib
from enum import Enum
from typing import List, Optional, Type

from pydantic import BaseModel, Field

from app.models.agent_template import AgentType


class OutputContractMode(str, Enum):
    """输出模式。"""

    TEXT = "text"
    HYBRID = "hybrid"
    STRICT = "strict"


class OutputContractScene(str, Enum):
    """输出发生的场景。"""

    WORKFLOW_EDITOR = "workflow_editor"
    WORKFLOW_RUNTIME = "workflow_runtime"
    ROUTE_UI = "route_ui"
    AGENT_CHAT = "agent_chat"


class OutputContractConsumer(str, Enum):
    """输出的消费方类型。"""

    WORKFLOW_DEFINITION = "workflow_definition"
    EXECUTION_EVENT = "execution_event"
    DOWNSTREAM_NODE = "downstream_node"
    DTO_RESPONSE = "dto_response"
    UI_METADATA = "ui_metadata"
    PERSISTED_OBJECT = "persisted_object"
    PROSE_ONLY = "prose_only"


class OutputContractRetryPolicy(str, Enum):
    """校验失败后的处理策略。"""

    NONE = "none"
    RETRY_ONLY = "retry_only"
    RETRY_THEN_REPAIR = "retry_then_repair"
    FAIL_FAST = "fail_fast"


class AgentOutputContract(BaseModel):
    """单个输出面的契约定义。"""

    contract_id: str = Field(..., description="契约唯一标识")
    surface_name: str = Field(..., description="输出面名称")
    description: str = Field(default="", description="该输出面的说明")

    agent_type: Optional[AgentType] = Field(default=None, description="关联的 Agent 类型")
    scene: OutputContractScene = Field(..., description="输出场景")
    consumer: OutputContractConsumer = Field(..., description="消费方类型")
    mode: OutputContractMode = Field(..., description="输出模式")

    schema_name: str = Field(..., description="契约 schema 名称")
    schema_version: str = Field(default="1.0.0", description="契约 schema 版本")

    structured_fields: List[str] = Field(default_factory=list, description="必须稳定可识别的结构化字段")
    text_field: Optional[str] = Field(default=None, description="文本主体字段；仅 hybrid/text 使用")
    schema_ref: Optional[str] = Field(
        default=None,
        description="对应 Pydantic schema 的 dotted-path（如 'app.models.agent_output_schemas.EvaluatorChapterEndSchema'）",
    )
    retry_policy: OutputContractRetryPolicy = Field(
        default=OutputContractRetryPolicy.RETRY_THEN_REPAIR,
        description="结构校验失败后的处理策略",
    )

    def requires_structured_output(self) -> bool:
        return self.mode in {OutputContractMode.HYBRID, OutputContractMode.STRICT}

    def allows_text_output(self) -> bool:
        return self.mode in {OutputContractMode.TEXT, OutputContractMode.HYBRID}

    def resolve_schema(self) -> Optional[Type[BaseModel]]:
        """按 ``schema_ref`` 懒加载 import 对应的 Pydantic schema。

        在 ``agent_output_contract.py`` 直接 import schema 会引入循环依赖，
        因此使用 dotted-path + ``importlib.import_module`` 在调用时解析。
        """
        if not self.schema_ref:
            return None
        try:
            module_path, _, class_name = self.schema_ref.rpartition(".")
            if not module_path or not class_name:
                return None
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name, None)
            if cls is None or not isinstance(cls, type) or not issubclass(cls, BaseModel):
                return None
            return cls
        except Exception:
            return None


class AgentOutputContractRegistry(BaseModel):
    """输出契约注册表。"""

    contracts: List[AgentOutputContract] = Field(default_factory=list, description="契约列表")

    def get(self, contract_id: str) -> Optional[AgentOutputContract]:
        for contract in self.contracts:
            if contract.contract_id == contract_id:
                return contract
        return None

    def list_for_agent(self, agent_type: AgentType) -> List[AgentOutputContract]:
        return [contract for contract in self.contracts if contract.agent_type == agent_type]

    def find(
        self,
        *,
        surface_name: Optional[str] = None,
        agent_type: Optional[AgentType] = None,
        scene: Optional[OutputContractScene] = None,
        consumer: Optional[OutputContractConsumer] = None,
        mode: Optional[OutputContractMode] = None,
    ) -> List[AgentOutputContract]:
        results = self.contracts
        if surface_name is not None:
            results = [contract for contract in results if contract.surface_name == surface_name]
        if agent_type is not None:
            results = [contract for contract in results if contract.agent_type == agent_type]
        if scene is not None:
            results = [contract for contract in results if contract.scene == scene]
        if consumer is not None:
            results = [contract for contract in results if contract.consumer == consumer]
        if mode is not None:
            results = [contract for contract in results if contract.mode == mode]
        return results


DEFAULT_AGENT_OUTPUT_CONTRACTS: List[AgentOutputContract] = [
    AgentOutputContract(
        contract_id="workflow.node_definition",
        surface_name="workflow_node_definition",
        description="工作流编辑器中的节点定义、输入与输出配置。",
        scene=OutputContractScene.WORKFLOW_EDITOR,
        consumer=OutputContractConsumer.WORKFLOW_DEFINITION,
        mode=OutputContractMode.STRICT,
        schema_name="workflow.node_definition",
        structured_fields=["nodes", "nodes[].inputs", "nodes[].outputs"],
        retry_policy=OutputContractRetryPolicy.FAIL_FAST,
    ),
    AgentOutputContract(
        contract_id="workflow.execution_event",
        surface_name="workflow_execution_event",
        description="/director 和其他 runtime 消费的执行事件 envelope。",
        scene=OutputContractScene.WORKFLOW_RUNTIME,
        consumer=OutputContractConsumer.EXECUTION_EVENT,
        mode=OutputContractMode.STRICT,
        schema_name="workflow.execution_event",
        structured_fields=["type", "execution_id", "data"],
        retry_policy=OutputContractRetryPolicy.FAIL_FAST,
    ),
    AgentOutputContract(
        contract_id="workflow.node_output",
        surface_name="workflow_node_output",
        description="写入节点状态并供下游节点消费的输出 payload。",
        scene=OutputContractScene.WORKFLOW_RUNTIME,
        consumer=OutputContractConsumer.DOWNSTREAM_NODE,
        mode=OutputContractMode.STRICT,
        schema_name="workflow.node_output",
        structured_fields=["node_id", "output"],
        retry_policy=OutputContractRetryPolicy.FAIL_FAST,
    ),
    AgentOutputContract(
        contract_id="director.agent_stream_text",
        surface_name="director_agent_stream_text",
        description="/director 中 Agent 卡片展示的实时流式文本。",
        scene=OutputContractScene.WORKFLOW_RUNTIME,
        consumer=OutputContractConsumer.PROSE_ONLY,
        mode=OutputContractMode.TEXT,
        schema_name="director.agent_stream_text",
        text_field="text",
        retry_policy=OutputContractRetryPolicy.NONE,
    ),
    AgentOutputContract(
        contract_id="plot_outline.workflow_output",
        surface_name="plot_outline_workflow_output",
        description="章节大纲 Agent 在工作流中交付给后续节点的结构化结果。",
        agent_type=AgentType.PLOT_OUTLINE,
        scene=OutputContractScene.WORKFLOW_RUNTIME,
        consumer=OutputContractConsumer.DOWNSTREAM_NODE,
        mode=OutputContractMode.STRICT,
        schema_name="plot_outline.workflow_output",
        structured_fields=[
            "chapter_number",
            "chapter_title",
            "chapter_outline",
            "chapter_summary",
            "scene_directions",
            "chapter_goals",
        ],
        retry_policy=OutputContractRetryPolicy.RETRY_THEN_REPAIR,
    ),
    AgentOutputContract(
        contract_id="writer.workflow_output",
        surface_name="writer_workflow_output",
        description="作家 Agent 的正文输出以及供程序消费的元数据。",
        agent_type=AgentType.WRITER,
        scene=OutputContractScene.WORKFLOW_RUNTIME,
        consumer=OutputContractConsumer.DOWNSTREAM_NODE,
        mode=OutputContractMode.HYBRID,
        schema_name="writer.workflow_output",
        structured_fields=[
            "metadata",
            "word_count",
            "style_check",
            "hooks_embedded",
            "future_setup",
        ],
        text_field="chapter_content",
        retry_policy=OutputContractRetryPolicy.RETRY_THEN_REPAIR,
    ),
    AgentOutputContract(
        contract_id="setting.workflow_output",
        surface_name="setting_workflow_output",
        description="设定 Agent 在工作流中输出并供后续节点或保存逻辑消费的结构。",
        agent_type=AgentType.SETTING,
        scene=OutputContractScene.WORKFLOW_RUNTIME,
        consumer=OutputContractConsumer.DOWNSTREAM_NODE,
        mode=OutputContractMode.STRICT,
        schema_name="setting.workflow_output",
        structured_fields=["lores", "characters", "character_location_updates", "state_changes", "hooks", "change_request", "conflicts"],
        schema_ref="app.models.agent_output_schemas.SettingWorkflowOutputSchema",
        retry_policy=OutputContractRetryPolicy.RETRY_THEN_REPAIR,
    ),
    AgentOutputContract(
        contract_id="setting.chat_response",
        surface_name="setting_chat_response",
        description="设定 Agent 聊天/协商接口的返回包。",
        agent_type=AgentType.SETTING,
        scene=OutputContractScene.AGENT_CHAT,
        consumer=OutputContractConsumer.DTO_RESPONSE,
        mode=OutputContractMode.HYBRID,
        schema_name="setting.chat_response",
        structured_fields=["pending_lores", "pending_characters", "pending_hooks", "conflicts"],
        text_field="message",
        retry_policy=OutputContractRetryPolicy.RETRY_THEN_REPAIR,
    ),
    AgentOutputContract(
        contract_id="setting.persisted_objects",
        surface_name="setting_persisted_objects",
        description="设定 Agent 生成且需要保存的业务对象。",
        agent_type=AgentType.SETTING,
        scene=OutputContractScene.ROUTE_UI,
        consumer=OutputContractConsumer.PERSISTED_OBJECT,
        mode=OutputContractMode.STRICT,
        schema_name="setting.persisted_objects",
        structured_fields=["pending_lores", "pending_characters", "pending_hooks"],
        retry_policy=OutputContractRetryPolicy.RETRY_THEN_REPAIR,
    ),
    AgentOutputContract(
        contract_id="setting.change_request",
        surface_name="setting_change_request",
        description="设定变更请求与冲突检测结果。",
        agent_type=AgentType.SETTING,
        scene=OutputContractScene.ROUTE_UI,
        consumer=OutputContractConsumer.PERSISTED_OBJECT,
        mode=OutputContractMode.STRICT,
        schema_name="setting.change_request",
        structured_fields=["request", "has_conflicts", "conflicts"],
        retry_policy=OutputContractRetryPolicy.RETRY_THEN_REPAIR,
    ),
    AgentOutputContract(
        contract_id="evaluator.quality_checks_response",
        surface_name="quality_checks_response",
        description="质量检测类接口返回给前端和判定逻辑的固定结构。",
        agent_type=AgentType.EVALUATOR,
        scene=OutputContractScene.ROUTE_UI,
        consumer=OutputContractConsumer.DTO_RESPONSE,
        mode=OutputContractMode.STRICT,
        schema_name="evaluator.quality_checks.response",
        structured_fields=[
            "opening_analysis",
            "chapter_scores",
            "golden_rules",
            "reader_retention_prediction",
            "improvement_suggestions",
            "overall_score",
        ],
        retry_policy=OutputContractRetryPolicy.RETRY_THEN_REPAIR,
    ),
    AgentOutputContract(
        contract_id="villains.design_response",
        surface_name="villains_design_response",
        description="反派设计页面需要稳定消费的设计结果。",
        scene=OutputContractScene.ROUTE_UI,
        consumer=OutputContractConsumer.DTO_RESPONSE,
        mode=OutputContractMode.STRICT,
        schema_name="villains.design.response",
        structured_fields=["villain_design", "conflict_design", "defeat_timeline", "suggestions"],
        retry_policy=OutputContractRetryPolicy.RETRY_THEN_REPAIR,
    ),
    AgentOutputContract(
        contract_id="volumes.plan_response",
        surface_name="volumes_plan_response",
        description="卷规划页面需要稳定消费的规划结果。",
        scene=OutputContractScene.ROUTE_UI,
        consumer=OutputContractConsumer.DTO_RESPONSE,
        mode=OutputContractMode.STRICT,
        schema_name="volumes.plan.response",
        structured_fields=[
            "volume_info",
            "emotional_arc",
            "climax_design",
            "chapter_plan",
            "transitions",
            "word_distribution",
        ],
        retry_policy=OutputContractRetryPolicy.RETRY_THEN_REPAIR,
    ),
    AgentOutputContract(
        contract_id="chapter_outline.chat_response",
        surface_name="chapter_outline_chat_response",
        description="章节大纲 Agent 聊天界面的说明文字与结构化更新。",
        scene=OutputContractScene.ROUTE_UI,
        consumer=OutputContractConsumer.DTO_RESPONSE,
        mode=OutputContractMode.HYBRID,
        schema_name="chapter_outline.chat.response",
        structured_fields=[
            "outline_updates",
            "suggestions",
            "pending_outlines",
            "saved_outline",
            "saved_outlines",
        ],
        text_field="message",
        retry_policy=OutputContractRetryPolicy.RETRY_THEN_REPAIR,
    ),
    AgentOutputContract(
        contract_id="agent_config.prompt_preview",
        surface_name="agent_config_prompt_preview",
        description="Agent 配置预览生成的最终 prompt 文本。",
        scene=OutputContractScene.ROUTE_UI,
        consumer=OutputContractConsumer.PROSE_ONLY,
        mode=OutputContractMode.TEXT,
        schema_name="agent_config.prompt_preview",
        text_field="final_prompt",
        retry_policy=OutputContractRetryPolicy.NONE,
    ),
    AgentOutputContract(
        contract_id="writing_rule.prompt_preview",
        surface_name="writing_rule_prompt_preview",
        description="写作规则预览或最终 prompt 组装文本。",
        scene=OutputContractScene.ROUTE_UI,
        consumer=OutputContractConsumer.PROSE_ONLY,
        mode=OutputContractMode.TEXT,
        schema_name="writing_rule.prompt_preview",
        text_field="final_prompt",
        retry_policy=OutputContractRetryPolicy.NONE,
    ),
]


DEFAULT_AGENT_OUTPUT_CONTRACT_REGISTRY = AgentOutputContractRegistry(
    contracts=DEFAULT_AGENT_OUTPUT_CONTRACTS
)
