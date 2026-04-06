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
        INSERT INTO characters (id, name, description, role, status, appearance, age, gender,
                                personality_traits, background_story, speech_pattern, lexicon,
                                forbidden_words, voice_samples, attributes, goals, inventory,
                                current_location, created_at, updated_at)
        VALUES (:id, :name, :description, :role, :status, :appearance, :age, :gender,
                :personality_traits, :background_story, :speech_pattern, :lexicon,
                :forbidden_words, :voice_samples, :attributes, :goals, :inventory,
                :current_location, :created_at, :updated_at)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
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

    async def get_all_characters(self) -> List[Dict[str, Any]]:
        """获取所有角色"""
        query = "SELECT * FROM characters ORDER BY created_at DESC"
        return await self.execute_query(query)

    async def delete_character(self, character_id: str) -> bool:
        """删除角色"""
        query = "DELETE FROM characters WHERE id = :id"
        await self.execute_query(query, {"id": character_id})
        return True

    # ==================== 世界相关操作 ====================

    async def save_world(self, world_data: Dict[str, Any]) -> str:
        """保存世界数据"""
        query = """
        INSERT INTO worlds (id, name, description, world_type, tone, rules, power_system,
                           technology_level, history, geography, factions, created_at, updated_at)
        VALUES (:id, :name, :description, :world_type, :tone, :rules, :power_system,
                :technology_level, :history, :geography, :factions, :created_at, :updated_at)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
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

    async def get_all_worlds(self) -> List[Dict[str, Any]]:
        """获取所有世界"""
        query = "SELECT * FROM worlds ORDER BY created_at DESC"
        return await self.execute_query(query)

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
        INSERT INTO hooks (id, title, description, hook_type, status, related_characters,
                          related_locations, related_objects, plant_context, plant_chapter,
                          resolution_hint, resolution_context, resolution_chapter, priority,
                          created_at, resolved_at)
        VALUES (:id, :title, :description, :hook_type, :status, :related_characters,
                :related_locations, :related_objects, :plant_context, :plant_chapter,
                :resolution_hint, :resolution_context, :resolution_chapter, :priority,
                :created_at, :resolved_at)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
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

    async def get_hooks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """根据状态获取伏笔"""
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

    async def get_all_hooks(self) -> List[Dict[str, Any]]:
        """获取所有伏笔"""
        query = "SELECT * FROM hooks ORDER BY priority DESC, created_at DESC"
        return await self.execute_query(query)

    # ==================== 章节相关操作 ====================

    async def save_chapter(self, chapter_data: Dict[str, Any]) -> str:
        """保存章节数据"""
        query = """
        INSERT INTO chapters (id, title, world_id, content, word_count, status, events,
                             hooks_planted, hooks_resolved, main_plot_progress, reader_scores,
                             created_at, updated_at, completed_at)
        VALUES (:id, :title, :world_id, :content, :word_count, :status, :events,
                :hooks_planted, :hooks_resolved, :main_plot_progress, :reader_scores,
                :created_at, :updated_at, :completed_at)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
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
        create_tables_sql = """
        -- 角色表
        CREATE TABLE IF NOT EXISTS characters (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            role TEXT DEFAULT 'supporting',
            status TEXT DEFAULT 'active',
            appearance TEXT,
            age INTEGER,
            gender TEXT,
            personality_traits JSONB DEFAULT '[]',
            background_story TEXT,
            speech_pattern TEXT,
            lexicon JSONB DEFAULT '[]',
            forbidden_words JSONB DEFAULT '[]',
            voice_samples JSONB DEFAULT '[]',
            attributes JSONB DEFAULT '{}',
            goals JSONB DEFAULT '[]',
            inventory JSONB DEFAULT '[]',
            current_location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 世界表
        CREATE TABLE IF NOT EXISTS worlds (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            world_type TEXT DEFAULT 'fantasy',
            tone TEXT DEFAULT 'serious',
            rules JSONB DEFAULT '[]',
            power_system TEXT,
            technology_level TEXT,
            history TEXT,
            geography TEXT,
            factions JSONB DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 区域表
        CREATE TABLE IF NOT EXISTS regions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            world_id TEXT REFERENCES worlds(id),
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 伏笔表
        CREATE TABLE IF NOT EXISTS hooks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            hook_type TEXT DEFAULT 'custom',
            status TEXT DEFAULT 'planted',
            related_characters JSONB DEFAULT '[]',
            related_locations JSONB DEFAULT '[]',
            related_objects JSONB DEFAULT '[]',
            plant_context TEXT,
            plant_chapter TEXT,
            resolution_hint TEXT,
            resolution_context TEXT,
            resolution_chapter TEXT,
            priority INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        );

        -- 章节表
        CREATE TABLE IF NOT EXISTS chapters (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            world_id TEXT REFERENCES worlds(id),
            content TEXT,
            word_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'draft',
            events JSONB DEFAULT '[]',
            hooks_planted JSONB DEFAULT '[]',
            hooks_resolved JSONB DEFAULT '[]',
            main_plot_progress FLOAT DEFAULT 0,
            reader_scores JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );

        -- 世界快照表
        CREATE TABLE IF NOT EXISTS world_snapshots (
            id TEXT PRIMARY KEY,
            world_id TEXT REFERENCES worlds(id),
            chapter_id TEXT REFERENCES chapters(id),
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT DEFAULT 'system',
            parent_snapshot_id TEXT REFERENCES world_snapshots(id),
            is_branch BOOLEAN DEFAULT FALSE,
            branch_reason TEXT
        );

        -- 干预日志表
        CREATE TABLE IF NOT EXISTS intervention_logs (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT REFERENCES world_snapshots(id),
            intervention_type TEXT NOT NULL,
            description TEXT,
            details JSONB DEFAULT '{}',
            affected_hooks JSONB DEFAULT '[]',
            affected_relationships JSONB DEFAULT '[]',
            affected_characters JSONB DEFAULT '[]',
            outcome_rating FLOAT,
            outcome_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 事件摘要表
        CREATE TABLE IF NOT EXISTS event_summaries (
            id TEXT PRIMARY KEY,
            chapter_id TEXT REFERENCES chapters(id),
            summary TEXT,
            event_type TEXT DEFAULT 'custom',
            participants JSONB DEFAULT '[]',
            subtext_markers JSONB DEFAULT '[]',
            hook_triggers JSONB DEFAULT '[]',
            info_gain_score FLOAT DEFAULT 0,
            raw_dialogue_refs JSONB DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "order" INTEGER DEFAULT 0
        );
        """

        async with self.get_session() as session:
            for statement in create_tables_sql.split(';'):
                if statement.strip():
                    await session.execute(text(statement))
            await session.commit()

        logger.info("数据库表结构初始化完成")
