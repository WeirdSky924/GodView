"""
NebulaGraph 数据库操作层
负责存储人物关系、记忆关联、伏笔追踪等图结构数据
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config
from nebula3.data.DataObject import Value, ValueWrapper

logger = logging.getLogger(__name__)


class NebulaGraphDatabase:
    """NebulaGraph 数据库操作类"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9669,
        user: str = "root",
        password: str = "nebula",
        space_name: str = "godview_space",
        timeout_ms: int = 10000,
    ):
        """
        初始化 NebulaGraph 连接

        Args:
            host: 主机地址
            port: 端口
            user: 用户名
            password: 密码
            space_name: 图空间名称
            timeout_ms: 超时时间 (毫秒)
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.space_name = space_name
        self.timeout_ms = timeout_ms

        self._pool: Optional[ConnectionPool] = None
        self._session_pool = None
        self._connected = False

    async def connect(self):
        """建立数据库连接"""
        if not self._connected:
            config = Config()
            config.max_connection_pool_size = 20
            config.timeout = self.timeout_ms

            self._pool = ConnectionPool()
            init_result = self._pool.init([(self.host, self.port)], config)

            if not init_result:
                raise ConnectionError(f"无法连接到 NebulaGraph: {self.host}:{self.port}")

            # 认证并创建会话
            session = self._pool.get_session(self.user, self.password)
            self._session_pool = session

            # 确保空间存在
            await self._ensure_space()

            self._connected = True
            logger.info(f"NebulaGraph 连接成功：{self.host}:{self.port}")

    async def disconnect(self):
        """关闭数据库连接"""
        if self._session_pool:
            self._session_pool.release()
            self._session_pool = None
        if self._pool:
            self._pool.close()
            self._pool = None
        self._connected = False
        logger.info("NebulaGraph 连接已关闭")

    async def _ensure_space(self):
        """确保图空间存在"""
        # 检查空间是否存在
        result = self._session_pool.execute(
            f"SHOW SPACES LIKE '{self.space_name}'"
        )

        if result.is_succeeded() and len(result.data.rows()) == 0:
            # 创建空间
            create_space = f"""
            CREATE SPACE IF NOT EXISTS {self.space_name} (
                vid_type = FIXED_STRING(64),
                partition_num = 10,
                replica_factor = 1
            )
            """
            result = self._session_pool.execute(create_space)
            if result.is_succeeded():
                logger.info(f"图空间 '{self.space_name}' 创建成功")
            else:
                logger.error(f"图空间创建失败：{result.error_msg()}")

        # 使用空间
        result = self._session_pool.execute(f"USE {self.space_name}")
        if not result.is_succeeded():
            logger.error(f"使用图空间失败：{result.error_msg()}")

    async def init_schema(self):
        """初始化图 schema（Tag 和 Edge）"""
        await self.connect()

        # 创建 Tag
        tags = [
            # 角色
            """
            CREATE TAG IF NOT EXISTS character (
                name STRING,
                description STRING,
                role STRING,
                status STRING,
                personality_traits STRING,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """,
            # 世界
            """
            CREATE TAG IF NOT EXISTS world (
                name STRING,
                world_type STRING,
                description STRING,
                created_at TIMESTAMP
            )
            """,
            # 区域
            """
            CREATE TAG IF NOT EXISTS region (
                name STRING,
                region_type STRING,
                description STRING,
                world_id STRING
            )
            """,
            # 伏笔
            """
            CREATE TAG IF NOT EXISTS hook (
                title STRING,
                hook_type STRING,
                status STRING,
                priority INT,
                created_at TIMESTAMP
            )
            """,
            # 事件
            """
            CREATE TAG IF NOT EXISTS event (
                summary STRING,
                event_type STRING,
                timestamp TIMESTAMP
            )
            """,
            # 记忆
            """
            CREATE TAG IF NOT EXISTS memory (
                content STRING,
                memory_type STRING,
                importance FLOAT,
                created_at TIMESTAMP
            )
            """,
        ]

        for tag_sql in tags:
            result = self._session_pool.execute(tag_sql)
            if result.is_succeeded():
                logger.info(f"Tag 创建成功：{tag_sql.split()[2]}")
            else:
                logger.warning(f"Tag 可能已存在：{result.error_msg()}")

        # 创建 Edge
        edges = [
            # 角色关系
            """
            CREATE EDGE IF NOT EXISTS knows (
                relationship_type STRING,
                strength FLOAT,
                since TIMESTAMP
            )
            """,
            # 角色在区域
            """
            CREATE EDGE IF NOT EXISTS located_in (
                since TIMESTAMP
            )
            """,
            # 角色属于世界
            """
            CREATE EDGE IF NOT EXISTS belongs_to (
                since TIMESTAMP
            )
            """,
            # 区域连接
            """
            CREATE EDGE IF NOT EXISTS connects_to (
                distance FLOAT
            )
            """,
            # 伏笔关联角色
            """
            CREATE EDGE IF NOT EXISTS involves_character (
                role STRING
            )
            """,
            # 伏笔关联区域
            """
            CREATE EDGE IF NOT EXISTS involves_location (
                context STRING
            )
            """,
            # 记忆归属
            """
            CREATE EDGE IF NOT EXISTS remembers (
                created_at TIMESTAMP
            )
            """,
            # 事件参与
            """
            CREATE EDGE IF NOT EXISTS participated_in (
                role STRING
            )
            """,
        ]

        for edge_sql in edges:
            result = self._session_pool.execute(edge_sql)
            if result.is_succeeded():
                logger.info(f"Edge 创建成功：{edge_sql.split()[2]}")
            else:
                logger.warning(f"Edge 可能已存在：{result.error_msg()}")

        logger.info("NebulaGraph Schema 初始化完成")

    # ==================== 角色相关操作 ====================

    async def insert_character(self, character_id: str, properties: Dict[str, Any]) -> bool:
        """
        插入角色节点

        Args:
            character_id: 角色 ID
            properties: 属性字典

        Returns:
            bool: 是否成功
        """
        # 处理时间字段
        now = datetime.utcnow().isoformat()
        props = {
            "name": f"'{properties.get('name', '')}'",
            "description": f"'{properties.get('description', '')}'",
            "role": f"'{properties.get('role', 'supporting')}'",
            "status": f"'{properties.get('status', 'active')}'",
            "personality_traits": f"'{properties.get('personality_traits', '[]')}'",
            "created_at": f"'{properties.get('created_at', now)}'",
            "updated_at": f"'{now}'",
        }

        props_str = ", ".join([f"{k}: {v}" for k, v in props.items()])

        query = f"""
        INSERT VERTEX IF NOT EXISTS character ({props_str})
        VALUES "{character_id}": ({props_str})
        """

        result = self._session_pool.execute(query)
        return result.is_succeeded()

    async def get_character(self, character_id: str) -> Optional[Dict[str, Any]]:
        """获取角色信息"""
        query = f"""
        FETCH PROP ON character("{character_id}")
        YIELD vertex AS v
        """
        result = self._session_pool.execute(query)

        if result.is_succeeded() and result.data.rows():
            return self._parse_vertex(result.data.rows()[0])
        return None

    async def get_character_neighbors(
        self,
        character_id: str,
        depth: int = 1,
        edge_types: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取角色的邻居节点

        Args:
            character_id: 角色 ID
            depth: 遍历深度
            edge_types: 边类型过滤

        Returns:
            Dict: 邻居节点列表
        """
        edge_filter = ""
        if edge_types:
            edge_filter = ", ".join([f":{e}" for e in edge_types])

        query = f"""
        GO {depth} STEPS FROM "{character_id}"{edge_filter}
        YIELD vertices AS vertices, edges AS edges
        """

        result = self._session_pool.execute(query)
        if not result.is_succeeded():
            return {"vertices": [], "edges": []}

        return self._parse_path(result.data)

    # ==================== 关系相关操作 ====================

    async def create_relationship(
        self,
        character_id_1: str,
        character_id_2: str,
        relationship_type: str,
        strength: float = 0.0,
    ) -> bool:
        """
        创建角色关系

        Args:
            character_id_1: 角色 1 ID
            character_id_2: 角色 2 ID
            relationship_type: 关系类型
            strength: 关系强度

        Returns:
            bool: 是否成功
        """
        now = datetime.utcnow().isoformat()

        query = f"""
        INSERT EDGE IF NOT EXISTS knows (relationship_type, strength, since)
        VALUES "{character_id_1}" -> "{character_id_2}": ("{relationship_type}", {strength}, "{now}")
        """

        result = self._session_pool.execute(query)
        return result.is_succeeded()

    async def get_relationships(
        self, character_id: str
    ) -> List[Dict[str, Any]]:
        """获取角色的所有关系"""
        query = f"""
        GO FROM "{character_id}" OVER knows
        YIELD $$.character.name AS target_name, knows.relationship_type AS type,
              knows.strength AS strength, knows.since AS since
        """

        result = self._session_pool.execute(query)
        if not result.is_succeeded():
            return []

        relationships = []
        for row in result.data.rows():
            relationships.append({
                "target_name": str(row.values[0]),
                "type": str(row.values[1]),
                "strength": float(row.values[2]) if row.values[2].is_double() else 0.0,
                "since": str(row.values[3]),
            })

        return relationships

    # ==================== 记忆相关操作 ====================

    async def add_memory(
        self,
        character_id: str,
        content: str,
        memory_type: str = "experience",
        importance: float = 0.5,
    ) -> bool:
        """
        添加角色记忆

        Args:
            character_id: 角色 ID
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要程度

        Returns:
            bool: 是否成功
        """
        now = datetime.utcnow().isoformat()
        memory_id = f"mem_{character_id}_{int(datetime.utcnow().timestamp())}"

        # 插入记忆节点
        insert_memory = f"""
        INSERT VERTEX IF NOT EXISTS memory (content, memory_type, importance, created_at)
        VALUES "{memory_id}": ("{content}", "{memory_type}", {importance}, "{now}")
        """

        result = self._session_pool.execute(insert_memory)
        if not result.is_succeeded():
            return False

        # 创建关系
        link_query = f"""
        INSERT EDGE IF NOT EXISTS remembers (created_at)
        VALUES "{character_id}" -> "{memory_id}": ("{now}")
        """

        result = self._session_pool.execute(link_query)
        return result.is_succeeded()

    async def get_memories(
        self,
        character_id: str,
        limit: int = 10,
        min_importance: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        获取角色记忆

        Args:
            character_id: 角色 ID
            limit: 返回数量
            min_importance: 最小重要性

        Returns:
            List: 记忆列表
        """
        query = f"""
        GO FROM "{character_id}" OVER remembers
        WHERE $$.memory.importance >= {min_importance}
        YIELD $$.memory.content AS content, $$.memory.memory_type AS type,
              $$.memory.importance AS importance
        LIMIT {limit}
        """

        result = self._session_pool.execute(query)
        if not result.is_succeeded():
            return []

        memories = []
        for row in result.data.rows():
            memories.append({
                "content": str(row.values[0]),
                "type": str(row.values[1]),
                "importance": float(row.values[2]) if row.values[2].is_double() else 0.0,
            })

        return memories

    # ==================== 伏笔追踪相关操作 ====================

    async def create_hook(
        self,
        hook_id: str,
        title: str,
        hook_type: str = "custom",
        priority: int = 1,
    ) -> bool:
        """创建伏笔节点"""
        now = datetime.utcnow().isoformat()

        query = f"""
        INSERT VERTEX IF NOT EXISTS hook (title, hook_type, status, priority, created_at)
        VALUES "{hook_id}": ("{title}", "{hook_type}", "planted", {priority}, "{now}")
        """

        result = self._session_pool.execute(query)
        return result.is_succeeded()

    async def link_hook_to_character(
        self, hook_id: str, character_id: str, role: str = "involved"
    ) -> bool:
        """将伏笔关联到角色"""
        query = f"""
        INSERT EDGE IF NOT EXISTS involves_character (role)
        VALUES "{hook_id}" -> "{character_id}": ("{role}")
        """

        result = self._session_pool.execute(query)
        return result.is_succeeded()

    async def link_hook_to_location(
        self, hook_id: str, region_id: str, context: str = ""
    ) -> bool:
        """将伏笔关联到地点"""
        query = f"""
        INSERT EDGE IF NOT EXISTS involves_location (context)
        VALUES "{hook_id}" -> "{region_id}": ("{context}")
        """

        result = self._session_pool.execute(query)
        return result.is_succeeded()

    async def get_hook_connections(self, hook_id: str) -> Dict[str, List[str]]:
        """获取伏笔的所有关联"""
        query = f"""
        GO 1 STEPS FROM "{hook_id}"
        YIELD step, type AS edge_type, dstid AS destination
        """

        result = self._session_pool.execute(query)
        if not result.is_succeeded():
            return {"characters": [], "locations": []}

        connections = {"characters": [], "locations": []}
        for row in result.data.rows():
            edge_type = str(row.values[1])
            dest = str(row.values[2])
            if edge_type == "involves_character":
                connections["characters"].append(dest)
            elif edge_type == "involves_location":
                connections["locations"].append(dest)

        return connections

    # ==================== 工具方法 ====================

    def _parse_vertex(self, row) -> Dict[str, Any]:
        """解析顶点数据"""
        result = {}
        # 简化解析，实际使用需要根据具体数据结构
        return result

    def _parse_path(self, data) -> Dict[str, List]:
        """解析路径数据"""
        return {"vertices": [], "edges": []}

    async def query(self, query_string: str) -> Dict[str, Any]:
        """
        执行自定义 nGQL 查询

        Args:
            query_string: nGQL 查询语句

        Returns:
            Dict: 查询结果
        """
        result = self._session_pool.execute(query_string)
        return {
            "success": result.is_succeeded(),
            "error": result.error_msg() if not result.is_succeeded() else None,
            "data": self._parse_result(result.data) if result.is_succeeded() else None,
        }

    def _parse_result(self, data) -> List[Dict[str, Any]]:
        """解析查询结果"""
        if not data or not data.rows():
            return []

        columns = data.column_names
        rows = data.rows()

        result = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row.values[i]
                row_dict[col] = self._value_to_python(value)
            result.append(row_dict)

        return result

    def _value_to_python(self, value: Value) -> Any:
        """将 Nebula Value 转换为 Python 类型"""
        if value.is_null():
            return None
        elif value.is_bool():
            return value.as_bool()
        elif value.is_int():
            return value.as_int()
        elif value.is_float():
            return value.as_double()
        elif value.is_string():
            return value.as_string()
        elif value.is_list():
            return [self._value_to_python(v) for v in value.get_list()]
        elif value.is_map():
            return {k: self._value_to_python(v) for k, v in value.get_map().items()}
        else:
            return str(value)
