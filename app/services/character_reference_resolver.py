"""Commercial-grade lore-to-character reference resolution.

This service is the single backend authority for turning weak character
references from lore payloads into canonical character UUID links, while
preserving unresolved or ambiguous references as explicit review metadata.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


@dataclass(frozen=True)
class CharacterReferenceResolution:
    """Resolved canonical links plus explicit unresolved review items."""

    related_characters: List[str]
    related_character_refs: List[Dict[str, Any]]
    unresolved_character_refs: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "related_characters": self.related_characters,
            "related_character_refs": self.related_character_refs,
            "unresolved_character_refs": self.unresolved_character_refs,
            "has_unresolved": bool(self.unresolved_character_refs),
        }


class CharacterReferenceResolver:
    """Resolve lore character references within a single project boundary."""

    def __init__(self, db: Any):
        self.db = db

    async def resolve_for_lore(
        self,
        *,
        project_id: str,
        references: Iterable[Any],
        provenance: Optional[Dict[str, Any]] = None,
    ) -> CharacterReferenceResolution:
        normalized_refs = self._normalize_references(references)
        if not normalized_refs:
            return CharacterReferenceResolution([], [], [])

        characters = await self._load_project_characters(project_id)
        by_id, by_name, by_alias = self._build_indexes(characters)

        canonical_ids: List[str] = []
        resolved: List[Dict[str, Any]] = []
        unresolved: List[Dict[str, Any]] = []
        provenance_payload = provenance or {}

        for ref in normalized_refs:
            source_text = ref["source_text"]
            source_payload = ref.get("source_payload") or source_text
            resolution = await self._resolve_one(
                project_id=project_id,
                source_text=source_text,
                source_payload=source_payload,
                by_id=by_id,
                by_name=by_name,
                by_alias=by_alias,
                characters=characters,
                provenance=provenance_payload,
            )
            if resolution.get("status") == "resolved":
                character_id = resolution["character_id"]
                if character_id not in canonical_ids:
                    canonical_ids.append(character_id)
                    resolved.append(resolution)
            else:
                unresolved.append(resolution)

        return CharacterReferenceResolution(canonical_ids, resolved, unresolved)

    async def persist_lore_resolution(
        self,
        *,
        lore_id: str,
        project_id: str,
        resolution: CharacterReferenceResolution,
    ) -> None:
        if hasattr(self.db, "save_lore_character_reference_resolution"):
            await self.db.save_lore_character_reference_resolution(
                lore_id=lore_id,
                project_id=project_id,
                resolution=resolution.to_dict(),
            )

    async def _resolve_one(
        self,
        *,
        project_id: str,
        source_text: str,
        source_payload: Any,
        by_id: Dict[str, Dict[str, Any]],
        by_name: Dict[str, List[Dict[str, Any]]],
        by_alias: Dict[str, List[Tuple[Dict[str, Any], str]]],
        characters: List[Dict[str, Any]],
        provenance: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self._is_uuid(source_text):
            character = by_id.get(source_text)
            if character:
                return self._resolved(source_text, source_payload, character, "id", 1.0, provenance)

            external_character = None
            if hasattr(self.db, "get_character"):
                external_character = await self.db.get_character(source_text)
            if external_character and str(external_character.get("project_id")) != str(project_id):
                return self._unresolved(
                    source_text,
                    source_payload,
                    "cross_project_reference",
                    "角色 ID 存在但不属于当前项目，不能建立跨项目设定关联。",
                    [],
                    provenance,
                )
            return self._unresolved(
                source_text,
                source_payload,
                "character_id_not_found",
                "未找到该角色 ID 对应的当前项目角色。",
                [],
                provenance,
            )

        key = self._match_key(source_text)
        name_matches = by_name.get(key, [])
        if len(name_matches) == 1:
            return self._resolved(source_text, source_payload, name_matches[0], "exact_name", 0.98, provenance)
        if len(name_matches) > 1:
            return self._unresolved(
                source_text,
                source_payload,
                "ambiguous_name",
                "找到多个同名角色，需要用户确认绑定哪一个。",
                [self._candidate(item, "exact_name", 0.98) for item in name_matches],
                provenance,
            )

        alias_matches = by_alias.get(key, [])
        unique_alias_matches = self._unique_by_id([item[0] for item in alias_matches])
        if len(unique_alias_matches) == 1:
            character = unique_alias_matches[0]
            alias = next((alias for item, alias in alias_matches if str(item.get("id")) == str(character.get("id"))), source_text)
            return self._resolved(source_text, source_payload, character, "exact_alias", 0.95, {**provenance, "matched_alias": alias})
        if len(unique_alias_matches) > 1:
            return self._unresolved(
                source_text,
                source_payload,
                "ambiguous_alias",
                "找到多个角色别名匹配，需要用户确认绑定哪一个。",
                [self._candidate(item, "exact_alias", 0.95) for item in unique_alias_matches],
                provenance,
            )

        candidates = self._deterministic_candidates(source_text, characters)
        return self._unresolved(
            source_text,
            source_payload,
            "no_deterministic_match",
            "当前项目中没有可确定绑定的角色；可选择绑定候选角色、创建新角色或保留为文本引用。",
            candidates,
            provenance,
        )

    async def _load_project_characters(self, project_id: str) -> List[Dict[str, Any]]:
        if hasattr(self.db, "get_characters_for_reference_resolution"):
            return await self.db.get_characters_for_reference_resolution(project_id)
        return await self.db.get_all_characters(project_id=project_id, limit=1000)

    def _normalize_references(self, references: Iterable[Any]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for value in references or []:
            source_text = self._reference_text(value)
            if not source_text:
                continue
            dedupe_key = self._match_key(source_text)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            result.append({"source_text": source_text, "source_payload": value})
        return result

    def _reference_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in ("character_id", "id", "name", "title", "source_text", "reference"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
        return ""

    def _build_indexes(
        self,
        characters: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, List[Tuple[Dict[str, Any], str]]]]:
        by_id: Dict[str, Dict[str, Any]] = {}
        by_name: Dict[str, List[Dict[str, Any]]] = {}
        by_alias: Dict[str, List[Tuple[Dict[str, Any], str]]] = {}
        for character in characters:
            character_id = str(character.get("id") or "").strip()
            if character_id:
                by_id[character_id] = character
            name = str(character.get("name") or "").strip()
            if name:
                by_name.setdefault(self._match_key(name), []).append(character)
            for alias in self._parse_aliases(character.get("aliases")):
                by_alias.setdefault(self._match_key(alias), []).append((character, alias))
        return by_id, by_name, by_alias

    def _parse_aliases(self, value: Any) -> List[str]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                value = []
        if not isinstance(value, list):
            return []
        aliases = []
        seen = set()
        for item in value:
            alias = str(item).strip()
            if alias and self._match_key(alias) not in seen:
                seen.add(self._match_key(alias))
                aliases.append(alias)
        return aliases

    def _resolved(
        self,
        source_text: str,
        source_payload: Any,
        character: Dict[str, Any],
        method: str,
        confidence: float,
        provenance: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "status": "resolved",
            "source_text": source_text,
            "source_payload": source_payload,
            "character_id": str(character.get("id")),
            "character_name": character.get("name") or "",
            "confidence": confidence,
            "resolution_method": method,
            "provenance": provenance,
        }

    def _unresolved(
        self,
        source_text: str,
        source_payload: Any,
        reason: str,
        message: str,
        candidates: List[Dict[str, Any]],
        provenance: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "status": "unresolved" if not reason.startswith("ambiguous") else "ambiguous",
            "source_text": source_text,
            "source_payload": source_payload,
            "reason": reason,
            "message": message,
            "candidates": candidates,
            "recommended_actions": ["bind_existing", "create_character", "keep_text_only", "ignore"],
            "provenance": provenance,
        }

    def _candidate(self, character: Dict[str, Any], reason: str, confidence: float) -> Dict[str, Any]:
        return {
            "character_id": str(character.get("id")),
            "name": character.get("name") or "",
            "role": character.get("role") or "",
            "importance_tier": character.get("importance_tier") or "",
            "description": character.get("description") or "",
            "match_reason": reason,
            "confidence": confidence,
        }

    def _deterministic_candidates(self, source_text: str, characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        key = self._match_key(source_text)
        if not key:
            return []
        candidates: List[Dict[str, Any]] = []
        for character in characters:
            names = [str(character.get("name") or ""), *self._parse_aliases(character.get("aliases"))]
            for name in names:
                name_key = self._match_key(name)
                if not name_key:
                    continue
                if key in name_key or name_key in key:
                    confidence = 0.72 if key in name_key else 0.68
                    candidates.append(self._candidate(character, "deterministic_partial", confidence))
                    break
        return self._unique_candidates(candidates)[:5]

    def _unique_by_id(self, characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        seen = set()
        for character in characters:
            character_id = str(character.get("id") or "")
            if character_id and character_id not in seen:
                seen.add(character_id)
                result.append(character)
        return result

    def _unique_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        seen = set()
        for candidate in sorted(candidates, key=lambda item: item.get("confidence", 0), reverse=True):
            character_id = candidate.get("character_id")
            if character_id and character_id not in seen:
                seen.add(character_id)
                result.append(candidate)
        return result

    def _match_key(self, value: str) -> str:
        return re.sub(r"\s+", "", str(value or "").strip().casefold())

    def _is_uuid(self, value: str) -> bool:
        if not UUID_RE.match(value or ""):
            return False
        try:
            uuid.UUID(value)
            return True
        except ValueError:
            return False


def get_character_reference_resolver(db: Any) -> CharacterReferenceResolver:
    return CharacterReferenceResolver(db)
