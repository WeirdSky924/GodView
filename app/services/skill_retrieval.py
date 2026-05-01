# -*- coding: utf-8 -*-
"""
Skill 智能检索服务
实现 Embedding 检索 + LLM 决策的两阶段混合架构

架构流程：
1. Embedding 粗筛：从大量 Skill 中检索 Top-K 相关候选
2. LLM 精决：让 LLM 从候选中选择最合适的并提取参数

适用场景：
- Skill 数量庞大时（数百甚至上千个）
- 需要语义理解而非简单关键词匹配
- 同义词、近义词场景的智能匹配
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.models.skill import Skill, SkillLoadMode

logger = logging.getLogger(__name__)


@dataclass
class SkillCandidate:
    """Skill 候选项"""
    skill: Skill
    similarity_score: float  # Embedding 相似度分数 (0-1)
    match_reason: Optional[str] = None  # LLM 判断的匹配原因


@dataclass
class SkillDecision:
    """LLM 对 Skill 的决策结果"""
    skill_id: str
    skill_name: str
    should_activate: bool
    confidence: float  # LLM 置信度 (0-1)
    parameters: Dict[str, Any]  # 提取的调用参数
    reason: str  # 决策理由


@dataclass
class RetrievalResult:
    """检索结果"""
    candidates: List[SkillCandidate]  # 候选列表
    decisions: List[SkillDecision]  # LLM 决策结果
    final_skills: List[Tuple[Skill, Dict[str, Any]]]  # 最终激活的 Skill 及参数


class SkillEmbeddingService:
    """
    Skill Embedding 服务

    负责：
    - 为 Skill 生成 embedding 向量
    - 存储和检索 embedding
    - 向量相似度计算
    """

    def __init__(self, embedding_provider: str = "openai"):
        """
        Args:
            embedding_provider: embedding 提供者 (openai, local, etc.)
        """
        self.embedding_provider = embedding_provider
        self._embedding_cache: Dict[str, List[float]] = {}
        self._embedding_dimension = 1536  # OpenAI text-embedding-3-small

    async def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的 embedding 向量

        Args:
            text: 输入文本

        Returns:
            List[float]: embedding 向量
        """
        # 检查缓存
        cache_key = text[:200]  # 截取前200字符作为缓存键
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        try:
            if self.embedding_provider == "openai":
                embedding = await self._get_openai_embedding(text)
            elif self.embedding_provider == "local":
                embedding = await self._get_local_embedding(text)
            else:
                # 回退到简单实现
                embedding = self._get_simple_embedding(text)

            # 缓存结果
            self._embedding_cache[cache_key] = embedding
            return embedding

        except Exception as e:
            logger.warning(f"获取 embedding 失败: {e}，使用简单实现")
            return self._get_simple_embedding(text)

    async def _get_openai_embedding(self, text: str) -> List[float]:
        """使用 OpenAI API 获取 embedding"""
        try:
            import openai

            response = await openai.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return response.data[0].embedding

        except ImportError:
            raise RuntimeError("openai 库未安装")
        except Exception as e:
            raise RuntimeError(f"OpenAI API 调用失败: {e}")

    async def _get_local_embedding(self, text: str) -> List[float]:
        """使用本地模型获取 embedding"""
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            embedding = model.encode(text)
            return embedding.tolist()

        except ImportError:
            raise RuntimeError("sentence-transformers 库未安装")
        except Exception as e:
            raise RuntimeError(f"本地模型推理失败: {e}")

    def _get_simple_embedding(self, text: str) -> List[float]:
        """
        简单的 embedding 实现（用于测试或无外部服务时）
        基于字符频率的简单向量化
        """
        import hashlib

        # 使用哈希生成伪向量（仅用于测试）
        text_hash = hashlib.sha256(text.encode()).digest()

        # 生成固定维度的向量
        dimension = self._embedding_dimension
        embedding = []
        for i in range(dimension):
            # 使用哈希字节循环填充
            byte_val = text_hash[i % len(text_hash)]
            # 归一化到 [-1, 1]
            embedding.append((byte_val / 128.0) - 1.0)

        return embedding

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        计算两个向量的余弦相似度

        Args:
            vec1: 向量1
            vec2: 向量2

        Returns:
            float: 相似度 (0-1)
        """
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        # 归一化到 [0, 1]
        return (similarity + 1) / 2

    def build_skill_text(self, skill: Skill) -> str:
        """
        构建 Skill 的 embedding 文本
        将关键信息组合成一段文本用于向量化

        Args:
            skill: Skill 对象

        Returns:
            str: 组合文本
        """
        parts = []

        # 名称和描述
        parts.append(f"技能名称：{skill.name}")
        if skill.description:
            parts.append(f"描述：{skill.description}")

        # 触发关键词
        if skill.trigger_keywords:
            parts.append(f"触发关键词：{', '.join(skill.trigger_keywords)}")

        # 触发场景
        if skill.trigger_scenes:
            parts.append(f"适用场景：{', '.join(skill.trigger_scenes)}")

        # 分类信息
        parts.append(f"类型：{skill.skill_type.value}")
        parts.append(f"分类：{skill.category.value}")

        # 参数说明
        if skill.parameters:
            param_desc = []
            for p in skill.parameters:
                param_desc.append(f"{p.name}({p.type}): {p.description}")
            parts.append(f"参数：{'; '.join(param_desc)}")

        return "\n".join(parts)


class SkillRetrievalService:
    """
    Skill 智能检索服务

    两阶段检索：
    1. Embedding 粗筛：向量相似度检索 Top-K
    2. LLM 精决：让 LLM 从候选中选择并提取参数
    """

    def __init__(
        self,
        skill_service=None,
        embedding_service: Optional[SkillEmbeddingService] = None,
        llm_client=None,
    ):
        """
        Args:
            skill_service: Skill 服务实例
            embedding_service: Embedding 服务实例
            llm_client: LLM 客户端实例
        """
        self.skill_service = skill_service
        self.embedding_service = embedding_service or SkillEmbeddingService()
        self.llm_client = llm_client

        # Skill embedding 缓存
        self._skill_embeddings: Dict[str, List[float]] = {}

    async def build_skill_embeddings(self, skills: List[Skill]) -> None:
        """
        为 Skill 列表构建 embedding 缓存

        Args:
            skills: Skill 列表
        """
        for skill in skills:
            if skill.id not in self._skill_embeddings:
                text = self.embedding_service.build_skill_text(skill)
                self._skill_embeddings[skill.id] = await self.embedding_service.get_embedding(text)

        logger.info(f"构建 {len(skills)} 个 Skill 的 embedding 缓存")

    async def retrieve_skills(
        self,
        query: str,
        agent_type: str,
        top_k: int = 5,
        min_similarity: float = 0.3,
        scenario: Optional[str] = None,
    ) -> RetrievalResult:
        """
        两阶段 Skill 检索

        Args:
            query: 查询文本（场景描述、用户指令等）
            agent_type: Agent 类型（用于过滤已分配的 Skills）
            top_k: 返回候选数量
            min_similarity: 最小相似度阈值
            scenario: Agent 使用场景

        Returns:
            RetrievalResult: 检索结果
        """
        # 1. 获取 Agent 可用的 Skills（仅已分配到插槽的）
        available_skills = await self._get_available_skills(agent_type, scenario)

        if not available_skills:
            logger.warning(f"Agent {agent_type} 没有可用的 Skills")
            return RetrievalResult([], [], [])

        # 分离核心层和按需层
        core_skills = [s for s in available_skills if s.load_mode == SkillLoadMode.CORE]
        on_demand_skills = [s for s in available_skills if s.load_mode == SkillLoadMode.ON_DEMAND]

        # 核心层 Skills 始终包含
        final_skills: List[Tuple[Skill, Dict[str, Any]]] = [(s, {}) for s in core_skills]

        # 2. Embedding 粗筛：对按需层 Skills 进行检索
        if on_demand_skills:
            # 确保 embedding 缓存存在
            await self.build_skill_embeddings(on_demand_skills)

            # 获取查询 embedding
            query_embedding = await self.embedding_service.get_embedding(query)

            # 计算相似度并排序
            candidates: List[SkillCandidate] = []
            for skill in on_demand_skills:
                skill_embedding = self._skill_embeddings.get(skill.id)
                if skill_embedding:
                    similarity = self.embedding_service.cosine_similarity(
                        query_embedding, skill_embedding
                    )
                    if similarity >= min_similarity:
                        candidates.append(SkillCandidate(
                            skill=skill,
                            similarity_score=similarity,
                        ))

            # 按相似度降序排序，取 Top-K
            candidates.sort(key=lambda x: -x.similarity_score)
            candidates = candidates[:top_k]

            logger.info(
                f"Embedding 粗筛: {len(on_demand_skills)} 个按需 Skill -> "
                f"{len(candidates)} 个候选 (阈值={min_similarity})"
            )

            # 3. LLM 精决：从候选中选择并提取参数
            if candidates:
                decisions = await self._llm_decision(query, candidates)

                # 根据 LLM 决策构建最终结果
                for decision in decisions:
                    if decision.should_activate:
                        skill = next((c.skill for c in candidates if c.skill.id == decision.skill_id), None)
                        if skill:
                            final_skills.append((skill, decision.parameters))
                            logger.info(
                                f"LLM 激活 Skill: {skill.name} "
                                f"(置信度={decision.confidence:.2f}, 参数={decision.parameters})"
                            )

                return RetrievalResult(candidates, decisions, final_skills)
            else:
                logger.info("Embedding 粗筛无候选，跳过 LLM 决策")

        return RetrievalResult([], [], final_skills)

    async def _get_available_skills(self, agent_type: str, scenario: Optional[str] = None) -> List[Skill]:
        """获取 Agent 可用的 Skills（仅插槽绑定的）"""
        if not self.skill_service:
            return []

        try:
            assigned = await self.skill_service.get_assigned_skills_for_agent(agent_type, scenario)
            return [skill for skill, _ in assigned]
        except Exception as e:
            logger.error(f"获取 Agent Skills 失败: {e}")
            return []

    async def _llm_decision(
        self,
        query: str,
        candidates: List[SkillCandidate],
    ) -> List[SkillDecision]:
        """
        LLM 决策阶段：从候选中选择并提取参数

        Args:
            query: 查询文本
            candidates: 候选 Skill 列表

        Returns:
            List[SkillDecision]: LLM 决策结果
        """
        if not candidates:
            return []

        # 如果没有 LLM 客户端，使用简单规则
        if not self.llm_client:
            return self._simple_decision(query, candidates)

        # 构建 LLM Prompt
        prompt = self._build_decision_prompt(query, candidates)

        try:
            # 调用 LLM
            response = await self._call_llm(prompt)

            # 解析响应
            decisions = self._parse_llm_response(response, candidates)

            return decisions

        except Exception as e:
            logger.error(f"LLM 决策失败: {e}，回退到简单规则")
            return self._simple_decision(query, candidates)

    def _build_decision_prompt(
        self,
        query: str,
        candidates: List[SkillCandidate],
    ) -> str:
        """构建 LLM 决策 Prompt"""
        candidate_info = []
        for i, c in enumerate(candidates):
            skill = c.skill
            params_info = ""
            if skill.parameters:
                params = []
                for p in skill.parameters:
                    params.append(f"  - {p.name} ({p.type}): {p.description}")
                    if p.default is not None:
                        params[-1] += f" [默认: {p.default}]"
                    if p.required:
                        params[-1] += " [必填]"
                params_info = "\n".join(params)

            param_block = f"- 参数:\n{params_info}" if params_info else ""
            candidate_info.append(f"""
