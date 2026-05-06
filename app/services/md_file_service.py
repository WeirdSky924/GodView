"""
MD 文件读取服务
从 prompts/ 和 skills/ 目录读取 Markdown 文件

设计理念：
- MD 文件存储内容（Git 可版本化，无编码问题）
- 数据库存储元数据和向量（用于搜索）
- 分离存储，统一服务

文件格式：
```md
---
id: skill_xxx
name: 技能名称
description: 描述
category: writing
# ... 其他 YAML 元数据
---

# 技能内容

这里是实际的 Prompt 内容...
```
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
SKILLS_DIR = PROJECT_ROOT / "skills"


class MDFileService:
    """MD 文件读取服务"""

    def __init__(self):
        # 内容缓存
        self._prompts_cache: Dict[str, Dict[str, Any]] = {}
        self._skills_cache: Dict[str, Dict[str, Any]] = {}
        self._scan_errors: List[Dict[str, str]] = []
        self._cache_valid: bool = False

        # 目录路径
        self.prompts_dir = PROMPTS_DIR
        self.skills_dir = SKILLS_DIR

    def _relative_path(self, file_path: Path) -> str:
        try:
            return str(file_path.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(file_path)

    def _record_scan_error(self, file_path: Path, error: str):
        self._scan_errors.append({
            'file_path': self._relative_path(file_path),
            'error': error,
        })

    def _parse_frontmatter(self, content: str, file_path: Optional[Path] = None) -> Tuple[Dict[str, Any], str, Optional[str]]:
        """
        解析 YAML frontmatter

        Args:
            content: MD 文件内容

        Returns:
            Tuple[frontmatter, body]
        """
        # 匹配 --- 包裹的 frontmatter
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)

        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1))
                if frontmatter is not None and not isinstance(frontmatter, dict):
                    return {}, content, "YAML frontmatter must be a mapping/object"
                body = match.group(2).strip()
                return frontmatter or {}, body, None
            except yaml.YAMLError as e:
                logger.warning(f"解析 YAML frontmatter 失败 {file_path or ''}: {e}")
                return {}, content, str(e)

        return {}, content, "Missing YAML frontmatter block"

    def _load_md_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        加载单个 MD 文件

        Args:
            file_path: 文件路径

        Returns:
            Dict: 包含 frontmatter 和 content 的字典
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            frontmatter, body, parse_error = self._parse_frontmatter(content, file_path)
            if parse_error:
                self._record_scan_error(file_path, parse_error)

            return {
                'file_path': self._relative_path(file_path),
                'frontmatter': frontmatter,
                'content': body,
                'raw_content': content,
                'parse_error': parse_error,
            }
        except Exception as e:
            logger.error(f"读取 MD 文件失败 {file_path}: {e}")
            self._record_scan_error(file_path, str(e))
            return None

    def _scan_directory(self, directory: Path) -> List[Path]:
        """
        扫描目录下的所有 MD 文件

        Args:
            directory: 目录路径

        Returns:
            List[Path]: MD 文件路径列表
        """
        if not directory.exists():
            logger.warning(f"目录不存在: {directory}")
            return []

        return list(directory.rglob("*.md"))

    def _ensure_cache(self):
        """确保缓存有效"""
        if self._cache_valid:
            return

        self._scan_errors.clear()

        # 扫描 prompts 目录
        prompts_files = self._scan_directory(self.prompts_dir)
        for file_path in prompts_files:
            data = self._load_md_file(file_path)
            if data and data['frontmatter']:
                # 使用 frontmatter 中的 id 或文件名作为 key
                prompt_id = data['frontmatter'].get('id') or file_path.stem
                self._prompts_cache[prompt_id] = data

        # 扫描 skills 目录
        skills_files = self._scan_directory(self.skills_dir)
        for file_path in skills_files:
            data = self._load_md_file(file_path)
            if data and data['frontmatter']:
                skill_id = data['frontmatter'].get('id') or file_path.stem
                self._skills_cache[skill_id] = data

        self._cache_valid = True
        logger.info(
            f"MD 文件缓存加载完成: {len(self._prompts_cache)} 个 Prompts, "
            f"{len(self._skills_cache)} 个 Skills"
        )

    def invalidate_cache(self):
        """使缓存失效"""
        self._cache_valid = False
        self._prompts_cache.clear()
        self._skills_cache.clear()
        self._scan_errors.clear()

    def get_scan_errors(self) -> List[Dict[str, str]]:
        """获取最近一次扫描中发现的文件级错误。"""
        self._ensure_cache()
        return list(self._scan_errors)

    # ==================== Prompt 相关方法 ====================

    def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个 Prompt

        Args:
            prompt_id: Prompt ID

        Returns:
            Dict: 包含 frontmatter 和 content 的字典
        """
        self._ensure_cache()
        return self._prompts_cache.get(prompt_id)

    def get_prompt_content(self, prompt_id: str) -> Optional[str]:
        """
        获取 Prompt 的内容（不含 frontmatter）

        Args:
            prompt_id: Prompt ID

        Returns:
            str: Prompt 内容
        """
        data = self.get_prompt(prompt_id)
        return data['content'] if data else None

    def list_prompts(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取 Prompt 列表

        Args:
            category: 分类过滤
            tags: 标签过滤

        Returns:
            List[Dict]: Prompt 列表
        """
        self._ensure_cache()
        results = []

        for prompt_id, data in self._prompts_cache.items():
            fm = data['frontmatter']

            # 分类过滤
            if category and fm.get('category') != category:
                continue

            # 标签过滤
            if tags:
                prompt_tags = fm.get('tags', [])
                if not any(tag in prompt_tags for tag in tags):
                    continue

            results.append({
                'id': prompt_id,
                **fm,
                'content': data['content'],
                'file_path': data['file_path'],
            })

        return results

    def get_prompts_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        按分类获取 Prompts

        Args:
            category: 分类名称

        Returns:
            List[Dict]: Prompt 列表
        """
        return self.list_prompts(category=category)

    # ==================== Skill 相关方法 ====================

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个 Skill

        Args:
            skill_id: Skill ID

        Returns:
            Dict: 包含 frontmatter 和 content 的字典
        """
        self._ensure_cache()
        return self._skills_cache.get(skill_id)

    def get_skill_content(self, skill_id: str) -> Optional[str]:
        """
        获取 Skill 的内容（不含 frontmatter）

        Args:
            skill_id: Skill ID

        Returns:
            str: Skill 内容
        """
        data = self.get_skill(skill_id)
        return data['content'] if data else None

    def list_skills(
        self,
        category: Optional[str] = None,
        skill_type: Optional[str] = None,
        applicable_agent_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取 Skill 列表

        Args:
            category: 分类过滤
            skill_type: 技能类型过滤
            applicable_agent_types: 适用 Agent 类型过滤
            tags: 标签过滤

        Returns:
            List[Dict]: Skill 列表
        """
        self._ensure_cache()
        results = []

        for skill_id, data in self._skills_cache.items():
            fm = data['frontmatter']

            # 分类过滤
            if category and fm.get('category') != category:
                continue

            # 技能类型过滤
            if skill_type and fm.get('skill_type') != skill_type:
                continue

            # 适用 Agent 类型过滤
            if applicable_agent_types:
                skill_applicable = fm.get('applicable_agent_types', [])
                # 空列表表示所有 Agent 都可用
                if skill_applicable and not any(
                    agent in skill_applicable for agent in applicable_agent_types
                ):
                    continue

            # 标签过滤
            if tags:
                skill_tags = fm.get('tags', [])
                if not any(tag in skill_tags for tag in tags):
                    continue

            results.append({
                'id': skill_id,
                **fm,
                'content': data['content'],
                'file_path': data['file_path'],
            })

        return results

    def get_skills_for_agent(self, agent_type: str) -> List[Dict[str, Any]]:
        """
        获取适用于指定 Agent 类型的 Skills

        Args:
            agent_type: Agent 类型

        Returns:
            List[Dict]: Skill 列表
        """
        return self.list_skills(applicable_agent_types=[agent_type])

    def get_core_skills_for_agent(self, agent_type: str) -> List[Dict[str, Any]]:
        """
        获取 Agent 的核心层 Skills（load_mode = core）

        Args:
            agent_type: Agent 类型

        Returns:
            List[Dict]: 核心 Skill 列表
        """
        skills = self.get_skills_for_agent(agent_type)
        return [s for s in skills if s.get('load_mode') == 'core']

    def get_on_demand_skills_for_agent(self, agent_type: str) -> List[Dict[str, Any]]:
        """
        获取 Agent 的按需层 Skills（load_mode = on_demand）

        Args:
            agent_type: Agent 类型

        Returns:
            List[Dict]: 按需 Skill 列表
        """
        skills = self.get_skills_for_agent(agent_type)
        return [s for s in skills if s.get('load_mode') != 'core']

    # ==================== 搜索相关方法 ====================

    def search_prompts(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        简单文本搜索 Prompts（用于无向量搜索时的回退）

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[Dict]: 匹配的 Prompt 列表
        """
        self._ensure_cache()
        query_lower = query.lower()
        results = []

        for prompt_id, data in self._prompts_cache.items():
            fm = data['frontmatter']
            content = data['content']

            # 计算匹配分数
            score = 0
            name = fm.get('name', '')
            description = fm.get('description', '')

            if query_lower in name.lower():
                score += 10
            if query_lower in description.lower():
                score += 5
            if query_lower in content.lower():
                score += 3

            if score > 0:
                results.append((score, {
                    'id': prompt_id,
                    **fm,
                    'content': content,
                    'match_score': score,
                }))

        # 按分数降序排序
        results.sort(key=lambda x: -x[0])
        return [r for _, r in results[:limit]]

    def search_skills(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        简单文本搜索 Skills（用于无向量搜索时的回退）

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[Dict]: 匹配的 Skill 列表
        """
        self._ensure_cache()
        query_lower = query.lower()
        results = []

        for skill_id, data in self._skills_cache.items():
            fm = data['frontmatter']
            content = data['content']

            # 计算匹配分数
            score = 0
            name = fm.get('name', '')
            description = fm.get('description', '')

            if query_lower in name.lower():
                score += 10
            if query_lower in description.lower():
                score += 5
            if query_lower in content.lower():
                score += 3

            if score > 0:
                results.append((score, {
                    'id': skill_id,
                    **fm,
                    'content': content,
                    'match_score': score,
                }))

        # 按分数降序排序
        results.sort(key=lambda x: -x[0])
        return [r for _, r in results[:limit]]

    # ==================== 统计方法 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        self._ensure_cache()

        prompt_categories = {}
        for data in self._prompts_cache.values():
            cat = data['frontmatter'].get('category', 'unknown')
            prompt_categories[cat] = prompt_categories.get(cat, 0) + 1

        skill_categories = {}
        skill_types = {}
        for data in self._skills_cache.values():
            fm = data['frontmatter']
            cat = fm.get('category', 'unknown')
            st = fm.get('skill_type', 'unknown')
            skill_categories[cat] = skill_categories.get(cat, 0) + 1
            skill_types[st] = skill_types.get(st, 0) + 1

        return {
            'prompts': {
                'total': len(self._prompts_cache),
                'by_category': prompt_categories,
            },
            'skills': {
                'total': len(self._skills_cache),
                'by_category': skill_categories,
                'by_type': skill_types,
            },
            'errors': list(self._scan_errors),
        }


# 全局单例
_md_file_service: Optional[MDFileService] = None


def get_md_file_service() -> MDFileService:
    """获取 MDFileService 单例"""
    global _md_file_service
    if _md_file_service is None:
        _md_file_service = MDFileService()
    return _md_file_service


def invalidate_md_cache():
    """使 MD 文件缓存失效"""
    global _md_file_service
    if _md_file_service:
        _md_file_service.invalidate_cache()
