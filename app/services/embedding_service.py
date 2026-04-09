"""
Embedding 服务抽象层 - 支持 OpenAI / Sentence-Transformers / Ollama 三种模式
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Callable

import httpx

logger = logging.getLogger(__name__)

# 全局下载进度状态
_download_progress = {
    "status": "idle",  # idle, downloading, completed, error
    "progress": 0,
    "message": "",
    "model": "",
}


def get_download_progress() -> dict:
    """获取当前下载进度"""
    return _download_progress.copy()


def set_download_progress(status: str, progress: int = 0, message: str = "", model: str = ""):
    """更新下载进度"""
    global _download_progress
    _download_progress = {
        "status": status,
        "progress": progress,
        "message": message,
        "model": model,
    }


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

    # 常见 OpenAI 模型的已知维度
    KNOWN_DIMENSIONS = {
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
    }

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._dimension = None

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
            embeddings = [item["embedding"] for item in data["data"]]
            # 动态获取维度
            if embeddings and self._dimension is None:
                self._dimension = len(embeddings[0])
            return embeddings

    async def get_dimension(self) -> int:
        # 优先使用已知维度
        if self._dimension is not None:
            return self._dimension
        if self.model in self.KNOWN_DIMENSIONS:
            return self.KNOWN_DIMENSIONS[self.model]
        # 回退到实测法
        await self.embed_text("test")
        return self._dimension or 1536

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
                    data = response.json()
                    embedding = data["data"][0]["embedding"]
                    self._dimension = len(embedding)
                    return True, f"OpenAI 连接成功（维度：{self._dimension}）"
                else:
                    return False, f"API 返回错误：{response.status_code} - {response.text}"
        except Exception as e:
            return False, f"连接失败：{str(e)}"


class SentenceTransformersEmbeddingService(EmbeddingService):
    """Sentence-Transformers Embedding 服务（本地模型）"""

    _model_cache = {}
    # 常见模型的已知维度（用于快速返回，无需加载模型）
    KNOWN_DIMENSIONS = {
        "all-MiniLM-L6-v2": 384,
        "all-MiniLM-L12-v2": 384,
        "all-mpnet-base-v2": 768,
        "paraphrase-multilingual-MiniLM-L12-v2": 384,
        "paraphrase-MiniLM-L6-v2": 384,
        "bge-small-en-v1.5": 384,
        "bge-base-en-v1.5": 768,
        "bge-large-en-v1.5": 1024,
        "e5-small-v2": 384,
        "e5-base-v2": 768,
        "e5-large-v2": 1024,
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
    }

    @staticmethod
    def is_model_cached(model_name: str, cache_folder: Optional[str] = None) -> bool:
        """检查模型是否已在本地缓存

        Args:
            model_name: 模型名称
            cache_folder: 模型缓存路径（可选）

        Returns:
            bool: 模型是否已缓存
        """
        import os

        cache_paths = []
        if cache_folder:
            cache_paths.append(cache_folder)

        default_cache = os.path.expanduser("~/.cache/huggingface/hub")
        cache_paths.append(default_cache)

        for cache_path in cache_paths:
            model_dir_patterns = [
                os.path.join(cache_path, f"models--sentence-transformers--{model_name}"),
                os.path.join(cache_path, f"models--{model_name.replace('/', '--')}"),
                os.path.join(cache_path, model_name),
            ]

            for model_dir in model_dir_patterns:
                if os.path.exists(model_dir):
                    # 检查是否有必要的模型文件
                    # 至少要有 config.json 或者 pytorch_model.bin / model.safetensors
                    config_path = os.path.join(model_dir, "config.json")
                    has_model_file = any(
                        os.path.exists(os.path.join(model_dir, f))
                        for f in ["pytorch_model.bin", "model.safetensors", "pytorch_model.bin.index"]
                    ) or os.path.exists(os.path.join(model_dir, "snapshots"))

                    if os.path.exists(config_path) or has_model_file:
                        return True

                    # 检查 snapshots 目录（HuggingFace Hub 格式）
                    snapshots_dir = os.path.join(model_dir, "snapshots")
                    if os.path.exists(snapshots_dir):
                        snapshots = os.listdir(snapshots_dir)
                        if snapshots:
                            return True

        return False

    @staticmethod
    def get_known_dimension(model_name: str, cache_folder: Optional[str] = None) -> Optional[int]:
        """静态方法：快速获取维度（无需实例化服务，无需加载模型）

        Args:
            model_name: 模型名称
            cache_folder: 模型缓存路径（可选）

        Returns:
            int | None: 维度，如果无法确定则返回 None
        """
        # 1. 检查已知维度
        if model_name in SentenceTransformersEmbeddingService.KNOWN_DIMENSIONS:
            return SentenceTransformersEmbeddingService.KNOWN_DIMENSIONS[model_name]

        # 2. 尝试从配置文件读取
        import json
        import os

        cache_paths = []
        if cache_folder:
            cache_paths.append(cache_folder)

        default_cache = os.path.expanduser("~/.cache/huggingface/hub")
        cache_paths.append(default_cache)

        for cache_path in cache_paths:
            model_dir_patterns = [
                os.path.join(cache_path, f"models--sentence-transformers--{model_name}"),
                os.path.join(cache_path, f"models--{model_name.replace('/', '--')}"),
                os.path.join(cache_path, model_name),
            ]

            for model_dir in model_dir_patterns:
                if not os.path.exists(model_dir):
                    continue

                # 1_Pooling/config.json
                pooling_config = os.path.join(model_dir, "1_Pooling", "config.json")
                if os.path.exists(pooling_config):
                    try:
                        with open(pooling_config, "r") as f:
                            config = json.load(f)
                            if "word_embedding_dimension" in config:
                                return config["word_embedding_dimension"]
                    except Exception:
                        pass

                # config.json
                config_path = os.path.join(model_dir, "config.json")
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r") as f:
                            config = json.load(f)
                            if "hidden_size" in config:
                                return config["hidden_size"]
                    except Exception:
                        pass

        return None

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_folder: Optional[str] = None,
    ):
        self.model_name = model_name
        self.cache_folder = cache_folder  # 自定义模型存储路径
        self._model = None
        self._dimension = None
        self._is_cached = None  # 缓存检查结果

    def _get_dimension_from_config(self) -> Optional[int]:
        """方法二：从配置文件读取维度（轻量级，无需加载模型）"""
        import json
        import os

        # 1. 首先检查已知维度
        if self.model_name in self.KNOWN_DIMENSIONS:
            return self.KNOWN_DIMENSIONS[self.model_name]

        # 2. 尝试从本地缓存读取配置文件
        cache_paths = []
        if self.cache_folder:
            cache_paths.append(self.cache_folder)

        # 默认 HuggingFace 缓存路径
        default_cache = os.path.expanduser("~/.cache/huggingface/hub")
        cache_paths.append(default_cache)

        for cache_path in cache_paths:
            # 查找模型目录
            model_dir_patterns = [
                os.path.join(cache_path, f"models--sentence-transformers--{self.model_name}"),
                os.path.join(cache_path, f"models--{self.model_name.replace('/', '--')}"),
                os.path.join(cache_path, self.model_name),
            ]

            for model_dir in model_dir_patterns:
                if not os.path.exists(model_dir):
                    continue

                # 尝试读取 1_Pooling/config.json (Sentence-Transformers 特有)
                pooling_config = os.path.join(model_dir, "1_Pooling", "config.json")
                if os.path.exists(pooling_config):
                    try:
                        with open(pooling_config, "r") as f:
                            config = json.load(f)
                            if "word_embedding_dimension" in config:
                                return config["word_embedding_dimension"]
                    except Exception:
                        pass

                # 尝试读取 config.json (标准 Transformer 配置)
                config_path = os.path.join(model_dir, "config.json")
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r") as f:
                            config = json.load(f)
                            if "hidden_size" in config:
                                return config["hidden_size"]
                    except Exception:
                        pass

        return None

    def _download_progress_callback(self, progress: float, desc: str = ""):
        """下载进度回调"""
        percent = int(progress * 100)
        set_download_progress(
            status="downloading",
            progress=percent,
            message=desc or f"下载中... {percent}%",
            model=self.model_name
        )

    def _get_model(self):
        """懒加载模型"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                import os

                # 设置 HuggingFace 缓存环境变量，避免网络请求
                if self.cache_folder:
                    os.makedirs(self.cache_folder, exist_ok=True)
                    os.environ['HF_HOME'] = self.cache_folder
                    os.environ['TRANSFORMERS_CACHE'] = self.cache_folder
                    os.environ['HF_HUB_CACHE'] = self.cache_folder

                # 先检查模型是否已在本地缓存
                is_cached = self.is_model_cached(self.model_name, self.cache_folder)

                if is_cached:
                    # 模型已缓存，直接加载，不触发下载进度
                    logger.info(f"模型 '{self.model_name}' 已在本地缓存，直接加载")
                    set_download_progress("completed", 100, f"模型已缓存，正在加载...", self.model_name)
                else:
                    # 模型未缓存，显示下载进度
                    logger.info(f"模型 '{self.model_name}' 未缓存，开始下载")
                    set_download_progress("downloading", 0, "检查模型...", self.model_name)

                # 加载模型
                if not is_cached:
                    set_download_progress("downloading", 10, "加载模型...", self.model_name)

                # 构建模型名称（sentence-transformers 格式）
                model_id = f"sentence-transformers/{self.model_name}" if "/" not in self.model_name else self.model_name

                if self.cache_folder:
                    self._model = SentenceTransformer(
                        model_id,
                        cache_folder=self.cache_folder,
                        local_files_only=is_cached  # 仅在已缓存时禁用网络请求
                    )
                else:
                    self._model = SentenceTransformer(
                        model_id,
                        local_files_only=is_cached
                    )

                self._dimension = self._model.get_sentence_embedding_dimension()
                set_download_progress("completed", 100, f"模型加载完成，维度：{self._dimension}", self.model_name)

            except Exception as e:
                set_download_progress("error", 0, f"加载失败: {str(e)}", self.model_name)
                raise

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
        """获取向量维度

        优先使用方法二（读取配置文件），失败时使用方法一（实测法）
        """
        if self._dimension is not None:
            return self._dimension

        # 方法二：尝试从配置文件读取（轻量级）
        dimension = self._get_dimension_from_config()
        if dimension is not None:
            self._dimension = dimension
            return dimension

        # 方法一：实测法（需要加载模型）
        self._get_model()
        return self._dimension or 384

    async def test_connection(self) -> tuple[bool, str]:
        try:
            # 先检查模型是否已缓存
            is_cached = self.is_model_cached(self.model_name, self.cache_folder)

            # 测试模型是否能正常加载和运行
            model = self._get_model()
            embedding = model.encode("test")
            dimension = len(embedding)

            if is_cached:
                return True, f"模型 '{self.model_name}' 已缓存，加载成功（维度：{dimension}）"
            else:
                return True, f"模型 '{self.model_name}' 下载完成，加载成功（维度：{dimension}）"
        except Exception as e:
            return False, f"模型加载失败：{str(e)}"


