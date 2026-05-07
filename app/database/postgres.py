"""
PostgreSQL 数据库操作层
负责存储角色基础数据、世界快照、章节内容等结构化数据
"""

import asyncio
import json
import logging
import uuid as uuid_module
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import Any, AsyncIterator, Dict, List, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _validate_uuid(value: Any) -> Optional[str]:
    """
    验证并转换为有效的 UUID 字符串

    Args:
        value: 输入值（可以是 UUID 对象、字符串或 None）

    Returns:
        Optional[str]: 有效的 UUID 字符串，或 None 如果无效
    """
    if value is None:
        return None
    try:
        # asyncpg UUID、uuid.UUID 等对象都先统一转字符串，避免直接传入 uuid.UUID()
        # 时触发对象内部的 .replace() 路径。
        uuid_text = str(value)
        uuid_module.UUID(uuid_text)
        return uuid_text
    except (ValueError, TypeError, AttributeError):
        return None


def _normalize_datetime(value: Any, default: Optional[datetime] = None) -> Optional[datetime]:
    """将字符串/日期时间对象归一化为 datetime。"""
    if value is None:
        return default
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return default
    return default


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
                    value = {} if field in ['attributes', 'metadata'] else []
            # 转换为 JSON 字符串
            if isinstance(value, (list, dict)):
                result[field] = json.dumps(value)
            elif value is None:
                result[field] = '{}' if field in ['attributes', 'metadata'] else '[]'
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
        self._workflow_event_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

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
                'before_state', 'after_state', 'diff',
                'completed_events', 'character_locations',
                'memories', 'knowledge', 'working_memory',
                'keywords', 'tags', 'constraints', 'related_characters', 'related_locations', 'related_items', 'forbidden_actions',
                'participants', 'consequences', 'effects', 'related_regions',
                # project_writing_configs 表的 JSONB 字段
                'enabled_rule_ids', 'enabled_rule_set_ids', 'rule_overrides', 'rule_priorities',
                # writing_rules 表的 JSONB 字段
                'examples', 'counter_examples', 'conditions', 'exceptions',
                # writing_rule_sets 表的 JSONB 字段
                'rule_ids', 'rule_overrides', 'target_genres',
                # operation lifecycle / workflow events / setting/bootstrap persistence / trace
                'response_payload', 'event_data', 'conversation_snapshot', 'pending_conflicts',
                'cached_pending_lores', 'cached_pending_characters', 'cached_pending_hooks',
                'cached_context_sections', 'payload', 'setting_agent_history', 'extracted_seed', 'confirmed_seed',
                'root_input_summary', 'metadata', 'attributes', 'content',
                'suggested_payload',
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

        # 验证 id 字段（必须是有效 UUID）
        char_id = _validate_uuid(params.get('id'))
        if not char_id:
            char_id = str(uuid_module.uuid4())
        params['id'] = char_id

        # 处理 JSONB 字段 (包括数组和对象类型)
        jsonb_list_fields = ['lexicon', 'forbidden_words', 'voice_samples', 'goals', 'inventory', 'agent_goals', 'agent_memory', 'personality_traits', 'relationships', 'major_events', 'available_presence_types']
        jsonb_dict_fields = ['attributes', 'key_relationships', 'death_detail']

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
        scalar_defaults = {
            'name': '未命名角色',
            'description': '',
            'role': 'npc',
            'status': 'active',
            'appearance': '',
            'age': None,
            'gender': '',
            'personality': None,
            'background_story': None,
            'speech_pattern': None,
        }
        for field, default_value in scalar_defaults.items():
            if params.get(field) is None:
                params[field] = default_value

        # 处理可选的 UUID 字段 - 验证是否为有效 UUID
        params['world_id'] = _validate_uuid(params.get('world_id'))
        params['project_id'] = _validate_uuid(params.get('project_id'))
        params['current_region_id'] = _validate_uuid(params.get('current_region_id'))
        params['current_location'] = params.get('current_location')
        params['current_location_reason'] = params.get('current_location_reason') or ''

        # 处理布尔字段
        params['has_agent'] = params.get('has_agent', False)
        params['agent_enabled'] = params.get('agent_enabled', True)

        # 处理角色层级字段
        params['importance_tier'] = params.get('importance_tier', 'npc')
        params['narrative_weight'] = params.get('narrative_weight', 'minimal')
        params['story_arc_role'] = params.get('story_arc_role', 'neutral')
        params['plot_priority'] = params.get('plot_priority', 0)

        # 处理登场控制字段
        params['debut_chapter'] = params.get('debut_chapter')
        params['debut_scene'] = params.get('debut_scene')
        params['exit_chapter'] = params.get('exit_chapter')
        params['exit_reason'] = params.get('exit_reason')
        params['active_arc'] = params.get('active_arc')

        # 处理统计字段
        params['total_scenes'] = params.get('total_scenes', 0)
        params['dialogue_count'] = params.get('dialogue_count', 0)
        # major_events is already handled in jsonb_list_fields

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
        INSERT INTO characters (id, name, project_id, world_id, description, role, status,
                                importance_tier, narrative_weight, story_arc_role, plot_priority,
                                debut_chapter, debut_scene, exit_chapter, exit_reason, active_arc,
                                relationships, key_relationships,
                                appearance, age, gender,
                                personality, personality_traits, background_story, speech_pattern, lexicon,
                                forbidden_words, voice_samples, attributes, goals, inventory, current_location,
                                current_region_id, current_location_reason, death_detail, available_presence_types,
                                has_agent, agent_enabled, agent_goals, agent_memory,
                                total_scenes, dialogue_count, major_events)
        VALUES (:id, :name, :project_id, :world_id, :description, :role, :status,
                :importance_tier, :narrative_weight, :story_arc_role, :plot_priority,
                :debut_chapter, :debut_scene, :exit_chapter, :exit_reason, :active_arc,
                CAST(:relationships AS jsonb), CAST(:key_relationships AS jsonb),
                :appearance, :age, :gender,
                :personality, CAST(:personality_traits AS jsonb), :background_story, :speech_pattern, CAST(:lexicon AS jsonb),
                CAST(:forbidden_words AS jsonb), CAST(:voice_samples AS jsonb), CAST(:attributes AS jsonb),
                CAST(:goals AS jsonb), CAST(:inventory AS jsonb), :current_location,
                :current_region_id, :current_location_reason, CAST(:death_detail AS jsonb), CAST(:available_presence_types AS jsonb),
                :has_agent, :agent_enabled, CAST(:agent_goals AS jsonb), CAST(:agent_memory AS jsonb),
                :total_scenes, :dialogue_count, CAST(:major_events AS jsonb))
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            project_id = EXCLUDED.project_id,
            world_id = EXCLUDED.world_id,
            description = EXCLUDED.description,
            role = EXCLUDED.role,
            status = EXCLUDED.status,
            importance_tier = EXCLUDED.importance_tier,
            narrative_weight = EXCLUDED.narrative_weight,
            story_arc_role = EXCLUDED.story_arc_role,
            plot_priority = EXCLUDED.plot_priority,
            debut_chapter = EXCLUDED.debut_chapter,
            debut_scene = EXCLUDED.debut_scene,
            exit_chapter = EXCLUDED.exit_chapter,
            exit_reason = EXCLUDED.exit_reason,
            active_arc = EXCLUDED.active_arc,
            relationships = EXCLUDED.relationships,
            key_relationships = EXCLUDED.key_relationships,
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
            current_region_id = EXCLUDED.current_region_id,
            current_location_reason = EXCLUDED.current_location_reason,
            death_detail = EXCLUDED.death_detail,
            available_presence_types = EXCLUDED.available_presence_types,
            has_agent = EXCLUDED.has_agent,
            agent_enabled = EXCLUDED.agent_enabled,
            agent_goals = EXCLUDED.agent_goals,
            agent_memory = EXCLUDED.agent_memory,
            total_scenes = EXCLUDED.total_scenes,
            dialogue_count = EXCLUDED.dialogue_count,
            major_events = EXCLUDED.major_events,
            updated_at = CURRENT_TIMESTAMP
        """
        await self.execute_write(query, params)
        return params.get("id", "")

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

    async def get_character_by_project_and_name(
        self,
        project_id: str,
        name: str,
    ) -> Optional[Dict[str, Any]]:
        """按项目和名称查找角色"""
        if not project_id or not name.strip():
            return None

        query = """
        SELECT * FROM characters
        WHERE project_id = CAST(:project_id AS UUID)
          AND LOWER(name) = LOWER(:name)
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 1
        """
        results = await self.execute_query(query, {
            "project_id": project_id,
            "name": name.strip(),
        })
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
        # 验证 id 字段（必须是有效 UUID）
        project_id = _validate_uuid(project_data.get("id"))
        if not project_id:
            project_id = str(uuid_module.uuid4())

        # 处理 metadata，确保是 JSON 字符串
        metadata = project_data.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        metadata_str = json.dumps(metadata)

        # 验证 UUID 字段
        world_id = _validate_uuid(project_data.get("world_id"))

        params = {
            "id": project_id,
            "name": project_data.get("name"),
            "description": project_data.get("description"),
            "user_id": project_data.get("user_id"),
            "status": project_data.get("status", "draft"),
            "world_id": world_id,
            "metadata": metadata_str
        }

        query = """
        INSERT INTO projects (id, name, description, user_id, status, world_id, metadata)
        VALUES (CAST(:id AS UUID), :name, :description, :user_id, :status, """ + ("CAST(:world_id AS UUID)" if world_id else "NULL") + """, CAST(:metadata AS jsonb))
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

        # 确保 JSON 字段存在并有默认值
        json_fields = ['rules', 'factions', 'content_styles', 'protagonist_types', 'character_archetypes', 'power_types', 'metadata']
        for field in json_fields:
            if field not in world_data or world_data[field] is None:
                world_data[field] = {} if field == 'metadata' else []

        # 处理 JSON 字段
        params = _prepare_json_params(world_data, json_fields)

        # 验证 id 字段（必须是有效 UUID）
        world_id = _validate_uuid(params.get('id'))
        if not world_id:
            world_id = str(uuid_module.uuid4())
        params['id'] = world_id

        # 验证 UUID 字段
        params['project_id'] = _validate_uuid(params.get('project_id'))
        params['parent_world_id'] = _validate_uuid(params.get('parent_world_id'))
        params['scope_type'] = params.get('scope_type') or 'root'
        params['is_default'] = bool(params.get('is_default', False))
        params['inherit_rules'] = bool(params.get('inherit_rules', True))
        params['order_index'] = int(params.get('order_index') or 0)

        # 确保 datetime 字段是 datetime 对象
        for field in ['created_at', 'updated_at']:
            if field in params and isinstance(params[field], str):
                try:
                    params[field] = datetime.fromisoformat(params[field].replace('Z', '+00:00'))
                except:
                    params[field] = datetime.now()
            elif field not in params or params[field] is None:
                params[field] = datetime.now()

        # 确保字符串字段有默认值
        for field in ['name', 'description', 'world_type', 'tone', 'power_system', 'technology_level', 'history', 'geography']:
            if field not in params:
                params[field] = ''

        # 动态构建 SQL
        project_id_sql = "CAST(:project_id AS UUID)" if params.get('project_id') else "NULL"
        parent_world_id_sql = "CAST(:parent_world_id AS UUID)" if params.get('parent_world_id') else "NULL"

        query = """
        INSERT INTO worlds (id, name, project_id, parent_world_id, scope_type, is_default, inherit_rules, order_index,
                           description, world_type, tone, rules, power_system,
                           technology_level, history, geography, factions, content_styles, protagonist_types,
                           character_archetypes, power_types, metadata, created_at, updated_at)
        VALUES (:id, :name, """ + project_id_sql + """, """ + parent_world_id_sql + """, :scope_type, :is_default, :inherit_rules, :order_index,
                :description, :world_type, :tone, CAST(:rules AS jsonb), :power_system,
                :technology_level, :history, :geography, CAST(:factions AS jsonb), CAST(:content_styles AS jsonb),
                CAST(:protagonist_types AS jsonb), CAST(:character_archetypes AS jsonb), CAST(:power_types AS jsonb),
                CAST(:metadata AS jsonb), :created_at, :updated_at)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            project_id = EXCLUDED.project_id,
            parent_world_id = EXCLUDED.parent_world_id,
            scope_type = EXCLUDED.scope_type,
            is_default = EXCLUDED.is_default,
            inherit_rules = EXCLUDED.inherit_rules,
            order_index = EXCLUDED.order_index,
            description = EXCLUDED.description,
            world_type = EXCLUDED.world_type,
            tone = EXCLUDED.tone,
            rules = EXCLUDED.rules,
            power_system = EXCLUDED.power_system,
            technology_level = EXCLUDED.technology_level,
            history = EXCLUDED.history,
            geography = EXCLUDED.geography,
            factions = EXCLUDED.factions,
            content_styles = EXCLUDED.content_styles,
            protagonist_types = EXCLUDED.protagonist_types,
            character_archetypes = EXCLUDED.character_archetypes,
            power_types = EXCLUDED.power_types,
            metadata = EXCLUDED.metadata,
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
            query = """
            SELECT * FROM worlds
            WHERE project_id = CAST(:project_id AS UUID)
            ORDER BY is_default DESC, parent_world_id NULLS FIRST, order_index ASC, created_at ASC
            LIMIT :limit
            """
            return await self.execute_query(query, {"project_id": project_id, "limit": limit})
        else:
            query = "SELECT * FROM worlds ORDER BY created_at DESC LIMIT :limit"
            return await self.execute_query(query, {"limit": limit})

    async def get_worlds_by_project(self, project_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """兼容旧调用：按项目获取世界列表。"""
        return await self.get_all_worlds(project_id=project_id, limit=limit)
    async def get_default_world(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目默认世界，兼容 projects.world_id。"""
        project = await self.get_project(project_id)
        if project and project.get("world_id"):
            world = await self.get_world(str(project["world_id"]))
            if world:
                return world

        rows = await self.execute_query(
            """
            SELECT * FROM worlds
            WHERE project_id = CAST(:project_id AS UUID)
            ORDER BY is_default DESC, parent_world_id NULLS FIRST, order_index ASC, created_at ASC
            LIMIT 1
            """,
            {"project_id": project_id},
        )
        return rows[0] if rows else None

    async def assert_world_belongs_to_project(self, world_id: str, project_id: str) -> bool:
        """校验世界是否属于项目。"""
        rows = await self.execute_query(
            """
            SELECT 1 FROM worlds
            WHERE id = CAST(:world_id AS UUID) AND project_id = CAST(:project_id AS UUID)
            LIMIT 1
            """,
            {"world_id": world_id, "project_id": project_id},
        )
        return bool(rows)

    async def get_world_ancestor_ids(self, world_id: str) -> List[str]:
        """获取世界祖先 ID，从父到根递归返回。"""
        rows = await self.execute_query(
            """
            WITH RECURSIVE ancestors AS (
                SELECT parent_world_id, 1 AS depth
                FROM worlds
                WHERE id = CAST(:world_id AS UUID)
                UNION ALL
                SELECT w.parent_world_id, a.depth + 1
                FROM worlds w
                JOIN ancestors a ON w.id = a.parent_world_id
                WHERE a.parent_world_id IS NOT NULL AND a.depth < 32
            )
            SELECT parent_world_id::text AS id
            FROM ancestors
            WHERE parent_world_id IS NOT NULL
            ORDER BY depth DESC
            """,
            {"world_id": world_id},
        )
        return [row["id"] for row in rows]

    async def get_world_descendant_ids(self, world_id: str) -> List[str]:
        """获取世界后代 ID。"""
        rows = await self.execute_query(
            """
            WITH RECURSIVE descendants AS (
                SELECT id, 1 AS depth
                FROM worlds
                WHERE parent_world_id = CAST(:world_id AS UUID)
                UNION ALL
                SELECT w.id, d.depth + 1
                FROM worlds w
                JOIN descendants d ON w.parent_world_id = d.id
                WHERE d.depth < 32
            )
            SELECT id::text AS id FROM descendants
            """,
            {"world_id": world_id},
        )
        return [row["id"] for row in rows]

    async def get_world_scope_ids(self, world_id: str, include_inherited: bool = True) -> List[str]:
        """返回当前世界及可继承父级世界 ID。"""
        if not world_id:
            return []
        if not include_inherited:
            return [world_id]
        ancestors = await self.get_world_ancestor_ids(world_id)
        return [*ancestors, world_id]

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
        if region_data.get("state") is None:
            region_data["state"] = "normal"
        if region_data.get("state_summary") is None:
            region_data["state_summary"] = ""
        if region_data.get("metadata") is None:
            region_data["metadata"] = {}
        logger.info(f"save_region after fix: area_size={region_data.get('area_size')}")

        # 验证 id 字段（必须是有效 UUID）
        region_id = _validate_uuid(region_data.get('id'))
        if not region_id:
            region_id = str(uuid_module.uuid4())
        region_data['id'] = region_id

        # 验证 UUID 字段
        region_data['world_id'] = _validate_uuid(region_data.get('world_id'))

        # 处理 JSONB 字段 - 转换为 JSON 字符串
        json_fields = ['coordinates', 'terrain_features', 'landmarks', 'encounters', 'connections', 'local_rules', 'metadata']
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
        datetime_fields = ['created_at', 'updated_at', 'destroyed_at']
        for field in datetime_fields:
            if field in region_data and region_data[field]:
                try:
                    region_data[field] = datetime.fromisoformat(region_data[field].replace('Z', '+00:00'))
                except:
                    region_data[field] = None

        # 动态构建 world_id 的 SQL
        world_id_sql = "CAST(:world_id AS UUID)" if region_data.get('world_id') else "NULL"

        query = """
        INSERT INTO regions (id, name, world_id, region_type, terrain_type, description,
                            atmosphere, coordinates, area_size, terrain_features, landmarks,
                            encounters, connections, local_rules, metadata, state, state_summary, destroyed_at,
                            is_generated, visit_count, created_at, updated_at)
        VALUES (:id, :name,""" + world_id_sql + """, :region_type, :terrain_type, :description,
                :atmosphere, CAST(:coordinates AS jsonb), :area_size, CAST(:terrain_features AS jsonb),
                CAST(:landmarks AS jsonb), CAST(:encounters AS jsonb), CAST(:connections AS jsonb),
                CAST(:local_rules AS jsonb), CAST(:metadata AS jsonb), :state, :state_summary, :destroyed_at,
                :is_generated, :visit_count, :created_at, :updated_at)
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
            metadata = EXCLUDED.metadata,
            state = EXCLUDED.state,
            state_summary = EXCLUDED.state_summary,
            destroyed_at = EXCLUDED.destroyed_at,
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

    async def save_location(self, location_data: Dict[str, Any]) -> str:
        """将地点作为特殊区域保存，复用现有地图/区域体系。"""
        raw = location_data.copy()
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        reserved_keys = {
            "id", "name", "location_name", "title", "world_id", "region_id", "parent_region_id",
            "description", "summary", "overview", "location_type", "region_type", "terrain_type",
            "atmosphere", "coordinates", "area_size", "terrain_features", "features", "landmarks",
            "encounters", "connections", "neighbors", "local_rules", "state", "state_summary",
            "destroyed_at", "is_generated", "visit_count", "created_at", "updated_at", "metadata",
        }
        extra_fields = {key: value for key, value in raw.items() if key not in reserved_keys}
        metadata = {
            **metadata,
            "asset_kind": "location",
            "parent_region_id": raw.get("parent_region_id") or raw.get("region_id"),
            "source_location": raw,
            "extra_fields": extra_fields,
        }
        location_type = raw.get("location_type") or raw.get("region_type") or "location"
        if raw.get("parent_region_id") or raw.get("region_id"):
            location_type = raw.get("location_type") or "sub_location"

        region_record = {
            "id": raw.get("id"),
            "name": raw.get("name") or raw.get("location_name") or raw.get("title") or "未命名地点",
            "world_id": raw.get("world_id"),
            "region_type": location_type,
            "terrain_type": raw.get("terrain_type") or raw.get("location_type") or "location",
            "description": raw.get("description") or raw.get("summary") or raw.get("overview") or "",
            "atmosphere": raw.get("atmosphere") or "",
            "coordinates": raw.get("coordinates") or {},
            "area_size": raw.get("area_size") or 0.0,
            "terrain_features": raw.get("terrain_features") or raw.get("features") or [],
            "landmarks": raw.get("landmarks") or [],
            "encounters": raw.get("encounters") or [],
            "connections": raw.get("connections") or raw.get("neighbors") or [],
            "local_rules": raw.get("local_rules") or [],
            "metadata": metadata,
            "state": raw.get("state") or "normal",
            "state_summary": raw.get("state_summary") or "",
            "destroyed_at": raw.get("destroyed_at"),
            "is_generated": raw.get("is_generated", True),
            "visit_count": raw.get("visit_count", 0),
            "created_at": raw.get("created_at") or datetime.now(),
            "updated_at": raw.get("updated_at") or datetime.now(),
        }
        return await self.save_region(region_record)

    async def get_locations(
        self,
        project_id: str,
        world_id: Optional[str] = None,
        region_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """获取作为区域保存的地点/子地点。"""
        params: Dict[str, Any] = {"project_id": project_id, "limit": limit}
        conditions = [
            "w.project_id = CAST(:project_id AS UUID)",
            "(r.region_type IN ('location', 'sub_location') OR r.metadata->>'asset_kind' = 'location')",
        ]
        if world_id:
            conditions.append("r.world_id = CAST(:world_id AS UUID)")
            params["world_id"] = world_id
        if region_id:
            conditions.append("r.metadata->>'parent_region_id' = :region_id")
            params["region_id"] = region_id
        query = f"""
        SELECT r.*
        FROM regions r
        JOIN worlds w ON w.id = r.world_id
        WHERE {' AND '.join(conditions)}
        ORDER BY r.created_at DESC, r.name ASC
        LIMIT :limit
        """
        return await self.execute_query(query, params)

    async def get_regions_by_world(self, world_id: str) -> List[Dict[str, Any]]:
        """获取世界的所有区域"""
        valid_world_id = _validate_uuid(world_id)
        if not valid_world_id:
            return []
        query = "SELECT * FROM regions WHERE world_id = CAST(:world_id AS UUID) ORDER BY created_at ASC, name ASC"
        return await self.execute_query(query, {"world_id": valid_world_id})

    async def delete_region(self, region_id: str) -> bool:
        """删除区域"""
        query = "DELETE FROM regions WHERE id = CAST(:id AS UUID)"
        rowcount = await self.execute_write(query, {"id": region_id})
        return rowcount > 0

    async def save_narrative_state_change(self, change_data: Dict[str, Any]) -> str:
        """保存剧情状态变更日志。"""
        params = change_data.copy()
        change_id = _validate_uuid(params.get('id')) or str(uuid_module.uuid4())
        params['id'] = change_id
        params['project_id'] = _validate_uuid(params.get('project_id'))
        if not params['project_id']:
            raise ValueError("剧情状态变更缺少有效 project_id")
        params['chapter_id'] = _validate_uuid(params.get('chapter_id'))
        params['world_id'] = _validate_uuid(params.get('world_id'))
        params['scope_type'] = params.get('scope_type')

        for field in ['before_state', 'after_state', 'diff', 'metadata']:
            value = params.get(field) or {}
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    value = {}
            params[field] = json.dumps(value if isinstance(value, dict) else {})

        for field in ['created_at', 'confirmed_at', 'applied_at', 'rejected_at']:
            if isinstance(params.get(field), str):
                try:
                    params[field] = datetime.fromisoformat(params[field].replace('Z', '+00:00'))
                except ValueError:
                    params[field] = None
        params['created_at'] = params.get('created_at') or datetime.utcnow()
        params['status'] = params.get('status') or 'proposed'
        params['confirmation_required'] = params.get('confirmation_required', True)
        params['title'] = params.get('title') or ''
        params['summary'] = params.get('summary') or ''
        params['reason'] = params.get('reason') or ''
        for field in [
            'entity_id', 'entity_name', 'workflow_execution_id', 'workflow_id',
            'node_id', 'agent_type', 'discussion_id', 'source_text', 'fingerprint',
            'scope_type', 'confirmed_at', 'applied_at', 'rejected_at',
        ]:
            params.setdefault(field, None)

        chapter_id_sql = "CAST(:chapter_id AS UUID)" if params.get('chapter_id') else "NULL"
        world_id_sql = "CAST(:world_id AS UUID)" if params.get('world_id') else "NULL"
        query = """
        INSERT INTO narrative_state_changes (
            id, project_id, world_id, scope_type, entity_type, entity_id, entity_name, change_type, status,
            confirmation_required, title, summary, reason, before_state, after_state,
            diff, metadata, workflow_execution_id, workflow_id, node_id, agent_type,
            chapter_id, discussion_id, source_text, fingerprint, created_at,
            confirmed_at, applied_at, rejected_at
        ) VALUES (
            CAST(:id AS UUID), CAST(:project_id AS UUID), """ + world_id_sql + """, :scope_type, :entity_type, :entity_id, :entity_name,
            :change_type, :status, :confirmation_required, :title, :summary, :reason,
            CAST(:before_state AS jsonb), CAST(:after_state AS jsonb), CAST(:diff AS jsonb),
            CAST(:metadata AS jsonb), :workflow_execution_id, :workflow_id, :node_id, :agent_type,
            """ + chapter_id_sql + """, :discussion_id, :source_text, :fingerprint, :created_at,
            :confirmed_at, :applied_at, :rejected_at
        )
        ON CONFLICT (id) DO UPDATE SET
            world_id = EXCLUDED.world_id,
            scope_type = EXCLUDED.scope_type,
            entity_type = EXCLUDED.entity_type,
            entity_id = EXCLUDED.entity_id,
            entity_name = EXCLUDED.entity_name,
            change_type = EXCLUDED.change_type,
            status = EXCLUDED.status,
            confirmation_required = EXCLUDED.confirmation_required,
            title = EXCLUDED.title,
            summary = EXCLUDED.summary,
            reason = EXCLUDED.reason,
            before_state = EXCLUDED.before_state,
            after_state = EXCLUDED.after_state,
            diff = EXCLUDED.diff,
            metadata = EXCLUDED.metadata,
            workflow_execution_id = EXCLUDED.workflow_execution_id,
            workflow_id = EXCLUDED.workflow_id,
            node_id = EXCLUDED.node_id,
            agent_type = EXCLUDED.agent_type,
            chapter_id = EXCLUDED.chapter_id,
            discussion_id = EXCLUDED.discussion_id,
            source_text = EXCLUDED.source_text,
            fingerprint = EXCLUDED.fingerprint,
            confirmed_at = EXCLUDED.confirmed_at,
            applied_at = EXCLUDED.applied_at,
            rejected_at = EXCLUDED.rejected_at
        """
        if params.get('fingerprint'):
            existing = await self.get_state_change_by_fingerprint(params['project_id'], params['fingerprint'])
            if existing and existing.get('id') != change_id:
                return str(existing['id'])
        await self.execute_write(query, params)
        return change_id

    async def get_narrative_state_change(self, change_id: str) -> Optional[Dict[str, Any]]:
        """获取单条剧情状态变更。"""
        results = await self.execute_query(
            "SELECT * FROM narrative_state_changes WHERE id = CAST(:id AS UUID)",
            {"id": change_id},
        )
        return results[0] if results else None

    async def get_state_change_by_fingerprint(self, project_id: str, fingerprint: str) -> Optional[Dict[str, Any]]:
        """按幂等指纹获取剧情状态变更。"""
        results = await self.execute_query(
            """
            SELECT * FROM narrative_state_changes
            WHERE project_id = CAST(:project_id AS UUID) AND fingerprint = :fingerprint
            LIMIT 1
            """,
            {"project_id": project_id, "fingerprint": fingerprint},
        )
        return results[0] if results else None

    async def list_narrative_state_changes(
        self,
        project_id: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        status: Optional[str] = None,
        change_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """列出项目剧情状态变更。"""
        conditions = ["project_id = CAST(:project_id AS UUID)"]
        params: Dict[str, Any] = {"project_id": project_id, "limit": limit}
        if entity_type:
            conditions.append("entity_type = :entity_type")
            params["entity_type"] = entity_type
        if entity_id:
            conditions.append("entity_id = :entity_id")
            params["entity_id"] = entity_id
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if change_type:
            conditions.append("change_type = :change_type")
            params["change_type"] = change_type
        query = f"""
        SELECT * FROM narrative_state_changes
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC
        LIMIT :limit
        """
        return await self.execute_query(query, params)

    async def update_narrative_state_change_status(
        self,
        change_id: str,
        status: str,
        timestamp_field: Optional[str] = None,
    ) -> bool:
        """更新剧情状态变更状态。"""
        allowed_timestamp_fields = {"confirmed_at", "applied_at", "rejected_at"}
        if timestamp_field in allowed_timestamp_fields:
            query = f"""
            UPDATE narrative_state_changes
            SET status = :status, {timestamp_field} = NOW()
            WHERE id = CAST(:id AS UUID)
            """
        else:
            query = """
            UPDATE narrative_state_changes
            SET status = :status
            WHERE id = CAST(:id AS UUID)
            """
        rowcount = await self.execute_write(query, {"id": change_id, "status": status})
        return rowcount > 0

    async def mark_narrative_state_change_applied(self, change_id: str) -> bool:
        """标记剧情状态变更已应用。"""
        return await self.update_narrative_state_change_status(change_id, 'applied', 'applied_at')

    # ==================== 伏笔相关操作 ====================


    async def find_duplicate_hook(
        self,
        project_id: str,
        title: str,
        description: str = "",
        world_id: Optional[str] = None,
        scope_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """按自然键查找可能重复的伏笔。"""
        title_key = " ".join(str(title or "").lower().split())
        description_key = " ".join(str(description or "").lower().split())
        if not title_key:
            return None
        conditions = ["project_id = CAST(:project_id AS UUID)", "LOWER(TRIM(title)) = :title"]
        params: Dict[str, Any] = {"project_id": project_id, "title": title_key}
        if world_id:
            conditions.append("world_id = CAST(:world_id AS UUID)")
            params["world_id"] = world_id
        if scope_type:
            conditions.append("scope_type = :scope_type")
            params["scope_type"] = scope_type
        if description_key:
            conditions.append("(LOWER(TRIM(description)) = :description OR LOWER(TRIM(plant_context)) = :description)")
            params["description"] = description_key
        rows = await self.execute_query(
            f"""
            SELECT * FROM hooks
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at ASC
            LIMIT 1
            """,
            params,
        )
        return rows[0] if rows else None

    async def find_duplicate_lore(
        self,
        project_id: str,
        title: str,
        content: str = "",
    ) -> Optional[Dict[str, Any]]:
        """按标题或正文查找可能重复的设定。"""
        title_key = " ".join(str(title or "").lower().split())
        content_key = " ".join(str(content or "").lower().split())
        if not title_key and not content_key:
            return None
        conditions = ["project_id = CAST(:project_id AS UUID)"]
        params: Dict[str, Any] = {"project_id": project_id}
        duplicate_conditions: List[str] = []
        if title_key:
            duplicate_conditions.append("LOWER(TRIM(title)) = :title")
            params["title"] = title_key
        if content_key:
            duplicate_conditions.append("LOWER(TRIM(content)) = :content")
            params["content"] = content_key
        conditions.append(f"({' OR '.join(duplicate_conditions)})")
        rows = await self.execute_query(
            f"""
            SELECT * FROM lore_entries
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at ASC
            LIMIT 1
            """,
            params,
        )
        return rows[0] if rows else None

    async def save_hook(self, hook_data: Dict[str, Any]) -> str:
        """保存伏笔数据"""
        # 处理可选字段，设置默认值
        params = hook_data.copy()

        # 验证 UUID 字段（包括 id）
        hook_id = _validate_uuid(params.get('id'))
        if not hook_id:
            # 如果 id 无效，生成新的 UUID
            hook_id = str(uuid_module.uuid4())
        params['id'] = hook_id

        params['project_id'] = _validate_uuid(params.get('project_id'))
        params['world_id'] = _validate_uuid(params.get('world_id'))
        params['plant_chapter'] = _validate_uuid(params.get('plant_chapter'))
        params['resolution_chapter'] = _validate_uuid(params.get('resolution_chapter'))
        params['character_id'] = _validate_uuid(params.get('character_id'))
        params['parent_hook_id'] = _validate_uuid(params.get('parent_hook_id'))
        params['promoted_from_hook_id'] = _validate_uuid(params.get('promoted_from_hook_id'))
        params['scope_type'] = params.get('scope_type') or ('world' if params.get('world_id') else 'project')
        params['visibility'] = params.get('visibility') or 'global'

        for field in ['title', 'description', 'hook_type', 'status', 'plant_context', 'resolution_hint', 'resolution_context']:
            params[field] = params.get(field) or ''
        raw_priority = params.get('priority')
        try:
            params['priority'] = int(raw_priority or 3)
        except (TypeError, ValueError):
            params['priority'] = 3
        params['priority'] = max(1, min(5, params['priority']))
        for field in ['related_characters', 'related_locations', 'related_objects']:
            value = params.get(field)
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except Exception:
                    value = [value] if value.strip() else []
            if value is None:
                value = []
            elif not isinstance(value, list):
                value = [value]
            params[field] = json.dumps(value)
        params['resolved_at'] = params.get('resolved_at')

        # 确保 datetime 字段是 datetime 对象
        for field in ['created_at', 'resolved_at']:
            if field in params and params[field] is not None:
                params[field] = _normalize_datetime(params[field], datetime.now())
            elif field == 'created_at' and (field not in params or params[field] is None):
                params[field] = datetime.now()

        # 动态构建 SQL
        project_id_sql = "CAST(:project_id AS UUID)" if params.get('project_id') else "NULL"
        world_id_sql = "CAST(:world_id AS UUID)" if params.get('world_id') else "NULL"
        plant_chapter_sql = "CAST(:plant_chapter AS UUID)" if params.get('plant_chapter') else "NULL"
        resolution_chapter_sql = "CAST(:resolution_chapter AS UUID)" if params.get('resolution_chapter') else "NULL"

        character_id_sql = "CAST(:character_id AS UUID)" if params.get('character_id') else "NULL"
        parent_hook_id_sql = "CAST(:parent_hook_id AS UUID)" if params.get('parent_hook_id') else "NULL"
        promoted_from_hook_id_sql = "CAST(:promoted_from_hook_id AS UUID)" if params.get('promoted_from_hook_id') else "NULL"

        query = """
        INSERT INTO hooks (id, title, project_id, world_id, scope_type, character_id, parent_hook_id,
                          promoted_from_hook_id, visibility, description, hook_type, status, related_characters,
                          related_locations, related_objects, plant_context, plant_chapter,
                          resolution_hint, resolution_context, resolution_chapter, priority,
                          created_at, resolved_at)
        VALUES (:id, :title, """ + project_id_sql + """, """ + world_id_sql + """, :scope_type, """ + character_id_sql + """,
                """ + parent_hook_id_sql + """, """ + promoted_from_hook_id_sql + """, :visibility,
                :description, :hook_type, :status, CAST(:related_characters AS jsonb),
                CAST(:related_locations AS jsonb), CAST(:related_objects AS jsonb), :plant_context,""" + plant_chapter_sql + """,
                :resolution_hint, :resolution_context, """ + resolution_chapter_sql + """, :priority,
                :created_at, :resolved_at)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            project_id = EXCLUDED.project_id,
            world_id = EXCLUDED.world_id,
            scope_type = EXCLUDED.scope_type,
            character_id = EXCLUDED.character_id,
            parent_hook_id = EXCLUDED.parent_hook_id,
            promoted_from_hook_id = EXCLUDED.promoted_from_hook_id,
            visibility = EXCLUDED.visibility,
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
        return params["id"]

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
        world_id: Optional[str] = None,
        include_inherited: bool = False,
        scope_type: Optional[str] = None,
        character_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取伏笔列表，支持项目、世界继承、作用域过滤。

        不传 world_id 时保持旧 project-wide 行为。
        """
        conditions = []
        params: Dict[str, Any] = {"limit": limit}

        if project_id:
            conditions.append("project_id = CAST(:project_id AS UUID)")
            params["project_id"] = project_id
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if scope_type:
            conditions.append("scope_type = :scope_type")
            params["scope_type"] = scope_type
        if character_id:
            conditions.append("character_id = CAST(:character_id AS UUID)")
            params["character_id"] = character_id
        if world_id:
            if include_inherited:
                world_scope_ids = await self.get_world_scope_ids(world_id, include_inherited=True)
                scoped_placeholders = []
                for idx, scoped_world_id in enumerate(world_scope_ids or [world_id]):
                    key = f"world_scope_id_{idx}"
                    scoped_placeholders.append(f"CAST(:{key} AS UUID)")
                    params[key] = scoped_world_id
                scope_sql = ", ".join(scoped_placeholders)
                conditions.append(f"(world_id IN ({scope_sql}) OR world_id IS NULL OR scope_type = 'project')")
            else:
                conditions.append("world_id = CAST(:world_id AS UUID)")
                params["world_id"] = world_id

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM hooks {where_clause} ORDER BY priority DESC, created_at DESC LIMIT :limit"

        return await self.execute_query(query, params)

    # ==================== 角色世界身份操作 ====================

    async def save_character_world_profile(self, profile_data: Dict[str, Any]) -> str:
        """保存角色在特定世界中的身份信息。"""
        params = profile_data.copy()
        profile_id = _validate_uuid(params.get('id')) or str(uuid_module.uuid4())
        params['id'] = profile_id
        for field in ['project_id', 'character_id', 'world_id', 'current_region_id', 'entry_chapter_id', 'exit_chapter_id']:
            params[field] = _validate_uuid(params.get(field))
        for field in ['local_abilities', 'local_relationships', 'memory_state']:
            value = params.get(field)
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except Exception:
                    value = {} if field != 'local_abilities' else []
            if value is None:
                value = {} if field != 'local_abilities' else []
            params[field] = json.dumps(value)
        for field in ['created_at', 'updated_at']:
            if isinstance(params.get(field), str):
                try:
                    params[field] = datetime.fromisoformat(params[field].replace('Z', '+00:00'))
                except Exception:
                    params[field] = datetime.now()
            elif not params.get(field):
                params[field] = datetime.now()
        for field in ['local_name', 'local_identity', 'local_role', 'local_status']:
            params[field] = params.get(field) or ''

        current_region_sql = "CAST(:current_region_id AS UUID)" if params.get('current_region_id') else "NULL"
        entry_chapter_sql = "CAST(:entry_chapter_id AS UUID)" if params.get('entry_chapter_id') else "NULL"
        exit_chapter_sql = "CAST(:exit_chapter_id AS UUID)" if params.get('exit_chapter_id') else "NULL"
        query = """
        INSERT INTO character_world_profiles (
            id, project_id, character_id, world_id, local_name, local_identity, local_role, local_status,
            local_abilities, local_relationships, current_region_id, entry_chapter_id, exit_chapter_id,
            memory_state, created_at, updated_at
        ) VALUES (
            CAST(:id AS UUID), CAST(:project_id AS UUID), CAST(:character_id AS UUID), CAST(:world_id AS UUID),
            :local_name, :local_identity, :local_role, :local_status, CAST(:local_abilities AS jsonb),
            CAST(:local_relationships AS jsonb), """ + current_region_sql + """, """ + entry_chapter_sql + """, """ + exit_chapter_sql + """,
            CAST(:memory_state AS jsonb), :created_at, :updated_at
        )
        ON CONFLICT (character_id, world_id) DO UPDATE SET
            project_id = EXCLUDED.project_id,
            local_name = EXCLUDED.local_name,
            local_identity = EXCLUDED.local_identity,
            local_role = EXCLUDED.local_role,
            local_status = EXCLUDED.local_status,
            local_abilities = EXCLUDED.local_abilities,
            local_relationships = EXCLUDED.local_relationships,
            current_region_id = EXCLUDED.current_region_id,
            entry_chapter_id = EXCLUDED.entry_chapter_id,
            exit_chapter_id = EXCLUDED.exit_chapter_id,
            memory_state = EXCLUDED.memory_state,
            updated_at = EXCLUDED.updated_at
        """
        await self.execute_write(query, params)
        return profile_id

    async def get_character_world_profile(self, character_id: str, world_id: str) -> Optional[Dict[str, Any]]:
        rows = await self.execute_query(
            """
            SELECT * FROM character_world_profiles
            WHERE character_id = CAST(:character_id AS UUID) AND world_id = CAST(:world_id AS UUID)
            LIMIT 1
            """,
            {"character_id": character_id, "world_id": world_id},
        )
        return rows[0] if rows else None

    async def list_character_world_profiles(
        self,
        project_id: Optional[str] = None,
        character_id: Optional[str] = None,
        world_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: Dict[str, Any] = {"limit": limit}
        if project_id:
            conditions.append("project_id = CAST(:project_id AS UUID)")
            params["project_id"] = project_id
        if character_id:
            conditions.append("character_id = CAST(:character_id AS UUID)")
            params["character_id"] = character_id
        if world_id:
            conditions.append("world_id = CAST(:world_id AS UUID)")
            params["world_id"] = world_id
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return await self.execute_query(
            f"SELECT * FROM character_world_profiles {where_clause} ORDER BY updated_at DESC LIMIT :limit",
            params,
        )

    # ==================== 章节相关操作 ====================

    async def save_chapter(self, chapter_data: Dict[str, Any]) -> str:
        """保存章节数据"""
        import uuid as uuid_module

        # 处理 JSON 字段
        params = _prepare_json_params(chapter_data, [
            'events', 'hooks_planted', 'hooks_resolved', 'main_plot_progress', 'reader_scores'
        ])

        # 验证 id 字段（必须是有效 UUID）
        chapter_id = _validate_uuid(params.get('id'))
        if not chapter_id:
            chapter_id = str(uuid_module.uuid4())
        params['id'] = chapter_id

        # 处理可选的 UUID 字段 - 验证是否为有效 UUID
        for field in ['world_id', 'project_id']:
            value = params.get(field)
            if value is not None:
                try:
                    # 如果是 UUID 对象，转为字符串
                    if hasattr(value, 'hex'):
                        params[field] = str(value)
                    else:
                        # 验证是否为有效 UUID 字符串
                        uuid_module.UUID(str(value))
                        params[field] = str(value)
                except (ValueError, TypeError, AttributeError):
                    # 不是有效的 UUID，设为 None
                    params[field] = None
            else:
                params[field] = None

        params['chapter_outline_id'] = str(params.get('chapter_outline_id')) if params.get('chapter_outline_id') else None

        # 确保 datetime 字段是 datetime 对象
        for field in ['created_at', 'updated_at', 'completed_at']:
            if field in params and isinstance(params[field], str):
                try:
                    params[field] = datetime.fromisoformat(params[field].replace('Z', '+00:00'))
                except:
                    params[field] = datetime.now()
            elif field in ['created_at', 'updated_at'] and (field not in params or params[field] is None):
                params[field] = datetime.now()

        # 构建 SQL，world_id、project_id 和 chapter_outline_id 可能为 NULL
        world_id_value = params.get('world_id')
        project_id_value = params.get('project_id')
        chapter_outline_id_value = params.get('chapter_outline_id')

        query = """
        INSERT INTO chapters (id, title, project_id, world_id, chapter_outline_id, summary, content, word_count, status, events,
                             hooks_planted, hooks_resolved, main_plot_progress, reader_scores,
                             created_at, updated_at, completed_at, deleted_at)
        VALUES (:id, :title, """ + (f"CAST(:project_id AS UUID)" if project_id_value else "NULL") + """, """ + (f"CAST(:world_id AS UUID)" if world_id_value else "NULL") + """, :chapter_outline_id, :summary, :content, :word_count, :status, :events,
                :hooks_planted, :hooks_resolved, :main_plot_progress, :reader_scores,
                :created_at, :updated_at, :completed_at, :deleted_at)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            project_id = EXCLUDED.project_id,
            world_id = EXCLUDED.world_id,
            chapter_outline_id = EXCLUDED.chapter_outline_id,
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
            completed_at = EXCLUDED.completed_at,
            deleted_at = EXCLUDED.deleted_at
        """
        params.setdefault('deleted_at', None)
        await self.execute_write(query, params)
        return chapter_data.get("id", "")

    async def get_chapter(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """获取章节数据"""
        query = "SELECT * FROM chapters WHERE id = CAST(:id AS UUID)"
        results = await self.execute_query(query, {"id": chapter_id})
        return results[0] if results else None

    async def get_chapters_by_world(self, world_id: str) -> List[Dict[str, Any]]:
        """获取世界的所有章节"""
        valid_world_id = _validate_uuid(world_id)
        if not valid_world_id:
            return []
        query = "SELECT * FROM chapters WHERE world_id = CAST(:world_id AS UUID) ORDER BY created_at ASC"
        return await self.execute_query(query, {"world_id": valid_world_id})

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
        conditions = ["project_id = :project_id", "deleted_at IS NULL"]
        params: Dict[str, Any] = {"project_id": project_id, "limit": limit}

        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = f"WHERE {' AND '.join(conditions)}"
        query = f"SELECT * FROM chapters {where_clause} ORDER BY created_at ASC LIMIT :limit"

        return await self.execute_query(query, params)

    async def soft_delete_chapters_by_outline(self, project_id: str, chapter_outline_id: str) -> int:
        """软删除指定大纲生成的章节。"""
        query = """
        UPDATE chapters
        SET deleted_at = CURRENT_TIMESTAMP,
            status = 'deleted',
            updated_at = CURRENT_TIMESTAMP
        WHERE project_id = CAST(:project_id AS UUID)
          AND chapter_outline_id = :chapter_outline_id
          AND deleted_at IS NULL
        """
        await self.execute_write(query, {
            "project_id": project_id,
            "chapter_outline_id": chapter_outline_id,
        })
        result = await self.execute_query(
            """
            SELECT COUNT(*) as count
            FROM chapters
            WHERE project_id = CAST(:project_id AS UUID)
              AND chapter_outline_id = :chapter_outline_id
              AND deleted_at IS NOT NULL
            """,
            {"project_id": project_id, "chapter_outline_id": chapter_outline_id},
        )
        return int(result[0]["count"]) if result else 0

    # ==================== 世界快照相关操作 ====================

    async def save_snapshot(self, snapshot_data: Dict[str, Any]) -> str:
        """保存世界快照"""
        from datetime import datetime

        # 验证 UUID 字段（包括 id）
        snapshot_id = _validate_uuid(snapshot_data.get('id'))
        if not snapshot_id:
            # 如果 id 无效，生成新的 UUID
            snapshot_id = str(uuid_module.uuid4())
        snapshot_data['id'] = snapshot_id

        snapshot_data['world_id'] = _validate_uuid(snapshot_data.get('world_id'))
        snapshot_data['chapter_id'] = _validate_uuid(snapshot_data.get('chapter_id'))
        snapshot_data['parent_snapshot_id'] = _validate_uuid(snapshot_data.get('parent_snapshot_id'))

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

        # 动态构建 SQL
        world_id_sql = "CAST(:world_id AS UUID)" if snapshot_data.get('world_id') else "NULL"
        chapter_id_sql = "CAST(:chapter_id AS UUID)" if snapshot_data.get('chapter_id') else "NULL"
        parent_snapshot_id_sql = "CAST(:parent_snapshot_id AS UUID)" if snapshot_data.get('parent_snapshot_id') else "NULL"

        query = """
        INSERT INTO world_snapshots (id, world_id, chapter_id, snapshot_type, name, description,
                                     characters, relationships, regions, hooks, main_plot_progress,
                                     completed_events, character_locations, created_at, created_by,
                                     parent_snapshot_id, is_branch, branch_reason)
        VALUES (:id, """ + world_id_sql + """, """ + chapter_id_sql + """, :snapshot_type, :name, :description,
                CAST(:characters AS jsonb), CAST(:relationships AS jsonb), CAST(:regions AS jsonb),
                CAST(:hooks AS jsonb), :main_plot_progress, CAST(:completed_events AS jsonb),
                CAST(:character_locations AS jsonb), :created_at, :created_by,
                """ + parent_snapshot_id_sql + """, :is_branch, :branch_reason)
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

    def _normalize_json_value(self, value: Any, default: Any) -> Any:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return default
        if isinstance(value, (list, dict)):
            return value
        if value is None:
            return default
        return [value]

    async def save_outline_resource_requirement(self, requirement_data: Dict[str, Any]) -> str:
        """保存大纲资源需求；用于 workflow 产生的 pending requirement。"""
        params = requirement_data.copy()
        requirement_id = str(params.get("id") or uuid_module.uuid4())
        project_id = _validate_uuid(params.get("project_id"))
        if not project_id:
            raise ValueError("资源需求缺少有效 project_id")

        chapter_id = _validate_uuid(params.get("chapter_id"))
        matched_resource_id = params.get("matched_resource_id")
        if matched_resource_id is not None:
            matched_resource_id = str(matched_resource_id)

        requirement_type = str(params.get("requirement_type") or "lore").strip() or "lore"
        resource_name = str(params.get("resource_name") or params.get("name") or "").strip()
        if not resource_name:
            raise ValueError("资源需求缺少 resource_name")

        severity = str(params.get("severity") or "advisory").strip().lower()
        if severity not in {"blocking", "advisory", "optional"}:
            severity = "advisory"
        status = str(params.get("status") or "pending").strip().lower() or "pending"
        if status not in {"pending", "in_progress", "resolved", "ignored", "superseded"}:
            status = "pending"

        suggested_payload = params.get("suggested_payload") if isinstance(params.get("suggested_payload"), dict) else {}
        metadata = params.get("metadata") if isinstance(params.get("metadata"), dict) else {}
        metadata = {
            **metadata,
            "source_requirement": requirement_data,
            "source_node_label": params.get("source_node_label"),
            "source_field": params.get("source_field"),
        }
        record = {
            "id": requirement_id,
            "project_id": project_id,
            "outline_id": params.get("outline_id") or params.get("chapter_outline_id"),
            "outline_version_id": params.get("outline_version_id"),
            "chapter_id": chapter_id,
            "chapter_num": params.get("chapter_num") or params.get("chapter_number"),
            "requirement_type": requirement_type,
            "resource_name": resource_name,
            "severity": severity,
            "status": status,
            "reason": params.get("reason") or "",
            "suggested_payload": json.dumps(suggested_payload, default=str),
            "matched_resource_id": matched_resource_id,
            "matched_resource_type": params.get("matched_resource_type"),
            "source_excerpt": params.get("source_excerpt") or params.get("reason") or "",
            "source_agent": params.get("source_agent"),
            "source_node_id": params.get("source_node_id") or params.get("node_id"),
            "source_execution_id": params.get("source_execution_id") or params.get("workflow_execution_id"),
            "metadata": json.dumps(metadata, default=str),
            "updated_at": params.get("updated_at") or datetime.now(),
            "resolved_at": params.get("resolved_at"),
        }
        fingerprint = "|".join([
            project_id,
            str(record["outline_id"] or ""),
            str(record["chapter_num"] or ""),
            requirement_type,
            resource_name,
            str(record["reason"] or ""),
            str(record["source_node_id"] or ""),
        ])
        record["fingerprint"] = fingerprint
        chapter_id_sql = "CAST(:chapter_id AS UUID)" if record.get("chapter_id") else "NULL"

        query = """
        INSERT INTO outline_resource_requirements (
            id, project_id, outline_id, outline_version_id, chapter_id, chapter_num,
            requirement_type, resource_name, severity, status, reason, suggested_payload,
            matched_resource_id, matched_resource_type, source_excerpt, source_agent,
            source_node_id, source_execution_id, fingerprint, metadata, updated_at, resolved_at
        ) VALUES (
            CAST(:id AS UUID), CAST(:project_id AS UUID), :outline_id, :outline_version_id, """ + chapter_id_sql + """, :chapter_num,
            :requirement_type, :resource_name, :severity, :status, :reason, CAST(:suggested_payload AS jsonb),
            :matched_resource_id, :matched_resource_type, :source_excerpt, :source_agent,
            :source_node_id, :source_execution_id, :fingerprint, CAST(:metadata AS jsonb), :updated_at, :resolved_at
        )
        ON CONFLICT (project_id, fingerprint) WHERE fingerprint IS NOT NULL DO UPDATE SET
            outline_id = EXCLUDED.outline_id,
            outline_version_id = EXCLUDED.outline_version_id,
            chapter_id = EXCLUDED.chapter_id,
            chapter_num = EXCLUDED.chapter_num,
            requirement_type = EXCLUDED.requirement_type,
            resource_name = EXCLUDED.resource_name,
            severity = EXCLUDED.severity,
            status = CASE
                WHEN outline_resource_requirements.status IN ('resolved', 'ignored') THEN outline_resource_requirements.status
                ELSE EXCLUDED.status
            END,
            reason = EXCLUDED.reason,
            suggested_payload = EXCLUDED.suggested_payload,
            matched_resource_id = EXCLUDED.matched_resource_id,
            matched_resource_type = EXCLUDED.matched_resource_type,
            source_excerpt = EXCLUDED.source_excerpt,
            source_agent = EXCLUDED.source_agent,
            source_node_id = EXCLUDED.source_node_id,
            source_execution_id = EXCLUDED.source_execution_id,
            metadata = EXCLUDED.metadata,
            updated_at = EXCLUDED.updated_at,
            resolved_at = COALESCE(outline_resource_requirements.resolved_at, EXCLUDED.resolved_at)
        """
        await self.execute_write(query, record)
        return requirement_id

    async def save_outline_resource_requirements(self, requirements: List[Dict[str, Any]]) -> List[str]:
        """批量保存大纲资源需求。"""
        saved_ids: List[str] = []
        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue
            saved_ids.append(await self.save_outline_resource_requirement(requirement))
        return saved_ids

    async def get_outline_resource_requirements(
        self,
        project_id: str,
        outline_id: Optional[str] = None,
        chapter_num: Optional[int] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        requirement_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """查询大纲资源需求。"""
        conditions = ["project_id = CAST(:project_id AS UUID)"]
        params: Dict[str, Any] = {"project_id": project_id}
        if outline_id:
            conditions.append("outline_id = :outline_id")
            params["outline_id"] = outline_id
        if chapter_num is not None:
            conditions.append("chapter_num = :chapter_num")
            params["chapter_num"] = chapter_num
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if severity:
            conditions.append("severity = :severity")
            params["severity"] = severity
        if requirement_type:
            conditions.append("requirement_type = :requirement_type")
            params["requirement_type"] = requirement_type
        query = f"""
        SELECT * FROM outline_resource_requirements
        WHERE {' AND '.join(conditions)}
        ORDER BY
            chapter_num NULLS LAST,
            CASE severity WHEN 'blocking' THEN 1 WHEN 'advisory' THEN 2 ELSE 3 END,
            created_at ASC
        """
        return await self.execute_query(query, params)

    async def update_outline_resource_requirement_status(
        self,
        requirement_id: str,
        status: str,
        matched_resource_id: Optional[str] = None,
        matched_resource_type: Optional[str] = None,
        resolution_method: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """更新大纲资源需求处理状态。"""
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in {"pending", "in_progress", "resolved", "ignored", "superseded"}:
            raise ValueError(f"无效的资源需求状态: {status}")

        existing_rows = await self.execute_query(
            "SELECT * FROM outline_resource_requirements WHERE id = CAST(:id AS UUID)",
            {"id": requirement_id},
        )
        if not existing_rows:
            return None
        existing = existing_rows[0]

        normalized_resource_id = str(matched_resource_id).strip() if matched_resource_id else None
        normalized_resource_type = str(matched_resource_type).strip().lower() if matched_resource_type else None
        if bool(normalized_resource_id) != bool(normalized_resource_type):
            raise ValueError("绑定资源时必须同时提供 matched_resource_id 和 matched_resource_type")
        if normalized_resource_id and normalized_resource_type:
            valid_resource_id = _validate_uuid(normalized_resource_id)
            if not valid_resource_id:
                raise ValueError("绑定资源 ID 不是有效 UUID")
            normalized_resource_id = valid_resource_id
            normalized_resource_type = await self._validate_requirement_matched_resource(
                project_id=str(existing.get("project_id")),
                resource_id=normalized_resource_id,
                resource_type=normalized_resource_type,
            )

        normalized_method = self._normalize_requirement_resolution_method(
            status=normalized_status,
            resolution_method=resolution_method,
            matched_resource_id=normalized_resource_id,
        )
        previous_metadata = existing.get("metadata") if isinstance(existing.get("metadata"), dict) else {}
        next_metadata = previous_metadata.copy()
        now = datetime.now()
        if normalized_status in {"resolved", "ignored", "superseded"} and normalized_method:
            next_metadata.update({
                "resolution_method": normalized_method,
                "resolution_recorded_at": now.isoformat(),
                "previous_status": existing.get("status"),
            })
            if normalized_resource_type:
                next_metadata["resolved_with_resource_type"] = normalized_resource_type
        elif normalized_status in {"pending", "in_progress"}:
            next_metadata.update({
                "reopened_at": now.isoformat(),
                "previous_status": existing.get("status"),
            })

        params = {
            "id": requirement_id,
            "status": normalized_status,
            "matched_resource_id": normalized_resource_id,
            "matched_resource_type": normalized_resource_type,
            "metadata": json.dumps(next_metadata, default=str),
            "updated_at": now,
        }
        query = """
        UPDATE outline_resource_requirements
        SET status = :status,
            matched_resource_id = CASE
                WHEN CAST(:matched_resource_id AS TEXT) IS NULL THEN matched_resource_id
                ELSE CAST(:matched_resource_id AS TEXT)
            END,
            matched_resource_type = CASE
                WHEN CAST(:matched_resource_type AS TEXT) IS NULL THEN matched_resource_type
                ELSE CAST(:matched_resource_type AS TEXT)
            END,
            metadata = CAST(:metadata AS jsonb),
            updated_at = :updated_at,
            resolved_at = CASE
                WHEN :status IN ('pending', 'in_progress') THEN NULL
                WHEN resolved_at IS NULL THEN :updated_at
                ELSE resolved_at
            END
        WHERE id = CAST(:id AS UUID)
        RETURNING *
        """
        rows = await self.execute_query(query, params)
        return rows[0] if rows else None

    async def _validate_requirement_matched_resource(
        self,
        project_id: str,
        resource_id: str,
        resource_type: str,
    ) -> str:
        """校验资源需求绑定的资源存在且属于同一项目。"""
        normalized_type = resource_type.strip().lower()
        if normalized_type in {"region", "place"}:
            normalized_type = "location"
        if normalized_type not in {"character", "lore", "location"}:
            raise ValueError(f"不支持的绑定资源类型: {resource_type}")

        if normalized_type == "character":
            resource = await self.get_character(resource_id)
            if not resource or str(resource.get("project_id")) != str(project_id):
                raise ValueError("绑定的角色资源不存在或不属于当前项目")
            return normalized_type

        if normalized_type == "lore":
            resource = await self.get_lore_entry(resource_id)
            if not resource or str(resource.get("project_id")) != str(project_id):
                raise ValueError("绑定的设定资源不存在或不属于当前项目")
            return normalized_type

        rows = await self.execute_query(
            """
            SELECT r.id
            FROM regions r
            JOIN worlds w ON w.id = r.world_id
            WHERE r.id = CAST(:resource_id AS UUID)
              AND w.project_id = CAST(:project_id AS UUID)
            LIMIT 1
            """,
            {"resource_id": resource_id, "project_id": project_id},
        )
        if not rows:
            raise ValueError("绑定的地点资源不存在或不属于当前项目")
        return normalized_type

    def _normalize_requirement_resolution_method(
        self,
        status: str,
        resolution_method: Optional[str],
        matched_resource_id: Optional[str],
    ) -> Optional[str]:
        """规范化资源需求处理方式。"""
        allowed_methods = {"bind_existing", "create_resource", "manual_resolved", "ignored"}
        if resolution_method:
            normalized_method = str(resolution_method).strip().lower()
            if normalized_method not in allowed_methods:
                raise ValueError(f"无效的资源需求处理方式: {resolution_method}")
            if normalized_method in {"bind_existing", "create_resource"} and not matched_resource_id:
                raise ValueError("绑定或创建资源解决需求时必须提供 matched_resource_id 和 matched_resource_type")
            if normalized_method in {"manual_resolved", "ignored"} and matched_resource_id:
                raise ValueError("人工解决或忽略需求时不能同时绑定资源")
            if normalized_method == "ignored" and status != "ignored":
                raise ValueError("ignored 处理方式只能用于 ignored 状态")
            if normalized_method != "ignored" and status != "resolved":
                raise ValueError("资源需求处理方式只能用于 resolved 或 ignored 状态")
            return normalized_method
        if status == "ignored":
            return "ignored"
        if status == "resolved":
            return "bind_existing" if matched_resource_id else "manual_resolved"
        return None

    async def get_lore_entry(self, lore_id: str) -> Optional[Dict[str, Any]]:
        """获取设定条目。"""
        rows = await self.execute_query(
            "SELECT * FROM lore_entries WHERE id = CAST(:id AS UUID)",
            {"id": lore_id},
        )
        return rows[0] if rows else None

    async def get_chapter_resource_readiness(
        self,
        project_id: str,
        outline_id: Optional[str] = None,
        chapter_num: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """查询章节资源 readiness 汇总。"""
        conditions = ["project_id = CAST(:project_id AS UUID)"]
        params: Dict[str, Any] = {"project_id": project_id}
        if outline_id:
            conditions.append("outline_id = :outline_id")
            params["outline_id"] = outline_id
        if chapter_num is not None:
            conditions.append("chapter_num = :chapter_num")
            params["chapter_num"] = chapter_num
        query = f"""
        SELECT * FROM chapter_resource_readiness
        WHERE {' AND '.join(conditions)}
        ORDER BY chapter_num ASC
        """
        return await self.execute_query(query, params)

    async def update_chapter_resource_readiness(
        self,
        project_id: str,
        outline_id: Optional[str],
        chapter_num: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        """根据未完成资源需求刷新章节 readiness 汇总。"""
        if chapter_num is None:
            return None
        if not outline_id:
            logger.warning(
                "拒绝在缺少 outline_id 时刷新章节资源 readiness: project_id=%s chapter_num=%s",
                project_id,
                chapter_num,
            )
            return None
        params = {
            "project_id": project_id,
            "outline_id": outline_id,
            "chapter_num": chapter_num,
            "updated_at": datetime.now(),
        }
        outline_filter = "outline_id = :outline_id"
        query = f"""
        WITH stats AS (
            SELECT
                COUNT(*) FILTER (WHERE severity = 'blocking' AND status NOT IN ('ignored', 'superseded')) AS blocking_total,
                COUNT(*) FILTER (WHERE severity = 'blocking' AND status = 'resolved') AS blocking_resolved,
                COUNT(*) FILTER (WHERE severity = 'advisory' AND status NOT IN ('ignored', 'superseded')) AS advisory_total,
                COUNT(*) FILTER (WHERE severity = 'advisory' AND status = 'resolved') AS advisory_resolved
            FROM outline_resource_requirements
            WHERE project_id = CAST(:project_id AS UUID)
              AND chapter_num = :chapter_num
              AND {outline_filter}
        ), upsert AS (
            UPDATE chapter_resource_readiness
            SET blocking_total = stats.blocking_total,
                blocking_resolved = stats.blocking_resolved,
                advisory_total = stats.advisory_total,
                advisory_resolved = stats.advisory_resolved,
                readiness_status = CASE
                    WHEN stats.blocking_total > stats.blocking_resolved THEN 'blocked'
                    WHEN stats.advisory_total > stats.advisory_resolved THEN 'ready_with_warnings'
                    ELSE 'ready'
                END,
                last_audited_at = :updated_at,
                updated_at = :updated_at
            FROM stats
            WHERE chapter_resource_readiness.project_id = CAST(:project_id AS UUID)
              AND chapter_resource_readiness.chapter_num = :chapter_num
              AND ((CAST(:outline_id AS TEXT) IS NULL AND chapter_resource_readiness.outline_id IS NULL) OR chapter_resource_readiness.outline_id = CAST(:outline_id AS TEXT))
            RETURNING chapter_resource_readiness.*
        ), inserted AS (
            INSERT INTO chapter_resource_readiness (
                project_id, outline_id, chapter_num, blocking_total, blocking_resolved,
                advisory_total, advisory_resolved, readiness_status, last_audited_at, updated_at
            )
            SELECT
                CAST(:project_id AS UUID), CAST(:outline_id AS TEXT), :chapter_num,
                blocking_total, blocking_resolved, advisory_total, advisory_resolved,
                CASE
                    WHEN blocking_total > blocking_resolved THEN 'blocked'
                    WHEN advisory_total > advisory_resolved THEN 'ready_with_warnings'
                    ELSE 'ready'
                END,
                :updated_at,
                :updated_at
            FROM stats
            WHERE NOT EXISTS (SELECT 1 FROM upsert)
            RETURNING *
        )
        SELECT * FROM upsert
        UNION ALL
        SELECT * FROM inserted
        """
        rows = await self.execute_query(query, params)
        return rows[0] if rows else None

    async def save_event(self, event_data: Dict[str, Any]) -> str:
        """保存工作流/事件 Agent 生成的领域剧情事件。"""
        params = event_data.copy()
        event_pk = _validate_uuid(params.get("id")) or str(uuid_module.uuid4())
        external_event_id = params.get("event_id")
        if not external_event_id and params.get("id") and not _validate_uuid(params.get("id")):
            external_event_id = str(params.get("id"))

        event_name = (
            params.get("event_name")
            or params.get("name")
            or params.get("title")
            or params.get("summary")
            or "未命名事件"
        )
        known_fields = {
            "id", "project_id", "world_id", "chapter_id", "event_id", "event_name", "name", "title",
            "summary", "event_type", "type", "status", "description", "trigger_condition", "trigger",
            "participants", "characters", "consequences", "effects", "related_regions", "regions",
            "related_locations", "locations", "narrative_purpose", "purpose", "suggested_chapter",
            "source", "workflow_execution_id", "workflow_id", "node_id", "agent_type", "metadata",
            "created_at", "updated_at",
        }
        metadata = params.get("metadata") if isinstance(params.get("metadata"), dict) else {}
        metadata = {
            **metadata,
            "source_event": event_data,
            "extra_fields": {key: value for key, value in event_data.items() if key not in known_fields},
        }
        record = {
            "id": event_pk,
            "project_id": _validate_uuid(params.get("project_id")),
            "world_id": _validate_uuid(params.get("world_id")),
            "chapter_id": _validate_uuid(params.get("chapter_id")),
            "event_id": str(external_event_id) if external_event_id else None,
            "event_name": event_name,
            "event_type": params.get("event_type") or params.get("type") or "custom",
            "status": params.get("status") or "planned",
            "description": params.get("description") or params.get("summary") or "",
            "trigger_condition": params.get("trigger_condition") or params.get("trigger") or "",
            "participants": self._normalize_json_value(params.get("participants") or params.get("characters"), []),
            "consequences": self._normalize_json_value(params.get("consequences"), []),
            "effects": self._normalize_json_value(params.get("effects"), []),
            "related_regions": self._normalize_json_value(params.get("related_regions") or params.get("regions"), []),
            "related_locations": self._normalize_json_value(params.get("related_locations") or params.get("locations"), []),
            "narrative_purpose": params.get("narrative_purpose") or params.get("purpose") or "",
            "suggested_chapter": str(params.get("suggested_chapter")) if params.get("suggested_chapter") is not None else "",
            "source": params.get("source") or "workflow",
            "workflow_execution_id": params.get("workflow_execution_id"),
            "workflow_id": params.get("workflow_id"),
            "node_id": params.get("node_id"),
            "agent_type": params.get("agent_type"),
            "metadata": metadata,
            "created_at": params.get("created_at") or datetime.now(),
            "updated_at": params.get("updated_at") or datetime.now(),
        }
        if not record["project_id"]:
            raise ValueError("事件缺少有效 project_id")
        for field in [
            "participants", "consequences", "effects", "related_regions", "related_locations", "metadata",
        ]:
            record[field] = json.dumps(record[field])
        world_id_sql = "CAST(:world_id AS UUID)" if record.get("world_id") else "NULL"
        chapter_id_sql = "CAST(:chapter_id AS UUID)" if record.get("chapter_id") else "NULL"
        conflict_clause = "ON CONFLICT (id) DO UPDATE SET"
        if record.get("event_id"):
            conflict_clause = "ON CONFLICT (project_id, event_id) WHERE event_id IS NOT NULL DO UPDATE SET"
        query = """
        INSERT INTO events (
            id, project_id, world_id, chapter_id, event_id, event_name, event_type, status,
            description, trigger_condition, participants, consequences, effects, related_regions,
            related_locations, narrative_purpose, suggested_chapter, source, workflow_execution_id,
            workflow_id, node_id, agent_type, metadata, created_at, updated_at
        ) VALUES (
            CAST(:id AS UUID), CAST(:project_id AS UUID), """ + world_id_sql + ", " + chapter_id_sql + """,
            :event_id, :event_name, :event_type, :status, :description, :trigger_condition,
            CAST(:participants AS jsonb), CAST(:consequences AS jsonb), CAST(:effects AS jsonb),
            CAST(:related_regions AS jsonb), CAST(:related_locations AS jsonb), :narrative_purpose,
            :suggested_chapter, :source, :workflow_execution_id, :workflow_id, :node_id,
            :agent_type, CAST(:metadata AS jsonb), :created_at, :updated_at
        )
        """ + conflict_clause + """
            project_id = EXCLUDED.project_id,
            world_id = EXCLUDED.world_id,
            chapter_id = EXCLUDED.chapter_id,
            event_id = EXCLUDED.event_id,
            event_name = EXCLUDED.event_name,
            event_type = EXCLUDED.event_type,
            status = EXCLUDED.status,
            description = EXCLUDED.description,
            trigger_condition = EXCLUDED.trigger_condition,
            participants = EXCLUDED.participants,
            consequences = EXCLUDED.consequences,
            effects = EXCLUDED.effects,
            related_regions = EXCLUDED.related_regions,
            related_locations = EXCLUDED.related_locations,
            narrative_purpose = EXCLUDED.narrative_purpose,
            suggested_chapter = EXCLUDED.suggested_chapter,
            source = EXCLUDED.source,
            workflow_execution_id = EXCLUDED.workflow_execution_id,
            workflow_id = EXCLUDED.workflow_id,
            node_id = EXCLUDED.node_id,
            agent_type = EXCLUDED.agent_type,
            metadata = EXCLUDED.metadata,
            updated_at = EXCLUDED.updated_at
        """
        await self.execute_write(query, record)
        if record.get("event_id"):
            existing = await self.execute_query(
                "SELECT id FROM events WHERE project_id = CAST(:project_id AS UUID) AND event_id = :event_id LIMIT 1",
                {"project_id": record["project_id"], "event_id": record["event_id"]},
            )
            if existing:
                return str(existing[0].get("id"))
        return event_pk

    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """按主键或外部 event_id 获取剧情事件。"""
        if _validate_uuid(event_id):
            rows = await self.execute_query("SELECT * FROM events WHERE id = CAST(:id AS UUID)", {"id": event_id})
        else:
            rows = await self.execute_query("SELECT * FROM events WHERE event_id = :id LIMIT 1", {"id": event_id})
        return rows[0] if rows else None

    async def get_events(
        self,
        project_id: str,
        world_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """获取项目/世界下的剧情事件。"""
        params: Dict[str, Any] = {"project_id": project_id, "limit": limit}
        conditions = ["project_id = CAST(:project_id AS UUID)"]
        if world_id:
            conditions.append("world_id = CAST(:world_id AS UUID)")
            params["world_id"] = world_id
        if status:
            conditions.append("status = :status")
            params["status"] = status
        query = f"""
        SELECT * FROM events
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC, event_name ASC
        LIMIT :limit
        """
        return await self.execute_query(query, params)

    # ==================== 干预日志相关操作 ====================


    async def log_intervention(self, intervention_data: Dict[str, Any]) -> str:
        """记录干预日志"""
        params = intervention_data.copy()

        # 验证并生成 UUID
        intervention_id = _validate_uuid(params.get('id'))
        if not intervention_id:
            intervention_id = str(uuid_module.uuid4())
        params['id'] = intervention_id

        # snapshot_id 可以为空，但如果提供则需要验证
        snapshot_id = _validate_uuid(params.get('snapshot_id'))
        params['snapshot_id'] = snapshot_id  # 可以为 None

        # 处理 JSONB 字段
        json_fields = ['details', 'affected_hooks', 'affected_relationships', 'affected_characters']
        for field in json_fields:
            if field in params and params[field] is not None:
                value = params[field]
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except:
                        value = {} if field == 'details' else []
                if isinstance(value, (list, dict)):
                    params[field] = json.dumps(value)
                elif value is None:
                    params[field] = '{}' if field == 'details' else '[]'

        # 处理 datetime 字段
        if 'created_at' in params and isinstance(params['created_at'], str):
            try:
                params['created_at'] = datetime.fromisoformat(params['created_at'].replace('Z', '+00:00'))
            except:
                params['created_at'] = datetime.now()
        elif 'created_at' not in params or params.get('created_at') is None:
            params['created_at'] = datetime.now()

        # 动态构建 SQL
        snapshot_id_sql = "CAST(:snapshot_id AS UUID)" if params.get('snapshot_id') else "NULL"

        query = f"""
        INSERT INTO intervention_logs (id, snapshot_id, intervention_type, description, details,
                                       affected_hooks, affected_relationships, affected_characters,
                                       outcome_rating, outcome_notes, created_at)
        VALUES (:id, {snapshot_id_sql}, :intervention_type, :description, CAST(:details AS jsonb),
                CAST(:affected_hooks AS jsonb), CAST(:affected_relationships AS jsonb), CAST(:affected_characters AS jsonb),
                :outcome_rating, :outcome_notes, :created_at)
        """
        await self.execute_write(query, params)
        return intervention_id

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

    async def delete_intervention_log(self, intervention_id: str) -> bool:
        """删除单条干预日志"""
        query = "DELETE FROM intervention_logs WHERE id = :id"
        await self.execute_write(query, {"id": intervention_id})
        return True

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
                parent_world_id UUID REFERENCES worlds(id) ON DELETE SET NULL,
                scope_type TEXT NOT NULL DEFAULT 'root',
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                inherit_rules BOOLEAN NOT NULL DEFAULT TRUE,
                order_index INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                world_type TEXT DEFAULT 'fantasy',
                tone TEXT DEFAULT 'serious',
                content_styles JSONB DEFAULT '[]',
                protagonist_types JSONB DEFAULT '[]',
                character_archetypes JSONB DEFAULT '[]',
                power_types JSONB DEFAULT '[]',
                rules JSONB DEFAULT '[]',
                power_system TEXT,
                technology_level TEXT,
                history TEXT,
                geography TEXT,
                factions JSONB DEFAULT '[]',
                metadata JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_worlds_project_id ON worlds(project_id);
            CREATE INDEX IF NOT EXISTS idx_worlds_project_parent ON worlds(project_id, parent_world_id);
            CREATE INDEX IF NOT EXISTS idx_worlds_project_default ON worlds(project_id, is_default);
            CREATE INDEX IF NOT EXISTS idx_worlds_scope_type ON worlds(scope_type);
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
                metadata JSONB NOT NULL DEFAULT '{}',
                state TEXT DEFAULT 'normal',
                state_summary TEXT,
                destroyed_at TIMESTAMP WITH TIME ZONE,
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

        # 领域剧情事件表
        if 'events' not in existing_tables:
            tables_to_create.append("""
            CREATE TABLE events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                world_id UUID REFERENCES worlds(id) ON DELETE SET NULL,
                chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
                event_id TEXT,
                event_name TEXT NOT NULL,
                event_type TEXT DEFAULT 'custom',
                status TEXT DEFAULT 'planned',
                description TEXT,
                trigger_condition TEXT,
                participants JSONB DEFAULT '[]',
                consequences JSONB DEFAULT '[]',
                effects JSONB DEFAULT '[]',
                related_regions JSONB DEFAULT '[]',
                related_locations JSONB DEFAULT '[]',
                narrative_purpose TEXT,
                suggested_chapter TEXT,
                source TEXT DEFAULT 'workflow',
                workflow_execution_id TEXT,
                workflow_id TEXT,
                node_id TEXT,
                agent_type TEXT,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_events_project_created ON events(project_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_events_project_type ON events(project_id, event_type);
            CREATE INDEX IF NOT EXISTS idx_events_project_status ON events(project_id, status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_events_project_event_id ON events(project_id, event_id) WHERE event_id IS NOT NULL;
            """)

        # 剧情状态变更表
        if 'narrative_state_changes' not in existing_tables:
            tables_to_create.append("""
            CREATE TABLE narrative_state_changes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                world_id UUID REFERENCES worlds(id) ON DELETE SET NULL,
                scope_type TEXT,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                entity_name TEXT,
                change_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposed',
                confirmation_required BOOLEAN NOT NULL DEFAULT TRUE,
                title TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                before_state JSONB NOT NULL DEFAULT '{}',
                after_state JSONB NOT NULL DEFAULT '{}',
                diff JSONB NOT NULL DEFAULT '{}',
                metadata JSONB NOT NULL DEFAULT '{}',
                workflow_execution_id TEXT,
                workflow_id TEXT,
                node_id TEXT,
                agent_type TEXT,
                chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
                discussion_id TEXT,
                source_text TEXT,
                fingerprint TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP WITH TIME ZONE,
                applied_at TIMESTAMP WITH TIME ZONE,
                rejected_at TIMESTAMP WITH TIME ZONE
            );
            CREATE INDEX IF NOT EXISTS idx_narrative_state_changes_project_created ON narrative_state_changes(project_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_narrative_state_changes_entity ON narrative_state_changes(project_id, entity_type, entity_id);
            CREATE INDEX IF NOT EXISTS idx_narrative_state_changes_status ON narrative_state_changes(project_id, status);
            CREATE INDEX IF NOT EXISTS idx_narrative_state_changes_project_world_status ON narrative_state_changes(project_id, world_id, status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_narrative_state_changes_fingerprint ON narrative_state_changes(project_id, fingerprint) WHERE fingerprint IS NOT NULL;
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

            event_schema_sql = """
            CREATE TABLE IF NOT EXISTS events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                world_id UUID REFERENCES worlds(id) ON DELETE SET NULL,
                chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
                event_id TEXT,
                event_name TEXT NOT NULL,
                event_type TEXT DEFAULT 'custom',
                status TEXT DEFAULT 'planned',
                description TEXT,
                trigger_condition TEXT,
                participants JSONB DEFAULT '[]',
                consequences JSONB DEFAULT '[]',
                effects JSONB DEFAULT '[]',
                related_regions JSONB DEFAULT '[]',
                related_locations JSONB DEFAULT '[]',
                narrative_purpose TEXT,
                suggested_chapter TEXT,
                source TEXT DEFAULT 'workflow',
                workflow_execution_id TEXT,
                workflow_id TEXT,
                node_id TEXT,
                agent_type TEXT,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_events_project_created ON events(project_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_events_project_type ON events(project_id, event_type);
            CREATE INDEX IF NOT EXISTS idx_events_project_status ON events(project_id, status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_events_project_event_id ON events(project_id, event_id) WHERE event_id IS NOT NULL;
            """
            for statement in event_schema_sql.split(';'):
                if statement.strip():
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"创建领域剧情事件表结构时出错: {str(e)[:100]}")

            resource_requirement_schema_sql = """
            CREATE TABLE IF NOT EXISTS outline_resource_requirements (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                outline_id TEXT,
                outline_version_id TEXT,
                chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
                chapter_num INTEGER,
                requirement_type TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'advisory',
                status TEXT NOT NULL DEFAULT 'pending',
                reason TEXT NOT NULL DEFAULT '',
                suggested_payload JSONB NOT NULL DEFAULT '{}',
                matched_resource_id TEXT,
                matched_resource_type TEXT,
                source_excerpt TEXT,
                source_agent TEXT,
                source_node_id TEXT,
                source_execution_id TEXT,
                fingerprint TEXT,
                metadata JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP WITH TIME ZONE
            );
            CREATE INDEX IF NOT EXISTS idx_outline_resource_requirements_project ON outline_resource_requirements(project_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_outline_resource_requirements_outline ON outline_resource_requirements(project_id, outline_id, chapter_num);
            CREATE INDEX IF NOT EXISTS idx_outline_resource_requirements_status ON outline_resource_requirements(project_id, status, severity);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_outline_resource_requirements_fingerprint ON outline_resource_requirements(project_id, fingerprint) WHERE fingerprint IS NOT NULL;

            CREATE TABLE IF NOT EXISTS chapter_resource_readiness (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                outline_id TEXT,
                outline_version_id TEXT,
                chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
                chapter_num INTEGER NOT NULL,
                blocking_total INTEGER NOT NULL DEFAULT 0,
                blocking_resolved INTEGER NOT NULL DEFAULT 0,
                advisory_total INTEGER NOT NULL DEFAULT 0,
                advisory_resolved INTEGER NOT NULL DEFAULT 0,
                readiness_status TEXT NOT NULL DEFAULT 'not_audited',
                last_audited_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_chapter_resource_readiness_project ON chapter_resource_readiness(project_id, chapter_num);
            CREATE INDEX IF NOT EXISTS idx_chapter_resource_readiness_status ON chapter_resource_readiness(project_id, readiness_status);
            CREATE INDEX IF NOT EXISTS idx_chapter_resource_readiness_outline ON chapter_resource_readiness(project_id, outline_id, chapter_num);
            """
            for statement in resource_requirement_schema_sql.split(';'):
                if statement.strip():
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"创建大纲资源需求表结构时出错: {str(e)[:100]}")

            operation_schema_sql = """
            CREATE TABLE IF NOT EXISTS operation_requests (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                request_id TEXT NOT NULL UNIQUE,
                operation_type TEXT NOT NULL,
                project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
                resource_type TEXT,
                resource_id TEXT,
                request_hash TEXT NOT NULL,
                trace_id UUID,
                status TEXT NOT NULL DEFAULT 'pending',
                response_payload JSONB DEFAULT '{}',
                error TEXT,
                lease_token TEXT,
                lease_expires_at TIMESTAMP WITH TIME ZONE,
                last_heartbeat_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP WITH TIME ZONE
            );
            CREATE INDEX IF NOT EXISTS idx_operation_requests_project ON operation_requests(project_id);
            CREATE INDEX IF NOT EXISTS idx_operation_requests_resource ON operation_requests(operation_type, project_id, resource_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_operation_requests_active_hash
                ON operation_requests(operation_type, project_id, resource_id, request_hash)
                WHERE status IN ('pending', 'running', 'paused');
            """
            for statement in operation_schema_sql.split(';'):
                if statement.strip():
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"创建操作请求表结构时出错: {str(e)[:100]}")

            trace_schema_sql = """
            CREATE TABLE IF NOT EXISTS execution_traces (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
                operation_id UUID REFERENCES operation_requests(id) ON DELETE SET NULL,
                request_id TEXT,
                workflow_id TEXT,
                workflow_execution_id TEXT,
                trace_type TEXT NOT NULL,
                root_name TEXT,
                status TEXT NOT NULL DEFAULT 'running',
                root_input_summary JSONB DEFAULT '{}',
                metadata JSONB DEFAULT '{}',
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP WITH TIME ZONE,
                duration_ms INTEGER,
                error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_execution_traces_execution ON execution_traces(workflow_execution_id);
            CREATE INDEX IF NOT EXISTS idx_execution_traces_project_started ON execution_traces(project_id, started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_execution_traces_operation ON execution_traces(operation_id);
            CREATE TABLE IF NOT EXISTS execution_trace_spans (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                trace_id UUID NOT NULL REFERENCES execution_traces(id) ON DELETE CASCADE,
                parent_span_id UUID REFERENCES execution_trace_spans(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                workflow_id TEXT,
                workflow_execution_id TEXT,
                node_id TEXT,
                agent_type TEXT,
                attributes JSONB DEFAULT '{}',
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP WITH TIME ZONE,
                duration_ms INTEGER,
                error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_execution_trace_spans_trace ON execution_trace_spans(trace_id, started_at ASC);
            CREATE INDEX IF NOT EXISTS idx_execution_trace_spans_parent ON execution_trace_spans(parent_span_id);
            CREATE TABLE IF NOT EXISTS execution_trace_events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                trace_id UUID NOT NULL REFERENCES execution_traces(id) ON DELETE CASCADE,
                span_id UUID REFERENCES execution_trace_spans(id) ON DELETE SET NULL,
                sequence BIGSERIAL,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                payload JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_execution_trace_events_trace_sequence ON execution_trace_events(trace_id, sequence ASC);
            CREATE INDEX IF NOT EXISTS idx_execution_trace_events_span ON execution_trace_events(span_id, created_at ASC);
            CREATE TABLE IF NOT EXISTS execution_trace_artifacts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                trace_id UUID NOT NULL REFERENCES execution_traces(id) ON DELETE CASCADE,
                span_id UUID REFERENCES execution_trace_spans(id) ON DELETE SET NULL,
                kind TEXT NOT NULL,
                content_type TEXT DEFAULT 'json',
                content JSONB,
                text_content TEXT,
                content_hash TEXT,
                size_bytes INTEGER,
                redaction_status TEXT DEFAULT 'none',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_execution_trace_artifacts_trace ON execution_trace_artifacts(trace_id, created_at ASC);
            CREATE INDEX IF NOT EXISTS idx_execution_trace_artifacts_span ON execution_trace_artifacts(span_id, created_at ASC);
            """
            for statement in trace_schema_sql.split(';'):
                if statement.strip():
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"创建 Trace 表结构时出错: {str(e)[:100]}")

            operation_trace_updates = [
                "ALTER TABLE operation_requests ADD COLUMN IF NOT EXISTS trace_id UUID REFERENCES execution_traces(id) ON DELETE SET NULL",
                "CREATE INDEX IF NOT EXISTS idx_operation_requests_trace ON operation_requests(trace_id)",
            ]
            for statement in operation_trace_updates:
                try:
                    await session.execute(text(statement))
                except Exception as e:
                    logger.warning(f"更新操作请求 Trace 字段时出错: {str(e)[:100]}")

            workflow_schema_updates = [
                "ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS operation_id UUID REFERENCES operation_requests(id) ON DELETE SET NULL",
                "ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS trace_id UUID REFERENCES execution_traces(id) ON DELETE SET NULL",
                "ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS request_id TEXT",
                "ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS request_hash TEXT",
                "ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS director_session_id TEXT",
                "ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS lease_token TEXT",
                "ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS cancel_requested BOOLEAN DEFAULT FALSE",
                "ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS resume_cursor JSONB DEFAULT '{}'",
                "CREATE INDEX IF NOT EXISTS idx_workflow_executions_project_workflow_status ON workflow_executions(project_id, workflow_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_workflow_executions_active_project ON workflow_executions(project_id, status, last_heartbeat_at DESC, started_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_workflow_executions_active_project_workflow ON workflow_executions(project_id, workflow_id, status, last_heartbeat_at DESC, started_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_workflow_executions_active_director_session ON workflow_executions(project_id, workflow_id, director_session_id, status, last_heartbeat_at DESC, started_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_workflow_executions_request ON workflow_executions(request_id)",
                "CREATE INDEX IF NOT EXISTS idx_workflow_executions_trace ON workflow_executions(trace_id)",
            ]
            if 'workflow_executions' in existing_tables:
                for statement in workflow_schema_updates:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"更新工作流执行表结构时出错: {str(e)[:100]}")

            event_and_session_schema_sql = """
            CREATE TABLE IF NOT EXISTS workflow_execution_events (
                id BIGSERIAL PRIMARY KEY,
                execution_id VARCHAR(64) REFERENCES workflow_executions(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                event_data JSONB DEFAULT '{}',
                sequence_no BIGINT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_execution_events_sequence ON workflow_execution_events(execution_id, sequence_no);
            CREATE INDEX IF NOT EXISTS idx_workflow_execution_events_created ON workflow_execution_events(execution_id, created_at);
            CREATE TABLE IF NOT EXISTS bootstrap_sessions (
                id TEXT PRIMARY KEY,
                project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                current_stage TEXT NOT NULL,
                progress DOUBLE PRECISION DEFAULT 0,
                setting_agent_history JSONB DEFAULT '[]',
                extracted_seed JSONB DEFAULT '{}',
                confirmed_seed JSONB DEFAULT '{}',
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP WITH TIME ZONE
            );
            CREATE INDEX IF NOT EXISTS idx_bootstrap_sessions_project ON bootstrap_sessions(project_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_bootstrap_sessions_active_project
                ON bootstrap_sessions(project_id)
                WHERE status NOT IN ('completed', 'failed');
            CREATE TABLE IF NOT EXISTS setting_agent_sessions (
                id TEXT PRIMARY KEY,
                project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
                mode TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                conversation_snapshot JSONB DEFAULT '[]',
                pending_conflicts JSONB DEFAULT '[]',
                cached_pending_lores JSONB DEFAULT '[]',
                cached_pending_characters JSONB DEFAULT '[]',
                cached_pending_hooks JSONB DEFAULT '[]',
                cached_context_sections JSONB DEFAULT '{}',
                full_context_loaded BOOLEAN DEFAULT FALSE,
                last_activity_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_setting_agent_sessions_project ON setting_agent_sessions(project_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_setting_agent_sessions_active_project_mode ON setting_agent_sessions(project_id, mode) WHERE status = 'active';
            CREATE TABLE IF NOT EXISTS setting_agent_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id TEXT REFERENCES setting_agent_sessions(id) ON DELETE CASCADE,
                request_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_setting_agent_messages_session_created ON setting_agent_messages(session_id, created_at);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_setting_agent_messages_request_role ON setting_agent_messages(session_id, request_id, role) WHERE request_id IS NOT NULL;
            CREATE TABLE IF NOT EXISTS setting_agent_pending_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id TEXT REFERENCES setting_agent_sessions(id) ON DELETE CASCADE,
                request_id TEXT,
                item_type TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                payload JSONB NOT NULL DEFAULT '{}',
                status TEXT DEFAULT 'pending',
                saved_ref_id TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_setting_agent_pending_items_session ON setting_agent_pending_items(session_id, status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_setting_agent_pending_items_fingerprint ON setting_agent_pending_items(session_id, item_type, fingerprint);
            """
            for statement in event_and_session_schema_sql.split(';'):
                if statement.strip():
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"创建执行事件/Setting Agent 会话表结构时出错: {str(e)[:100]}")

            graph_projection_schema_sql = """
            CREATE TABLE IF NOT EXISTS graph_projection_jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                idempotency_key TEXT NOT NULL UNIQUE,
                project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
                source_entity_type TEXT NOT NULL,
                source_entity_id TEXT NOT NULL,
                projection_type TEXT NOT NULL,
                operation TEXT NOT NULL DEFAULT 'upsert',
                payload JSONB NOT NULL DEFAULT '{}',
                content_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                available_at TIMESTAMP WITH TIME ZONE,
                worker_id TEXT,
                claimed_at TIMESTAMP WITH TIME ZONE,
                lease_expires_at TIMESTAMP WITH TIME ZONE,
                next_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP WITH TIME ZONE
            );
            CREATE INDEX IF NOT EXISTS idx_graph_projection_jobs_status_created
                ON graph_projection_jobs(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_graph_projection_jobs_project_status
                ON graph_projection_jobs(project_id, status);
            CREATE INDEX IF NOT EXISTS idx_graph_projection_jobs_entity
                ON graph_projection_jobs(source_entity_type, source_entity_id);
            """
            for statement in graph_projection_schema_sql.split(';'):
                if statement.strip():
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"创建关系图投影任务表结构时出错: {str(e)[:100]}")

            graph_projection_schema_updates = [
                "ALTER TABLE graph_projection_jobs ADD COLUMN IF NOT EXISTS worker_id TEXT",
                "ALTER TABLE graph_projection_jobs ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE graph_projection_jobs ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE graph_projection_jobs ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            ]
            for statement in graph_projection_schema_updates:
                try:
                    await session.execute(text(statement))
                except Exception as e:
                    logger.warning(f"更新关系图投影任务表结构时出错: {str(e)[:100]}")

            chapter_schema_updates = [
                "ALTER TABLE chapters ADD COLUMN IF NOT EXISTS chapter_outline_id TEXT",
                "ALTER TABLE chapters ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
                "CREATE INDEX IF NOT EXISTS idx_chapters_outline_id ON chapters(chapter_outline_id)",
                "CREATE INDEX IF NOT EXISTS idx_chapters_deleted_at ON chapters(deleted_at)",
            ]
            if 'chapters' in existing_tables:
                for statement in chapter_schema_updates:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"更新章节表软删除结构时出错: {str(e)[:100]}")

            chapter_outline_schema_updates = [
                "ALTER TABLE chapter_outlines ADD COLUMN IF NOT EXISTS previous_outline_id VARCHAR(64)",
                "ALTER TABLE chapter_outlines ADD COLUMN IF NOT EXISTS next_outline_id VARCHAR(64)",
                "ALTER TABLE chapter_outlines DROP CONSTRAINT IF EXISTS chapter_outlines_project_id_chapter_number_key",
                "DROP INDEX IF EXISTS chapter_outlines_project_id_chapter_number_key",
                "CREATE INDEX IF NOT EXISTS idx_chapter_outlines_project_chapter ON chapter_outlines(project_id, chapter_number)",
                "CREATE INDEX IF NOT EXISTS idx_chapter_outlines_previous ON chapter_outlines(previous_outline_id)",
                "CREATE INDEX IF NOT EXISTS idx_chapter_outlines_next ON chapter_outlines(next_outline_id)",
            ]
            if 'chapter_outlines' in existing_tables:
                for statement in chapter_outline_schema_updates:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"更新章节大纲版本结构时出错: {str(e)[:100]}")

            project_schema_updates = [
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS user_id TEXT",
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'draft'",
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS world_id UUID REFERENCES worlds(id) ON DELETE SET NULL",
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS total_tokens INTEGER DEFAULT 0",
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS total_cost DOUBLE PRECISION DEFAULT 0",
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'",
            ]
            if 'projects' in existing_tables:
                for statement in project_schema_updates:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"更新项目表结构时出错: {str(e)[:100]}")

            agent_config_schema_updates = [
                "ALTER TABLE agent_templates ADD COLUMN IF NOT EXISTS scenario TEXT DEFAULT 'default'",
                "ALTER TABLE agent_configs ADD COLUMN IF NOT EXISTS scenario TEXT DEFAULT 'default'",
                "ALTER TABLE skill_assignments ADD COLUMN IF NOT EXISTS scenario TEXT DEFAULT 'default'",
                "ALTER TABLE skill_assignments ADD COLUMN IF NOT EXISTS slot_name TEXT DEFAULT ''",
                "ALTER TABLE skill_assignments ADD COLUMN IF NOT EXISTS is_required BOOLEAN DEFAULT FALSE",
                "ALTER TABLE skill_assignments ADD COLUMN IF NOT EXISTS variable_overrides JSONB DEFAULT '{}'",
                "ALTER TABLE skill_assignments ADD COLUMN IF NOT EXISTS execution_condition TEXT",
                "ALTER TABLE skill_assignments ADD COLUMN IF NOT EXISTS assigned_by TEXT DEFAULT 'user'",
                "ALTER TABLE skill_assignments ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
                "ALTER TABLE skill_assignments DROP CONSTRAINT IF EXISTS skill_assignments_skill_id_agent_type_slot_name_key",
                "DROP INDEX IF EXISTS skill_assignments_skill_id_agent_type_slot_name_key",
                "DROP INDEX IF EXISTS uq_skill_assignments_skill_agent_scenario_slot",
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_skill_assignments_skill_agent_scenario_slot ON skill_assignments(skill_id, agent_type, scenario, slot_name)",
            ]
            if 'agent_templates' in existing_tables or 'agent_configs' in existing_tables or 'skill_assignments' in existing_tables:
                for statement in agent_config_schema_updates:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"更新 Agent 配置表结构时出错: {str(e)[:100]}")

            world_schema_updates = [
                "ALTER TABLE worlds ADD COLUMN IF NOT EXISTS content_styles JSONB DEFAULT '[]'",
                "ALTER TABLE worlds ADD COLUMN IF NOT EXISTS protagonist_types JSONB DEFAULT '[]'",
                "ALTER TABLE worlds ADD COLUMN IF NOT EXISTS character_archetypes JSONB DEFAULT '[]'",
                "ALTER TABLE worlds ADD COLUMN IF NOT EXISTS power_types JSONB DEFAULT '[]'",
                "ALTER TABLE worlds ADD COLUMN IF NOT EXISTS parent_world_id UUID REFERENCES worlds(id) ON DELETE SET NULL",
                "ALTER TABLE worlds ADD COLUMN IF NOT EXISTS scope_type TEXT NOT NULL DEFAULT 'root'",
                "ALTER TABLE worlds ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE",
                "ALTER TABLE worlds ADD COLUMN IF NOT EXISTS inherit_rules BOOLEAN NOT NULL DEFAULT TRUE",
                "ALTER TABLE worlds ADD COLUMN IF NOT EXISTS order_index INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE worlds ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'",
                "CREATE INDEX IF NOT EXISTS idx_worlds_project_parent ON worlds(project_id, parent_world_id)",
                "CREATE INDEX IF NOT EXISTS idx_worlds_project_default ON worlds(project_id, is_default)",
                "CREATE INDEX IF NOT EXISTS idx_worlds_scope_type ON worlds(scope_type)",
            ]
            if 'worlds' in existing_tables or any('CREATE TABLE worlds' in sql for sql in tables_to_create):
                for statement in world_schema_updates:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"更新世界表层级结构时出错: {str(e)[:100]}")

            hook_schema_updates = [
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS title VARCHAR(500) NOT NULL DEFAULT ''",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS world_id UUID REFERENCES worlds(id) ON DELETE SET NULL",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'planted'",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS related_characters JSONB DEFAULT '[]'",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS related_locations JSONB DEFAULT '[]'",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS related_objects JSONB DEFAULT '[]'",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS plant_context TEXT",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS plant_chapter UUID REFERENCES chapters(id) ON DELETE SET NULL",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS resolution_hint TEXT",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS resolution_context TEXT",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS resolution_chapter UUID REFERENCES chapters(id) ON DELETE SET NULL",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 3",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS scope_type TEXT NOT NULL DEFAULT 'project'",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS character_id UUID REFERENCES characters(id) ON DELETE SET NULL",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS parent_hook_id UUID REFERENCES hooks(id) ON DELETE SET NULL",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS promoted_from_hook_id UUID REFERENCES hooks(id) ON DELETE SET NULL",
                "ALTER TABLE hooks ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'global'",
                "CREATE INDEX IF NOT EXISTS idx_hooks_project_world ON hooks(project_id, world_id)",
                "CREATE INDEX IF NOT EXISTS idx_hooks_scope ON hooks(project_id, scope_type)",
                "CREATE INDEX IF NOT EXISTS idx_hooks_character_id ON hooks(character_id)",
            ]
            if 'hooks' in existing_tables or any('hooks' in sql for sql in tables_to_create):
                for statement in hook_schema_updates:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"更新伏笔表作用域结构时出错: {str(e)[:100]}")
                hook_jsonb_migration = """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'hooks'
                          AND column_name = 'related_characters'
                          AND data_type <> 'jsonb'
                    ) THEN
                        ALTER TABLE hooks
                        ALTER COLUMN related_characters DROP DEFAULT,
                        ALTER COLUMN related_characters TYPE JSONB
                        USING COALESCE(to_jsonb(related_characters), '[]'::jsonb),
                        ALTER COLUMN related_characters SET DEFAULT '[]'::jsonb;
                    END IF;

                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'hooks'
                          AND column_name = 'related_locations'
                          AND data_type <> 'jsonb'
                    ) THEN
                        ALTER TABLE hooks
                        ALTER COLUMN related_locations DROP DEFAULT,
                        ALTER COLUMN related_locations TYPE JSONB
                        USING COALESCE(to_jsonb(related_locations), '[]'::jsonb),
                        ALTER COLUMN related_locations SET DEFAULT '[]'::jsonb;
                    END IF;

                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'hooks'
                          AND column_name = 'related_objects'
                          AND data_type <> 'jsonb'
                    ) THEN
                        ALTER TABLE hooks
                        ALTER COLUMN related_objects DROP DEFAULT,
                        ALTER COLUMN related_objects TYPE JSONB
                        USING COALESCE(to_jsonb(related_objects), '[]'::jsonb),
                        ALTER COLUMN related_objects SET DEFAULT '[]'::jsonb;
                    END IF;
                END $$
                """
                try:
                    await session.execute(text(hook_jsonb_migration))
                except Exception as e:
                    logger.warning(f"迁移伏笔关联字段为 JSONB 时出错: {str(e)[:100]}")

            character_world_profile_schema = """
            CREATE TABLE IF NOT EXISTS character_world_profiles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                world_id UUID NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                local_name TEXT,
                local_identity TEXT,
                local_role TEXT,
                local_status TEXT,
                local_abilities JSONB DEFAULT '[]',
                local_relationships JSONB DEFAULT '{}',
                current_region_id UUID REFERENCES regions(id) ON DELETE SET NULL,
                entry_chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
                exit_chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
                memory_state JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(character_id, world_id)
            );
            CREATE INDEX IF NOT EXISTS idx_character_world_profiles_project ON character_world_profiles(project_id);
            CREATE INDEX IF NOT EXISTS idx_character_world_profiles_world ON character_world_profiles(world_id);
            """
            for statement in character_world_profile_schema.split(';'):
                if statement.strip():
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"创建角色世界身份表结构时出错: {str(e)[:100]}")

            narrative_scope_updates = [
                "ALTER TABLE narrative_state_changes ADD COLUMN IF NOT EXISTS world_id UUID REFERENCES worlds(id) ON DELETE SET NULL",
                "ALTER TABLE narrative_state_changes ADD COLUMN IF NOT EXISTS scope_type TEXT",
                "CREATE INDEX IF NOT EXISTS idx_narrative_state_changes_project_world_status ON narrative_state_changes(project_id, world_id, status)",
            ]
            if 'narrative_state_changes' in existing_tables or any('narrative_state_changes' in sql for sql in tables_to_create):
                for statement in narrative_scope_updates:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"更新剧情状态变更作用域结构时出错: {str(e)[:100]}")

            region_schema_updates = [
                "ALTER TABLE regions ADD COLUMN IF NOT EXISTS state TEXT DEFAULT 'normal'",
                "ALTER TABLE regions ADD COLUMN IF NOT EXISTS state_summary TEXT",
                "ALTER TABLE regions ADD COLUMN IF NOT EXISTS destroyed_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE regions ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'",
            ]
            if 'regions' in existing_tables or tables_to_create:
                for statement in region_schema_updates:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"更新区域表结构时出错: {str(e)[:100]}")

            state_change_schema_updates = [
                "ALTER TABLE narrative_state_changes ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'",
                "ALTER TABLE narrative_state_changes ADD COLUMN IF NOT EXISTS workflow_execution_id TEXT",
                "ALTER TABLE narrative_state_changes ADD COLUMN IF NOT EXISTS workflow_id TEXT",
                "ALTER TABLE narrative_state_changes ADD COLUMN IF NOT EXISTS node_id TEXT",
                "ALTER TABLE narrative_state_changes ADD COLUMN IF NOT EXISTS agent_type TEXT",
                "ALTER TABLE narrative_state_changes ADD COLUMN IF NOT EXISTS chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL",
                "ALTER TABLE narrative_state_changes ADD COLUMN IF NOT EXISTS discussion_id TEXT",
                "ALTER TABLE narrative_state_changes ADD COLUMN IF NOT EXISTS source_text TEXT",
                "CREATE INDEX IF NOT EXISTS idx_narrative_state_changes_project_created ON narrative_state_changes(project_id, created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_narrative_state_changes_entity ON narrative_state_changes(project_id, entity_type, entity_id)",
                "CREATE INDEX IF NOT EXISTS idx_narrative_state_changes_status ON narrative_state_changes(project_id, status)",
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_narrative_state_changes_fingerprint ON narrative_state_changes(project_id, fingerprint) WHERE fingerprint IS NOT NULL",
            ]
            if 'narrative_state_changes' in existing_tables or any('narrative_state_changes' in sql for sql in tables_to_create):
                for statement in state_change_schema_updates:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"更新剧情状态变更表结构时出错: {str(e)[:100]}")

            character_schema_updates = [
                "ALTER TABLE characters ADD COLUMN IF NOT EXISTS world_id UUID REFERENCES worlds(id) ON DELETE SET NULL",
                "ALTER TABLE characters ADD COLUMN IF NOT EXISTS current_location TEXT",
                "ALTER TABLE characters ADD COLUMN IF NOT EXISTS current_region_id UUID REFERENCES regions(id) ON DELETE SET NULL",
                "ALTER TABLE characters ADD COLUMN IF NOT EXISTS current_location_reason TEXT DEFAULT ''",
                "ALTER TABLE characters ADD COLUMN IF NOT EXISTS death_detail JSONB",
                "ALTER TABLE characters ADD COLUMN IF NOT EXISTS available_presence_types JSONB DEFAULT '[\"present\"]'::jsonb",
                "CREATE INDEX IF NOT EXISTS idx_characters_world_id ON characters(world_id)",
                "CREATE INDEX IF NOT EXISTS idx_characters_current_region_id ON characters(current_region_id)",
            ]
            if 'characters' in existing_tables or tables_to_create:
                for statement in character_schema_updates:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"更新角色表结构时出错: {str(e)[:100]}")
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

    # ==================== v8 工作流相关操作 ====================

    async def save_workflow_definition(self, workflow_data: Dict[str, Any]) -> str:
        """
        保存工作流定义

        Args:
            workflow_data: 工作流定义数据

        Returns:
            str: 工作流 ID
        """
        # 验证 UUID 字段
        workflow_data['project_id'] = _validate_uuid(workflow_data.get('project_id'))

        # 处理 JSON 字段
        json_fields = ['nodes', 'edges', 'variables']
        for field in json_fields:
            if field in workflow_data and workflow_data[field] is not None:
                value = workflow_data[field]
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except:
                        value = [] if field != 'variables' else {}
                if isinstance(value, (list, dict)):
                    workflow_data[field] = json.dumps(value)

        # 处理时间字段
        for field in ['created_at', 'updated_at']:
            if field in workflow_data and isinstance(workflow_data[field], str):
                try:
                    workflow_data[field] = datetime.fromisoformat(
                        workflow_data[field].replace('Z', '+00:00')
                    )
                except:
                    workflow_data[field] = datetime.now()
            elif field not in workflow_data or workflow_data[field] is None:
                workflow_data[field] = datetime.now()

        # 动态构建 SQL
        project_id_sql = "CAST(:project_id AS UUID)" if workflow_data.get('project_id') else "NULL"

        query = """
        INSERT INTO workflow_definitions (id, project_id, name, description, nodes, edges, variables, is_template, created_at, updated_at)
        VALUES (:id, """ + project_id_sql + """, :name, :description, :nodes, :edges, :variables, :is_template, :created_at, :updated_at)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            nodes = EXCLUDED.nodes,
            edges = EXCLUDED.edges,
            variables = EXCLUDED.variables,
            is_template = EXCLUDED.is_template,
            updated_at = EXCLUDED.updated_at
        """
        await self.execute_write(query, workflow_data)
        return workflow_data.get("id", "")

    async def get_workflow_definition(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        获取工作流定义

        Args:
            workflow_id: 工作流 ID

        Returns:
            Optional[Dict]: 工作流定义
        """
        query = "SELECT * FROM workflow_definitions WHERE id = :id"
        results = await self.execute_query(query, {"id": workflow_id})
        return results[0] if results else None

    async def get_all_workflows(
        self,
        project_id: str,
        include_templates: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        获取工作流列表

        Args:
            project_id: 项目 ID
            include_templates: 是否包含模板

        Returns:
            List: 工作流列表
        """
        if include_templates:
            query = """
            SELECT * FROM workflow_definitions
            WHERE project_id = :project_id OR is_template = true
            ORDER BY created_at DESC
            """
        else:
            query = """
            SELECT * FROM workflow_definitions
            WHERE project_id = :project_id
            ORDER BY created_at DESC
            """
        return await self.execute_query(query, {"project_id": project_id})

    async def delete_workflow_definition(self, workflow_id: str) -> bool:
        """
        删除工作流定义

        Args:
            workflow_id: 工作流 ID

        Returns:
            bool: 是否成功
        """
        query = "DELETE FROM workflow_definitions WHERE id = :id"
        await self.execute_write(query, {"id": workflow_id})
        return True

    async def save_workflow_execution(self, execution_data: Dict[str, Any]) -> str:
        """
        保存工作流执行记录

        Args:
            execution_data: 执行记录数据

        Returns:
            str: 执行 ID
        """
        # 验证 UUID 字段
        execution_data['project_id'] = _validate_uuid(execution_data.get('project_id'))

        # 处理 JSON 字段
        json_fields = ['node_states', 'context', 'intervention_ids', 'resume_cursor']
        for field in json_fields:
            if field in execution_data and execution_data[field] is not None:
                value = execution_data[field]
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except:
                        value = {} if field != 'intervention_ids' else []
                if isinstance(value, (list, dict)):
                    execution_data[field] = json.dumps(value)

        # 处理时间字段
        for field in ['started_at', 'completed_at', 'lease_expires_at', 'last_heartbeat_at']:
            if field in execution_data and isinstance(execution_data[field], str):
                try:
                    execution_data[field] = datetime.fromisoformat(
                        execution_data[field].replace('Z', '+00:00')
                    )
                except:
                    execution_data[field] = None

        # 动态构建 SQL
        project_id_sql = "CAST(:project_id AS UUID)" if execution_data.get('project_id') else "NULL"

        execution_data.setdefault('operation_id', None)
        execution_data.setdefault('trace_id', None)
        execution_data.setdefault('request_id', None)
        execution_data.setdefault('request_hash', None)
        execution_data.setdefault('director_session_id', None)
        execution_data.setdefault('lease_token', None)
        execution_data.setdefault('lease_expires_at', None)
        execution_data.setdefault('last_heartbeat_at', None)
        execution_data.setdefault('cancel_requested', False)
        execution_data.setdefault('resume_cursor', {})
        operation_id_sql = "CAST(:operation_id AS UUID)" if execution_data.get('operation_id') else "NULL"
        trace_id_sql = "CAST(:trace_id AS UUID)" if execution_data.get('trace_id') else "NULL"

        query = """
        INSERT INTO workflow_executions (
            id, workflow_id, project_id, operation_id, trace_id, request_id, request_hash, director_session_id,
            status, current_node, node_states, context, intervention_ids,
            lease_token, lease_expires_at, last_heartbeat_at, cancel_requested, resume_cursor,
            started_at, completed_at, total_duration_ms, error
        )
        VALUES (
            :id, :workflow_id, """ + project_id_sql + ", " + operation_id_sql + ", " + trace_id_sql + """, :request_id, :request_hash, :director_session_id,
            :status, :current_node, :node_states, :context, :intervention_ids,
            :lease_token, :lease_expires_at, :last_heartbeat_at, :cancel_requested, :resume_cursor,
            :started_at, :completed_at, :total_duration_ms, :error
        )
        ON CONFLICT (id) DO UPDATE SET
            operation_id = EXCLUDED.operation_id,
            trace_id = EXCLUDED.trace_id,
            request_id = EXCLUDED.request_id,
            request_hash = EXCLUDED.request_hash,
            director_session_id = EXCLUDED.director_session_id,
            status = EXCLUDED.status,
            current_node = EXCLUDED.current_node,
            node_states = EXCLUDED.node_states,
            context = EXCLUDED.context,
            intervention_ids = EXCLUDED.intervention_ids,
            lease_token = EXCLUDED.lease_token,
            lease_expires_at = EXCLUDED.lease_expires_at,
            last_heartbeat_at = EXCLUDED.last_heartbeat_at,
            cancel_requested = EXCLUDED.cancel_requested,
            resume_cursor = EXCLUDED.resume_cursor,
            completed_at = EXCLUDED.completed_at,
            total_duration_ms = EXCLUDED.total_duration_ms,
            error = EXCLUDED.error
        """
        await self.execute_write(query, execution_data)
        return execution_data.get("id", "")

    async def get_workflow_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        获取工作流执行记录

        Args:
            execution_id: 执行 ID

        Returns:
            Optional[Dict]: 执行记录
        """
        query = "SELECT * FROM workflow_executions WHERE id = :id"
        results = await self.execute_query(query, {"id": execution_id})
        return results[0] if results else None

    async def get_active_workflow_execution(
        self,
        project_id: str,
        workflow_id: Optional[str] = None,
        director_session_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """获取项目/工作流当前活跃执行。"""
        conditions = ["project_id = :project_id", "status IN ('pending', 'running', 'paused')"]
        params: Dict[str, Any] = {"project_id": project_id}
        if workflow_id:
            conditions.append("workflow_id = :workflow_id")
            params["workflow_id"] = workflow_id
        if director_session_id:
            conditions.append("director_session_id = :director_session_id")
            params["director_session_id"] = director_session_id

        query = f"""
        SELECT * FROM workflow_executions
        WHERE {' AND '.join(conditions)}
        ORDER BY
            CASE status
                WHEN 'running' THEN 1
                WHEN 'paused' THEN 2
                WHEN 'pending' THEN 3
                ELSE 4
            END ASC,
            CASE
                WHEN lease_expires_at IS NOT NULL AND lease_expires_at > CURRENT_TIMESTAMP THEN 0
                ELSE 1
            END ASC,
            COALESCE(last_heartbeat_at, started_at) DESC,
            started_at DESC,
            id DESC
        LIMIT 1
        """
        results = await self.execute_query(query, params)
        return results[0] if results else None

    async def append_workflow_execution_event(
        self,
        execution_id: str,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> int:
        """追加工作流执行事件并返回 sequence_no。"""
        if isinstance(event_data, str):
            payload = event_data
        else:
            payload = json.dumps(event_data, default=str)
        query = """
        WITH next_seq AS (
            SELECT COALESCE(MAX(sequence_no), 0) + 1 AS sequence_no
            FROM workflow_execution_events
            WHERE execution_id = :execution_id
        )
        INSERT INTO workflow_execution_events (execution_id, event_type, event_data, sequence_no)
        SELECT :execution_id, :event_type, :event_data, sequence_no FROM next_seq
        RETURNING sequence_no
        """
        async with self._workflow_event_locks[execution_id]:
            results = await self.execute_query(
                query,
                {"execution_id": execution_id, "event_type": event_type, "event_data": payload},
            )
        return int(results[0]["sequence_no"]) if results else 0

    async def get_workflow_execution_events_since(
        self,
        execution_id: str,
        sequence_no: int = 0,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """获取指定序号后的工作流执行事件。"""
        query = """
        SELECT * FROM workflow_execution_events
        WHERE execution_id = :execution_id AND sequence_no > :sequence_no
        ORDER BY sequence_no ASC
        LIMIT :limit
        """
        return await self.execute_query(
            query,
            {"execution_id": execution_id, "sequence_no": sequence_no, "limit": limit},
        )

    async def save_operation_request(self, operation_data: Dict[str, Any]) -> str:
        """保存或更新操作请求。"""
        data = dict(operation_data)
        for field in ['id', 'project_id', 'trace_id']:
            data[field] = _validate_uuid(data.get(field))
        for field in ["response_payload"]:
            value = data.get(field, {})
            if isinstance(value, (dict, list)):
                data[field] = json.dumps(value, default=str)
            elif value is None:
                data[field] = '{}'
        for field in ["lease_expires_at", "last_heartbeat_at", "completed_at"]:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                except Exception:
                    data[field] = None
        data.setdefault("id", None)
        data.setdefault("trace_id", None)
        data.setdefault("resource_type", None)
        data.setdefault("resource_id", None)
        data.setdefault("response_payload", {})
        data.setdefault("error", None)
        data.setdefault("lease_token", None)
        data.setdefault("lease_expires_at", None)
        data.setdefault("last_heartbeat_at", None)
        data.setdefault("completed_at", None)
        id_sql = "CAST(:id AS UUID)" if data.get("id") else "gen_random_uuid()"
        project_id_sql = "CAST(:project_id AS UUID)" if data.get("project_id") else "NULL"
        trace_id_sql = "CAST(:trace_id AS UUID)" if data.get("trace_id") else "NULL"
        query = """
        INSERT INTO operation_requests (
            id, request_id, operation_type, project_id, resource_type, resource_id,
            request_hash, trace_id, status, response_payload, error, lease_token,
            lease_expires_at, last_heartbeat_at, completed_at, updated_at
        )
        VALUES (
            """ + id_sql + """, :request_id, :operation_type, """ + project_id_sql + """, :resource_type, :resource_id,
            :request_hash, """ + trace_id_sql + """, :status, :response_payload, :error, :lease_token,
            :lease_expires_at, :last_heartbeat_at, :completed_at, CURRENT_TIMESTAMP
        )
        ON CONFLICT (request_id) DO UPDATE SET
            trace_id = COALESCE(EXCLUDED.trace_id, operation_requests.trace_id),
            status = EXCLUDED.status,
            response_payload = EXCLUDED.response_payload,
            error = EXCLUDED.error,
            lease_token = EXCLUDED.lease_token,
            lease_expires_at = EXCLUDED.lease_expires_at,
            last_heartbeat_at = EXCLUDED.last_heartbeat_at,
            completed_at = EXCLUDED.completed_at,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """
        results = await self.execute_query(query, data)
        return str(results[0]["id"]) if results else str(data.get("id") or "")

    async def get_operation_request_by_request_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        """按 request_id 获取操作请求。"""
        results = await self.execute_query(
            "SELECT * FROM operation_requests WHERE request_id = :request_id",
            {"request_id": request_id},
        )
        return results[0] if results else None

    async def get_active_operation_request(
        self,
        operation_type: str,
        project_id: str,
        resource_id: Optional[str],
        request_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """按语义哈希查找活跃操作。"""
        results = await self.execute_query(
            """
            SELECT * FROM operation_requests
            WHERE operation_type = :operation_type
              AND project_id = :project_id
              AND COALESCE(resource_id, '') = COALESCE(:resource_id, '')
              AND request_hash = :request_hash
              AND status IN ('pending', 'running', 'paused')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {
                "operation_type": operation_type,
                "project_id": project_id,
                "resource_id": resource_id,
                "request_hash": request_hash,
            },
        )
        return results[0] if results else None

    # ==================== Trace 相关操作 ====================

    async def create_execution_trace(self, trace_data: Dict[str, Any]) -> str:
        """创建或更新执行 Trace。Trace 写入失败不影响主流程。"""
        data = dict(trace_data)
        trace_id = data.get("id") or str(uuid_module.uuid4())
        data["id"] = trace_id
        data["project_id"] = _validate_uuid(data.get("project_id"))
        data["operation_id"] = _validate_uuid(data.get("operation_id"))
        for field in ["root_input_summary", "metadata"]:
            value = data.get(field, {})
            if isinstance(value, (dict, list)):
                data[field] = json.dumps(value, default=str)
            elif value is None:
                data[field] = '{}'
        data.setdefault("request_id", None)
        data.setdefault("workflow_id", None)
        data.setdefault("workflow_execution_id", None)
        data.setdefault("trace_type", "manual")
        data.setdefault("root_name", None)
        data.setdefault("status", "running")
        data.setdefault("started_at", datetime.now())
        data.setdefault("error", None)
        project_id_sql = "CAST(:project_id AS UUID)" if data.get("project_id") else "NULL"
        operation_id_sql = "CAST(:operation_id AS UUID)" if data.get("operation_id") else "NULL"
        try:
            await self.execute_write(
                f"""
                INSERT INTO execution_traces (
                    id, project_id, operation_id, request_id, workflow_id, workflow_execution_id,
                    trace_type, root_name, status, root_input_summary, metadata, started_at, error
                )
                VALUES (
                    CAST(:id AS UUID),
                    {project_id_sql},
                    {operation_id_sql},
                    :request_id, :workflow_id, :workflow_execution_id,
                    :trace_type, :root_name, :status,
                    CAST(:root_input_summary AS jsonb), CAST(:metadata AS jsonb), :started_at, :error
                )
                ON CONFLICT (id) DO UPDATE SET
                    project_id = EXCLUDED.project_id,
                    operation_id = EXCLUDED.operation_id,
                    request_id = EXCLUDED.request_id,
                    workflow_id = EXCLUDED.workflow_id,
                    workflow_execution_id = EXCLUDED.workflow_execution_id,
                    trace_type = EXCLUDED.trace_type,
                    root_name = EXCLUDED.root_name,
                    status = EXCLUDED.status,
                    root_input_summary = EXCLUDED.root_input_summary,
                    metadata = EXCLUDED.metadata,
                    error = EXCLUDED.error
                """,
                data,
            )
        except Exception as e:
            logger.warning(f"Trace 创建失败: {e}")
        return trace_id

    async def finish_execution_trace(self, trace_id: str, status: str, error: Optional[str] = None) -> None:
        """结束执行 Trace。"""
        try:
            await self.execute_write(
                """
                UPDATE execution_traces
                SET status = :status,
                    ended_at = CURRENT_TIMESTAMP,
                    duration_ms = CAST(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)) * 1000 AS INTEGER),
                    error = :error
                WHERE id = CAST(:trace_id AS UUID)
                """,
                {"trace_id": trace_id, "status": status, "error": error},
            )
        except Exception as e:
            logger.warning(f"Trace 结束失败: {e}")

    async def create_trace_span(self, span_data: Dict[str, Any]) -> str:
        """创建 Trace span。"""
        data = dict(span_data)
        span_id = data.get("id") or str(uuid_module.uuid4())
        data["id"] = span_id
        data.setdefault("parent_span_id", None)
        data.setdefault("status", "running")
        data.setdefault("workflow_id", None)
        data.setdefault("workflow_execution_id", None)
        data.setdefault("node_id", None)
        data.setdefault("agent_type", None)
        data.setdefault("attributes", {})
        data.setdefault("started_at", datetime.now())
        data.setdefault("error", None)
        parent_span_id_sql = "CAST(:parent_span_id AS UUID)" if data.get("parent_span_id") else "NULL"
        if isinstance(data.get("attributes"), (dict, list)):
            data["attributes"] = json.dumps(data["attributes"], default=str)
        try:
            await self.execute_write(
                f"""
                INSERT INTO execution_trace_spans (
                    id, trace_id, parent_span_id, name, kind, status,
                    workflow_id, workflow_execution_id, node_id, agent_type,
                    attributes, started_at, error
                )
                VALUES (
                    CAST(:id AS UUID), CAST(:trace_id AS UUID),
                    {parent_span_id_sql},
                    :name, :kind, :status,
                    :workflow_id, :workflow_execution_id, :node_id, :agent_type,
                    CAST(:attributes AS jsonb), :started_at, :error
                )
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    attributes = EXCLUDED.attributes,
                    error = EXCLUDED.error
                """,
                data,
            )
        except Exception as e:
            logger.warning(f"Trace span 创建失败: {e}")
        return span_id

    async def finish_trace_span(
        self,
        span_id: str,
        status: str,
        error: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """结束 Trace span。"""
        payload = {
            "span_id": span_id,
            "status": status,
            "error": error,
            "attributes": json.dumps(attributes, default=str) if attributes is not None else None,
        }
        try:
            if attributes is None:
                await self.execute_write(
                    """
                    UPDATE execution_trace_spans
                    SET status = :status,
                        ended_at = CURRENT_TIMESTAMP,
                        duration_ms = CAST(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)) * 1000 AS INTEGER),
                        error = :error
                    WHERE id = CAST(:span_id AS UUID)
                    """,
                    payload,
                )
            else:
                await self.execute_write(
                    """
                    UPDATE execution_trace_spans
                    SET status = :status,
                        ended_at = CURRENT_TIMESTAMP,
                        duration_ms = CAST(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)) * 1000 AS INTEGER),
                        error = :error,
                        attributes = attributes || CAST(:attributes AS jsonb)
                    WHERE id = CAST(:span_id AS UUID)
                    """,
                    payload,
                )
        except Exception as e:
            logger.warning(f"Trace span 结束失败: {e}")

    async def finish_running_trace_spans_for_node(
        self,
        workflow_execution_id: str,
        node_id: str,
        trace_id: Optional[str] = None,
        status: str = "interrupted",
        error: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> int:
        """结束某次执行中指定节点残留的 running Trace span。"""
        trace_id = _validate_uuid(trace_id)
        payload = {
            "workflow_execution_id": workflow_execution_id,
            "node_id": node_id,
            "trace_id": trace_id,
            "status": status,
            "error": error,
            "attributes": json.dumps(attributes or {}, default=str),
        }
        try:
            trace_filter = "AND trace_id = CAST(:trace_id AS UUID)" if trace_id else ""
            return await self.execute_write(
                f"""
                UPDATE execution_trace_spans
                SET status = :status,
                    ended_at = CURRENT_TIMESTAMP,
                    duration_ms = CAST(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)) * 1000 AS INTEGER),
                    error = COALESCE(:error, error),
                    attributes = attributes || CAST(:attributes AS jsonb)
                WHERE workflow_execution_id = :workflow_execution_id
                  AND node_id = :node_id
                  AND status = 'running'
                  AND ended_at IS NULL
                  {trace_filter}
                """,
                payload,
            )
        except Exception as e:
            logger.warning(f"Trace running span 清理失败: {e}")
            return 0

    async def append_trace_event(self, event_data: Dict[str, Any]) -> Optional[str]:
        """追加 Trace 事件。"""
        data = dict(event_data)
        data.setdefault("span_id", None)
        data.setdefault("severity", "info")
        data.setdefault("payload", {})
        span_id_sql = "CAST(:span_id AS UUID)" if data.get("span_id") else "NULL"
        if isinstance(data.get("payload"), (dict, list)):
            data["payload"] = json.dumps(data["payload"], default=str)
        try:
            results = await self.execute_query(
                f"""
                INSERT INTO execution_trace_events (trace_id, span_id, event_type, severity, payload)
                VALUES (
                    CAST(:trace_id AS UUID),
                    {span_id_sql},
                    :event_type, :severity, CAST(:payload AS jsonb)
                )
                RETURNING id
                """,
                data,
            )
            return str(results[0]["id"]) if results else None
        except Exception as e:
            logger.warning(f"Trace event 写入失败: {e}")
            return None

    async def save_trace_artifact(self, artifact_data: Dict[str, Any]) -> Optional[str]:
        """保存 Trace artifact。"""
        data = dict(artifact_data)
        data.setdefault("span_id", None)
        data.setdefault("content_type", "json")
        data.setdefault("content", None)
        data.setdefault("text_content", None)
        data.setdefault("content_hash", None)
        data.setdefault("size_bytes", None)
        data.setdefault("redaction_status", "none")
        span_id_sql = "CAST(:span_id AS UUID)" if data.get("span_id") else "NULL"
        content_sql = "CAST(:content AS jsonb)" if data.get("content") is not None else "NULL"
        if isinstance(data.get("content"), (dict, list)):
            data["content"] = json.dumps(data["content"], default=str)
        elif data.get("content") is None:
            data["content"] = None
        try:
            results = await self.execute_query(
                f"""
                INSERT INTO execution_trace_artifacts (
                    trace_id, span_id, kind, content_type, content, text_content,
                    content_hash, size_bytes, redaction_status
                )
                VALUES (
                    CAST(:trace_id AS UUID),
                    {span_id_sql},
                    :kind, :content_type,
                    {content_sql},
                    :text_content, :content_hash, :size_bytes, :redaction_status
                )
                RETURNING id
                """,
                data,
            )
            return str(results[0]["id"]) if results else None
        except Exception as e:
            logger.warning(f"Trace artifact 写入失败: {e}")
            return None

    async def get_trace_by_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """按 workflow execution ID 获取 Trace。"""
        try:
            results = await self.execute_query(
                """
                SELECT * FROM execution_traces
                WHERE workflow_execution_id = :execution_id
                ORDER BY started_at DESC
                LIMIT 1
                """,
                {"execution_id": execution_id},
            )
            return results[0] if results else None
        except Exception as e:
            logger.warning(f"读取 execution Trace 失败: {e}")
            return None

    async def get_execution_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """按 Trace ID 获取 Trace。"""
        try:
            results = await self.execute_query(
                "SELECT * FROM execution_traces WHERE id = CAST(:trace_id AS UUID)",
                {"trace_id": trace_id},
            )
            return results[0] if results else None
        except Exception as e:
            logger.warning(f"读取 Trace 失败: {e}")
            return None

    async def get_trace_spans(self, trace_id: str) -> List[Dict[str, Any]]:
        """获取 Trace spans。"""
        try:
            return await self.execute_query(
                """
                SELECT * FROM execution_trace_spans
                WHERE trace_id = CAST(:trace_id AS UUID)
                ORDER BY started_at ASC
                """,
                {"trace_id": trace_id},
            )
        except Exception as e:
            logger.warning(f"读取 Trace spans 失败: {e}")
            return []

    async def get_trace_events(self, trace_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        """获取 Trace events。"""
        try:
            return await self.execute_query(
                """
                SELECT * FROM execution_trace_events
                WHERE trace_id = CAST(:trace_id AS UUID)
                ORDER BY sequence ASC
                LIMIT :limit
                """,
                {"trace_id": trace_id, "limit": limit},
            )
        except Exception as e:
            logger.warning(f"读取 Trace events 失败: {e}")
            return []

    async def get_trace_artifacts(self, trace_id: str, span_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取 Trace artifacts。"""
        try:
            if span_id:
                return await self.execute_query(
                    """
                    SELECT * FROM execution_trace_artifacts
                    WHERE trace_id = CAST(:trace_id AS UUID) AND span_id = CAST(:span_id AS UUID)
                    ORDER BY created_at ASC
                    """,
                    {"trace_id": trace_id, "span_id": span_id},
                )
            return await self.execute_query(
                """
                SELECT * FROM execution_trace_artifacts
                WHERE trace_id = CAST(:trace_id AS UUID)
                ORDER BY created_at ASC
                """,
                {"trace_id": trace_id},
            )
        except Exception as e:
            logger.warning(f"读取 Trace artifacts 失败: {e}")
            return []

    async def save_bootstrap_session(self, session_data: Dict[str, Any]) -> str:
        """保存或更新 Bootstrap 会话快照。"""
        data = dict(session_data)
        data["project_id"] = _validate_uuid(data.get("project_id"))
        for field in ["setting_agent_history", "extracted_seed", "confirmed_seed"]:
            value = data.get(field, [] if field == "setting_agent_history" else {})
            if isinstance(value, (dict, list)):
                data[field] = json.dumps(value, default=str)
        for field in ["created_at", "updated_at", "completed_at"]:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                except Exception:
                    data[field] = None
        query = """
        INSERT INTO bootstrap_sessions (
            id, project_id, status, current_stage, progress, setting_agent_history,
            extracted_seed, confirmed_seed, error_message, retry_count,
            created_at, updated_at, completed_at
        )
        VALUES (
            :id, CAST(:project_id AS UUID), :status, :current_stage, :progress,
            :setting_agent_history, :extracted_seed, :confirmed_seed, :error_message,
            :retry_count, :created_at, :updated_at, :completed_at
        )
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            current_stage = EXCLUDED.current_stage,
            progress = EXCLUDED.progress,
            setting_agent_history = EXCLUDED.setting_agent_history,
            extracted_seed = EXCLUDED.extracted_seed,
            confirmed_seed = EXCLUDED.confirmed_seed,
            error_message = EXCLUDED.error_message,
            retry_count = EXCLUDED.retry_count,
            updated_at = EXCLUDED.updated_at,
            completed_at = EXCLUDED.completed_at
        RETURNING id
        """
        results = await self.execute_query(query, data)
        return str(results[0]["id"]) if results else str(data.get("id"))

    async def get_bootstrap_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 获取 Bootstrap 会话。"""
        results = await self.execute_query(
            "SELECT * FROM bootstrap_sessions WHERE id = :id",
            {"id": session_id},
        )
        return results[0] if results else None

    async def get_active_bootstrap_session(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目当前未结束 Bootstrap 会话。"""
        results = await self.execute_query(
            """
            SELECT * FROM bootstrap_sessions
            WHERE project_id = CAST(:project_id AS UUID)
              AND status NOT IN ('completed', 'failed')
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            {"project_id": project_id},
        )
        return results[0] if results else None

    # ==================== 关系图投影任务操作 ====================

    async def upsert_graph_projection_job(self, job_data: Dict[str, Any]) -> str:
        """保存或更新关系图投影任务，按 idempotency_key 幂等。"""
        data = dict(job_data)
        data["project_id"] = _validate_uuid(data.get("project_id"))
        payload = data.get("payload") or {}
        if isinstance(payload, str):
            try:
                json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                payload = {}
        if isinstance(payload, (dict, list)):
            data["payload"] = json.dumps(payload, default=str)
        elif payload is None:
            data["payload"] = "{}"

        data.setdefault("operation", "upsert")
        data.setdefault("status", "queued")
        data.setdefault("attempt_count", 0)
        data.setdefault("last_error", None)
        data.setdefault("available_at", None)
        data.setdefault("next_attempt_at", None)
        data.setdefault("processed_at", None)
        for field in ["available_at", "next_attempt_at", "processed_at"]:
            if isinstance(data.get(field), str):
                try:
                    data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                except Exception:
                    data[field] = None

        query = """
        INSERT INTO graph_projection_jobs (
            idempotency_key, project_id, source_entity_type, source_entity_id,
            projection_type, operation, payload, content_hash, status,
            attempt_count, last_error, available_at, next_attempt_at, processed_at, updated_at
        )
        VALUES (
            :idempotency_key, CAST(:project_id AS UUID), :source_entity_type, :source_entity_id,
            :projection_type, :operation, :payload, :content_hash, :status,
            :attempt_count, :last_error, :available_at, :next_attempt_at, :processed_at, CURRENT_TIMESTAMP
        )
        ON CONFLICT (idempotency_key) DO UPDATE SET
            project_id = EXCLUDED.project_id,
            source_entity_type = EXCLUDED.source_entity_type,
            source_entity_id = EXCLUDED.source_entity_id,
            projection_type = EXCLUDED.projection_type,
            operation = EXCLUDED.operation,
            payload = EXCLUDED.payload,
            content_hash = EXCLUDED.content_hash,
            status = CASE
                WHEN graph_projection_jobs.content_hash IS DISTINCT FROM EXCLUDED.content_hash THEN 'queued'
                WHEN graph_projection_jobs.status = 'completed' THEN graph_projection_jobs.status
                ELSE EXCLUDED.status
            END,
            attempt_count = CASE
                WHEN graph_projection_jobs.content_hash IS DISTINCT FROM EXCLUDED.content_hash THEN 0
                ELSE graph_projection_jobs.attempt_count
            END,
            last_error = NULL,
            available_at = EXCLUDED.available_at,
            next_attempt_at = EXCLUDED.next_attempt_at,
            processed_at = CASE
                WHEN graph_projection_jobs.content_hash IS DISTINCT FROM EXCLUDED.content_hash THEN NULL
                ELSE graph_projection_jobs.processed_at
            END,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """
        results = await self.execute_query(query, data)
        return str(results[0]["id"]) if results else ""

    async def get_graph_projection_job_by_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """按幂等 key 获取关系图投影任务。"""
        results = await self.execute_query(
            "SELECT * FROM graph_projection_jobs WHERE idempotency_key = :idempotency_key",
            {"idempotency_key": idempotency_key},
        )
        return results[0] if results else None

    async def list_graph_projection_jobs(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """列出关系图投影任务，用于状态查询和后续 worker 消费。"""
        conditions = []
        params: Dict[str, Any] = {"limit": limit}
        if project_id:
            conditions.append("project_id = CAST(:project_id AS UUID)")
            params["project_id"] = _validate_uuid(project_id)
        if status:
            conditions.append("status = :status")
            params["status"] = status
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return await self.execute_query(
            f"""
            SELECT * FROM graph_projection_jobs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            params,
        )

    async def claim_graph_projection_jobs(
        self,
        worker_id: str,
        limit: int = 100,
        lease_seconds: int = 60,
    ) -> List[Dict[str, Any]]:
        """原子领取待处理的关系图投影任务。"""
        query = """
        WITH due_jobs AS (
            SELECT id
            FROM graph_projection_jobs
            WHERE (
                status = 'queued'
                AND (next_attempt_at IS NULL OR next_attempt_at <= CURRENT_TIMESTAMP)
            ) OR (
                status = 'processing'
                AND lease_expires_at IS NOT NULL
                AND lease_expires_at < CURRENT_TIMESTAMP
            )
            ORDER BY created_at ASC
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
        )
        UPDATE graph_projection_jobs jobs
        SET status = 'processing',
            worker_id = :worker_id,
            claimed_at = CURRENT_TIMESTAMP,
            lease_expires_at = CURRENT_TIMESTAMP + (:lease_seconds * INTERVAL '1 second'),
            updated_at = CURRENT_TIMESTAMP
        FROM due_jobs
        WHERE jobs.id = due_jobs.id
        RETURNING jobs.*
        """
        return await self.execute_query(
            query,
            {
                "worker_id": worker_id,
                "limit": limit,
                "lease_seconds": lease_seconds,
            },
        )

    async def mark_graph_projection_job_completed(self, job_id: str, worker_id: str) -> bool:
        """标记关系图投影任务完成。"""
        query = """
        UPDATE graph_projection_jobs
        SET status = 'completed',
            last_error = NULL,
            worker_id = NULL,
            claimed_at = NULL,
            lease_expires_at = NULL,
            processed_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = CAST(:job_id AS UUID)
          AND worker_id = :worker_id
          AND status = 'processing'
        """
        return await self.execute_write(query, {"job_id": job_id, "worker_id": worker_id}) > 0

    async def mark_graph_projection_job_retry(
        self,
        job_id: str,
        worker_id: str,
        error: str,
        retry_in_seconds: int,
    ) -> bool:
        """释放关系图投影任务并安排重试。"""
        query = """
        UPDATE graph_projection_jobs
        SET status = 'queued',
            attempt_count = attempt_count + 1,
            last_error = :error,
            worker_id = NULL,
            claimed_at = NULL,
            lease_expires_at = NULL,
            next_attempt_at = CURRENT_TIMESTAMP + (:retry_in_seconds * INTERVAL '1 second'),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = CAST(:job_id AS UUID)
          AND worker_id = :worker_id
          AND status = 'processing'
        """
        return await self.execute_write(
            query,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "error": error[:2000],
                "retry_in_seconds": retry_in_seconds,
            },
        ) > 0

    async def mark_graph_projection_job_failed(
        self,
        job_id: str,
        worker_id: str,
        error: str,
    ) -> bool:
        """标记关系图投影任务永久失败。"""
        query = """
        UPDATE graph_projection_jobs
        SET status = 'failed',
            attempt_count = attempt_count + 1,
            last_error = :error,
            worker_id = NULL,
            claimed_at = NULL,
            lease_expires_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = CAST(:job_id AS UUID)
          AND worker_id = :worker_id
          AND status = 'processing'
        """
        return await self.execute_write(
            query,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "error": error[:2000],
            },
        ) > 0

    async def save_setting_agent_session(self, session_data: Dict[str, Any]) -> str:
        """保存或更新 Setting Agent 会话。"""
        data = dict(session_data)
        data["project_id"] = _validate_uuid(data.get("project_id"))
        for field in [
            "conversation_snapshot",
            "pending_conflicts",
            "cached_pending_lores",
            "cached_pending_characters",
            "cached_pending_hooks",
            "cached_context_sections",
        ]:
            value = data.get(field, [] if field != "cached_context_sections" else {})
            if isinstance(value, str):
                try:
                    json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    value = [] if field != "cached_context_sections" else {}
            if isinstance(value, (dict, list)):
                data[field] = json.dumps(value, default=str)
            elif value is None:
                data[field] = "[]" if field != "cached_context_sections" else "{}"
        for field in ["created_at", "updated_at", "last_activity_at"]:
            if isinstance(data.get(field), str):
                try:
                    data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                except Exception:
                    data[field] = None
        data.setdefault("status", "active")
        data.setdefault("conversation_snapshot", "[]")
        data.setdefault("pending_conflicts", "[]")
        data.setdefault("cached_pending_lores", "[]")
        data.setdefault("cached_pending_characters", "[]")
        data.setdefault("cached_pending_hooks", "[]")
        data.setdefault("cached_context_sections", "{}")
        data.setdefault("full_context_loaded", False)
        data.setdefault("created_at", datetime.now())
        data.setdefault("updated_at", datetime.now())
        data.setdefault("last_activity_at", datetime.now())
        query = """
        INSERT INTO setting_agent_sessions (
            id, project_id, mode, status, conversation_snapshot, pending_conflicts,
            cached_pending_lores, cached_pending_characters, cached_pending_hooks,
            cached_context_sections, full_context_loaded, last_activity_at, created_at, updated_at
        )
        VALUES (
            :id, CAST(:project_id AS UUID), :mode, :status, :conversation_snapshot, :pending_conflicts,
            :cached_pending_lores, :cached_pending_characters, :cached_pending_hooks,
            :cached_context_sections, :full_context_loaded, :last_activity_at, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            mode = EXCLUDED.mode,
            status = EXCLUDED.status,
            conversation_snapshot = EXCLUDED.conversation_snapshot,
            pending_conflicts = EXCLUDED.pending_conflicts,
            cached_pending_lores = EXCLUDED.cached_pending_lores,
            cached_pending_characters = EXCLUDED.cached_pending_characters,
            cached_pending_hooks = EXCLUDED.cached_pending_hooks,
            cached_context_sections = EXCLUDED.cached_context_sections,
            full_context_loaded = EXCLUDED.full_context_loaded,
            last_activity_at = EXCLUDED.last_activity_at,
            updated_at = CURRENT_TIMESTAMP
        """
        await self.execute_write(query, data)
        return data["id"]

    async def get_setting_agent_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 获取 Setting Agent 会话。"""
        results = await self.execute_query(
            "SELECT * FROM setting_agent_sessions WHERE id = :id",
            {"id": session_id},
        )
        return results[0] if results else None

    async def get_active_setting_agent_session(
        self,
        project_id: str,
        mode: str,
    ) -> Optional[Dict[str, Any]]:
        """获取项目指定模式的活跃 Setting Agent 会话。"""
        results = await self.execute_query(
            """
            SELECT * FROM setting_agent_sessions
            WHERE project_id = CAST(:project_id AS UUID)
              AND mode = :mode
              AND status = 'active'
            ORDER BY last_activity_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            {"project_id": project_id, "mode": mode},
        )
        return results[0] if results else None

    async def append_setting_agent_message(
        self,
        session_id: str,
        role: str,
        content: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """追加 Setting Agent 消息；带 request_id 时按角色幂等。"""
        payload = json.dumps(metadata or {}, default=str)
        query = """
        INSERT INTO setting_agent_messages (session_id, request_id, role, content, metadata)
        VALUES (:session_id, :request_id, :role, :content, :metadata)
        ON CONFLICT (session_id, request_id, role) WHERE request_id IS NOT NULL DO UPDATE SET
            content = EXCLUDED.content,
            metadata = EXCLUDED.metadata
        RETURNING id
        """
        results = await self.execute_query(
            query,
            {
                "session_id": session_id,
                "request_id": request_id,
                "role": role,
                "content": content,
                "metadata": payload,
            },
        )
        return str(results[0]["id"]) if results else ""

    async def get_setting_agent_messages(
        self,
        session_id: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """获取 Setting Agent 会话消息。"""
        return await self.execute_query(
            """
            SELECT * FROM setting_agent_messages
            WHERE session_id = :session_id
            ORDER BY created_at ASC
            LIMIT :limit
            """,
            {"session_id": session_id, "limit": limit},
        )

    async def get_setting_agent_message_by_request(
        self,
        session_id: str,
        request_id: str,
        role: str = "assistant",
    ) -> Optional[Dict[str, Any]]:
        """按 request_id 和角色获取 Setting Agent 消息。"""
        results = await self.execute_query(
            """
            SELECT * FROM setting_agent_messages
            WHERE session_id = :session_id AND request_id = :request_id AND role = :role
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"session_id": session_id, "request_id": request_id, "role": role},
        )
        return results[0] if results else None

    async def upsert_setting_agent_pending_item(
        self,
        session_id: str,
        item_type: str,
        fingerprint: str,
        payload: Dict[str, Any],
        request_id: Optional[str] = None,
        status: str = "pending",
        saved_ref_id: Optional[str] = None,
    ) -> str:
        """保存 Setting Agent 待确认项，按 fingerprint 幂等。"""
        query = """
        INSERT INTO setting_agent_pending_items (
            session_id, request_id, item_type, fingerprint, payload, status, saved_ref_id, updated_at
        )
        VALUES (
            :session_id, :request_id, :item_type, :fingerprint, :payload, :status, :saved_ref_id, CURRENT_TIMESTAMP
        )
        ON CONFLICT (session_id, item_type, fingerprint) DO UPDATE SET
            request_id = COALESCE(EXCLUDED.request_id, setting_agent_pending_items.request_id),
            payload = EXCLUDED.payload,
            status = EXCLUDED.status,
            saved_ref_id = EXCLUDED.saved_ref_id,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """
        results = await self.execute_query(
            query,
            {
                "session_id": session_id,
                "request_id": request_id,
                "item_type": item_type,
                "fingerprint": fingerprint,
                "payload": json.dumps(payload, default=str),
                "status": status,
                "saved_ref_id": saved_ref_id,
            },
        )
        return str(results[0]["id"]) if results else ""

    async def get_setting_agent_pending_items(
        self,
        session_id: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取 Setting Agent 待确认项。"""
        conditions = ["session_id = :session_id"]
        params: Dict[str, Any] = {"session_id": session_id}
        if status:
            conditions.append("status = :status")
            params["status"] = status
        return await self.execute_query(
            f"""
            SELECT * FROM setting_agent_pending_items
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at ASC
            """,
            params,
        )

    async def get_setting_agent_pending_item(
        self,
        session_id: str,
        item_type: str,
        fingerprint: str,
    ) -> Optional[Dict[str, Any]]:
        """按 fingerprint 获取 Setting Agent 待确认项。"""
        results = await self.execute_query(
            """
            SELECT * FROM setting_agent_pending_items
            WHERE session_id = :session_id
              AND item_type = :item_type
              AND fingerprint = :fingerprint
            LIMIT 1
            """,
            {
                "session_id": session_id,
                "item_type": item_type,
                "fingerprint": fingerprint,
            },
        )
        return results[0] if results else None

    async def mark_setting_agent_pending_item_saved(
        self,
        session_id: str,
        item_type: str,
        fingerprint: str,
        saved_ref_id: str,
    ) -> None:
        """标记 Setting Agent 待确认项已落库。"""
        await self.execute_write(
            """
            UPDATE setting_agent_pending_items
            SET status = 'saved', saved_ref_id = :saved_ref_id, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = :session_id AND item_type = :item_type AND fingerprint = :fingerprint
            """,
            {
                "session_id": session_id,
                "item_type": item_type,
                "fingerprint": fingerprint,
                "saved_ref_id": saved_ref_id,
            },
        )

    async def get_workflow_executions_by_project(
        self,
        project_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        获取项目的工作流执行记录列表

        Args:
            project_id: 项目 ID
            status: 状态过滤
            limit: 返回数量限制

        Returns:
            List: 执行记录列表
        """
        conditions = ["project_id = :project_id"]
        params: Dict[str, Any] = {"project_id": project_id, "limit": limit}

        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = f"WHERE {' AND '.join(conditions)}"
        query = f"SELECT * FROM workflow_executions {where_clause} ORDER BY started_at DESC LIMIT :limit"

        return await self.execute_query(query, params)

    async def save_v8_intervention_log(self, log_data: Dict[str, Any]) -> str:
        """
        保存 v8 干预日志

        Args:
            log_data: 干预日志数据

        Returns:
            str: 日志 ID
        """
        # 验证 UUID 字段
        log_data['project_id'] = _validate_uuid(log_data.get('project_id'))

        # 处理 JSON 字段
        json_fields = ['context_snapshot']
        for field in json_fields:
            if field in log_data and log_data[field] is not None:
                value = log_data[field]
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except:
                        value = {}
                if isinstance(value, (list, dict)):
                    log_data[field] = json.dumps(value)

        # 处理时间字段
        if 'created_at' in log_data and isinstance(log_data['created_at'], str):
            try:
                log_data['created_at'] = datetime.fromisoformat(
                    log_data['created_at'].replace('Z', '+00:00')
                )
            except:
                log_data['created_at'] = datetime.now()
        elif 'created_at' not in log_data or log_data['created_at'] is None:
            log_data['created_at'] = datetime.now()

        # 动态构建 SQL
        project_id_sql = "CAST(:project_id AS UUID)" if log_data.get('project_id') else "NULL"

        query = """
        INSERT INTO v8_intervention_logs (id, project_id, workflow_execution_id, node_id, agent_type, agent_name, intervention_type, user_message, agent_response, context_snapshot, response_time_ms, created_at)
        VALUES (:id, """ + project_id_sql + """, :workflow_execution_id, :node_id, :agent_type, :agent_name, :intervention_type, :user_message, :agent_response, :context_snapshot, :response_time_ms, :created_at)
        """
        await self.execute_write(query, log_data)
        return log_data.get("id", "")

    async def get_v8_intervention_logs(
        self,
        project_id: str,
        workflow_execution_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        获取 v8 干预日志列表

        Args:
            project_id: 项目 ID
            workflow_execution_id: 工作流执行 ID
            agent_type: Agent 类型过滤
            keyword: 关键词搜索
            limit: 返回数量
            offset: 偏移量

        Returns:
            List: 干预日志列表
        """
        conditions = ["project_id = :project_id"]
        params: Dict[str, Any] = {
            "project_id": project_id,
            "limit": limit,
            "offset": offset,
        }

        if workflow_execution_id:
            conditions.append("workflow_execution_id = :workflow_execution_id")
            params["workflow_execution_id"] = workflow_execution_id

        if agent_type:
            conditions.append("agent_type = :agent_type")
            params["agent_type"] = agent_type

        if keyword:
            conditions.append("(user_message ILIKE :keyword OR agent_response ILIKE :keyword)")
            params["keyword"] = f"%{keyword}%"

        where_clause = f"WHERE {' AND '.join(conditions)}"
        query = f"""
        SELECT * FROM v8_intervention_logs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """

        return await self.execute_query(query, params)

    async def get_v8_intervention_log(self, log_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个 v8 干预日志

        Args:
            log_id: 日志 ID

        Returns:
            Optional[Dict]: 干预日志
        """
        query = "SELECT * FROM v8_intervention_logs WHERE id = :id"
        results = await self.execute_query(query, {"id": log_id})
        return results[0] if results else None

    async def delete_v8_intervention_logs_by_execution(self, execution_id: str) -> int:
        """
        删除某次执行的所有干预日志

        Args:
            execution_id: 执行 ID

        Returns:
            int: 删除数量
        """
        # 先获取数量
        count_query = "SELECT COUNT(*) as count FROM v8_intervention_logs WHERE workflow_execution_id = :execution_id"
        count_result = await self.execute_query(count_query, {"execution_id": execution_id})
        count = count_result[0]["count"] if count_result else 0

        # 删除
        delete_query = "DELETE FROM v8_intervention_logs WHERE workflow_execution_id = :execution_id"
        await self.execute_write(delete_query, {"execution_id": execution_id})

        return count
