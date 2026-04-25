"""
服务层包
"""

__all__ = ["DirectorSystem", "NovelFileManager", "ChapterInfo"]


def __getattr__(name):
    if name == "DirectorSystem":
        from app.services.director import DirectorSystem

        return DirectorSystem
    if name in {"NovelFileManager", "ChapterInfo"}:
        from app.services.novel_file_manager import ChapterInfo, NovelFileManager

        return {"NovelFileManager": NovelFileManager, "ChapterInfo": ChapterInfo}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