### 候选 {i + 1}: {skill.name}
- ID: {skill.id}
- 描述: {skill.description}
- 相似度: {c.similarity_score:.2f}
- 类型: {skill.skill_type.value}
- 分类: {skill.category.value}
{param_block}
""")

        prompt = f"""你是一个智能技能选择系统。根据用户的场景描述，从候选技能中选择最合适的技能并提取调用参数。

## 用户场景描述
{query}

## 候选技能列表
{''.join(candidate_info)}

## 你的任务
1. 分析用户场景，判断哪些技能应该被激活
2. 对于需要激活的技能，提取必要的调用参数
3. 输出 JSON 格式的决策结果

## 输出格式
请输出一个 JSON 数组，每个元素包含：
- skill_id: 技能ID
- should_activate: 是否激活 (true/false)
- confidence: 置信度 (0.0-1.0)
- parameters: 调用参数对象 {{}}
- reason: 决策理由（简短说明）

## 输出示例
```json
[
  {{
    "skill_id": "skill_combat_scene",
    "should_activate": true,
    "confidence": 0.9,
    "parameters": {{}},
    "reason": "场景涉及战斗对抗"
  }},
  {{
    "skill_id": "skill_romance_scene",
    "should_activate": false,
    "confidence": 0.3,
    "parameters": {{}},
    "reason": "场景中没有恋爱元素"
  }}
]
```

