"""
大纲数据模型
GodView v4 新增：管理小说大纲文本的输入、处理和检索
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """大纲来源类型"""

    PASTED_TEXT = "pasted_text"  # 粘贴文本
    FILE_TXT = "file_txt"  # .txt 文件
    FILE_MD = "file_md"  # .md 文件


class OutlineChunk(BaseModel):
    """大纲文本分块

    用于长文本的分块处理和向量检索
    """

    id: str = Field(..., description="分块ID")
    content: str = Field(..., description="内容")
    chunk_index: int = Field(..., description="分块索引")
    start_char: int = Field(..., description="起始字符位置")
    end_char: int = Field(..., description="结束字符位置")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="分块元数据")


class OutlineSource(BaseModel):
    """大纲来源模型

    存储原始大纲文本和处理后的信息
    """

    id: str = Field(..., description="大纲源ID")
    project_id: str = Field(..., description="项目ID")
    session_id: Optional[str] = Field(None, description="关联的Bootstrap会话ID")

    # 来源信息
    source_type: SourceType = Field(default=SourceType.PASTED_TEXT, description="来源类型")

    # 内容
    original_content: str = Field(..., description="原始内容")
    processed_content: Optional[str] = Field(None, description="处理后的内容")

    # 分块信息
    chunks: List[OutlineChunk] = Field(default_factory=list, description="文本分块")
    chunk_size: int = Field(default=1000, description="分块大小（字符数）")
    chunk_overlap: int = Field(default=200, description="分块重叠（字符数）")

    # 向量检索
    embedding_ready: bool = Field(default=False, description="是否已生成向量")
    embedding_model: Optional[str] = Field(None, description="使用的嵌入模型")

    # 元数据
    file_name: Optional[str] = Field(None, description="文件名（如果来自文件）")
    file_size: Optional[int] = Field(None, description="文件大小（字节）")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 扩展元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="大纲元数据")


class OutlineAnalysisResult(BaseModel):
    """大纲分析结果"""

    outline_source_id: str = Field(..., description="大纲源ID")

    # 提取的关键元素
    characters: List[Dict[str, Any]] = Field(default_factory=list, description="提取的角色")
    locations: List[Dict[str, Any]] = Field(default_factory=list, description="提取的地点")
    events: List[Dict[str, Any]] = Field(default_factory=list, description="提取的事件")
    themes: List[str] = Field(default_factory=list, description="提取的主题")

    # 分析指标
    character_count: int = Field(default=0, description="角色数量")
    location_count: int = Field(default=0, description="地点数量")
    event_count: int = Field(default=0, description="事件数量")
    word_count: int = Field(default=0, description="总词数")

    # 质量评估
    coherence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="连贯性评分")
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0, description="完整性评分")

    # 分析元数据
    analysis_method: str = Field(default="llm_extraction", description="分析方法")
    analysis_timestamp: datetime = Field(default_factory=datetime.now)


class OutlineChunkWithSimilarity(OutlineChunk):
    """带相似度分数的大纲分块"""

    similarity_score: float = Field(..., ge=0.0, le=1.0, description="相似度分数")


class OutlineQueryRequest(BaseModel):
    """大纲查询请求"""

    query_text: str = Field(..., description="查询文本")
    outline_source_id: str = Field(..., description="大纲源ID")
    limit: int = Field(default=5, ge=1, le=50, description="返回结果数量")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="相似度阈值")