class OllamaEmbeddingService(EmbeddingService):
    """Ollama Embedding 服务（本地自部署）"""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._dimension = None

    async def embed_text(self, text: str) -> List[float]:
        vectors = await self.embed_texts([text])
        return vectors[0] if vectors else []

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        # trust_env=False 避免 httpx 使用系统代理导致本地连接失败
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
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
        # 动态获取维度
        if embeddings and self._dimension is None:
            self._dimension = len(embeddings[0])
        return embeddings

    async def get_dimension(self) -> int:
        if self._dimension is None:
            await self.embed_text("test")
        return self._dimension or 768

    async def test_connection(self) -> tuple[bool, str]:
        try:
            # trust_env=False 避免 httpx 使用系统代理导致本地连接失败
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": "test"},
                )
                if response.status_code == 200:
                    embedding = response.json().get("embedding", [])
                    self._dimension = len(embedding)
                    return True, f"Ollama 连接成功（维度：{self._dimension}）"
                else:
                    return False, f"Ollama 返回错误：{response.status_code} - {response.text}"
        except Exception as e:
            return False, f"Ollama 连接失败：{str(e)}"


def create_embedding_service(
    provider: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
) -> EmbeddingService:
    """
    工厂函数 - 根据配置创建对应的 Embedding 服务

    Args:
        provider: openai / sentence_transformers / ollama
        model: 模型名称
        api_key: API Key（仅 openai 需要）
        base_url: 基础 URL（ollama 需要）或模型存储路径（sentence_transformers）

    Returns:
        EmbeddingService: embedding 服务实例
    """
    if provider == "openai":
        return OpenAIEmbeddingService(
            model=model,
            api_key=api_key or "",
            base_url=base_url or "https://api.openai.com/v1",
        )
    elif provider == "sentence_transformers":
        # base_url 作为自定义模型存储路径
        return SentenceTransformersEmbeddingService(
            model_name=model or "all-MiniLM-L6-v2",
            cache_folder=base_url if base_url else None,
        )
    elif provider == "ollama":
        return OllamaEmbeddingService(
            model=model or "nomic-embed-text",
            base_url=base_url or "http://localhost:11434",
        )
    else:
        raise ValueError(f"不支持的 embedding provider: {provider}")
