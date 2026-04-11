"""
AI 协作者模式
v5.3 功能：AI 作为协作者参与创作过程
"""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

from app.models.world import World
from app.models.character import Character
from app.services.model_router import create_llm
from app.services.token_tracker import token_tracker
from app.models.token_usage import UsageCategory

logger = logging.getLogger(__name__)


class CollaborationRole(str, Enum):
    """协作角色枚举"""
    IDEA_GENERATOR = "idea_generator"  # 创意生成者
    CRITIC = "critic"  # 批评家
    PLOT_ADVISOR = "plot_advisor"  # 剧情顾问
    CHARACTER_CONSULTANT = "character_consultant"  # 角色顾问
    WORLD_BUILDER = "world_builder"  # 世界构建者
    DIALOGUE_WRITER = "dialogue_writer"  # 对话写手


class CollaborationRequest:
    """协作请求"""

    def __init__(
        self,
        request_type: str,
        context: Dict[str, Any],
        role: CollaborationRole,
        priority: int = 1,
    ):
        self.id = f"collab_{uuid.uuid4().hex[:12]}"
        self.request_type = request_type
        self.context = context
        self.role = role
        self.priority = priority
        self.created_at = datetime.utcnow()
        self.status = "pending"  # pending, processing, completed, failed
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None


