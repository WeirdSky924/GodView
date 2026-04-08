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
        执行 SQL 查询

        Args:
            query: SQL 查询语句
            params: 查询参数

        Returns:
            List[Dict]: 查询结果
        """
        async with self.get_session() as session:
            result = await session.execute(text(query), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]

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
        query = """
        INSERT INTO characters (id, name, project_id, world_id, description, role, status, appearance, age, gender,
                                personality_traits, background_story, speech_pattern, lexicon,
                                forbidden_words, voice_samples, attributes, goals, inventory,
                                current_location, created_at, updated_at)
        VALUES (:id, :name, :project_id, :world_id, :description, :role, :status, :appearance, :age, :gender,
                :personality_traits, :background_story, :speech_pattern, :lexicon,
                :forbidden_words, :voice_samples, :attributes, :goals, :inventory,
                :current_location, :created_at, :updated_at)
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
            updated_at = EXCLUDED.updated_at
        """
        await self.execute_query(query, character_data)
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
        status: Optional[str] = None,
        role: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取角色列表，支持项目过滤

        Args:
            project_id: 项目 ID 过滤
            status: 状态过滤
            role: 角色类型过滤
            limit: 返回数量限制

        Returns:
            List: 角色列表
        """
        conditions = []
        params: Dict[str, Any] = {"limit": limit}

        if project_id:
            conditions.append("project_id = :project_id")
            params["project_id"] = project_id
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if role:
            conditions.append("role = :role")
            params["role"] = role

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM characters {where_clause} ORDER BY created_at DESC LIMIT :limit"

        return await self.execute_query(query, params)

    async def delete_character(self, character_id: str) -> bool:
        """删除角色"""
        query = "DELETE FROM characters WHERE id = :id"
        await self.execute_query(query, {"id": character_id})
        return True

    # ==================== 世界相关操作 ====================

    # ==================== 项目相关操作 ====================

    async def save_project(self, project_data: Dict[str, Any]) -> str:
        """保存项目数据"""
        query = """
        INSERT INTO projects (id, name, description, user_id, status, world_id,
                             created_at, updated_at, metadata)
        VALUES (:id, :name, :description, :user_id, :status, :world_id,
                :created_at, :updated_at, :metadata)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            user_id = EXCLUDED.user_id,
            status = EXCLUDED.status,
            world_id = EXCLUDED.world_id,
            updated_at = EXCLUDED.updated_at,
            metadata = EXCLUDED.metadata
        """
        await self.execute_query(query, project_data)
        return project_data.get("id", "")

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

        query = f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = :id"
        await self.execute_query(query, params)
        return True

    async def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        query = "DELETE FROM projects WHERE id = :id"
        await self.execute_query(query, {"id": project_id})
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
                   (SELECT COUNT(*) FROM characters c WHERE c.created_by = p.id) as character_count,
                   (SELECT COUNT(*) FROM chapters c WHERE c.world_id = p.world_id) as chapter_count
            FROM projects p
            WHERE p.status = :status
            ORDER BY p.created_at DESC
            LIMIT :limit
            """
            return await self.execute_query(query, {"status": status, "limit": limit})
        else:
            query = """
            SELECT p.*,
                   (SELECT COUNT(*) FROM characters c WHERE c.created_by = p.id) as character_count,
                   (SELECT COUNT(*) FROM chapters c WHERE c.world_id = p.world_id) as chapter_count
            FROM projects p
            ORDER BY p.created_at DESC
            LIMIT :limit
            """
            return await self.execute_query(query, {"limit": limit})

    async def get_project_summary(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目摘要信息"""
        query = """
        SELECT p.*,
               (SELECT COUNT(*) FROM characters c WHERE c.created_by = p.id) as character_count,
               (SELECT COUNT(*) FROM chapters c WHERE c.world_id = p.world_id) as chapter_count
        FROM projects p
        WHERE p.id = :id
        """
        results = await self.execute_query(query, {"id": project_id})
        return results[0] if results else None

    async def save_world(self, world_data: Dict[str, Any]) -> str:
        """保存世界数据"""
        query = """
        INSERT INTO worlds (id, name, project_id, description, world_type, tone, rules, power_system,
                           technology_level, history, geography, factions, created_at, updated_at)
        VALUES (:id, :name, :project_id, :description, :world_type, :tone, :rules, :power_system,
                :technology_level, :history, :geography, :factions, :created_at, :updated_at)
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
        await self.execute_query(query, world_data)
        return world_data.get("id", "")

    async def get_world(self, world_id: str) -> Optional[Dict[str, Any]]:
        """获取世界数据"""
        query = "SELECT * FROM worlds WHERE id = :id"
        results = await self.execute_query(query, {"id": world_id})
        return results[0] if results else None

    async def delete_world(self, world_id: str) -> bool:
        """删除世界"""
        query = "DELETE FROM worlds WHERE id = :id"
        await self.execute_query(query, {"id": world_id})
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
        query = """
        INSERT INTO regions (id, name, world_id, region_type, terrain_type, description,
                            atmosphere, coordinates, area_size, terrain_features, landmarks,
                            encounters, connections, local_rules, is_generated, visit_count,
                            created_at, updated_at)
        VALUES (:id, :name, :world_id, :region_type, :terrain_type, :description,
                :atmosphere, :coordinates, :area_size, :terrain_features, :landmarks,
                :encounters, :connections, :local_rules, :is_generated, :visit_count,
                :created_at, :updated_at)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            world_id = EXCLUDED.world_id,
            region_type = EXCLUDED.region_type,
            terrain_type = EXCLUDED.terrain_type,
            description = EXCLUDED.description,
            atmosphere = EXCLUDED.atmosphere,
            coordinates = EXCLUDED.coordinates,
            terrain_features = EXCLUDED.terrain_features,
            landmarks = EXCLUDED.landmarks,
            encounters = EXCLUDED.encounters,
            connections = EXCLUDED.connections,
            local_rules = EXCLUDED.local_rules,
            is_generated = EXCLUDED.is_generated,
            visit_count = EXCLUDED.visit_count,
            updated_at = EXCLUDED.updated_at
        """
        await self.execute_query(query, region_data)
        return region_data.get("id", "")

    async def get_region(self, region_id: str) -> Optional[Dict[str, Any]]:
        """获取区域数据"""
        query = "SELECT * FROM regions WHERE id = :id"
        results = await self.execute_query(query, {"id": region_id})
        return results[0] if results else None

    async def get_regions_by_world(self, world_id: str) -> List[Dict[str, Any]]:
        """获取世界的所有区域"""
        query = "SELECT * FROM regions WHERE world_id = :world_id"
        return await self.execute_query(query, {"world_id": world_id})

    # ==================== 伏笔相关操作 ====================

    async def save_hook(self, hook_data: Dict[str, Any]) -> str:
        """保存伏笔数据"""
        query = """
        INSERT INTO hooks (id, title, project_id, world_id, description, hook_type, status, related_characters,
                          related_locations, related_objects, plant_context, plant_chapter,
                          resolution_hint, resolution_context, resolution_chapter, priority,
                          created_at, resolved_at)
        VALUES (:id, :title, :project_id, :world_id, :description, :hook_type, :status, :related_characters,
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
        await self.execute_query(query, hook_data)
        return hook_data.get("id", "")

    async def get_hook(self, hook_id: str) -> Optional[Dict[str, Any]]:
        """获取伏笔数据"""
        query = "SELECT * FROM hooks WHERE id = :id"
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
            query = "SELECT * FROM hooks WHERE status = :status AND project_id = :project_id ORDER BY priority DESC"
            return await self.execute_query(query, {"status": status, "project_id": project_id})
        else:
            query = "SELECT * FROM hooks WHERE status = :status ORDER BY priority DESC"
            return await self.execute_query(query, {"status": status})

    async def update_hook_status(self, hook_id: str, status: str) -> bool:
        """更新伏笔状态"""
        query = "UPDATE hooks SET status = :status WHERE id = :id"
        await self.execute_query(query, {"id": hook_id, "status": status})
        return True

    async def delete_hook(self, hook_id: str) -> bool:
        """删除伏笔"""
        query = "DELETE FROM hooks WHERE id = :id"
        await self.execute_query(query, {"id": hook_id})
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
            status: 状态过滤
            limit: 返回数量限制

        Returns:
            List: 伏笔列表
        """
        conditions = []
        params: Dict[str, Any] = {"limit": limit}

        if project_id:
            conditions.append("project_id = :project_id")
            params["project_id"] = project_id
        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM hooks {where_clause} ORDER BY priority DESC, created_at DESC LIMIT :limit"

        return await self.execute_query(query, params)

    # ==================== 章节相关操作 ====================

    async def save_chapter(self, chapter_data: Dict[str, Any]) -> str:
        """保存章节数据"""
        query = """
        INSERT INTO chapters (id, title, project_id, world_id, content, word_count, status, events,
                             hooks_planted, hooks_resolved, main_plot_progress, reader_scores,
                             created_at, updated_at, completed_at)
        VALUES (:id, :title, :project_id, :world_id, :content, :word_count, :status, :events,
                :hooks_planted, :hooks_resolved, :main_plot_progress, :reader_scores,
                :created_at, :updated_at, :completed_at)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            project_id = EXCLUDED.project_id,
            world_id = EXCLUDED.world_id,
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
        await self.execute_query(query, chapter_data)
        return chapter_data.get("id", "")

    async def get_chapter(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """获取章节数据"""
        query = "SELECT * FROM chapters WHERE id = :id"
        results = await self.execute_query(query, {"id": chapter_id})
        return results[0] if results else None

    async def get_chapters_by_world(self, world_id: str) -> List[Dict[str, Any]]:
        """获取世界的所有章节"""
        query = "SELECT * FROM chapters WHERE world_id = :world_id ORDER BY created_at ASC"
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
        query = """
        INSERT INTO world_snapshots (id, world_id, chapter_id, snapshot_type, name, description,
                                     characters, relationships, regions, hooks, main_plot_progress,
                                     completed_events, character_locations, created_at, created_by,
                                     parent_snapshot_id, is_branch, branch_reason)
        VALUES (:id, :world_id, :chapter_id, :snapshot_type, :name, :description,
                :characters, :relationships, :regions, :hooks, :main_plot_progress,
                :completed_events, :character_locations, :created_at, :created_by,
                :parent_snapshot_id, :is_branch, :branch_reason)
        """
        await self.execute_query(query, snapshot_data)
        return snapshot_data.get("id", "")

    async def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """获取快照数据"""
        query = "SELECT * FROM world_snapshots WHERE id = :id"
        results = await self.execute_query(query, {"id": snapshot_id})
        return results[0] if results else None

    async def get_snapshots_by_world(self, world_id: str) -> List[Dict[str, Any]]:
        """获取世界的所有快照"""
        query = "SELECT * FROM world_snapshots WHERE world_id = :world_id ORDER BY created_at DESC"
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
        query = """
        INSERT INTO intervention_logs (id, snapshot_id, intervention_type, description, details,
                                       affected_hooks, affected_relationships, affected_characters,
                                       outcome_rating, outcome_notes, created_at)
        VALUES (:id, :snapshot_id, :intervention_type, :description, :details,
                :affected_hooks, :affected_relationships, :affected_characters,
                :outcome_rating, :outcome_notes, :created_at)
        """
        await self.execute_query(query, intervention_data)
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
        WHERE id = :id
        """
        await self.execute_query(
            query,
            {
                "id": intervention_id,
                "outcome_rating": outcome_rating,
                "outcome_notes": outcome_notes,
            },
        )

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
        query = """
        INSERT INTO token_usage (
            id, project_id, input_tokens, output_tokens, total_tokens,
            provider, model, category, agent_name, session_id,
            chapter_id, character_id, estimated_cost, metadata, created_at
        ) VALUES (
            :id, :project_id, :input_tokens, :output_tokens, :total_tokens,
            :provider, :model, :category, :agent_name, :session_id,
            :chapter_id, :character_id, :estimated_cost, :metadata, :created_at
        )
        """
        await self.execute_query(query, usage_data)
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
        WHERE id = :project_id
        """
        await self.execute_query(query, {
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
            p.id as project_id,
            p.name as project_name,
            COALESCE(p.total_tokens, 0) as total_tokens,
            COALESCE(p.total_cost, 0) as total_cost
        FROM projects p
        ORDER BY p.total_tokens DESC NULLS LAST
        """
        return await self.execute_query(query, {})
