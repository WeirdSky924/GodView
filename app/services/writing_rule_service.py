"""
写作规则服务层
管理写作规则、规则集和项目写作配置
"""

import json
import logging
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.writing_rule import (
    ProjectWritingConfig,
    ProjectWritingConfigUpdate,
    RuleSeverity,
    WritingRule,
    WritingRuleApplicationMode,
    WritingRuleCategory,
    WritingRuleCreate,
    WritingRuleSet,
    WritingRuleSetCreate,
    WritingRuleSetUpdate,
    WritingRuleUpdate,
    get_default_application_mode,
)
from app.services.writing_rules_init import (
    get_system_rule_by_id,
    get_system_rule_set_by_id,
    get_system_rule_sets,
    get_system_writing_rules,
)

logger = logging.getLogger(__name__)


class WritingRuleService:
    """写作规则服务"""

    BASELINE_RULE_SET_ID = "rule_set_web_novel_basics"
    SEVERITY_ORDER = {
        RuleSeverity.REQUIRED.value: 5,
        RuleSeverity.STRONG.value: 4,
        RuleSeverity.RECOMMENDED.value: 3,
        RuleSeverity.OPTIONAL.value: 2,
        RuleSeverity.INFO.value: 1,
    }
    SEVERITY_LABELS = {
        RuleSeverity.REQUIRED.value: "必须遵守",
        RuleSeverity.STRONG.value: "强烈建议",
        RuleSeverity.RECOMMENDED.value: "推荐",
        RuleSeverity.OPTIONAL.value: "可选",
        RuleSeverity.INFO.value: "参考",
    }

    def __init__(self, db=None):
        self._db = db
        self._rules: Dict[str, WritingRule] = {}
        self._rule_sets: Dict[str, WritingRuleSet] = {}
        self._project_configs: Dict[str, ProjectWritingConfig] = {}

    def _get_db(self):
        if self._db is not None:
            return self._db

        from app.api.app import postgres_db

        return postgres_db

    @staticmethod
    def _json_dumps(value: Any) -> str:
        return json.dumps(value if value is not None else [])

    @staticmethod
    def _ensure_list(value: Optional[List[Any]]) -> List[Any]:
        return value or []

    @staticmethod
    def _ensure_dict(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return value or {}

    @staticmethod
    def _normalize_application_mode(value: Any, severity: Any) -> WritingRuleApplicationMode:
        if isinstance(value, WritingRuleApplicationMode):
            return value
        if value:
            try:
                return WritingRuleApplicationMode(value)
            except ValueError:
                pass
        return get_default_application_mode(severity)

    @staticmethod
    def _clip_text(value: Any, limit: int = 600) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit].rstrip()}..."

    def _rule_from_data(self, data: Dict[str, Any], is_system: bool = False) -> WritingRule:
        payload = deepcopy(data)
        payload["description"] = payload.get("description") or ""
        payload["tags"] = self._ensure_list(payload.get("tags"))
        payload["examples"] = self._ensure_list(payload.get("examples"))
        payload["counter_examples"] = self._ensure_list(payload.get("counter_examples"))
        payload["conditions"] = self._ensure_list(payload.get("conditions"))
        payload["exceptions"] = self._ensure_list(payload.get("exceptions"))
        payload["version"] = payload.get("version") or "1.0.0"
        payload["usage_count"] = payload.get("usage_count") or 0
        payload["is_system"] = bool(payload.get("is_system", is_system))
        payload["application_mode"] = self._normalize_application_mode(
            payload.get("application_mode"),
            payload.get("severity"),
        )
        return WritingRule(**payload)

    def _rule_set_from_data(self, data: Dict[str, Any], is_system: bool = False) -> WritingRuleSet:
        payload = deepcopy(data)
        payload["description"] = payload.get("description") or ""
        payload["rule_ids"] = self._ensure_list(payload.get("rule_ids"))
        payload["rule_overrides"] = self._ensure_dict(payload.get("rule_overrides"))
        payload["tags"] = self._ensure_list(payload.get("tags"))
        payload["target_genres"] = self._ensure_list(payload.get("target_genres"))
        payload["version"] = payload.get("version") or "1.0.0"
        payload["usage_count"] = payload.get("usage_count") or 0
        payload["is_system"] = bool(payload.get("is_system", is_system))
        return WritingRuleSet(**payload)

    def _project_config_from_data(self, project_id: str, data: Optional[Dict[str, Any]] = None) -> ProjectWritingConfig:
        payload = deepcopy(data or {})
        payload.setdefault("id", f"project_writing_config_{project_id}")
        payload["project_id"] = project_id
        payload["enabled_rule_ids"] = self._ensure_list(payload.get("enabled_rule_ids"))
        payload["enabled_rule_set_ids"] = self._ensure_list(payload.get("enabled_rule_set_ids"))
        payload["rule_overrides"] = self._ensure_dict(payload.get("rule_overrides"))
        payload["rule_priorities"] = self._ensure_dict(payload.get("rule_priorities"))
        payload["default_severity"] = payload.get("default_severity") or RuleSeverity.RECOMMENDED.value
        payload["apply_to_chapters"] = payload.get("apply_to_chapters", True)
        payload["apply_to_characters"] = payload.get("apply_to_characters", True)
        payload["apply_to_descriptions"] = payload.get("apply_to_descriptions", True)
        payload["apply_to_narration"] = payload.get("apply_to_narration", True)
        payload["is_active"] = payload.get("is_active", True)
        payload["version"] = payload.get("version") or "1.0.0"
        return ProjectWritingConfig(**payload)

    async def _sync_rule_index(self, rule: WritingRule) -> None:
        try:
            from app.services.writing_rule_index_service import get_writing_rule_index_service

            await get_writing_rule_index_service().index_rule(rule)
        except Exception as e:
            logger.warning(f"同步写作规则索引失败 {rule.id}: {e}")

    async def _remove_rule_index(self, rule_id: str) -> None:
        try:
            from app.services.writing_rule_index_service import get_writing_rule_index_service

            await get_writing_rule_index_service().delete_rule(rule_id)
        except Exception as e:
            logger.warning(f"删除写作规则索引失败 {rule_id}: {e}")

    async def _list_custom_rules(self) -> List[WritingRule]:
        db = self._get_db()
        if db is None:
            return list(self._rules.values())

        rows = await db.execute_query(
            """
            SELECT *
            FROM writing_rules
            WHERE COALESCE(is_system, FALSE) = FALSE
            ORDER BY updated_at DESC, created_at DESC
            """
        )
        rules = [self._rule_from_data(row) for row in rows]
        for rule in rules:
            self._rules[rule.id] = rule
        return rules

    async def _list_custom_rule_sets(self) -> List[WritingRuleSet]:
        db = self._get_db()
        if db is None:
            return list(self._rule_sets.values())

        rows = await db.execute_query(
            """
            SELECT *
            FROM writing_rule_sets
            WHERE COALESCE(is_system, FALSE) = FALSE
            ORDER BY updated_at DESC, created_at DESC
            """
        )
        rule_sets = [self._rule_set_from_data(row) for row in rows]
        for rule_set in rule_sets:
            self._rule_sets[rule_set.id] = rule_set
        return rule_sets

    async def _get_custom_rule(self, rule_id: str) -> Optional[WritingRule]:
        if rule_id in self._rules:
            return self._rules[rule_id]

        db = self._get_db()
        if db is None:
            return None

        rows = await db.execute_query(
            """
            SELECT *
            FROM writing_rules
            WHERE id = :rule_id AND COALESCE(is_system, FALSE) = FALSE
            LIMIT 1
            """,
            {"rule_id": rule_id},
        )
        if not rows:
            return None
        rule = self._rule_from_data(rows[0])
        self._rules[rule.id] = rule
        return rule

    async def _get_custom_rule_set(self, rule_set_id: str) -> Optional[WritingRuleSet]:
        if rule_set_id in self._rule_sets:
            return self._rule_sets[rule_set_id]

        db = self._get_db()
        if db is None:
            return None

        rows = await db.execute_query(
            """
            SELECT *
            FROM writing_rule_sets
            WHERE id = :rule_set_id AND COALESCE(is_system, FALSE) = FALSE
            LIMIT 1
            """,
            {"rule_set_id": rule_set_id},
        )
        if not rows:
            return None
        rule_set = self._rule_set_from_data(rows[0])
        self._rule_sets[rule_set.id] = rule_set
        return rule_set

    async def get_rule_merged(self, rule_id: str) -> Optional[WritingRule]:
        system_rule = get_system_rule_by_id(rule_id)
        if system_rule:
            return self._rule_from_data(system_rule, is_system=True)
        return await self._get_custom_rule(rule_id)

    async def get_rule_set_merged(self, rule_set_id: str) -> Optional[WritingRuleSet]:
        system_rule_set = get_system_rule_set_by_id(rule_set_id)
        if system_rule_set:
            return self._rule_set_from_data(system_rule_set, is_system=True)
        return await self._get_custom_rule_set(rule_set_id)

    async def list_rules_merged(
        self,
        category: Optional[WritingRuleCategory] = None,
        severity: Optional[RuleSeverity] = None,
        tags: Optional[List[str]] = None,
        is_system: Optional[bool] = None,
        search: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WritingRule]:
        rules: List[WritingRule] = []

        if is_system is not False:
            rules.extend(
                self._rule_from_data(rule, is_system=True)
                for rule in get_system_writing_rules(
                    category=category.value if isinstance(category, WritingRuleCategory) else category,
                    severity=severity.value if isinstance(severity, RuleSeverity) else severity,
                    tags=tags,
                    search=search,
                    source=source,
                )
            )

        if is_system is not True:
            custom_rules = await self._list_custom_rules()
            for rule in custom_rules:
                if category and rule.category != category:
                    continue
                if severity and rule.severity != severity:
                    continue
                if tags and not any(tag in rule.tags for tag in tags):
                    continue
                if source and rule.source != source:
                    continue
                if search:
                    search_lower = search.lower()
                    haystacks = [rule.name, rule.description, rule.content]
                    if not any(search_lower in (item or "").lower() for item in haystacks):
                        continue
                rules.append(rule)

        rules.sort(
            key=lambda rule: (
                -self.SEVERITY_ORDER.get(rule.severity.value, 0),
                -(rule.usage_count or 0),
                rule.name,
            )
        )
        return rules[offset:offset + limit]

    async def list_rule_sets_merged(
        self,
        category: Optional[WritingRuleCategory] = None,
        tags: Optional[List[str]] = None,
        target_genre: Optional[str] = None,
        is_system: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WritingRuleSet]:
        rule_sets: List[WritingRuleSet] = []

        if is_system is not False:
            rule_sets.extend(
                self._rule_set_from_data(rule_set, is_system=True)
                for rule_set in get_system_rule_sets(
                    category=category.value if isinstance(category, WritingRuleCategory) else category,
                    tags=tags,
                    target_genre=target_genre,
                )
            )

        if is_system is not True:
            custom_rule_sets = await self._list_custom_rule_sets()
            for rule_set in custom_rule_sets:
                if category and rule_set.category != category:
                    continue
                if tags and not any(tag in rule_set.tags for tag in tags):
                    continue
                if target_genre and target_genre not in rule_set.target_genres:
                    continue
                rule_sets.append(rule_set)

        rule_sets.sort(
            key=lambda rule_set: (
                -(rule_set.usage_count or 0),
                rule_set.name,
            )
        )
        return rule_sets[offset:offset + limit]

    async def create_rule(self, dto: WritingRuleCreate) -> WritingRule:
        rule_id = f"custom_{uuid.uuid4().hex[:12]}"
        now = datetime.now()
        rule = WritingRule(
            id=rule_id,
            name=dto.name,
            description=dto.description,
            category=dto.category,
            severity=dto.severity,
            application_mode=self._normalize_application_mode(dto.application_mode, dto.severity),
            tags=dto.tags,
            content=dto.content,
            examples=dto.examples,
            counter_examples=dto.counter_examples,
            conditions=dto.conditions,
            exceptions=dto.exceptions,
            author=dto.author,
            source=dto.source,
            is_system=False,
            created_at=now,
            updated_at=now,
        )

        db = self._get_db()
        if db is None:
            self._rules[rule_id] = rule
            await self._sync_rule_index(rule)
            return rule

        await db.execute_write(
            """
            INSERT INTO writing_rules (
                id, name, description, category, severity, application_mode, tags, content,
                examples, counter_examples, conditions, exceptions,
                is_system, version, author, source, usage_count,
                last_used_at, created_at, updated_at
            ) VALUES (
                :id, :name, :description, :category, :severity, :application_mode, :tags, :content,
                :examples, :counter_examples, :conditions, :exceptions,
                FALSE, :version, :author, :source, :usage_count,
                :last_used_at, :created_at, :updated_at
            )
            """,
            {
                "id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "category": rule.category.value,
                "severity": rule.severity.value,
                "application_mode": rule.application_mode.value,
                "tags": self._json_dumps(rule.tags),
                "content": rule.content,
                "examples": self._json_dumps(rule.examples),
                "counter_examples": self._json_dumps(rule.counter_examples),
                "conditions": self._json_dumps(rule.conditions),
                "exceptions": self._json_dumps(rule.exceptions),
                "version": rule.version,
                "author": rule.author,
                "source": rule.source,
                "usage_count": rule.usage_count,
                "last_used_at": rule.last_used_at,
                "created_at": rule.created_at,
                "updated_at": rule.updated_at,
            },
        )
        self._rules[rule_id] = rule
        await self._sync_rule_index(rule)
        return rule

    async def update_rule(self, rule_id: str, dto: WritingRuleUpdate) -> tuple[Optional[WritingRule], Optional[str]]:
        current = await self._get_custom_rule(rule_id)
        if not current:
            if get_system_rule_by_id(rule_id):
                return None, "is_system"
            return None, "not_found"

        update_data = dto.dict(exclude_unset=True)
        current_data = current.dict()
        current_data.update({k: v for k, v in update_data.items() if v is not None})
        current_data["updated_at"] = datetime.now()
        current_data["is_system"] = False
        current_data["application_mode"] = self._normalize_application_mode(
            current_data.get("application_mode"),
            current_data.get("severity"),
        )
        updated = WritingRule(**current_data)

        db = self._get_db()
        if db is None:
            self._rules[rule_id] = updated
            await self._sync_rule_index(updated)
            return updated, None

        await db.execute_write(
            """
            UPDATE writing_rules
            SET name = :name,
                description = :description,
                category = :category,
                severity = :severity,
                application_mode = :application_mode,
                tags = :tags,
                content = :content,
                examples = :examples,
                counter_examples = :counter_examples,
                conditions = :conditions,
                exceptions = :exceptions,
                version = :version,
                author = :author,
                source = :source,
                updated_at = :updated_at
            WHERE id = :id AND COALESCE(is_system, FALSE) = FALSE
            """,
            {
                "id": updated.id,
                "name": updated.name,
                "description": updated.description,
                "category": updated.category.value,
                "severity": updated.severity.value,
                "application_mode": updated.application_mode.value,
                "tags": self._json_dumps(updated.tags),
                "content": updated.content,
                "examples": self._json_dumps(updated.examples),
                "counter_examples": self._json_dumps(updated.counter_examples),
                "conditions": self._json_dumps(updated.conditions),
                "exceptions": self._json_dumps(updated.exceptions),
                "version": updated.version,
                "author": updated.author,
                "source": updated.source,
                "updated_at": updated.updated_at,
            },
        )
        self._rules[rule_id] = updated
        await self._sync_rule_index(updated)
        return updated, None

    async def delete_rule(self, rule_id: str) -> tuple[bool, Optional[str]]:
        if get_system_rule_by_id(rule_id):
            return False, "is_system"

        current = await self._get_custom_rule(rule_id)
        if not current:
            return False, "not_found"

        if await self._is_rule_referenced(rule_id):
            return False, "in_use"

        db = self._get_db()
        if db is None:
            self._rules.pop(rule_id, None)
            await self._remove_rule_index(rule_id)
            return True, None

        await db.execute_write(
            "DELETE FROM writing_rules WHERE id = :rule_id AND COALESCE(is_system, FALSE) = FALSE",
            {"rule_id": rule_id},
        )
        self._rules.pop(rule_id, None)
        await self._remove_rule_index(rule_id)
        return True, None

    async def _is_rule_referenced(self, rule_id: str) -> bool:
        for rule_set in await self._list_custom_rule_sets():
            if rule_id in rule_set.rule_ids:
                return True
        return False

    async def create_rule_set(self, dto: WritingRuleSetCreate) -> WritingRuleSet:
        rule_set_id = f"custom_ruleset_{uuid.uuid4().hex[:12]}"
        now = datetime.now()
        rule_set = WritingRuleSet(
            id=rule_set_id,
            name=dto.name,
            description=dto.description,
            rule_ids=dto.rule_ids,
            rule_overrides=dto.rule_overrides,
            category=dto.category,
            tags=dto.tags,
            target_genres=dto.target_genres,
            author=dto.author,
            is_system=False,
            created_at=now,
            updated_at=now,
        )

        db = self._get_db()
        if db is None:
            self._rule_sets[rule_set_id] = rule_set
            return rule_set

        await db.execute_write(
            """
            INSERT INTO writing_rule_sets (
                id, name, description, rule_ids, rule_overrides,
                category, tags, target_genres, is_system, version,
                author, usage_count, last_used_at, created_at, updated_at
            ) VALUES (
                :id, :name, :description, :rule_ids, :rule_overrides,
                :category, :tags, :target_genres, FALSE, :version,
                :author, :usage_count, :last_used_at, :created_at, :updated_at
            )
            """,
            {
                "id": rule_set.id,
                "name": rule_set.name,
                "description": rule_set.description,
                "rule_ids": self._json_dumps(rule_set.rule_ids),
                "rule_overrides": self._json_dumps(rule_set.rule_overrides),
                "category": rule_set.category.value,
                "tags": self._json_dumps(rule_set.tags),
                "target_genres": self._json_dumps(rule_set.target_genres),
                "version": rule_set.version,
                "author": rule_set.author,
                "usage_count": rule_set.usage_count,
                "last_used_at": rule_set.last_used_at,
                "created_at": rule_set.created_at,
                "updated_at": rule_set.updated_at,
            },
        )
        self._rule_sets[rule_set_id] = rule_set
        return rule_set

    async def update_rule_set(self, rule_set_id: str, dto: WritingRuleSetUpdate) -> tuple[Optional[WritingRuleSet], Optional[str]]:
        current = await self._get_custom_rule_set(rule_set_id)
        if not current:
            if get_system_rule_set_by_id(rule_set_id):
                return None, "is_system"
            return None, "not_found"

        update_data = dto.dict(exclude_unset=True)
        current_data = current.dict()
        current_data.update({k: v for k, v in update_data.items() if v is not None})
        current_data["updated_at"] = datetime.now()
        current_data["is_system"] = False
        updated = WritingRuleSet(**current_data)

        db = self._get_db()
        if db is None:
            self._rule_sets[rule_set_id] = updated
            return updated, None

        await db.execute_write(
            """
            UPDATE writing_rule_sets
            SET name = :name,
                description = :description,
                rule_ids = :rule_ids,
                rule_overrides = :rule_overrides,
                category = :category,
                tags = :tags,
                target_genres = :target_genres,
                version = :version,
                author = :author,
                updated_at = :updated_at
            WHERE id = :id AND COALESCE(is_system, FALSE) = FALSE
            """,
            {
                "id": updated.id,
                "name": updated.name,
                "description": updated.description,
                "rule_ids": self._json_dumps(updated.rule_ids),
                "rule_overrides": self._json_dumps(updated.rule_overrides),
                "category": updated.category.value,
                "tags": self._json_dumps(updated.tags),
                "target_genres": self._json_dumps(updated.target_genres),
                "version": updated.version,
                "author": updated.author,
                "updated_at": updated.updated_at,
            },
        )
        self._rule_sets[rule_set_id] = updated
        return updated, None

    async def delete_rule_set(self, rule_set_id: str) -> tuple[bool, Optional[str]]:
        if get_system_rule_set_by_id(rule_set_id):
            return False, "is_system"

        current = await self._get_custom_rule_set(rule_set_id)
        if not current:
            return False, "not_found"

        db = self._get_db()
        if db is None:
            self._rule_sets.pop(rule_set_id, None)
            return True, None

        await db.execute_write(
            "DELETE FROM writing_rule_sets WHERE id = :rule_set_id AND COALESCE(is_system, FALSE) = FALSE",
            {"rule_set_id": rule_set_id},
        )
        self._rule_sets.pop(rule_set_id, None)
        return True, None

    async def get_project_writing_config(self, project_id: str) -> ProjectWritingConfig:
        for config in self._project_configs.values():
            if config.project_id == project_id:
                return config

        db = self._get_db()
        if db is None:
            return self._project_config_from_data(project_id)

        rows = await db.execute_query(
            "SELECT * FROM project_writing_configs WHERE project_id = :project_id LIMIT 1",
            {"project_id": project_id},
        )
        if not rows:
            return self._project_config_from_data(project_id)

        config = self._project_config_from_data(project_id, rows[0])
        self._project_configs[project_id] = config
        return config

    async def update_project_writing_config(
        self,
        project_id: str,
        dto: ProjectWritingConfigUpdate,
    ) -> Optional[ProjectWritingConfig]:
        current = await self.get_project_writing_config(project_id)
        current_data = current.dict()
        update_data = {k: v for k, v in dto.dict(exclude_unset=True).items() if v is not None}
        current_data.update(update_data)
        current_data["updated_at"] = datetime.now()
        updated = ProjectWritingConfig(**current_data)

        db = self._get_db()
        if db is None:
            self._project_configs[project_id] = updated
            return updated

        await db.execute_write(
            """
            INSERT INTO project_writing_configs (
                id, project_id, enabled_rule_ids, enabled_rule_set_ids,
                rule_overrides, rule_priorities, default_severity,
                apply_to_chapters, apply_to_characters, apply_to_descriptions,
                apply_to_narration, is_active, version, created_at, updated_at
            ) VALUES (
                :id, :project_id, :enabled_rule_ids, :enabled_rule_set_ids,
                :rule_overrides, :rule_priorities, :default_severity,
                :apply_to_chapters, :apply_to_characters, :apply_to_descriptions,
                :apply_to_narration, :is_active, :version, :created_at, :updated_at
            )
            ON CONFLICT (project_id) DO UPDATE SET
                enabled_rule_ids = EXCLUDED.enabled_rule_ids,
                enabled_rule_set_ids = EXCLUDED.enabled_rule_set_ids,
                rule_overrides = EXCLUDED.rule_overrides,
                rule_priorities = EXCLUDED.rule_priorities,
                default_severity = EXCLUDED.default_severity,
                apply_to_chapters = EXCLUDED.apply_to_chapters,
                apply_to_characters = EXCLUDED.apply_to_characters,
                apply_to_descriptions = EXCLUDED.apply_to_descriptions,
                apply_to_narration = EXCLUDED.apply_to_narration,
                is_active = EXCLUDED.is_active,
                version = EXCLUDED.version,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "id": updated.id,
                "project_id": updated.project_id,
                "enabled_rule_ids": self._json_dumps(updated.enabled_rule_ids),
                "enabled_rule_set_ids": self._json_dumps(updated.enabled_rule_set_ids),
                "rule_overrides": self._json_dumps(updated.rule_overrides),
                "rule_priorities": self._json_dumps(updated.rule_priorities),
                "default_severity": updated.default_severity.value if hasattr(updated.default_severity, "value") else updated.default_severity,
                "apply_to_chapters": updated.apply_to_chapters,
                "apply_to_characters": updated.apply_to_characters,
                "apply_to_descriptions": updated.apply_to_descriptions,
                "apply_to_narration": updated.apply_to_narration,
                "is_active": updated.is_active,
                "version": updated.version,
                "created_at": updated.created_at,
                "updated_at": updated.updated_at,
            },
        )
        self._project_configs[project_id] = updated
        return updated

    async def resolve_rules(
        self,
        rule_ids: Optional[List[str]] = None,
        rule_set_ids: Optional[List[str]] = None,
        category: Optional[str] = None,
        severity_min: Optional[str] = None,
        rule_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        rule_priorities: Optional[Dict[str, int]] = None,
        default_to_baseline: bool = False,
    ) -> List[WritingRule]:
        resolved_rules: List[WritingRule] = []
        seen_rule_ids = set()

        selected_rule_ids = list(rule_ids or [])
        selected_rule_set_ids = list(rule_set_ids or [])

        if default_to_baseline and not selected_rule_ids and not selected_rule_set_ids:
            selected_rule_set_ids = [self.BASELINE_RULE_SET_ID]

        for rule_set_id in selected_rule_set_ids:
            rule_set = await self.get_rule_set_merged(rule_set_id)
            if not rule_set:
                continue

            for nested_rule_id in rule_set.rule_ids:
                if nested_rule_id in seen_rule_ids:
                    continue

                rule = await self.get_rule_merged(nested_rule_id)
                if not rule:
                    continue

                rule = self._apply_rule_overrides(rule, rule_set.rule_overrides.get(nested_rule_id, {}))
                resolved_rules.append(rule)
                seen_rule_ids.add(nested_rule_id)

        for rule_id in selected_rule_ids:
            if rule_id in seen_rule_ids:
                continue

            rule = await self.get_rule_merged(rule_id)
            if not rule:
                continue

            resolved_rules.append(rule)
            seen_rule_ids.add(rule_id)

        if rule_overrides:
            resolved_rules = [
                self._apply_rule_overrides(rule, rule_overrides.get(rule.id, {}))
                for rule in resolved_rules
            ]

        if category:
            resolved_rules = [rule for rule in resolved_rules if rule.category.value == category]

        if severity_min:
            min_rank = self.SEVERITY_ORDER.get(severity_min, 0)
            resolved_rules = [
                rule for rule in resolved_rules
                if self.SEVERITY_ORDER.get(rule.severity.value, 0) >= min_rank
            ]

        priorities = rule_priorities or {}
        resolved_rules.sort(
            key=lambda rule: (
                -int(priorities.get(rule.id, 0)),
                -self.SEVERITY_ORDER.get(rule.severity.value, 0),
                rule.name,
            )
        )
        return resolved_rules

    async def resolve_rules_for_project(
        self,
        project_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[WritingRule]:
        del context
        scope = await self.resolve_project_rule_scope(project_id)
        return scope["rules"]

    async def resolve_project_rule_scope(self, project_id: str) -> Dict[str, Any]:
        config = await self.get_project_writing_config(project_id)
        if not config.is_active:
            return {
                "project_id": project_id,
                "is_active": False,
                "used_baseline": False,
                "enabled_rule_ids": [],
                "enabled_rule_set_ids": [],
                "resolved_rule_ids": [],
                "rule_priorities": {},
                "rule_overrides": {},
                "rules": [],
            }

        used_baseline = not config.enabled_rule_ids and not config.enabled_rule_set_ids
        rules = await self.resolve_rules(
            rule_ids=config.enabled_rule_ids,
            rule_set_ids=config.enabled_rule_set_ids,
            rule_overrides=config.rule_overrides,
            rule_priorities=config.rule_priorities,
            default_to_baseline=True,
        )

        return {
            "project_id": project_id,
            "is_active": True,
            "used_baseline": used_baseline,
            "enabled_rule_ids": list(config.enabled_rule_ids),
            "enabled_rule_set_ids": list(config.enabled_rule_set_ids) if config.enabled_rule_set_ids else ([self.BASELINE_RULE_SET_ID] if used_baseline else []),
            "resolved_rule_ids": [rule.id for rule in rules],
            "rule_priorities": dict(config.rule_priorities),
            "rule_overrides": deepcopy(config.rule_overrides),
            "rules": rules,
        }

    def build_retrieval_query_context(self, project_id: str, context: Optional[Dict[str, Any]] = None) -> str:
        payload = context or {}
        sections: List[str] = [f"project:{project_id}"]

        def append_section(title: str, value: Any):
            if value is None:
                return
            if isinstance(value, str):
                text = value.strip()
                if text:
                    sections.append(f"{title}: {text}")
                return
            if isinstance(value, list):
                items = [str(item).strip() for item in value if str(item).strip()]
                if items:
                    sections.append(f"{title}: {' | '.join(items[:12])}")
                return
            if isinstance(value, dict):
                parts = []
                for key, item in value.items():
                    text = str(item).strip()
                    if text:
                        parts.append(f"{key}={text}")
                if parts:
                    sections.append(f"{title}: {' | '.join(parts[:12])}")
                return
            text = str(value).strip()
            if text:
                sections.append(f"{title}: {text}")

        append_section("chapter", payload.get("chapter_num"))
        append_section("total_chapters", payload.get("total_chapters"))
        append_section("discussion_summary", payload.get("discussion_summary"))
        append_section("environment", payload.get("environment"))
        append_section("intents", payload.get("intents"))
        append_section("hooks", payload.get("hooks"))
        append_section("character_moods", payload.get("character_moods"))
        append_section("scene", payload.get("scene"))
        append_section("world", payload.get("world_info"))
        append_section("segment_focus", payload.get("segment_focus"))
        append_section("segment_elements", payload.get("segment_elements"))
        append_section("query", payload.get("query"))

        return "\n".join(sections).strip()

    def has_meaningful_retrieval_context(self, context: Optional[Dict[str, Any]] = None) -> bool:
        payload = context or {}
        meaningful_keys = [
            "discussion_summary",
            "environment",
            "intents",
            "hooks",
            "character_moods",
            "scene",
            "world_info",
            "segment_focus",
            "segment_elements",
            "query",
        ]

        for key in meaningful_keys:
            value = payload.get(key)
            if value in (None, "", [], {}):
                continue
            return True

        return False

    def build_always_rule_guidance(self, rules: List[WritingRule]) -> str:
        constitutional_rules = [
            rule for rule in rules
            if rule.application_mode in {
                WritingRuleApplicationMode.ALWAYS,
                WritingRuleApplicationMode.ALWAYS_POSTCHECK,
            }
        ]
        if not constitutional_rules:
            return ""

        lines = ["## 当前必须常驻的写作约束"]
        for rule in constitutional_rules:
            line = f"- [{rule.severity.value}] {rule.name}: {self._clip_text(rule.content, 180)}"
            if rule.exceptions:
                line += f"（例外：{'; '.join(rule.exceptions[:2])}）"
            lines.append(line)
        return "\n".join(lines)

    def build_retrieved_guidance(self, rules: List[WritingRule], limit: int = 6) -> str:
        if not rules:
            return ""

        lines = ["## 当前任务命中的写作规则"]
        for rule in rules[:limit]:
            lines.append(f"- [{rule.severity.value}] {rule.name}: {self._clip_text(rule.content, 220)}")
            if rule.examples:
                lines.append(f"  示例：{self._clip_text(rule.examples[0], 120)}")
        return "\n".join(lines)

    def describe_project_rule_scope(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        rules: List[WritingRule] = scope.get("rules", [])
        severity_counts: Dict[str, int] = {}
        mode_counts: Dict[str, int] = {}
        for rule in rules:
            severity_counts[rule.severity.value] = severity_counts.get(rule.severity.value, 0) + 1
            mode_counts[rule.application_mode.value] = mode_counts.get(rule.application_mode.value, 0) + 1

        return {
            "project_id": scope.get("project_id"),
            "is_active": scope.get("is_active", True),
            "used_baseline": scope.get("used_baseline", False),
            "enabled_rule_ids": scope.get("enabled_rule_ids", []),
            "enabled_rule_set_ids": scope.get("enabled_rule_set_ids", []),
            "resolved_rule_ids": scope.get("resolved_rule_ids", []),
            "resolved_rule_count": len(rules),
            "severity_counts": severity_counts,
            "application_mode_counts": mode_counts,
        }

    async def build_prompt(
        self,
        rule_ids: Optional[List[str]] = None,
        rule_set_ids: Optional[List[str]] = None,
        category: Optional[str] = None,
        severity_min: Optional[str] = "recommended",
        context: Optional[Dict[str, Any]] = None,
        rule_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        rule_priorities: Optional[Dict[str, int]] = None,
        default_to_baseline: bool = False,
    ) -> str:
        rules = await self.resolve_rules(
            rule_ids=rule_ids,
            rule_set_ids=rule_set_ids,
            category=category,
            severity_min=severity_min,
            rule_overrides=rule_overrides,
            rule_priorities=rule_priorities,
            default_to_baseline=default_to_baseline,
        )
        if not rules:
            return ""

        prompt_parts = [
            "# 写作规范指南\n",
            "以下仅包含当前项目显式启用的规则；若项目未单独配置，则使用基础默认规则集。\n",
        ]

        grouped_rules: Dict[str, List[WritingRule]] = {}
        for rule in rules:
            grouped_rules.setdefault(rule.severity.value, []).append(rule)

        for severity in [
            RuleSeverity.REQUIRED.value,
            RuleSeverity.STRONG.value,
            RuleSeverity.RECOMMENDED.value,
            RuleSeverity.OPTIONAL.value,
            RuleSeverity.INFO.value,
        ]:
            items = grouped_rules.get(severity)
            if not items:
                continue

            prompt_parts.append(f"\n## [{self.SEVERITY_LABELS.get(severity, severity)}]\n")
            for rule in items:
                prompt_parts.append(self._build_rule_prompt(rule, context))

        return "".join(prompt_parts).strip()

    async def build_prompt_for_project(
        self,
        project_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        scope = await self.resolve_project_rule_scope(project_id)
        if not scope.get("is_active"):
            return ""

        return await self.build_prompt(
            rule_ids=scope["enabled_rule_ids"],
            rule_set_ids=scope["enabled_rule_set_ids"],
            context=context,
            rule_overrides=scope["rule_overrides"],
            rule_priorities=scope["rule_priorities"],
            severity_min=None,
            default_to_baseline=scope["used_baseline"],
        )

    async def build_writing_prompt(
        self,
        project_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        return await self.build_prompt_for_project(project_id, context)

    def _apply_rule_overrides(self, rule: WritingRule, overrides: Dict[str, Any]) -> WritingRule:
        if not overrides:
            return rule

        rule_data = rule.dict()
        for key, value in overrides.items():
            if key in rule_data and value is not None:
                rule_data[key] = value
        rule_data["application_mode"] = self._normalize_application_mode(
            rule_data.get("application_mode"),
            rule_data.get("severity"),
        )
        return WritingRule(**rule_data)

    def _build_rule_prompt(
        self,
        rule: WritingRule,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        del context
        lines = [f"\n### {rule.name}\n", f"{rule.content}\n"]

        example_limit = 2 if rule.severity in {RuleSeverity.REQUIRED, RuleSeverity.STRONG} else 1
        counter_example_limit = 1 if rule.severity in {RuleSeverity.REQUIRED, RuleSeverity.STRONG} else 0

        if rule.examples:
            lines.append("\n**示例：**\n")
            for example in rule.examples[:example_limit]:
                lines.append(f"- {example}\n")

        if counter_example_limit and rule.counter_examples:
            lines.append("\n**反例：**\n")
            for counter_example in rule.counter_examples[:counter_example_limit]:
                lines.append(f"- {counter_example}\n")

        return "".join(lines)

    async def record_rule_usage(self, rule_id: str):
        rule = await self._get_custom_rule(rule_id)
        if not rule:
            return

        rule.usage_count += 1
        rule.last_used_at = datetime.now()
        rule.updated_at = datetime.now()

    async def record_rule_set_usage(self, rule_set_id: str):
        rule_set = await self._get_custom_rule_set(rule_set_id)
        if not rule_set:
            return

        rule_set.usage_count += 1
        rule_set.last_used_at = datetime.now()
        rule_set.updated_at = datetime.now()

    async def initialize_system_rules(self, rules: List[WritingRule]):
        for rule in rules:
            if rule.id not in self._rules:
                rule.is_system = True
                self._rules[rule.id] = rule

    async def initialize_system_rule_sets(self, rule_sets: List[WritingRuleSet]):
        for rule_set in rule_sets:
            if rule_set.id not in self._rule_sets:
                rule_set.is_system = True
                self._rule_sets[rule_set.id] = rule_set


_writing_rule_service: Optional[WritingRuleService] = None


def get_writing_rule_service() -> WritingRuleService:
    global _writing_rule_service
    if _writing_rule_service is None:
        _writing_rule_service = WritingRuleService()
    return _writing_rule_service
