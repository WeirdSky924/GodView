"""
PostgreSQL 数据库操作层
负责存储角色基础数据、世界快照、章节内容等结构化数据
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _prepare_json_params(data: Dict[str, Any], json_fields: List[str]) -> Dict[str, Any]:
    """
    将 Python 列表/字典转换为 JSON 字符串，用于 SQLAlchemy text 查询

    Args:
        data: 原始数据字典
        json_fields: 需要转换的 JSON 字段名列表

    Returns:
        Dict: 处理后的数据字典
    """
    result = data.copy()
    for field in json_fields:
        if field in result:
            value = result[field]
            # 如果值是字符串，先尝试解析再重新序列化（确保格式正确）
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    value = [] if field not in ['attributes'] else {}
            # 转换为 JSON 字符串
            if isinstance(value, (list, dict)):
                result[field] = json.dumps(value)
            elif value is None:
                result[field] = '[]' if field not in ['attributes'] else '{}'
            else:
                result[field] = json.dumps(value)
    return result


def _to_postgres_array(items: List[str]) -> str:
    """
    将 Python 列表转换为 PostgreSQL 数组字面量格式

    Args:
        items: 字符串列表

    Returns:
        str: PostgreSQL 数组格式字符串，如 '{item1,item2}'
    """
    if not items:
        return '{}'

    # 转义单引号和特殊字符
    escaped = []
    for item in items:
        if item is None:
            escaped.append('NULL')
        else:
            # 转义单引号（PostgreSQL 数组中用双引号包裹元素）
            item_str = str(item).replace('\\', '\\\\').replace('"', '\\"')
            escaped.append(f'"{item_str}"')

    return '{' + ','.join(escaped) + '}'


class PostgresDatabase:
    """PostgreSQL 数据库操作类"""

    def __init__(self, connection_url: str, pool_size: int = 10):
        """
        初始化数据库连接

        Args:
            connection_url: 数据库连接 URL
            pool_size: 连接池大小
        """
        self.connection_url = connection_url
        self.pool_size = pool_size
        self._engine: Optional[AsyncEngine] = None
        self._session_maker: Optional[async_sessionmaker] = None

    async def connect(self):
        """建立数据库连接"""
        if self._engine is None:
            self._engine = create_async_engine(
                self.connection_url,
                pool_size=self.pool_size,
                max_overflow=20,
                pool_pre_ping=True,
                echo=False,
            )
            self._session_maker = async_sessionmaker(
                self._engine, class_=AsyncSession, expire_on_commit=False
            )
            logger.info("PostgreSQL 连接池已创建")

    async def disconnect(self):
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None
            logger.info("PostgreSQL 连接已关闭")

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """
        获取数据库会话上下文管理器

        Yields:
            AsyncSession: 数据库会话
        """
        if self._session_maker is None:
            await self.connect()

        session = self._session_maker()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"数据库事务失败：{e}")
            raise
        finally:
            await session.close()

    async def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        执行 SQL 查询（SELECT）

        Args:
            query: SQL 查询语句
            params: 查询参数

        Returns:
            List[Dict]: 查询结果
        """
        async with self.get_session() as session:
            result = await session.execute(text(query), params or {})
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

            # 处理 JSONB 字段 - 确保返回正确的 Python 类型
            jsonb_fields = [
                'personality_traits', 'attributes', 'rules', 'factions', 'metadata',
                'details', 'affected_hooks', 'affected_relationships', 'affected_characters',
                'characters', 'relationships', 'regions', 'hooks',
                'coordinates', 'terrain_features', 'landmarks', 'encounters', 'connections', 'local_rules',
                'completed_events', 'character_locations',
                # project_writing_configs 表的 JSONB 字段
                'enabled_rule_ids', 'enabled_rule_set_ids', 'rule_overrides', 'rule_priorities',
                # writing_rules 表的 JSONB 字段
                'tags', 'examples', 'counter_examples', 'conditions', 'exceptions',
                # writing_rule_sets 表的 JSONB 字段
                'rule_ids', 'rule_overrides', 'target_genres',
            ]

            for row in rows:
                for field in jsonb_fields:
                    if field in row and isinstance(row[field], str):
                        try:
                            row[field] = json.loads(row[field])
                        except (json.JSONDecodeError, TypeError):
                            pass  # 保持原值

            return rows

    async def execute_write(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        执行 SQL 写操作（INSERT/UPDATE/DELETE）

        Args:
            query: SQL 语句
            params: 参数

        Returns:
            int: 影响的行数
        """
        async with self.get_session() as session:
            result = await session.execute(text(query), params or {})
            return result.rowcount

    async def execute_many(
        self, query: str, params_list: List[Dict[str, Any]]
    ) -> int:
        """
        批量执行 SQL

        Args:
            query: SQL 语句
            params_list: 参数列表

        Returns:
            int: 影响的行数
        """
        async with self.get_session() as session:
            result = await session.execute(text(query), params_list)
            return result.rowcount

    # ==================== 角色相关操作 ====================

    async def save_character(self, character_data: Dict[str, Any]) -> str:
        """
        保存角色数据

        Args:
            character_data: 角色数据字典

        Returns:
            str: 角色 ID
        """
        from datetime import datetime

        params = character_data.copy()

        # 处理 JSONB 字段 (包括数组和对象类型)
        jsonb_list_fields = ['lexicon', 'forbidden_words', 'voice_samples', 'goals', 'inventory', 'agent_goals', 'agent_memory']
        jsonb_dict_fields = ['personality_traits', 'attributes']

        # 处理字段名映射 (background -> background_story)
        if 'background' in params and 'background_story' not in params:
            params['background_story'] = params.pop('background')

        # 处理数组类型的 JSONB 字段
        for field in jsonb_list_fields:
            value = params.get(field)
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except:
                    value = []
            if not isinstance(value, list):
                value = []
            params[field] = json.dumps(value)

        # 处理对象类型的 JSONB 字段
        for field in jsonb_dict_fields:
            value = params.get(field)
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except:
                    value = {}
            if not isinstance(value, dict):
                value = {}
            params[field] = json.dumps(value)

        # 确保可选字段有默认值
        if params.get('background_story') is None:
            params['background_story'] = None
        if params.get('speech_pattern') is None:
            params['speech_pattern'] = None
        if params.get('personality') is None:
            params['personality'] = None

        # 处理可选的 UUID 字段
        if params.get('world_id') is None:
            params['world_id'] = None

        # 处理布尔字段
        params['has_agent'] = params.get('has_agent', False)
        params['agent_enabled'] = params.get('agent_enabled', True)

        # 确保 datetime 字段是 datetime 对象
        for field in ['created_at', 'updated_at']:
            if field in params and isinstance(params[field], str):
                try:
                    params[field] = datetime.fromisoformat(params[field].replace('Z', '+00:00'))
                except:
                    params[field] = datetime.now()
            elif field not in params or params[field] is None:
                params[field] = datetime.now()

        # 使用 SQLAlchemy text 查询
        query = """
        INSERT INTO characters (id, name, project_id, world_id, description, role, status, appearance, age, gender,
                                personality, personality_traits, background_story, speech_pattern, lexicon,
                                forbidden_words, voice_samples, attributes, goals, inventory, current_location,
                                has_agent, agent_enabled, agent_goals, agent_memory)
        VALUES (:id, :name, :project_id, :world_id, :description, :role, :status, :appearance, :age, :gender,
                :personality, CAST(:personality_traits AS jsonb), :background_story, :speech_pattern, CAST(:lexicon AS jsonb),
                CAST(:forbidden_words AS jsonb), CAST(:voice_samples AS jsonb), CAST(:attributes AS jsonb),
                CAST(:goals AS jsonb), CAST(:inventory AS jsonb), :current_location,
                :has_agent, :agent_enabled, CAST(:agent_goals AS jsonb), CAST(:agent_memory AS jsonb))
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            project_id = EXCLUDED.project_id,
            world_id = EXCLUDED.world_id,
            description = EXCLUDED.description,
            role = EXCLUDED.role,
            status = EXCLUDED.status,
            appearance = EXCLUDED.appearance,
            age = EXCLUDED.age,
            gender = EXCLUDED.gender,
            personality = EXCLUDED.personality,
            personality_traits = EXCLUDED.personality_traits,
            background_story = EXCLUDED.background_story,
            speech_pattern = EXCLUDED.speech_pattern,
            lexicon = EXCLUDED.lexicon,
            forbidden_words = EXCLUDED.forbidden_words,
            voice_samples = EXCLUDED.voice_samples,
            attributes = EXCLUDED.attributes,
            goals = EXCLUDED.goals,
            inventory = EXCLUDED.inventory,
            current_location = EXCLUDED.current_location,
            has_agent = EXCLUDED.has_agent,
            agent_enabled = EXCLUDED.agent_enabled,
            agent_goals = EXCLUDED.agent_goals,
            agent_memory = EXCLUDED.agent_memory,
            updated_at = CURRENT_TIMESTAMP
        """
        await self.execute_write(query, params)
        return character_data.get("id", "")

    async def get_character(self, character_id: str) -> Optional[Dict[str, Any]]:
        """
        获取角色数据

        Args:
            character_id: 角色 ID

        Returns:
            Optional[Dict]: 角色数据
        """
        query = "SELECT * FROM characters WHERE id = :id"
        results = await self.execute_query(query, {"id": character_id})
        return results[0] if results else None

    async def get_all_characters(
        self,
        project_id: Optional[str] = None,
        role: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取角色列表，支持项目过滤

        Args:
            project_id: 项目 ID 过滤
            role: 角色类型过滤
            limit: 返回数量限制

        Returns:
            List: 角色列表
        """
        conditions = []
        params: Dict[str, Any] = {"limit": limit}

        if project_id:
            conditions.append("project_id = CAST(:project_id AS UUID)")
            params["project_id"] = project_id
        if role:
            conditions.append("role = :role")
            params["role"] = role

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM characters {where_clause} ORDER BY created_at DESC LIMIT :limit"

        return await self.execute_query(query, params)

    async def delete_character(self, character_id: str) -> bool:
        """删除角色"""
        query = "DELETE FROM characters WHERE id = CAST(:id AS UUID)"
        await self.execute_write(query, {"id": character_id})
        return True

    # ==================== 世界相关操作 ====================

    # ==================== 项目相关操作 ====================

    async def save_project(self, project_data: Dict[str, Any]) -> str:
        """保存项目数据"""
        # 如果有 id，将其转换为 UUID
        project_id = project_data.get("id")

        # 处理 metadata，确保是 JSON 字符串
        metadata = project_data.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        metadata_str = json.dumps(metadata)

        params = {
            "id": project_data.get("id"),
            "name": project_data.get("name"),
            "description": project_data.get("description"),
            "user_id": project_data.get("user_id"),
            "status": project_data.get("status", "draft"),
            "world_id": project_data.get("world_id"),
            "metadata": metadata_str
        }

        query = """
        INSERT INTO projects (id, name, description, user_id, status, world_id, metadata)
        VALUES (CAST(:id AS UUID), :name, :description, :user_id, :status, :world_id, CAST(:metadata AS jsonb))
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            user_id = EXCLUDED.user_id,
            status = EXCLUDED.status,
            world_id = EXCLUDED.world_id,
            updated_at = CURRENT_TIMESTAMP,
            metadata = EXCLUDED.metadata
        """
        await self.execute_write(query, params)
        return project_id or ""

    async def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目数据"""
        query = "SELECT * FROM projects WHERE id = :id"
        results = await self.execute_query(query, {"id": project_id})
        return results[0] if results else None

    async def update_project(self, project_id: str, update_data: Dict[str, Any]) -> bool:
        """更新项目数据"""
        # 构建动态更新语句
        set_clauses = []
        params = {"id": project_id}

        for key, value in update_data.items():
            set_clauses.append(f"{key} = :{key}")
            params[key] = value

        if not set_clauses:
            return False

        # 添加更新时间
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        query = f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = CAST(:id AS UUID)"
        await self.execute_write(query, params)
        return True

    async def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        query = "DELETE FROM projects WHERE id = CAST(:id AS UUID)"
        await self.execute_write(query, {"id": project_id})
        return True

    async def get_all_projects(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取所有项目（支持状态过滤和分页）"""
        if status:
            query = "SELECT * FROM projects WHERE status = :status ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            return await self.execute_query(query, {"status": status, "limit": limit, "offset": offset})
        else:
            query = "SELECT * FROM projects ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            return await self.execute_query(query, {"limit": limit, "offset": offset})

    async def get_project_summaries(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取项目摘要列表（含角色和章节数量）"""
        if status:
            query = """
            SELECT p.*,
                   (SELECT COUNT(*) FROM characters c WHERE c.project_id = p.id) as character_count,
                   (SELECT COUNT(*) FROM chapters ch WHERE ch.project_id = p.id) as chapter_count
            FROM projects p
            WHERE p.status = :status
            ORDER BY p.created_at DESC
            LIMIT :limit
            """
            return await self.execute_query(query, {"status": status, "limit": limit})
        else:
            query = """
            SELECT p.*,
                   (SELECT COUNT(*) FROM characters c WHERE c.project_id = p.id) as character_count,
                   (SELECT COUNT(*) FROM chapters ch WHERE ch.project_id = p.id) as chapter_count
            FROM projects p
            ORDER BY p.created_at DESC
            LIMIT :limit
            """
            return await self.execute_query(query, {"limit": limit})

    async def get_project_summary(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目摘要信息"""
        query = """
        SELECT p.*,
               (SELECT COUNT(*) FROM characters c WHERE c.project_id = p.id) as character_count,
               (SELECT COUNT(*) FROM chapters ch WHERE ch.project_id = p.id) as chapter_count
        FROM projects p
        WHERE p.id = CAST(:id AS UUID)
        """
        results = await self.execute_query(query, {"id": project_id})
        return results[0] if results else None

    async def save_world(self, world_data: Dict[str, Any]) -> str:
        """保存世界数据"""
        from datetime import datetime

        # 处理 JSON 字段
        params = _prepare_json_params(world_data, ['rules', 'factions'])

        # 确保 datetime 字段是 datetime 对象
        for field in ['created_at', 'updated_at']:
            if field in params and isinstance(params[field], str):
                try:
                    params[field] = datetime.fromisoformat(params[field].replace('Z', '+00:00'))
                except:
                    params[field] = datetime.now()
            elif field not in params or params[field] is None:
                params[field] = datetime.now()

        query = """
        INSERT INTO worlds (id, name, project_id, description, world_type, tone, rules, power_system,
                           technology_level, history, geography, factions, created_at, updated_at)
        VALUES (:id, :name, CAST(:project_id AS UUID), :description, :world_type, :tone, CAST(:rules AS jsonb), :power_system,
                :technology_level, :history, :geography, CAST(:factions AS jsonb), :created_at, :updated_at)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            project_id = EXCLUDED.project_id,
            description = EXCLUDED.description,
            world_type = EXCLUDED.world_type,
            tone = EXCLUDED.tone,
            rules = EXCLUDED.rules,
            power_system = EXCLUDED.power_system,
            technology_level = EXCLUDED.technology_level,
            history = EXCLUDED.history,
            geography = EXCLUDED.geography,
            factions = EXCLUDED.factions,
            updated_at = EXCLUDED.updated_at
        """
        await self.execute_write(query, params)
        return world_data.get("id", "")

    async def get_world(self, world_id: str) -> Optional[Dict[str, Any]]:
        """获取世界数据"""
        query = "SELECT * FROM worlds WHERE id = CAST(:id AS UUID)"
        results = await self.execute_query(query, {"id": world_id})
        return results[0] if results else None

    async def delete_world(self, world_id: str) -> bool:
        """删除世界"""
        query = "DELETE FROM worlds WHERE id = CAST(:id AS UUID)"
        await self.execute_write(query, {"id": world_id})
        return True

    async def get_all_worlds(
        self,
        project_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取世界列表，支持项目过滤

        Args:
            project_id: 项目 ID 过滤
            limit: 返回数量限制

        Returns:
            List: 世界列表
        """
        if project_id:
            query = "SELECT * FROM worlds WHERE project_id = :project_id ORDER BY created_at DESC LIMIT :limit"
            return await self.execute_query(query, {"project_id": project_id, "limit": limit})
        else:
            query = "SELECT * FROM worlds ORDER BY created_at DESC LIMIT :limit"
            return await self.execute_query(query, {"limit": limit})

    # ==================== 区域相关操作 ====================

    async def save_region(self, region_data: Dict[str, Any]) -> str:
        """保存区域数据"""
        import json
        from datetime import datetime

        # 确保必要字段有默认值
        logger = logging.getLogger(__name__)
        logger.info(f"save_region input keys: {list(region_data.keys())}")
        if region_data.get("area_size") is None:
            region_data["area_size"] = 0.0
        if region_data.get("atmosphere") is None:
            region_data["atmosphere"] = ""
        logger.info(f"save_region after fix: area_size={region_data.get('area_size')}")

        # 处理 JSONB 字段 - 转换为 JSON 字符串
        json_fields = ['coordinates', 'terrain_features', 'landmarks', 'encounters', 'connections', 'local_rules']
        for field in json_fields:
            if field in region_data and region_data[field] is not None:
                value = region_data[field]
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except:
                        value = {} if field == 'coordinates' else []
                if isinstance(value, (list, dict)):
                    region_data[field] = json.dumps(value)
                elif value is None:
                    region_data[field] = '{}' if field == 'coordinates' else '[]'

        # 确保 datetime 字段是 datetime 对象
        datetime_fields = ['created_at', 'updated_at']
        for field in datetime_fields:
            if field in region_data and isinstance(region_data[field], str):
                try:
                    region_data[field] = datetime.fromisoformat(region_data[field].replace('Z', '+00:00'))
                except:
                    region_data[field] = datetime.utcnow()

        query = """
        INSERT INTO regions (id, name, world_id, region_type, terrain_type, description,
                            atmosphere, coordinates, area_size, terrain_features, landmarks,
                            encounters, connections, local_rules, is_generated, visit_count,
                            created_at, updated_at)
        VALUES (:id, :name, :world_id, :region_type, :terrain_type, :description,
                :atmosphere, CAST(:coordinates AS jsonb), :area_size, CAST(:terrain_features AS jsonb),
                CAST(:landmarks AS jsonb), CAST(:encounters AS jsonb), CAST(:connections AS jsonb),
                CAST(:local_rules AS jsonb), :is_generated, :visit_count, :created_at, :updated_at)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            world_id = EXCLUDED.world_id,
            region_type = EXCLUDED.region_type,
            terrain_type = EXCLUDED.terrain_type,
            description = EXCLUDED.description,
            atmosphere = EXCLUDED.atmosphere,
            coordinates = EXCLUDED.coordinates,
            area_size = EXCLUDED.area_size,
            terrain_features = EXCLUDED.terrain_features,
            landmarks = EXCLUDED.landmarks,
            encounters = EXCLUDED.encounters,
            connections = EXCLUDED.connections,
            local_rules = EXCLUDED.local_rules,
            is_generated = EXCLUDED.is_generated,
            visit_count = EXCLUDED.visit_count,
            updated_at = EXCLUDED.updated_at
        """
        await self.execute_write(query, region_data)
        return region_data.get("id", "")

    async def get_region(self, region_id: str) -> Optional[Dict[str, Any]]:
        """获取区域数据"""
        query = "SELECT * FROM regions WHERE id = CAST(:id AS UUID)"
        results = await self.execute_query(query, {"id": region_id})
        return results[0] if results else None

    async def get_regions_by_world(self, world_id: str) -> List[Dict[str, Any]]:
        """获取世界的所有区域"""
        # 验证 world_id 是否为有效的 UUID 格式
        import uuid
        try:
            uuid.UUID(world_id)
        except (ValueError, TypeError):
            return []
        query = "SELECT * FROM regions WHERE world_id = CAST(:world_id AS UUID)"
        return await self.execute_query(query, {"world_id": world_id})

    # ==================== 伏笔相关操作 ====================

    async def save_hook(self, hook_data: Dict[str, Any]) -> str:
        """保存伏笔数据"""
        # 处理可选字段，设置默认值
        params = hook_data.copy()
        for field in ['world_id', 'plant_chapter', 'resolution_chapter']:
            if params.get(field) is None:
                params[field] = None

        # 确保 datetime 字段是 datetime 对象
        for field in ['created_at', 'resolved_at']:
            if field in params and isinstance(params[field], str):
                try:
                    params[field] = datetime.fromisoformat(params[field].replace('Z', '+00:00'))
                except:
                    params[field] = datetime.now()
            elif field == 'created_at' and (field not in params or params[field] is None):
                params[field] = datetime.now()

        query = """
        INSERT INTO hooks (id, title, project_id, world_id, description, hook_type, status, related_characters,
                          related_locations, related_objects, plant_context, plant_chapter,
                          resolution_hint, resolution_context, resolution_chapter, priority,
                          created_at, resolved_at)
        VALUES (:id, :title, CAST(:project_id AS UUID), :world_id, :description, :hook_type, :status, :related_characters,
                :related_locations, :related_objects, :plant_context, :plant_chapter,
                :resolution_hint, :resolution_context, :resolution_chapter, :priority,
                :created_at, :resolved_at)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            project_id = EXCLUDED.project_id,
            world_id = EXCLUDED.world_id,
            description = EXCLUDED.description,
            hook_type = EXCLUDED.hook_type,
            status = EXCLUDED.status,
            related_characters = EXCLUDED.related_characters,
            related_locations = EXCLUDED.related_locations,
            related_objects = EXCLUDED.related_objects,
            plant_context = EXCLUDED.plant_context,
            plant_chapter = EXCLUDED.plant_chapter,
            resolution_hint = EXCLUDED.resolution_hint,
            resolution_context = EXCLUDED.resolution_context,
            resolution_chapter = EXCLUDED.resolution_chapter,
            priority = EXCLUDED.priority,
            resolved_at = EXCLUDED.resolved_at
        """
        await self.execute_write(query, params)
        return hook_data.get("id", "")

    async def get_hook(self, hook_id: str) -> Optional[Dict[str, Any]]:
        """获取伏笔数据"""
        query = "SELECT * FROM hooks WHERE id = CAST(:id AS UUID)"
        results = await self.execute_query(query, {"id": hook_id})
        return results[0] if results else None

    async def get_hooks_by_status(
        self,
        status: str,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        根据状态获取伏笔，支持项目过滤

        Args:
            status: 伏笔状态
            project_id: 项目 ID 过滤

        Returns:
            List: 伏笔列表
        """
        if project_id:
            query = "SELECT * FROM hooks WHERE status = :status AND project_id = CAST(:project_id AS UUID) ORDER BY priority DESC"
            return await self.execute_query(query, {"status": status, "project_id": project_id})
        else:
            query = "SELECT * FROM hooks WHERE status = :status ORDER BY priority DESC"
            return await self.execute_query(query, {"status": status})

    async def update_hook_status(self, hook_id: str, status: str) -> bool:
        """更新伏笔状态"""
        query = "UPDATE hooks SET status = :status WHERE id = CAST(:id AS UUID)"
        await self.execute_write(query, {"id": hook_id, "status": status})
        return True

    async def delete_hook(self, hook_id: str) -> bool:
        """删除伏笔"""
        query = "DELETE FROM hooks WHERE id = CAST(:id AS UUID)"
        await self.execute_write(query, {"id": hook_id})
        return True

    async def get_all_hooks(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取伏笔列表，支持项目过滤

        Args:
            project_id: 项目 ID 过滤
            status: 状态过滤 (resolved: True/False)
            limit: 返回数量限制

        Returns:
            List: 伏笔列表
        """
        conditions = []
        params: Dict[str, Any] = {"limit": limit}

        if project_id:
            conditions.append("project_id = CAST(:project_id AS UUID)")
            params["project_id"] = project_id
        if status:
            # Map status to resolved column
            if status == "resolved":
                conditions.append("resolved = TRUE")
            elif status in ["planted", "triggered"]:
                conditions.append("resolved = FALSE")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM hooks {where_clause} ORDER BY importance DESC, created_at DESC LIMIT :limit"

        return await self.execute_query(query, params)

    # ==================== 章节相关操作 ====================

    async def save_chapter(self, chapter_data: Dict[str, Any]) -> str:
        """保存章节数据"""
        # 处理 JSON 字段
        params = _prepare_json_params(chapter_data, [
            'events', 'hooks_planted', 'hooks_resolved', 'main_plot_progress', 'reader_scores'
        ])

        # 处理可选字段
        if params.get('world_id') is None:
            params['world_id'] = None
        if params.get('project_id') is None:
            params['project_id'] = None

        # 确保 datetime 字段是 datetime 对象
        for field in ['created_at', 'updated_at', 'completed_at']:
            if field in params and isinstance(params[field], str):
                try:
                    params[field] = datetime.fromisoformat(params[field].replace('Z', '+00:00'))
                except:
                    params[field] = datetime.now()
            elif field in ['created_at', 'updated_at'] and (field not in params or params[field] is None):
                params[field] = datetime.now()

        query = """
        INSERT INTO chapters (id, title, project_id, world_id, summary, content, word_count, status, events,
                             hooks_planted, hooks_resolved, main_plot_progress, reader_scores,
                             created_at, updated_at, completed_at)
        VALUES (:id, :title, CAST(:project_id AS UUID), :world_id, :summary, :content, :word_count, :status, :events,
                :hooks_planted, :hooks_resolved, :main_plot_progress, :reader_scores,
                :created_at, :updated_at, :completed_at)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            project_id = EXCLUDED.project_id,
            world_id = EXCLUDED.world_id,
            summary = EXCLUDED.summary,
            content = EXCLUDED.content,
            word_count = EXCLUDED.word_count,
            status = EXCLUDED.status,
            events = EXCLUDED.events,
            hooks_planted = EXCLUDED.hooks_planted,
            hooks_resolved = EXCLUDED.hooks_resolved,
            main_plot_progress = EXCLUDED.main_plot_progress,
            reader_scores = EXCLUDED.reader_scores,
            updated_at = EXCLUDED.updated_at,
            completed_at = EXCLUDED.completed_at
        """
        await self.execute_write(query, params)
        return chapter_data.get("id", "")

    async def get_chapter(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """获取章节数据"""
        query = "SELECT * FROM chapters WHERE id = CAST(:id AS UUID)"
        results = await self.execute_query(query, {"id": chapter_id})
        return results[0] if results else None

    async def get_chapters_by_world(self, world_id: str) -> List[Dict[str, Any]]:
        """获取世界的所有章节"""
        # 验证 world_id 是否为有效的 UUID 格式
        import uuid
        try:
            uuid.UUID(world_id)
        except (ValueError, TypeError):
            return []
        query = "SELECT * FROM chapters WHERE world_id = CAST(:world_id AS UUID) ORDER BY created_at ASC"
        return await self.execute_query(query, {"world_id": world_id})

    async def get_chapters_by_project(
        self,
        project_id: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取项目的所有章节

        Args:
            project_id: 项目 ID
            status: 状态过滤
            limit: 返回数量限制

        Returns:
            List: 章节列表
        """
        conditions = ["project_id = :project_id"]
        params: Dict[str, Any] = {"project_id": project_id, "limit": limit}

        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = f"WHERE {' AND '.join(conditions)}"
        query = f"SELECT * FROM chapters {where_clause} ORDER BY created_at ASC LIMIT :limit"

        return await self.execute_query(query, params)

    # ==================== 世界快照相关操作 ====================

    async def save_snapshot(self, snapshot_data: Dict[str, Any]) -> str:
        """保存世界快照"""
        from datetime import datetime

        # 处理 JSONB 字段 - 转换为 JSON 字符串
        json_fields = ['characters', 'relationships', 'regions', 'hooks', 'completed_events', 'character_locations']
        for field in json_fields:
            if field in snapshot_data and snapshot_data[field] is not None:
                value = snapshot_data[field]
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except:
                        value = {}
                if isinstance(value, (list, dict)):
                    snapshot_data[field] = json.dumps(value)
                elif value is None:
                    snapshot_data[field] = '{}'

        # 确保 created_at 是 datetime 对象
        if 'created_at' in snapshot_data and isinstance(snapshot_data['created_at'], str):
            try:
                snapshot_data['created_at'] = datetime.fromisoformat(snapshot_data['created_at'].replace('Z', '+00:00'))
            except:
                snapshot_data['created_at'] = datetime.utcnow()

        query = """
        INSERT INTO world_snapshots (id, world_id, chapter_id, snapshot_type, name, description,
                                     characters, relationships, regions, hooks, main_plot_progress,
                                     completed_events, character_locations, created_at, created_by,
                                     parent_snapshot_id, is_branch, branch_reason)
        VALUES (:id, :world_id, :chapter_id, :snapshot_type, :name, :description,
                CAST(:characters AS jsonb), CAST(:relationships AS jsonb), CAST(:regions AS jsonb),
                CAST(:hooks AS jsonb), :main_plot_progress, CAST(:completed_events AS jsonb),
                CAST(:character_locations AS jsonb), :created_at, :created_by,
                :parent_snapshot_id, :is_branch, :branch_reason)
        """
        await self.execute_write(query, snapshot_data)
        return snapshot_data.get("id", "")

    async def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """获取快照数据"""
        query = "SELECT * FROM world_snapshots WHERE id = CAST(:id AS UUID)"
        results = await self.execute_query(query, {"id": snapshot_id})
        return results[0] if results else None

    async def get_snapshots_by_world(self, world_id: str) -> List[Dict[str, Any]]:
        """获取世界的所有快照"""
        # 验证 world_id 是否为有效的 UUID 格式
        import uuid
        try:
            uuid.UUID(world_id)
        except (ValueError, TypeError):
            # 如果不是有效的 UUID，返回空列表
            return []
        query = "SELECT * FROM world_snapshots WHERE world_id = CAST(:world_id AS UUID) ORDER BY created_at DESC"
        return await self.execute_query(query, {"world_id": world_id})

    async def rollback_to_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """
        回档到指定快照

        Args:
            snapshot_id: 快照 ID

        Returns:
            Dict: 快照数据
        """
        snapshot = await self.get_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError(f"快照不存在：{snapshot_id}")

        # 恢复角色数据
        characters = snapshot.get("characters", {})
        for char_id, char_data in characters.items():
            await self.save_character({"id": char_id, **char_data})

        # 恢复伏笔数据
        hooks = snapshot.get("hooks", {})
        for hook_id, hook_data in hooks.items():
            await self.save_hook({"id": hook_id, **hook_data})

        return snapshot

    # ==================== 干预日志相关操作 ====================

    async def log_intervention(self, intervention_data: Dict[str, Any]) -> str:
        """记录干预日志"""
        # 处理 JSONB 字段
        json_fields = ['details', 'affected_hooks', 'affected_relationships', 'affected_characters']
        for field in json_fields:
            if field in intervention_data and intervention_data[field] is not None:
                value = intervention_data[field]
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except:
                        value = {} if field == 'details' else []
                if isinstance(value, (list, dict)):
                    intervention_data[field] = json.dumps(value)
                elif value is None:
                    intervention_data[field] = '{}' if field == 'details' else '[]'

        query = """
        INSERT INTO intervention_logs (id, snapshot_id, intervention_type, description, details,
                                       affected_hooks, affected_relationships, affected_characters,
                                       outcome_rating, outcome_notes, created_at)
        VALUES (:id, :snapshot_id, :intervention_type, :description, CAST(:details AS jsonb),
                CAST(:affected_hooks AS jsonb), CAST(:affected_relationships AS jsonb), CAST(:affected_characters AS jsonb),
                :outcome_rating, :outcome_notes, :created_at)
        """
        await self.execute_write(query, intervention_data)
        return intervention_data.get("id", "")

    async def update_intervention_evaluation(
        self,
        intervention_id: str,
        outcome_rating: Optional[float] = None,
        outcome_notes: Optional[str] = None,
    ) -> None:
        """更新干预效果评估"""
        query = """
        UPDATE intervention_logs
        SET outcome_rating = :outcome_rating,
            outcome_notes = :outcome_notes
        WHERE id = CAST(:id AS UUID)
        """
        await self.execute_write(
            query,
            {
                "id": intervention_id,
                "outcome_rating": outcome_rating,
                "outcome_notes": outcome_notes,
            },
        )

    async def get_intervention_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取干预日志列表"""
        query = """
        SELECT id, snapshot_id, intervention_type, description, details,
               affected_hooks, affected_relationships, affected_characters,
               outcome_rating, outcome_notes, created_at
        FROM intervention_logs
        ORDER BY created_at DESC
        LIMIT :limit
        """
        rows = await self.execute_query(query, {"limit": limit})
        return [dict(row) for row in rows]

    # ==================== 初始化表结构 ====================

    async def init_tables(self):
        """初始化数据库表结构"""
        # 先检查已存在的表
        existing_tables = []
        try:
            check_sql = """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            """
            result = await self.execute_query(check_sql)
            existing_tables = [row['table_name'] for row in result]
        except Exception:
            pass

        # 定义需要创建的表（仅包含新表，不包含已存在的表）
        tables_to_create = []

        # 世界表 - 使用 UUID 类型匹配现有 schema
        if 'worlds' not in existing_tables:
            tables_to_create.append("""
            CREATE TABLE worlds (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
                description TEXT,
                world_type TEXT DEFAULT 'fantasy',
                tone TEXT DEFAULT 'serious',
                rules JSONB DEFAULT '[]',
                power_system TEXT,
                technology_level TEXT,
                history TEXT,
                geography TEXT,
                factions JSONB DEFAULT '[]',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_worlds_project_id ON worlds(project_id);
            """)

        # 区域表
        if 'regions' not in existing_tables:
            tables_to_create.append("""
            CREATE TABLE regions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                world_id UUID REFERENCES worlds(id) ON DELETE CASCADE,
                region_type TEXT DEFAULT 'custom',
                terrain_type TEXT DEFAULT 'custom',
                description TEXT,
                atmosphere TEXT,
                coordinates JSONB,
                area_size FLOAT,
                terrain_features JSONB DEFAULT '[]',
                landmarks JSONB DEFAULT '[]',
                encounters JSONB DEFAULT '[]',
                connections JSONB DEFAULT '[]',
                local_rules JSONB DEFAULT '[]',
                is_generated BOOLEAN DEFAULT FALSE,
                visit_count INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_regions_world_id ON regions(world_id);
            """)

        # 世界快照表
        if 'world_snapshots' not in existing_tables:
            tables_to_create.append("""
            CREATE TABLE world_snapshots (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                world_id UUID REFERENCES worlds(id) ON DELETE CASCADE,
                chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
                snapshot_type TEXT DEFAULT 'auto',
                name TEXT,
                description TEXT,
                characters JSONB DEFAULT '{}',
                relationships JSONB DEFAULT '{}',
                regions JSONB DEFAULT '{}',
                hooks JSONB DEFAULT '{}',
                main_plot_progress FLOAT DEFAULT 0,
                completed_events JSONB DEFAULT '[]',
                character_locations JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT DEFAULT 'system',
                parent_snapshot_id UUID REFERENCES world_snapshots(id),
                is_branch BOOLEAN DEFAULT FALSE,
                branch_reason TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_world_snapshots_world_id ON world_snapshots(world_id);
            CREATE INDEX IF NOT EXISTS idx_world_snapshots_chapter_id ON world_snapshots(chapter_id);
            """)

        # 干预日志表
        if 'intervention_logs' not in existing_tables:
            tables_to_create.append("""
            CREATE TABLE intervention_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                snapshot_id UUID REFERENCES world_snapshots(id) ON DELETE SET NULL,
                intervention_type TEXT NOT NULL,
                description TEXT,
                details JSONB DEFAULT '{}',
                affected_hooks JSONB DEFAULT '[]',
                affected_relationships JSONB DEFAULT '[]',
                affected_characters JSONB DEFAULT '[]',
                outcome_rating FLOAT,
                outcome_notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_intervention_logs_snapshot_id ON intervention_logs(snapshot_id);
            """)

        # 事件摘要表
        if 'event_summaries' not in existing_tables:
            tables_to_create.append("""
            CREATE TABLE event_summaries (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
                summary TEXT,
                event_type TEXT DEFAULT 'custom',
                participants JSONB DEFAULT '[]',
                subtext_markers JSONB DEFAULT '[]',
                hook_triggers JSONB DEFAULT '[]',
                info_gain_score FLOAT DEFAULT 0,
                raw_dialogue_refs JSONB DEFAULT '[]',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                "order" INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_event_summaries_chapter_id ON event_summaries(chapter_id);
            """)

        # 执行创建表
        async with self.get_session() as session:
            for table_sql in tables_to_create:
                for statement in table_sql.split(';'):
                    if statement.strip():
                        try:
                            await session.execute(text(statement))
                        except Exception as e:
                            logger.warning(f"创建表时出错（可能已存在）: {str(e)[:100]}")
            await session.commit()

        logger.info(f"数据库表结构初始化完成，已存在表: {existing_tables}, 新创建表: {len(tables_to_create)}")

    # ==================== Token 使用统计操作 ====================

    async def save_token_usage(self, usage_data: Dict[str, Any]) -> str:
        """
        保存 Token 使用记录

        Args:
            usage_data: Token 使用数据

        Returns:
            str: 记录 ID
        """
        # 处理 metadata JSONB 字段
        metadata = usage_data.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        usage_data["metadata"] = json.dumps(metadata) if isinstance(metadata, dict) else '{}'

        query = """
        INSERT INTO token_usage (
            id, project_id, input_tokens, output_tokens, total_tokens,
            provider, model, category, agent_name, session_id,
            chapter_id, character_id, estimated_cost, metadata, created_at
        ) VALUES (
            CAST(:id AS UUID), CAST(:project_id AS UUID), :input_tokens, :output_tokens, :total_tokens,
            :provider, :model, :category, :agent_name, :session_id,
            :chapter_id, :character_id, :estimated_cost, CAST(:metadata AS jsonb), :created_at
        )
        """
        await self.execute_write(query, usage_data)
        return usage_data.get("id", "")

    async def _update_project_token_stats(
        self,
        project_id: str,
        tokens: int,
        cost: float
    ) -> None:
        """
        更新项目的 Token 统计

        Args:
            project_id: 项目 ID
            tokens: 新增 token 数
            cost: 新增成本
        """
        query = """
        UPDATE projects
        SET total_tokens = COALESCE(total_tokens, 0) + :tokens,
            total_cost = COALESCE(total_cost, 0) + :cost,
            updated_at = NOW()
        WHERE id = CAST(:project_id AS UUID)
        """
        await self.execute_write(query, {
            "project_id": project_id,
            "tokens": tokens,
            "cost": cost,
        })

    async def get_token_usage_by_project(
        self,
        project_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取项目的 Token 使用记录

        Args:
            project_id: 项目 ID
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量限制

        Returns:
            List: Token 使用记录列表
        """
        conditions = ["project_id = :project_id"]
        params: Dict[str, Any] = {"project_id": project_id, "limit": limit}

        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date

        where_clause = f"WHERE {' AND '.join(conditions)}"
        query = f"SELECT * FROM token_usage {where_clause} ORDER BY created_at DESC LIMIT :limit"

        return await self.execute_query(query, params)

    async def get_token_stats_by_project(self, project_id: str) -> Dict[str, Any]:
        """
        获取项目的 Token 统计

        Args:
            project_id: 项目 ID

        Returns:
            Dict: 统计数据
        """
        query = """
        SELECT
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(SUM(estimated_cost), 0) as total_cost,
            COUNT(*) as record_count
        FROM token_usage
        WHERE project_id = :project_id
        """
        results = await self.execute_query(query, {"project_id": project_id})
        return results[0] if results else {}

    async def get_token_stats_by_category(self, project_id: str) -> List[Dict[str, Any]]:
        """
        获取按场景分组的 Token 统计

        Args:
            project_id: 项目 ID

        Returns:
            List: 按场景分组的统计
        """
        query = """
        SELECT category, SUM(total_tokens) as tokens
        FROM token_usage
        WHERE project_id = :project_id
        GROUP BY category
        ORDER BY tokens DESC
        """
        return await self.execute_query(query, {"project_id": project_id})

    async def get_token_stats_by_model(self, project_id: str) -> List[Dict[str, Any]]:
        """
        获取按模型分组的 Token 统计

        Args:
            project_id: 项目 ID

        Returns:
            List: 按模型分组的统计
        """
        query = """
        SELECT model, SUM(total_tokens) as tokens, SUM(estimated_cost) as cost
        FROM token_usage
        WHERE project_id = :project_id
        GROUP BY model
        ORDER BY tokens DESC
        """
        return await self.execute_query(query, {"project_id": project_id})

    async def get_daily_token_stats(
        self,
        project_id: str,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        获取每日 Token 统计

        Args:
            project_id: 项目 ID
            days: 天数

        Returns:
            List: 每日统计
        """
        query = """
        SELECT
            DATE(created_at) as date,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(SUM(estimated_cost), 0) as cost,
            COUNT(*) as record_count
        FROM token_usage
        WHERE project_id = :project_id
          AND created_at >= NOW() - INTERVAL '%s days'
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        """ % days

        return await self.execute_query(query, {"project_id": project_id})

    async def get_all_project_token_stats(self) -> List[Dict[str, Any]]:
        """
        获取所有项目的 Token 统计

        Returns:
            List: 项目统计列表
        """
        query = """
        SELECT
            CAST(p.id AS VARCHAR) as project_id,
            p.name as project_name,
            COALESCE(p.total_tokens, 0) as total_tokens,
            COALESCE(p.total_cost, 0) as total_cost
        FROM projects p
        ORDER BY p.total_tokens DESC NULLS LAST
        """
        return await self.execute_query(query, {})

    # ==================== 全局统计操作 ====================

    async def get_global_stats(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取统计数据

        Args:
            project_id: 项目 ID（可选，传入则返回该项目的统计）

        Returns:
            Dict: 统计数据
        """
        if project_id:
            # 按项目过滤的统计
            character_count = await self.execute_query(
                "SELECT COUNT(*) as count FROM characters WHERE project_id = CAST(:project_id AS UUID)",
                {"project_id": project_id}
            )
            world_count = await self.execute_query(
                "SELECT COUNT(*) as count FROM worlds WHERE project_id = CAST(:project_id AS UUID)",
                {"project_id": project_id}
            )
            chapter_count = await self.execute_query(
                "SELECT COUNT(*) as count FROM chapters WHERE project_id = CAST(:project_id AS UUID)",
                {"project_id": project_id}
            )
            token_stats = await self.execute_query(
                "SELECT COALESCE(SUM(total_tokens), 0) as total_tokens, COALESCE(SUM(estimated_cost), 0) as total_cost FROM token_usage WHERE project_id = CAST(:project_id AS UUID)",
                {"project_id": project_id}
            )
            # 单个项目时项目数为 1
            return {
                "project_count": 1,
                "character_count": character_count[0]["count"] if character_count else 0,
                "world_count": world_count[0]["count"] if world_count else 0,
                "chapter_count": chapter_count[0]["count"] if chapter_count else 0,
                "total_tokens": token_stats[0]["total_tokens"] if token_stats else 0,
                "total_cost": float(token_stats[0]["total_cost"]) if token_stats else 0.0,
            }
        else:
            # 全局统计
            project_count = await self.execute_query("SELECT COUNT(*) as count FROM projects")
            character_count = await self.execute_query("SELECT COUNT(*) as count FROM characters")
            world_count = await self.execute_query("SELECT COUNT(*) as count FROM worlds")
            chapter_count = await self.execute_query("SELECT COUNT(*) as count FROM chapters")
            token_stats = await self.execute_query("""
                SELECT
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(estimated_cost), 0) as total_cost
                FROM token_usage
            """)

            return {
                "project_count": project_count[0]["count"] if project_count else 0,
                "character_count": character_count[0]["count"] if character_count else 0,
                "world_count": world_count[0]["count"] if world_count else 0,
                "chapter_count": chapter_count[0]["count"] if chapter_count else 0,
                "total_tokens": token_stats[0]["total_tokens"] if token_stats else 0,
                "total_cost": float(token_stats[0]["total_cost"]) if token_stats else 0.0,
            }
