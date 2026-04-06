"""
Embedding 服务抽象层 - 支持 OpenAI / Sentence-Transformers / Ollama 三种模式
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)


class EmbeddingService(ABC):
    """Embedding 服务基类"""

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """将单条文本转换为向量"""
        pass

    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """将多条文本转换为向量列表"""
        pass

    @abstractmethod
    async def get_dimension(self) -> int:
        """获取向量维度"""
        pass

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """测试连接是否可用，返回 (success, message)"""
        pass


class OpenAIEmbeddingService(EmbeddingService):
    """OpenAI Embedding 服务（在线 API）"""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        dimension: int = 1536,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._dimension = dimension

    async def embed_text(self, text: str) -> List[float]:
        vectors = await self.embed_texts([text])
        return vectors[0] if vectors else []

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": texts,
                },
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]

    async def get_dimension(self) -> int:
        return self._dimension

    async def test_connection(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.model, "input": "test"},
                )
                if response.status_code == 200:
                    return True, "OpenAI 连接成功"
                else:
                    return False, f"API 返回错误：{response.status_code} - {response.text}"
        except Exception as e:
            return False, f"连接失败：{str(e)}"


class SentenceTransformersEmbeddingService(EmbeddingService):
    """Sentence-Transformers Embedding 服务（本地模型）"""

    _model_cache = {}

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        dimension: Optional[int] = None,
    ):
        self.model_name = model_name
        self._model = None
        self._dimension = dimension

    def _get_model(self):
        """懒加载模型"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            if self._dimension is None:
                self._dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    async def embed_text(self, text: str) -> List[float]:
        model = self._get_model()
        embedding = model.encode(text)
        return embedding.tolist()

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        embeddings = model.encode(texts)
        return [e.tolist() for e in embeddings]

    async def get_dimension(self) -> int:
        if self._dimension is None:
            self._get_model()
        return self._dimension

    async def test_connection(self) -> tuple[bool, str]:
        try:
            # 测试模型是否能正常加载和运行
            model = self._get_model()
            embedding = model.encode("test")
            return True, f"Sentence-Transformers 模型 '{self.model_name}' 加载成功（维度：{len(embedding)}）"
        except Exception as e:
            return False, f"模型加载失败：{str(e)}"


class OllamaEmbeddingService(EmbeddingService):
    """Ollama Embedding 服务（本地自部署）"""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        dimension: int = 768,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._dimension = dimension

    async def embed_text(self, text: str) -> List[float]:
        vectors = await self.embed_texts([text])
        return vectors[0] if vectors else []

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for text in texts:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text,
                    },
                )
                response.raise_for_status()
                data = response.json()
                embeddings.append(data["embedding"])
        return embeddings

    async def get_dimension(self) -> int:
        return self._dimension

    async def test_connection(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": "test"},
                )
                if response.status_code == 200:
                    embedding = response.json().get("embedding", [])
                    self._dimension = len(embedding)
                    return True, f"Ollama 连接成功（模型：{self.model}，维度：{len(embedding)}）"
                else:
                    return False, f"Ollama 返回错误：{response.status_code} - {response.text}"
        except Exception as e:
            return False, f"Ollama 连接失败：{str(e)}"


def create_embedding_service(
    provider: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
    dimension: int = 0,
) -> EmbeddingService:
    """
    工厂函数 - 根据配置创建对应的 Embedding 服务

    Args:
        provider: openai / sentence_transformers / ollama
        model: 模型名称
        api_key: API Key（仅 openai 需要）
        base_url: 基础 URL（ollama 需要）
        dimension: 向量维度

    Returns:
        EmbeddingService: embedding 服务实例
    """
    if provider == "openai":
        return OpenAIEmbeddingService(
            model=model,
            api_key=api_key or "",
            base_url=base_url or "https://api.openai.com/v1",
            dimension=dimension or 1536,
        )
    elif provider == "sentence_transformers":
        return SentenceTransformersEmbeddingService(
            model_name=model or "all-MiniLM-L6-v2",
            dimension=dimension if dimension > 0 else None,
        )
    elif provider == "ollama":
        return OllamaEmbeddingService(
            model=model or "nomic-embed-text",
            base_url=base_url or "http://localhost:11434",
            dimension=dimension or 768,
        )
    else:
        raise ValueError(f"不支持的 embedding provider: {provider}")
