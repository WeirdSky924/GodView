"""
小说文件管理 - 章节存储与总文本合并
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ChapterInfo:
    """章节信息"""
    number: int
    title: str
    file_path: Path
    word_count: int
    created_at: str
    content: str = ""


class NovelFileManager:
    """小说文件管理器 - 管理章节文件和总文本"""

    def __init__(self, output_dir: str, novel_name: str = "untitled"):
        """
        初始化

        Args:
            output_dir: 输出根目录
            novel_name: 小说名称
        """
        self.novel_name = self._sanitize_filename(novel_name)
        self.output_dir = Path(output_dir) / self.novel_name
        self.chapters_dir = self.output_dir / "chapters"
        self.master_file = self.output_dir / f"{self.novel_name}.txt"
        self.metadata_file = self.output_dir / "metadata.txt"

        # 确保目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chapters_dir.mkdir(exist_ok=True)

        logger.info(f"小说文件管理器初始化：{self.output_dir}")

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名中的非法字符"""
        # 移除 Windows 文件名非法字符
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        return name.strip()

    def _format_chapter_filename(self, number: int, title: str) -> str:
        """格式化章节文件名"""
        safe_title = self._sanitize_filename(title)
        return f"第{number:03d}章_{safe_title}.txt"

    async def save_chapter(
        self,
        number: int,
        title: str,
        content: str,
    ) -> ChapterInfo:
        """
        保存章节到独立文件

        Args:
            number: 章节序号
            title: 章节标题
            content: 章节正文内容

        Returns:
            ChapterInfo: 章节信息
        """
        filename = self._format_chapter_filename(number, title)
        file_path = self.chapters_dir / filename

        # 写入章节文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 更新主文件
        await self._update_master_file(number, title, content)

        # 更新元数据
        await self._update_metadata()

        info = ChapterInfo(
            number=number,
            title=title,
            file_path=file_path,
            word_count=len(content),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            content=content,
        )

        logger.info(f"章节已保存：{filename} ({len(content)} 字)")
        return info

    async def _update_master_file(
        self,
        number: int,
        title: str,
        content: str,
    ):
        """
        更新总小说文本文件

        策略：读取现有内容，在末尾追加新章节
        """
        separator = "=" * 60

        # 读取现有内容（如果有）
        if self.master_file.exists():
            with open(self.master_file, "r", encoding="utf-8") as f:
                existing = f.read()
        else:
            # 首次创建，写入标题
            existing = f"《{self.novel_name}》\n{separator}\n\n"

        # 追加新章节
        chapter_header = f"\n\n{separator}\n第{number}章 {title}\n{separator}\n\n"
        new_content = existing + chapter_header + content

        # 写入总文件
        with open(self.master_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        logger.info(f"总文本已更新：{self.master_file}")

    async def _update_metadata(self):
        """更新元数据文件"""
        chapters = self.list_chapters()

        with open(self.metadata_file, "w", encoding="utf-8") as f:
            f.write(f"小说：{self.novel_name}\n")
            f.write(f"总章节数：{len(chapters)}\n")
            f.write(f"总字数：{sum(c.word_count for c in chapters)}\n")
            f.write(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 40 + "\n")
            for ch in chapters:
                f.write(f"  第{ch.number:03d}章 {ch.title} ({ch.word_count}字)\n")

    def list_chapters(self) -> List[ChapterInfo]:
        """
        列出所有章节

        Returns:
            List[ChapterInfo]: 章节信息列表
        """
        chapters = []

        if not self.chapters_dir.exists():
            return chapters

        for file_path in sorted(self.chapters_dir.glob("*.txt")):
            # 解析文件名 "第001章_标题.txt"
            match = re.match(r"第(\d+)章_(.+)\.txt", file_path.name)
            if match:
                number = int(match.group(1))
                title = match.group(2)
                content = file_path.read_text(encoding="utf-8")
                chapters.append(ChapterInfo(
                    number=number,
                    title=title,
                    file_path=file_path,
                    word_count=len(content),
                    created_at=datetime.fromtimestamp(
                        file_path.stat().st_mtime
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    content=content,
                ))

        return chapters

    def get_chapter_content(self, number: int) -> Optional[str]:
        """
        获取指定章节内容

        Args:
            number: 章节序号

        Returns:
            Optional[str]: 章节内容
        """
        chapters = self.list_chapters()
        for ch in chapters:
            if ch.number == number:
                return ch.content
        return None

    def get_master_content(self) -> Optional[str]:
        """
        获取总小说文本

        Returns:
            Optional[str]: 总文本内容
        """
        if self.master_file.exists():
            return self.master_file.read_text(encoding="utf-8")
        return None

    def regenerate_master_file(self):
        """
        从所有章节重新生成总文件（确保顺序和一致性）
        """
        chapters = self.list_chapters()
        separator = "=" * 60

        content = f"《{self.novel_name}》\n{separator}\n\n"

        for ch in chapters:
            chapter_header = f"\n\n{separator}\n第{ch.number}章 {ch.title}\n{separator}\n\n"
            content += chapter_header + ch.content

        with open(self.master_file, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"总文本已从 {len(chapters)} 个章节重新生成")

    def delete_chapter(self, number: int) -> bool:
        """
        删除指定章节（并从总文件移除）

        Args:
            number: 章节序号

        Returns:
            bool: 是否成功
        """
        chapters = self.list_chapters()
        target = None
        for ch in chapters:
            if ch.number == number:
                target = ch
                break

        if not target:
            return False

        # 删除章节文件
        target.file_path.unlink()

        # 重新生成总文件
        self.regenerate_master_file()

        logger.info(f"已删除章节 {number} 并重新生成总文本")
        return True
