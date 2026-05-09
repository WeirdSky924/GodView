"""Filesystem-backed chapter document storage."""

import hashlib
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings


class ChapterDocumentStorage:
    """Stores chapter content as local files and returns DB-safe metadata."""

    def __init__(self, root_dir: Optional[str] = None):
        configured_root = root_dir or getattr(settings, "chapter_document_root", "") or os.getenv(
            "CHAPTER_DOCUMENT_ROOT",
            "data/documents",
        )
        self.root_dir = Path(configured_root).expanduser().resolve()

    def _safe_title(self, title: str) -> str:
        value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "", title or "")
        value = re.sub(r"\s+", "_", value.strip())
        value = re.sub(r"[^\w\-.\u4e00-\u9fff]+", "_", value)
        value = value.strip("._-")
        return (value or "untitled")[:80]

    def _safe_id(self, value: str) -> str:
        try:
            return str(uuid.UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            return re.sub(r"[^a-zA-Z0-9_-]", "_", str(value or "document"))[:80]

    def _project_dir(self, project_id: Optional[str]) -> Path:
        safe_project = self._safe_id(project_id or "unassigned")
        return self.root_dir / "projects" / safe_project / "chapters"

    def _relative_path(self, path: Path) -> str:
        resolved = path.resolve()
        self._assert_under_root(resolved)
        return str(resolved.relative_to(self.root_dir)).replace(os.sep, "/")

    def _resolve_content_path(self, content_path: str) -> Path:
        if not content_path:
            raise ValueError("章节文件路径为空")
        candidate = Path(content_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.root_dir / candidate).resolve()
        self._assert_under_root(resolved)
        return resolved

    def _assert_under_root(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self.root_dir)
        except ValueError as exc:
            raise ValueError("章节文件路径越界") from exc

    def _metadata(self, path: Path, content: str) -> Dict[str, Any]:
        encoded = content.encode("utf-8")
        return {
            "content_path": self._relative_path(path),
            "content_storage": "filesystem",
            "content_size_bytes": len(encoded),
            "content_checksum": hashlib.sha256(encoded).hexdigest(),
        }

    def _target_path(self, chapter_id: str, project_id: Optional[str], title: str) -> Path:
        filename = f"{self._safe_id(chapter_id)}__{self._safe_title(title)}.md"
        return self._project_dir(project_id) / filename

    def write_chapter(
        self,
        chapter_id: str,
        project_id: Optional[str],
        title: str,
        content: str,
        existing_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        target = self._resolve_content_path(existing_path) if existing_path else self._target_path(chapter_id, project_id, title)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._assert_under_root(target)

        tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        return self._metadata(target, content)

    def read_chapter_content(self, content_path: str) -> str:
        path = self._resolve_content_path(content_path)
        return path.read_text(encoding="utf-8")

    def rename_chapter(
        self,
        old_path: str,
        chapter_id: str,
        project_id: Optional[str],
        new_title: str,
    ) -> Dict[str, Any]:
        source = self._resolve_content_path(old_path)
        target = self._target_path(chapter_id, project_id, new_title)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._assert_under_root(target)

        if source.exists() and source != target:
            os.replace(source, target)
        elif not source.exists() and not target.exists():
            raise FileNotFoundError(f"章节文件不存在: {old_path}")

        content = target.read_text(encoding="utf-8") if target.exists() else ""
        return self._metadata(target, content)

    def delete_chapter_file(self, content_path: Optional[str]) -> bool:
        if not content_path:
            return False
        path = self._resolve_content_path(content_path)
        if not path.exists():
            return False
        path.unlink()
        return True

    def archive_deleted_chapter_file(self, content_path: Optional[str]) -> Optional[str]:
        """Rename a deleted chapter file so DB index removal does not erase local content."""
        if not content_path:
            return None
        source = self._resolve_content_path(content_path)
        if not source.exists():
            return None
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        base_name = source.stem
        suffix = source.suffix or ".md"
        target = source.with_name(f"{base_name}__deleted_{timestamp}{suffix}")
        counter = 1
        while target.exists():
            target = source.with_name(f"{base_name}__deleted_{timestamp}_{counter}{suffix}")
            counter += 1
        self._assert_under_root(target)
        os.replace(source, target)
        return self._relative_path(target)

    def hydrate_chapter(self, row: Dict[str, Any]) -> Dict[str, Any]:
        hydrated = dict(row)
        if (hydrated.get("content_storage") == "filesystem" or hydrated.get("content_path")) and hydrated.get("content_path"):
            hydrated["content"] = self.read_chapter_content(str(hydrated["content_path"]))
        return hydrated


chapter_document_storage = ChapterDocumentStorage()
