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

    async def init_lore_schema(self):
        """
        初始化 Lore（设定）相关的图 Schema

        用于存储世界设定之间的层级关系和约束关系
        """
        await self.connect()

        # Lore Tags - 按类别分组的设定节点
        lore_tags = [
            # 世界规则
            """
            CREATE TAG IF NOT EXISTS lore_world_rule (
                title STRING,
                content STRING,
                priority STRING,
                keywords STRING,
                constraints STRING,
                project_id STRING,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """,
            # 地理设定
            """
            CREATE TAG IF NOT EXISTS lore_geography (
                title STRING,
                content STRING,
                priority STRING,
                keywords STRING,
                location_type STRING,
                parent_location STRING,
                project_id STRING,
                created_at TIMESTAMP
            )
            """,
            # 势力/组织
            """
            CREATE TAG IF NOT EXISTS lore_faction (
                title STRING,
                content STRING,
                priority STRING,
                keywords STRING,
                faction_type STRING,
                power_level STRING,
                project_id STRING,
                created_at TIMESTAMP
            )
            """,
            # 种族
            """
            CREATE TAG IF NOT EXISTS lore_race (
                title STRING,
                content STRING,
                priority STRING,
                keywords STRING,
                traits STRING,
                project_id STRING,
                created_at TIMESTAMP
            )
            """,
            # 物品
            """
            CREATE TAG IF NOT EXISTS lore_item (
                title STRING,
                content STRING,
                priority STRING,
                keywords STRING,
                item_type STRING,
                rarity STRING,
                project_id STRING,
                created_at TIMESTAMP
            )
            """,
        ]

        for tag_sql in lore_tags:
            result = self._session_pool.execute(tag_sql)
            if result.is_succeeded():
                tag_name = tag_sql.split()[5]  # 提取 Tag 名称
                logger.info(f"Lore Tag 创建成功：{tag_name}")
            else:
                logger.warning(f"Lore Tag 可能已存在：{result.error_msg()}")

        # Lore Edges - 设定之间的关系
        lore_edges = [
            # 父子关系（层级结构）
            """
            CREATE EDGE IF NOT EXISTS lore_parent_of (
                relationship_type STRING,
                created_at TIMESTAMP
            )
            """,
            # 相互关联
            """
            CREATE EDGE IF NOT EXISTS lore_related_to (
                relationship_strength FLOAT,
                description STRING,
                created_at TIMESTAMP
            )
            """,
            # 约束关系
            """
            CREATE EDGE IF NOT EXISTS lore_constrains (
                constraint_type STRING,
                constraint_value STRING,
                created_at TIMESTAMP
            )
            """,
        ]

        for edge_sql in lore_edges:
            result = self._session_pool.execute(edge_sql)
            if result.is_succeeded():
                edge_name = edge_sql.split()[5]
                logger.info(f"Lore Edge 创建成功：{edge_name}")
            else:
                logger.warning(f"Lore Edge 可能已存在：{result.error_msg()}")

        logger.info("NebulaGraph Lore Schema 初始化完成")

    async def init_narrative_schema(self):
        """
        初始化 Narrative（叙事）相关的图 Schema

        用于追踪故事进展、角色状态变化和事件因果关系
        """
        await self.connect()

        # Narrative Tags
        narrative_tags = [
            # 叙事事件
            """
            CREATE TAG IF NOT EXISTS narrative_event (
                event_id STRING,
                event_type STRING,
                summary STRING,
                chapter INT,
                scene INT,
                timestamp STRING,
                importance FLOAT,
                project_id STRING,
                created_at TIMESTAMP
            )
            """,
            # 状态变化
            """
            CREATE TAG IF NOT EXISTS narrative_state_change (
                change_id STRING,
                entity_type STRING,
                entity_id STRING,
                attribute STRING,
                old_value STRING,
                new_value STRING,
                reason STRING,
                project_id STRING,
                created_at TIMESTAMP
            )
            """,
            # 关系变化
            """
            CREATE TAG IF NOT EXISTS narrative_relationship_change (
                change_id STRING,
                character1_id STRING,
                character2_id STRING,
                relationship_type STRING,
                old_strength FLOAT,
                new_strength FLOAT,
                reason STRING,
                project_id STRING,
                created_at TIMESTAMP
            )
            """,
        ]

        for tag_sql in narrative_tags:
            result = self._session_pool.execute(tag_sql)
            if result.is_succeeded():
                tag_name = tag_sql.split()[5]
                logger.info(f"Narrative Tag 创建成功：{tag_name}")
            else:
                logger.warning(f"Narrative Tag 可能已存在：{result.error_msg()}")

        # Narrative Edges
        narrative_edges = [
            # 因果关系
            """
            CREATE EDGE IF NOT EXISTS causes (
                causality_strength FLOAT,
                description STRING
            )
            """,
            # 参与事件
            """
            CREATE EDGE IF NOT EXISTS participates_in (
                role STRING,
                involvement_level STRING
            )
            """,
            # 发生地点
            """
            CREATE EDGE IF NOT EXISTS occurs_at (
                location_name STRING
            )
            """,
            # 引用设定
            """
            CREATE EDGE IF NOT EXISTS references_lore (
                reference_type STRING,
                relevance FLOAT
            )
            """,
        ]

        for edge_sql in narrative_edges:
            result = self._session_pool.execute(edge_sql)
            if result.is_succeeded():
                edge_name = edge_sql.split()[5]
                logger.info(f"Narrative Edge 创建成功：{edge_name}")
            else:
                logger.warning(f"Narrative Edge 可能已存在：{result.error_msg()}")

        logger.info("NebulaGraph Narrative Schema 初始化完成")

    # ==================== Lore 图操作 ====================

    async def add_lore_node(
        self,
        lore_id: str,
        category: str,
        properties: Dict[str, Any],
    ) -> bool:
        """
        添加设定节点到图数据库

        Args:
            lore_id: 设定 ID
            category: 设定类别 (world_rule, geography, faction, race, item)
            properties: 节点属性

        Returns:
            bool: 是否成功
        """
        tag_map = {
            "world_rule": "lore_world_rule",
            "geography": "lore_geography",
            "faction": "lore_faction",
            "race": "lore_race",
            "item": "lore_item",
        }

        tag_name = tag_map.get(category, "lore_world_rule")
        now = datetime.utcnow().isoformat()

        # 构建属性字符串
        props = []
        for key, value in properties.items():
            if isinstance(value, str):
                # 转义单引号
                escaped_value = value.replace("'", "\\'")
                props.append(f'{key}: "{escaped_value}"')
            elif isinstance(value, (int, float)):
                props.append(f"{key}: {value}")
            elif isinstance(value, list):
                props.append(f'{key}: "{str(value)}"')

        props.append(f'created_at: "{now}"')
        props_str = ", ".join(props)

        query = f"""
        INSERT VERTEX IF NOT EXISTS {tag_name} ({props_str})
        VALUES "{lore_id}": ({props_str})
        """

        result = self._session_pool.execute(query)
        return result.is_succeeded()

    async def create_lore_relationship(
        self,
        lore_id_1: str,
        lore_id_2: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        创建设定之间的关系

        Args:
            lore_id_1: 设定 1 ID
            lore_id_2: 设定 2 ID
            relationship_type: 关系类型 (parent_of, related_to, constrains)
            properties: 边属性

        Returns:
            bool: 是否成功
        """
        edge_map = {
            "parent_of": "lore_parent_of",
            "related_to": "lore_related_to",
            "constrains": "lore_constrains",
        }

        edge_name = edge_map.get(relationship_type, "lore_related_to")
        now = datetime.utcnow().isoformat()

        if properties:
            props_str = ", ".join([
                f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}"
                for k, v in properties.items()
            ])
            props_str += f', created_at: "{now}"'
        else:
            props_str = f'created_at: "{now}"'

        query = f"""
        INSERT EDGE IF NOT EXISTS {edge_name} ({props_str})
        VALUES "{lore_id_1}" -> "{lore_id_2}": ({props_str})
        """

        result = self._session_pool.execute(query)
        return result.is_succeeded()

    async def get_lore_tree(
        self,
        root_lore_id: str,
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        """
        获取设定的层级树结构

        Args:
            root_lore_id: 根设定 ID
            max_depth: 最大遍历深度

        Returns:
            Dict: 树结构数据
        """
        query = f"""
        GO {max_depth} STEPS FROM "{root_lore_id}" OVER lore_parent_of, lore_related_to
        YIELD vertices AS v, edges AS e
        """

        result = self._session_pool.execute(query)
        if not result.is_succeeded():
            return {"nodes": [], "edges": []}

        return self._parse_path(result.data)

    # ==================== Narrative 图操作 ====================

    async def add_narrative_event_node(
        self,
        event_id: str,
        properties: Dict[str, Any],
    ) -> bool:
        """
        添加叙事事件节点

        Args:
            event_id: 事件 ID
            properties: 节点属性

        Returns:
            bool: 是否成功
        """
        now = datetime.utcnow().isoformat()

        props = []
        for key, value in properties.items():
            if isinstance(value, str):
                escaped_value = value.replace("'", "\\'")
                props.append(f'{key}: "{escaped_value}"')
            elif isinstance(value, (int, float)):
                props.append(f"{key}: {value}")

        props.append(f'created_at: "{now}"')
        props_str = ", ".join(props)

        query = f"""
        INSERT VERTEX IF NOT EXISTS narrative_event ({props_str})
        VALUES "{event_id}": ({props_str})
        """

        result = self._session_pool.execute(query)
        return result.is_succeeded()

    async def link_event_causality(
        self,
        cause_event_id: str,
        effect_event_id: str,
        strength: float = 1.0,
        description: str = "",
    ) -> bool:
        """
        建立事件因果关系

        Args:
            cause_event_id: 原因事件 ID
            effect_event_id: 结果事件 ID
            strength: 因果强度
            description: 描述

        Returns:
            bool: 是否成功
        """
        query = f"""
        INSERT EDGE IF NOT EXISTS causes (causality_strength, description)
        VALUES "{cause_event_id}" -> "{effect_event_id}": ({strength}, "{description}")
        """

        result = self._session_pool.execute(query)
        return result.is_succeeded()

    async def link_event_to_character(
        self,
        event_id: str,
        character_id: str,
        role: str = "participant",
        involvement_level: str = "direct",
    ) -> bool:
        """
        将事件关联到角色

        Args:
            event_id: 事件 ID
            character_id: 角色 ID
            role: 角色在事件中的角色
            involvement_level: 参与程度

        Returns:
            bool: 是否成功
        """
        query = f"""
        INSERT EDGE IF NOT EXISTS participates_in (role, involvement_level)
        VALUES "{character_id}" -> "{event_id}": ("{role}", "{involvement_level}")
        """

        result = self._session_pool.execute(query)
        return result.is_succeeded()

    async def link_event_to_lore(
        self,
        event_id: str,
        lore_id: str,
        reference_type: str = "mentioned",
        relevance: float = 0.5,
    ) -> bool:
        """
        将事件关联到设定

        Args:
            event_id: 事件 ID
            lore_id: 设定 ID
            reference_type: 引用类型
            relevance: 相关性

        Returns:
            bool: 是否成功
        """
        query = f"""
        INSERT EDGE IF NOT EXISTS references_lore (reference_type, relevance)
        VALUES "{event_id}" -> "{lore_id}": ("{reference_type}", {relevance})
        """

        result = self._session_pool.execute(query)
        return result.is_succeeded()

    async def get_event_chain(
        self,
        event_id: str,
        direction: str = "forward",
        max_depth: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        获取事件链

        Args:
            event_id: 起始事件 ID
            direction: 方向 (forward/backward/both)
            max_depth: 最大深度

        Returns:
            List: 事件链列表
        """
        if direction == "forward":
            query = f"""
            GO {max_depth} STEPS FROM "{event_id}" OVER causes
            YIELD $$.narrative_event.event_id AS event_id,
                  $$.narrative_event.summary AS summary,
                  $$.narrative_event.chapter AS chapter
            """
        elif direction == "backward":
            query = f"""
            GO {max_depth} STEPS FROM "{event_id}" OVER causes REVERSELY
            YIELD $$.narrative_event.event_id AS event_id,
                  $$.narrative_event.summary AS summary,
                  $$.narrative_event.chapter AS chapter
            """
        else:
            query = f"""
            GO {max_depth} STEPS FROM "{event_id}" OVER causes BIDIRECT
            YIELD $$.narrative_event.event_id AS event_id,
                  $$.narrative_event.summary AS summary,
                  $$.narrative_event.chapter AS chapter
            """

        result = self._session_pool.execute(query)
        if not result.is_succeeded():
            return []

        events = []
        for row in result.data.rows():
            events.append({
                "event_id": str(row.values[0]),
                "summary": str(row.values[1]),
                "chapter": row.values[2].as_int() if row.values[2].is_int() else None,
            })

        return events

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