请直接输出 JSON，不要包含其他内容："""

        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if not self.llm_client:
            raise RuntimeError("LLM 客户端未配置")

        # 根据客户端类型调用
        if hasattr(self.llm_client, 'chat'):
            # LangChain 或类似接口
            response = await self.llm_client.chat(prompt)
            return response
        elif hasattr(self.llm_client, 'ainvoke'):
            # LangChain Runnable 接口
            response = await self.llm_client.ainvoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        elif hasattr(self.llm_client, 'messages'):
            # OpenAI 接口
            response = await self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return response.choices[0].message.content
        else:
            raise RuntimeError("不支持的 LLM 客户端类型")

    def _parse_llm_response(
        self,
        response: str,
        candidates: List[SkillCandidate],
    ) -> List[SkillDecision]:
        """解析 LLM 响应"""
        try:
            # 提取 JSON 部分
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start == -1 or json_end == 0:
                raise ValueError("响应中未找到 JSON 数组")

            json_str = response[json_start:json_end]
            data = json.loads(json_str)

            decisions = []
            for item in data:
                skill_id = item.get('skill_id')
                skill = next((c.skill for c in candidates if c.skill.id == skill_id), None)
                if skill:
                    decisions.append(SkillDecision(
                        skill_id=skill_id,
                        skill_name=skill.name,
                        should_activate=item.get('should_activate', False),
                        confidence=min(1.0, max(0.0, item.get('confidence', 0.5))),
                        parameters=item.get('parameters', {}),
                        reason=item.get('reason', ''),
                    ))

            return decisions

        except json.JSONDecodeError as e:
            logger.error(f"解析 LLM 响应失败: {e}")
            return []
        except Exception as e:
            logger.error(f"处理 LLM 响应失败: {e}")
            return []

    def _simple_decision(
        self,
        query: str,
        candidates: List[SkillCandidate],
    ) -> List[SkillDecision]:
        """
        简单决策规则（无 LLM 时的回退）
        基于相似度阈值决定是否激活
        """
        decisions = []
        for candidate in candidates:
            # 相似度 > 0.5 则激活
            should_activate = candidate.similarity_score > 0.5

            decisions.append(SkillDecision(
                skill_id=candidate.skill.id,
                skill_name=candidate.skill.name,
                should_activate=should_activate,
                confidence=candidate.similarity_score,
                parameters={},
                reason=f"相似度={candidate.similarity_score:.2f}",
            ))

        return decisions

    def clear_embedding_cache(self):
        """清除 embedding 缓存"""
        self._skill_embeddings.clear()
        self.embedding_service._embedding_cache.clear()


# 全局单例
_skill_retrieval_service: Optional[SkillRetrievalService] = None


def get_skill_retrieval_service(
    skill_service=None,
    llm_client=None,
) -> SkillRetrievalService:
    """获取 SkillRetrievalService 单例"""
    global _skill_retrieval_service
    if _skill_retrieval_service is None:
        _skill_retrieval_service = SkillRetrievalService(
            skill_service=skill_service,
            llm_client=llm_client,
        )
    return _skill_retrieval_service


def set_skill_retrieval_service(service: SkillRetrievalService):
    """设置 SkillRetrievalService 实例"""
    global _skill_retrieval_service
    _skill_retrieval_service = service