class CollaboratorSystem:
    """AI 协作者系统"""

    def __init__(self, model_factory: Optional[Callable] = None):
        self.model_factory = model_factory or create_llm
        self.collaboration_history: List[Dict[str, Any]] = []
        self.active_collaborations: Dict[str, CollaborationRequest] = {}
        self.role_profiles = self._initialize_role_profiles()

        logger.info("AI 协作者系统初始化完成")

    def _initialize_role_profiles(self) -> Dict[CollaborationRole, Dict[str, Any]]:
        """初始化角色配置文件"""

        return {
            CollaborationRole.IDEA_GENERATOR: {
                "name": "创意生成者",
                "description": "擅长提出新颖创意和故事点子",
                "system_prompt": """你是一个创意生成者，擅长提出新颖、有趣的故事创意。
                你的任务是基于给定的上下文，提出有创意、可执行的故事点子。
                请提供具体、详细、有启发性的建议。""",
                "strengths": ["创意发散", "联想能力", "创新思维"],
            },
            CollaborationRole.CRITIC: {
                "name": "批评家",
                "description": "擅长发现问题和提出改进建议",
                "system_prompt": """你是一个严谨的批评家，擅长分析故事中的问题并提出改进建议。
                你的任务是客观分析故事的质量，指出优缺点，并提出具体的改进方案。
                请保持建设性、具体的批评态度。""",
                "strengths": ["分析能力", "问题识别", "改进建议"],
            },
            CollaborationRole.PLOT_ADVISOR: {
                "name": "剧情顾问",
                "description": "擅长设计剧情结构和节奏",
                "system_prompt": """你是一个经验丰富的剧情顾问，擅长设计剧情结构和节奏。
                你的任务是分析剧情发展，提出结构优化建议，确保故事有良好的起承转合。
                请关注剧情的连贯性、张力和节奏感。""",
                "strengths": ["结构设计", "节奏控制", "张力构建"],
            },
            CollaborationRole.CHARACTER_CONSULTANT: {
                "name": "角色顾问",
                "description": "擅长角色设计和成长弧线",
                "system_prompt": """你是一个专业的角色顾问，擅长角色设计和成长弧线规划。
                你的任务是分析角色设定，提出角色发展建议，确保角色行为一致且有深度。
                请关注角色的动机、成长和内在一致性。""",
                "strengths": ["角色设计", "动机分析", "成长规划"],
            },
            CollaborationRole.WORLD_BUILDER: {
                "name": "世界构建者",
                "description": "擅长世界观设定和规则设计",
                "system_prompt": """你是一个世界构建专家，擅长世界观设定和规则设计。
                你的任务是分析世界设定，提出完善建议，确保世界观自洽且有深度。
                请关注世界的逻辑性、一致性和趣味性。""",
                "strengths": ["世界观构建", "规则设计", "细节完善"],
            },
            CollaborationRole.DIALOGUE_WRITER: {
                "name": "对话写手",
                "description": "擅长编写符合角色特点的对话",
                "system_prompt": """你是一个专业的对话写手，擅长编写符合角色特点的对话。
                你的任务是分析角色设定，编写自然、生动、符合角色特点的对话。
                请关注对话的口语化、角色特点和情感表达。""",
                "strengths": ["对话创作", "角色声音", "情感表达"],
            },
        }

    async def request_collaboration(
        self,
        request_type: str,
        context: Dict[str, Any],
        role: CollaborationRole,
        priority: int = 1,
    ) -> CollaborationRequest:
        """请求协作"""

        request = CollaborationRequest(
            request_type=request_type,
            context=context,
            role=role,
            priority=priority,
        )

        self.active_collaborations[request.id] = request
        logger.info(f"创建协作请求: {request.id} - {role} - {request_type}")

        # 异步处理请求
        import asyncio
        asyncio.create_task(self._process_collaboration(request))

        return request

    async def _process_collaboration(self, request: CollaborationRequest):
        """处理协作请求"""

        request.status = "processing"

        try:
            role_profile = self.role_profiles[request.role]

            # 准备提示词
            prompt = self._prepare_prompt(request, role_profile)

            # 调用模型
            model = self.model_factory()
            response = await model.ainvoke(prompt)

            # 记录 token 使用量
            await self._record_token_usage(request, prompt, response)

            # 解析响应
            result = self._parse_response(response, request.request_type)

            request.status = "completed"
            request.result = result

            # 记录历史
            self.collaboration_history.append({
                "id": request.id,
                "role": request.role,
                "request_type": request.request_type,
                "context": request.context,
                "result": result,
                "created_at": request.created_at,
                "completed_at": datetime.utcnow(),
            })

            # 从活跃列表中移除
            self.active_collaborations.pop(request.id, None)

            logger.info(f"协作请求处理完成: {request.id}")

        except Exception as e:
            request.status = "failed"
            request.error = str(e)
            logger.error(f"协作请求处理失败: {request.id} - {e}")

    async def _record_token_usage(self, request: CollaborationRequest, prompt: List[Dict], response: Any):
        """记录 token 使用量"""
        try:
            # 获取 project_id（从上下文中获取）
            project_id = request.context.get("project_id")
            if not project_id:
                return

            # 计算输入 token（估算）
            input_text = " ".join([msg.get("content", "") for msg in prompt])
            input_tokens = len(input_text) // 4

            # 计算输出 token
            output_text = ""
            if hasattr(response, "content"):
                output_text = response.content
            elif isinstance(response, dict):
                output_text = response.get("content", "")
            elif isinstance(response, str):
                output_text = response
            output_tokens = len(output_text) // 4

            # 尝试从响应中获取实际 token 使用量
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens = response.usage_metadata.get('input_tokens', input_tokens)
                output_tokens = response.usage_metadata.get('output_tokens', output_tokens)
            elif hasattr(response, 'response_metadata') and response.response_metadata:
                token_usage = response.response_metadata.get('token_usage', {})
                if token_usage:
                    input_tokens = token_usage.get('prompt_tokens', input_tokens)
                    output_tokens = token_usage.get('completion_tokens', output_tokens)

            # 确定 category
            category = UsageCategory.DIRECTOR
            if request.role == CollaborationRole.CHARACTER_CONSULTANT:
                category = UsageCategory.CHARACTER
            elif request.role == CollaborationRole.WORLD_BUILDER:
                category = UsageCategory.WORLD
            elif request.role == CollaborationRole.PLOT_ADVISOR:
                category = UsageCategory.PLOT
            elif request.role == CollaborationRole.DIALOGUE_WRITER:
                category = UsageCategory.CHAPTER

            await token_tracker.record_usage(
                project_id=project_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider="unknown",
                model="collaborator",
                category=category,
                agent_name=f"Collaborator-{request.role.value}",
                metadata={"request_type": request.request_type},
            )
        except Exception as e:
            logger.warning(f"记录协作 token 使用失败: {e}")

    def _prepare_prompt(self, request: CollaborationRequest, role_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """准备提示词"""

        system_prompt = role_profile["system_prompt"]
        context = request.context
        request_type = request.request_type

        # 构建用户消息
        user_message = f"""协作请求类型：{request_type}

上下文信息：
{self._format_context(context)}

请根据你的角色"{role_profile['name']}"的特点，提供专业的协作建议。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    def _format_context(self, context: Dict[str, Any]) -> str:
        """格式化上下文信息"""

        formatted = []

        if "world" in context:
            world = context["world"]
            if isinstance(world, World):
                formatted.append(f"世界：{world.name}")
                formatted.append(f"描述：{world.description}")
                formatted.append(f"类型：{world.world_type}")
            elif isinstance(world, dict):
                formatted.append(f"世界：{world.get('name', '未命名')}")
                if "description" in world:
                    formatted.append(f"描述：{world['description']}")

        if "characters" in context:
            characters = context["characters"]
            formatted.append("\n角色列表：")
            for i, char in enumerate(characters[:5]):  # 限制数量
                if isinstance(char, Character):
                    formatted.append(f"  {i + 1}. {char.name} - {char.role}")
                elif isinstance(char, dict):
                    formatted.append(f"  {i + 1}. {char.get('name', '未命名')} - {char.get('role', '未指定')}")

        if "plot" in context:
            plot = context["plot"]
            formatted.append(f"\n剧情：{plot}")

        if "current_issue" in context:
            issue = context["current_issue"]
            formatted.append(f"\n当前问题：{issue}")

        if "specific_question" in context:
            question = context["specific_question"]
            formatted.append(f"\n具体问题：{question}")

        return "\n".join(formatted)

    def _parse_response(self, response: Any, request_type: str) -> Dict[str, Any]:
        """解析模型响应"""

        # 提取文本内容
        content = ""
        if hasattr(response, "content"):
            content = response.content
        elif isinstance(response, dict):
            content = response.get("content", "")
        elif isinstance(response, str):
            content = response

        # 根据请求类型结构化结果
        result = {
            "raw_response": content,
            "parsed_suggestions": [],
            "key_points": [],
            "actionable_items": [],
        }

        # 尝试提取结构化信息
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测建议
            if line.startswith(("建议：", "建议:", "建议 ", "•", "-", "✓")):
                suggestion = line.lstrip("•-✓建议：: ").strip()
                if suggestion:
                    result["parsed_suggestions"].append(suggestion)

            # 检测关键点
            if line.startswith(("关键：", "关键:", "关键点：", "关键点:", "要点：")):
                point = line.lstrip("关键：:点要").strip()
                if point:
                    result["key_points"].append(point)

            # 检测可执行项
            if line.startswith(("行动：", "行动:", "执行：", "执行:", "TODO：")):
                action = line.lstrip("行动：:执行：:TODO").strip()
                if action:
                    result["actionable_items"].append(action)

        # 如果没有提取到结构化信息，尝试其他方法
        if not result["parsed_suggestions"]:
            # 按句子分割
            sentences = [s.strip() for s in content.split("。") if s.strip()]
            result["parsed_suggestions"] = sentences[:5]  # 取前5句作为建议

        return result

    async def get_collaboration_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """获取协作请求状态"""

        if request_id in self.active_collaborations:
            request = self.active_collaborations[request_id]
            return {
                "id": request.id,
                "status": request.status,
                "role": request.role,
                "request_type": request.request_type,
                "created_at": request.created_at,
            }

        # 在历史中查找
        for record in self.collaboration_history:
            if record["id"] == request_id:
                return {
                    "id": record["id"],
                    "status": "completed",
                    "role": record["role"],
                    "request_type": record["request_type"],
                    "created_at": record["created_at"],
                    "completed_at": record.get("completed_at"),
                    "result": record.get("result"),
                }

        return None

    async def get_active_collaborations(self) -> List[Dict[str, Any]]:
        """获取活跃的协作请求"""

        return [
            {
                "id": req.id,
                "role": req.role,
                "request_type": req.request_type,
                "status": req.status,
                "created_at": req.created_at,
            }
            for req in self.active_collaborations.values()
        ]

    async def get_collaboration_history(
        self,
        role: Optional[CollaborationRole] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取协作历史"""

        history = self.collaboration_history

        if role:
            history = [record for record in history if record["role"] == role]

        return history[:limit]

    async def request_multiple_collaborations(
        self,
        request_type: str,
        context: Dict[str, Any],
        roles: List[CollaborationRole],
    ) -> Dict[str, Any]:
        """请求多个角色的协作"""

        requests = []
        for role in roles:
            request = await self.request_collaboration(
                request_type=request_type,
                context=context,
                role=role,
            )
            requests.append(request.id)

        return {
            "request_ids": requests,
            "roles": [role.value for role in roles],
            "total_requests": len(requests),
        }

    async def compare_collaboration_advice(
        self,
        request_type: str,
        context: Dict[str, Any],
        roles: List[CollaborationRole],
    ) -> Dict[str, Any]:
        """比较不同角色的协作建议"""

        # 请求多个角色的协作
        requests_result = await self.request_multiple_collaborations(
            request_type=request_type,
            context=context,
            roles=roles,
        )

        # 等待所有请求完成（简化处理，实际应该使用更复杂的等待逻辑）
        import asyncio
        await asyncio.sleep(2)  # 简化的等待

        # 收集结果
        results = {}
        for request_id in requests_result["request_ids"]:
            status = await self.get_collaboration_status(request_id)
            if status and status.get("status") == "completed":
                role = status["role"]
                results[role.value] = {
                    "advice": status.get("result", {}).get("parsed_suggestions", []),
                    "key_points": status.get("result", {}).get("key_points", []),
                    "raw_response": status.get("result", {}).get("raw_response", ""),
                }

        return {
            "comparison": results,
            "summary": self._generate_comparison_summary(results),
        }

    def _generate_comparison_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """生成比较摘要"""

        if not results:
            return {"message": "无结果可比较"}

        # 收集所有建议
        all_suggestions = []
        for role, data in results.items():
            for suggestion in data.get("advice", []):
                all_suggestions.append({
                    "role": role,
                    "suggestion": suggestion,
                })

        # 寻找共同主题（简化版）
        common_themes = []
        if len(all_suggestions) >= 2:
            # 简单的关键词匹配
            words = {}
            for item in all_suggestions:
                for word in item["suggestion"].split():
                    if len(word) > 2:  # 过滤短词
                        words[word] = words.get(word, 0) + 1

            # 找出高频词
            for word, count in words.items():
                if count >= len(results) - 1:  # 大多数角色都提到的词
                    common_themes.append(word)

        return {
            "total_suggestions": len(all_suggestions),
            "common_themes": common_themes[:5],  # 取前5个
            "role_count": len(results),
        }

    async def provide_feedback_on_collaboration(
        self,
        request_id: str,
        feedback: str,
        rating: int = 5,  # 1-5分
    ) -> Dict[str, Any]:
        """对协作结果提供反馈"""

        # 查找协作记录
        for record in self.collaboration_history:
            if record["id"] == request_id:
                record["feedback"] = feedback
                record["rating"] = rating
                record["feedback_at"] = datetime.utcnow()

                logger.info(f"协作反馈已记录: {request_id} - 评分: {rating}")

                return {
                    "request_id": request_id,
                    "feedback_recorded": True,
                    "rating": rating,
                }

        return {
            "request_id": request_id,
            "feedback_recorded": False,
            "error": "协作记录未找到",
        }